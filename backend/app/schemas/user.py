from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from backend.app.core.security import BCRYPT_MAX_PASSWORD_BYTES


COMMON_PASSWORDS = {
    "12345678",
    "password",
    "password1",
    "qwerty123",
    "admin123",
}


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError("Password must be at most 72 bytes when UTF-8 encoded.")
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError("Password is too common.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must include one uppercase letter.")
        if not any(char.isdigit() or not char.isalnum() for char in value):
            raise ValueError("Password must include one number or symbol.")
        return value


class UserRead(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SessionExchangeRequest(BaseModel):
    email: EmailStr
    provider: str
    provider_account_id: str
    full_name: Optional[str] = None
    secret: str


class UserConfigBase(BaseModel):
    config_type: str
    config_data: Dict[str, Any]


class UserConfigCreate(UserConfigBase):
    pass


class UserConfigRead(UserConfigBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class SourceGroupPreviewRequest(BaseModel):
    chat: str


class DestinationChannelBase(BaseModel):
    chat_id: str
    title: Optional[str] = None
    chat_type: str = "channel"
    enabled: bool = True


class DestinationChannelCreate(DestinationChannelBase):
    pass


class DestinationChannelRead(DestinationChannelBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
