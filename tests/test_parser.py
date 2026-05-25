import unittest

from offers_bot.main import format_offer, format_outgoing_offer
from offers_bot.parser import Offer, extract_ml_ids, extract_offers, extract_shopee_ids


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
        self.assertEqual(
            offers[0].url, "https://www.mercadolivre.com.br/x/p/MLB19603205"
        )

    def test_extracts_amazon_offer_title_and_price(self):
        offers = extract_offers(
            "iPhone 16 256 GB R$ 5.999 https://www.amazon.com.br/dp/B0DXR6MKR8?tag=exampletag-20"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].title, "iPhone 16 256 GB")
        self.assertEqual(offers[0].price, "R$ 5.999")
        self.assertEqual(
            offers[0].url, "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=exampletag-20"
        )

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

        self.assertIn("🎟️ CUPOM: `10MELIMAIS` ou `MELIMAISPROMO`", formatted)
        self.assertIn("⭐ Exclusivo para clientes Meli+", formatted)

    def test_prefers_price_after_por_when_original_price_exists(self):
        offers = extract_offers(
            "🔥 Filtro De Linha iClamper Energia 8 | DPS | 8 Tomadas | Bivolt\n\n✅ De R$ 188 → Por R$ 116\n🔻 38% OFF\n🛒 https://meli.la/2ELDuyN"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 116")

    def test_prefers_por_price_with_colon_and_emoji_over_de_price(self):
        offers = extract_offers(
            "🛍️ Jarra De Vidro Com Tampa De Bambu Para Servir Suco Água 1200ml Hermética Garrafa\n\nDe: R$ 69,25\n💥Por: R$ 36,70\n\n🛒 Compre aqui 👉🏻 https://s.shopee.com.br/5VRzNIezJW"
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            offers[0].title,
            "Jarra De Vidro Com Tampa De Bambu Para Servir Suco Água 1200ml Hermética Garrafa",
        )
        self.assertEqual(offers[0].price, "R$ 36,70")
        self.assertEqual(offers[0].url, "https://s.shopee.com.br/5VRzNIezJW")

    def test_extracts_pix_price_installments_and_free_shipping(self):
        offers = extract_offers(
            'CELULAR DO BRUCE BANNER\n\n✅ Smartphone Motorola Moto g35 5G - 128GB 12GB (4GB RAM+8GB Ram Boost) e Camera 50MP com AI NFC Tela 6.7" com Superbrilho - Verde - Vegan Leather\n\nDE R$ 1.327,14\n🔥POR R$ 844,90 🔥 no PIX\n\nparcelado em 10x sem juros\nFRETE GRÁTIS PARA SUL E SUDESTE\n\n🔗 https://meli.la/2jLohD3\nSelecione a Loja Oficial Motorola\n\n*anúncio'
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
            '✅ Smartphone Motorola Moto g35 5G - 128GB 12GB (4GB RAM+8GB Ram Boost) e Camera 50MP com AI NFC Tela 6.7" com Superbrilho - Verde - Vegan Leather\n\nDE R$ 1.327,14\n🔥POR R$ 844,90 🔥 no PIX\n\n10x sem juros\nFRETE GRÁTIS\n\nhttps://meli.la/2jLohD3'
        )[0]

        formatted = format_offer(offer, "https://meli.la/final123")

        self.assertIn("[10X SEM JUROS] Smartphone Motorola Moto g35 5G", formatted)
        self.assertIn("💰 R$ 844,90 no PIX\nFRETE GRÁTIS", formatted)

    def test_resgate_anuncio_note_appears_and_no_fake_coupon(self):
        text = """🔥 Processador Amd Ryzen 5 5600GT

✅ Por R$ 913
🎟️ Resgate o cupom no anúncio do produto
🛒 https://meli.la/2Pc3tDW"""
        offer = extract_offers(text)[0]

        self.assertIsNone(offer.coupon)

        formatted = format_offer(offer, "https://meli.la/final123")
        self.assertIn("🏷️ Resgate o cupom no anúncio", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_ignores_non_supported_urls(self):
        self.assertEqual(extract_offers("Oferta https://example.com/item"), [])

    def test_formats_amazon_coupon_message_pattern(self):
        text = (
            "☑️ Novo Cupom Amazon!\n\n"
            "▪️ 10% OFF em compras abra de R$200, Limitado a R$50\n\n"
            "🎯 Usem o cupom: SUPER10OFF\n\n"
            "🛒 Resgate nesse produto: https://amzn.to/4wh62jk"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://amzn.to/affiliate123")

        self.assertEqual(
            formatted,
            "☑️ Cupom Amazon!\n\n"
            "🎟 10% OFF em compras abra de R$ 200, Limitado a R$ 50: `SUPER10OFF`\n\n"
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
            "🎟 10% OFF acima de R$ 200 limite R$ 50: `SUPER10OFF`\n\n"
            "🛒 Resgate aqui: https://amzn.to/affiliate123",
        )

    def test_formats_novo_cupom_mercado_livre(self):
        text = (
            "🔥 Novo Cupom Mercado Livre em produtos ELECTROLUX!\n\n"
            "▪️ 15% OFF em compras acima de R$199, Limitado a R$2.000\n\n"
            "🎯 Usem o cupom: ELUX15OFF\n\n"
            "🛒 https://meli.la/1GwL6Yt\n\n"
            '⚠️ Clique em "Mostrar mais" para ver a lista completa.'
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://meli.la/affiliate123")

        self.assertEqual(
            formatted,
            "🤑 15% OFF em compras acima de R$199, Limitado a R$2.000\n\n"
            "🎟️ Cupom: `ELUX15OFF`\n\n"
            "🔗 https://meli.la/affiliate123",
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
            "🎟 12% OFF acima de R$ 79, limite R$ 60: `CUPOMDOML`\n"
            "🎟 12% OFF acima de R$ 79, limite R$ 50: `OFFDOZE`\n\n"
            "🛒 Resgate aqui: https://meli.la/affiliate123",
        )

    def test_formats_generic_coupon_bulletin_without_header(self):
        text = (
            "🔥 15% OFF em produtos selecionados!\n\n"
            "Use o cupom: GERAL15\n\n"
            "https://meli.la/abc1234"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://meli.la/aff123")

        self.assertEqual(
            formatted,
            "15% OFF em produtos selecionados!\n\n"
            "🎟️ Cupom: `GERAL15`\n\n"
            "🔗 https://meli.la/aff123",
        )

    def test_product_with_coupon_not_mistaken_for_bulletin(self):
        text = (
            "Notebook Gamer Lenovo LOQ 15IRX9\n\n"
            "R$ 4.999\n\n"
            "Cupom: EXTRA5\n\n"
            "https://meli.la/xyz5678"
        )
        offer = extract_offers(text)[0]

        formatted = format_offer(offer, "https://meli.la/aff456")

        self.assertIn("CUPOM: `EXTRA5`", formatted)
        self.assertNotIn("🎟️ Cupom:", formatted)

    # --- 9 sample patterns from user ---

    def test_sample1_amazon_app_hojetem(self):
        text = (
            "🚨 Cupom Amazon APP\n\n"
            "🎟 R$100 OFF em R$999: HOJETEM\n\n"
            "✅ Resgate aqui:\n"
            "https://amzn.to/3OmdZT1"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://amzn.to/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("☑️ Cupom Amazon!", formatted)
        self.assertIn("HOJETEM", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_sample2_amazon_plain_hojetem(self):
        text = (
            "Cupom Amazon\n\n"
            "R$ 100 OFF em R$ 999: HOJETEM\n\n"
            "-Resgate o cupom aqui: https://amzn.to/4ljRg64"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://amzn.to/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("☑️ Cupom Amazon!", formatted)
        self.assertIn("HOJETEM", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_sample3_amazon_cupom_hojetem(self):
        text = (
            "🔵 Cupom Amazon\n\n"
            "R$ 100 OFF acima de R$ 999\n\n"
            "🎟️ Cupom: HOJETEM\n\n"
            "✅ Ative Aqui:\n"
            "https://www.amazon.com.br/dp/B0CQMT33WX?tag=milyoficial-20"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://amzn.to/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("☑️ Cupom Amazon!", formatted)
        self.assertIn("HOJETEM", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_sample4_amazon_app2_hojetem(self):
        text = (
            "🔥 Cupom Amazon no APP\n\n"
            "🎟 R$ 100 OFF em R$ 999: HOJETEM\n\n"
            "✅ Resgate aqui:\n"
            "https://www.amazon.com.br/dp/B0CYW2N6TX?tag=anaporto-20"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://amzn.to/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("☑️ Cupom Amazon!", formatted)
        self.assertIn("HOJETEM", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_sample5_shopee_no_coupon_code(self):
        text = (
            "🔥 Cupons Shopee\n\n"
            "🎟 R$ 35 OFF em R$ 299 (Válido para produtos Full)\n"
            "https://s.shopee.com.br/4LG2NNghN4\n\n"
            "✅ Cupons Fidelidade no APP\n"
            '-Resgate em "Confira seu nível":\n'
            "https://s.shopee.com.br/2qREachwMz"
        )
        offers = extract_offers(text)
        self.assertEqual(len(offers), 2)
        for i, o in enumerate(offers):
            formatted = format_offer(o, f"https://s.shopee.com.br/aff{i}")
            print(f"\n--- {self._testMethodName} (offer {i + 1}) ---\n{formatted}")
            self.assertIsNone(o.coupon)

    def test_shopee_resgate_and_product_links_become_one_offer(self):
        text = (
            "🔥 Cupom Shopee\n\n"
            "✅ Resgate aqui: https://s.shopee.com.br/resgate123\n\n"
            "🛒 Produto: https://shopee.com.br/product/412968566/58207918412"
        )

        offers = extract_offers(text)

        self.assertEqual(len(offers), 1)
        self.assertEqual(
            offers[0].url, "https://shopee.com.br/product/412968566/58207918412"
        )

    def test_shopee_resgate_output_preserves_original_message_formatting(self):
        text = (
            "🔥 Cupom Shopee\n\n"
            "✅ Resgate aqui: https://s.shopee.com.br/resgate123\n\n"
            "🛒 Produto: https://shopee.com.br/product/412968566/58207918412\n\n"
            "- Anúncio"
        )
        offer = extract_offers(text)[0]

        formatted = format_outgoing_offer(offer, "https://s.shopee.com.br/aff123")

        self.assertEqual(
            formatted,
            "🔥 Cupom Shopee\n\n"
            "✅ Resgate aqui: https://s.shopee.com.br/resgate123\n\n"
            "🛒 Produto: https://s.shopee.com.br/aff123\n\n"
            "- Anúncio",
        )

    def test_shopee_single_resgate_link_preserves_original_message_formatting(self):
        text = (
            "🔥 CUPONS SHOPEE\n\n"
            "👀 Cupom de Frete Grátis\n\n"
            "📱 APENAS PELO APLICATIVO\n\n"
            "Resgate na Sacola no canto esquerdo (SACOLA LARANJA) dentro da live no APP.\n\n"
            "🎯 Resgate aqui:\n"
            "https://s.shopee.com.br/5pz2uDWQuz"
        )
        offer = extract_offers(text)[0]

        formatted = format_outgoing_offer(offer, "https://s.shopee.com.br/9fHg7A8YKd")

        self.assertEqual(
            formatted,
            "🔥 CUPONS SHOPEE\n\n"
            "👀 Cupom de Frete Grátis\n\n"
            "📱 APENAS PELO APLICATIVO\n\n"
            "Resgate na Sacola no canto esquerdo (SACOLA LARANJA) dentro da live no APP.\n\n"
            "🎯 Resgate aqui:\n"
            "https://s.shopee.com.br/9fHg7A8YKd\n\n"
            "- Anúncio",
        )

    def test_shopee_resgate_and_cart_links_preserve_original_message_formatting(self):
        text = (
            "☑️ Cupom Shopee - Acessórios para veículos!!!\n"
            " \n"
            "R$30 OFF nas compras acima de R$119\n\n"
            "🎯 Usem o Cupom: AUTOS30G4AF\n\n"
            "🛒 Resgate aqui: https://s.shopee.com.br/LXc7aGHOO\n\n"
            "🛒 Link do Carrinho: https://s.shopee.com.br/2AzGIy4Uqa"
        )
        offers = extract_offers(text)
        offer = offers[0]

        self.assertEqual(len(offers), 1)
        self.assertEqual(offer.coupon, "AUTOS30G4AF")
        self.assertEqual(offer.url, "https://s.shopee.com.br/2AzGIy4Uqa")
        formatted = format_outgoing_offer(offer, "https://s.shopee.com.br/aff1")

        self.assertEqual(
            formatted,
            "☑️ Cupom Shopee - Acessórios para veículos!!!\n"
            " \n"
            "R$30 OFF nas compras acima de R$119\n\n"
            "🎯 Usem o Cupom: `AUTOS30G4AF`\n\n"
            "🛒 Resgate aqui: https://s.shopee.com.br/LXc7aGHOO\n\n"
            "🛒 Link do Carrinho: https://s.shopee.com.br/aff1\n\n"
            "- Anúncio",
        )
        self.assertNotIn("https://s.shopee.com.br/2AzGIy4Uqa", formatted)

    def test_shopee_resgate_and_short_product_link_become_one_offer(self):
        text = (
            'Monitor Gamer Acer LED IPS 23,8" Full HD HDMI VGA MK241Y - Preto -\n\n'
            "R$ 405\n"
            "-Resgate todos os cupons na Live (sacola laranja) no APP aqui:\n"
            "https://s.shopee.com.br/4qCQiaA0eB\n\n"
            "-Link produto:\n"
            "https://s.shopee.com.br/30kmXDH3d2\n\n"
            "-Anúncio"
        )

        offers = extract_offers(text)

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].url, "https://s.shopee.com.br/30kmXDH3d2")

    def test_shopee_resgate_output_strips_anuncio_variants(self):
        text = (
            "Oferta Shopee\n\n"
            "-Resgate aqui:\n"
            "https://s.shopee.com.br/resgate123\n\n"
            "-Link produto:\n"
            "https://s.shopee.com.br/prod123\n\n"
            "-Anúncio"
        )
        offer = extract_offers(text)[0]

        formatted = format_outgoing_offer(offer, "https://s.shopee.com.br/aff123")

        self.assertEqual(formatted.count("Anúncio"), 1)
        self.assertTrue(formatted.endswith("- Anúncio"))

    def test_sample6_amazon_multilist(self):
        text = (
            "⚠️ LISTA DE CUPONS AMAZON\n"
            "------------------------------------------------------\n"
            "🤑 R$300 OFF EM SMARTPHONES\n"
            "🎟️ CUPOM: SMART300\n"
            "🔗https://amzn.to/4uDivfA\n\n"
            "🤑 20%OFF EM ITENS SELECIONADOS\n"
            "🎟️ CUPOM: LEVE20\n"
            "🔗https://amzn.to/4eyex32\n\n"
            "🤑 10%OFF EM ESQUENTA CONSUMIDOR\n"
            "🎟️ CUPOM: CONSUMI10\n"
            "🔗https://amzn.to/4d0u3SA\n\n"
            "🤑 R$100 OFF EM SMARTPHONES\n"
            "🔗https://amzn.to/42g9jBB\n\n"
            "🤑 COMPRE 3 E GANHE 25% DE DESCONTO\n"
            "🔗https://amzn.to/3PdDFBA\n\n"
            "🤑 10%OFF SELEÇÃO DE ITENS\n"
            "🎟️ CUPOM: LEVE10OFF\n"
            "🔗https://amzn.to/4naaWdu\n\n"
            "🤑 15%OFF EM DIVERSIDADES PARA CASA\n"
            "🎟️ CUPOM: CASA15\n"
            "🔗https://amzn.to/4neobdj\n\n"
            "🤑 10%OFF EM SELECIONADOS\n"
            "🎟️ CUPOM: TOMA10\n"
            "🔗https://amzn.to/49nNNP9"
        )
        offers = extract_offers(text)
        self.assertEqual(len(offers), 8)
        formatted = format_offer(offers[0], "https://amzn.to/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("☑️ Cupom Amazon!", formatted)
        self.assertIn("SMART300", formatted)
        self.assertIn("LEVE20", formatted)
        self.assertIn("CONSUMI10", formatted)
        self.assertIn("LEVE10OFF", formatted)
        self.assertIn("CASA15", formatted)
        self.assertIn("TOMA10", formatted)

    def test_sample7_aliexpress_multicoupon(self):
        text = (
            "Cupons EXCLUSIVOS Aliexpress DIA DAS MÃES 2026\n\n"
            "Página 1: https://s.click.aliexpress.com/e/_c3ErZnNh\n\n"
            "A promoção ACABA hoje\n\n"
            "Cupons:\n\n"
            "R$ 11 off acima de R$ 86: IFPDAB9R\n"
            "R$ 23 off acima de R$ 172: IFPBTUME\n"
            "R$ 35 off acima de R$260: IFP7D0MS\n"
            "R$ 69 off acima de R$ 511: IFPMEIRL\n"
            "R$ 95 off acima de R$ 800: IFPMEIRL\n"
            "R$ 144 off acima de R$ 1.200: IFPAF7UN"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://s.click.aliexpress.com/e/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("IFPDAB9R", formatted)
        self.assertIn("IFPBTUME", formatted)
        self.assertIn("IFP7D0MS", formatted)
        self.assertIn("IFPMEIRL", formatted)
        self.assertIn("IFPAF7UN", formatted)
        self.assertNotIn("CUPOM:", formatted)
        self.assertNotIn("EXCLUSIVOS", formatted)

    def test_sample8_ml_visa_maesbbvisa(self):
        text = (
            "🔥 Cupom Mercado Livre Visa\n\n"
            "🎟️ R$ 40 OFF em R$ 400: MAESBBVISA\n\n"
            "Nossa lista de sugestões:\n"
            "https://mercadolivre.com/sec/1N9WRdF\n\n"
            "Produtos mais vendidos (clique em mostrar mais):\n"
            "https://meli.la/1QaQhxF"
        )
        offers = extract_offers(text)
        self.assertEqual(len(offers), 1)
        formatted = format_offer(offers[0], "https://meli.la/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("🔥 Cupons Mercado Livre!", formatted)
        self.assertIn("MAESBBVISA", formatted)
        self.assertNotIn("CUPOM:", formatted)

    def test_sample9_novo_ml_recebidospago(self):
        text = (
            "🚨 NOVO CUPOM MERCADO LIVRE\n\n"
            "🎟️ Cupom: RECEBIDOSPAGO\n"
            "12% OFF em compras, limite de R$ 60 de desconto\n\n"
            'Acesse o link, procure o(s) produto(s) desejado(s) e ative o cupom na tela de pagamento clicando em "cupons"\n\n'
            "🔗 https://meli.la/2qsgG2b\n\n"
            "*anúncio"
        )
        offer = extract_offers(text)[0]
        formatted = format_offer(offer, "https://meli.la/aff123")

        print(f"\n--- {self._testMethodName} ---\n{formatted}")
        self.assertIn("12% OFF em compras", formatted)
        self.assertIn("🎟️ Cupom: `RECEBIDOSPAGO`", formatted)
        self.assertIn("🔗 https://meli.la/aff123", formatted)
        self.assertNotIn("*anúncio", formatted)

    def test_aliexpress_multi_link_grouping(self):
        text = (
            "⚡ Teclado Mecânico Akko x Veekos 5075S/K75\n\n"
            "💰 R$ 231 em 3x sem juros\n"
            "🏷 Cupom: IFPQCADG\n\n"
            "Link App: https://a.aliexpress.com/_c384gu15\n"
            "Link PC: https://a.aliexpress.com/_c3lx2IcT\n\n"
            "(anuncio)"
        )
        offers = extract_offers(text)
        self.assertEqual(len(offers), 1)
        self.assertEqual(len(offers[0].all_urls), 2)
        self.assertIn("https://a.aliexpress.com/_c384gu15", offers[0].all_urls)
        self.assertIn("https://a.aliexpress.com/_c3lx2IcT", offers[0].all_urls)

    def test_anuncio_suffix_appended_to_all_messages(self):
        offer = extract_offers(
            "Creatina Growth R$ 49,90 https://www.mercadolivre.com.br/x/p/MLB19603205"
        )[0]
        formatted = format_offer(offer, "https://meli.la/123")
        final = formatted + "\n\n- Anúncio"
        self.assertTrue(final.endswith("- Anúncio"))

    def test_format_offer_shows_resgate_cupom_no_anuncio_note(self):
        offer = extract_offers(
            "Micro-ondas 35L Branco MasterCook Midea 220V\n\n"
            "R$ 355\n"
            "-Resgate cupom do anúncio\n\n"
            "https://www.amazon.com.br/dp/B0FGZGY6VG?tag=exampletag-20\n\n"
            "-Anúncio"
        )[0]

        formatted = format_offer(offer, "https://amzn.to/affiliate123")

        self.assertIn("🏷️ Resgate cupom do anúncio", formatted)

    def test_extracts_pix_and_card_prices(self):
        text = (
            '📺 86" 4K\n\n'
            "Smart Tv Philips 86 4k 86pug7019 Comando De Voz Playstore\n\n"
            "🔥 Por: R$ 5.921,06 via Pix\n"
            "🔥 Por: R$ 6.299,00 parcelado\n\n"
            "🎯 Usem o cupom: TVCASASBAHIA\n"
            "🛒 https://meli.la/1Z7GBcN"
        )
        offers = extract_offers(text)

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, "R$ 5.921,06 no PIX")
        self.assertEqual(offers[0].card_price, "R$ 6.299,00 no cartão")
        self.assertEqual(offers[0].coupon, "TVCASASBAHIA")

    def test_format_offer_shows_card_price(self):
        offer = extract_offers(
            "Product\n"
            "🔥 Por: R$ 100 via Pix\n"
            "🔥 Por: R$ 110 no cartão\n"
            "https://meli.la/123"
        )[0]

        formatted = format_offer(offer, "https://meli.la/aff")

        self.assertIn("💰 R$ 100 no PIX", formatted)
        self.assertIn("💳 R$ 110 no cartão", formatted)

    def test_trims_meli_short_url_before_appended_noise(self):
        offers = extract_offers(
            "Oferta https://meli.la/1vMs9xn167.51:443/TcpFull complete!"
        )

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

    def test_extract_shopee_ids_from_opaanlp_url(self):
        self.assertEqual(
            extract_shopee_ids(
                "https://shopee.com.br/opaanlp/1231924500/22998179385?__mobile__=1"
            ),
            ("1231924500", "22998179385"),
        )

    def test_extract_shopee_ids_from_product_slash_url(self):
        self.assertEqual(
            extract_shopee_ids(
                "https://shopee.com.br/product/412968566/58207918412?credential_token=abc&exp_group=rollout"
            ),
            ("412968566", "58207918412"),
        )

    def test_original_links_not_in_formatted_output(self):
        text = """Mesa L De Canto Para Estudo Retro Design Nórdico Mod: Pier https://other.com/badtitle

R$ 109
-CUPOM: OFFMELI

https://meli.la/2RNUWDH
https://meli.la/1zx1PDb
https://meli.la/1k61SVq

-Anúncio

-Dica NEGRETYH"""
        offers = extract_offers(text)
        self.assertEqual(len(offers), 3)

        for i, offer in enumerate(offers):
            affiliate_url = f"https://meli.la/generated{i}"
            formatted = format_offer(offer, affiliate_url)

            # Original links should NOT be in the formatted output
            self.assertNotIn("https://meli.la/2RNUWDH", formatted)
            self.assertNotIn("https://meli.la/1zx1PDb", formatted)
            self.assertNotIn("https://meli.la/1k61SVq", formatted)
            self.assertNotIn("https://other.com/badtitle", formatted)

            # Generated link SHOULD be in the formatted output
            self.assertIn(affiliate_url, formatted)

    def test_ml_coupon_header_without_code_omits_cupom_line(self):
        text = (
            "🔥 Cupom Mercado Livre\n\n"
            "🎟️40% OFF em Smart Home\n\n"
            "Nossa lista de sugestões:\n"
            "https://meli.la/1uDk4iS\n\n"
            "Produtos mais vendidos (clique em mostrar mais):\n"
            "https://meli.la/2k2Scmy"
        )
        offers = extract_offers(text)
        self.assertEqual(len(offers), 2)
        for offer in offers:
            formatted = format_offer(offer, "https://meli.la/aff123")
            self.assertNotIn("🎟️ Cupom:", formatted)
            self.assertNotIn("🤑", formatted)

    def test_llm_novo_ml_coupon_without_code_falls_back(self):
        offer = Offer(
            original_text=(
                "🔥 Cupom Mercado Livre\n\n"
                "🎟️40% OFF em Smart Home\n\n"
                "Nossa lista de sugestões:\n"
                "https://meli.la/1uDk4iS"
            ),
            url="https://meli.la/1uDk4iS",
            title="40% OFF em Smart Home",
            price=None,
            card_price=None,
            installment_info=None,
            shipping_info=None,
            coupon=None,
            meli_plus_only=False,
            llm_result={
                "classification": "coupon",
                "coupon": {
                    "platform": "Mercado Livre",
                    "novo_ml_format": True,
                    "coupons": [],
                },
            },
        )
        formatted = format_offer(offer, "https://meli.la/aff123")
        self.assertNotIn("🎟️ Cupom:", formatted)
        self.assertNotIn("🤑", formatted)

    def test_llm_novo_ml_coupon_detail_without_code_falls_back(self):
        offer = Offer(
            original_text=(
                "🔥 Cupom Mercado Livre\n\n"
                "🎟️40% OFF em Smart Home\n\n"
                "https://meli.la/1uDk4iS"
            ),
            url="https://meli.la/1uDk4iS",
            title="40% OFF em Smart Home",
            price=None,
            card_price=None,
            installment_info=None,
            shipping_info=None,
            coupon=None,
            meli_plus_only=False,
            llm_result={
                "classification": "coupon",
                "coupon": {
                    "platform": "Mercado Livre",
                    "novo_ml_format": True,
                    "coupons": [{"detail": "40% OFF em Smart Home", "code": ""}],
                },
            },
        )
        formatted = format_offer(offer, "https://meli.la/aff123")
        self.assertNotIn("🎟️ Cupom:", formatted)
        self.assertNotIn("🤑", formatted)

    def test_llm_generic_coupon_without_code_falls_back(self):
        offer = Offer(
            original_text="🔥 15% OFF em produtos selecionados!\n\nhttps://meli.la/abc1234",
            url="https://meli.la/abc1234",
            title="15% OFF em produtos selecionados!",
            price=None,
            card_price=None,
            installment_info=None,
            shipping_info=None,
            coupon=None,
            meli_plus_only=False,
            llm_result={
                "classification": "coupon",
                "coupon": {
                    "platform": "Generic",
                    "novo_ml_format": False,
                    "generic_format": True,
                    "coupons": [
                        {"detail": "15% OFF em produtos selecionados!", "code": ""}
                    ],
                },
            },
        )
        formatted = format_offer(offer, "https://meli.la/aff123")
        self.assertNotIn("🎟️ Cupom:", formatted)


if __name__ == "__main__":
    unittest.main()
