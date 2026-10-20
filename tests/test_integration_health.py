import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints import users
from backend.app.core import integration_health as health
from backend.worker.poster import BotPosterError


class IntegrationHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_whatsapp_only_alerts_for_existing_integration(self):
        for state, saved, expected in (
            ({"status": "WORKING"}, False, "connected"),
            ({"status": "STOPPED"}, False, "not_configured"),
            ({"status": "STOPPED"}, True, "disconnected"),
            ({"status": "STOPPED", "session_exists": True}, False, "disconnected"),
            ({"status": "SCAN_QR_CODE", "session_exists": True}, False, "disconnected"),
            ({"status": "FAILED", "session_exists": True}, True, "disconnected"),
            ({"status": "UNCONFIGURED"}, True, "unknown"),
        ):
            with self.subTest(state=state, saved=saved):
                with patch.object(health, "WahaClient") as client:
                    client.return_value.status = AsyncMock(return_value=state)
                    result = await health.whatsapp_health(7, saved)
                self.assertEqual(result, expected)
                client.assert_called_once_with(7)

    async def test_whatsapp_outage_is_not_disconnection(self):
        with patch.object(health, "WahaClient") as client:
            client.return_value.status = AsyncMock(
                side_effect=BotPosterError("offline")
            )
            self.assertEqual(await health.whatsapp_health(7, True), "unknown")

    async def test_cookie_rejection_is_distinct_from_transient_errors(self):
        values = {
            "ml_affiliate_tag": "tag",
            "ml_cookie_header": "session=secret",
            "ml_csrf_token": "secret-csrf",
        }
        cases = (
            (
                httpx.Response(
                    302,
                    headers={
                        "location": "https://www.mercadolivre.com/jms/mlb/lgz/login"
                    },
                ),
                "expired",
            ),
            (httpx.Response(401), "expired"),
            (httpx.Response(403, json={"error": "session expired"}), "expired"),
            (httpx.Response(403, text="captcha"), "unknown"),
            (httpx.Response(429), "unknown"),
            (httpx.Response(503), "unknown"),
            (httpx.Response(302, headers={"location": "/challenge"}), "unknown"),
            (
                httpx.Response(
                    200,
                    text='<input type="password">',
                    headers={"content-type": "text/html"},
                ),
                "expired",
            ),
            (
                httpx.Response(
                    200, text="captcha", headers={"content-type": "text/html"}
                ),
                "unknown",
            ),
            (
                httpx.Response(
                    200, text="Affiliate hub", headers={"content-type": "text/html"}
                ),
                "connected",
            ),
        )
        for response, expected in cases:
            with self.subTest(status=response.status_code, expected=expected):
                with patch.object(health.httpx, "AsyncClient") as factory:
                    client = AsyncMock()
                    factory.return_value.__aenter__.return_value = client
                    client.get.return_value = response
                    self.assertEqual(
                        await health.mercado_livre_health(values), expected
                    )
                    client.get.assert_awaited_once()

    async def test_missing_credentials_do_not_probe_provider(self):
        with patch.object(health.httpx, "AsyncClient") as factory:
            self.assertEqual(await health.mercado_livre_health(None), "not_configured")
            self.assertEqual(await health.mercado_livre_health({}), "incomplete")
        factory.assert_not_called()

    async def test_provider_timeout_is_inconclusive(self):
        with patch.object(health.httpx, "AsyncClient") as factory:
            client = AsyncMock()
            factory.return_value.__aenter__.return_value = client
            client.get.side_effect = httpx.ReadTimeout("offline")
            self.assertEqual(
                await health.mercado_livre_health(
                    {
                        "ml_affiliate_tag": "tag",
                        "ml_cookie_header": "session=secret",
                        "ml_csrf_token": "csrf",
                    }
                ),
                "unknown",
            )


class IntegrationHealthEndpointTests(unittest.TestCase):
    def test_requires_authentication(self):
        app = FastAPI()
        app.include_router(users.router, prefix="/users")
        with TestClient(app) as client:
            self.assertEqual(
                client.get("/users/me/integration-health").status_code, 401
            )

    def test_owner_scoped_checks_return_no_credentials_and_disable_caching(self):
        app = FastAPI()
        app.include_router(users.router, prefix="/users")
        db = AsyncMock()
        config_result = MagicMock()
        config_result.scalars.return_value.first.return_value = SimpleNamespace(
            config_data="encrypted"
        )
        destination_result = MagicMock()
        destination_result.scalar_one_or_none.return_value = 12
        db.execute.side_effect = [config_result, destination_result]
        app.dependency_overrides[users.get_current_user] = lambda: SimpleNamespace(id=7)
        app.dependency_overrides[users.get_db] = lambda: db
        with (
            patch.object(
                users, "decrypt_config", return_value={"ml_cookie_header": "secret"}
            ) as decrypt,
            patch.object(
                users, "whatsapp_health", AsyncMock(return_value="disconnected")
            ) as whatsapp,
            patch.object(
                users, "mercado_livre_health", AsyncMock(return_value="expired")
            ),
            TestClient(app) as client,
        ):
            response = client.get("/users/me/integration-health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"whatsapp": "disconnected", "mercado_livre": "expired"}
        )
        self.assertEqual(response.headers["cache-control"], "no-store")
        decrypt.assert_called_once_with("encrypted", 7, "mercado_livre")
        whatsapp.assert_awaited_once_with(7, True)
        for call in db.execute.call_args_list:
            self.assertEqual(call.args[0].compile().params["user_id_1"], 7)
