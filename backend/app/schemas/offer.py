from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OfferBase(BaseModel):
    """Offer fields shared by create and read payloads."""

    platform: str
    product_url: str
    title: str
    price: str
    currency: str = "BRL"
    affiliate_url: str


class OfferCreate(OfferBase):
    """Payload for manually persisting an offer."""

    pass


class OfferRead(OfferBase):
    """Persisted offer response including ownership and creation metadata."""

    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
