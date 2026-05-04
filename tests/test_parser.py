import unittest

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
        self.assertEqual(offers[0].url, "https://www.mercadolivre.com.br/x/p/MLB19603205")

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


if __name__ == "__main__":
    unittest.main()
