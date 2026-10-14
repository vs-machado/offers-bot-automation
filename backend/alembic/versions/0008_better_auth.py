"""Move identity and sessions to Better Auth while preserving application IDs."""

from datetime import datetime, timezone
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "0008_better_auth"
down_revision = "0007_delivery_details"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    """Seed credential/social accounts without changing tenant IDs, roles or routing."""
    auth_users = op.create_table(
        "auth_users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), unique=True, nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("image", sa.Text()),
        *timestamps(),
    )
    for name, columns in {
        "auth_sessions": [
            sa.Column("token", sa.Text(), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ip_address", sa.Text()),
            sa.Column("user_agent", sa.Text()),
        ],
        "auth_accounts": [
            sa.Column("account_id", sa.Text(), nullable=False),
            sa.Column("provider_id", sa.Text(), nullable=False),
            *[
                sa.Column(name, sa.Text())
                for name in (
                    "password",
                    "access_token",
                    "refresh_token",
                    "id_token",
                    "scope",
                )
            ],
            sa.Column("access_token_expires_at", sa.DateTime(timezone=True)),
            sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True)),
        ],
    }.items():
        op.create_table(
            name,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("auth_users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            *columns,
            *timestamps(),
        )
        op.create_index(f"ix_{name}_user_id", name, ["user_id"])
    op.create_table(
        "auth_verifications",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
    )
    op.create_index(
        "ix_auth_verifications_identifier", "auth_verifications", ["identifier"]
    )
    op.create_table(
        "auth_rate_limits",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_request", sa.BigInteger(), nullable=False),
    )
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("auth_user_id", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_users_auth_user_id",
            "auth_users",
            ["auth_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint("uq_users_auth_user_id", ["auth_user_id"])
    bind = op.get_bind()
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, autoload_with=bind)
    accounts = sa.Table("auth_accounts", metadata, autoload_with=bind)
    for user in bind.execute(sa.select(users)).mappings().all():
        identity = str(uuid4())
        now = datetime.now(timezone.utc)
        bind.execute(
            auth_users.insert().values(
                id=identity,
                name=user["full_name"] or user["email"].split("@")[0],
                email=user["email"].lower(),
                email_verified=user["auth_provider"] == "google",
                created_at=now,
                updated_at=now,
            )
        )
        if user["hashed_password"]:
            bind.execute(
                accounts.insert().values(
                    id=str(uuid4()),
                    user_id=identity,
                    account_id=identity,
                    provider_id="credential",
                    password=user["hashed_password"],
                    created_at=now,
                    updated_at=now,
                )
            )
        if user["auth_provider"] == "google" and user["provider_account_id"]:
            bind.execute(
                accounts.insert().values(
                    id=str(uuid4()),
                    user_id=identity,
                    account_id=user["provider_account_id"],
                    provider_id="google",
                    created_at=now,
                    updated_at=now,
                )
            )
        bind.execute(
            users.update().where(users.c.id == user["id"]).values(auth_user_id=identity)
        )


def downgrade() -> None:
    """Remove Better Auth storage; new or reset passwords cannot restore legacy login."""
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_auth_user_id", type_="foreignkey")
        batch.drop_constraint("uq_users_auth_user_id", type_="unique")
        batch.drop_column("auth_user_id")
    for table in (
        "auth_rate_limits",
        "auth_verifications",
        "auth_accounts",
        "auth_sessions",
        "auth_users",
    ):
        op.drop_table(table)
