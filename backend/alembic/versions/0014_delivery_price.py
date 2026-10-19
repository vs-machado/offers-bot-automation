"""Retain advertised product prices in delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0014_delivery_price"
down_revision = "0013_destination_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store original price text; legacy records retain an unknown price."""
    op.add_column(
        "promotion_deliveries", sa.Column("price", sa.String(200), nullable=True)
    )


def downgrade() -> None:
    """Remove recorded prices without removing delivery history."""
    op.drop_column("promotion_deliveries", "price")
