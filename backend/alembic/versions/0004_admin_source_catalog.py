"""Add database roles and seed the operator-managed source catalog."""

from alembic import op
import sqlalchemy as sa

revision = "0004_admin_source_catalog"
down_revision = "0003_add_processed_product_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep existing users unprivileged and preserve the initial catalog."""
    op.add_column(
        "users", sa.Column("role", sa.String(20), nullable=False, server_default="user")
    )
    table = op.create_table(
        "source_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("url", sa.String(255), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    names = [
        "promotom",
        "fumotom",
        "promochina",
        "promotop",
        "peperaiohardware",
        "achadinhomily",
        "achadinhossdamily1",
    ]
    op.bulk_insert(
        table,
        [
            {"url": f"https://t.me/{name}", "label": name, "enabled": True}
            for name in names
        ],
    )


def downgrade() -> None:
    """Remove admin roles and the configurable catalog."""
    op.drop_table("source_groups")
    op.drop_column("users", "role")
