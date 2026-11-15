"""Replace D1 synchronization with owner-specific PostgreSQL public entry state."""

from alembic import op
import sqlalchemy as sa

from backend.app.core.credentials import decrypt_config, encrypt_config

revision = "0021_whatsapp_public_entry"
down_revision = "0020_whatsapp_websites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve campaigns/receipts, remove obsolete tokens, and require fresh invite observations."""
    op.add_column(
        "whatsapp_websites",
        sa.Column(
            "public_id",
            sa.String(36),
            server_default=sa.text("gen_random_uuid()::text"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_whatsapp_websites_public_id", "whatsapp_websites", ["public_id"]
    )
    op.add_column(
        "whatsapp_websites",
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "whatsapp_websites",
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey(
                "whatsapp_connections.id",
                name="fk_website_connection",
                ondelete="RESTRICT",
            ),
        ),
    )
    op.add_column("whatsapp_websites", sa.Column("invite_url", sa.String(255)))
    op.add_column(
        "whatsapp_websites", sa.Column("invite_expires_at", sa.DateTime(timezone=True))
    )
    op.add_column("whatsapp_websites", sa.Column("observed_entry_limit", sa.Integer()))
    connection = op.get_bind()
    rows = (
        connection.execute(
            sa.text("SELECT user_id, config_data FROM whatsapp_websites")
        )
        .mappings()
        .all()
    )
    for row in rows:
        settings = decrypt_config(
            row["config_data"], row["user_id"], "whatsapp_website"
        )
        settings.pop("update_token", None)
        connection.execute(
            sa.text(
                "UPDATE whatsapp_websites SET config_data=:config, enabled=:enabled, connection_id=:connection, next_check_at=NULL WHERE user_id=:user"
            ),
            {
                "config": encrypt_config(settings, row["user_id"], "whatsapp_website"),
                "enabled": bool(settings.get("enabled", False)),
                "connection": settings.get("connection_id"),
                "user": row["user_id"],
            },
        )
    op.drop_column("whatsapp_websites", "revision")
    op.drop_column("whatsapp_websites", "last_synced_at")


def downgrade() -> None:
    """Restore legacy columns, without restoring deleted credentials or enabling D1 writes."""
    op.add_column(
        "whatsapp_websites",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_websites", sa.Column("last_synced_at", sa.DateTime(timezone=True))
    )
    for column in (
        "observed_entry_limit",
        "invite_expires_at",
        "invite_url",
        "connection_id",
        "enabled",
        "public_id",
    ):
        op.drop_column("whatsapp_websites", column)
