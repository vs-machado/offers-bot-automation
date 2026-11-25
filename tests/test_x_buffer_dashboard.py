import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import FastAPI
import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.api.v1.endpoints.x_buffer import get_db, router
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel, User
from backend.app.models.worker import XBufferSettings


@unittest.skipUnless(
    os.getenv("X_OFFERS_DASHBOARD_TEST_DATABASE_URL"),
    "Requires a migrated disposable PostgreSQL database",
)
class BufferDashboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_can_save_test_and_pause_without_exposing_the_key(self):
        load_models()
        engine = create_async_engine(os.environ["X_OFFERS_DASHBOARD_TEST_DATABASE_URL"])
        self.addAsyncCleanup(engine.dispose)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions.begin() as db:
            user = User(email=f"{uuid4()}@example.test", role="user")
            db.add(user)
            await db.flush()
            dest = DestinationChannel(user_id=user.id, chat_id="-100123", enabled=True)
            db.add(dest)
            await db.flush()

        async def provide_db():
            async with sessions() as db:
                yield db

        async def current_user():
            return user

        app = FastAPI()
        app.include_router(router, prefix="/admin")
        app.dependency_overrides[get_db] = provide_db
        app.dependency_overrides[get_current_user] = current_user
        url = "/admin/x-buffer"
        draft = {
            "enabled": True,
            "destination_id": dest.id,
            "landing_url": "https://vsm.example/ofertas",
            "channel_id": "vsm-channel",
            "daily_limit": 1,
        }
        secret = "buffer-private-key"
        with patch.dict(
            os.environ, {"CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                self.assertEqual((await client.get(url)).status_code, 403)
                self.assertEqual(
                    (
                        await client.put(url, json={**draft, "api_key": secret})
                    ).status_code,
                    403,
                )
                user.role = "admin"
                self.assertEqual((await client.put(url, json=draft)).status_code, 422)
                saved = await client.put(url, json={**draft, "api_key": secret})
                self.assertEqual(saved.status_code, 200)
                self.assertNotIn(secret, saved.text)
                self.assertTrue(saved.json()["settings"]["has_api_key"])
                paused = await client.put(url, json={**draft, "enabled": False})
                self.assertFalse(paused.json()["settings"]["enabled"])
                with patch(
                    "backend.worker.buffer_publisher.BufferPublisher.check_connection",
                    autospec=True,
                    return_value="vsm",
                ) as probe:
                    self.assertEqual(
                        (await client.post(url + "/check")).json(), {"account": "vsm"}
                    )
                    self.assertEqual(probe.call_args.args[0].token, secret)
            async with sessions() as db:
                stored = await db.get(XBufferSettings, 1)
                self.assertTrue(stored.encrypted_key.startswith("fernet:v1:"))
                self.assertNotIn(secret, stored.encrypted_key)
