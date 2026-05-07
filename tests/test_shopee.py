import unittest
import httpx
from offers_bot.shopee import ShopeeClient


class ShopeeClientTest(unittest.TestCase):
    def test_create_link_uses_api(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "s.shopee.com.br":
                return httpx.Response(
                    302,
                    headers={
                        "location": "https://shopee.com.br/Liquidificador-portatil-i.1499852820.22199186045"
                    },
                    request=request,
                )
            if request.url.host == "open-api.affiliate.shopee.com.br":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "generateShortLink": {
                                "shortLink": "https://s.shopee.com.br/2LUuD6CVXp"
                            }
                        }
                    },
                    request=request,
                )
            return httpx.Response(200, text="ok", request=request)

        client = ShopeeClient(
            app_id="123456",
            app_secret="demo",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            resolver_client=httpx.Client(
                transport=httpx.MockTransport(handler), follow_redirects=True
            ),
        )

        link = client.create_link("https://s.shopee.com.br/LjpppnYGZ")

        self.assertEqual(link.short_url, "https://s.shopee.com.br/2LUuD6CVXp")
        self.assertEqual(
            link.long_url,
            "https://shopee.com.br/Liquidificador-portatil-i.1499852820.22199186045",
        )
        self.assertEqual(link.product_key, "SHOPEE:1499852820:22199186045")

    def test_create_link_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "open-api.affiliate.shopee.com.br":
                return httpx.Response(
                    200,
                    json={
                        "errors": [{"message": "Invalid application", "code": 10020}]
                    },
                    request=request,
                )
            return httpx.Response(200, text="ok", request=request)

        client = ShopeeClient(
            app_id="123456",
            app_secret="demo",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

        with self.assertRaisesRegex(RuntimeError, "Shopee API error"):
            client.create_link("https://shopee.com.br/product-i.1.2")


if __name__ == "__main__":
    unittest.main()
