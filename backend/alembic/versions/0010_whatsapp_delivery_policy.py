"""Persist WhatsApp editorial controls and source-aware queue selection."""

from alembic import op
import sqlalchemy as sa

revision = "0010_whatsapp_delivery_policy"
down_revision = "0009_whatsapp_destinations"
branch_labels = None
depends_on = None


def upgrade():
    """Add policy/state tables and nullable audit metadata for existing deliveries."""
    op.create_table(
        "whatsapp_delivery_policies",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("config_data", sa.String(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "whatsapp_delivery_states",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("chat_id", sa.String(100), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("paused_until", sa.DateTime(timezone=True)),
        sa.Column("pause_reason", sa.String(100)),
    )
    op.create_table(
        "whatsapp_send_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(100), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_whatsapp_attempt_user_time",
        "whatsapp_send_attempts",
        ["user_id", "attempted_at"],
    )
    op.add_column(
        "promotion_deliveries", sa.Column("source_at", sa.DateTime(timezone=True))
    )
    op.add_column("promotion_deliveries", sa.Column("dedup_key", sa.String(64)))
    op.create_index(
        "ix_delivery_routing",
        "promotion_deliveries",
        ["user_id", "chat_id", "created_at"],
    )


def downgrade():
    """Remove control state without deleting the delivery audit."""
    op.drop_index("ix_delivery_routing", table_name="promotion_deliveries")
    op.drop_column("promotion_deliveries", "dedup_key")
    op.drop_column("promotion_deliveries", "source_at")
    op.drop_table("whatsapp_send_attempts")
    op.drop_table("whatsapp_delivery_states")
    op.drop_table("whatsapp_delivery_policies")
