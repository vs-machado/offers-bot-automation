import unittest

from offers_bot.main import format_offer
from offers_bot.parser import extract_ml_ids, extract_offers


class ParserTest(unittest.TestCase):
    def test_extracts_mercado_livre_offer_title_and_price(self):
        offers = extract_offers(
            "Creatina Growth R$ 49,90 https://www.mercadolivre.com.br/x/p/MLB19603205"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "Creatina Growth")
        self.assertEqual(offers[0].price, "R$ 49,90")
        self.assertIsNone(offers[0].coupon)
        self.assertFalse(offers[0].meli_plus_only)
        self.assertEqual(offers[0].url, "https://www.mercadolivre.com.br/x/p/MLB19603205")

    def test_removes_leading_status_text_from_inline_title(self):
        offers = extract_offers(
            'AINDA ATIVO! Notebook Gamer Lenovo LOQ 15IRX9, 15.6" Full HD 144Hz, Intel Core i5-13450HX, 16GB, 512GB SSD, NVIDIA RTX 4050, Linux - 83KHS00300 R$ 5084 -CUPOM: 5DO5 https://tidd.ly/4ulBz1F -Anúncio https://meli.la/2DYnu6W'
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            offers[0].title,
            'Notebook Gamer Lenovo LOQ 15IRX9, 15.6" Full HD 144Hz, Intel Core i5-13450HX, 16GB, 512GB SSD, NVIDIA RTX 4050, Linux - 83KHS00300',
        )
        self.assertEqual(offers[0].price, "R$ 5084")
        self.assertEqual(offers[0].coupon, "5DO5")
        self.assertFalse(offers[0].meli_plus_only)

    def test_prefers_product_line_over_status_line(self):
        offers = extract_offers(
            "AINDA ATIVO!\n\nNotebook Gamer Lenovo LOQ 15IRX9\n\nR$ 5084\n\nhttps://meli.la/2DYnu6W"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "Notebook Gamer Lenovo LOQ 15IRX9")

    def test_ignores_promo_citation_when_product_line_exists(self):
        offers = extract_offers(
            "LEGO SAINDO POR UM PREÇO BAIXO, APROVEITA!\n\n✅ Blocos De Montar Star Wars 75373 Pack Da Emboscada Em Mandalore 109 peças Lego\n\nDE:R$199,99\n🔥 POR R$111 🔥\n\n🎟️ Cupom: 10MELIMAIS\n\n⚡ Produto com entrega FULL\n\n🔗https://meli.la/1CX6mXd\nSelecione a loja Oficial Lego\n\n*anúncio\n\n💥 Hoje, 00h, começa o 5.5 — prepara o carrinho porque vem oferta pesada!"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            offers[0].title,
            "Blocos De Montar Star Wars 75373 Pack Da Emboscada Em Mandalore 109 peças Lego",
        )

    def test_extracts_coupon_from_offer_message(self):
        offers = extract_offers(
            "Jogo De Ferramentas 169 Peças\n\n💰 R$ 236,00\n\n🎟 Cupom: MELIMAISPROMO\n\nhttps://meli.la/136mqYH"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].coupon, "MELIMAISPROMO")

    def test_extracts_coupon_from_common_variants(self):
        samples = [
            (
                "Teclado Mecânico Gamer Sem Fio Bluetooth Attack Shark X87\n\nR$ 239\n-CUPOM: MELIMAISPROMO\n\nhttps://meli.la/1Kgq6Qa",
                "R$ 239",
            ),
            (
                "Natura Homem Tradicional Desodorante Colônia Perfume Masculino Original 100ml\n\n🔥 Por: R$ 98,85 à vista\n🎯 Usem o cupom: MELIMAISPROMO\n🛒 https://meli.la/24Cu5QT\n\n⚠️ Cupom exclusivo para assinantes Meli+",
                "R$ 98,85",
            ),
            (
                "Cooktop Atlas Agile Up 4 Bocas Vidro\n\nPOR R$ 281,91\n\n🎟️ Use o cupom: MELIMAISPROMO\n\nCOMPRE AQUI https://meli.la/1UYPfY5",
                "R$ 281,91",
            ),
            (
                "Perfume Masculino Malbec 100ml\n\n💰 R$ 142\n\n🎟 Cupom: MELIMAISPROMO\n\n⚡️ Link do Produto:\nhttps://meli.la/2Z866Jm",
                "R$ 142",
            ),
        ]

        for sample, expected_price in samples:
            with self.subTest(sample=sample[:40]):
                offers = extract_offers(sample)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0].coupon, "MELIMAISPROMO")
                self.assertEqual(offers[0].price, expected_price)

    def test_extracts_multiple_coupons_and_meli_plus_flag(self):
        offers = extract_offers(
            "sérum super vitamina c 20% 30ml sallve de R$ 89,90 por R$ 59,84\n\n🔗 https://meli.la/1jujZ2D\nanúncio / válido por tempo limitado\n\n🏷️ cupom *10MELIMAIS* ou *MELIMAISPROMO* (para clientes meli+)"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].coupon, "10MELIMAIS ou MELIMAISPROMO")
        self.assertTrue(offers[0].meli_plus_only)

    def test_format_offer_shows_meli_plus_flag(self):
        offer = extract_offers(
            "sérum super vitamina c 20% 30ml sallve de R$ 89,90 por R$ 59,84\n\n🔗 https://meli.la/1jujZ2D\n\n🏷️ cupom *10MELIMAIS* ou *MELIMAISPROMO* (para clientes meli+)"
        )[0]

        formatted = format_offer(offer, "https://meli.la/final123")

        self.assertIn("🎟️ CUPOM: 10MELIMAIS ou MELIMAISPROMO", formatted)
        self.assertIn("⭐ Exclusivo para clientes Meli+", formatted)

    def test_prefers_price_after_por_when_original_price_exists(self):
        offers = extract_offers(
            "🔥 Filtro De Linha iClamper Energia 8 | DPS | 8 Tomadas | Bivolt\n\n✅ De R$ 188 → Por R$ 116\n🔻 38% OFF\n🛒 https://meli.la/2ELDuyN"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 116")

    def test_ignores_non_mercado_livre_urls(self):
        self.assertEqual(extract_offers("Oferta https://example.com/item"), [])

    def test_trims_meli_short_url_before_appended_noise(self):
        offers = extract_offers("Oferta https://meli.la/1vMs9xn167.51:443/TcpFull complete!")

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].url, "https://meli.la/1vMs9xn")

    def test_extracts_unique_ml_ids(self):
        self.assertEqual(
            extract_ml_ids("MLB19603205 /p/MLB19603205 item MLB5872060016"),
            ["MLB19603205", "MLB5872060016"],
        )

    def test_extract_ml_ids_normalizes_hyphenated_ids(self):
        self.assertEqual(
            extract_ml_ids(
                "https://produto.mercadolivre.com.br/MLB-4222666581-sapato-masculino-casual-_JM"
            ),
            ["MLB4222666581"],
        )


if __name__ == "__main__":
    unittest.main()
