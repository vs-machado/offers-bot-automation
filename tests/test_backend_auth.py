import unittest
from datetime import timedelta

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.main import app
from backend.app.models.user import DestinationChannel, Offer, User, UserConfig
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class BackendAuthTest(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.db = SQLiteAsyncSession(self.session)

        async def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def login(self, email="user@example.com", **kwargs):
        identity, login = create_identity(self.session, email, **kwargs)
        return identity, login, {"Authorization": f"Bearer {login.token}"}

    def test_current_user_response_never_returns_credentials(self):
        _, login, headers = self.login()
        response = self.client.get("/users/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        for field in ("password", "hashed_password", "token", "sessionToken"):
            self.assertNotIn(field, response.json())
        self.assertNotIn(login.token, response.text)

    def test_legacy_auth_endpoints_are_not_available(self):
        for path in ("/auth/register", "/auth/login", "/auth/session/exchange"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={}).status_code, 404)

    def test_expired_session_rejected(self):
        _, _, headers = self.login(expires_in=timedelta(minutes=-1))
        self.assertEqual(
            self.client.get("/users/me/configs", headers=headers).status_code, 401
        )
        self.assertEqual(self.session.query(User).count(), 0)

    def test_invalid_session_rejected(self):
        for token in ("short", "unknown-session-token", "x" * 257):
            with self.subTest(token_length=len(token)):
                response = self.client.get(
                    "/users/me/configs", headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_protected_route_requires_and_accepts_valid_session(self):
        self.assertEqual(self.client.get("/users/me/configs").status_code, 401)
        _, _, headers = self.login()
        response = self.client.get("/users/me/configs", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_current_user_ignores_payload_identity_and_role(self):
        self.assertEqual(self.client.get("/users/me").status_code, 401)
        _, _, headers = self.login(name="Current User")
        self.login("other@example.com", name="Other User")
        response = self.client.request(
            "GET",
            "/users/me?email=other@example.com&role=admin",
            headers=headers,
            json={"email": "other@example.com", "role": "admin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        self.assertEqual(response.json()["full_name"], "Current User")
        self.assertEqual(response.json()["role"], "user")

    def test_session_identity_creates_one_application_user(self):
        identity, _, headers = self.login()
        first = self.client.get("/users/me", headers=headers)
        second = self.client.get("/users/me", headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json()["id"], first.json()["id"])
        user = self.session.query(User).one()
        self.assertEqual(user.auth_user_id, identity.id)
        self.assertEqual(user.auth_provider, "better_auth")
        self.assertIsNone(user.hashed_password)
        self.assertEqual(user.role, "user")

    def test_revoked_session_is_rejected_immediately(self):
        _, login, headers = self.login()
        self.assertEqual(self.client.get("/users/me", headers=headers).status_code, 200)
        self.session.delete(login)
        self.session.commit()
        self.assertEqual(self.client.get("/users/me", headers=headers).status_code, 401)

    def test_linked_user_is_selected_by_identity_not_email(self):
        identity, _, headers = self.login()
        linked = User(
            auth_user_id=identity.id, email="original@example.com", role="user"
        )
        other = User(email=identity.email, role="admin")
        self.session.add_all([linked, other])
        self.session.commit()
        response = self.client.get("/users/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], linked.id)
        self.assertEqual(response.json()["role"], "user")

    def test_user_cannot_access_another_users_resources(self):
        _, _, headers = self.login()
        _, _, other_headers = self.login("other@example.com")
        self.client.get("/users/me", headers=headers)
        other_id = self.client.get("/users/me", headers=other_headers).json()["id"]
        self.session.add_all(
            [
                UserConfig(user_id=other_id, config_type="amazon", config_data="{}"),
                DestinationChannel(
                    user_id=other_id,
                    chat_id="-1001",
                    title="Other",
                    chat_type="channel",
                    enabled=True,
                ),
                Offer(
                    user_id=other_id,
                    platform="amazon",
                    product_url="https://example.com/product",
                    title="Other offer",
                    price="10",
                    currency="BRL",
                    affiliate_url="https://example.com/affiliate",
                ),
            ]
        )
        self.session.commit()
        for path in ("configs", "destinations", "offers"):
            with self.subTest(path=path):
                response = self.client.get(f"/users/me/{path}", headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), [])


if __name__ == "__main__":
    unittest.main()
