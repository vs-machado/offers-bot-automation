"""Separate Telegram and WhatsApp destinations without changing existing routing."""

from alembic import op
import sqlalchemy as sa

revision = "0009_whatsapp_destinations"
down_revision = "0008_better_auth"
branch_labels = None
depends_on = None


def upgrade():
    """Default existing destinations to Telegram."""
    op.add_column(
        "destination_channels",
        sa.Column("platform", sa.String(20), nullable=False, server_default="telegram"),
    )


def downgrade():
    """Remove WhatsApp destinations before dropping their platform marker."""
    op.execute("DELETE FROM destination_channels WHERE platform='whatsapp'")
    op.drop_column("destination_channels", "platform")
