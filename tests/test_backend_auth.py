import os
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from backend.app.api.v1.endpoints import auth as auth_endpoint
from backend.app.core.db.session import get_db
from backend.app.core.security import ALGORITHM, SECRET_KEY, create_access_token
from backend.app.main import app
from backend.app.models.user import DestinationChannel, Offer, User, UserConfig
from jose import jwt


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value


class FakeAsyncSession:
    def __init__(self):
        self.users_by_email = {}
        self.configs = []
        self.destinations = []
        self.offers = []
        self.next_id = 1

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is User:
            params = statement.compile().params
            email = params.get("email_1")
            return FakeResult(self.users_by_email.get(email))
        if entity is UserConfig:
            params = statement.compile().params
            user_id = params.get("user_id_1")
            return FakeResult(
                [config for config in self.configs if config.user_id == user_id]
            )
        if entity is DestinationChannel:
            params = statement.compile().params
            user_id = params.get("user_id_1")
            return FakeResult(
                [item for item in self.destinations if item.user_id == user_id]
            )
        if entity is Offer:
            params = statement.compile().params
            user_id = params.get("user_id_1")
            return FakeResult([item for item in self.offers if item.user_id == user_id])
        return FakeResult(None)

    def add(self, item):
        if isinstance(item, User):
            item.id = self.next_id
            self.next_id += 1
            item.created_at = datetime.now(timezone.utc)
            self.users_by_email[item.email] = item
        elif isinstance(item, UserConfig):
            self.configs.append(item)
        elif isinstance(item, DestinationChannel):
            self.destinations.append(item)
        elif isinstance(item, Offer):
            self.offers.append(item)

    async def commit(self):
        return None

    async def refresh(self, item):
        return None


class BackendAuthTest(unittest.TestCase):
    def setUp(self):
        auth_endpoint._rate_limit_buckets.clear()
        self.db = FakeAsyncSession()

        async def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_registration_response_never_returns_password(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "full_name": "User Example",
                "password": "Validpass1",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "user@example.com")
        self.assertNotIn("password", data)

    def test_failed_login_rejects_bad_password(self):
        self.client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "Validpass1"},
        )

        response = self.client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)

    def test_expired_jwt_rejected(self):
        user = User(
            email="user@example.com",
            hashed_password="hash",
            full_name=None,
            auth_provider="credentials",
        )
        self.db.add(user)
        expired_token = jwt.encode(
            {
                "sub": user.email,
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            SECRET_KEY,
            algorithm=ALGORITHM,
        )

        response = self.client.get(
            "/users/me/configs", headers={"Authorization": f"Bearer {expired_token}"}
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_jwt_rejected(self):
        response = self.client.get(
            "/users/me/configs", headers={"Authorization": "Bearer invalid-token"}
        )

        self.assertEqual(response.status_code, 401)

    def test_protected_route_requires_and_accepts_valid_token(self):
        missing_response = self.client.get("/users/me/configs")
        self.assertEqual(missing_response.status_code, 401)

        user = User(
            email="user@example.com",
            hashed_password="hash",
            full_name=None,
            auth_provider="credentials",
        )
        self.db.add(user)
        token = create_access_token({"sub": user.email, "user_id": user.id})

        valid_response = self.client.get(
            "/users/me/configs", headers={"Authorization": f"Bearer {token}"}
        )

        self.assertEqual(valid_response.status_code, 200)
        self.assertEqual(valid_response.json(), [])

    def test_current_user_requires_token_and_ignores_payload_identity(self):
        missing_response = self.client.get("/users/me")
        self.assertEqual(missing_response.status_code, 401)

        user = User(
            email="user@example.com",
            hashed_password="hash",
            full_name="Current User",
            auth_provider="credentials",
        )
        other_user = User(
            email="other@example.com",
            hashed_password="hash",
            full_name="Other User",
            auth_provider="credentials",
        )
        self.db.add(user)
        self.db.add(other_user)
        token = create_access_token({"sub": user.email, "user_id": user.id})

        response = self.client.request(
            "GET",
            "/users/me?email=other@example.com",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": other_user.email},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], user.email)
        self.assertEqual(data["full_name"], user.full_name)

    def test_google_session_exchange_creates_and_links_backend_user(self):
        os.environ["NEXTAUTH_BACKEND_SECRET"] = "exchange-secret"

        response = self.client.post(
            "/auth/session/exchange",
            json={
                "email": "google@example.com",
                "provider": "google",
                "provider_account_id": "google-account-1",
                "full_name": "Google User",
                "secret": "exchange-secret",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        user = self.db.users_by_email["google@example.com"]
        self.assertIsNone(user.hashed_password)
        self.assertEqual(user.auth_provider, "google")
        self.assertEqual(user.provider_account_id, "google-account-1")

        second_response = self.client.post(
            "/auth/session/exchange",
            json={
                "email": "google@example.com",
                "provider": "google",
                "provider_account_id": "google-account-2",
                "full_name": "Google User",
                "secret": "exchange-secret",
            },
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(len(self.db.users_by_email), 1)
        self.assertEqual(user.provider_account_id, "google-account-2")

    def test_user_cannot_access_another_users_resources(self):
        user = User(
            email="user@example.com",
            hashed_password="hash",
            full_name=None,
            auth_provider="credentials",
        )
        other_user = User(
            email="other@example.com",
            hashed_password="hash",
            full_name=None,
            auth_provider="credentials",
        )
        self.db.add(user)
        self.db.add(other_user)
        self.db.add(
            UserConfig(
                id=1, user_id=other_user.id, config_type="amazon", config_data="{}"
            )
        )
        self.db.add(
            DestinationChannel(
                id=1,
                user_id=other_user.id,
                chat_id="-1001",
                title="Other",
                chat_type="channel",
                enabled=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        self.db.add(
            Offer(
                id=1,
                user_id=other_user.id,
                platform="amazon",
                product_url="https://example.com/product",
                title="Other offer",
                price="10",
                currency="BRL",
                affiliate_url="https://example.com/affiliate",
                created_at=datetime.now(timezone.utc),
            )
        )
        token = create_access_token({"sub": user.email, "user_id": user.id})
        headers = {"Authorization": f"Bearer {token}"}

        configs_response = self.client.get("/users/me/configs", headers=headers)
        destinations_response = self.client.get(
            "/users/me/destinations", headers=headers
        )
        offers_response = self.client.get("/users/me/offers", headers=headers)

        self.assertEqual(configs_response.status_code, 200)
        self.assertEqual(destinations_response.status_code, 200)
        self.assertEqual(offers_response.status_code, 200)
        self.assertEqual(configs_response.json(), [])
        self.assertEqual(destinations_response.json(), [])
        self.assertEqual(offers_response.json(), [])


if __name__ == "__main__":
    unittest.main()
