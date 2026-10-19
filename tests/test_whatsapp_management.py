"""Offline management integration tests: tenant isolation, cloning, retries, and routing."""

import base64
import copy
import importlib
import unittest
from unittest.mock import patch
from uuid import uuid4

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
from backend.app.core.whatsapp_management import is_admin, member_count, next_group_name
from backend.app.main import app
from backend.app.models.user import DestinationChannel, WhatsAppGroupCreation
from tests.auth_fixtures import SQLiteAsyncSession, create_identity

PREFIX = "/users/me/whatsapp/manage"


class WhatsAppManagementTests(unittest.TestCase):
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
        self.headers, self.user_id = self.login("owner@example.com")
        self.seen = []
        self.fail_setting = None
        self.timeout_create = False
        self.fail_groups = False
        self.source = {
            "id": {"_serialized": "123@g.us"},
            "groupMetadata": {
                "subject": "My tech group #2",
                "desc": "Original description",
                "size": 1024,
                "participants": [{"id": "12345@lid", "pn": "1@c.us", "role": "admin"}],
            },
        }
        self.groups = [self.source, {"id": "456@g.us", "subject": "My tech group #4"}]

        async def request(client, method, path, body=None, timeout=20):
            self.seen.append((client.session, method, path, body))
            own = client.session == f"offers-user-{self.user_id}"
            if method == "POST" and path.endswith("/groups"):
                if self.timeout_create:
                    raise httpx.ReadTimeout("Outcome unknown")
                self.groups.append(
                    {
                        "id": "789@g.us",
                        "subject": body["name"],
                        "participants": [{"id": "1@c.us", "role": "superadmin"}],
                    }
                )
                return httpx.Response(200, json={"gid": {"_serialized": "789@g.us"}})
            if method == "PUT":
                return httpx.Response(
                    200,
                    json={
                        "success": not (
                            self.fail_setting and path.endswith(self.fail_setting)
                        )
                    },
                )
            if path.endswith("/groups"):
                if self.fail_groups:
                    raise httpx.ReadTimeout("Groups unavailable")
                return httpx.Response(
                    200, json=copy.deepcopy(self.groups) if own else []
                )
            if path.endswith("/channels"):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "321@newsletter",
                            "name": "Tech channel",
                            "role": "OWNER",
                        },
                        {"id": "999@newsletter", "role": "SUBSCRIBER"},
                    ],
                )
            if path.endswith("/channels/321%40newsletter"):
                return httpx.Response(
                    200,
                    json={
                        "id": "321@newsletter",
                        "name": "Tech channel",
                        "role": "OWNER",
                        "subscribersCount": 5000,
                    },
                )
            if path.endswith("/picture"):
                return httpx.Response(
                    200, json={"url": "https://mmg.whatsapp.net/original.jpg"}
                )
            if path.endswith("/messages-admin-only"):
                return httpx.Response(200, json={"adminsOnly": True})
            if path.endswith("/me"):
                return httpx.Response(200, json={"id": "1@c.us"})
            if "/groups/" in path:
                group = next(
                    (
                        group
                        for group in self.groups
                        if (
                            group["id"].get("_serialized")
                            if isinstance(group["id"], dict)
                            else group["id"]
                        ).replace("@", "%40")
                        in path
                    ),
                    None,
                )
                return httpx.Response(200, json=copy.deepcopy(group or {}))
            return httpx.Response(200, json={"status": "WORKING"})

        self.request_patch = patch.object(WahaClient, "request", request)
        self.request_patch.start()
        self.env_patch = patch.dict(
            "os.environ",
            {"WAHA_BASE_URL": "http://waha", "WAHA_API_KEY": "private-operator-key"},
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
        return headers, self.client.get("/users/me", headers=headers).json()["id"]

    def create(self, **changes):
        body = {
            "name": "My tech group #5",
            "source_id": "123@g.us",
            "request_id": str(uuid4()),
            **changes,
        }
        return self.client.post(f"{PREFIX}/groups", headers=self.headers, json=body)

    def test_capacity_unknown_counts_and_private_fields(self):
        response = self.client.get(f"{PREFIX}/groups", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        full, unknown = response.json()
        self.assertEqual(full["member_count"], 1024)
        self.assertTrue(full["is_full"])
        self.assertTrue(full["can_manage"])
        self.assertFalse(full["capacity_reported"])
        self.assertIsNone(unknown["member_count"])
        self.assertIsNone(unknown["is_full"])
        self.assertNotIn("participants", response.text)
        self.assertNotIn("1@c.us", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_details_suggest_next_unused_name_and_respect_provider_capacity(self):
        self.source["groupMetadata"]["maxParticipants"] = 2048
        response = self.client.get(f"{PREFIX}/groups/123@g.us", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["suggested_name"], "My tech group #5")
        self.assertEqual(data["description"], "Original description")
        self.assertEqual(data["capacity"], 2048)
        self.assertFalse(data["is_full"])
        self.assertTrue(data["admins_only"])

    def test_successor_copies_description_photo_categories_not_members(self):
        self.session.add(
            DestinationChannel(
                user_id=self.user_id,
                chat_id="123@g.us",
                platform="whatsapp",
                chat_type="group",
                categories=["tech"],
                enabled=True,
            )
        )
        self.session.commit()
        request_id = str(uuid4())
        response = self.create(request_id=request_id)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertTrue(response.json()["enabled"])
        self.assertEqual(response.json()["categories"], ["tech"])
        self.assertEqual(response.json()["warnings"], [])
        writes = [
            (method, path, body)
            for _, method, path, body in self.seen
            if method in ("POST", "PUT")
        ]
        self.assertEqual(writes[0][2], {"name": "My tech group #5", "participants": []})
        self.assertTrue(writes[1][1].endswith("/messages-admin-only"))
        self.assertEqual(writes[1][2], {"adminsOnly": True})
        self.assertEqual(writes[3][2], {"description": "Original description"})
        self.assertEqual(
            writes[4][2], {"file": {"url": "https://mmg.whatsapp.net/original.jpg"}}
        )
        repeated = self.create(request_id=request_id)
        self.assertEqual(repeated.json(), response.json())
        self.assertEqual(sum(method == "POST" for _, method, _, _ in self.seen), 1)

    def test_uploaded_photo_overrides_source_and_empty_categories_stay_empty(self):
        photo = (
            "data:image/png;base64,"
            + base64.b64encode(b"\x89PNG\r\n\x1a\nphoto").decode()
        )
        response = self.create(photo=photo, categories=[])
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["categories"], [])
        photo_writes = [
            body
            for _, method, path, body in self.seen
            if method == "PUT" and path.endswith("/picture")
        ]
        self.assertEqual(photo_writes[0]["file"]["data"], photo.split(",")[1])
        self.assertFalse(
            any(
                method == "GET" and path.endswith("/picture")
                for _, method, path, _ in self.seen
            )
        )

    def test_partial_creation_retains_disabled_destination_and_reports_failure(self):
        self.fail_setting = "messages-admin-only"
        response = self.create()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertFalse(response.json()["enabled"])
        self.assertIn("permissão de mensagens", response.json()["warnings"][0])
        destination = (
            self.session.query(DestinationChannel).filter_by(chat_id="789@g.us").one()
        )
        self.assertFalse(destination.enabled)
        self.assertIsNotNone(self.session.query(WhatsAppGroupCreation).one().result)

    def test_unknown_creation_outcome_does_not_repeat_external_side_effect(self):
        self.timeout_create = True
        request_id = str(uuid4())
        self.assertEqual(self.create(request_id=request_id).status_code, 400)
        self.assertEqual(self.create(request_id=request_id).status_code, 409)
        self.assertEqual(sum(method == "POST" for _, method, _, _ in self.seen), 1)

    def test_nonadmin_and_other_tenant_cannot_clone_or_edit(self):
        other_headers, _ = self.login("other@example.com")
        body = {"name": "Copy", "source_id": "123@g.us", "request_id": str(uuid4())}
        response = self.client.post(
            f"{PREFIX}/groups", headers=other_headers, json=body
        )
        self.assertEqual(response.status_code, 400)
        self.source["groupMetadata"]["participants"][0]["role"] = "participant"
        self.assertEqual(self.create().status_code, 400)
        response = self.client.put(
            f"{PREFIX}/groups/123@g.us", headers=self.headers, json={"name": "Edit"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            any(method in ("POST", "PUT") for _, method, _, _ in self.seen)
        )

    def test_channels_remain_available_when_groups_fail_and_have_no_group_capacity(
        self,
    ):
        self.fail_groups = True
        self.assertEqual(
            self.client.get(f"{PREFIX}/groups", headers=self.headers).status_code, 400
        )
        response = self.client.get(f"{PREFIX}/channels", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()], ["321@newsletter"])
        response = self.client.get(
            f"{PREFIX}/channels/321@newsletter", headers=self.headers
        )
        self.assertEqual(response.json()["member_count"], 5000)
        self.assertIsNone(response.json()["capacity"])
        self.assertIsNone(response.json()["is_full"])

    def test_routing_saves_existing_rules_and_allows_pausing_offline(self):
        destination = DestinationChannel(
            user_id=self.user_id,
            chat_id="123@g.us",
            platform="whatsapp",
            chat_type="group",
            categories=["home"],
            enabled=True,
        )
        self.session.add(destination)
        self.session.commit()
        self.fail_groups = True
        response = self.client.put(
            f"{PREFIX}/groups/123@g.us/routing",
            headers=self.headers,
            json={"categories": [], "enabled": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.session.refresh(destination)
        self.assertEqual(destination.categories, [])
        self.assertFalse(destination.enabled)
        self.assertFalse(self.seen)

    def test_admin_can_edit_group_and_keep_current_photo(self):
        response = self.client.put(
            f"{PREFIX}/groups/123@g.us",
            headers=self.headers,
            json={
                "name": "Updated tech",
                "description": "Updated description",
                "categories": ["tech", "coupon"],
                "enabled": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        stored = (
            self.session.query(DestinationChannel)
            .filter_by(user_id=self.user_id, chat_id="123@g.us")
            .one()
        )
        self.assertEqual(stored.title, "Updated tech")
        self.assertEqual(stored.categories, ["tech", "coupon"])
        self.assertFalse(stored.enabled)
        self.assertFalse(any(path.endswith("/picture") for _, _, path, _ in self.seen))

    def test_channel_routing_uses_same_destination_table_and_blocks_subscribers(self):
        response = self.client.put(
            f"{PREFIX}/channels/321@newsletter/routing",
            headers=self.headers,
            json={"categories": ["tech"], "enabled": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        stored = (
            self.session.query(DestinationChannel)
            .filter_by(user_id=self.user_id, chat_id="321@newsletter")
            .one()
        )
        self.assertEqual(stored.categories, ["tech"])
        self.assertEqual(stored.platform, "whatsapp")
        self.assertEqual(stored.chat_type, "channel")
        self.assertTrue(stored.enabled)
        response = self.client.put(
            f"{PREFIX}/channels/999@newsletter/routing",
            headers=self.headers,
            json={"categories": None, "enabled": True},
        )
        self.assertEqual(response.status_code, 400)
        invalid = self.client.put(
            f"{PREFIX}/channels/123@g.us/routing",
            headers=self.headers,
            json={"enabled": False},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_new_group_without_template_uses_defaults(self):
        response = self.create(source_id=None, name="Fresh group")
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIsNone(response.json()["categories"])
        self.assertTrue(response.json()["enabled"])
        settings = [
            body
            for _, method, path, body in self.seen
            if method == "PUT" and path.endswith("messages-admin-only")
        ]
        self.assertEqual(settings, [{"adminsOnly": True}])
        self.assertFalse(any(path.endswith("/picture") for _, _, path, _ in self.seen))

    def test_authentication_and_image_validation(self):
        self.assertEqual(self.client.get(f"{PREFIX}/groups").status_code, 401)
        for photo in (
            "https://attacker/image.jpg",
            "data:image/png;base64,not-base64",
            "data:image/png;base64," + base64.b64encode(b"not PNG").decode(),
        ):
            response = self.create(photo=photo)
            self.assertEqual(response.status_code, 422)
        self.assertFalse(self.seen)


class WhatsAppManagementNormalizationTests(unittest.TestCase):
    def test_numbering_and_long_names(self):
        self.assertEqual(
            next_group_name("My tech group #2", ["my TECH group #7", "Unrelated #40"]),
            "My tech group #8",
        )
        self.assertEqual(next_group_name("Tech", []), "Tech #2")
        self.assertLessEqual(len(next_group_name("x" * 100, [])), 100)

    def test_device_jids_and_lid_phone_mapping(self):
        self.assertTrue(
            is_admin(
                [{"id": "123@lid", "pn": "551199999@s.whatsapp.net", "role": "admin"}],
                {"id": "551199999:3@c.us"},
            )
        )
        self.assertFalse(
            is_admin([{"id": "123@lid", "role": "participant"}], {"lid": "123@lid"})
        )
        self.assertTrue(
            is_admin(
                [{"id": "551199999@s.whatsapp.net", "admin": "superadmin"}],
                {"id": "551199999@c.us"},
            )
        )
        self.assertIsNone(member_count({}))
        self.assertEqual(
            member_count({"participants": [{"role": "participant"}, {"role": "left"}]}),
            1,
        )


class WhatsAppManagementMigrationTests(unittest.TestCase):
    def test_receipts_are_tenant_scoped_and_migration_is_reversible(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        migration = importlib.import_module(
            "backend.alembic.versions.0015_whatsapp_group_management"
        )
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO users (id) VALUES (1), (2)")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                connection.execute(
                    sa.text(
                        "INSERT INTO whatsapp_group_creations (request_id, user_id) VALUES (:key, 1), (:key, 2)"
                    ),
                    {"key": str(uuid4())},
                )
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT COUNT(*) FROM whatsapp_group_creations"
                    ).scalar(),
                    2,
                )
                migration.downgrade()
            self.assertNotIn(
                "whatsapp_group_creations", sa.inspect(connection).get_table_names()
            )
