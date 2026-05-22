import gc
import unittest
import os
import sqlite3
import tempfile
from unittest.mock import patch
from offers_bot.parser import extract_offers
from offers_bot.main import format_offer
from offers_bot.llm_parser import save_token_usage


class LLMParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
