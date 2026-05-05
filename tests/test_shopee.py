import unittest

import httpx

from offers_bot.shopee import ShopeeClient


class ShopeeClientTest(unittest.TestCase):
    def test_create_link_resolves_short_url_and_uses_browser_flow(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "s.shopee.com.br":
                return httpx.Response(
                    302,
                    headers={
                        "location": "https://shopee.com.br/Liquidificador-portatil-i.1499852820.22199186045"
                    },
                    request=request,
                )
            return httpx.Response(200, text="ok", request=request)

        class TestShopeeClient(ShopeeClient):
            def __init__(self) -> None:
                super().__init__(
                    cookie_header="SPC_F=abc",
                    csrf_token="csrf",
                    af_ac_enc_dat="enc-dat",
                    af_ac_enc_sz_token="enc-sz",
                    x_sap_ri="sap-ri",
                    x_sap_sec="sap-sec",
                    resolver_client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
                )
                self.seen_item_id = None

            def _fetch_offer_link_via_browser(self, item_id: str) -> str:
                self.seen_item_id = item_id
                return "https://s.shopee.com.br/2LUuD6CVXp"

        client = TestShopeeClient()

        link = client.create_link("https://s.shopee.com.br/LjpppnYGZ")

        self.assertEqual(client.seen_item_id, "22199186045")
        self.assertEqual(link.short_url, "https://s.shopee.com.br/2LUuD6CVXp")
        self.assertEqual(
            link.long_url,
            "https://shopee.com.br/Liquidificador-portatil-i.1499852820.22199186045",
        )
        self.assertEqual(link.product_key, "SHOPEE:1499852820:22199186045")

    def test_create_link_raises_when_final_url_has_no_ids(self):
        client = ShopeeClient(
            cookie_header="SPC_F=abc",
            csrf_token="csrf",
            af_ac_enc_dat="enc-dat",
            af_ac_enc_sz_token="enc-sz",
            x_sap_ri="sap-ri",
            x_sap_sec="sap-sec",
            resolver_client=httpx.Client(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, text="ok", request=request)),
                follow_redirects=True,
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "Could not find Shopee shop/item ids"):
            client.create_link("https://s.shopee.com.br/LjpppnYGZ")

    def test_build_offer_page_url(self):
        self.assertEqual(
            ShopeeClient._build_offer_page_url("13639006300"),
            "https://affiliate.shopee.com.br/offer/product_offer/13639006300",
        )


if __name__ == "__main__":
    unittest.main()
