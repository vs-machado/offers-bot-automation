from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    auth_provider: Mapped[str] = mapped_column(String(50), default="credentials")
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


class Offer(Base):
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
    __tablename__ = "destination_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    chat_id: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    chat_type: Mapped[str] = mapped_column(String(50), default="channel")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="destinations")
