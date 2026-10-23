"""Formatting regressions at WhatsApp's outbound text and preview boundary."""

import base64
import tempfile
import unittest
from unittest.mock import AsyncMock

import httpx

from backend.app.core.whatsapp import WahaClient
from backend.app.core.whatsapp_formatting import format_whatsapp_offer
from backend.worker.poster import BotPosterError


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
    async def test_text_and_preview_use_same_formatter_for_groups_and_channels(self):
        for chat_id in ("123@g.us", "123@newsletter"):
            for image in (None, "https://example.com/photo.jpg"):
                with self.subTest(chat_id=chat_id, image=image):
                    client = WahaClient(7)
                    client.request = AsyncMock(
                        return_value=httpx.Response(200, json={"id": "sent"})
                    )
                    await client.send_offer(
                        chat_id,
                        "**Oferta**\nCupom: ```SAVE10```\nhttps://shop.example/item?tag=a__b",
                        image_file=image,
                    )
                    _, endpoint, payload = client.request.call_args.args
                    self.assertEqual(
                        endpoint, "send/link-custom-preview" if image else "sendText"
                    )
                    self.assertEqual(
                        payload["text"],
                        "*Oferta*\nCupom: SAVE10\nhttps://shop.example/item?tag=a__b",
                    )
                    self.assertEqual(payload["session"], "offers-user-7")
                    self.assertTrue(payload["linkPreviewHighQuality"])
                    if image:
                        self.assertEqual(payload["preview"]["title"], "Oferta")
                        self.assertEqual(
                            payload["preview"]["url"],
                            "https://shop.example/item?tag=a__b",
                        )
                        self.assertEqual(payload["preview"]["image"], {"url": image})
                    else:
                        self.assertTrue(payload["linkPreview"])

    async def test_local_image_preview_preserves_markdown_link_and_connection(self):
        client = WahaClient(7, 12)
        client.request = AsyncMock(
            return_value=httpx.Response(200, json={"id": "sent"})
        )
        url = "https://shop.example/item_(blue)?tag=a**b&coupon=SAVE~~20#fragment"
        with tempfile.NamedTemporaryFile() as image:
            image.write(b"product image")
            image.flush()
            await client.send_offer(
                "123@g.us",
                f"**Produto**\n[Comprar]({url})",
                image.name,
                request_timeout=8,
            )
        _, endpoint, payload = client.request.call_args.args
        self.assertEqual(endpoint, "send/link-custom-preview")
        self.assertEqual(payload["session"], "offers-user-7-connection-12")
        self.assertEqual(payload["preview"]["url"], url)
        self.assertEqual(
            payload["preview"]["image"],
            {"data": base64.b64encode(b"product image").decode()},
        )
        self.assertIn(url, payload["text"])
        self.assertEqual(client.request.call_args.kwargs, {"timeout": 8})

    async def test_offer_without_link_sends_text_without_opening_image(self):
        client = WahaClient(7)
        client.request = AsyncMock(
            return_value=httpx.Response(200, json={"id": "sent"})
        )
        await client.send_offer("123@newsletter", "**Oferta**", "/missing/image.jpg")
        _, endpoint, payload = client.request.call_args.args
        self.assertEqual(endpoint, "sendText")
        self.assertEqual(payload["text"], "*Oferta*")
        self.assertNotIn("preview", payload)

    async def test_preview_failure_does_not_send_another_message(self):
        client = WahaClient(7)
        client.request = AsyncMock(side_effect=BotPosterError("Preview failed"))
        with self.assertRaises(BotPosterError):
            await client.send_offer(
                "123@newsletter",
                "Oferta\nhttps://shop.example/item",
                "https://example.com/photo.jpg",
            )
        client.request.assert_awaited_once()
