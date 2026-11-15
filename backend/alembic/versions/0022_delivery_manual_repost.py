"""Store rendered offer content and allow explicit owner-triggered reposts."""

from alembic import op
import sqlalchemy as sa

revision = "0022_delivery_manual_repost"
down_revision = "0021_whatsapp_public_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep the original message for reposts and flag deliveries that bypass caps."""
    op.add_column("promotion_deliveries", sa.Column("text", sa.Text(), nullable=True))
    op.add_column(
        "promotion_deliveries",
        sa.Column("image_url", sa.String(1000), nullable=True),
    )
    op.add_column(
        "promotion_deliveries",
        sa.Column(
            "manual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Remove repost metadata while preserving delivery records."""
    op.drop_column("promotion_deliveries", "manual")
    op.drop_column("promotion_deliveries", "image_url")
    op.drop_column("promotion_deliveries", "text")
