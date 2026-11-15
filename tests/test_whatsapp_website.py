"""Offline website rotation tests exercise durable receipts, ownership and real ORM state."""

import os
import unittest
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import httpx
import sqlalchemy as sa
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.credentials import decrypt_config, encrypt_config
from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import User, DestinationChannel, WhatsAppGroupCreation
from backend.app.models.whatsapp_connection import WhatsAppConnection
from backend.app.models.whatsapp_website import WhatsAppWebsite
from backend.app.schemas.whatsapp_website import WebsiteSettings
from backend.app.core.whatsapp_entry import set_entry
from backend.worker import website_rotation as worker
from backend.worker.poster import BotPosterError
from tests.auth_fixtures import SQLiteAsyncSession, create_identity

load_models()
TOKEN = "test_abcdefghijklmnopqrstuvwxyz_123456789"
INVITE = "https://chat.whatsapp.com/ABCDEFGHIJKLMNOPQRSTUV"
PREFIX = "/users/me/whatsapp/website"


class Database(SQLiteAsyncSession):
    async def flush(self):
        self.session.flush()


@asynccontextmanager
async def unlocked(_user_id):
    yield True


class WebsiteFixture:
    def setup_database(self):
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.db = Database(self.session)
        self.environment = patch.dict(
            os.environ, {"CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        )
        self.environment.start()

    def close_database(self):
        self.session.close()
        self.engine.dispose()
        self.environment.stop()


class WebsiteAPITests(WebsiteFixture, unittest.TestCase):
    def setUp(self):
        self.setup_database()

        async def database():
            yield self.db

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        _, login = create_identity(self.session, "website@example.com")
        self.headers = {"Authorization": f"Bearer {login.token}"}
        self.user_id = self.client.get("/users/me", headers=self.headers).json()["id"]
        self.connection = WhatsAppConnection(
            user_id=self.user_id, name="Primary", is_default=True
        )
        self.session.add(self.connection)
        self.session.commit()
        self.lock_patch = patch(
            "backend.app.api.v1.endpoints.whatsapp_website.website_lock", unlocked
        )
        self.lock_patch.start()

    def tearDown(self):
        self.lock_patch.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.close_database()

    def save(self, **changes):
        body = WebsiteSettings(
            enabled=True,
            website_url="https://my-site.pages.dev",
            connection_id=self.connection.id,
        ).model_dump()
        return self.client.put(PREFIX, headers=self.headers, json={**body, **changes})

    def test_draft_without_pages_url_and_no_auth(self):
        self.assertEqual(self.client.get(PREFIX).status_code, 401)
        response = self.client.put(
            PREFIX, headers=self.headers, json=WebsiteSettings().model_dump()
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["settings"]["enabled"])

    def test_settings_encrypted_and_public_path_stable_without_token(self):
        response = self.save()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(TOKEN, response.text)
        self.assertNotIn("update_token", response.json()["settings"])
        path = response.json()["entry_path"]
        self.assertTrue(path.startswith("/join/whatsapp/"))
        stored = self.session.get(WhatsAppWebsite, self.user_id)
        self.assertTrue(stored.config_data.startswith("fernet:v1:"))
        self.assertNotIn(TOKEN, stored.config_data)
        self.assertEqual(self.save(entry_limit=900).status_code, 200)
        data = decrypt_config(stored.config_data, self.user_id, "whatsapp_website")
        self.assertNotIn("update_token", data)
        self.assertEqual(
            self.client.get(PREFIX, headers=self.headers).json()["entry_path"], path
        )
        self.assertEqual(data["entry_limit"], 900)
        self.assertEqual(
            self.client.get(PREFIX, headers=self.headers).headers["cache-control"],
            "no-store",
        )

    def test_reject_foreign_connection_and_template_and_ssrf_origins(self):
        other = User(email="foreign@example.com")
        self.session.add(other)
        self.session.flush()
        connection = WhatsAppConnection(
            user_id=other.id, name="Foreign", is_default=True
        )
        self.session.add(connection)
        destination = DestinationChannel(
            user_id=other.id, platform="whatsapp", chat_type="group", chat_id="999@g.us"
        )
        self.session.add(destination)
        self.session.commit()
        self.assertEqual(self.save(connection_id=connection.id).status_code, 404)
        self.assertEqual(
            self.save(template_destination_id=destination.id).status_code, 404
        )
        for url in [
            "http://site.pages.dev",
            "https://127.0.0.1",
            "https://user:pass@site.pages.dev",
            "https://site.pages.dev/api",
        ]:
            self.assertEqual(self.save(website_url=url).status_code, 422, url)
        self.assertEqual(
            self.save(website_url="https://my-own-domain.example").status_code, 200
        )

    def test_another_user_cannot_read_or_recover_owners_campaign(self):
        self.assertEqual(self.save().status_code, 200)
        _, login = create_identity(self.session, "other@example.com")
        headers = {"Authorization": f"Bearer {login.token}"}
        self.assertEqual(
            self.client.get(PREFIX, headers=headers).json()["settings"]["website_url"],
            "",
        )
        self.assertEqual(
            self.client.post(
                f"{PREFIX}/recover", headers=headers, json={"destination_id": 1}
            ).status_code,
            404,
        )

    def test_recovery_adopts_only_enabled_owned_admin_group(self):
        self.assertEqual(self.save().status_code, 200)
        destination = DestinationChannel(
            user_id=self.user_id,
            connection_id=self.connection.id,
            chat_id="123@g.us",
            platform="whatsapp",
            chat_type="group",
            enabled=False,
        )
        self.session.add(destination)
        self.session.commit()
        row = self.session.get(WhatsAppWebsite, self.user_id)
        row.pending_request_id = "uncertain-test-request"
        self.session.commit()
        with patch(
            "backend.app.api.v1.endpoints.whatsapp_website.WhatsAppManagement"
        ) as manager:
            manager.return_value.group = AsyncMock(return_value={"can_manage": True})
            response = self.client.post(
                f"{PREFIX}/recover",
                headers=self.headers,
                json={"destination_id": destination.id},
            )
            self.assertEqual(response.status_code, 400)
            destination.enabled = True
            self.session.commit()
            response = self.client.post(
                f"{PREFIX}/recover",
                headers=self.headers,
                json={"destination_id": destination.id},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["active_destination_id"], destination.id)
            self.assertFalse(response.json()["needs_recovery"])
            self.assertIsNone(row.pending_request_id)

    def active_campaign(self):
        self.assertEqual(self.save().status_code, 200)
        row = self.session.get(WhatsAppWebsite, self.user_id)
        destination = DestinationChannel(
            user_id=self.user_id,
            connection_id=self.connection.id,
            chat_id="123@g.us",
            platform="whatsapp",
            chat_type="group",
            enabled=True,
        )
        self.session.add(destination)
        self.session.flush()
        row.active_destination_id = destination.id
        row.member_count = 5
        row.observed_entry_limit = 10
        row.observed_at = worker.now()
        set_entry(row, INVITE)
        self.session.commit()
        return row, destination, f"/public/whatsapp/{row.public_id}"

    def test_public_redirect_and_head_need_no_login_or_waha(self):
        row, _, path = self.active_campaign()
        with patch(
            "backend.app.core.whatsapp.WahaClient.request", new_callable=AsyncMock
        ) as request:
            for method in ("GET", "HEAD"):
                response = self.client.request(
                    method, path + "?url=https://evil.example", follow_redirects=False
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["location"], INVITE)
                self.assertIn("no-store", response.headers["cache-control"])
                self.assertEqual(response.content, b"")
            request.assert_not_awaited()
        row.invite_url = "https://chat.whatsapp.com/ZYXWVUTSRQPONMLKJIHGFE"
        self.session.commit()
        self.assertEqual(
            self.client.get(path, follow_redirects=False).headers["location"],
            row.invite_url,
        )

    def test_public_redirect_rejects_unavailable_full_stale_and_invalid_snapshots(self):
        row, destination, path = self.active_campaign()
        for changes in (
            {"enabled": False},
            {"invite_url": None},
            {"invite_url": "https://evil.example"},
            {"member_count": None},
            {"member_count": 10},
            {"observed_entry_limit": None},
            {"pending_request_id": "uncertain"},
            {"active_destination_id": None},
            {"invite_expires_at": worker.now() - timedelta(seconds=1)},
            {"observed_at": worker.now() - timedelta(seconds=181)},
        ):
            with self.subTest(changes=changes):
                previous = {key: getattr(row, key) for key in changes}
                for key, value in changes.items():
                    setattr(row, key, value)
                self.session.commit()
                for method in ("GET", "HEAD"):
                    response = self.client.request(method, path, follow_redirects=False)
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn("location", response.headers)
                    self.assertIn("no-store", response.headers["cache-control"])
                    if method == "HEAD":
                        self.assertEqual(response.content, b"")
                for key, value in previous.items():
                    setattr(row, key, value)
                self.session.commit()
        destination.enabled = False
        self.session.commit()
        self.assertEqual(self.client.get(path).status_code, 503)

    def test_public_unknown_campaign_and_database_failure_are_controlled(self):
        from sqlalchemy.exc import OperationalError
        from uuid import uuid4

        _, _, path = self.active_campaign()
        self.assertEqual(
            self.client.get(f"/public/whatsapp/{uuid4()}").status_code, 503
        )
        with patch.object(
            self.db,
            "execute",
            side_effect=OperationalError("private SQL", {}, Exception("private host")),
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private", response.text)

    def test_campaign_disable_withdraws_immediately_and_transfer_cannot_redirect(self):
        row, destination, path = self.active_campaign()
        self.assertEqual(self.save(enabled=False).status_code, 200)
        self.assertIsNone(row.invite_url)
        self.assertEqual(self.client.get(path).status_code, 503)
        self.assertTrue(destination.enabled)
        row.enabled = True
        set_entry(row, INVITE)
        other = WhatsAppConnection(
            user_id=self.user_id, name="Secondary", is_default=False
        )
        self.session.add(other)
        self.session.flush()
        destination.connection_id = other.id
        self.session.commit()
        self.assertEqual(self.client.get(path).status_code, 503)


class WebsiteRotationTests(WebsiteFixture, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.setup_database()
        user = User(email="rotation@example.com")
        self.session.add(user)
        self.session.flush()
        self.connection = WhatsAppConnection(
            user_id=user.id, name="Primary", is_default=True
        )
        self.session.add(self.connection)
        self.session.flush()
        self.settings = WebsiteSettings(
            enabled=True,
            website_url="https://my-site.pages.dev",
            connection_id=self.connection.id,
            group_name="Deals",
            entry_limit=10,
            safety_margin=2,
        )
        self.row = WhatsAppWebsite(
            user_id=user.id,
            enabled=True,
            connection_id=self.connection.id,
            config_data=encrypt_config(
                self.settings.model_dump(), user.id, "whatsapp_website"
            ),
        )
        self.source = DestinationChannel(
            user_id=user.id,
            connection_id=self.connection.id,
            chat_id="123@g.us",
            platform="whatsapp",
            chat_type="group",
            title="Deals",
            categories=["tech"],
            enabled=True,
        )
        self.session.add_all([self.row, self.source])
        self.session.commit()
        self.row.active_destination_id = self.source.id
        self.session.commit()
        self.manager = AsyncMock()
        self.manager.client.status.return_value = {"status": "WORKING"}
        self.manager.client.groups.return_value = [{"name": "Deals"}]
        self.manager.create.return_value = "456@g.us"
        self.manager.group.return_value = {"description": "Template description"}
        self.manager.source_photo.return_value = None
        self.manager.apply_settings.return_value = []
        self.patches = [
            patch.object(worker, "WhatsAppManagement", return_value=self.manager),
            patch.object(worker, "group_observation", new_callable=AsyncMock),
            patch.object(
                worker, "group_invite", new_callable=AsyncMock, return_value=INVITE
            ),
        ]
        _, self.observe, self.invite = [p.start() for p in self.patches]

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.close_database()

    async def test_below_limit_refreshes_without_creating(self):
        self.observe.return_value = (9, 100)
        await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_not_awaited()
        self.assertEqual(self.row.invite_url, INVITE)
        self.assertEqual(
            self.row.invite_expires_at, self.row.observed_at + timedelta(seconds=180)
        )
        self.assertEqual(self.row.member_count, 9)

    async def test_full_creates_once_and_old_group_keeps_publication(self):
        self.observe.side_effect = [(10, 100), (1, 100)]
        await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_awaited_once_with("Deals #2")
        new = self.session.get(DestinationChannel, self.row.active_destination_id)
        self.assertNotEqual(new.id, self.source.id)
        self.assertTrue(self.source.enabled)
        self.assertTrue(new.enabled)
        self.assertEqual(new.categories, ["tech"])
        self.assertIsNone(self.row.pending_request_id)
        self.assertIsNone(self.row.pending_destination_id)
        receipt = self.session.query(WhatsAppGroupCreation).one()
        self.assertEqual(receipt.result["warnings"], [])
        self.assertEqual(self.row.invite_url, INVITE)
        self.observe.side_effect = None
        self.observe.return_value = (1, 100)
        await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_awaited_once()

    async def test_timeout_persists_intent_and_never_retries_creation(self):
        self.observe.return_value = (10, 100)
        self.manager.create.side_effect = httpx.ReadTimeout("uncertain")
        with self.assertRaises(httpx.ReadTimeout):
            await worker.reconcile(self.db, self.row, self.settings)
        self.assertIsNotNone(self.row.pending_request_id)
        self.assertIsNone(self.row.pending_destination_id)
        with self.assertRaisesRegex(BotPosterError, "incerto"):
            await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_awaited_once()
        self.assertIsNone(self.session.query(WhatsAppGroupCreation).one().result)

    async def test_partial_settings_remain_disabled_and_resume_known_group(self):
        self.observe.side_effect = [(10, 100), (1, 100)]
        self.manager.apply_settings.return_value = ["permission failed"]
        with self.assertRaisesRegex(BotPosterError, "incompleta"):
            await worker.reconcile(self.db, self.row, self.settings)
        pending = self.session.get(DestinationChannel, self.row.pending_destination_id)
        self.assertFalse(pending.enabled)
        self.assertEqual(self.row.active_destination_id, self.source.id)
        self.manager.apply_settings.return_value = []
        await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_awaited_once()
        self.assertTrue(pending.enabled)
        self.assertEqual(self.row.active_destination_id, pending.id)

    async def test_disabled_integration_withdraws_invite_without_waha(self):
        await worker.reconcile(
            self.db, self.row, self.settings.model_copy(update={"enabled": False})
        )
        self.assertIsNone(self.row.invite_url)
        self.manager.client.status.assert_not_awaited()
        self.assertTrue(self.source.enabled)

    async def test_disabled_active_group_is_withdrawn_and_not_reenabled(self):
        self.source.enabled = False
        self.session.commit()
        with self.assertRaisesRegex(BotPosterError, "desativadas"):
            await worker.reconcile(self.db, self.row, self.settings)
        self.assertIsNone(self.row.invite_url)
        self.manager.create.assert_not_awaited()
        self.assertFalse(self.source.enabled)

    async def test_unknown_count_and_failed_invite_never_publish_new_destination(self):
        self.observe.side_effect = BotPosterError("unknown")
        with self.assertRaises(BotPosterError):
            await worker.reconcile(self.db, self.row, self.settings)
        self.assertIsNone(self.row.invite_url)
        self.manager.create.assert_not_awaited()
        self.observe.side_effect = [(10, 100), (1, 100)]
        self.invite.side_effect = BotPosterError("invalid invite")
        with self.assertRaises(BotPosterError):
            await worker.reconcile(self.db, self.row, self.settings)
        self.assertEqual(self.row.active_destination_id, self.source.id)
        self.assertIsNotNone(self.row.pending_destination_id)
        self.assertIsNone(self.row.invite_url)

    async def test_group_quota_blocks_creation_without_disabling_old_group(self):
        self.observe.return_value = (10, 100)
        with patch.object(
            worker, "validate_routing", side_effect=worker.HTTPException(409, "quota")
        ):
            with self.assertRaises(worker.HTTPException):
                await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_not_awaited()
        self.assertTrue(self.source.enabled)

    async def test_snapshot_expiry_is_measured_from_observation_without_http(self):
        self.row.observed_at = worker.now() - timedelta(seconds=60)
        await self.db.commit()
        self.row.member_count = 1
        self.row.observed_entry_limit = 10
        set_entry(self.row, INVITE)
        self.assertEqual(
            self.row.invite_expires_at, self.row.observed_at + timedelta(seconds=180)
        )

    async def test_rotation_does_not_call_external_website(self):
        self.observe.side_effect = [(10, 100), (1, 100)]
        with patch.object(httpx, "AsyncClient") as client:
            await worker.reconcile(self.db, self.row, self.settings)
            client.assert_not_called()
        with Session(self.engine) as session:
            persisted = session.get(WhatsAppWebsite, self.row.user_id)
            self.assertEqual(persisted.invite_url, INVITE)


class ObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_participants_not_treated_as_zero(self):
        manager = AsyncMock()
        manager.path = lambda _: "session/groups/123%40g.us"
        for payload in [[], {}, [None], [{"unexpected": True}]]:
            manager.client.request.return_value = httpx.Response(200, json=payload)
            with self.assertRaises(BotPosterError):
                await worker.group_observation(manager, "123@g.us")

    async def test_invite_codes_constrained_to_whatsapp(self):
        manager = AsyncMock()
        manager.path = lambda _: "session/groups/123%40g.us"
        for payload in [
            {"code": "https://evil.example"},
            {"code": "ABC?next=evil"},
            {},
        ]:
            manager.client.request.return_value = httpx.Response(200, json=payload)
            with self.assertRaises(BotPosterError):
                await worker.group_invite(manager, "123@g.us")
        manager.client.request.return_value = httpx.Response(
            200, json={"code": "ABCDEFGHIJKLMNOPQRSTUV"}
        )
        self.assertEqual(await worker.group_invite(manager, "123@g.us"), INVITE)
