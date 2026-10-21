"""Add owned WhatsApp connections without renaming existing WAHA sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0016_whatsapp_connections"
down_revision = "0015_whatsapp_group_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill primary routing; preserve existing policies, pauses and attempts."""
    op.create_table(
        "whatsapp_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("config_data", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_whatsapp_connections_user_id", "whatsapp_connections", ["user_id"]
    )
    op.create_index(
        "uq_whatsapp_primary_connection",
        "whatsapp_connections",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
        sqlite_where=sa.text("is_default = 1"),
    )
    op.create_table(
        "whatsapp_connection_states",
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("whatsapp_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("chat_id", sa.String(100), primary_key=True),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paused_until", sa.DateTime(timezone=True)),
        sa.Column("pause_reason", sa.String(100)),
    )
    op.execute(
        sa.text(
            "INSERT INTO whatsapp_connections(user_id,name,is_default) SELECT id,'Principal',true FROM users"
        )
    )
    op.add_column(
        "whatsapp_send_attempts",
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
    )
    for table in (
        "destination_channels",
        "promotion_deliveries",
        "whatsapp_send_attempts",
        "whatsapp_group_creations",
    ):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("connection_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_connection",
                "whatsapp_connections",
                ["connection_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        if table != "whatsapp_group_creations":
            op.create_index(f"ix_{table}_connection_id", table, ["connection_id"])
        condition = (
            " WHERE platform='whatsapp'" if table == "destination_channels" else ""
        )
        if table == "promotion_deliveries":
            condition = " WHERE chat_id LIKE '%@g.us' OR chat_id LIKE '%@newsletter'"
        op.execute(
            sa.text(
                f"UPDATE {table} SET connection_id=(SELECT id FROM whatsapp_connections c WHERE c.user_id={table}.user_id AND c.is_default=true){condition}"
            )
        )


def downgrade() -> None:
    """Require explicit removal of extra connections before restoring single-account routing."""
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM whatsapp_connections WHERE is_default=false")
        )
        .scalar()
    ):
        raise RuntimeError("Remove additional WhatsApp connections before downgrade")
    for table in (
        "whatsapp_group_creations",
        "whatsapp_send_attempts",
        "promotion_deliveries",
        "destination_channels",
    ):
        if table != "whatsapp_group_creations":
            op.drop_index(f"ix_{table}_connection_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_connection", type_="foreignkey")
            batch.drop_column("connection_id")
    op.drop_table("whatsapp_connection_states")
    op.drop_column("whatsapp_send_attempts", "next_send_at")
    op.drop_table("whatsapp_connections")
