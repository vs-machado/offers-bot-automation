"""Validate Better Auth sessions; application permissions remain database-owned."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import get_db
from backend.app.models.better_auth import AuthUser, AuthSession
from backend.app.models.user import User

session_scheme = HTTPBearer(auto_error=False, scheme_name="BetterAuthSession")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(session_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Check the opaque session in PostgreSQL on every request, including revocations."""
    invalid = HTTPException(
        status_code=401,
        detail="Sua sessão expirou ou foi encerrada. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise invalid
    token = credentials.credentials
    if not 16 <= len(token) <= 256:
        raise invalid
    result = await db.execute(
        select(AuthUser)
        .join(AuthSession, AuthSession.user_id == AuthUser.id)
        .where(AuthSession.token == token, AuthSession.expires_at > func.now())
    )
    identity = result.scalar_one_or_none()
    if identity is None:
        raise invalid
    result = await db.execute(select(User).where(User.auth_user_id == identity.id))
    user = result.scalar_one_or_none()
    if user is None:
        # Stable session identity binds ownership; client-provided email cannot select a user.
        await db.execute(
            insert(User)
            .values(
                auth_user_id=identity.id,
                email=identity.email,
                full_name=identity.name,
                auth_provider="better_auth",
                role="user",
            )
            .on_conflict_do_nothing(index_elements=["auth_user_id"])
        )
        await db.commit()
        result = await db.execute(select(User).where(User.auth_user_id == identity.id))
        user = result.scalar_one_or_none()
    if user is None:
        raise invalid
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Read current application role; session or request fields cannot grant admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Você não tem permissão para acessar essa página."
        )
    return current_user
