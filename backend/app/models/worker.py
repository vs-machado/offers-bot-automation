from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.db.base import Base


class ProcessedOffer(Base):
    """Per-user source and affiliate identities used for deduplication."""

    __tablename__ = "processed_offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_chat: Mapped[str] = mapped_column(String(100))
    source_message_id: Mapped[int]
    source_url: Mapped[str] = mapped_column(String(1000))
    affiliate_url: Mapped[str] = mapped_column(String(1000), nullable=True)
    product_key: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_chat",
            "source_message_id",
            "source_url",
            name="uq_processed_offer",
        ),
    )


class TelegramSession(Base):
    """Persisted Telegram session string associated with one user."""

    __tablename__ = "telegram_sessions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    session_string: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlatformTelegramSession(Base):
    """Shared operator session; independent of individual user accounts."""

    __tablename__ = "platform_telegram_sessions"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    session_string: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TokenUsage(Base):
    """LLM accounting with an optional identity for idempotent legacy import."""

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    prompt_tokens: Mapped[int]
    completion_tokens: Mapped[int]
    total_tokens: Mapped[int]
    legacy_id: Mapped[int | None] = mapped_column(unique=True)


class PromotionDelivery(Base):
    """Delivery audit only; expired rows never regenerate queue payloads."""

    __tablename__ = "promotion_deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[str | None] = mapped_column(String(200))
    affiliate_url: Mapped[str | None] = mapped_column(String(1000))
    platform: Mapped[str | None] = mapped_column(String(50))
    stage: Mapped[str] = mapped_column(String(20), server_default="posting")
    __table_args__ = (
        Index("ix_delivery_user_created", "user_id", "created_at", "id"),
        Index("ix_delivery_routing", "user_id", "chat_id", "created_at"),
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedup_key: Mapped[str | None] = mapped_column(String(64))
    connection_id: Mapped[int | None] = mapped_column(
        ForeignKey("whatsapp_connections.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
