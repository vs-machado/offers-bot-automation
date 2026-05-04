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
        self.assertEqual(offers[0].url, "https://www.mercadolivre.com.br/x/p/MLB19603205")

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
