"""Add external authentication identity fields.

Revision ID: 0002_add_user_provider_identity
Revises: 0001_initial_schema
"""

from __future__ import annotations

from alembic import context, op
from sqlalchemy import inspect
import sqlalchemy as sa


revision = "0002_add_user_provider_identity"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    if context.is_offline_mode():
        return set()
    return {column["name"] for column in inspect(bind).get_columns(table_name)}


def _index_exists(bind, index_name: str) -> bool:
    if context.is_offline_mode():
        return False
    inspector = inspect(bind)
    return any(
        index["name"] == index_name
        for table_name in inspector.get_table_names()
        for index in inspector.get_indexes(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "users")

    if "hashed_password" in columns:
        op.alter_column(
            "users",
            "hashed_password",
            existing_type=sa.String(length=500),
            nullable=True,
        )

    if "auth_provider" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "auth_provider",
                sa.String(length=50),
                nullable=True,
                server_default=sa.text("'credentials'"),
            ),
        )
    op.execute(
        "UPDATE users SET auth_provider = 'credentials' WHERE auth_provider IS NULL"
    )
    op.alter_column(
        "users",
        "auth_provider",
        existing_type=sa.String(length=50),
        nullable=False,
        server_default=sa.text("'credentials'"),
    )

    if "provider_account_id" not in columns:
        op.add_column(
            "users",
            sa.Column("provider_account_id", sa.String(length=255), nullable=True),
        )

    if not _index_exists(bind, "ix_users_provider_account_id"):
        op.create_index(
            "ix_users_provider_account_id", "users", ["provider_account_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "ix_users_provider_account_id"):
        op.drop_index("ix_users_provider_account_id", table_name="users")
    columns = _column_names(bind, "users")
    if "provider_account_id" in columns:
        op.drop_column("users", "provider_account_id")
    if "auth_provider" in columns:
        op.drop_column("users", "auth_provider")
