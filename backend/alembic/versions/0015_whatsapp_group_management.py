"""Record group creation requests to prevent duplicate external side effects."""

from alembic import op
import sqlalchemy as sa

revision = "0015_whatsapp_group_management"
down_revision = "0014_delivery_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tenant-scoped receipts before enabling group creation endpoints."""
    op.create_table(
        "whatsapp_group_creations",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("result", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove creation receipts without deleting WhatsApp groups or destinations."""
    op.drop_table("whatsapp_group_creations")
