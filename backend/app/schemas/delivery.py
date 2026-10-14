"""User-scoped publication history with safe failure messages."""

from datetime import datetime
from pydantic import BaseModel


class DeliveryRead(BaseModel):
    id: str
    title: str | None
    platform: str | None
    chat_id: str
    destination_title: str | None
    status: str
    reason: str | None
    reason_message: str | None
    stage: str
    attempts: int
    created_at: datetime
    updated_at: datetime


class DeliveryHistory(BaseModel):
    items: list[DeliveryRead]
    total: int
    counts: dict[str, int]
