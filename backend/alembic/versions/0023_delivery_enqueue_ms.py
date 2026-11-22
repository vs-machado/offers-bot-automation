"""Store measured ingestion duration in delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0023_delivery_enqueue_ms"
down_revision = "0022_delivery_manual_repost"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promotion_deliveries", sa.Column("enqueue_ms", sa.Integer()))


def downgrade():
    op.drop_column("promotion_deliveries", "enqueue_ms")
