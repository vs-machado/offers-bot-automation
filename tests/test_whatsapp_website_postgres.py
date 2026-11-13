"""Optional disposable-PostgreSQL checks for the real migration and cross-replica locks."""

import asyncio
import importlib
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core import website_rotation

DATABASE_URL = os.getenv("WAHA_POLICY_TEST_DATABASE_URL")


@unittest.skipUnless(
    DATABASE_URL, "Set WAHA_POLICY_TEST_DATABASE_URL to disposable PostgreSQL"
)
class WebsitePostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = DATABASE_URL.replace(
            "postgresql+psycopg://", "postgresql+asyncpg://"
        ).replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(url, pool_size=4)
        self.engine_patch = patch.object(website_rotation, "engine", self.engine)
        self.engine_patch.start()

    async def asyncTearDown(self):
        self.engine_patch.stop()
        await self.engine.dispose()

    async def test_same_owner_excluded_other_owner_independent_and_exception_releases(
        self,
    ):
        async with website_rotation.website_lock(1) as first:
            self.assertTrue(first)
            async with website_rotation.website_lock(1) as duplicate:
                self.assertFalse(duplicate)
            async with website_rotation.website_lock(2) as other:
                self.assertTrue(other)
        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            async with website_rotation.website_lock(1) as acquired:
                self.assertTrue(acquired)
                raise RuntimeError("worker failed")
        async with website_rotation.website_lock(1) as acquired:
            self.assertTrue(acquired)

    async def test_cancellation_releases_lock_before_pool_reuse(self):
        ready = asyncio.Event()

        async def monitor():
            async with website_rotation.website_lock(3) as acquired:
                self.assertTrue(acquired)
                ready.set()
                await asyncio.sleep(60)

        task = asyncio.create_task(monitor())
        await ready.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        async with website_rotation.website_lock(3) as acquired:
            self.assertTrue(acquired)

    async def test_migration_foreign_keys_and_downgrade_preserve_publishing(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0020_whatsapp_websites"
        )
        schema = "website_test_" + uuid4().hex
        async with self.engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            await connection.execute(text(f"SET LOCAL search_path={schema}"))
            await connection.execute(
                text("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            )
            await connection.execute(
                text(
                    "CREATE TABLE destination_channels (id INTEGER PRIMARY KEY, enabled BOOLEAN NOT NULL)"
                )
            )
            await connection.execute(text("INSERT INTO users VALUES (1)"))
            await connection.execute(
                text("INSERT INTO destination_channels VALUES (1, true), (2, true)")
            )

            def upgrade(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration.upgrade()

            await connection.run_sync(upgrade)
            await connection.execute(
                text(
                    "INSERT INTO whatsapp_websites (user_id, config_data, active_destination_id, pending_destination_id) VALUES (1, 'encrypted-test-placeholder', 1, 2)"
                )
            )
            await connection.execute(
                text("DELETE FROM destination_channels WHERE id=1")
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT active_destination_id, pending_destination_id, revision FROM whatsapp_websites"
                    )
                )
            ).one()
            self.assertEqual(tuple(row), (None, 2, 0))
            await connection.execute(text("DELETE FROM users WHERE id=1"))
            self.assertEqual(
                (
                    await connection.execute(
                        text("SELECT count(*) FROM whatsapp_websites")
                    )
                ).scalar(),
                0,
            )

            def downgrade(sync_connection):
                with Operations.context(MigrationContext.configure(sync_connection)):
                    migration.downgrade()

            await connection.run_sync(downgrade)
            self.assertTrue(
                (
                    await connection.execute(
                        text("SELECT enabled FROM destination_channels WHERE id=2")
                    )
                ).scalar()
            )
            await connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
