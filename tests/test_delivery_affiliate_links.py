import importlib
import time
import unittest
from unittest.mock import AsyncMock

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.core.delivery_history import get_delivery_history
from backend.app.schemas.delivery import DeliveryHistory
from backend.worker.posting_queue import QueuePoster
from offers_bot.message_context import promotion_context
from tests import test_delivery_prices


class DeliveryAffiliateLinkTests(unittest.IsolatedAsyncioTestCase):
    setUp = test_delivery_prices.DeliveryPriceTests.setUp
    asyncSetUp = test_delivery_prices.DeliveryPriceTests.asyncSetUp
    asyncTearDown = test_delivery_prices.DeliveryPriceTests.asyncTearDown

    async def load_history(self, user_id=1):
        with Session(self.engine) as session:
            db = AsyncMock()
            db.execute.side_effect = session.execute
            db.scalar.side_effect = session.scalar
            return DeliveryHistory.model_validate(
                await get_delivery_history(db, user_id, 1, 20, None, True)
            )

    async def test_generated_link_survives_queue_and_owned_history(self):
        url = "https://example.com/product?tag=my-affiliate&variant=blue"
        promotion_context.set({**promotion_context.get(), "affiliate_url": url})
        QueuePoster(1)._publish("-100123", "Product", None, None, time.time() + 600)

        history = await self.load_history()
        self.assertEqual(history.items[0].affiliate_url, url)
        self.assertEqual((await self.load_history(user_id=2)).items, [])

    async def test_failure_retains_generated_link(self):
        url = "https://example.com/product?tag=my-affiliate"
        promotion_context.set({**promotion_context.get(), "affiliate_url": url})
        await QueuePoster(1).record_failure(
            ("-100123",), "processing_failure", "processing"
        )

        history = await self.load_history()
        self.assertEqual(history.items[0].affiliate_url, url)

    async def test_missing_link_remains_unknown(self):
        QueuePoster(1)._publish("-100123", "Product", None, None, time.time() + 600)
        self.assertIsNone((await self.load_history()).items[0].affiliate_url)


class DeliveryAffiliateLinkMigrationTests(unittest.TestCase):
    def test_migration_preserves_legacy_deliveries(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0017_delivery_affiliate_url"
        )
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        table = Table(
            "promotion_deliveries", MetaData(), Column("id", String, primary_key=True)
        )
        table.create(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(id="legacy"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT id, affiliate_url FROM promotion_deliveries"
                    ).all(),
                    [("legacy", None)],
                )
                migration.downgrade()
            self.assertEqual(
                [
                    column["name"]
                    for column in inspect(connection).get_columns(table.name)
                ],
                ["id"],
            )
