from datetime import datetime
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from backend.app.core.security import BCRYPT_MAX_PASSWORD_BYTES
from backend.app.core.offer_categories import OfferCategory


COMMON_PASSWORDS = {
    "12345678",
    "password",
    "password1",
    "qwerty123",
    "admin123",
}


class UserBase(BaseModel):
    """Shared public profile fields for user request and response models."""

    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Credentials registration payload with password policy validation."""

    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Enforce length, strength, and bcrypt-compatible password constraints."""
        if len(value) < 8:
            raise ValueError("Use uma senha com pelo menos 8 caracteres.")
        if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
            raise ValueError(
                "Sua senha ficou muito longa. Reduza a quantidade de caracteres."
            )
        if value.lower() in COMMON_PASSWORDS:
            raise ValueError(
                "Essa senha é muito comum. Escolha uma senha mais difícil."
            )
        if not any(char.isupper() for char in value):
            raise ValueError("Inclua uma letra maiúscula na senha.")
        if not any(char.isdigit() or not char.isalnum() for char in value):
            raise ValueError("Inclua um número ou símbolo na senha.")
        return value


class UserRead(UserBase):
    """Safe user response excluding password and authentication secrets."""

    id: int
    created_at: datetime
    role: Literal["user", "admin"] = "user"
    model_config = ConfigDict(from_attributes=True)

    @field_validator("role", mode="before")
    @classmethod
    def default_role(cls, value):
        return value or "user"


class SessionExchangeRequest(BaseModel):
    """Trusted frontend session data used to create or update external identity."""

    email: EmailStr
    provider: str
    provider_account_id: str
    full_name: Optional[str] = None
    secret: str


class UserConfigBase(BaseModel):
    """Serialized user-owned routing or affiliate provider configuration."""

    config_type: str
    config_data: Dict[str, Any]


class UserConfigCreate(UserConfigBase):
    """Payload for creating or replacing user configuration."""

    pass


class UserConfigRead(UserConfigBase):
    """Persisted user configuration response."""

    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class SourceGroupPreviewRequest(BaseModel):
    """Public Telegram chat identifier submitted for preview."""

    chat: str


class DestinationChannelBase(BaseModel):
    """Group/channel destination metadata for Telegram or linked WhatsApp account."""

    chat_id: str
    title: Optional[str] = None
    chat_type: str = "channel"
    enabled: bool = True
    platform: Literal["telegram", "whatsapp"] = "telegram"
    categories: list[OfferCategory] | None = None
    connection_id: int | None = None

    @model_validator(mode="after")
    def validate_platform_chat(self):
        if self.connection_id is not None and (
            self.connection_id < 1 or self.platform != "whatsapp"
        ):
            raise ValueError("Conexão válida é permitida somente para WhatsApp.")
        if self.platform == "whatsapp":
            from backend.app.core.whatsapp import GROUP_ID, CHANNEL_ID

            pattern = {"group": GROUP_ID, "channel": CHANNEL_ID}.get(self.chat_type)
            if pattern is None or not pattern.fullmatch(self.chat_id):
                raise ValueError("Selecione um grupo ou canal válido do WhatsApp.")
        elif self.chat_id.endswith(("@g.us", "@newsletter")):
            raise ValueError("Destino WhatsApp não pode ser um destino Telegram.")
        return self


class DestinationChannelCreate(DestinationChannelBase):
    """Payload for creating or replacing a user-owned publication destination."""

    pass


class DestinationChannelRead(DestinationChannelBase):
    """Persisted publication destination response."""

    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Credentials login payload."""

    email: str
    password: str


class Token(BaseModel):
    """Bearer access token response."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """JWT identity claims needed to load authenticated user."""

    email: Optional[str] = None
