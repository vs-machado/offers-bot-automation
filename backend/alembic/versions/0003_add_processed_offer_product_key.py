"""Add product key to processed offers.

Revision ID: 0003_add_processed_product_key
Revises: 0002_add_user_provider_identity
"""

from __future__ import annotations

from alembic import context, op
from sqlalchemy import inspect
import sqlalchemy as sa


revision = "0003_add_processed_product_key"
down_revision = "0002_add_user_provider_identity"
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
    if "product_key" not in _column_names(bind, "processed_offers"):
        op.add_column(
            "processed_offers",
            sa.Column("product_key", sa.String(length=500), nullable=True),
        )
    if not _index_exists(bind, "ix_processed_offers_product_key"):
        op.create_index(
            "ix_processed_offers_product_key", "processed_offers", ["product_key"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "ix_processed_offers_product_key"):
        op.drop_index("ix_processed_offers_product_key", table_name="processed_offers")
    if "product_key" in _column_names(bind, "processed_offers"):
        op.drop_column("processed_offers", "product_key")
