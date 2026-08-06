from __future__ import annotations

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.app.core.db.session import engine


ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parents[3] / "alembic.ini"
BASELINE_REVISION = "0001_initial_schema"
PROVIDER_REVISION = "0002_add_user_provider_identity"


def _alembic_config() -> Config:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


async def _legacy_baseline_revision() -> str | None:
    async with engine.connect() as connection:

        def inspect_schema(sync_connection) -> str | None:
            inspector = inspect(sync_connection)
            tables = set(inspector.get_table_names())
            if "alembic_version" in tables or "users" not in tables:
                return None

            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if {"auth_provider", "provider_account_id"}.issubset(user_columns):
                return PROVIDER_REVISION
            return BASELINE_REVISION

        return await connection.run_sync(inspect_schema)


async def run_migrations() -> None:
    """Stamp legacy schemas when needed, then upgrade database to Alembic head."""
    baseline_revision = await _legacy_baseline_revision()
    config = _alembic_config()

    if baseline_revision:
        await asyncio.to_thread(command.stamp, config, baseline_revision)

    await asyncio.to_thread(command.upgrade, config, "head")
