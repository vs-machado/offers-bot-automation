import asyncio
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from offers_bot.main import format_outgoing_offer
from offers_bot.parser import extract_offers, extract_offers_async
from offers_bot.source_cleanup import clean_source_advertising


class SourceAdvertisingTest(unittest.TestCase):
    source = (
        "Memória Gbt 8GB Ddr5 5600mhz - Gbt5600d5/8\n\n"
        "💵 R$ 792\n\n"
        "🏷️ Resgate todos os cupons desta página:\n"
        "https://s.shopee.com.br/3Vl3w8QKCi\n\n"
        "✅ Link do produto:\n"
        "https://s.shopee.com.br/20wG9NVtif\n\n"
        "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot\n\n"
        "- Anúncio"
    )

    def test_shopee_source_reuse_removes_ad_and_preserves_both_offer_links(self):
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offer = extract_offers(self.source)[0]
        # Previously parsed/queued offers can still carry unclean source text.
        offer = replace(offer, original_text=self.source)
        outgoing = asyncio.run(
            format_outgoing_offer(
                offer,
                "https://s.shopee.com.br/ourproduct",
                url_replacements={
                    "https://s.shopee.com.br/3Vl3w8QKCi": "https://s.shopee.com.br/ourcoupons"
                },
            )
        )
        self.assertIn("Memória Gbt 8GB Ddr5 5600mhz - Gbt5600d5/8", outgoing)
        self.assertIn("💵 R$ 792", outgoing)
        self.assertIn("🏷️ Resgate todos os cupons desta página:", outgoing)
        self.assertIn("https://s.shopee.com.br/ourcoupons", outgoing)
        self.assertIn("https://s.shopee.com.br/ourproduct", outgoing)
        self.assertNotIn("BOT DE ALERTAS", outgoing)
        self.assertNotIn("alertadaspromobot", outgoing)
        self.assertEqual(outgoing.count("- Anúncio"), 1)

    def test_aliexpress_source_reuse_also_cleans_advertising(self):
        text = (
            "SSD R$ 50 com moedas no AliExpress\n"
            "https://s.click.aliexpress.com/e/itemA\n"
            "https://s.click.aliexpress.com/e/itemB\n\n"
            "Robô de alertas:\n\n@outro_servico\n\n- Anúncio"
        )
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offer = replace(extract_offers(text)[0], original_text=text)
        outgoing = asyncio.run(
            format_outgoing_offer(
                offer, "https://s.click.aliexpress.com/e/ours", is_ali=True
            )
        )
        self.assertNotIn("Robô", outgoing)
        self.assertNotIn("@outro_servico", outgoing)
        self.assertIn("R$ 50 com moedas", outgoing)
        self.assertIn("https://s.click.aliexpress.com/e/itemB", outgoing)
        self.assertIn("https://s.click.aliexpress.com/e/ours", outgoing)

    def test_removes_label_variants_without_fixed_bot_username(self):
        ads = (
            "🔔 BOT DE ALERTAS: https://t.me/qualquer_nome?start=referral",
            "**Bot de avisos:**\nhttps://telegram.me/novo_nome",
            "🤖 Bot para alertas\n\n@servico_novo",
            "[Bot de monitoramento](https://t.me/precos)",
            "Receba avisos quando baixar: @qualquernome",
        )
        for ad in ads:
            with self.subTest(ad=ad):
                text = f"Produto R$ 50\n\n{ad}\n\nCUPOM: TESTE20"
                self.assertEqual(
                    clean_source_advertising(text),
                    "Produto R$ 50\n\nCUPOM: TESTE20",
                )

    def test_does_not_consume_offer_after_destinationless_label(self):
        text = "Bot de alertas:\n\nResgate aqui:\nhttps://s.shopee.com.br/cupom"
        self.assertEqual(
            clean_source_advertising(text),
            "Resgate aqui:\nhttps://s.shopee.com.br/cupom",
        )

    def test_keeps_legitimate_conditions_and_unrelated_telegram_links(self):
        text = (
            "Robô aspirador R$ 500\n\n"
            "R$ 50 com moedas no AliExpress\n"
            "Ative notificações de entrega no aplicativo\n"
            "Suporte: https://t.me/loja_oficial\n"
            "https://s.shopee.com.br/produto?ref=affiliate"
        )
        self.assertEqual(clean_source_advertising(text), text)

    def test_sync_and_async_parsers_send_clean_content_to_llm(self):
        with patch("offers_bot.parser.parse_with_llm", return_value=None) as parse:
            offers = extract_offers(self.source)
        clean_text = parse.call_args.args[0]
        self.assertNotIn("BOT DE ALERTAS", clean_text)
        self.assertNotIn("alertadaspromobot", clean_text)
        self.assertEqual(offers[0].original_text, clean_text)
        with patch(
            "offers_bot.parser.parse_with_llm_async", new_callable=AsyncMock
        ) as parse_async:
            parse_async.return_value = None
            async_offers = asyncio.run(extract_offers_async(self.source))
        parse_async.assert_awaited_once_with(clean_text)
        self.assertEqual(async_offers, offers)
