"""Awin transport contract, KaBuM routing, and credential handling regressions."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.api.v1.endpoints import users
from backend.app.core.affiliate_validation import probe, validate_credentials
from backend.app.core.credentials import MASK, mask_config, restore_masked_secrets
from backend.app.core.delivery_errors import classify_failure
from backend.app.core.delivery_history import get_delivery_history
from backend.app.models.user import DestinationChannel
from backend.app.models.whatsapp_connection import WhatsAppConnection
from backend.app.models.worker import PromotionDelivery
from backend.app.schemas.affiliate_validation import CredentialValidationRequest
from backend.app.schemas.user import UserConfigCreate
from backend.worker.manager import UserBotInstance
from offers_bot.awin import AwinClient
from offers_bot.parser import detect_platform, extract_offers, is_kabum_url

PRODUCT = "https://www.kabum.com.br/produto/123456/notebook?utm_source=old#details"
TRACKING = "https://www.awin1.com/cread.php?awinmid=17729&awinaffid=123"
SHORT = "https://tidd.ly/example"
VALUES = {"awin_publisher_id": "123", "awin_access_token": "private-token"}


class AwinClientTests(unittest.TestCase):
    def generate(self, payload, status=200, url=PRODUCT):
        def handle(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(
                str(request.url),
                "https://api.awin.com/publishers/123/linkbuilder/generate",
            )
            self.assertEqual(request.headers["Authorization"], "Bearer private-token")
            self.assertEqual(
                json.loads(request.content),
                {
                    "advertiserId": 17729,
                    "destinationUrl": url.split("#")[0],
                    "shorten": True,
                },
            )
            return httpx.Response(status, json=payload)

        transport = httpx.Client(transport=httpx.MockTransport(handle))
        with patch("offers_bot.awin.httpx.Client", return_value=transport):
            return AwinClient("123", "private-token").create_link(url)

    def test_generate_uses_bearer_and_deduplicates_by_product_id(self):
        link = self.generate({"url": TRACKING, "shortUrl": SHORT})
        self.assertEqual(link.short_url, SHORT)
        self.assertEqual(link.long_url, TRACKING)
        self.assertEqual(link.origin_url, PRODUCT)
        self.assertEqual(link.product_key, "KABUM:123456")
        other = self.generate(
            {"url": TRACKING}, url="https://kabum.com.br/produto/123456/new-slug?x=y"
        )
        self.assertEqual(other.product_key, link.product_key)
        self.assertEqual(other.short_url, TRACKING)

    def test_errors_and_invalid_output_never_fall_back_to_original_link(self):
        for payload in (
            {"description": "Unknown error! Please try again later!"},
            {"url": "https://evil.example/link"},
            {"url": TRACKING, "shortUrl": "http://tidd.ly/insecure"},
            {"url": TRACKING, "shortUrl": "https://tidd.ly.evil.example/link"},
            [],
        ):
            with self.subTest(payload=payload), self.assertRaises(RuntimeError):
                self.generate(payload)
        for status, reason in (
            (401, "affiliate_authentication"),
            (403, "affiliate_permission"),
            (429, "affiliate_rate_limit"),
            (500, "affiliate_api"),
        ):
            with self.subTest(status=status):
                with self.assertRaises(httpx.HTTPStatusError) as caught:
                    self.generate({"error": "redacted"}, status=status)
                self.assertEqual(
                    classify_failure(caught.exception, "affiliate", "KaBuM"), reason
                )

    def test_missing_credentials_and_unsupported_urls_make_no_requests(self):
        with patch("offers_bot.awin.httpx.Client") as transport:
            for publisher in ("", "0", "../other", "１２３", "9223372036854775808"):
                self.assertFalse(AwinClient(publisher, "token").ready())
                with self.assertRaises(RuntimeError):
                    AwinClient(publisher, "token").create_link(PRODUCT)
            for url in (
                "https://kabum.com.br.evil.example/produto/123",
                "https://kabum.com.br@evil.example/produto/123",
                "https://user@kabum.com.br/produto/123",
                "https://kabum.com.br:bad/produto/123",
                "https://amazon.com.br/dp/123",
            ):
                self.assertFalse(is_kabum_url(url))
                with self.assertRaises(ValueError):
                    AwinClient("123", "token").create_link(url)
            transport.assert_not_called()

    def test_parser_recognizes_kabum_without_llm(self):
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offers = extract_offers(f"Notebook Gamer R$ 2.999,90 {PRODUCT}")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].platform, "kabum")
        self.assertEqual(offers[0].price, "R$ 2.999,90")
        self.assertEqual(detect_platform(PRODUCT), "kabum")

    def test_saved_config_validates_and_masks_token(self):
        config = UserConfigCreate(config_type="awin", config_data=VALUES)
        users._validate_config(config)
        masked = mask_config(config.config_data)
        self.assertEqual(masked["awin_access_token"], MASK)
        self.assertEqual(masked["awin_publisher_id"], "123")
        self.assertEqual(restore_masked_secrets(masked, VALUES), VALUES)
        for values in (
            {},
            {**VALUES, "awin_publisher_id": "../123"},
            {**VALUES, "awin_access_token": "a\nb"},
        ):
            with self.subTest(values=values), self.assertRaises(HTTPException):
                users._validate_config(
                    UserConfigCreate(config_type="awin", config_data=values)
                )


class AwinBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_returns_safe_outcomes_from_awin_responses(self):
        request = CredentialValidationRequest(provider="awin", config_data=VALUES)
        for status_code, payload, status, reason in (
            (200, {"url": TRACKING, "shortUrl": SHORT}, "valid", "validated"),
            (401, {"error": "private-token"}, "invalid", "authentication"),
            (429, {}, "inconclusive", "rate_limit"),
            (500, {}, "inconclusive", "api_unavailable"),
            (
                200,
                {"description": "Unknown error! Please try again later!"},
                "inconclusive",
                "link_not_generated",
            ),
        ):
            with self.subTest(status_code=status_code, reason=reason):
                client = httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda _: httpx.Response(status_code, json=payload)
                    )
                )
                with patch(
                    "backend.app.core.affiliate_validation.httpx.AsyncClient",
                    return_value=client,
                ):
                    result = await validate_credentials(request, 7)
                self.assertEqual(result.status, status)
                self.assertEqual(result.reason, reason)
                self.assertNotIn("private-token", result.model_dump_json())

    async def test_probe_generates_kabum_link_without_visiting_destination(self):
        requests = []

        def handle(request):
            requests.append(request)
            self.assertEqual(request.url.host, "api.awin.com")
            self.assertEqual(request.headers["Authorization"], "Bearer private-token")
            self.assertEqual(json.loads(request.content)["advertiserId"], 17729)
            return httpx.Response(200, json={"url": TRACKING, "shortUrl": SHORT})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await probe(client, "awin", VALUES, None)
        self.assertEqual(len(requests), 1)

    async def test_validation_rejects_bad_publisher_before_network(self):
        request = CredentialValidationRequest(
            provider="awin", config_data={**VALUES, "awin_publisher_id": "../123"}
        )
        with patch("backend.app.core.affiliate_validation.httpx.AsyncClient") as client:
            result = await validate_credentials(request, 7)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.reason, "invalid_format")
        client.assert_not_called()

    async def test_awin_only_configuration_activates_worker_and_routes_kabum(self):
        bot = UserBotInstance(7, None)
        self.addCleanup(bot.close)
        with (
            patch.object(
                bot,
                "_load_configs",
                new=AsyncMock(
                    return_value={
                        **VALUES,
                        "source_chats": ["https://t.me/promotom"],
                    }
                ),
            ),
            patch.object(
                bot,
                "_load_destination_chat_ids",
                new=AsyncMock(return_value=["-100123"]),
            ),
        ):
            await bot.configure(None, ["https://t.me/promotom"])
        self.assertTrue(bot.active)
        self.assertIsInstance(bot._affiliate_client_for_platform("kabum"), AwinClient)
        self.assertTrue(bot._affiliate_client_for_platform("kabum").ready())

    async def test_kabum_filter_selects_worker_label_and_excludes_other_stores(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        WhatsAppConnection.__table__.create(engine)
        PromotionDelivery.__table__.create(engine)
        DestinationChannel.__table__.create(engine)
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            for identity, platform, user_id in (
                ("kabum", "KaBuM", 7),
                ("amazon", "Amazon", 7),
                ("foreign", "KaBuM", 8),
            ):
                session.add(
                    PromotionDelivery(
                        id=identity,
                        user_id=user_id,
                        dedup_key=identity,
                        title="Notebook",
                        platform=platform,
                        chat_id="-100123",
                        status="sent",
                        stage="posting",
                        attempts=1,
                        expires_at=now + timedelta(hours=1),
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.commit()
            db = AsyncMock()
            db.execute.side_effect = session.execute
            db.scalar.side_effect = session.scalar
            result = await get_delivery_history(db, 7, 1, 20, None, True, "kabum")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["counts"], {"sent": 1})
        self.assertEqual([row["id"] for row in result["items"]], ["kabum"])
