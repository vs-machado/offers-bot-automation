import json
import unittest

import httpx

from offers_bot.mercado_livre import MercadoLivreClient, UnsupportedOfferError


class MercadoLivreClientTest(unittest.TestCase):
    def test_create_link_uses_task_context_payload_shape(self):
        seen_payloads = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                html = "catalog MLB19603205 listing MLB5872060016"
                return httpx.Response(200, text=html, request=request)

            payload = json.loads(request.content.decode())
            seen_payloads.append(payload)
            self.assertEqual(request.headers["cookie"], "ssid=abc")
            self.assertEqual(request.headers["x-csrf-token"], "csrf")
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "urls": [
                        {
                            "short_url": "https://meli.la/1BwH3aR",
                            "long_url": "https://www.mercadolivre.com.br/social/axdxs2",
                            "origin_url": "https://www.mercadolivre.com.br/x/p/MLB19603205",
                            "text": "Ou acesse o link:\nhttps://meli.la/1BwH3aR",
                        }
                    ],
                },
                request=request,
            )

        client = MercadoLivreClient(
            tag="axdxs2",
            cookie_header="ssid=abc",
            csrf_token="csrf",
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        link = client.create_link("https://www.mercadolivre.com.br/x/p/MLB19603205")

        self.assertEqual(link.short_url, "https://meli.la/1BwH3aR")
        self.assertEqual(
            seen_payloads,
            [
                {
                    "itemId": "MLB19603205",
                    "itemAddToList": "MLB5872060016",
                    "tag": "axdxs2",
                    "type": "product",
                    "urls": ["www.mercadolivre.com.br/x/p/MLB19603205"],
                    "extraCommission": "false",
                }
            ],
        )

    def test_create_link_raises_supported_error_for_already_affiliate_url(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, text="MLB19603205", request=request)

            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "urls": [
                        {
                            "origin_url": "www.mercadolivre.com.br/social/promotom?ref=abc",
                            "message": "URL not allowed in affiliates program",
                            "error_code": 111,
                            "status": 200,
                        }
                    ],
                    "total_success": 0,
                    "total_error": 1,
                },
                request=request,
            )

        client = MercadoLivreClient(
            tag="axdxs2",
            cookie_header="ssid=abc",
            csrf_token="csrf",
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        with self.assertRaisesRegex(UnsupportedOfferError, "URL not allowed"):
            client.create_link("https://www.mercadolivre.com.br/social/promotom?ref=abc")

    def test_create_link_retries_with_browser_resolved_product_url(self):
        posts = []

        class Resolver:
            def resolve(self, url: str) -> str | None:
                self.seen_url = url
                return "https://www.mercadolivre.com.br/cooktop/p/MLB23997577?wid=MLB4548038861"

        resolver = Resolver()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, request=request)

            payload = json.loads(request.content.decode())
            posts.append(payload)
            if "social/promotom" in payload["urls"][0]:
                return httpx.Response(
                    200,
                    json={
                        "urls": [
                            {
                                "origin_url": "www.mercadolivre.com.br/social/promotom?ref=abc",
                                "message": "URL not allowed in affiliates program",
                                "error_code": 111,
                            }
                        ]
                    },
                    request=request,
                )
            return httpx.Response(
                200,
                json={"urls": [{"short_url": "https://meli.la/mine", "origin_url": payload["urls"][0]}]},
                request=request,
            )

        client = MercadoLivreClient(
            tag="axdxs2",
            cookie_header="ssid=abc",
            csrf_token="csrf",
            product_url_resolver=resolver,
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        link = client.create_link("https://www.mercadolivre.com.br/social/promotom?ref=abc")

        self.assertEqual(link.short_url, "https://meli.la/mine")
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["itemId"], "MLB23997577")
        self.assertEqual(posts[0]["itemAddToList"], "MLB4548038861")


if __name__ == "__main__":
    unittest.main()
