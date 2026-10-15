import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints import users
from backend.app.core import affiliate_validation as validation
from backend.app.schemas.affiliate_validation import CredentialValidationRequest
from backend.app.schemas.user import UserConfigCreate


class CredentialValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_amazon_tag_only_is_local_even_when_probes_are_busy(self):
        request = CredentialValidationRequest(
            provider="amazon", config_data={"amazon_affiliate_tag": " Minha-Loja-20 "}
        )
        with (
            patch.object(validation.httpx, "AsyncClient") as client,
            patch.object(validation, "probe", new_callable=AsyncMock) as probe,
            patch.object(validation, "_active_users", {7}),
        ):
            result = await validation.validate_credentials(request, 7)
        client.assert_not_called()
        probe.assert_not_awaited()
        self.assertEqual(result.status, "valid")
        self.assertEqual(result.reason, "locally_valid")
        self.assertIn("válida localmente", result.message)
        self.assertIn("não autentica", result.message)
        self.assertIn("titularidade", result.message)
        self.assertIsNotNone(result.checked_at.tzinfo)
        self.assertNotIn("Minha-Loja-20", result.model_dump_json())

    async def test_amazon_ignores_obsolete_cookie_and_marketplace(self):
        request = CredentialValidationRequest(
            provider="amazon",
            config_data={
                "amazon_affiliate_tag": "loja-20",
                "amazon_cookie_header": "obsolete\r\nsecret",
                "amazon_marketplace_id": "not-a-marketplace",
            },
        )
        with patch.object(validation.httpx, "AsyncClient") as client:
            result = await validation.validate_credentials(request, 7)
        self.assertEqual(result.status, "valid")
        client.assert_not_called()

    async def test_amazon_missing_and_invalid_tags_do_not_use_network(self):
        for tag, reason in (
            (None, "missing_fields"),
            ("", "missing_fields"),
            ("   ", "missing_fields"),
            ("loja", "invalid_amazon_tag"),
            ("loja-2", "invalid_amazon_tag"),
            ("loja-200", "invalid_amazon_tag"),
            ("loja 20", "invalid_amazon_tag"),
            ("loja_20", "invalid_amazon_tag"),
            ("lojá-20", "invalid_amazon_tag"),
            ("https://amazon.com.br/?tag=loja-20", "invalid_amazon_tag"),
            ("loja-20&other=value", "invalid_amazon_tag"),
            ("loja\n-20", "invalid_amazon_tag"),
            ("x" * 98 + "-20", "invalid_amazon_tag"),
        ):
            with self.subTest(tag=tag):
                request = CredentialValidationRequest(
                    provider="amazon",
                    config_data={} if tag is None else {"amazon_affiliate_tag": tag},
                )
                with patch.object(validation.httpx, "AsyncClient") as client:
                    result = await validation.validate_credentials(request, 7)
                self.assertEqual(result.status, "invalid")
                self.assertEqual(result.reason, reason)
                client.assert_not_called()

    async def test_other_providers_keep_operational_probes(self):
        for provider, values in (
            (
                "mercado_livre",
                {
                    "ml_affiliate_tag": "loja",
                    "ml_cookie_header": "session=test",
                    "ml_csrf_token": "csrf",
                },
            ),
            ("shopee", {"shopee_app_id": "123", "shopee_app_secret": "secret"}),
            (
                "aliexpress",
                {"aliexpress_app_key": "key", "aliexpress_app_secret": "secret"},
            ),
        ):
            with self.subTest(provider=provider):
                request = CredentialValidationRequest(
                    provider=provider, config_data=values
                )
                with patch.object(validation, "probe", new_callable=AsyncMock) as probe:
                    result = await validation.validate_credentials(request, 7)
                self.assertEqual(result.status, "valid")
                self.assertEqual(result.reason, "validated")
                probe.assert_awaited_once()


class AmazonConfigValidationTests(unittest.TestCase):
    def test_save_accepts_only_tag_and_normalizes_whitespace(self):
        for tag in ("loja-20", "Minha-Loja-21", "x" * 97 + "-20"):
            with self.subTest(tag=tag):
                config = UserConfigCreate(
                    config_type="amazon",
                    config_data={"amazon_affiliate_tag": f" {tag} "},
                )
                users._validate_config(config)
                self.assertEqual(config.config_data, {"amazon_affiliate_tag": tag})

    def test_save_rejects_missing_invalid_and_non_string_tags(self):
        for tag in (None, "", "   ", "loja", "loja-20&x=y", 123, [], {}):
            with self.subTest(tag=tag):
                config = UserConfigCreate(
                    config_type="amazon", config_data={"amazon_affiliate_tag": tag}
                )
                with self.assertRaises(HTTPException) as caught:
                    users._validate_config(config)
                self.assertEqual(caught.exception.status_code, 400)

    def test_amazon_endpoints_validate_create_and_update_tag_only(self):
        app = FastAPI()
        app.include_router(users.router)
        user = SimpleNamespace(id=7)
        config = SimpleNamespace(
            id=12, user_id=7, config_type="amazon", config_data="{}"
        )
        db = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.execute.return_value = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = config
        app.dependency_overrides[users.get_current_user] = lambda: user
        app.dependency_overrides[users.get_db] = lambda: db

        async def refresh(record):
            record.id = 12

        db.refresh.side_effect = refresh
        payload = {
            "config_type": "amazon",
            "config_data": {"amazon_affiliate_tag": "loja-20"},
        }
        with TestClient(app) as client:
            with patch.object(validation, "probe", new_callable=AsyncMock) as probe:
                response = client.post(
                    "/me/affiliate-credentials/validate",
                    json={"provider": "amazon", "config_data": payload["config_data"]},
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["reason"], "locally_valid")
            probe.assert_not_awaited()
            db.commit.assert_not_awaited()
            response = client.post(
                "/me/affiliate-credentials/validate",
                json={
                    "provider": "amazon",
                    "config_data": {"amazon_affiliate_tag": "not-a-tag"},
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "invalid")
            db.commit.assert_not_awaited()
            response = client.post("/me/configs", json=payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["config_data"], payload["config_data"])
            response = client.put("/me/configs/12", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["config_data"], payload["config_data"])
            self.assertEqual(db.commit.await_count, 2)
            for method, path in (
                (client.post, "/me/configs"),
                (client.put, "/me/configs/12"),
            ):
                response = method(
                    path,
                    json={"config_type": "amazon", "config_data": {}},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json()["detail"]["missing_keys"], ["amazon_affiliate_tag"]
                )
            self.assertEqual(db.commit.await_count, 2)


if __name__ == "__main__":
    unittest.main()
