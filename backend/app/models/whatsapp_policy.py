"""Tenant-owned WhatsApp limits, circuit state and delivery reservations."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db.base import Base


class WhatsAppDeliveryPolicy(Base):
    __tablename__ = "whatsapp_delivery_policies"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    config_data: Mapped[str] = mapped_column(String, server_default="{}")


class WhatsAppDeliveryState(Base):
    __tablename__ = "whatsapp_delivery_states"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    chat_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    failures: Mapped[int] = mapped_column(server_default="0")
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pause_reason: Mapped[str | None] = mapped_column(String(100))


class WhatsAppSendAttempt(Base):
    __tablename__ = "whatsapp_send_attempts"
    __table_args__ = (
        Index("ix_whatsapp_attempt_user_time", "user_id", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[str] = mapped_column(String(100))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("whatsapp_connections.id", ondelete="RESTRICT"), index=True
    )
