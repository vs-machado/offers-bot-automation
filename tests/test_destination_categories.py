"""Category routing, persistence, migration, and pending-delivery enforcement."""

from datetime import datetime, timezone
import importlib
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.offer_categories import offer_category
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel
from backend.worker.manager import UserBotInstance
from backend.worker.posting_queue import post_promotion
from offers_bot.message_context import promotion_context
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class DestinationCategoryAPITests(unittest.TestCase):
    def setUp(self):
        load_models()
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        async def database():
            yield SQLiteAsyncSession(self.session)

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        _, login = create_identity(self.session, "routing@example.com")
        self.headers = {"Authorization": f"Bearer {login.token}"}
        self.client.get("/users/me", headers=self.headers)
        self.verify = patch(
            "backend.app.api.v1.endpoints.users._verify_destination_enabled",
            new_callable=AsyncMock,
        )
        self.verify.start()

    def tearDown(self):
        self.verify.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_platforms_persist_all_selected_and_empty_rules_with_owner_isolation(self):
        for platform, chat_id, chat_type in (
            ("telegram", "-100123", "group"),
            ("whatsapp", "123@newsletter", "channel"),
        ):
            with self.subTest(platform=platform):
                body = {
                    "platform": platform,
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "title": "Offers",
                }
                created = self.client.post(
                    "/users/me/destinations", headers=self.headers, json=body
                )
                self.assertEqual(created.status_code, 201, created.text)
                self.assertIsNone(created.json()["categories"])
                destination_id = created.json()["id"]
                url = f"/users/me/destinations/{destination_id}"
                for selection in (["tech", "coupon"], [], None):
                    updated = self.client.put(
                        url,
                        headers=self.headers,
                        json={**body, "categories": selection},
                    )
                    self.assertEqual(updated.status_code, 200, updated.text)
                    self.assertEqual(updated.json()["categories"], selection)
                    listed = self.client.get(
                        "/users/me/destinations", headers=self.headers
                    ).json()
                    self.assertEqual(
                        next(item for item in listed if item["id"] == destination_id)[
                            "categories"
                        ],
                        selection,
                    )
                invalid = self.client.put(
                    url, headers=self.headers, json={**body, "categories": ["invalid"]}
                )
                self.assertEqual(invalid.status_code, 422)
                _, other = create_identity(
                    self.session, f"other-{platform}@example.com"
                )
                denied = self.client.put(
                    url,
                    headers={"Authorization": f"Bearer {other.token}"},
                    json={**body, "categories": []},
                )
                self.assertEqual(denied.status_code, 404)


class DestinationCategoryRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_configuration_reload_picks_up_saved_rules(self):
        load_models()
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            destination = DestinationChannel(
                user_id=1, chat_id="-100123", enabled=True, categories=["tech"]
            )
            session.add(destination)
            session.commit()
            bot = UserBotInstance(1, None)
            self.addCleanup(bot.close)
            database = SQLiteAsyncSession(session)
            await bot.configure(database)
            self.assertEqual(bot._matching_destination_ids("tech"), ("-100123",))
            self.assertEqual(bot._matching_destination_ids("home"), ())
            previous = bot._config_signature
            destination.categories = ["home"]
            session.commit()
            await bot.configure(database)
            self.assertNotEqual(bot._config_signature, previous)
            self.assertEqual(bot._matching_destination_ids("tech"), ())
            self.assertEqual(bot._matching_destination_ids("home"), ("-100123",))

    async def test_routes_each_category_to_all_and_matching_platform_destinations(self):
        poster = MagicMock()
        poster.send_offer = AsyncMock()
        bot = UserBotInstance(1, None, poster=poster)
        bot._destination_chat_ids = (
            "all",
            "tech-tg",
            "home-wa",
            "no-clothes",
            "none",
            "coupons",
        )
        bot._destination_categories = {
            "all": None,
            "tech-tg": ["tech"],
            "home-wa": ["home"],
            "no-clothes": ["tech", "home", "other", "coupon"],
            "none": [],
            "coupons": ["coupon"],
        }
        for category, expected in (
            ("tech", ["all", "tech-tg", "no-clothes"]),
            ("home", ["all", "home-wa", "no-clothes"]),
            ("clothes", ["all"]),
            ("other", ["all", "no-clothes"]),
            ("coupon", ["all", "no-clothes", "coupons"]),
        ):
            with self.subTest(category=category):
                poster.send_offer.reset_mock()
                token = promotion_context.set({"category": category})
                try:
                    await bot._send_offer("offer")
                finally:
                    promotion_context.reset(token)
                self.assertEqual(
                    [call.args[0] for call in poster.send_offer.await_args_list],
                    expected,
                )

    def test_coupon_and_unclassified_product_semantics(self):
        self.assertEqual(
            offer_category({"classification": "coupon", "category": "tech"}), "coupon"
        )
        self.assertEqual(offer_category(None), "other")
        self.assertEqual(offer_category({"category": "unknown"}), "other")


class DestinationCategoryQueueTests(unittest.TestCase):
    def test_whatsapp_deferral_keeps_category_for_next_rule_check(self):
        connection = MagicMock()
        now = datetime.now(timezone.utc)
        deadline = datetime.fromtimestamp(time.time() + 500, timezone.utc)
        connection.execute.return_value.fetchone.side_effect = [
            (now, now),
            ("whatsapp", ["tech"]),
            (deadline,),
        ]
        with (
            patch("backend.worker.posting_queue.connect") as connect,
            patch(
                "backend.worker.whatsapp_delivery.reserve_delivery",
                return_value=("wait", 30),
            ),
            patch.object(post_promotion, "apply_async") as publish,
        ):
            connect.return_value.__enter__.return_value = connection
            post_promotion.run(
                identity="offer",
                user_id=1,
                chat_id="chat",
                text="offer",
                deadline=deadline.timestamp(),
                category="tech",
            )
            self.assertEqual(publish.call_args.kwargs["kwargs"]["category"], "tech")

    def test_changed_rule_cancels_pending_delivery_on_both_platforms(self):
        for platform in ("telegram", "whatsapp"):
            with self.subTest(platform=platform):
                connection = MagicMock()
                now = datetime.now(timezone.utc)
                connection.execute.return_value.fetchone.side_effect = [
                    (now, now),
                    (platform, ["home"]),
                ]
                with (
                    patch("backend.worker.posting_queue.connect") as connect,
                    patch("backend.worker.posting_queue.update_status") as update,
                    patch(
                        "backend.worker.posting_queue.deliver", new_callable=AsyncMock
                    ) as deliver,
                    patch(
                        "backend.worker.whatsapp_delivery.reserve_delivery"
                    ) as reserve,
                ):
                    connect.return_value.__enter__.return_value = connection
                    post_promotion.run(
                        identity="offer",
                        user_id=1,
                        chat_id="chat",
                        text="offer",
                        deadline=time.time() + 500,
                        category="tech",
                    )
                    update.assert_called_once_with(
                        "offer", "cancelled", "category_disabled", pending_only=True
                    )
                    deliver.assert_not_awaited()
                    reserve.assert_not_called()


class DestinationCategoryMigrationTests(unittest.TestCase):
    def test_existing_destinations_keep_all_offers(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0013_destination_categories"
        )
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE destination_channels (id INTEGER PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO destination_channels (id) VALUES (1)"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT id,categories FROM destination_channels"
                    ).one(),
                    (1, None),
                )
                migration.downgrade()
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT id FROM destination_channels"
                ).scalar(),
                1,
            )
