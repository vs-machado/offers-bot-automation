"""Owner-triggered reposts bypass caps while keeping validation and ownership."""

from datetime import datetime, timedelta, timezone
import importlib
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.manual_delivery import compose_manual_text
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class ManualRepostAPITests(unittest.TestCase):
    def setUp(self):
        load_models()
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        async def database():
            yield SQLiteAsyncSession(self.session)

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.now = datetime.now(timezone.utc)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def login(self, email):
        _, login = create_identity(self.session, email)
        headers = {"Authorization": f"Bearer {login.token}"}
        user = self.client.get("/users/me", headers=headers).json()
        return user["id"], headers

    def add_source(self, user_id, identity="source", text="Oferta original"):
        self.session.add(
            PromotionDelivery(
                id=identity,
                user_id=user_id,
                chat_id="111@newsletter",
                status="sent",
                stage="posting",
                title="Fone Bluetooth",
                price="R$ 199",
                coupon="TECH10",
                affiliate_url="https://example.com/aff",
                platform="Amazon",
                dedup_key="product-key",
                text=text,
                image_url="https://example.com/image.jpg",
                expires_at=self.now + timedelta(hours=1),
                source_at=self.now,
                created_at=self.now,
                updated_at=self.now,
            )
        )
        self.session.commit()

    def add_destination(self, user_id, chat_id="222@g.us", enabled=True):
        self.session.add(
            DestinationChannel(
                user_id=user_id,
                chat_id=chat_id,
                platform="whatsapp",
                chat_type="group",
                title="Grupo novo",
                enabled=enabled,
            )
        )
        self.session.commit()

    def test_manual_repost_queues_copy_and_bypasses_caps(self):
        user_id, headers = self.login("owner@example.com")
        self.add_source(user_id)
        self.add_destination(user_id)
        with patch("backend.app.core.manual_delivery.enqueue_promotion") as enqueue:
            response = self.client.post(
                "/users/me/deliveries/source/repost",
                headers=headers,
                json={"chat_id": "222@g.us"},
            )
        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["status"], "queued")
        self.assertTrue(body["manual"])
        enqueue.assert_called_once()
        kwargs = enqueue.call_args.kwargs
        self.assertEqual(kwargs["chat_id"], "222@g.us")
        self.assertEqual(kwargs["text"], "Oferta original")
        self.assertEqual(kwargs["image_url"], "https://example.com/image.jpg")
        row = self.session.get(PromotionDelivery, body["id"])
        self.assertIsNotNone(row)
        self.assertTrue(row.manual)
        self.assertEqual(row.text, "Oferta original")
        self.assertEqual(row.dedup_key, "product-key")
        self.assertEqual(row.status, "queued")

    def test_rejects_already_active_destination_and_disabled_destination(self):
        user_id, headers = self.login("owner@example.com")
        self.add_source(user_id)
        self.add_destination(user_id)
        self.session.add(
            PromotionDelivery(
                id="existing",
                user_id=user_id,
                chat_id="222@g.us",
                status="sent",
                stage="posting",
                dedup_key="product-key",
                expires_at=self.now + timedelta(hours=1),
            )
        )
        self.session.commit()
        duplicate = self.client.post(
            "/users/me/deliveries/source/repost",
            headers=headers,
            json={"chat_id": "222@g.us"},
        )
        self.assertEqual(duplicate.status_code, 409)

        self.add_destination(user_id, chat_id="333@g.us", enabled=False)
        disabled = self.client.post(
            "/users/me/deliveries/source/repost",
            headers=headers,
            json={"chat_id": "333@g.us"},
        )
        self.assertEqual(disabled.status_code, 404)

    def test_foreign_delivery_is_not_reposted(self):
        owner_id, _ = self.login("owner@example.com")
        _, intruder = self.login("intruder@example.com")
        self.add_source(owner_id)
        self.add_destination(owner_id)
        response = self.client.post(
            "/users/me/deliveries/source/repost",
            headers=intruder,
            json={"chat_id": "222@g.us"},
        )
        self.assertEqual(response.status_code, 404)

    def test_compose_falls_back_to_stored_fields(self):
        delivery = PromotionDelivery(
            title="Cafeteira",
            price="R$ 249",
            coupon="CAFE15",
            affiliate_url="https://example.com/cafe",
        )
        self.assertEqual(
            compose_manual_text(delivery),
            "Cafeteira\n\n💰 R$ 249\n\n🎟️ Cupom: CAFE15\n\n🔗 https://example.com/cafe",
        )


class ManualRepostMigrationTests(unittest.TestCase):
    def test_migration_defaults_legacy_rows_to_automatic(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0022_delivery_manual_repost"
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
                        "SELECT id, text, image_url, manual FROM promotion_deliveries"
                    ).all(),
                    [("legacy", None, None, False)],
                )
                migration.downgrade()
            self.assertEqual(
                [
                    column["name"]
                    for column in inspect(connection).get_columns(table.name)
                ],
                ["id"],
            )
