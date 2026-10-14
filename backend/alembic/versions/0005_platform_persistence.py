"""Move operator sessions and LLM accounting into PostgreSQL."""

from alembic import op
import sqlalchemy as sa

revision = "0005_platform_persistence"
down_revision = "0004_admin_source_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create platform tables without changing per-user sessions."""
    op.create_table(
        "platform_telegram_sessions",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("session_string", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("legacy_id", sa.Integer(), unique=True, nullable=True),
    )


def downgrade() -> None:
    """Remove platform persistence tables."""
    op.drop_table("token_usage")
    op.drop_table("platform_telegram_sessions")
