import unittest
from unittest.mock import AsyncMock, patch

import httpx
from telethon.extensions import html
from telethon.helpers import add_surrogate
from telethon.tl.types import MessageEntityBold, MessageEntityCode, MessageEntityPre

from backend.worker.poster import BotPoster, _telegram_offer_html
from offers_bot.main import wrap_coupon_codes


class TelegramOfferFormattingTests(unittest.TestCase):
    def test_coupons_are_independent_inline_entities_after_emoji(self):
        text = (
            "🔥 **Oferta & desconto**\n🎟️ Cupom: "
            + wrap_coupon_codes("EXTRA5 ou SUPER10")
            + " + moedas\nhttps://example.com/?a=1&b=2"
        )

        rendered = _telegram_offer_html(text)
        plain_text, entities = html.parse(rendered)
        surrogate_text = add_surrogate(plain_text)
        codes = [entity for entity in entities if isinstance(entity, MessageEntityCode)]

        self.assertEqual(
            [surrogate_text[code.offset : code.offset + code.length] for code in codes],
            ["EXTRA5", "SUPER10"],
        )
        self.assertFalse(
            any(isinstance(entity, MessageEntityPre) for entity in entities)
        )
        self.assertTrue(
            any(isinstance(entity, MessageEntityBold) for entity in entities)
        )
        self.assertIn("Oferta & desconto", plain_text)
        self.assertIn(" + moedas", plain_text)
        self.assertIn("https://example.com/?a=1&b=2", plain_text)

    def test_inline_code_and_multiline_blocks_keep_their_entities(self):
        rendered = _telegram_offer_html("Cupom: `EXTRA5`\n```linha 1\nlinha 2```")
        _, entities = html.parse(rendered)

        self.assertEqual(
            [type(entity) for entity in entities],
            [MessageEntityCode, MessageEntityPre],
        )


class TelegramPosterTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_photo_caption_send_inline_coupon_html(self):
        for image_file in (None, "https://example.com/photo.jpg"):
            with self.subTest(image_file=image_file):
                client = AsyncMock()
                client.post.return_value = httpx.Response(
                    200, json={"ok": True, "result": {"message_id": 1}}
                )
                with patch("backend.worker.poster.httpx.AsyncClient") as client_class:
                    client_class.return_value.__aenter__.return_value = client
                    await BotPoster(token="test-token").send_offer(
                        "-100123",
                        "🎟️ Cupom: " + wrap_coupon_codes("EXTRA5"),
                        image_file=image_file,
                        parse_mode="Markdown",
                    )

                payload = client.post.call_args.kwargs["json"]
                self.assertEqual(payload["parse_mode"], "HTML")
                self.assertEqual(
                    payload["caption" if image_file else "text"],
                    "🎟️ Cupom: <code>EXTRA5</code>",
                )
                self.assertTrue(
                    client.post.call_args.args[0].endswith(
                        "/sendPhoto" if image_file else "/sendMessage"
                    )
                )

    async def test_plain_text_keeps_literal_backticks(self):
        client = AsyncMock()
        client.post.return_value = httpx.Response(
            200, json={"ok": True, "result": {"message_id": 1}}
        )
        with patch("backend.worker.poster.httpx.AsyncClient") as client_class:
            client_class.return_value.__aenter__.return_value = client
            await BotPoster(token="test-token").send_offer("-100123", "`EXTRA5`")

        self.assertEqual(
            client.post.call_args.kwargs["json"],
            {"chat_id": "-100123", "text": "`EXTRA5`"},
        )
