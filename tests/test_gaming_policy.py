"""Editorial sampling, authenticated ownership, and queued-offer revalidation."""

from datetime import datetime, timezone
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from pydantic import ValidationError
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.db.base import Base
from backend.app.core.db.session import get_db
from backend.app.core.gaming_policy import GamingPolicy, accepts_gaming, is_gaming_offer
from backend.app.main import app
from backend.app.models import load_models
from backend.app.models.user import DestinationChannel
from backend.worker.posting_queue import QueuePoster, post_promotion
from offers_bot.message_context import promotion_context
from tests.auth_fixtures import SQLiteAsyncSession, create_identity


class GamingSamplingTests(unittest.TestCase):
    def test_title_and_semantics_do_not_treat_all_tech_as_gaming(self):
        for title in (
            "Monitor Gamer LG",
            "Placa de Vídeo RTX 5060",
            "Console PlayStation 5",
            "Mouse Redragon",
        ):
            self.assertTrue(is_gaming_offer(title), title)
        for title in (
            "Notebook Asus Vivobook 8GB 256GB",
            "Memória RAM DDR4 8GB",
            "Smart TV Samsung",
            "Asmodee Homem Batata",
            "Teclado Logitech Pebble",
        ):
            self.assertFalse(is_gaming_offer(title), title)
        self.assertTrue(is_gaming_offer("Produto especializado", {"is_gaming": True}))

    def test_default_override_extremes_and_stable_sampling(self):
        policy = GamingPolicy(
            platforms={"whatsapp": 25},
            destinations={"gamer-group": 100, "blocked-group": 0},
        )
        kept = [
            i
            for i in range(10000)
            if accepts_gaming(policy, 1, "whatsapp", "general", str(i))
        ]
        self.assertTrue(2300 < len(kept) < 2700, len(kept))
        for i in range(100):
            key = str(i)
            self.assertTrue(accepts_gaming(policy, 1, "telegram", "tg", key))
            self.assertTrue(accepts_gaming(policy, 1, "whatsapp", "gamer-group", key))
            self.assertFalse(
                accepts_gaming(policy, 1, "whatsapp", "blocked-group", key)
            )
            self.assertEqual(
                accepts_gaming(policy, 1, "whatsapp", "general", key),
                accepts_gaming(policy, 1, "whatsapp", "another-general", key),
            )
        for value in (-1, 101, True, "25", 25.5):
            with self.assertRaises(ValidationError):
                GamingPolicy(platforms={"whatsapp": value})

    def test_admission_filters_before_broker_and_burst(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (
            "whatsapp",
            "channel",
            None,
            True,
            1,
        )
        token = promotion_context.set({"title": "Monitor Gamer", "is_gaming": True})
        try:
            with (
                patch("backend.worker.posting_queue.connect") as connect,
                patch(
                    "backend.worker.whatsapp_delivery.connection_scope",
                    return_value=(1, True),
                ),
                patch("backend.worker.whatsapp_delivery.lock_account"),
                patch(
                    "backend.worker.posting_queue.load_gaming_policy",
                    return_value=GamingPolicy(platforms={"whatsapp": 0}),
                ),
                patch.object(post_promotion, "apply_async") as publish,
            ):
                connect.return_value.__enter__.return_value = conn
                result = QueuePoster(1)._publish(
                    "group", "offer", None, None, time.time() + 600
                )
                self.assertEqual(
                    result, {"status": "filtered", "reason": "gaming_reduced"}
                )
                publish.assert_not_called()
        finally:
            promotion_context.reset(token)

    def test_queued_legacy_gaming_offer_rechecks_latest_policy(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [
            (
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                1,
                "Monitor Gamer",
                "key",
            ),
            ("whatsapp", None),
        ]
        with (
            patch("backend.worker.posting_queue.connect") as connect,
            patch(
                "backend.worker.posting_queue.load_gaming_policy",
                return_value=GamingPolicy(platforms={"whatsapp": 0}),
            ),
            patch("backend.worker.posting_queue.update_status") as status,
            patch("backend.worker.whatsapp_delivery.reserve_delivery") as reserve,
        ):
            connect.return_value.__enter__.return_value = conn
            post_promotion.run(
                identity="offer",
                user_id=1,
                chat_id="group",
                text="offer",
                deadline=time.time() + 600,
            )
            status.assert_called_once_with(
                "offer", "cancelled", "gaming_reduced", pending_only=True
            )
            reserve.assert_not_called()


class GamingPolicyAPITests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(
            os.environ, {"CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode()}
        )
        environment.start()
        self.addCleanup(environment.stop)
        load_models()
        self.engine = sa.create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        async def database():
            yield SQLiteAsyncSession(self.session)

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        _, login = create_identity(self.session, "gaming@example.com")
        self.headers = {"Authorization": f"Bearer {login.token}"}
        self.user_id = self.client.get("/users/me", headers=self.headers).json()["id"]
        self.session.add(
            DestinationChannel(
                user_id=self.user_id, chat_id="owned", platform="telegram", enabled=True
            )
        )
        self.session.commit()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def test_save_load_validation_and_user_isolation(self):
        endpoint = "/users/me/gaming-policy"
        self.assertEqual(
            self.client.get(endpoint, headers=self.headers).json(),
            {"platforms": {}, "destinations": {}},
        )
        body = {"platforms": {"whatsapp": 25}, "destinations": {"owned": 50}}
        response = self.client.put(endpoint, headers=self.headers, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(endpoint, headers=self.headers).json(), body)
        self.assertEqual(
            self.client.put(
                endpoint, headers=self.headers, json={"destinations": {"foreign": 0}}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                endpoint, headers=self.headers, json={"platforms": {"whatsapp": -1}}
            ).status_code,
            422,
        )
        _, other = create_identity(self.session, "other-gaming@example.com")
        self.assertEqual(
            self.client.get(
                endpoint, headers={"Authorization": f"Bearer {other.token}"}
            ).json(),
            {"platforms": {}, "destinations": {}},
        )
