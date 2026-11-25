"""Persist the admin-managed Buffer connection."""

from alembic import op
import sqlalchemy as sa

revision = "0027_x_buffer_settings"
down_revision = "0026_x_offer_attempts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "x_buffer_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "destination_id",
            sa.Integer(),
            sa.ForeignKey("destination_channels.id", ondelete="SET NULL"),
        ),
        sa.Column("landing_url", sa.String(1000), nullable=False),
        sa.Column("channel_id", sa.String(128), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_x_buffer_singleton"),
    )


def downgrade():
    op.drop_table("x_buffer_settings")
