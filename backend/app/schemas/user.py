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


class OfferBase(BaseModel):
    platform: str
    product_url: str
    title: str
    price: str
    currency: str = "BRL"
    affiliate_url: str


class OfferCreate(OfferBase):
    pass


class OfferRead(OfferBase):
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
