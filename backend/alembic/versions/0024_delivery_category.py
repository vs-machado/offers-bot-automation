"""Persist the category assigned during offer ingestion."""

from alembic import op
import sqlalchemy as sa

revision = "0024_delivery_category"
down_revision = "0023_delivery_enqueue_ms"
branch_labels = None
depends_on = None


def upgrade():
    """Add a nullable category without guessing categories for existing deliveries."""
    op.add_column("promotion_deliveries", sa.Column("category", sa.String(20)))


def downgrade():
    """Remove the stored category while keeping delivery history."""
    op.drop_column("promotion_deliveries", "category")
