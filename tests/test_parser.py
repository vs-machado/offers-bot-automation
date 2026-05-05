import unittest

from offers_bot.main import format_offer
from offers_bot.parser import extract_ml_ids, extract_offers, extract_shopee_ids


class ParserTest(unittest.TestCase):
    def test_extracts_mercado_livre_offer_title_and_price(self):
        offers = extract_offers(
            "Creatina Growth R$ 49,90 https://www.mercadolivre.com.br/x/p/MLB19603205"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "Creatina Growth")
        self.assertEqual(offers[0].price, "R$ 49,90")
        self.assertIsNone(offers[0].installment_info)
        self.assertIsNone(offers[0].shipping_info)
        self.assertIsNone(offers[0].coupon)
        self.assertFalse(offers[0].meli_plus_only)
        self.assertEqual(offers[0].url, "https://www.mercadolivre.com.br/x/p/MLB19603205")

    def test_extracts_amazon_offer_title_and_price(self):
        offers = extract_offers(
            "iPhone 16 256 GB R$ 5.999 https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "iPhone 16 256 GB")
        self.assertEqual(offers[0].price, "R$ 5.999")
        self.assertEqual(offers[0].url, "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")

    def test_extracts_shopee_offer_title_and_price(self):
        offers = extract_offers(
            "Liquidificador portátil Mondial R$ 89,90 https://s.shopee.com.br/LjpppnYGZ"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "Liquidificador portátil Mondial")
        self.assertEqual(offers[0].price, "R$ 89,90")
        self.assertEqual(offers[0].url, "https://s.shopee.com.br/LjpppnYGZ")

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

    def test_ignores_conversational_copy_when_product_title_exists(self):
        offers = extract_offers(
            "Roupas Pet Outono Inverno Roupas Roupas Pet Outono Inverno Roupas Pet Para Cachorro E Gato\n\nCuide também dos seus amiguinhos de 4 patas🐾 !\n\nPOR R$ 29,90\n\nCusta R$ 45,90\n\nCOMPRE AQUI:\nhttps://meli.la/2XDwu59\n\nO que você achou dessa oferta?  👍❤️😳🥲😱🫠"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            offers[0].title,
            "Roupas Pet Outono Inverno Roupas Roupas Pet Outono Inverno Roupas Pet Para Cachorro E Gato",
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

    def test_prefers_real_coupon_code_over_status_line(self):
        offers = extract_offers(
            "CUPOM ESGOTANDOO\n\n"
            "iPhone 17e 256gb Preto\n"
            "Mercado Livre\n\n"
            "De: R$ 5.799,00\n"
            "🔥Por: R$ 4.453,90\n\n"
            "🎟 Use o cupom: RONALDO10\n\n"
            "Link: https://meli.la/2oN3Kne"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].coupon, "RONALDO10")

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

    def test_extracts_pix_price_installments_and_free_shipping(self):
        offers = extract_offers(
            "CELULAR DO BRUCE BANNER\n\n✅ Smartphone Motorola Moto g35 5G - 128GB 12GB (4GB RAM+8GB Ram Boost) e Camera 50MP com AI NFC Tela 6.7\" com Superbrilho - Verde - Vegan Leather\n\nDE R$ 1.327,14\n🔥POR R$ 844,90 🔥 no PIX\n\nparcelado em 10x sem juros\nFRETE GRÁTIS PARA SUL E SUDESTE\n\n🔗 https://meli.la/2jLohD3\nSelecione a Loja Oficial Motorola\n\n*anúncio"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 844,90 no PIX")
        self.assertEqual(offers[0].installment_info, "10X SEM JUROS")
        self.assertEqual(offers[0].shipping_info, "FRETE GRÁTIS PARA SUL E SUDESTE")

    def test_extracts_pix_price_without_installments_or_shipping(self):
        offers = extract_offers(
            "Console Portátil Retro\n\nDE R$ 399,90\nPOR R$ 259,90 no PIX\n\nhttps://meli.la/2jLohD3"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 259,90 no PIX")
        self.assertIsNone(offers[0].installment_info)
        self.assertIsNone(offers[0].shipping_info)

    def test_extracts_free_shipping_without_pix_or_installments(self):
        offers = extract_offers(
            "Mochila Escolar Reforçada\n\nR$ 89,90\nFRETE GRÁTIS\n\nhttps://meli.la/2jLohD3"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 89,90")
        self.assertIsNone(offers[0].installment_info)
        self.assertEqual(offers[0].shipping_info, "FRETE GRÁTIS")

    def test_format_offer_shows_installments_pix_and_shipping(self):
        offer = extract_offers(
            "✅ Smartphone Motorola Moto g35 5G - 128GB 12GB (4GB RAM+8GB Ram Boost) e Camera 50MP com AI NFC Tela 6.7\" com Superbrilho - Verde - Vegan Leather\n\nDE R$ 1.327,14\n🔥POR R$ 844,90 🔥 no PIX\n\n10x sem juros\nFRETE GRÁTIS\n\nhttps://meli.la/2jLohD3"
        )[0]

        formatted = format_offer(offer, "https://meli.la/final123")

        self.assertIn("🛍️ [10X SEM JUROS] Smartphone Motorola Moto g35 5G", formatted)
        self.assertIn("💰 R$ 844,90 no PIX\nFRETE GRÁTIS", formatted)

    def test_ignores_non_supported_urls(self):
        self.assertEqual(extract_offers("Oferta https://example.com/item"), [])

    def test_formats_amazon_coupon_message_pattern(self):
        text = (
            "☑️ Novo Cupom Amazon!\n\n"
            "▪️ 10% OFF em compras acima de R$200, Limitado a R$50\n\n"
            "🎯 Usem o cupom: SUPER10OFF\n\n"
            "🛒 Resgate nesse produto: https://amzn.to/4wh62jk"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://amzn.to/affiliate123")

        self.assertEqual(
            formatted,
            "☑️ Cupom Amazon!\n\n"
            "🎟 10% OFF em compras acima de R$ 200, Limitado a R$ 50: SUPER10OFF\n\n"
            "🛒 Resgate aqui: https://amzn.to/affiliate123",
        )

    def test_formats_amazon_coupon_with_codigo_and_ative_aqui(self):
        text = (
            "🔵 Cupom Amazon\n\n"
            "10% OFF acima de R$200 limite R$50\n\n"
            "🎟️ Código:  SUPER10OFF\n\n"
            "✅ Ative Aqui:\n"
            "https://www.amazon.com.br/dp/B0CQMT33WX/ref=cm_sw_r_as_gl_apa_gl_i_dl_S3M6VSFKXRHPMX3KKKBH?tag=milyoficial-20"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://amzn.to/affiliate123")

        self.assertEqual(
            formatted,
            "☑️ Cupom Amazon!\n\n"
            "🎟 10% OFF acima de R$ 200 limite R$ 50: SUPER10OFF\n\n"
            "🛒 Resgate aqui: https://amzn.to/affiliate123",
        )

    def test_formats_mercado_livre_multi_coupon_bulletin(self):
        text = (
            "🔥 Cupons Mercado Livre\n\n"
            "🎟 12% OFF acima de R$79, limite R$60: CUPOMDOML\n"
            "🎟 12% OFF acima de R$79, limite R$50: OFFDOZE\n\n"
            "✅ Resgate aqui:\n"
            "https://meli.la/2KJ1Ghn"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://meli.la/affiliate123")

        self.assertEqual(
            formatted,
            "🔥 Cupons Mercado Livre!\n\n"
            "🎟 12% OFF acima de R$ 79, limite R$ 60: CUPOMDOML\n"
            "🎟 12% OFF acima de R$ 79, limite R$ 50: OFFDOZE\n\n"
            "🛒 Resgate aqui: https://meli.la/affiliate123",
        )

    def test_format_offer_shows_resgate_cupom_no_anuncio_note(self):
        offer = extract_offers(
            "Micro-ondas 35L Branco MasterCook Midea 220V\n\n"
            "R$ 355\n"
            "-Resgate cupom do anúncio\n\n"
            "https://www.amazon.com.br/dp/B0FGZGY6VG?tag=promotom05-20\n\n"
            "-Anúncio"
        )[0]

        formatted = format_offer(offer, "https://amzn.to/affiliate123")

        self.assertIn("🏷️ Resgate cupom do anúncio", formatted)

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

    def test_extract_shopee_ids_from_product_url(self):
        self.assertEqual(
            extract_shopee_ids(
                "https://shopee.com.br/Liquidificador-portatil-i.1499852820.22199186045?x=1"
            ),
            ("1499852820", "22199186045"),
        )


if __name__ == "__main__":
    unittest.main()
