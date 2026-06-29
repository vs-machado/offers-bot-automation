import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

# Configuration from environment
DEV_SECRET_KEY = "super-secret-dev-key-change-this-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEV_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_production() -> bool:
    return os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower() in {
        "prod",
        "production",
    }


def validate_auth_config() -> None:
    missing: list[str] = []
    if not os.getenv("JWT_SECRET_KEY") or SECRET_KEY == DEV_SECRET_KEY:
        missing.append("JWT_SECRET_KEY")
    if missing and is_production():
        raise RuntimeError(
            "Missing required production auth settings: " + ", ".join(missing)
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_token
