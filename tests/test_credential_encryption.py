"""Credential persistence, migration, rotation and API secrecy regression tests."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import sqlalchemy as sa
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.endpoints import users
from backend.app.core.credentials import (
    MASK,
    PREFIX,
    credential_cipher,
    decrypt_config,
    encrypt_config,
)
from backend.app.core.db.credential_rotation import reencrypt_configs
from backend.app.models.user import UserConfig
from backend.worker.manager import UserBotInstance
from offers_bot.iop import base as iop
from tests.auth_fixtures import SQLiteAsyncSession


class EncryptionTests(unittest.TestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode()
        self.env = patch.dict(
            os.environ,
            {
                "CREDENTIALS_ENCRYPTION_KEY": self.key,
                "CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_randomized_authenticated_encryption_binds_owner_and_provider(self):
        data = {"ml_cookie_header": "session=segredo", "label": "Configuração"}
        first = encrypt_config(data, 7, "mercado_livre")
        second = encrypt_config(data, 7, "mercado_livre")
        self.assertTrue(first.startswith(PREFIX))
        self.assertNotEqual(first, second)
        self.assertNotIn("segredo", first)
        self.assertEqual(decrypt_config(first, 7, "mercado_livre"), data)
        for value, owner, provider in (
            (first, 8, "mercado_livre"),
            (first, 7, "shopee"),
            (first[:30] + "!" + first[31:], 7, "mercado_livre"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Unable to decrypt"):
                decrypt_config(value, owner, provider)
        with patch.dict(
            os.environ, {"CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        ):
            with self.assertRaisesRegex(RuntimeError, "Unable to decrypt"):
                decrypt_config(first, 7, "mercado_livre")

    def test_missing_or_invalid_key_fails_closed(self):
        for key in ("", "not-a-key", "á"):
            with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": key}):
                with self.assertRaises(RuntimeError):
                    credential_cipher()
                with self.assertRaises(RuntimeError):
                    encrypt_config({}, 7, "amazon")

    def test_sdk_logs_and_transport_errors_do_not_expose_credentials(self):
        with patch.object(iop, "logger") as logger:
            iop.logApiError(
                "private-key",
                "sdk",
                "https://example.test/?session=private-token",
                "HTTP_ERROR",
                "private-message",
            )
        logged = str(logger.error.call_args)
        for secret in ("private-key", "private-token", "private-message"):
            self.assertNotIn(secret, logged)
        client = iop.IopClient("https://example.test", "private-key", "private-secret")
        request = iop.IopRequest("test")
        with (
            patch.object(
                iop.requests, "post", side_effect=RuntimeError("private-token")
            ),
            patch.object(iop, "logger"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "^AliExpress HTTP request failed$"
            ) as caught:
                client.execute(request, access_token="private-token")
        self.assertTrue(caught.exception.__suppress_context__)

    def test_migration_rotation_and_atomic_failure(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        metadata = sa.MetaData()
        table = sa.Table(
            "user_configs",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.Integer),
            sa.Column("config_type", sa.String),
            sa.Column("config_data", sa.String),
        )
        metadata.create_all(engine)
        data = {"shopee_app_secret": "stored-secret"}
        with engine.begin() as conn:
            conn.execute(
                table.insert(),
                {
                    "id": 1,
                    "user_id": 7,
                    "config_type": "shopee",
                    "config_data": json.dumps(data),
                },
            )
            self.assertEqual(reencrypt_configs(conn), 1)
        with engine.connect() as conn:
            old = conn.scalar(sa.select(table.c.config_data))
        self.assertNotIn("stored-secret", old)
        self.assertEqual(decrypt_config(old, 7, "shopee"), data)

        new_key = Fernet.generate_key().decode()
        with patch.dict(
            os.environ,
            {
                "CREDENTIALS_ENCRYPTION_KEY": new_key,
                "CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS": self.key,
            },
        ):
            with engine.begin() as conn:
                self.assertEqual(reencrypt_configs(conn), 1)
        with patch.dict(os.environ, {"CREDENTIALS_ENCRYPTION_KEY": new_key}):
            with engine.connect() as conn:
                rotated = conn.scalar(sa.select(table.c.config_data))
            self.assertEqual(decrypt_config(rotated, 7, "shopee"), data)
            with self.assertRaises(RuntimeError):
                decrypt_config(old, 7, "shopee")
            with engine.begin() as conn:
                conn.execute(
                    table.insert(),
                    {
                        "id": 2,
                        "user_id": 8,
                        "config_type": "shopee",
                        "config_data": PREFIX + "invalid",
                    },
                )
            with self.assertRaises(RuntimeError):
                with engine.begin() as conn:
                    reencrypt_configs(conn)
            with engine.connect() as conn:
                self.assertEqual(
                    conn.scalar(sa.select(table.c.config_data).where(table.c.id == 1)),
                    rotated,
                )


class CredentialApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        self.addCleanup(engine.dispose)
        UserConfig.__table__.create(engine)
        self.session = Session(engine)
        self.addCleanup(self.session.close)
        db = SQLiteAsyncSession(self.session)
        app = FastAPI()
        app.include_router(users.router)
        app.dependency_overrides[users.get_current_user] = lambda: SimpleNamespace(id=7)
        app.dependency_overrides[users.get_db] = lambda: db
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def create_config(self):
        response = self.client.post(
            "/me/configs",
            json={
                "config_type": "shopee",
                "config_data": {
                    "shopee_app_id": "123",
                    "shopee_app_secret": "original-secret",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_persist_list_update_and_probe_never_return_saved_secrets(self):
        created = self.create_config()
        self.assertEqual(created["config_data"]["shopee_app_secret"], MASK)
        row = self.session.get(UserConfig, created["id"])
        self.assertTrue(row.config_data.startswith(PREFIX))
        self.assertNotIn("original-secret", row.config_data)
        listed = self.client.get("/me/configs")
        self.assertNotIn("original-secret", listed.text)
        self.assertNotIn(PREFIX, listed.text)
        values = {"shopee_app_id": "456", "shopee_app_secret": MASK}
        updated = self.client.put(
            f"/me/configs/{row.id}",
            json={"config_type": "shopee", "config_data": values},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            decrypt_config(row.config_data, 7, "shopee")["shopee_app_secret"],
            "original-secret",
        )
        with patch(
            "backend.app.core.affiliate_validation.probe", new_callable=AsyncMock
        ) as probe:
            result = self.client.post(
                "/me/affiliate-credentials/validate",
                json={"provider": "shopee", "config_data": values},
            )
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("original-secret", result.text)
        self.assertEqual(
            probe.call_args.args[2]["shopee_app_secret"], "original-secret"
        )
        values["shopee_app_secret"] = "replacement-secret"
        result = self.client.put(
            f"/me/configs/{row.id}",
            json={"config_type": "shopee", "config_data": values},
        )
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("replacement-secret", result.text)
        self.assertEqual(
            decrypt_config(row.config_data, 7, "shopee")["shopee_app_secret"],
            "replacement-secret",
        )

    def test_placeholders_cannot_borrow_another_users_or_providers_secret(self):
        row = UserConfig(
            user_id=8,
            config_type="shopee",
            config_data=encrypt_config(
                {"shopee_app_secret": "other-secret"}, 8, "shopee"
            ),
        )
        self.session.add(row)
        self.session.commit()
        payload = {
            "config_type": "shopee",
            "config_data": {"shopee_app_id": "123", "shopee_app_secret": MASK},
        }
        self.assertEqual(self.client.post("/me/configs", json=payload).status_code, 400)
        self.assertEqual(
            self.client.put(f"/me/configs/{row.id}", json=payload).status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/me/affiliate-credentials/validate",
                json={"provider": "shopee", "config_data": payload["config_data"]},
            ).status_code,
            400,
        )
        own = self.create_config()
        response = self.client.put(
            f"/me/configs/{own['id']}",
            json={
                "config_type": "aliexpress",
                "config_data": {
                    "aliexpress_app_key": "key",
                    "aliexpress_app_secret": MASK,
                },
            },
        )
        self.assertEqual(response.status_code, 400)


class EncryptedWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_reads_encrypted_credentials(self):
        with patch.dict(
            os.environ,
            {
                "CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                "CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS": "",
            },
        ):
            row = UserConfig(
                user_id=7,
                config_type="shopee",
                config_data=encrypt_config(
                    {"shopee_app_id": "123", "shopee_app_secret": "worker-secret"},
                    7,
                    "shopee",
                ),
            )
            db = SimpleNamespace(execute=AsyncMock())
            db.execute.return_value = MagicMock()
            db.execute.return_value.scalars.return_value.all.return_value = [row]
            bot = UserBotInstance(user_id=7, db_factory=None)
            values = await bot._load_configs(db)
            self.assertEqual(values["shopee_app_secret"], "worker-secret")


if __name__ == "__main__":
    unittest.main()
