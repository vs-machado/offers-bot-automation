"""User-scoped publication history with safe failure messages."""

from datetime import datetime
from pydantic import BaseModel, Field

from backend.app.core.offer_categories import OfferCategory


class DeliveryRead(BaseModel):
    id: str
    offer_id: str
    title: str | None
    price: str | None
    coupon: str | None = None
    affiliate_url: str | None = None
    platform: str | None
    category: OfferCategory | None = None
    chat_id: str
    destination_title: str | None
    status: str
    reason: str | None
    reason_message: str | None
    stage: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    enqueue_ms: int | None = None


class DeliveryHistory(BaseModel):
    items: list[DeliveryRead]
    total: int
    counts: dict[str, int]


class DeliveryRepost(BaseModel):
    """Destination selected for an explicit owner-triggered repost."""

    chat_id: str = Field(min_length=1, max_length=100)


class DeliveryRepostResult(BaseModel):
    """Accepted manual delivery that bypasses editorial post caps."""

    id: str
    status: str
    chat_id: str
    manual: bool = True
