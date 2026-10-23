import importlib
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.core.delivery_history import get_delivery_history
from backend.app.schemas.delivery import DeliveryHistory
from backend.worker.manager import UserBotInstance
from backend.worker.posting_queue import QueuePoster
from offers_bot.message_context import promotion_context
from offers_bot.models import AffiliateLink
from tests import test_delivery_prices


class DeliveryCouponTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_coupon_survives_queue_and_owned_history(self):
        promotion_context.set({**promotion_context.get(), "coupon": "NOMEDOCUPOM"})
        QueuePoster(1)._publish("-100123", "Product", None, None, time.time() + 600)

        history = await self.load_history()
        self.assertEqual(history.items[0].coupon, "NOMEDOCUPOM")
        self.assertEqual(history.items[0].price, "R$ 1.299,90 no Pix")
        self.assertEqual((await self.load_history(user_id=2)).items, [])

    async def test_failure_retains_coupon_before_link_generation(self):
        promotion_context.set({**promotion_context.get(), "coupon": "ECONOMIZE10"})
        await QueuePoster(1).record_failure(
            ("-100123",), "affiliate_credentials_missing", "affiliate"
        )

        history = await self.load_history()
        self.assertEqual(history.items[0].coupon, "ECONOMIZE10")
        self.assertEqual(history.items[0].status, "failed")

    async def test_missing_coupon_stays_unknown(self):
        QueuePoster(1)._publish("-100123", "Product", None, None, time.time() + 600)
        self.assertIsNone((await self.load_history()).items[0].coupon)

    async def test_worker_preserves_each_llm_product_coupon_without_leaking(self):
        products = [
            {
                "title": "Product A",
                "coupon": " PRIME10 ",
                "urls": ["https://amzn.to/a"],
            },
            {
                "title": "Product B",
                "coupon": "SAVE5 ou SAVE10",
                "urls": ["https://amzn.to/b"],
            },
            {"title": "Product C", "coupon": None, "urls": ["https://amzn.to/c"]},
        ]
        factory = Mock(return_value=AsyncMock())
        bot = UserBotInstance(1, factory, poster=QueuePoster(1))
        bot._source_chats = ("source",)
        bot._destination_chat_ids = ("-100123",)
        bot._amazon = Mock()
        bot._amazon.create_link.side_effect = lambda url: AffiliateLink(
            short_url=f"{url}?tag=example-20",
            long_url=None,
            origin_url=url,
            raw_text=None,
            product_key=url,
        )
        store = AsyncMock()
        store.seen.return_value = False
        with (
            patch("backend.worker.manager.PgOfferStore", return_value=store),
            patch(
                "offers_bot.parser.parse_with_llm_async",
                AsyncMock(
                    return_value={
                        "classification": "product",
                        "products": products,
                    }
                ),
            ),
            patch(
                "backend.worker.manager.format_outgoing_offer",
                AsyncMock(return_value="Product message"),
            ),
        ):
            await bot.process_message(
                "source", 1, "\n".join(product["urls"][0] for product in products)
            )

        history = await self.load_history()
        self.assertEqual(
            {item.title: item.coupon for item in history.items},
            {"Product A": "PRIME10", "Product B": "SAVE5 ou SAVE10", "Product C": None},
        )
        self.assertEqual(promotion_context.get().get("identity"), "source:123")


class DeliveryCouponMigrationTests(unittest.TestCase):
    def test_migration_preserves_legacy_deliveries_without_inventing_coupons(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0018_delivery_coupon"
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
                        "SELECT id, coupon FROM promotion_deliveries"
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
