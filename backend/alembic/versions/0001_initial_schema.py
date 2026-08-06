"""Create initial application schema.

Revision ID: 0001_initial_schema
Revises:
"""

from __future__ import annotations

from alembic import context, op
from sqlalchemy import inspect
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    if context.is_offline_mode():
        return False
    return inspect(bind).has_table(table_name)


def _index_exists(bind, index_name: str) -> bool:
    if context.is_offline_mode():
        return False
    inspector = inspect(bind)
    return any(
        index["name"] == index_name
        for table_name in inspector.get_table_names()
        for index in inspector.get_indexes(table_name)
    )


def _create_index_if_missing(
    bind, index_name: str, table_name: str, columns: list[str]
) -> None:
    if not _index_exists(bind, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=500), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )

    if not _table_exists(bind, "user_configs"):
        op.create_table(
            "user_configs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("config_type", sa.String(length=50), nullable=False),
            sa.Column("config_data", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(bind, "offers"):
        op.create_table(
            "offers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("platform", sa.String(length=50), nullable=False),
            sa.Column("product_url", sa.String(length=1000), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("price", sa.String(length=50), nullable=False),
            sa.Column(
                "currency", sa.String(length=10), nullable=False, server_default="BRL"
            ),
            sa.Column("affiliate_url", sa.String(length=1000), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(bind, "destination_channels"):
        op.create_table(
            "destination_channels",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("chat_id", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column(
                "chat_type",
                sa.String(length=50),
                nullable=False,
                server_default="channel",
            ),
            sa.Column(
                "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists(bind, "processed_offers"):
        op.create_table(
            "processed_offers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_chat", sa.String(length=100), nullable=False),
            sa.Column("source_message_id", sa.Integer(), nullable=False),
            sa.Column("source_url", sa.String(length=1000), nullable=False),
            sa.Column("affiliate_url", sa.String(length=1000), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "source_chat",
                "source_message_id",
                "source_url",
                name="uq_processed_offer",
            ),
        )

    if not _table_exists(bind, "telegram_sessions"):
        op.create_table(
            "telegram_sessions",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_string", sa.String(length=500), nullable=False),
            sa.Column(
                "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.Column(
                "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    _create_index_if_missing(bind, "ix_users_email", "users", ["email"])
    _create_index_if_missing(
        bind, "ix_user_configs_user_id", "user_configs", ["user_id"]
    )
    _create_index_if_missing(
        bind, "ix_user_configs_config_type", "user_configs", ["config_type"]
    )
    _create_index_if_missing(bind, "ix_offers_user_id", "offers", ["user_id"])
    _create_index_if_missing(bind, "ix_offers_platform", "offers", ["platform"])
    _create_index_if_missing(
        bind, "ix_destination_channels_user_id", "destination_channels", ["user_id"]
    )
    _create_index_if_missing(
        bind, "ix_destination_channels_chat_id", "destination_channels", ["chat_id"]
    )
    _create_index_if_missing(
        bind, "ix_processed_offers_user_id", "processed_offers", ["user_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in (
        "telegram_sessions",
        "processed_offers",
        "destination_channels",
        "offers",
        "user_configs",
        "users",
    ):
        if _table_exists(bind, table_name):
            op.drop_table(table_name)
