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
from backend.worker import website_rotation as worker
from backend.worker.poster import BotPosterError
from tests.auth_fixtures import SQLiteAsyncSession, create_identity

load_models()
TOKEN = "test_abcdefghijklmnopqrstuvwxyz_123456789"
INVITE = "https://chat.whatsapp.com/ABCDEFGHIJKLMNOPQRSTUV"
PREFIX = "/users/me/whatsapp/website"
PUSH_WEBSITE = worker.push_website


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
            update_token=TOKEN,
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

    def test_secret_is_encrypted_and_mask_survives_update(self):
        response = self.save()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(TOKEN, response.text)
        self.assertEqual(response.json()["settings"]["update_token"], "********")
        stored = self.session.get(WhatsAppWebsite, self.user_id)
        self.assertTrue(stored.config_data.startswith("fernet:v1:"))
        self.assertNotIn(TOKEN, stored.config_data)
        self.assertEqual(
            self.save(update_token="********", entry_limit=900).status_code, 200
        )
        data = decrypt_config(stored.config_data, self.user_id, "whatsapp_website")
        self.assertEqual(data["update_token"], TOKEN)
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
            "https://site.pages.dev.evil.test",
            "https://user:pass@site.pages.dev",
            "https://site.pages.dev/api",
        ]:
            self.assertEqual(self.save(website_url=url).status_code, 422, url)

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
            update_token=TOKEN,
            connection_id=self.connection.id,
            group_name="Deals",
            entry_limit=10,
            safety_margin=2,
        )
        self.row = WhatsAppWebsite(
            user_id=user.id,
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
            patch.object(worker, "push_website", new_callable=AsyncMock),
            patch.object(worker, "group_observation", new_callable=AsyncMock),
            patch.object(
                worker, "group_invite", new_callable=AsyncMock, return_value=INVITE
            ),
        ]
        _, self.push, self.observe, self.invite = [p.start() for p in self.patches]

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.close_database()

    async def test_below_limit_refreshes_without_creating(self):
        self.observe.return_value = (9, 100)
        await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_not_awaited()
        self.push.assert_awaited_once_with(self.db, self.row, self.settings, INVITE)
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
        self.assertEqual(
            self.push.await_args_list[0].args, (self.db, self.row, self.settings)
        )
        self.assertEqual(self.push.await_args_list[-1].args[-1], INVITE)
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
        self.push.assert_awaited_once()
        self.manager.client.status.assert_not_awaited()
        self.assertTrue(self.source.enabled)

    async def test_disabled_active_group_is_withdrawn_and_not_reenabled(self):
        self.source.enabled = False
        self.session.commit()
        with self.assertRaisesRegex(BotPosterError, "desativadas"):
            await worker.reconcile(self.db, self.row, self.settings)
        self.push.assert_awaited_once_with(self.db, self.row, self.settings)
        self.manager.create.assert_not_awaited()
        self.assertFalse(self.source.enabled)

    async def test_unknown_count_and_failed_invite_never_publish_new_destination(self):
        self.observe.side_effect = BotPosterError("unknown")
        with self.assertRaises(BotPosterError):
            await worker.reconcile(self.db, self.row, self.settings)
        self.push.assert_not_awaited()
        self.manager.create.assert_not_awaited()
        self.observe.side_effect = [(10, 100), (1, 100)]
        self.invite.side_effect = BotPosterError("invalid invite")
        with self.assertRaises(BotPosterError):
            await worker.reconcile(self.db, self.row, self.settings)
        self.assertEqual(self.row.active_destination_id, self.source.id)
        self.assertIsNotNone(self.row.pending_destination_id)
        self.assertEqual(len(self.push.await_args_list[0].args), 3)

    async def test_group_quota_blocks_creation_without_disabling_old_group(self):
        self.observe.return_value = (10, 100)
        with patch.object(
            worker, "validate_routing", side_effect=worker.HTTPException(409, "quota")
        ):
            with self.assertRaises(worker.HTTPException):
                await worker.reconcile(self.db, self.row, self.settings)
        self.manager.create.assert_not_awaited()
        self.assertTrue(self.source.enabled)

    async def test_push_persists_revision_before_http_and_does_not_renew_observation(
        self,
    ):
        self.row.observed_at = worker.now() - timedelta(seconds=60)
        await self.db.commit()
        with patch.object(worker.httpx, "AsyncClient") as client:
            post = client.return_value.__aenter__.return_value.post

            async def acknowledge(*_args, **_kwargs):
                revision = self.session.execute(
                    sa.select(WhatsAppWebsite.revision)
                ).scalar_one()
                self.assertEqual(revision, 1)
                return httpx.Response(200, json={"revision": revision})

            post.side_effect = acknowledge
            await PUSH_WEBSITE(self.db, self.row, self.settings, INVITE)
            payload = post.call_args.kwargs["json"]
            self.assertEqual(
                payload["expires_at"],
                int((self.row.observed_at + timedelta(seconds=180)).timestamp()),
            )
            self.assertEqual(set(payload), {"revision", "invite_url", "expires_at"})
            self.assertEqual(
                post.call_args.kwargs["headers"], {"Authorization": f"Bearer {TOKEN}"}
            )
            self.assertFalse(client.call_args.kwargs["follow_redirects"])
        self.assertIsNotNone(self.row.last_synced_at)

    async def test_push_timeout_keeps_revision_durable_and_retry_advances(self):
        with patch.object(worker.httpx, "AsyncClient") as client:
            post = client.return_value.__aenter__.return_value.post
            post.side_effect = httpx.ReadTimeout("site unavailable")
            with self.assertRaises(httpx.ReadTimeout):
                await PUSH_WEBSITE(self.db, self.row, self.settings)
            self.assertEqual(
                self.session.execute(sa.select(WhatsAppWebsite.revision)).scalar_one(),
                1,
            )
            self.assertIsNone(self.row.last_synced_at)
            post.side_effect = None
            post.return_value = httpx.Response(200, json={"revision": 2})
            await PUSH_WEBSITE(self.db, self.row, self.settings)
            self.assertEqual(self.row.revision, 2)


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
