import asyncio
import unittest
from unittest.mock import patch

from offers_bot.main import format_offer, format_outgoing_offer
from offers_bot.parser import Offer, extract_offers, select_product_title
from offers_bot.source_cleanup import clean_source_advertising


class FormattingRegressionTest(unittest.TestCase):
    gta_source = (
        "GTA VI PS5\n\n"
        "R$ 335\n\n"
        "🏷️ Resgate todos os cupons desta página:\n"
        "https://s.shopee.com.br/2gCq4B3G7j\n\n"
        "✅ Link do produto:\n"
        "https://s.shopee.com.br/5q9rq13aRE\n\n"
        "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot\n\n"
        "-Anúncio"
    )

    def test_product_link_span_does_not_remove_shopee_product(self):
        llm = {
            "classification": "product",
            "source_advertising_spans": [
                "✅ Link do produto:\n"
                "https://s.shopee.com.br/5q9rq13aRE\n\n"
                "🔔 BOT DE ALERTAS: https://t.me/alertadaspromobot"
            ],
        }
        with patch("offers_bot.parser.parse_with_llm", return_value=llm):
            offers = extract_offers(self.gta_source)

        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.url, "https://s.shopee.com.br/5q9rq13aRE")
        self.assertIn("https://s.shopee.com.br/5q9rq13aRE", offer.all_urls)
        self.assertIn("https://s.shopee.com.br/2gCq4B3G7j", offer.all_urls)
        self.assertIn("Link do produto", offer.original_text)
        self.assertNotIn("BOT DE ALERTAS", offer.original_text)

    def test_llm_normalized_shopee_url_matches_source_url(self):
        source = (
            "Smart TV 65 QNED\n\n"
            "R$ 3.128\n\n"
            "🏷️ Resgate todos os cupons desta página:\n"
            "https://s.shopee.com.br/coupon1\n\n"
            "✅ Link do produto:\n"
            "https://s.shopee.com.br/2qWGETZaZn"
        )
        llm = {
            "classification": "product",
            "products": [
                {
                    "title": "Smart TV 65 QNED",
                    "price": "R$ 3.128",
                    "urls": ["https://shopee.com.br/2qWGETZaZn"],
                }
            ],
            "source_advertising_spans": [],
        }
        with patch("offers_bot.parser.parse_with_llm", return_value=llm):
            offers = extract_offers(source)

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].url, "https://s.shopee.com.br/2qWGETZaZn")
        self.assertIsNotNone(offers[0].llm_product)
        self.assertEqual(offers[0].llm_product["title"], "Smart TV 65 QNED")

    def test_unlabeled_store_url_survives_ad_span(self):
        url = "https://s.shopee.com.br/product1"
        span = f"{url}\nBOT DE ALERTAS: https://t.me/alertas"
        source = f"GTA VI\nR$ 100\n{span}"

        cleaned = clean_source_advertising(source, [span])

        self.assertIn(url, cleaned)
        self.assertNotIn("BOT DE ALERTAS", cleaned)

    def test_shopee_product_label_without_product_url_is_skipped(self):
        source = (
            "Produto qualquer\n\n"
            "R$ 10\n\n"
            "Resgate cupons:\n"
            "https://s.shopee.com.br/coupon1\n\n"
            "Link do produto:\n"
            "-Anúncio"
        )

        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offers = extract_offers(source)

        self.assertEqual(offers, [])

    def test_product_label_does_not_claim_coupon_from_later_section(self):
        coupon_section = "Resgate cupons:\nhttps://s.shopee.com.br/coupon1"
        for label in ("Link do produto:", "Produto:", "Carrinho:"):
            for sections in (
                f"{label}\n\n{coupon_section}",
                f"{coupon_section}\n\n{label}",
            ):
                with self.subTest(sections=sections):
                    with patch("offers_bot.parser.parse_with_llm", return_value=None):
                        offers = extract_offers(f"GTA VI\nR$ 100\n{sections}")
                    self.assertEqual(offers, [])

    def test_short_product_url_under_standalone_label_is_selected(self):
        source = (
            "GTA VI\nR$ 100\n"
            "Produto:\n\nhttps://s.shopee.com.br/product1\n"
            "Resgate cupons:\nhttps://s.shopee.com.br/coupon1"
        )
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offers = extract_offers(source)

        self.assertEqual(
            [offer.url for offer in offers], ["https://s.shopee.com.br/product1"]
        )

    def test_shopee_resgate_output_normalizes_price_and_keeps_one_disclosure(self):
        source = (
            "GTA VI\nR$ 255 - Finalização\n"
            "Resgate cupons:\nhttps://s.shopee.com.br/coupon1\n"
            "- Anúncio\nLink do produto:\nhttps://s.shopee.com.br/product1"
        )
        with patch("offers_bot.parser.parse_with_llm", return_value=None):
            offer = extract_offers(source)[0]

        formatted = asyncio.run(
            format_outgoing_offer(offer, "https://s.shopee.com.br/affiliate")
        )

        self.assertIn("R$ 255 (preço na finalização)", formatted)
        self.assertIn("https://s.shopee.com.br/coupon1", formatted)
        self.assertIn("https://s.shopee.com.br/affiliate", formatted)
        self.assertEqual(formatted.count("- Anúncio"), 1)
        self.assertTrue(formatted.endswith("- Anúncio"))

    def test_finalization_price_is_explicit(self):
        offer = extract_offers(
            "INVICTA Relógio masculino\n\n"
            "R$ 255 - Finalização\n\n"
            "https://amzn.to/abc123"
        )[0]

        formatted = format_offer(offer, "https://amzn.to/aff123")

        self.assertEqual(offer.price, "R$ 255 (preço na finalização)")
        self.assertIn("💰 R$ 255 (preço na finalização)", formatted)

    def test_title_truncates_at_word_boundary(self):
        long_title = (
            "Utopia Towels "
            + "conjunto de toalhas macias para banheiro spa academia " * 6
            + "toalha"
        )

        truncated = select_product_title("", long_title)

        self.assertTrue(truncated.endswith("..."))
        self.assertLessEqual(len(truncated), 183)
        prefix = truncated[:-3]
        self.assertTrue(long_title.startswith(prefix))
        self.assertEqual(long_title[len(prefix)], " ")

    def test_disclosure_from_llm_note_is_not_duplicated(self):
        offer = Offer(
            original_text="Produto\n\nR$ 10\n\nhttps://amzn.to/abc123",
            url="https://amzn.to/abc123",
            title="Produto",
            price="R$ 10",
            card_price=None,
            installment_info=None,
            shipping_info=None,
            coupon=None,
            meli_plus_only=False,
            llm_result={
                "classification": "product",
                "products": [
                    {
                        "title": "Produto",
                        "price": "R$ 10",
                        "resgate_anuncio_note": "-Anúncio",
                        "meli_plus_only": False,
                        "urls": ["https://amzn.to/abc123"],
                    }
                ],
            },
            llm_product={
                "title": "Produto",
                "price": "R$ 10",
                "resgate_anuncio_note": "-Anúncio",
                "meli_plus_only": False,
                "urls": ["https://amzn.to/abc123"],
            },
        )

        formatted = asyncio.run(format_outgoing_offer(offer, "https://amzn.to/aff123"))

        self.assertEqual(formatted.count("Anúncio"), 1)
        self.assertTrue(formatted.endswith("- Anúncio"))


if __name__ == "__main__":
    unittest.main()
