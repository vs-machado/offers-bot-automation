"""Add safe promotion context to the delivery audit."""

from alembic import op
import sqlalchemy as sa

revision = "0007_delivery_details"
down_revision = "0006_promotion_deliveries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep old history readable while enriching future records."""
    op.add_column(
        "promotion_deliveries", sa.Column("title", sa.String(200), nullable=True)
    )
    op.add_column(
        "promotion_deliveries", sa.Column("platform", sa.String(50), nullable=True)
    )
    op.add_column(
        "promotion_deliveries",
        sa.Column("stage", sa.String(20), nullable=False, server_default="posting"),
    )
    op.create_index(
        "ix_delivery_user_created",
        "promotion_deliveries",
        ["user_id", "created_at", "id"],
    )


def downgrade() -> None:
    """Remove history context without touching delivery outcomes."""
    op.drop_index("ix_delivery_user_created", table_name="promotion_deliveries")
    op.drop_column("promotion_deliveries", "stage")
    op.drop_column("promotion_deliveries", "platform")
    op.drop_column("promotion_deliveries", "title")
