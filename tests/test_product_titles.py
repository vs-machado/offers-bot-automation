"""Regression coverage for source disclaimers replacing product names."""

import asyncio
from dataclasses import replace
import unittest

from offers_bot.main import format_offer, format_outgoing_offer
from offers_bot.parser import _extract_offers


class ProductTitleTest(unittest.TestCase):
    url = "https://amzn.to/abc123"
    notice = "sujeita à alteração de preço e estoque do site"

    def message(self, title, notice=None):
        return f"{title}\nPor: R$ 49,90\n{self.url}\n{notice or self.notice}"

    def test_short_and_uppercase_names_beat_disclaimers(self):
        for title in ("Camiseta", "CAFETEIRA ELÉTRICA", "Kit de toalhas", "SSD"):
            for notice in (
                self.notice,
                "⚠️ Oferta sujeita a alteração de preço e estoque do site.",
                "Ofertas sujeitas à disponibilidade de estoque",
                "Preços e estoques sujeitos a alteração sem aviso prévio",
                "Preços podem variar sem aviso prévio",
                "Enquanto durarem os estoques",
            ):
                with self.subTest(title=title, notice=notice):
                    offer = _extract_offers(self.message(title, notice), None)[0]
                    self.assertEqual(offer.title, title)
                    self.assertEqual(
                        format_offer(offer, self.url).splitlines()[0], title
                    )

    def test_inline_disclaimer_preserves_product_name(self):
        text = self.message(f"Kit de toalhas — {self.notice}")
        self.assertEqual(_extract_offers(text, None)[0].title, "Kit de toalhas")

    def test_notice_without_product_does_not_become_title(self):
        offer = _extract_offers(self.message(""), None)[0]
        self.assertIsNone(offer.title)
        self.assertNotIn(self.notice, format_offer(offer, self.url))

    def test_invalid_llm_title_falls_back_for_each_offer_path(self):
        url_groups = (
            [self.url],
            ["https://s.shopee.com.br/abc", "https://shopee.com.br/product/123/456"],
            [
                "https://s.click.aliexpress.com/e/abc",
                "https://s.click.aliexpress.com/e/def",
            ],
        )
        for urls in url_groups:
            with self.subTest(urls=urls):
                text = f"Kit de toalhas\nResgate aqui\n{' '.join(urls)}\n{self.notice}"
                result = {
                    "classification": "product",
                    "products": [{"title": self.notice, "urls": urls}],
                }
                offers = _extract_offers(text, result)
                self.assertTrue(offers)
                for offer in offers:
                    self.assertEqual(offer.title, "Kit de toalhas")
                    formatted = format_offer(offer, urls[0])
                    self.assertEqual(formatted.splitlines()[0], "Kit de toalhas")
                    self.assertNotIn(self.notice, formatted)

    def test_formatter_validates_legacy_offer_and_raw_llm_title(self):
        result = {
            "classification": "product",
            "products": [{"title": self.notice, "urls": [self.url]}],
        }
        offer = _extract_offers(self.message("Camiseta"), result)[0]
        legacy_offer = replace(offer, title=self.notice)
        self.assertEqual(
            format_offer(legacy_offer, self.url).splitlines()[0], "Camiseta"
        )

    def test_variant_names_remain_distinct_in_grouped_post(self):
        urls = [self.url, "https://amzn.to/def456"]
        titles = ("Camiseta azul", "Camiseta verde")
        result = {
            "classification": "product",
            "products": [
                {"title": title, "urls": [url]} for title, url in zip(titles, urls)
            ],
        }
        source = "\n".join(f"{title}\n{url}" for title, url in zip(titles, urls))
        (offer,) = _extract_offers(f"{source}\n{self.notice}", result)
        affiliates = ["https://amzn.to/aff_azul", "https://amzn.to/aff_verde"]
        post = asyncio.run(
            format_outgoing_offer(
                offer, affiliates[0], url_replacements={urls[1]: affiliates[1]}
            )
        )
        self.assertIn("\n".join(f"{t}\n{u}" for t, u in zip(titles, affiliates)), post)

    def test_valid_llm_title_keeps_words_used_in_promo_copy(self):
        title = "Kit de moedas colecionáveis"
        result = {
            "classification": "product",
            "products": [{"title": title, "urls": [self.url]}],
        }
        offer = _extract_offers(self.message(title), result)[0]
        self.assertEqual(offer.title, title)
        self.assertEqual(format_offer(offer, self.url).splitlines()[0], title)
