import os
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import get_db
from backend.app.core.security import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.user import User
from backend.app.schemas.user import (
    LoginRequest,
    SessionExchangeRequest,
    TokenData,
    Token,
    UserCreate,
    UserRead,
)
from jose import JWTError, jwt

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 5
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(action: str, request: Request) -> None:
    now = time.monotonic()
    key = f"{action}:{_client_ip(request)}"
    bucket = _rate_limit_buckets[key]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Você fez muitas tentativas em pouco tempo. Aguarde um minuto e tente novamente.",
        )
    bucket.append(now)


def _token_for_user(user: User) -> Token:
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Decode bearer token and load its user from the database."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sua sessão não é válida. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    statement = select(User).where(User.email == token_data.email)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Check database role on every request; stale JWT claims cannot grant access."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para acessar essa página.",
        )
    return current_user


@router.post("/register", response_model=UserRead)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create credentials-based user after rate-limit and uniqueness checks."""
    _check_rate_limit("register", request)
    statement = select(User).where(User.email == user_data.email)
    result = await db.execute(statement)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este e-mail já está cadastrado. Entre na sua conta ou use outro e-mail.",
        )

    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        auth_provider="credentials",
        role="user",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify credentials and return a signed bearer access token."""
    _check_rate_limit("login", request)
    statement = select(User).where(User.email == body.email)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()

    if (
        not user
        or not user.hashed_password
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _token_for_user(user)


@router.post("/session/exchange", response_model=Token)
async def exchange_session(
    body: SessionExchangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Exchange trusted NextAuth session proof for a backend access token."""
    _check_rate_limit("session-exchange", request)
    expected_secret = os.getenv("NEXTAUTH_BACKEND_SECRET")
    if not expected_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O acesso com o Google não está disponível no momento.",
        )
    if not secrets.compare_digest(body.secret, expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar sua sessão. Entre novamente.",
        )

    statement = select(User).where(User.email == body.email)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=body.email,
            hashed_password=None,
            full_name=body.full_name,
            auth_provider=body.provider,
            role="user",
            provider_account_id=body.provider_account_id,
        )
        db.add(user)
    else:
        user.auth_provider = body.provider
        user.provider_account_id = body.provider_account_id
        if body.full_name and not user.full_name:
            user.full_name = body.full_name

    await db.commit()
    await db.refresh(user)
    return _token_for_user(user)
