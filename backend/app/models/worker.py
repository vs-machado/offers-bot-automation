from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func, UniqueConstraint
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
