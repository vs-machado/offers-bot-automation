"""Persist website group rotation and durable creation recovery."""

from alembic import op
import sqlalchemy as sa

revision = "0020_whatsapp_websites"
down_revision = "0019_llm_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add per-user encrypted configuration and monitor state without enabling rotation."""
    op.create_table(
        "whatsapp_websites",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("config_data", sa.Text(), nullable=False),
        sa.Column(
            "active_destination_id",
            sa.Integer(),
            sa.ForeignKey("destination_channels.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "pending_destination_id",
            sa.Integer(),
            sa.ForeignKey("destination_channels.id", ondelete="SET NULL"),
        ),
        sa.Column("pending_request_id", sa.String(36)),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("member_count", sa.Integer()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
    )
    op.create_index(
        "ix_whatsapp_websites_next_check_at", "whatsapp_websites", ["next_check_at"]
    )


def downgrade() -> None:
    """Remove website state without deleting WhatsApp destinations or creation receipts."""
    op.drop_table("whatsapp_websites")
