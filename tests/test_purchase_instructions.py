import os
import unittest
from unittest.mock import patch

from offers_bot.llm_parser import ProductSection
from offers_bot.main import format_offer
from offers_bot.parser import extract_offers


class PurchaseInstructionsTests(unittest.TestCase):
    def test_quantity_survives_parsing_and_formatting_alongside_installments(self):
        product = ProductSection(
            title="Sabonete",
            price="R$ 5,90 por unidade",
            purchase_instructions="Adicionar 6 unidades ao carrinho",
            installment_info="3X SEM JUROS",
            meli_plus_only=False,
            urls=["https://amzn.to/soap"],
        )
        with (
            patch.dict(os.environ, {"DISABLE_LLM": "false"}),
            patch(
                "offers_bot.parser.parse_with_llm",
                return_value={
                    "classification": "product",
                    "products": [product.model_dump()],
                },
            ),
        ):
            offers = extract_offers(
                "6x Sabonete R$ 5,90 por unidade em 3x sem juros https://amzn.to/soap"
            )

        self.assertEqual(len(offers), 1)
        message = format_offer(offers[0], "https://amzn.to/affiliate")
        self.assertIn("🛒 Adicionar 6 unidades ao carrinho", message)
        self.assertIn("[3X SEM JUROS] Sabonete", message)
        self.assertIn("R$ 5,90 por unidade", message)

    def test_older_product_payloads_do_not_require_instructions(self):
        product = ProductSection(title="Sabonete", meli_plus_only=False)
        self.assertIsNone(product.purchase_instructions)
