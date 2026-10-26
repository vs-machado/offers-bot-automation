import asyncio
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

from offers_bot.main import format_outgoing_offer
from offers_bot.llm_parser import DealParseResult
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
        llm_result = {
            "classification": "product",
            "source_advertising_spans": [
                "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot"
            ],
        }
        with patch("offers_bot.parser.parse_with_llm", return_value=llm_result):
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
        llm_result = {
            "classification": "product",
            "source_advertising_spans": ["Robô de alertas:\n\n@outro_servico"],
        }
        with patch("offers_bot.parser.parse_with_llm", return_value=llm_result):
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

    def test_removes_semantic_spans_without_phrase_or_destination_rules(self):
        ads = (
            "🔔 BOT DE ALERTAS: https://t.me/qualquer_nome?start=referral",
            "**Bot de avisos:**\nhttps://telegram.me/novo_nome",
            "🤖 Bot para alertas\n\n@servico_novo",
            "[Bot de monitoramento](https://t.me/precos)",
            "Receba avisos quando baixar: @qualquernome",
            "Quando o preço cair, a gente te chama!\n[Quero participar](https://example.org/convite)",
            "Junte moedas pelo nosso robozinho: @outro_nome",
        )
        for ad in ads:
            with self.subTest(ad=ad):
                text = f"Produto R$ 50\n\n{ad}\n\nCUPOM: TESTE20"
                self.assertEqual(
                    clean_source_advertising(text, [ad]),
                    "Produto R$ 50\n\nCUPOM: TESTE20",
                )

    def test_does_not_consume_offer_after_advertising_span(self):
        text = "Bot de alertas:\n\nResgate aqui:\nhttps://s.shopee.com.br/cupom"
        self.assertEqual(
            clean_source_advertising(text, ["Bot de alertas:"]),
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
        self.assertEqual(clean_source_advertising(text, []), text)

    def test_sync_and_async_parsers_use_same_llm_decisions(self):
        ad = "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot"
        llm_result = {
            "classification": "product",
            "source_advertising_spans": [ad],
        }
        with patch(
            "offers_bot.parser.parse_with_llm", return_value=llm_result
        ) as parse:
            offers = extract_offers(self.source)
        parse.assert_called_once_with(self.source)
        self.assertNotIn(ad, offers[0].original_text)
        with patch(
            "offers_bot.parser.parse_with_llm_async", new_callable=AsyncMock
        ) as parse_async:
            parse_async.return_value = llm_result
            async_offers = asyncio.run(extract_offers_async(self.source))
        parse_async.assert_awaited_once_with(self.source)
        self.assertEqual(async_offers, offers)

    def test_rejects_invented_ambiguous_and_malformed_spans(self):
        text = "Oferta válida\nSuporte\nSuporte\nResgate aqui"
        for spans in (
            ["rewritten text"],
            ["Suporte"],
            ["", " ", None, 123],
            "Oferta válida",
            None,
        ):
            with self.subTest(spans=spans):
                self.assertEqual(clean_source_advertising(text, spans), text)

    def test_overlapping_and_duplicate_spans_use_original_positions(self):
        text = "Produto\n\nSiga nosso canal: @concorrente\n\nR$ 50"
        spans = ["Siga nosso canal: @concorrente", "@concorrente", "@concorrente"]
        self.assertEqual(clean_source_advertising(text, spans), "Produto\n\nR$ 50")

    def test_inline_ad_removal_keeps_offer_on_same_line(self):
        text = "SSD R$ 50 | Participe: @concorrente | CUPOM: SSD20"
        self.assertEqual(
            clean_source_advertising(text, ["Participe: @concorrente | "]),
            "SSD R$ 50 | CUPOM: SSD20",
        )

    def test_unavailable_llm_removes_explicit_alert_advertising(self):
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offer = extract_offers(self.source)[0]
        outgoing = asyncio.run(
            format_outgoing_offer(offer, "https://s.shopee.com.br/ourproduct")
        )
        self.assertNotIn("BOT DE ALERTAS", outgoing)
        self.assertNotIn("alertadaspromobot", outgoing)
        self.assertIn("💵 R$ 792", outgoing)
        self.assertIn("Resgate todos os cupons desta página", outgoing)
        self.assertIn("https://s.shopee.com.br/3Vl3w8QKCi", outgoing)
        self.assertIn("https://s.shopee.com.br/ourproduct", outgoing)

    def test_fallback_cleans_explicit_labels_with_missing_or_malformed_decisions(self):
        for ad in (
            "🔔 BOT DE ALERTAS: https://t.me/qualquer_nome?start=referral",
            "**Bot de avisos:**\nhttps://telegram.me/novo_nome",
            "🤖 Bot para alertas\n\n@servico_novo",
            "[Bot de monitoramento](https://t.me/precos)",
            "Robô de alertas:\n[Participar](https://t.me/avisos)",
        ):
            for spans in ([], None, "invalid"):
                with self.subTest(ad=ad, spans=spans):
                    text = f"SSD R$ 50 com moedas\n\n{ad}\n\nCUPOM: SSD20"
                    self.assertEqual(
                        clean_source_advertising(text, spans),
                        "SSD R$ 50 com moedas\n\nCUPOM: SSD20",
                    )

    def test_fallback_preserves_offer_content_and_unpaired_labels(self):
        for text in (
            "Bot de alertas: R$ 50 https://t.me/loja",
            "Bot de alertas: CUPOM: SSD20 https://t.me/loja",
            "Bot de alertas: https://s.shopee.com.br/produto",
            "Bot de alertas:\n\nResgate aqui:\nhttps://s.shopee.com.br/cupom",
            "Bot de alertas:\nSuporte: https://t.me/loja_oficial",
            "https://t.me/loja_oficial\nCUPOM: SSD20",
            "Robô aspirador R$ 500 https://t.me/loja_oficial",
        ):
            with self.subTest(text=text):
                self.assertEqual(clean_source_advertising(text, []), text)

    def test_missed_llm_ad_selection_and_legacy_offers_use_fallback(self):
        with patch(
            "offers_bot.parser.parse_with_llm",
            return_value={"classification": "product"},
        ):
            offer = extract_offers(self.source)[0]
        offer = replace(offer, original_text=self.source)
        outgoing = asyncio.run(
            format_outgoing_offer(offer, "https://s.shopee.com.br/ourproduct")
        )
        self.assertNotIn("BOT DE ALERTAS", outgoing)
        self.assertNotIn("alertadaspromobot", outgoing)
        self.assertIn("Resgate todos os cupons desta página", outgoing)

    def test_async_aliexpress_fallback_removes_repeated_ads_without_llm(self):
        ad = "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot"
        text = (
            f"SSD R$ 50 com moedas no AliExpress\n{ad}\n"
            "https://s.click.aliexpress.com/e/itemA\n"
            "https://s.click.aliexpress.com/e/itemB\n"
            f"{ad}\nCUPOM: SSD20"
        )
        with patch(
            "offers_bot.parser.parse_with_llm_async", new_callable=AsyncMock
        ) as parse:
            parse.return_value = None
            offer = asyncio.run(extract_offers_async(text))[0]
        outgoing = asyncio.run(
            format_outgoing_offer(
                offer, "https://s.click.aliexpress.com/e/ours", is_ali=True
            )
        )
        self.assertNotIn("BOT DE ALERTAS", outgoing)
        self.assertNotIn("alertadaspromobot", outgoing)
        self.assertIn("R$ 50 com moedas", outgoing)
        self.assertIn("SSD20", outgoing)
        self.assertIn("https://s.click.aliexpress.com/e/ours", outgoing)
        self.assertIn("https://s.click.aliexpress.com/e/itemB", outgoing)

    def test_advertising_shopping_link_does_not_become_an_offer(self):
        ad = "Entre no grupo da loja: https://s.shopee.com.br/convite"
        source = f"SSD R$ 50 https://s.shopee.com.br/produto\n\n{ad}"
        with patch(
            "offers_bot.parser.parse_with_llm",
            return_value={
                "classification": "product",
                "source_advertising_spans": [ad],
            },
        ):
            offers = extract_offers(source)
        self.assertEqual(
            [offer.url for offer in offers], ["https://s.shopee.com.br/produto"]
        )

    def test_schema_round_trips_spans_and_defaults_for_legacy_results(self):
        ad = "🔔 Quando baixar, avisamos:\n[Entrar](https://example.org/convite)"
        result = DealParseResult.model_validate(
            {"classification": "product", "source_advertising_spans": [ad]}
        )
        self.assertEqual(result.model_dump()["source_advertising_spans"], [ad])
        legacy = DealParseResult.model_validate({"classification": "product"})
        self.assertEqual(legacy.source_advertising_spans, [])
