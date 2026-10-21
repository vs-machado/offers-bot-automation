"""Policy API, rolling limits and real PostgreSQL concurrency admission tests.

PostgreSQL tests require an explicit WAHA_POLICY_TEST_DATABASE_URL pointing at a
disposable test database. Each test uses an isolated schema, never application data.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel, User
from backend.app.models.whatsapp_policy import WhatsAppDeliveryState
from backend.app.schemas.whatsapp_policy import WhatsAppPolicy
from backend.worker.posting_queue import (
    QueuePoster,
    post_promotion,
    promotion_ttl,
    update_status,
)
from backend.worker.poster import BotPosterError
from backend.worker.whatsapp_delivery import (
    next_slot,
    offer_key,
    record_outcome,
    reserve_delivery,
)
from offers_bot.message_context import promotion_context, source_timestamp
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class PolicyCalculationTests(unittest.TestCase):
    def test_limits_and_collection_must_fit_validity(self):
        for settings in (
            {"ttl_seconds": 601},
            {"burst_threshold": 5},
            {"start_hour_utc": 20, "end_hour_utc": 10},
            {"ttl_seconds": 60, "burst_window_seconds": 60},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                WhatsAppPolicy(**settings)
        with (
            patch.dict(os.environ, {"PROMOTION_TTL_SECONDS": "601"}),
            self.assertRaises(ValueError),
        ):
            promotion_ttl()

    def test_rolling_quota_and_cross_channel_spacing(self):
        now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        policy = WhatsAppPolicy(max_per_hour=2, max_per_day=3)
        attempts = [
            ("a", now - timedelta(seconds=120)),
            ("b", now - timedelta(seconds=5)),
        ]
        self.assertEqual(
            next_slot(policy, now, attempts, "a"), now + timedelta(seconds=3480)
        )
        self.assertEqual(
            next_slot(WhatsAppPolicy(), now, attempts[-1:], "a"),
            now + timedelta(seconds=15),
        )
        self.assertEqual(
            next_slot(WhatsAppPolicy(), now, attempts[-1:], "b"),
            now + timedelta(seconds=40),
        )

    def test_window_moves_send_to_next_opening(self):
        now = datetime(2026, 10, 15, 23, tzinfo=timezone.utc)
        policy = WhatsAppPolicy(start_hour_utc=10, end_hour_utc=22)
        self.assertEqual(
            next_slot(policy, now, [], "a"), now.replace(hour=10) + timedelta(days=1)
        )

    def test_resolved_product_dedup_is_price_sensitive(self):
        context = {"product_key": "amazon:123:blue", "price": "100|90"}
        self.assertEqual(offer_key(context, "origem A"), offer_key(context, "origem B"))
        self.assertEqual(
            offer_key(context, "A"),
            offer_key({**context, "price": "R$ 100,00|R$ 90,00"}, "B"),
        )
        self.assertNotEqual(
            offer_key(context, "A"), offer_key({**context, "price": "80|70"}, "A")
        )
        self.assertNotEqual(
            offer_key({}, "https://shop/item?variant=blue"),
            offer_key({}, "https://shop/item?variant=red"),
        )


class PolicyMigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_preserve_existing_delivery(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0010_whatsapp_delivery_policy"
        )
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql(
                "CREATE TABLE promotion_deliveries (id TEXT PRIMARY KEY,user_id INTEGER,chat_id TEXT,created_at TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "INSERT INTO promotion_deliveries (id,user_id,chat_id) VALUES ('old',1,'123@newsletter')"
            )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                self.assertEqual(
                    conn.exec_driver_sql(
                        "SELECT id,source_at,dedup_key FROM promotion_deliveries"
                    ).one(),
                    ("old", None, None),
                )
                self.assertIn(
                    "whatsapp_delivery_policies", sa.inspect(conn).get_table_names()
                )
                migration.downgrade()
            self.assertEqual(
                conn.exec_driver_sql("SELECT id FROM promotion_deliveries").scalar(),
                "old",
            )
            self.assertNotIn(
                "whatsapp_delivery_policies", sa.inspect(conn).get_table_names()
            )


class PolicyAPITests(unittest.TestCase):
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

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def login(self, email):
        _, login = create_identity(self.session, email)
        headers = {"Authorization": f"Bearer {login.token}"}
        user = self.client.get("/users/me", headers=headers).json()
        return user["id"], headers

    def test_policy_authentication_validation_and_owner_isolation(self):
        self.assertEqual(self.client.get("/users/me/whatsapp/policy").status_code, 401)
        _, first = self.login("first@example.com")
        _, second = self.login("second@example.com")
        settings = WhatsAppPolicy(max_per_hour=20).model_dump()
        saved = self.client.put(
            "/users/me/whatsapp/policy", headers=first, json=settings
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        own = self.client.get("/users/me/whatsapp/policy", headers=first)
        self.assertEqual(own.headers["cache-control"], "no-store")
        self.assertEqual(own.json()["settings"]["max_per_hour"], 20)
        self.assertEqual(
            self.client.get("/users/me/whatsapp/policy", headers=second).json()[
                "settings"
            ]["max_per_hour"],
            90,
        )
        invalid = self.client.put(
            "/users/me/whatsapp/policy",
            headers=first,
            json={**settings, "ttl_seconds": 601},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_resume_clears_only_owners_pauses_without_enabling_destinations(self):
        first_id, headers = self.login("first@example.com")
        second_id, _ = self.login("second@example.com")
        until = datetime.now(timezone.utc) + timedelta(minutes=15)
        for owner in (first_id, second_id):
            self.session.add(
                WhatsAppDeliveryState(
                    user_id=owner,
                    chat_id="",
                    failures=3,
                    paused_until=until,
                    pause_reason="whatsapp_api",
                )
            )
        self.session.add(
            DestinationChannel(
                user_id=first_id,
                platform="whatsapp",
                chat_id="123@newsletter",
                enabled=False,
            )
        )
        self.session.commit()
        self.assertEqual(
            len(
                self.client.get("/users/me/whatsapp/policy", headers=headers).json()[
                    "pauses"
                ]
            ),
            1,
        )
        self.assertEqual(
            self.client.post(
                "/users/me/whatsapp/policy/resume", headers=headers
            ).status_code,
            204,
        )
        self.session.expire_all()
        self.assertIsNone(
            self.session.get(WhatsAppDeliveryState, (first_id, "")).paused_until
        )
        self.assertIsNotNone(
            self.session.get(WhatsAppDeliveryState, (second_id, "")).paused_until
        )
        self.assertFalse(self.session.query(DestinationChannel).one().enabled)


@unittest.skipUnless(
    os.getenv("WAHA_POLICY_TEST_DATABASE_URL"), "Disposable PostgreSQL URL not supplied"
)
class PostgreSQLAdmissionTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg import sql

        self.url = os.environ["WAHA_POLICY_TEST_DATABASE_URL"]
        self.schema = "waha_test_" + uuid4().hex
        with psycopg.connect(self.url) as conn:
            conn.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema))
            )
        self.addCleanup(self.drop_schema)
        self.engine = sa.create_engine(
            sa.engine.make_url(self.url).set(drivername="postgresql+psycopg"),
            connect_args={"options": f"-csearch_path={self.schema}"},
        )
        self.addCleanup(self.engine.dispose)
        load_models()
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            for identity in (1, 2):
                db.add(User(id=identity, email=f"user{identity}@example.com"))
            db.flush()
            for owner, chat in (
                (1, "123@newsletter"),
                (1, "456@newsletter"),
                (2, "123@newsletter"),
            ):
                db.add(
                    DestinationChannel(
                        user_id=owner,
                        chat_id=chat,
                        platform="whatsapp",
                        chat_type="channel",
                        enabled=True,
                    )
                )
            db.commit()

        def connection():
            return psycopg.connect(self.url, options=f"-csearch_path={self.schema}")

        self.connection = connection
        for target in (
            "backend.worker.posting_queue.connect",
            "backend.worker.whatsapp_delivery.connect",
        ):
            patcher = patch(target, connection)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {"PROMOTION_TTL_SECONDS": "600"})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("backend.worker.posting_queue.post_promotion.apply_async")
        self.broker = patcher.start()
        self.addCleanup(patcher.stop)

    def drop_schema(self):
        import psycopg
        from psycopg import sql

        with psycopg.connect(self.url) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))
            )

    def enqueue(
        self,
        index,
        user_id=1,
        chat_id="123@newsletter",
        age=0,
        product=None,
        price="100",
    ):
        source_token = source_timestamp.set(time.time() - age)
        context_token = promotion_context.set(
            {
                "identity": str(index),
                "product_key": product or f"product-{index}",
                "price": price,
            }
        )
        try:
            return QueuePoster(user_id)._publish(
                chat_id, f"oferta {index}", None, None, time.time() + 600 - age
            )
        finally:
            source_timestamp.reset(source_token)
            promotion_context.reset(context_token)

    def make_ready(self):
        with self.connection() as conn:
            conn.execute(
                "UPDATE promotion_deliveries SET created_at=created_at-interval '61 seconds'"
            )

    def test_ten_minutes_and_terminal_discard_survive_expiry(self):
        self.assertEqual(self.enqueue(1, age=601)["status"], "expired")
        self.broker.assert_not_called()
        items = [self.enqueue(i) for i in range(2, 8)]
        update_status(items[0]["id"], "expired")
        with self.connection() as conn:
            status = conn.execute(
                "SELECT status,reason FROM promotion_deliveries WHERE id=%s",
                (items[0]["id"],),
            ).fetchone()
        self.assertEqual(status, ("cancelled", "burst_superseded"))

    def test_burst_keeps_five_newest_by_source_and_isolates_users(self):
        other = self.enqueue(99, user_id=2)
        # New arrivals can carry older source messages: select by source, not arrival.
        items = [self.enqueue(i, age=100 - i) for i in range(8)]
        with self.connection() as conn:
            pending = conn.execute(
                "SELECT id FROM promotion_deliveries WHERE user_id=1 AND status='queued' ORDER BY source_at DESC"
            ).fetchall()
            self.assertEqual(
                [row[0] for row in pending], [item["id"] for item in items[-1:-6:-1]]
            )
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM promotion_deliveries WHERE id=%s",
                    (other["id"],),
                ).fetchone()[0],
                "queued",
            )

    def test_concurrent_duplicate_sources_do_not_fill_burst_slots(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(
                executor.map(
                    lambda index: self.enqueue(index, product="same-product"), range(6)
                )
            )
        self.assertEqual(sum(item["status"] == "queued" for item in results), 1)
        self.assertEqual(
            self.enqueue(8, product="same-product", price="80")["status"], "queued"
        )

    def test_reservation_serializes_workers_and_enforces_cross_channel_spacing(self):
        first = self.enqueue(1)
        second = self.enqueue(2, chat_id="456@newsletter")
        self.make_ready()
        with ThreadPoolExecutor(max_workers=2) as executor:
            actions = list(
                executor.map(
                    lambda args: reserve_delivery(
                        args[0]["id"], 1, args[1], time.time() + 600
                    )[0],
                    ((first, "123@newsletter"), (second, "456@newsletter")),
                )
            )
        self.assertEqual(sorted(actions), ["send", "wait"])
        sent = first if actions[0] == "send" else second
        waiting = second if actions[0] == "send" else first
        waiting_chat = "456@newsletter" if actions[0] == "send" else "123@newsletter"
        update_status(sent["id"], "sent")
        self.assertEqual(
            reserve_delivery(waiting["id"], 1, waiting_chat, time.time() + 600)[0],
            "wait",
        )
        self.assertEqual(
            reserve_delivery(
                sent["id"],
                1,
                "123@newsletter" if actions[0] == "send" else "456@newsletter",
                time.time() + 600,
            )[0],
            "stop",
        )

    def test_policy_shortening_does_not_renew_source_deadline(self):
        item = self.enqueue(1, age=150)
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO whatsapp_delivery_policies(user_id,config_data) VALUES (%s,%s)",
                (1, WhatsAppPolicy(ttl_seconds=120).model_dump_json()),
            )
        self.assertEqual(
            reserve_delivery(item["id"], 1, "123@newsletter", time.time() + 600)[0],
            "stop",
        )
        with self.connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status FROM promotion_deliveries WHERE id=%s", (item["id"],)
                ).fetchone()[0],
                "expired",
            )

    def test_telegram_sends_while_whatsapp_is_locked_paused_and_at_quota(self):
        from backend.worker.whatsapp_delivery import lock_account

        with self.connection() as conn:
            conn.execute(
                "INSERT INTO destination_channels(user_id,chat_id,platform,chat_type,enabled) VALUES (1,'-100123','telegram','channel',true)"
            )
            conn.execute(
                "INSERT INTO whatsapp_delivery_policies(user_id,config_data) VALUES (%s,%s)",
                (
                    1,
                    WhatsAppPolicy(
                        ttl_seconds=90, max_per_hour=1, max_per_day=1
                    ).model_dump_json(),
                ),
            )
            conn.execute(
                "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at) VALUES (1,'123@newsletter',CURRENT_TIMESTAMP)"
            )
        record_outcome(1, "123@newsletter", "whatsapp_authentication")

        with self.connection() as locked, ThreadPoolExecutor(max_workers=1) as executor:
            lock_account(locked, 1)

            def enqueue_telegram():
                with self.connection() as conn:
                    conn.execute("SET statement_timeout = '2s'")
                    with patch(
                        "backend.worker.posting_queue.connect", return_value=conn
                    ):
                        return self.enqueue(1, chat_id="-100123", age=180)

            item = executor.submit(enqueue_telegram).result(timeout=5)
            self.assertEqual(item["status"], "queued")
            kwargs = dict(self.broker.call_args.kwargs["kwargs"])
            self.broker.reset_mock()
            with (
                patch(
                    "backend.worker.posting_queue.deliver", new_callable=AsyncMock
                ) as send,
                patch("backend.worker.whatsapp_delivery.reserve_delivery") as reserve,
                patch("backend.worker.whatsapp_delivery.record_outcome") as outcome,
            ):
                post_promotion.run(**kwargs)
                send.assert_awaited_once()
                self.assertEqual(send.call_args.kwargs["platform"], "telegram")
                reserve.assert_not_called()
                outcome.assert_not_called()
            self.broker.assert_not_called()

        with self.connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT status,attempts FROM promotion_deliveries WHERE id=%s",
                    (item["id"],),
                ).fetchone(),
                ("sent", 1),
            )

    def test_failures_pause_account_or_destination_without_replaying(self):
        for _ in range(3):
            record_outcome(1, "123@newsletter", "connection_failure")
        record_outcome(2, "123@newsletter", "whatsapp_permission")
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT user_id,chat_id,failures,paused_until FROM whatsapp_delivery_states ORDER BY user_id"
            ).fetchall()
        self.assertEqual(rows[0][:3], (1, "", 3))
        self.assertEqual(rows[1][:3], (2, "123@newsletter", 1))
        self.assertTrue(all(row[3] > datetime.now(timezone.utc) for row in rows))
        item = self.enqueue(1)
        self.assertEqual(
            reserve_delivery(item["id"], 1, "123@newsletter", time.time() + 600)[0],
            "stop",
        )

    def test_task_defers_without_attempt_then_sends_only_once(self):
        item = self.enqueue(1)
        kwargs = dict(self.broker.call_args.kwargs["kwargs"])
        self.broker.reset_mock()
        with patch(
            "backend.worker.posting_queue.deliver", new_callable=AsyncMock
        ) as send:
            post_promotion.run(**kwargs)
            send.assert_not_awaited()
            self.assertGreater(self.broker.call_args.kwargs["countdown"], 0)
            self.assertEqual(
                self.broker.call_args.kwargs["kwargs"]["deadline"], kwargs["deadline"]
            )
            self.make_ready()
            post_promotion.run(**kwargs)
            post_promotion.run(**kwargs)
            send.assert_awaited_once()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT status,attempts FROM promotion_deliveries WHERE id=%s",
                (item["id"],),
            ).fetchone()
        self.assertEqual(row, ("sent", 1))

    def test_uncertain_task_is_not_retried_or_deduplicated_as_new_work(self):
        import httpx

        item = self.enqueue(1)
        kwargs = dict(self.broker.call_args.kwargs["kwargs"])
        self.make_ready()
        self.broker.reset_mock()
        with patch(
            "backend.worker.posting_queue.deliver",
            new_callable=AsyncMock,
            side_effect=httpx.ReadTimeout("uncertain"),
        ) as send:
            post_promotion.run(**kwargs)
            post_promotion.run(**kwargs)
            send.assert_awaited_once()
        self.broker.assert_not_called()
        self.assertEqual(self.enqueue(2, product="product-1")["status"], "duplicate")
        with self.connection() as conn:
            row = conn.execute(
                "SELECT status,reason FROM promotion_deliveries WHERE id=%s",
                (item["id"],),
            ).fetchone()
        self.assertEqual(row, ("uncertain", "delivery_uncertain"))

    def test_permission_failure_uses_whatsapp_reason_and_pauses_destination(self):
        item = self.enqueue(1)
        kwargs = dict(self.broker.call_args.kwargs["kwargs"])
        self.make_ready()
        with patch(
            "backend.worker.posting_queue.deliver",
            new_callable=AsyncMock,
            side_effect=BotPosterError("denied", status_code=403),
        ):
            post_promotion.run(**kwargs)
        with self.connection() as conn:
            row = conn.execute(
                "SELECT status,reason FROM promotion_deliveries WHERE id=%s",
                (item["id"],),
            ).fetchone()
            pause = conn.execute(
                "SELECT chat_id,pause_reason FROM whatsapp_delivery_states WHERE user_id=1"
            ).fetchone()
        self.assertEqual(row, ("failed", "whatsapp_permission"))
        self.assertEqual(pause, ("123@newsletter", "whatsapp_permission"))

    def test_rate_limit_retry_budget_survives_policy_deferral(self):
        from celery.exceptions import Retry

        self.enqueue(1)
        kwargs = dict(self.broker.call_args.kwargs["kwargs"])
        self.make_ready()
        with patch(
            "backend.worker.posting_queue.deliver",
            new_callable=AsyncMock,
            side_effect=BotPosterError("limited", status_code=429, retry_after=120),
        ):
            with patch.object(post_promotion, "retry", side_effect=Retry) as retry:
                with self.assertRaises(Retry):
                    post_promotion.run(**kwargs)
        self.assertEqual(retry.call_args.kwargs["countdown"], 120)
        self.assertEqual(retry.call_args.kwargs["headers"], {"delivery_retries": 1})
        self.broker.reset_mock()
        post_promotion.push_request(headers={"delivery_retries": 1}, retries=0)
        try:
            post_promotion.run(**kwargs)
        finally:
            post_promotion.pop_request()
        self.assertEqual(
            self.broker.call_args.kwargs["headers"], {"delivery_retries": 1}
        )
        self.assertEqual(
            self.broker.call_args.kwargs["kwargs"]["deadline"], kwargs["deadline"]
        )
