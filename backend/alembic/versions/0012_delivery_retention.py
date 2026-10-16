"""Index delivery creation time for bounded history cleanup."""

from alembic import op

revision = "0012_delivery_retention"
down_revision = "0011_encrypt_user_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow global retention scans without scanning each user's history."""
    op.create_index(
        "ix_promotion_deliveries_created_at", "promotion_deliveries", ["created_at"]
    )


def downgrade() -> None:
    """Remove the retention index without deleting history."""
    op.drop_index(
        "ix_promotion_deliveries_created_at", table_name="promotion_deliveries"
    )
