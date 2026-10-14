"""Tenant isolation, authenticated pairing, and destination delivery routing."""

import base64
import importlib
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp import WahaClient
from backend.app.main import app
from backend.app.models.user import DestinationChannel
from backend.worker.poster import BotPosterError
from backend.worker.posting_queue import deliver
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class WhatsAppAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.db = SQLiteAsyncSession(self.session)

        async def database():
            yield self.db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.seen = []
        seen = self.seen

        async def request(client, method, path, body=None, timeout=20):
            seen.append((client.session, method, path, body))
            if path.endswith("/auth/qr"):
                return httpx.Response(
                    200, content=b"qr", headers={"content-type": "image/png"}
                )
            if path.endswith("/channels"):
                return httpx.Response(
                    200,
                    json=[
                        {"id": "123@newsletter", "name": "Meu canal", "role": "ADMIN"},
                        {
                            "id": "999@newsletter",
                            "name": "Canal seguido",
                            "role": "SUBSCRIBER",
                        },
                    ],
                )
            if path.endswith("/groups"):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": {"_serialized": "123@g.us"},
                            "groupMetadata": {"subject": "Ofertas"},
                        }
                    ],
                )
            if "/groups/" in path:
                return httpx.Response(200, json={"groupMetadata": {"announce": False}})
            return httpx.Response(
                200, json={"status": "WORKING", "me": {"pushName": "Conta"}}
            )

        self.request_patch = patch.object(WahaClient, "request", request)
        self.request_patch.start()
        self.env_patch = patch.dict(
            "os.environ",
            {"WAHA_BASE_URL": "http://waha:3000", "WAHA_API_KEY": "operator-secret"},
        )
        self.env_patch.start()

    def tearDown(self):
        self.request_patch.stop()
        self.env_patch.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def login(self, email):
        _, login = create_identity(self.session, email)
        headers = {"Authorization": f"Bearer {login.token}"}
        user = self.client.get("/users/me", headers=headers).json()
        return user["id"], headers

    def test_pairing_requires_login_and_scopes_qr_to_session_owner(self):
        self.assertEqual(self.client.get("/users/me/whatsapp/qr").status_code, 401)
        for email in ("first@example.com", "second@example.com"):
            user_id, headers = self.login(email)
            response = self.client.get(
                "/users/me/whatsapp/qr?session=offers-user-999", headers=headers
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(self.seen[-1][0], f"offers-user-{user_id}")
            self.assertEqual(
                response.json()["qr"],
                "data:image/png;base64," + base64.b64encode(b"qr").decode(),
            )
            self.assertNotIn("operator-secret", response.text)

    def test_destination_rejects_groups_outside_account(self):
        _, headers = self.login("user@example.com")
        payload = {
            "chat_id": "999@g.us",
            "platform": "whatsapp",
            "chat_type": "group",
            "enabled": True,
        }
        response = self.client.post(
            "/users/me/destinations", headers=headers, json=payload
        )
        self.assertEqual(response.status_code, 400)
        payload["chat_id"] = "123@g.us"
        response = self.client.post(
            "/users/me/destinations", headers=headers, json=payload
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["platform"], "whatsapp")

    def test_disconnect_disables_only_owners_whatsapp_destinations(self):
        user_id, headers = self.login("user@example.com")
        other_id, _ = self.login("other@example.com")
        for owner, platform, chat in (
            (user_id, "whatsapp", "123@g.us"),
            (user_id, "telegram", "-100123"),
            (other_id, "whatsapp", "123@g.us"),
        ):
            self.session.add(
                DestinationChannel(
                    user_id=owner, platform=platform, chat_id=chat, enabled=True
                )
            )
        self.session.commit()
        response = self.client.delete("/users/me/whatsapp", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.session.expire_all()
        for row in self.session.query(DestinationChannel).all():
            self.assertEqual(
                row.enabled, not (row.user_id == user_id and row.platform == "whatsapp")
            )
        self.assertEqual(self.seen[-1][2], f"sessions/offers-user-{user_id}")

    def test_only_admin_channels_can_be_selected_and_saved(self):
        user_id, headers = self.login("channels@example.com")
        listed = self.client.get(
            "/users/me/whatsapp/channels?session=offers-user-999", headers=headers
        )
        self.assertEqual(listed.json(), [{"id": "123@newsletter", "name": "Meu canal"}])
        self.assertEqual(self.seen[-1][0], f"offers-user-{user_id}")
        payload = {
            "platform": "whatsapp",
            "chat_type": "channel",
            "chat_id": "999@newsletter",
        }
        self.assertEqual(
            self.client.post(
                "/users/me/destinations", headers=headers, json=payload
            ).status_code,
            400,
        )
        payload["chat_id"] = "123@newsletter"
        response = self.client.post(
            "/users/me/destinations", headers=headers, json=payload
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["chat_type"], "channel")

    def test_reject_mismatched_whatsapp_destination_type(self):
        _, headers = self.login("types@example.com")
        for chat, kind, platform in (
            ("123@newsletter", "group", "whatsapp"),
            ("123@g.us", "channel", "whatsapp"),
            ("123@newsletter", "channel", "telegram"),
        ):
            response = self.client.post(
                "/users/me/destinations",
                headers=headers,
                json={"chat_id": chat, "chat_type": kind, "platform": platform},
            )
            self.assertEqual(response.status_code, 422)


class WhatsAppDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_channel_photo_targets_newsletter_in_tenants_session(self):
        client = WahaClient(7)
        client.request = AsyncMock(
            return_value=httpx.Response(200, json={"id": "sent"})
        )
        await client.send_offer(
            "123@newsletter", "Oferta", image_file="https://example.com/image.webp"
        )
        _, endpoint, payload = client.request.call_args.args
        self.assertEqual(endpoint, "sendImage")
        self.assertEqual(payload["chatId"], "123@newsletter")
        self.assertEqual(payload["session"], "offers-user-7")
        self.assertEqual(payload["file"]["mimetype"], "image/webp")

    async def test_whatsapp_delivery_never_uses_telegram_token(self):
        with (
            patch.object(WahaClient, "send_offer", new_callable=AsyncMock) as send,
            patch("backend.worker.posting_queue.BotPoster") as telegram,
        ):
            await deliver(
                "123@g.us",
                "Oferta",
                time.time() + 60,
                None,
                None,
                None,
                user_id=7,
                platform="whatsapp",
            )
        telegram.assert_not_called()
        send.assert_awaited_once()
        self.assertEqual(send.call_args.args, ("123@g.us", "Oferta"))

    async def test_restricted_group_requires_admin(self):
        client = WahaClient(7)
        client.groups = AsyncMock(return_value=[{"id": "123@g.us", "name": "Ofertas"}])
        client.request = AsyncMock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "groupMetadata": {
                            "announce": True,
                            "participants": [{"id": "1@c.us", "isAdmin": False}],
                        }
                    },
                ),
                httpx.Response(200, json={"id": "1@c.us"}),
            ]
        )
        with self.assertRaises(BotPosterError):
            await client.verify_group("123@g.us")

    async def test_photo_uses_tenant_session_without_exposing_operator_key(self):
        client = WahaClient(7)
        client.request = AsyncMock(
            return_value=httpx.Response(200, json={"id": "sent"})
        )
        await client.send_offer(
            "123@g.us", "Oferta", image_file="https://example.com/photo.jpg"
        )
        _, endpoint, payload = client.request.call_args.args
        self.assertEqual(endpoint, "sendImage")
        self.assertEqual(payload["session"], "offers-user-7")
        self.assertEqual(payload["caption"], "Oferta")


class WhatsAppMigrationTests(unittest.TestCase):
    def test_existing_destinations_remain_telegram(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        migration = importlib.import_module(
            "backend.alembic.versions.0009_whatsapp_destinations"
        )
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE destination_channels (id INTEGER PRIMARY KEY, chat_id TEXT)"
            )
            connection.exec_driver_sql(
                "INSERT INTO destination_channels (chat_id) VALUES ('-100123')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            self.assertEqual(
                connection.exec_driver_sql(
                    "SELECT chat_id, platform FROM destination_channels"
                ).one(),
                ("-100123", "telegram"),
            )
