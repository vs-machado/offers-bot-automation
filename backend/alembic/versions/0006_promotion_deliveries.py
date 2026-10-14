"""Track per-destination delivery outcomes without persisting pending payloads."""

from alembic import op
import sqlalchemy as sa

revision = "0006_promotion_deliveries"
down_revision = "0005_platform_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create an audit ledger, not a replayable posting backlog."""
    op.create_table(
        "promotion_deliveries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(100), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_promotion_deliveries_user_id", "promotion_deliveries", ["user_id"]
    )


def downgrade() -> None:
    """Remove the delivery ledger."""
    op.drop_table("promotion_deliveries")
