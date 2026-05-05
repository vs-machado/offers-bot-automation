import unittest

import httpx

from offers_bot.amazon import AmazonClient


class AmazonClientTest(unittest.TestCase):
    def test_create_link_resolves_url_and_calls_sitestripe_shortener(self):
        seen_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_requests.append(request)
            if request.url.path == "/dp/B0DXR6MKR8":
                return httpx.Response(200, request=request)
            if request.url.host == "amzn.to":
                return httpx.Response(200, request=request)
            self.assertEqual(request.url.path, "/associates/sitestripe/getShortUrl")
            self.assertEqual(request.headers["cookie"], "session-id=abc")
            self.assertEqual(
                request.url.params["longUrl"],
                "https://www.amazon.com.br/dp/B0DXR6MKR8?linkCode=sl2&tag=mytag-20",
            )
            self.assertEqual(request.url.params["marketplaceId"], "526970")
            return httpx.Response(
                200,
                json={
                    "shortUrl": "https://amzn.to/4abc123",
                    "longUrl": (
                        "https://www.amazon.com.br/dp/B0DXR6MKR8?linkCode=sl2"
                        "&tag=mytag-20&linkId=abc123&ref_=as_li_ss_tl"
                    ),
                },
                request=request,
            )

        client = AmazonClient(
            tag="mytag-20",
            cookie_header="session-id=abc",
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        link = client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")

        self.assertEqual(link.short_url, "https://amzn.to/4abc123")
        self.assertEqual(
            link.long_url,
            "https://www.amazon.com.br/dp/B0DXR6MKR8?linkCode=sl2&tag=mytag-20&linkId=abc123&ref_=as_li_ss_tl",
        )
        self.assertEqual(link.origin_url, "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")
        self.assertEqual(link.product_key, "AMZN:B0DXR6MKR8")
        self.assertEqual(len(seen_requests), 3)

    def test_create_link_preserves_non_affiliate_query_params(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/dp/B0DXR6MKR8":
                return httpx.Response(200, request=request)
            if request.url.host == "amzn.to":
                return httpx.Response(200, request=request)
            self.assertEqual(
                request.url.params["longUrl"],
                "https://www.amazon.com.br/dp/B0DXR6MKR8?th=1&psc=1&linkCode=sl2&tag=mytag-20",
            )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "shortUrl": "https://amzn.to/4abc123",
                        "longUrl": (
                            "https://www.amazon.com.br/dp/B0DXR6MKR8?th=1&psc=1&linkCode=sl2"
                            "&tag=mytag-20&linkId=abc123&ref_=as_li_ss_tl"
                        ),
                    }
                },
                request=request,
            )

        client = AmazonClient(
            tag="mytag-20",
            cookie_header="session-id=abc",
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        link = client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8?th=1&psc=1&tag=old-20&linkId=123")

        self.assertEqual(link.short_url, "https://amzn.to/4abc123")
        self.assertEqual(
            link.long_url,
            "https://www.amazon.com.br/dp/B0DXR6MKR8?th=1&psc=1&linkCode=sl2&tag=mytag-20&linkId=abc123&ref_=as_li_ss_tl",
        )

    def test_create_link_extracts_image_with_resolver(self):
        class Resolver:
            def get_image(self, url: str) -> str | None:
                self.seen_url = url
                return "https://m.media-amazon.com/images/I/41Zguc9CziL._AC_SL1000_.jpg"

        resolver = Resolver()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/dp/B0DXR6MKR8":
                return httpx.Response(200, request=request)
            if request.url.host == "amzn.to":
                return httpx.Response(200, request=request)
            return httpx.Response(200, json={"shortUrl": "https://amzn.to/4abc123"}, request=request)

        client = AmazonClient(
            tag="mytag-20",
            cookie_header="session-id=abc",
            image_resolver=resolver,
            client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        )

        link = client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")

        self.assertEqual(resolver.seen_url, "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")
        self.assertEqual(link.image_url, "https://m.media-amazon.com/images/I/41Zguc9CziL._AC_SL1000_.jpg")

    def test_create_link_prefers_short_url_redirect_target(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/dp/B0DXR6MKR8":
                return httpx.Response(200, request=request)
            if request.url.host == "amzn.to":
                return httpx.Response(
                    200,
                    request=request,
                    extensions={
                        "http_version": b"HTTP/1.1",
                    },
                )
            return httpx.Response(
                200,
                json={"shortUrl": "https://amzn.to/4abc123"},
                request=request,
            )

        client = AmazonClient(
            tag="mytag-20",
            cookie_header="session-id=abc",
            client=httpx.Client(
                transport=httpx.MockTransport(handler),
                follow_redirects=True,
            ),
        )

        original_resolve_short_url = client._resolve_short_url
        client._resolve_short_url = lambda url: (
            "https://www.amazon.com.br/dp/B0DXR6MKR8?linkCode=sl2&tag=mytag-20"
            "&linkId=abc123&ref_=as_li_ss_tl"
        )
        try:
            link = client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20")
        finally:
            client._resolve_short_url = original_resolve_short_url

        self.assertEqual(
            link.long_url,
            "https://www.amazon.com.br/dp/B0DXR6MKR8?linkCode=sl2&tag=mytag-20&linkId=abc123&ref_=as_li_ss_tl",
        )


if __name__ == "__main__":
    unittest.main()
