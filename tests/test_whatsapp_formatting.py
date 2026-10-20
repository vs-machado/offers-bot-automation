"""Formatting regressions at WhatsApp's outbound text and photo boundary."""

import unittest
from unittest.mock import AsyncMock

import httpx

from backend.app.core.whatsapp import WahaClient
from backend.app.core.whatsapp_formatting import format_whatsapp_offer


class WhatsAppFormattingTests(unittest.TestCase):
    def test_offer_styles_and_individual_coupons(self):
        text = (
            "🔥 **Oferta 🎧**\n~~R$ 199,90~~ **R$ 99,90**\n"
            "__Só hoje__\n🎟️ Cupom: ```SAVE10``` ou ```OFF20``` + moedas"
        )
        self.assertEqual(
            format_whatsapp_offer(text),
            "🔥 *Oferta 🎧*\n~R$ 199,90~ *R$ 99,90*\n"
            "_Só hoje_\n🎟️ Cupom: SAVE10 ou OFF20 + moedas",
        )

    def test_code_contents_and_affiliate_parameters_are_not_rewritten(self):
        text = (
            "```SAVE__10**OFF~~20```\n`CODE__10`\n"
            "https://shop.example/item__id?tag=a**b&coupon=SAVE~~20#fragment"
        )
        self.assertEqual(
            format_whatsapp_offer(text),
            "SAVE__10**OFF~~20\nCODE__10\n"
            "https://shop.example/item__id?tag=a**b&coupon=SAVE~~20#fragment",
        )

    def test_link_labels_retain_clickable_target_and_tracking(self):
        url = "https://shop.example/item?tag=affiliate&coupon=SAVE10"
        self.assertEqual(
            format_whatsapp_offer(f"[**Comprar**]({url})"),
            f"*Comprar* ({url})",
        )
        self.assertEqual(format_whatsapp_offer(f"[{url}]({url})"), url)

    def test_nested_styles_and_native_whatsapp_markup(self):
        self.assertEqual(
            format_whatsapp_offer("**Oferta __hoje__**"), "*Oferta _hoje_*"
        )
        native = "*Oferta* _hoje_ ~antes~\n```SAVE10```"
        self.assertEqual(
            format_whatsapp_offer(native), "*Oferta* _hoje_ ~antes~\nSAVE10"
        )

    def test_multiline_code_and_unmatched_delimiters(self):
        text = "```**literal**\n__literal__```\n**aberto\ntexto normal"
        self.assertEqual(
            format_whatsapp_offer(text),
            "**literal**\n__literal__\n**aberto\ntexto normal",
        )


class WhatsAppFormattingDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_and_photo_use_same_formatter_for_groups_and_channels(self):
        for chat_id in ("123@g.us", "123@newsletter"):
            for image in (None, "https://example.com/photo.jpg"):
                with self.subTest(chat_id=chat_id, image=image):
                    client = WahaClient(7)
                    client.request = AsyncMock(
                        return_value=httpx.Response(200, json={"id": "sent"})
                    )
                    await client.send_offer(
                        chat_id, "**Oferta**\nCupom: ```SAVE10```", image_file=image
                    )
                    _, endpoint, payload = client.request.call_args.args
                    self.assertEqual(endpoint, "sendImage" if image else "sendText")
                    self.assertEqual(
                        payload["caption" if image else "text"],
                        "*Oferta*\nCupom: SAVE10",
                    )
                    self.assertEqual(payload["session"], "offers-user-7")
