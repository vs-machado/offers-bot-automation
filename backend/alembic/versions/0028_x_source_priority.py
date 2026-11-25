"""Record promotion provenance for the preferred X source group."""

from alembic import op
import sqlalchemy as sa

revision = "0028_x_source_priority"
down_revision = "0027_x_buffer_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("promotion_deliveries", sa.Column("source_group_url", sa.String(255)))
    op.add_column("x_buffer_settings", sa.Column("priority_source_id", sa.Integer()))
    op.create_foreign_key(
        "fk_x_buffer_priority_source",
        "x_buffer_settings",
        "source_groups",
        ["priority_source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_x_buffer_priority_source", "x_buffer_settings", type_="foreignkey"
    )
    op.drop_column("x_buffer_settings", "priority_source_id")
    op.drop_column("promotion_deliveries", "source_group_url")
