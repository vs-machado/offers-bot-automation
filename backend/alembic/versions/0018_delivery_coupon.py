"""Retain parsed coupon codes in delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0018_delivery_coupon"
down_revision = "0017_delivery_affiliate_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Store coupon codes; leave historical deliveries without known coupons."""
    op.add_column(
        "promotion_deliveries",
        sa.Column("coupon", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    """Remove coupon data while preserving delivery records."""
    op.drop_column("promotion_deliveries", "coupon")
