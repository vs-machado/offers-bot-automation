import gc
import unittest
import os
import sqlite3
import tempfile
from unittest.mock import patch
from offers_bot.parser import extract_offers
from offers_bot.main import format_offer
from offers_bot.llm_parser import (
    FALLBACK_LLM_MODEL,
    FINAL_FALLBACK_LLM_MODEL,
    PRIMARY_LLM_MODEL,
    _llm_configs,
    save_token_usage,
)


class LLMParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(_cls):
        # Explicitly enable LLM for this test suite
        if "DISABLE_LLM" in os.environ:
            del os.environ["DISABLE_LLM"]

    def test_save_token_usage(self):
        fd, temp_db = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        os.environ["DATABASE_PATH"] = temp_db

        try:
            save_token_usage(150, 250)
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT prompt_tokens, completion_tokens, total_tokens FROM token_usage"
                )
                row = cursor.fetchone()
                self.assertEqual(row, (150, 250, 400))
        finally:
            if "DATABASE_PATH" in os.environ:
                del os.environ["DATABASE_PATH"]
            gc.collect()
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except Exception:
                    pass

    def test_llm_configs_use_openrouter_key_in_fallback_order(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=True):
            self.assertEqual(
                _llm_configs(),
                [
                    ("primary", PRIMARY_LLM_MODEL, "test-key"),
                    ("fallback", FALLBACK_LLM_MODEL, "test-key"),
                    ("final fallback", FINAL_FALLBACK_LLM_MODEL, "test-key"),
                ],
            )

    @patch("offers_bot.parser.parse_with_llm")
    def test_llm_classifies_product_offer(self, mock_parse):
        mock_parse.return_value = {
            "classification": "product",
            "product": {
                "title": "Creatina Growth",
                "price": "R$ 49,90",
                "meli_plus_only": False,
            },
        }
        text = (
            "Creatina Growth R$ 49,90 https://www.mercadolivre.com.br/x/p/MLB19603205"
        )
        offers = extract_offers(text)

        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.llm_result.get("classification"), "product")
        self.assertIn("Creatina", offer.title)
        self.assertIn("49,90", offer.price)

    @patch("offers_bot.parser.parse_with_llm")
    def test_llm_classifies_coupon_offer(self, mock_parse):
        mock_parse.return_value = {
            "classification": "coupon",
            "coupon": {
                "platform": "Mercado Livre",
                "novo_ml_format": True,
                "generic_format": False,
                "coupons": [
                    {
                        "detail": "15% OFF em compras acima de R$199, Limitado a R$2.000",
                        "code": "ELUX15OFF",
                    }
                ],
            },
        }
        text = (
            "🔥 Novo Cupom Mercado Livre em produtos ELECTROLUX!\n\n"
            "▪️ 15% OFF em compras acima de R$199, Limitado a R$2.000\n\n"
            "🎯 Usem o cupom: ELUX15OFF\n\n"
            "🛒 https://meli.la/1GwL6Yt"
        )
        offers = extract_offers(text)

        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.llm_result.get("classification"), "coupon")

        formatted = format_offer(offer, "https://meli.la/aff123")
        self.assertIn("ELUX15OFF", formatted)
        self.assertIn("15% OFF", formatted)

    @patch("offers_bot.parser.parse_with_llm")
    def test_llm_product_coupon_codes_are_individually_wrapped(self, mock_parse):
        mock_parse.return_value = {
            "classification": "product",
            "product": {
                "title": "Processador Ryzen 5 5600",
                "price": "R$ 717,51",
                "coupon": "LIBRETX5600 + IFPAF7UN ou MAES5 + moedas no APP",
                "meli_plus_only": False,
            },
        }
        offers = extract_offers(
            "Processador Ryzen 5 5600\n"
            "R$ 717,51\n"
            "Cupom: LIBRETX5600 + IFPAF7UN ou MAES5 + moedas no APP\n"
            "https://s.click.aliexpress.com/e/_c4LBE5wb"
        )

        formatted = format_offer(offers[0], "https://s.click.aliexpress.com/e/aff123")

        self.assertIn("🎟️ CUPOM: `LIBRETX5600` + `IFPAF7UN` ou `MAES5`", formatted)
        self.assertNotIn("LIBRETX5600 + IFPAF7UN", formatted)

    @patch("offers_bot.parser.parse_with_llm")
    def test_multi_product_different_prices_per_url(self, mock_parse):
        mock_parse.return_value = {
            "classification": "product",
            "products": [
                {
                    "title": "Havit Headphone Fone de Ouvido H2002d",
                    "price": "R$ 119",
                    "card_price": None,
                    "installment_info": None,
                    "shipping_info": None,
                    "coupon": None,
                    "resgate_anuncio_note": None,
                    "meli_plus_only": False,
                    "urls": [
                        "https://amzn.to/3PyDv8h",
                        "https://amzn.to/4fEgxHd",
                    ],
                },
                {
                    "title": "Fone de Ouvido Sem Fio Fuxi H3",
                    "price": "R$ 151",
                    "card_price": None,
                    "installment_info": None,
                    "shipping_info": None,
                    "coupon": None,
                    "resgate_anuncio_note": None,
                    "meli_plus_only": False,
                    "urls": [
                        "https://amzn.to/4vsqtIT",
                        "https://amzn.to/4uq2XMd",
                        "https://amzn.to/49mxh21",
                    ],
                },
                {
                    "title": "Headphone H2030S",
                    "price": "R$ 65",
                    "card_price": None,
                    "installment_info": None,
                    "shipping_info": None,
                    "coupon": None,
                    "resgate_anuncio_note": None,
                    "meli_plus_only": False,
                    "urls": [],
                },
            ],
        }
        text = (
            "Havit Headphone Fone de Ouvido H2002d\n\n"
            "R$ 119\n\n"
            "1 https://amzn.to/3PyDv8h\n"
            "2 https://amzn.to/4fEgxHd\n\n"
            "-Fuxi-H3  Sem Fio = R$ 151\n"
            "https://amzn.to/4vsqtIT\n"
            "https://amzn.to/4uq2XMd\n"
            "https://amzn.to/49mxh21\n\n"
            "-H2030S = R$ 65\n\n"
            "-Anúncio"
        )
        offers = extract_offers(text)

        self.assertEqual(len(offers), 5)

        # Offer 0: first Havit URL -> R$ 119
        self.assertEqual(offers[0].url, "https://amzn.to/3PyDv8h")
        self.assertEqual(offers[0].title, "Havit Headphone Fone de Ouvido H2002d")
        self.assertEqual(offers[0].price, "R$ 119")
        self.assertIsNotNone(offers[0].llm_product)
        self.assertEqual(offers[0].llm_product.get("price"), "R$ 119")

        # Offer 1: second Havit URL -> R$ 119
        self.assertEqual(offers[1].url, "https://amzn.to/4fEgxHd")
        self.assertEqual(offers[1].title, "Havit Headphone Fone de Ouvido H2002d")
        self.assertEqual(offers[1].price, "R$ 119")

        # Offer 2: first Fuxi URL -> R$ 151
        self.assertEqual(offers[2].url, "https://amzn.to/4vsqtIT")
        self.assertEqual(offers[2].title, "Fone de Ouvido Sem Fio Fuxi H3")
        self.assertEqual(offers[2].price, "R$ 151")

        # Offer 3: second Fuxi URL -> R$ 151
        self.assertEqual(offers[3].url, "https://amzn.to/4uq2XMd")
        self.assertEqual(offers[3].title, "Fone de Ouvido Sem Fio Fuxi H3")
        self.assertEqual(offers[3].price, "R$ 151")

        # Offer 4: third Fuxi URL -> R$ 151
        self.assertEqual(offers[4].url, "https://amzn.to/49mxh21")
        self.assertEqual(offers[4].title, "Fone de Ouvido Sem Fio Fuxi H3")
        self.assertEqual(offers[4].price, "R$ 151")

    @patch("offers_bot.parser.parse_with_llm")
    def test_multi_product_format_offer_uses_correct_price(self, mock_parse):
        mock_parse.return_value = {
            "classification": "product",
            "products": [
                {
                    "title": "Havit Headphone Fone de Ouvido H2002d",
                    "price": "R$ 119",
                    "card_price": None,
                    "installment_info": None,
                    "shipping_info": "FRETE GRÁTIS",
                    "coupon": "HAVIT10",
                    "resgate_anuncio_note": None,
                    "meli_plus_only": False,
                    "urls": [
                        "https://amzn.to/3PyDv8h",
                        "https://amzn.to/4fEgxHd",
                    ],
                },
                {
                    "title": "Fone de Ouvido Sem Fio Fuxi H3",
                    "price": "R$ 151",
                    "card_price": None,
                    "installment_info": None,
                    "shipping_info": None,
                    "coupon": None,
                    "resgate_anuncio_note": None,
                    "meli_plus_only": False,
                    "urls": [
                        "https://amzn.to/4vsqtIT",
                        "https://amzn.to/4uq2XMd",
                        "https://amzn.to/49mxh21",
                    ],
                },
            ],
        }
        text = (
            "Havit Headphone Fone de Ouvido H2002d\n\n"
            "R$ 119\n\n"
            "1 https://amzn.to/3PyDv8h\n"
            "2 https://amzn.to/4fEgxHd\n\n"
            "-Fuxi-H3  Sem Fio = R$ 151\n"
            "https://amzn.to/4vsqtIT\n"
            "https://amzn.to/4uq2XMd\n"
            "https://amzn.to/49mxh21\n\n"
            "-Anúncio"
        )
        offers = extract_offers(text)

        # Havit formatted output includes R$ 119
        formatted_havit = format_offer(offers[0], "https://amzn.to/aff_havit")
        self.assertIn("Havit Headphone", formatted_havit)
        self.assertIn("R$ 119", formatted_havit)
        self.assertIn("HAVIT10", formatted_havit)
        self.assertIn("FRETE GRÁTIS", formatted_havit)
        self.assertNotIn("R$ 151", formatted_havit)

        # Fuxi formatted output includes R$ 151
        formatted_fuxi = format_offer(offers[2], "https://amzn.to/aff_fuxi")
        self.assertIn("Fuxi H3", formatted_fuxi)
        self.assertIn("R$ 151", formatted_fuxi)
        self.assertNotIn("R$ 119", formatted_fuxi)
        self.assertNotIn("HAVIT10", formatted_fuxi)
