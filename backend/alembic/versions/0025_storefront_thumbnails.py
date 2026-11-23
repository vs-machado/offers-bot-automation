"""Cache bounded storefront thumbnails separately from delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0025_storefront_thumbnails"
down_revision = "0024_delivery_category"
branch_labels = None
depends_on = None


def upgrade():
    """Create the independently expiring thumbnail cache."""
    op.create_table(
        "storefront_thumbnails",
        sa.Column("delivery_id", sa.String(64), primary_key=True),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["promotion_deliveries.id"], ondelete="CASCADE"
        ),
    )


def downgrade():
    """Remove cached thumbnails without changing delivery history."""
    op.drop_table("storefront_thumbnails")
