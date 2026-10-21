"""User-owned connections; the primary connection preserves legacy session/state."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.db.base import Base


class WhatsAppConnection(Base):
    __tablename__ = "whatsapp_connections"
    __table_args__ = (
        Index(
            "uq_whatsapp_primary_connection",
            "user_id",
            unique=True,
            postgresql_where=text("is_default = true"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    is_default: Mapped[bool] = mapped_column(default=False, server_default="false")
    config_data: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WhatsAppConnectionState(Base):
    __tablename__ = "whatsapp_connection_states"

    connection_id: Mapped[int] = mapped_column(
        ForeignKey("whatsapp_connections.id", ondelete="CASCADE"), primary_key=True
    )
    chat_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    failures: Mapped[int] = mapped_column(server_default="0")
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pause_reason: Mapped[str | None] = mapped_column(String(100))
