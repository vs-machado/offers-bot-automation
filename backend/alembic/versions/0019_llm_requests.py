"""Track outgoing LLM requests by provider and model."""

from alembic import op
import sqlalchemy as sa

revision = "0019_llm_requests"
down_revision = "0018_delivery_coupon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create persistent request accounting without attributing historical usage."""
    op.create_table(
        "llm_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
    )
    op.create_index("ix_llm_requests_timestamp", "llm_requests", ["timestamp"])


def downgrade() -> None:
    """Remove request accounting."""
    op.drop_table("llm_requests")
