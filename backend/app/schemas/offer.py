from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
