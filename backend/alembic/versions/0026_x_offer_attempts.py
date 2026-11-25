"""Record reservations before sending non-idempotent X API requests."""

import sqlalchemy as sa
from alembic import op

revision = "0026_x_offer_attempts"
down_revision = "0025_storefront_thumbnails"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "x_offer_attempts",
        sa.Column("delivery_id", sa.String(64), primary_key=True),
        sa.Column("product_key", sa.String(64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("post_id", sa.String(19)),
    )
    op.create_index(
        "ix_x_offer_attempts_attempted_at", "x_offer_attempts", ["attempted_at"]
    )


def downgrade():
    op.drop_table("x_offer_attempts")
