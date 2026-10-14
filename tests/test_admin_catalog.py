import importlib
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.endpoints import auth
from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.models.user import User
from backend.worker.telegram_reader import TelegramSourceReader


class SQLiteAsyncSession:
    """Run API ORM operations against isolated SQLite instead of mocking catalog state."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, item):
        self.session.add(item)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, item):
        self.session.refresh(item)

    async def delete(self, item):
        self.session.delete(item)


class AdminCatalogTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.db = SQLiteAsyncSession(self.session)
        self.admin = User(
            email="admin@example.com",
            role="admin",
            auth_provider="credentials",
            created_at=datetime.now(timezone.utc),
        )
        self.user = User(
            email="user@example.com",
            role="user",
            auth_provider="credentials",
            created_at=datetime.now(timezone.utc),
        )
        self.session.add_all([self.admin, self.user])
        self.session.commit()
        auth._rate_limit_buckets.clear()

        async def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.admin_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': self.admin.email})}"
        }
        self.user_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': self.user.email, 'role': 'admin'})}"
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_every_admin_operation_rejects_anonymous_and_regular_users(self):
        for method, path in [
            ("GET", "/admin/source-groups"),
            ("POST", "/admin/source-groups"),
            ("PUT", "/admin/source-groups/1"),
            ("DELETE", "/admin/source-groups/1"),
        ]:
            for headers, expected in [({}, 401), (self.user_headers, 403)]:
                with self.subTest(method=method, status=expected):
                    response = self.client.request(
                        method,
                        path,
                        headers=headers,
                        json={"url": "@newsource", "label": "New source"},
                    )
                    self.assertEqual(response.status_code, expected)

    def test_admin_crud_changes_user_catalog_and_selection_validation(self):
        response = self.client.post(
            "/admin/source-groups",
            headers=self.admin_headers,
            json={"url": "@NEWSOURCE", "label": " New source "},
        )
        self.assertEqual(response.status_code, 201)
        group = response.json()
        self.assertEqual(group["url"], "https://t.me/newsource")
        self.assertEqual(group["label"], "New source")
        duplicate = self.client.post(
            "/admin/source-groups",
            headers=self.admin_headers,
            json={"url": group["url"], "label": "Duplicate"},
        )
        self.assertEqual(duplicate.status_code, 409)
        with patch(
            "backend.app.api.v1.endpoints.users.fetch_source_messages",
            new=AsyncMock(return_value={}),
        ):
            catalog = self.client.get(
                "/users/me/source-groups/messages", headers=self.user_headers
            ).json()
        self.assertEqual(
            [(item["id"], item["label"]) for item in catalog["groups"]],
            [(group["url"], "New source")],
        )
        selected = self.client.post(
            "/users/me/configs",
            headers=self.user_headers,
            json={
                "config_type": "source_chats",
                "config_data": {"source_chats": ["@newsource"]},
            },
        )
        self.assertEqual(selected.status_code, 201)
        self.assertEqual(selected.json()["config_data"]["source_chats"], [group["url"]])
        updated = self.client.put(
            f"/admin/source-groups/{group['id']}",
            headers=self.admin_headers,
            json={"url": group["url"], "label": "Paused source", "enabled": False},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["enabled"])
        self.assertEqual(
            self.client.get(
                "/users/me/source-groups/messages", headers=self.user_headers
            ).json()["groups"],
            [],
        )
        rejected = self.client.post(
            "/users/me/configs",
            headers=self.user_headers,
            json={
                "config_type": "source_chats",
                "config_data": {"source_chats": [group["url"]]},
            },
        )
        self.assertEqual(rejected.status_code, 400)
        deleted = self.client.delete(
            f"/admin/source-groups/{group['id']}", headers=self.admin_headers
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get("/admin/source-groups", headers=self.admin_headers).json(),
            [],
        )

    def test_role_revocation_applies_to_existing_token(self):
        self.assertEqual(
            self.client.get(
                "/admin/source-groups", headers=self.admin_headers
            ).status_code,
            200,
        )
        self.admin.role = "user"
        self.session.commit()
        self.assertEqual(
            self.client.get(
                "/admin/source-groups", headers=self.admin_headers
            ).status_code,
            403,
        )

    def test_registration_cannot_choose_admin_role(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "Validpass1",
                "role": "admin",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "user")

    def test_bad_urls_and_unknown_sources_are_rejected(self):
        for url in [
            "https://evil.example/groupname",
            "https://t.me/+privateinvite",
            "https://t.me/groupname/123",
        ]:
            with self.subTest(url=url):
                response = self.client.post(
                    "/admin/source-groups",
                    headers=self.admin_headers,
                    json={"url": url, "label": "Source"},
                )
                self.assertEqual(response.status_code, 422)
        response = self.client.post(
            "/users/me/configs",
            headers=self.user_headers,
            json={
                "config_type": "source_chats",
                "config_data": {"source_chats": ["@promotom"]},
            },
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/users/me/source-groups/preview",
            headers=self.user_headers,
            json={"chat": "@promotom"},
        )
        self.assertEqual(response.status_code, 400)


class CatalogMigrationTests(unittest.TestCase):
    def test_migration_preserves_users_and_seeds_catalog_once(self):
        revision = importlib.import_module(
            "backend.alembic.versions.0004_admin_source_catalog"
        )
        engine = sa.create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255))"
                )
            )
            connection.execute(
                sa.text("INSERT INTO users VALUES (1, 'existing@example.com')")
            )
            with patch.object(
                revision, "op", Operations(MigrationContext.configure(connection))
            ):
                revision.upgrade()
                self.assertEqual(
                    connection.execute(sa.text("SELECT role FROM users")).scalar_one(),
                    "user",
                )
                self.assertEqual(
                    connection.execute(
                        sa.text(
                            "SELECT count(*) FROM source_groups WHERE enabled = true"
                        )
                    ).scalar_one(),
                    7,
                )
                revision.downgrade()
            self.assertNotIn("source_groups", sa.inspect(connection).get_table_names())
            self.assertEqual(
                connection.execute(sa.text("SELECT email FROM users")).scalar_one(),
                "existing@example.com",
            )
        engine.dispose()


class LiveCatalogReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_reader_adds_and_removes_catalog_sources_without_restart(self):
        bot = MagicMock()
        bot.client = AsyncMock()
        bot.client.get_entity.return_value = SimpleNamespace(id=88)
        with (
            patch.dict(
                os.environ, {"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "test-hash"}
            ),
            patch("backend.worker.telegram_reader.SessionStore"),
            patch("backend.worker.telegram_reader.TelegramOfferBot", return_value=bot),
            patch(
                "backend.worker.telegram_reader.utils.get_peer_id", return_value=-10088
            ),
        ):
            reader = TelegramSourceReader([])
            reader._ready = True
            await reader.refresh_sources(["https://t.me/newsource"])
            self.assertEqual(reader._sources, {"-10088": "https://t.me/newsource"})
            bot.set_allowed_source_ids.assert_called_with({"-10088"})
            await reader.refresh_sources([])
            self.assertEqual(reader._sources, {})
            bot.set_allowed_source_ids.assert_called_with(set())
            reader._store.close()
