"""Durable, owner-scoped website rotation state, separate from offer publishing."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db.base import Base


class WhatsAppWebsite(Base):
    __tablename__ = "whatsapp_websites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    config_data: Mapped[str] = mapped_column(Text)
    active_destination_id: Mapped[int | None] = mapped_column(
        ForeignKey("destination_channels.id", ondelete="SET NULL")
    )
    pending_destination_id: Mapped[int | None] = mapped_column(
        ForeignKey("destination_channels.id", ondelete="SET NULL")
    )
    pending_request_id: Mapped[str | None] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(default=0, server_default="0")
    failures: Mapped[int] = mapped_column(default=0, server_default="0")
    member_count: Mapped[int | None]
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
