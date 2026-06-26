from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserConfigBase(BaseModel):
    config_type: str
    config_data: Dict[str, Any]


class UserConfigCreate(UserConfigBase):
    pass


class UserConfigRead(UserConfigBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)


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
