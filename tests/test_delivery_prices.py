import importlib
import time
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.delivery_history import get_delivery_history
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery
from backend.app.schemas.delivery import DeliveryHistory
from backend.worker.posting_queue import QueuePoster
from offers_bot.message_context import promotion_context, source_timestamp


class DeliveryPriceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        PromotionDelivery.__table__.create(self.engine)
        DestinationChannel.__table__.create(self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                DestinationChannel.__table__.insert().values(
                    user_id=1,
                    chat_id="-100123",
                    platform="telegram",
                    chat_type="group",
                    enabled=True,
                )
            )

        class QueueConnection:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, statement, parameters):
                return self.connection.exec_driver_sql(
                    statement.replace("%s", "?"), parameters
                )

        @contextmanager
        def connect():
            with self.engine.begin() as connection:
                yield QueueConnection(connection)

        for target, replacement in (
            ("backend.worker.posting_queue.connect", connect),
            ("backend.worker.whatsapp_delivery.lock_account", lambda *args: None),
        ):
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch("backend.worker.posting_queue.post_promotion.apply_async")
        patcher.start()
        self.addCleanup(patcher.stop)

    async def asyncSetUp(self):
        self.source_token = source_timestamp.set(time.time())
        self.promotion_token = promotion_context.set(
            {
                "identity": "source:123",
                "title": "Example product",
                "platform": "amazon",
                "product_key": "product:123",
                "price": "R$ 1.299,90 no Pix|R$ 1.399,90",
                "advertised_price": "R$ 1.299,90 no Pix",
            }
        )

    async def asyncTearDown(self):
        promotion_context.reset(self.promotion_token)
        source_timestamp.reset(self.source_token)

    async def test_queued_price_survives_storage_and_history_serialization(self):
        result = QueuePoster(1)._publish(
            "-100123", "Example product", None, None, time.time() + 600
        )
        self.assertEqual(result["status"], "queued")

        with Session(self.engine) as session:
            db = AsyncMock()
            db.execute.side_effect = session.execute
            db.scalar.side_effect = session.scalar
            history = DeliveryHistory.model_validate(
                await get_delivery_history(db, 1, 1, 20, None, True)
            )
        self.assertEqual(history.items[0].price, "R$ 1.299,90 no Pix")

    async def test_pre_queue_failure_retains_available_price(self):
        await QueuePoster(1).record_failure(
            ("-100123",), "affiliate_credentials_missing", "affiliate"
        )
        with Session(self.engine) as session:
            delivery = session.scalars(select(PromotionDelivery)).one()
            self.assertEqual(delivery.status, "failed")
            self.assertEqual(delivery.price, "R$ 1.299,90 no Pix")

    async def test_missing_price_remains_unknown(self):
        promotion_context.set({"identity": "source:unknown"})
        QueuePoster(1)._publish(
            "-100123", "Offer without a price", None, None, time.time() + 600
        )
        with Session(self.engine) as session:
            delivery = session.scalars(select(PromotionDelivery)).one()
            self.assertIsNone(delivery.price)


class DeliveryPriceMigrationTests(unittest.TestCase):
    def test_migration_keeps_existing_history_and_unknown_prices(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0014_delivery_price"
        )
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        table = Table(
            "promotion_deliveries",
            MetaData(),
            Column("id", String, primary_key=True),
        )
        table.create(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(id="existing"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT id, price FROM promotion_deliveries"
                    ).all(),
                    [("existing", None)],
                )
                migration.downgrade()
            self.assertEqual(
                [
                    column["name"]
                    for column in inspect(connection).get_columns(table.name)
                ],
                ["id"],
            )
            self.assertEqual(
                connection.execute(select(table.c.id)).all(), [("existing",)]
            )
