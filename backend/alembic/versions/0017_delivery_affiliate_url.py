"""Retain generated affiliate links in delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0017_delivery_affiliate_url"
down_revision = "0016_whatsapp_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store generated links; leave legacy deliveries without a known link."""
    op.add_column(
        "promotion_deliveries",
        sa.Column("affiliate_url", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    """Remove stored affiliate links while preserving delivery records."""
    op.drop_column("promotion_deliveries", "affiliate_url")
