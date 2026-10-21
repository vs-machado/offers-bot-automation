"""Owned multi-account routing, legacy migration and independent PostgreSQL admission."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
from datetime import datetime, timedelta, timezone
import importlib
import os
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from fastapi.testclient import TestClient
import httpx
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp import WahaClient
from backend.app.core.whatsapp_connections import validate_routing
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel
from backend.app.models.whatsapp_connection import (
    WhatsAppConnection,
    WhatsAppConnectionState,
)
from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, new_connection_policy
from backend.worker.posting_queue import post_promotion, update_status
from backend.worker.whatsapp_delivery import (
    lock_account,
    next_slot,
    record_outcome,
    reserve_delivery,
)
from tests.auth_fixtures import SQLiteAsyncSession, create_identity
import tests.test_whatsapp_delivery_policy as policy_tests


class ConnectionAPITests(unittest.TestCase):
    def setUp(self):
        load_models()
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        class Database(SQLiteAsyncSession):
            async def flush(self):
                self.session.flush()

        async def database():
            yield Database(self.session)

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.seen = []
        seen = self.seen

        async def request(client, method, path, body=None, timeout=20):
            seen.append((client.session, method, path))
            if path.endswith("/auth/qr"):
                return httpx.Response(
                    200, content=b"qr", headers={"content-type": "image/png"}
                )
            return httpx.Response(
                200, json={"status": "WORKING", "me": {"pushName": "Conta"}}
            )

        for patcher in (
            patch.object(WahaClient, "request", request),
            patch.object(WahaClient, "verify_destination", new_callable=AsyncMock),
            patch.dict(
                os.environ,
                {"WAHA_BASE_URL": "http://waha:3000", "WAHA_API_KEY": "test-secret"},
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def login(self, email):
        _, login = create_identity(self.session, email)
        headers = {"Authorization": f"Bearer {login.token}"}
        user_id = self.client.get("/users/me", headers=headers).json()["id"]
        return user_id, headers

    def connections(self, headers):
        response = self.client.get("/users/me/whatsapp/connections", headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()

    def create(self, headers):
        response = self.client.post(
            "/users/me/whatsapp/connections", headers=headers, json={"name": "Número 2"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def test_connection_selection_is_owned_and_preserves_primary_session(self):
        user_id, headers = self.login("one@example.com")
        _, foreign = self.login("two@example.com")
        primary = self.connections(headers)[0]["id"]
        secondary = self.create(headers)
        self.assertEqual(len(self.connections(headers)), 2)
        self.assertEqual(len(self.connections(foreign)), 1)
        self.assertEqual(
            self.client.get("/users/me/whatsapp/connections").status_code, 401
        )
        for connection_id, expected in (
            (primary, f"offers-user-{user_id}"),
            (secondary, f"offers-user-{user_id}-connection-{secondary}"),
        ):
            response = self.client.get(
                f"/users/me/whatsapp/qr?connection_id={connection_id}&session=foreign",
                headers=headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.seen[-1][0], expected)
            self.assertNotIn("test-secret", response.text)
        before = len(self.seen)
        for suffix, method, body in (
            ("/qr", "GET", None),
            ("", "POST", None),
            ("", "DELETE", None),
            ("/policy", "PUT", WhatsAppPolicy().model_dump()),
            ("/manage/groups", "GET", None),
        ):
            response = self.client.request(
                method,
                f"/users/me/whatsapp{suffix}?connection_id={secondary}",
                headers=foreign,
                json=body,
            )
            self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(len(self.seen), before)

    def test_policy_pauses_and_disconnect_are_connection_scoped(self):
        user_id, headers = self.login("one@example.com")
        primary = self.connections(headers)[0]["id"]
        secondary = self.create(headers)
        settings = self.client.get(
            f"/users/me/whatsapp/policy?connection_id={secondary}", headers=headers
        ).json()["settings"]
        self.assertEqual(settings["account_interval_seconds"], 30)
        self.assertEqual(settings["account_interval_max_seconds"], 90)
        self.assertEqual(settings["destination_max_per_day"], 100)
        changed = {**settings, "max_per_hour": 10}
        response = self.client.put(
            f"/users/me/whatsapp/policy?connection_id={secondary}",
            headers=headers,
            json=changed,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.client.get("/users/me/whatsapp/policy", headers=headers).json()[
                "settings"
            ]["max_per_hour"],
            90,
        )
        for conn_id, chat in ((primary, "123@g.us"), (secondary, "456@g.us")):
            self.session.add(
                DestinationChannel(
                    user_id=user_id,
                    platform="whatsapp",
                    chat_id=chat,
                    chat_type="group",
                    connection_id=conn_id,
                    enabled=True,
                )
            )
        self.session.add(
            WhatsAppConnectionState(
                connection_id=secondary,
                chat_id="",
                paused_until=datetime.now(timezone.utc) + timedelta(minutes=15),
                failures=3,
            )
        )
        self.session.commit()
        self.assertEqual(
            len(
                self.client.get(
                    f"/users/me/whatsapp/policy?connection_id={secondary}",
                    headers=headers,
                ).json()["pauses"]
            ),
            1,
        )
        self.assertEqual(
            self.client.get("/users/me/whatsapp/policy", headers=headers).json()[
                "pauses"
            ],
            [],
        )
        response = self.client.post("/users/me/whatsapp/policy/resume", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.session.expire_all()
        self.assertIsNotNone(
            self.session.get(WhatsAppConnectionState, (secondary, "")).paused_until
        )
        response = self.client.delete(
            f"/users/me/whatsapp?connection_id={secondary}", headers=headers
        )
        self.assertEqual(response.status_code, 204, response.text)
        self.session.expire_all()
        self.assertTrue(
            self.session.query(DestinationChannel)
            .filter_by(connection_id=primary)
            .one()
            .enabled
        )
        self.assertFalse(
            self.session.query(DestinationChannel)
            .filter_by(connection_id=secondary)
            .one()
            .enabled
        )
        self.assertEqual(
            self.seen[-1][0], f"offers-user-{user_id}-connection-{secondary}"
        )

    def test_six_enabled_groups_per_connection_and_explicit_transfer(self):
        user_id, headers = self.login("one@example.com")
        _, foreign = self.login("two@example.com")
        primary = self.connections(headers)[0]["id"]
        secondary = self.create(headers)
        for index in range(6):
            self.session.add(
                DestinationChannel(
                    user_id=user_id,
                    chat_id=f"{100 + index}@g.us",
                    platform="whatsapp",
                    chat_type="group",
                    connection_id=primary,
                    enabled=True,
                )
            )
        self.session.commit()
        payload = {
            "chat_id": "999@g.us",
            "chat_type": "group",
            "platform": "whatsapp",
            "connection_id": primary,
            "enabled": True,
        }
        response = self.client.post(
            "/users/me/destinations", headers=headers, json=payload
        )
        self.assertEqual(response.status_code, 409, response.text)
        payload["connection_id"] = secondary
        response = self.client.post(
            "/users/me/destinations", headers=headers, json=payload
        )
        self.assertEqual(response.status_code, 201, response.text)
        destination_id = response.json()["id"]
        self.assertEqual(
            self.client.post(
                "/users/me/destinations", headers=headers, json=payload
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                "/users/me/destinations",
                headers=foreign,
                json={**payload, "chat_id": "888@g.us"},
            ).status_code,
            404,
        )
        moved = {**payload, "connection_id": primary, "enabled": False}
        response = self.client.put(
            f"/users/me/destinations/{destination_id}", headers=headers, json=moved
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["connection_id"], primary)
        self.assertFalse(response.json()["enabled"])

    def test_dashboard_checks_all_owned_connections(self):
        user_id, headers = self.login("health@example.com")
        self.connections(headers)
        secondary = self.create(headers)
        self.session.add(
            DestinationChannel(
                user_id=user_id,
                chat_id="555@g.us",
                chat_type="group",
                platform="whatsapp",
                connection_id=secondary,
                enabled=True,
            )
        )
        self.session.commit()
        seen = []

        async def status(client, *, include_session=False):
            seen.append(client.session)
            return {
                "status": "STOPPED"
                if client.session.endswith(f"-connection-{secondary}")
                else "WORKING",
                "session_exists": True,
            }

        with patch.object(WahaClient, "status", status):
            response = self.client.get(
                "/users/me/integration-health?all_whatsapp_accounts=true",
                headers=headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["whatsapp"], "disconnected")
        self.assertCountEqual(
            seen,
            [f"offers-user-{user_id}", f"offers-user-{user_id}-connection-{secondary}"],
        )


class ConnectionCalculationTests(unittest.TestCase):
    def test_destination_quota_and_local_window(self):
        now = datetime(2026, 10, 21, 9, tzinfo=timezone.utc)  # 06:00 in Brasilia.
        policy = new_connection_policy()
        self.assertEqual(next_slot(policy, now, [], "a"), now + timedelta(hours=1))
        policy = WhatsAppPolicy(destination_max_per_day=1)
        self.assertEqual(
            next_slot(policy, now, [("a", now - timedelta(hours=2))], "a"),
            now + timedelta(hours=22),
        )
        self.assertEqual(
            next_slot(policy, now, [("a", now - timedelta(hours=2))], "b"), now
        )
        for values in (
            {"account_interval_seconds": 90, "account_interval_max_seconds": 30},
            {"posting_timezone": "not/a/timezone"},
            {"max_groups": 7},
        ):
            with self.assertRaises(ValidationError):
                WhatsAppPolicy(**values)


@unittest.skipUnless(
    os.getenv("WAHA_POLICY_TEST_DATABASE_URL"), "Disposable PostgreSQL URL not supplied"
)
class ConnectionPostgreSQLTests(unittest.TestCase):
    def setUp(self):
        self.fixture = policy_tests.PostgreSQLAdmissionTests(
            "test_task_defers_without_attempt_then_sends_only_once"
        )
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.connection = self.fixture.connection
        self.enqueue = self.fixture.enqueue
        settings = WhatsAppPolicy(
            account_interval_seconds=30,
            account_interval_max_seconds=90,
            channel_interval_seconds=60,
        )
        with self.connection() as conn:
            self.primary = conn.execute(
                "INSERT INTO whatsapp_connections(user_id,name,is_default) VALUES (1,'Primary',true) RETURNING id"
            ).fetchone()[0]
            self.secondary = conn.execute(
                "INSERT INTO whatsapp_connections(user_id,name,is_default,config_data) VALUES (1,'Second',false,%s) RETURNING id",
                (settings.model_dump_json(),),
            ).fetchone()[0]
            conn.execute(
                "UPDATE destination_channels SET connection_id=%s WHERE user_id=1 AND chat_id='123@newsletter'",
                (self.primary,),
            )
            conn.execute(
                "UPDATE destination_channels SET connection_id=%s WHERE user_id=1 AND chat_id='456@newsletter'",
                (self.secondary,),
            )

    def test_locks_quotas_and_pauses_do_not_cross_connections(self):
        first = self.enqueue(1)
        second = self.enqueue(2, chat_id="456@newsletter")
        self.fixture.make_ready()
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO whatsapp_delivery_policies(user_id,config_data) VALUES (1,%s)",
                (WhatsAppPolicy(max_per_hour=1, max_per_day=1).model_dump_json(),),
            )
            conn.execute(
                "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at,connection_id) VALUES (1,'123@newsletter',CURRENT_TIMESTAMP,%s)",
                (self.primary,),
            )
        record_outcome(
            1, "123@newsletter", "whatsapp_authentication", connection_id=self.primary
        )
        with self.connection() as locked, ThreadPoolExecutor(max_workers=1) as pool:
            lock_account(locked, 1, self.primary)
            action = pool.submit(
                reserve_delivery, second["id"], 1, "456@newsletter", time.time() + 600
            ).result(timeout=5)
        self.assertEqual(action[0], "send")
        self.assertEqual(
            reserve_delivery(first["id"], 1, "123@newsletter", time.time() + 600)[0],
            "stop",
        )

    def test_distinct_connections_can_reserve_simultaneously(self):
        first = self.enqueue(1)
        second = self.enqueue(2, chat_id="456@newsletter")
        self.fixture.make_ready()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda args: reserve_delivery(
                        args[0]["id"], 1, args[1], time.time() + 600
                    )[0],
                    ((first, "123@newsletter"), (second, "456@newsletter")),
                )
            )
        self.assertEqual(results, ["send", "send"])

    def test_random_gap_is_persisted_once_and_survives_polling(self):
        first = self.enqueue(1, chat_id="456@newsletter")
        second = self.enqueue(2, chat_id="456@newsletter")
        self.fixture.make_ready()
        with patch(
            "backend.worker.whatsapp_delivery.secrets.randbelow", return_value=60
        ) as random:
            self.assertEqual(
                reserve_delivery(first["id"], 1, "456@newsletter", time.time() + 600)[
                    0
                ],
                "send",
            )
            update_status(first["id"], "sent")
            for _ in range(2):
                self.assertEqual(
                    reserve_delivery(
                        second["id"], 1, "456@newsletter", time.time() + 600
                    )[0],
                    "wait",
                )
            random.assert_called_once_with(61)
        with self.connection() as conn:
            at, next_at = conn.execute(
                "SELECT attempted_at,next_send_at FROM whatsapp_send_attempts WHERE connection_id=%s",
                (self.secondary,),
            ).fetchone()
        self.assertEqual(next_at - at, timedelta(seconds=90))

    def test_destination_quota_is_preserved_across_transfer(self):
        item = self.enqueue(1, chat_id="456@newsletter")
        self.fixture.make_ready()
        with self.connection() as conn:
            conn.execute(
                "UPDATE whatsapp_connections SET config_data=%s WHERE id=%s",
                (
                    WhatsAppPolicy(destination_max_per_day=1).model_dump_json(),
                    self.secondary,
                ),
            )
            conn.execute(
                "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at,connection_id) VALUES (1,'456@newsletter',CURRENT_TIMESTAMP-interval '2 hours',%s)",
                (self.primary,),
            )
        self.assertEqual(
            reserve_delivery(item["id"], 1, "456@newsletter", time.time() + 600)[0],
            "stop",
        )
        with self.connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT reason FROM promotion_deliveries WHERE id=%s", (item["id"],)
                ).fetchone()[0],
                "policy_deadline",
            )

    def test_concurrent_group_activation_cannot_exceed_six(self):
        with self.connection() as conn:
            for index in range(5):
                conn.execute(
                    "INSERT INTO destination_channels(user_id,chat_id,chat_type,platform,connection_id,enabled) VALUES (1,%s,'group','whatsapp',%s,true)",
                    (f"{100 + index}@g.us", self.primary),
                )

        def activate(index):
            async def run():
                with Session(self.fixture.engine) as session:
                    connection = session.get(WhatsAppConnection, self.primary)
                    try:
                        await validate_routing(
                            SQLiteAsyncSession(session),
                            1,
                            connection,
                            f"{index}@g.us",
                            "group",
                            True,
                        )
                    except HTTPException as exc:
                        return exc.status_code
                    session.add(
                        DestinationChannel(
                            user_id=1,
                            chat_id=f"{index}@g.us",
                            chat_type="group",
                            platform="whatsapp",
                            connection_id=self.primary,
                            enabled=True,
                        )
                    )
                    session.commit()
                    return 201

            return asyncio.run(run())

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(activate, (200, 201))), [201, 409])

    def test_reassignment_cancels_queued_work_and_send_uses_snapshot_session(self):
        item = self.enqueue(1, chat_id="456@newsletter")
        kwargs = dict(self.fixture.broker.call_args.kwargs["kwargs"])
        self.fixture.make_ready()
        with patch.object(WahaClient, "send_offer", new_callable=AsyncMock) as send:
            with patch.object(WahaClient, "__init__", return_value=None) as constructor:
                post_promotion.run(**kwargs)
                constructor.assert_called_once_with(1, self.secondary)
                send.assert_awaited_once()
        second = self.enqueue(2, chat_id="456@newsletter")
        with self.connection() as conn:
            conn.execute(
                "UPDATE destination_channels SET connection_id=%s WHERE user_id=1 AND chat_id='456@newsletter'",
                (self.primary,),
            )
        self.assertEqual(
            reserve_delivery(second["id"], 1, "456@newsletter", time.time() + 600)[0],
            "stop",
        )
        with self.connection() as conn:
            row = conn.execute(
                "SELECT status,reason FROM promotion_deliveries WHERE id=%s",
                (second["id"],),
            ).fetchone()
        self.assertEqual(row, ("cancelled", "destination_connection_changed"))
        self.assertEqual(item["status"], "queued")

    def test_migration_preserves_legacy_session_routing_and_attempts(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0016_whatsapp_connections"
        )
        with self.fixture.engine.begin() as conn:
            schema = "migration_" + uuid4().hex
            conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
            conn.exec_driver_sql(f"SET LOCAL search_path={schema}")
            conn.exec_driver_sql("CREATE TABLE users(id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql("INSERT INTO users VALUES (1)")
            conn.exec_driver_sql(
                "CREATE TABLE destination_channels(id INTEGER PRIMARY KEY,user_id INTEGER,chat_id TEXT,platform TEXT)"
            )
            conn.exec_driver_sql(
                "INSERT INTO destination_channels VALUES (1,1,'123@newsletter','whatsapp')"
            )
            conn.exec_driver_sql(
                "CREATE TABLE promotion_deliveries(id TEXT PRIMARY KEY,user_id INTEGER,chat_id TEXT)"
            )
            conn.exec_driver_sql(
                "INSERT INTO promotion_deliveries VALUES ('old',1,'123@newsletter')"
            )
            conn.exec_driver_sql(
                "CREATE TABLE whatsapp_group_creations(request_id TEXT PRIMARY KEY,user_id INTEGER)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE whatsapp_send_attempts(id SERIAL PRIMARY KEY,user_id INTEGER,chat_id TEXT,attempted_at TIMESTAMPTZ)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE whatsapp_delivery_policies(user_id INTEGER PRIMARY KEY,config_data TEXT)"
            )
            conn.exec_driver_sql(
                "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at) VALUES (1,'123@newsletter',CURRENT_TIMESTAMP)"
            )
            conn.exec_driver_sql(
                "INSERT INTO whatsapp_delivery_policies(user_id,config_data) VALUES (1,'{\"max_per_hour\":60}')"
            )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
            primary = conn.exec_driver_sql(
                "SELECT id FROM whatsapp_connections WHERE user_id=1 AND is_default=true"
            ).scalar_one()
            self.assertEqual(
                conn.exec_driver_sql(
                    "SELECT connection_id FROM destination_channels WHERE user_id=1 AND chat_id='123@newsletter'"
                ).scalar_one(),
                primary,
            )
            self.assertEqual(
                conn.exec_driver_sql(
                    "SELECT connection_id FROM whatsapp_send_attempts WHERE user_id=1"
                ).scalar_one(),
                primary,
            )
            self.assertEqual(
                conn.exec_driver_sql(
                    "SELECT config_data FROM whatsapp_delivery_policies WHERE user_id=1"
                ).scalar_one(),
                '{"max_per_hour":60}',
            )
            self.assertEqual(
                conn.exec_driver_sql(
                    "SELECT connection_id FROM promotion_deliveries WHERE id='old'"
                ).scalar_one(),
                primary,
            )
            with Operations.context(MigrationContext.configure(conn)):
                migration.downgrade()
            self.assertEqual(
                conn.exec_driver_sql(
                    "SELECT id FROM promotion_deliveries"
                ).scalar_one(),
                "old",
            )
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
