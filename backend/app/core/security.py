import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

# Configuration from environment
DEV_SECRET_KEY = "super-secret-dev-key-change-this-in-production"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEV_SECRET_KEY)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

BCRYPT_MAX_PASSWORD_BYTES = 72


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
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


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
