from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.db.base import Base


class User(Base):
    """Application user and relationships to owned automation records."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    auth_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_users.id", ondelete="CASCADE"), unique=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(50), default="credentials")
    role: Mapped[str] = mapped_column(
        String(20), default="user", server_default="user", nullable=False
    )
    provider_account_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    configs: Mapped[List["UserConfig"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    offers: Mapped[List["Offer"]] = relationship(back_populates="user")
    destinations: Mapped[List["DestinationChannel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserConfig(Base):
    """JSON-serialized routing, provider, and resolver settings for one user."""

    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    config_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # 'telegram', 'amazon', etc.
    config_data: Mapped[str] = mapped_column(String)  # JSON string of credentials

    user: Mapped["User"] = relationship(back_populates="configs")


class SourceGroup(Base):
    """Operator-managed Telegram sources available for user subscriptions."""

    __tablename__ = "source_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        default=True, server_default="true", nullable=False
    )


class Offer(Base):
    """Persisted affiliate offer associated with one user."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(50), index=True)
    product_url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(500))
    price: Mapped[str] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10), default="BRL")
    affiliate_url: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="offers")


class DestinationChannel(Base):
    """Telegram or WhatsApp chat where this user's offers may be published."""

    __tablename__ = "destination_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[str] = mapped_column(String(100), index=True)
    platform: Mapped[str] = mapped_column(
        String(20), default="telegram", server_default="telegram", nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    chat_type: Mapped[str] = mapped_column(String(50), default="channel")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="destinations")
