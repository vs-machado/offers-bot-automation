import asyncio
import importlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    select,
)

from backend.worker.service import WorkerService


class DeliveryRetentionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        metadata = MetaData()
        self.deliveries = Table(
            "promotion_deliveries",
            metadata,
            Column("id", String, primary_key=True),
            Column("created_at", DateTime(timezone=True)),
            Column("user_id", Integer),
            Column("status", String),
        )
        self.processed = Table(
            "processed_offers", metadata, Column("id", Integer, primary_key=True)
        )
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)
        self.session = AsyncMock()
        self.session.execute.side_effect = lambda statement, **kwargs: (
            self.connection.execute(statement)
        )
        self.session.commit.side_effect = self.connection.commit
        self.factory = MagicMock()
        self.factory.return_value.__aenter__.return_value = self.session
        self.now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
        self.worker = WorkerService()

    async def test_cleanup_batches_old_history_and_preserves_boundary_and_dedup(self):
        cutoff = self.now - timedelta(days=60)
        self.connection.execute(
            self.deliveries.insert(),
            [
                {
                    "id": str(i),
                    "created_at": cutoff - timedelta(seconds=1),
                    "user_id": i % 2 + 1,
                    "status": status,
                }
                for i, status in enumerate(
                    ("sent", "failed", "expired", "uncertain", "queued")
                )
            ]
            + [
                {
                    "id": "boundary",
                    "created_at": cutoff,
                    "user_id": 1,
                    "status": "sent",
                },
                {
                    "id": "recent",
                    "created_at": self.now,
                    "user_id": 2,
                    "status": "sent",
                },
            ],
        )
        self.connection.execute(self.processed.insert(), {"id": 1})
        self.connection.commit()
        with (
            patch("backend.worker.service.AsyncSessionLocal", self.factory),
            patch("backend.worker.service.datetime") as clock,
            patch("backend.worker.service.DELIVERY_CLEANUP_BATCH_SIZE", 2),
        ):
            clock.now.return_value = self.now
            self.assertEqual(await self.worker._cleanup_delivery_history(), 5)
            self.assertEqual(self.session.commit.await_count, 3)
            self.assertEqual(await self.worker._cleanup_delivery_history(), 0)

        self.assertEqual(
            set(self.connection.scalars(select(self.deliveries.c.id))),
            {"boundary", "recent"},
        )
        self.assertEqual(
            list(self.connection.scalars(select(self.processed.c.id))), [1]
        )

    async def test_cleanup_does_not_commit_failed_deletion(self):
        self.session.execute.side_effect = RuntimeError("database unavailable")
        with patch("backend.worker.service.AsyncSessionLocal", self.factory):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                await self.worker._cleanup_delivery_history()
        self.session.commit.assert_not_awaited()
        self.factory.return_value.__aexit__.assert_awaited_once()

    def test_retention_index_migration(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0012_delivery_retention"
        )
        with Operations.context(MigrationContext.configure(self.connection)):
            migration.upgrade()
            indexes = inspect(self.connection).get_indexes("promotion_deliveries")
            self.assertIn(
                ("ix_promotion_deliveries_created_at", ["created_at"]),
                [(index["name"], index["column_names"]) for index in indexes],
            )
            migration.downgrade()
            self.assertEqual(
                inspect(self.connection).get_indexes("promotion_deliveries"), []
            )


class DeliveryRetentionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_runs_immediately_then_waits_one_day(self):
        worker = WorkerService()
        worker._cleanup_delivery_history = AsyncMock(return_value=0)
        with patch(
            "backend.worker.service.asyncio.sleep", side_effect=asyncio.CancelledError
        ) as sleep:
            with self.assertRaises(asyncio.CancelledError):
                await worker._retention_loop()
        worker._cleanup_delivery_history.assert_awaited_once_with()
        sleep.assert_awaited_once_with(86400)

    async def test_cleanup_failure_retries_after_30_seconds(self):
        worker = WorkerService()
        worker._cleanup_delivery_history = AsyncMock(
            side_effect=[RuntimeError("database unavailable"), 7]
        )
        with (
            patch("backend.worker.service.LOGGER") as logger,
            patch(
                "backend.worker.service.asyncio.sleep",
                side_effect=[None, asyncio.CancelledError()],
            ) as sleep,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await worker._retention_loop()
        self.assertEqual(worker._cleanup_delivery_history.await_count, 2)
        self.assertEqual(sleep.await_args_list, [call(30), call(86400)])
        logger.exception.assert_called_once()

    async def test_worker_starts_and_cancels_cleanup_with_reader(self):
        worker = WorkerService()
        worker._sync_bots = AsyncMock()
        worker._sync_loop = AsyncMock()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def cleanup():
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        async def listen(callback):
            await asyncio.wait_for(started.wait(), timeout=1)

        worker._retention_loop = cleanup
        with patch("backend.worker.service.TelegramSourceReader") as reader:
            reader.return_value.listen = AsyncMock(side_effect=listen)
            await worker.start()
        self.assertTrue(started.is_set())
        self.assertTrue(cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
