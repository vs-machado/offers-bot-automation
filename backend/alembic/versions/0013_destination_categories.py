"""Add opt-in category selection while preserving all-offers destinations."""

from alembic import op
import sqlalchemy as sa

revision = "0013_destination_categories"
down_revision = "0012_delivery_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Existing destinations retain all-offers behavior through SQL NULL."""
    op.add_column(
        "destination_channels", sa.Column("categories", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Remove category rules without removing destinations."""
    op.drop_column("destination_channels", "categories")
