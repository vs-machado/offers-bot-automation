"""Magalu request contract, short-link safety, owned settings and worker routing."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.app.api.v1.endpoints import magalu, users
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.affiliate_validation import validate_credentials
from backend.app.core.db.session import get_db
from backend.app.schemas.affiliate_validation import CredentialValidationRequest
from backend.app.schemas.user import UserConfigCreate
from backend.worker.manager import UserBotInstance
from offers_bot.magalu import (
    MAGALU_ENDPOINT,
    SAMPLE_PRODUCT_URL,
    MagaluClient,
    MagaluError,
    resolve_product_url,
)
from offers_bot.parser import detect_platform, extract_offers, extract_offers_async

VALUES = {
    "magalu_partner_id": "1234",
    "magalu_promoter_id": "5678",
    "magalu_store_name": "minhaloja",
}
IDS = {"partner_id": "1234", "promoter_id": "5678", "store_name": "minhaloja"}
SHORT = "https://magazineluiza.onelink.me/589508454/newlink"


def generated():
    return {
        "status": "success",
        **IDS,
        "affiliate_url": SHORT,
        "shortlink_url": "https://magazineluiza.onelink.me/589508454/otherlink",
        "canonical_product_url": SAMPLE_PRODUCT_URL,
        "sku": "240466500",
        "seller_id": "magazineluiza",
        "title": "Galaxy A07",
        "image_url": "https://a-static.mlcdn.com.br/product.jpg",
        "current_price": 0,
        "original_price": None,
        "installment": None,
    }


class MagaluClientTests(unittest.TestCase):
    def generate(
        self,
        payload=None,
        status=200,
        url=SAMPLE_PRODUCT_URL,
        channel="lucreator",
        content=None,
    ):
        self.requests = []

        def handle(request):
            self.requests.append(request)
            if content is not None:
                return httpx.Response(status, content=content)
            return httpx.Response(
                status, json=payload if payload is not None else generated()
            )

        transport = httpx.Client(transport=httpx.MockTransport(handle))
        with patch("offers_bot.magalu.httpx.Client", return_value=transport):
            return MagaluClient(**IDS).generate(url, channel)

    def test_request_replaces_previous_ids_preserves_seller_and_defaults_to_direct(
        self,
    ):
        data = self.generate(
            url=SAMPLE_PRODUCT_URL
            + "&partner_id=old&partner_id=other&promoter_id=old&utm_source=whatsapp#details"
        )
        self.assertEqual(data["current_price"], 0)
        request = self.requests[0]
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url).split("?")[0], MAGALU_ENDPOINT)
        self.assertEqual(dict(request.url.params), IDS)
        self.assertNotIn("origin", request.headers)
        self.assertNotIn("referer", request.headers)
        body = json.loads(request.content)
        self.assertEqual(body["utm_source"], "lucreator")
        self.assertEqual(body["utm_medium"], "link_afiliado")
        self.assertEqual(body["utm_campaign"], "divulgacao_influencer")
        for key, value in IDS.items():
            self.assertEqual(body[key], value)
        query = parse_qs(urlparse(body["url"]).query)
        self.assertEqual(query["partner_id"], ["1234"])
        self.assertEqual(query["promoter_id"], ["5678"])
        self.assertEqual(query["seller_id"], ["magazineluiza"])
        self.assertEqual(query["utm_source"], ["lucreator"])
        self.assertFalse(urlparse(body["url"]).fragment)

    def test_explicit_whatsapp_and_web_attribution_validation(self):
        self.generate(channel="whatsapp")
        body = json.loads(self.requests[0].content)
        self.assertEqual(body["utm_source"], "whatsapp")
        self.assertEqual(body["utm_medium"], "compartilhamento_social")
        web = (
            SAMPLE_PRODUCT_URL
            + "&partner_id=1234&promoter_id=5678&utm_campaign=divulgacao_influencer&utm_source=lucreator&utm_medium=link_afiliado"
        )
        self.generate({**generated(), "web_affiliate_url": web})
        with self.assertRaises(MagaluError):
            self.generate(
                {
                    **generated(),
                    "web_affiliate_url": web.replace(
                        "promoter_id=5678", "promoter_id=999"
                    ),
                }
            )

    def test_wrong_account_and_untrusted_output_never_fall_back(self):
        for changes in (
            {"status": "error"},
            {"affiliate_url": None},
            {"affiliate_url": "https://magazineluiza.onelink.me.evil.test/link"},
            {"shortlink_url": "https://user@magazineluiza.onelink.me/link"},
            {"image_url": "http://127.0.0.1/image"},
            {"canonical_product_url": "https://evil.test/product"},
            {"promoter_id": "another-account"},
        ):
            with self.subTest(changes=changes), self.assertRaises(MagaluError):
                self.generate({**generated(), **changes})
        for payload in ([], "not an object"):
            with self.assertRaises(MagaluError):
                self.generate(payload)
        with self.assertRaises(MagaluError):
            self.generate(content=b"invalid JSON")
        for code in (400, 401, 403, 429, 500):
            with self.subTest(code=code), self.assertRaises(MagaluError):
                self.generate(status=code)
            self.assertEqual(len(self.requests), 1)

    def test_timeout_is_wrapped_without_retry(self):
        transport = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    httpx.ReadTimeout("private error", request=request)
                )
            )
        )
        with patch("offers_bot.magalu.httpx.Client", return_value=transport):
            with self.assertRaises(MagaluError) as caught:
                MagaluClient(**IDS).generate(SAMPLE_PRODUCT_URL)
        self.assertNotIn("private error", str(caught.exception))

    def test_product_identity_is_stable_and_seller_specific(self):
        with patch.object(MagaluClient, "generate", return_value=generated()):
            link = MagaluClient(**IDS).create_link(SAMPLE_PRODUCT_URL)
            other = MagaluClient(**IDS).create_link(
                SAMPLE_PRODUCT_URL + "&utm_source=old"
            )
        self.assertEqual(link.product_key, "MAGALU:240466500:magazineluiza")
        self.assertEqual(link.product_key, other.product_key)
        self.assertEqual(link.short_url, SHORT)
        self.assertNotEqual(link.short_url, generated()["shortlink_url"])

    def test_invalid_input_configuration_and_channel_make_no_requests(self):
        with patch("offers_bot.magalu.httpx.Client") as client:
            for url in (
                "http://www.magazineluiza.com.br/p/123/",
                "file:///etc/passwd",
                "https://127.0.0.1/p/123/",
                "https://magazineluiza.com.br.evil.test/p/123/",
                "https://user@www.magazineluiza.com.br/p/123/",
                "https://@www.magazineluiza.com.br/p/123/",
                "https://www.magazineluiza.com.br:444/p/123/",
                "https://www.magazineluiza.com.br/",
                "https://www.magazineluiza.com.br:bad/p/123/",
            ):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    MagaluClient(**IDS).generate(url)
            with self.assertRaises(ValueError):
                MagaluClient(**IDS).generate(SAMPLE_PRODUCT_URL, "unknown")
            with self.assertRaises(ValueError):
                MagaluClient().generate(SAMPLE_PRODUCT_URL)
            client.assert_not_called()


class MagaluShortLinkTests(unittest.IsolatedAsyncioTestCase):
    def transport(self, destination):
        self.requests = []

        def handle(request):
            self.requests.append(str(request.url))
            return httpx.Response(302, headers={"location": destination})

        return httpx.Client(transport=httpx.MockTransport(handle))

    async def test_cuttly_is_opened_before_regex_and_llm_in_both_parsers(self):
        for asynchronous in (False, True):
            client = self.transport(SAMPLE_PRODUCT_URL)
            with (
                patch("offers_bot.magalu.httpx.Client", return_value=client),
                patch(
                    "offers_bot.parser.parse_with_llm", return_value=None
                ) as sync_llm,
                patch(
                    "offers_bot.parser.parse_with_llm_async",
                    new=AsyncMock(return_value=None),
                ) as async_llm,
            ):
                text = "Galaxy A07 R$ 798,30 https://cutt.ly/example"
                offers = (
                    await extract_offers_async(text)
                    if asynchronous
                    else extract_offers(text)
                )
            self.assertEqual(self.requests, ["https://cutt.ly/example"])
            self.assertEqual(len(offers), 1)
            self.assertEqual(offers[0].url, SAMPLE_PRODUCT_URL)
            self.assertEqual(offers[0].platform, "magalu")
            used_llm = async_llm if asynchronous else sync_llm
            self.assertIn(SAMPLE_PRODUCT_URL, used_llm.call_args.args[0])
            self.assertNotIn("cutt.ly", offers[0].original_text)

    async def test_unsafe_redirects_are_rejected_before_second_request(self):
        for destination in (
            "http://www.magazineluiza.com.br/p/123/",
            "https://127.0.0.1/",
            "https://evil.test/product",
            "https://user@www.magazineluiza.com.br/p/123/",
        ):
            client = self.transport(destination)
            with patch("offers_bot.magalu.httpx.Client", return_value=client):
                with self.assertRaises(ValueError):
                    resolve_product_url("https://cutt.ly/example")
            self.assertEqual(len(self.requests), 1)

    async def test_redirect_loop_is_bounded_and_failed_link_not_parsed(self):
        client = self.transport("https://cutt.ly/loop")
        with patch("offers_bot.magalu.httpx.Client", return_value=client):
            with self.assertRaises(MagaluError):
                resolve_product_url("https://cutt.ly/loop")
        self.assertEqual(len(self.requests), 5)
        with (
            patch(
                "offers_bot.parser.resolve_product_url",
                side_effect=MagaluError("failed"),
            ),
            patch("offers_bot.parser.parse_with_llm", return_value=None),
        ):
            self.assertEqual(extract_offers("Produto https://cutt.ly/example"), [])
        self.assertEqual(detect_platform(SAMPLE_PRODUCT_URL), "magalu")


class MagaluBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_shortened_offer_is_converted_before_posting_and_deduplicated(self):
        factory = MagicMock()
        bot = UserBotInstance(42, factory)
        bot._source_chats = ("source",)
        bot._destination_chat_ids = ("destination",)
        bot._magalu = MagaluClient(**IDS)
        store = AsyncMock()
        store.seen.return_value = False
        store.seen_affiliate_url.return_value = False
        store.seen_product_key.return_value = False
        with (
            patch(
                "offers_bot.parser.resolve_product_url", return_value=SAMPLE_PRODUCT_URL
            ),
            patch(
                "offers_bot.parser.parse_with_llm_async",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                MagaluClient, "generate", return_value=generated()
            ) as generate,
            patch("backend.worker.manager.PgOfferStore", return_value=store),
            patch.object(bot, "_send_offer_with_image", new=AsyncMock()) as send,
        ):
            await bot.process_message(
                "source", 123, "Galaxy A07 R$ 798,30 https://cutt.ly/example"
            )
        generate.assert_called_once_with(SAMPLE_PRODUCT_URL)
        send.assert_awaited_once()
        self.assertIn(SHORT, send.call_args.args[0])
        self.assertIn("798,30", send.call_args.args[0])
        self.assertNotIn("cutt.ly", send.call_args.args[0])
        store.mark.assert_awaited_once_with(
            "source", 123, SAMPLE_PRODUCT_URL, SHORT, "MAGALU:240466500:magazineluiza"
        )

    async def test_saved_config_is_validated_without_endpoint_overrides(self):
        config = UserConfigCreate(config_type="magalu", config_data=VALUES)
        users._validate_config(config)
        self.assertEqual(config.config_data, VALUES)
        for values in (
            {},
            {**VALUES, "magalu_promoter_id": "bad"},
            {**VALUES, "endpoint": "https://evil.test"},
        ):
            with self.subTest(values=values), self.assertRaises(HTTPException):
                users._validate_config(
                    UserConfigCreate(config_type="magalu", config_data=values)
                )

    async def test_credential_probe_generates_with_draft_ids_without_saving(self):
        with patch.object(
            MagaluClient, "generate", return_value=generated()
        ) as generate:
            result = await validate_credentials(
                CredentialValidationRequest(provider="magalu", config_data=VALUES), 42
            )
        self.assertEqual(result.status, "valid")
        generate.assert_called_once_with(SAMPLE_PRODUCT_URL)

    async def test_magalu_only_configuration_activates_and_routes_worker(self):
        bot = UserBotInstance(42, None)
        self.addCleanup(bot.close)
        with (
            patch.object(
                bot,
                "_load_configs",
                new=AsyncMock(
                    return_value={**VALUES, "source_chats": ["https://t.me/promotom"]}
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
        self.assertTrue(bot._affiliate_client_for_platform("magalu").ready())


class MagaluEndpointTests(unittest.TestCase):
    def setUp(self):
        magalu._recent.clear()
        magalu._active.clear()
        app = FastAPI()
        app.include_router(magalu.router)
        self.db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.first.return_value = SimpleNamespace(
            config_data=json.dumps(VALUES)
        )
        self.db.execute.return_value = result

        async def database():
            yield self.db

        app.dependency_overrides[get_db] = database
        self.app = app
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def authenticate(self):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=42)

    def test_authentication_required(self):
        response = self.client.post(
            "/affiliate/magalu", json={"url": SAMPLE_PRODUCT_URL}
        )
        self.assertEqual(response.status_code, 401)
        self.db.execute.assert_not_called()

    def test_only_owned_saved_ids_are_used_and_rate_is_bounded(self):
        self.authenticate()
        with patch.object(
            MagaluClient, "generate", return_value=generated()
        ) as generate:
            response = self.client.post(
                "/affiliate/magalu", json={"url": SAMPLE_PRODUCT_URL}
            )
            limited = self.client.post(
                "/affiliate/magalu", json={"url": SAMPLE_PRODUCT_URL}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["affiliate_url"], SHORT)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(limited.status_code, 429)
        generate.assert_called_once_with(SAMPLE_PRODUCT_URL, "lucreator")
        statement = str(self.db.execute.call_args.args[0])
        self.assertIn("user_configs.user_id", statement)
        self.assertEqual(
            self.db.execute.call_args.args[0].compile().params["user_id_1"], 42
        )

    def test_caller_cannot_supply_account_or_endpoint(self):
        self.authenticate()
        for extra in (
            {"promoter_id": "another"},
            {"endpoint": "https://evil.test"},
            {"channel": "unknown"},
        ):
            response = self.client.post(
                "/affiliate/magalu", json={"url": SAMPLE_PRODUCT_URL, **extra}
            )
            self.assertEqual(response.status_code, 422)
        self.db.execute.assert_not_called()

    def test_provider_errors_are_safe(self):
        self.authenticate()
        with patch.object(
            MagaluClient, "generate", side_effect=MagaluError("private upstream body")
        ):
            response = self.client.post(
                "/affiliate/magalu", json={"url": SAMPLE_PRODUCT_URL}
            )
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private upstream body", response.text)
        self.assertNotIn(42, magalu._active)
