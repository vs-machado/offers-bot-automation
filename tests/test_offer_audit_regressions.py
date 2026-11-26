import unittest
from unittest.mock import patch

from offers_bot.main import format_llm_offer, format_offer, format_outgoing_offer
from offers_bot.parser import _extract_offers, extract_offers, extract_offers_async


class OfferAuditTests(unittest.TestCase):
    def test_standalone_price_beats_title_price_with_or_without_model(self):
        url = "https://meli.la/2ELDuyN"
        source = (
            f"Purificador Electrolux PN10B - R$ 289\n\nR$ 245\n-CUPOM: 15ELUX\n{url}"
        )
        parsed = {
            "classification": "product",
            "products": [
                {
                    "title": "Purificador Electrolux PN10B",
                    "price": "R$ 289",
                    "urls": [url],
                }
            ],
        }
        for result in (None, parsed):
            with self.subTest(model=bool(result)):
                (offer,) = _extract_offers(source, result)
                self.assertEqual(offer.price, "R$ 245")
                self.assertIn("💰 R$ 245", format_offer(offer, url))

    def test_checkout_conditions_must_come_from_source(self):
        url = "https://meli.la/2ELDuyN"
        source = f"Presente Natura Mamãe e Bebê\nR$ 93\nCupom: BLACK25BABY\n{url}"
        parsed = {
            "classification": "product",
            "products": [
                {
                    "title": "Presente Natura Mamãe e Bebê",
                    "shipping_info": "FRETE GRÁTIS",
                    "meli_plus_only": True,
                    "urls": [url],
                }
            ],
        }
        (offer,) = _extract_offers(source, parsed)
        post = format_offer(offer, url)
        self.assertNotIn("FRETE GRÁTIS", post)
        self.assertNotIn("Meli+", post)

        (offer,) = _extract_offers(
            source + "\nFrete grátis para Sul\nCupom exclusivo para clientes Meli+",
            parsed,
        )
        post = format_offer(offer, url)
        self.assertIn("FRETE GRÁTIS PARA SUL", post)
        self.assertIn("Exclusivo para clientes Meli+", post)

    def test_app_only_condition_survives_both_formatter_paths(self):
        url = "https://www.magazineluiza.com.br/notebook/p/123456789/in/note/"
        source = f"Notebook Lenovo IdeaPad\n-Somente no APP Magalu\nR$ 2484\n-CUPOM: NOTE10\n{url}"
        parsed = {
            "classification": "product",
            "products": [{"title": "Notebook Lenovo IdeaPad", "urls": [url]}],
        }
        for result in (None, parsed):
            with self.subTest(model=bool(result)):
                (offer,) = _extract_offers(source, result)
                post = format_offer(offer, url)
                self.assertIn("Somente no APP Magalu", post)
                self.assertIn("NOTE10", post)


class CompetitorLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_competitor_broadcast_skips_both_parser_entry_points(self):
        source = (
            "Live de Ofertas Shopee\n\n-Link Live: https://s.shopee.com.br/example\n\n"
            "Mande o link ou ID do produto nos comentários deste post!"
        )
        with (
            patch("offers_bot.parser.parse_with_llm") as parse,
            patch("offers_bot.parser.parse_with_llm_async") as parse_async,
        ):
            self.assertEqual(extract_offers(source), [])
            self.assertEqual(await extract_offers_async(source), [])
        parse.assert_not_called()
        parse_async.assert_not_called()


class CouponTutorialTests(unittest.IsolatedAsyncioTestCase):
    async def test_coupon_without_code_keeps_source_redemption_steps(self):
        url = "https://meli.la/2ELDuyN"
        affiliate = "https://meli.la/1jujZ2D"
        source = (
            "Próximo Cupom 25% OFF Mercado Livre\n\n"
            "•Tutorial para resgate:\n"
            f"1 Entre no APP do Meli aqui: {url}\n"
            '2 Clique em "Mais" no rodapé do APP\n'
            '3 Depois clique em "Cupons Black Friday"\n'
            "4 Resgate o cupom"
        )
        parsed = {
            "classification": "coupon",
            "coupon": {
                "platform": "Mercado Livre",
                "novo_ml_format": True,
                "coupons": [{"detail": "25% OFF", "code": "25% OFF"}],
            },
        }
        for result in (None, parsed):
            with self.subTest(model=bool(result)):
                (offer,) = _extract_offers(source, result)
                self.assertEqual(
                    await format_outgoing_offer(offer, affiliate),
                    source.replace(url, affiliate) + "\n\n- Anúncio",
                )

    def test_discount_percent_is_not_a_code_but_25off_is(self):
        url = "https://meli.la/2ELDuyN"
        source = f"Cupons Mercado Livre\n25% OFF\n20% OFF: 25OFF\n{url}"
        parsed = {
            "classification": "coupon",
            "coupon": {
                "platform": "Mercado Livre",
                "coupons": [
                    {"detail": "25% OFF", "code": "25% OFF"},
                    {"detail": "20% OFF", "code": "25OFF"},
                ],
            },
        }
        (offer,) = _extract_offers(source, parsed)
        post = format_llm_offer(offer, url)
        self.assertNotIn("25% OFF: 25% OFF", post)
        self.assertIn("20% OFF: ```25OFF```", post)
