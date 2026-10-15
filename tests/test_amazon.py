import hashlib
import unittest
from urllib.parse import parse_qsl, urlparse

import httpx

from offers_bot.amazon import AmazonClient


class AmazonClientTest(unittest.TestCase):
    def make_client(self, handler=None, **kwargs):
        def reject_request(request):
            self.fail(f"Unexpected HTTP request: {request.url}")

        http = httpx.Client(
            transport=httpx.MockTransport(handler or reject_request),
            follow_redirects=True,
        )
        self.addCleanup(http.close)
        return AmazonClient(client=http, **{"tag": "mytag-20", **kwargs})

    def test_ready_requires_only_nonblank_tag(self):
        self.assertTrue(self.make_client(tag=" mytag-20 ").ready())
        for tag in ("", " \t\n"):
            with self.subTest(tag=tag):
                client = self.make_client(tag=tag)
                self.assertFalse(client.ready())
                with self.assertRaisesRegex(RuntimeError, "AMAZON_AFFILIATE_TAG"):
                    client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8")

    def test_expanded_product_needs_no_http_and_returns_expanded_links(self):
        client = self.make_client(tag=" mytag-20 ")
        for path in ("/dp/B0DXR6MKR8", "/gp/product/B0DXR6MKR8"):
            with self.subTest(path=path):
                original = f"https://www.amazon.com.br{path}?th=1&tag=old-20"
                link = client.create_link(original)
                expected = f"https://www.amazon.com.br{path}?th=1&tag=mytag-20"
                self.assertEqual(link.short_url, expected)
                self.assertEqual(link.long_url, expected)
                self.assertEqual(link.origin_url, original)
                self.assertEqual(link.product_key, "AMZN:B0DXR6MKR8")
                self.assertIsNone(link.image_url)

    def test_removes_repeated_tracking_and_path_ref_keeps_functional_params(self):
        link = self.make_client().create_link(
            "https://www.amazon.com.br/Produto/dp/B0DXR6MKR8/ref=as_li_ss_tl?"
            "tag=old&tag=older&linkCode=sl1&linkCode=sl2&linkId=a&linkId=b&"
            "ref=x&ref_=y&creative=1&camp=2&creativeASIN=B0DXR6MKR8&"
            "utm_source=group&utm_medium=social&utm_campaign=promo&"
            "th=1&psc=1&keywords=caf%C3%A9+em+gr%C3%A3os&filter=a&filter=b&blank="
        )
        self.assertEqual(urlparse(link.long_url).path, "/Produto/dp/B0DXR6MKR8")
        self.assertEqual(
            parse_qsl(urlparse(link.long_url).query, keep_blank_values=True),
            [
                ("th", "1"),
                ("psc", "1"),
                ("keywords", "caf\u00e9 em gr\u00e3os"),
                ("filter", "a"),
                ("filter", "b"),
                ("blank", ""),
                ("tag", "mytag-20"),
            ],
        )
        self.assertEqual(link.short_url, link.long_url)
        self.assertEqual(link.product_key, "AMZN:B0DXR6MKR8")

    def test_campaign_without_asin_preserves_destination_and_hashes_canonical_url(self):
        original = (
            "https://www.amazon.com.br/b?node=16209062011&"
            "pf_rd_p=campaign&tag=old-20&ref_=nav_cs#offers"
        )
        link = self.make_client().create_link(original)
        expected = (
            "https://www.amazon.com.br/b?node=16209062011&"
            "pf_rd_p=campaign&tag=mytag-20#offers"
        )
        canonical = "https://www.amazon.com.br/b?node=16209062011&pf_rd_p=campaign"
        self.assertEqual(link.short_url, expected)
        self.assertEqual(link.long_url, expected)
        self.assertEqual(link.origin_url, original)
        self.assertEqual(
            link.product_key,
            "AMZN:URL:" + hashlib.sha256(canonical.encode()).hexdigest(),
        )

    def test_campaign_dedup_ignores_tracking_query_order_and_fragment(self):
        client = self.make_client()
        urls = (
            "https://www.amazon.com.br/b?node=123&filter=b&filter=a&blank=&tag=old"
            "&utm_source=groupA#one",
            "https://www.amazon.com.br/b/ref=nav?blank=&filter=a&node=123&filter=b&"
            "tag=other&linkCode=sl2&linkId=1&ref=x&ref_=y&creative=2&camp=3&"
            "creativeASIN=B0DXR6MKR8&utm_source=groupB&utm_medium=social#two",
        )
        keys = [client.create_link(url).product_key for url in urls]
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(
            keys[0], self.make_client(tag="another-20").create_link(urls[0]).product_key
        )
        for url in (
            "https://www.amazon.com.br/b?node=456&filter=b&filter=a&blank=",
            "https://www.amazon.com.br/b?node=123&filter=c&filter=a&blank=",
            "https://www.amazon.com.br/b?node=123&filter=b&filter=a",
            "https://www.amazon.com.br/s?node=123&filter=b&filter=a&blank=",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(keys[0], client.create_link(url).product_key)

    def test_product_dedup_uses_asin_not_parameters(self):
        client = self.make_client()
        first = client.create_link("https://www.amazon.com.br/dp/B0DXR6MKR8?th=1")
        second = client.create_link(
            "https://www.amazon.com.br/name/gp/product/b0dxr6mkr8?psc=1&tag=old"
        )
        other = client.create_link("https://www.amazon.com.br/dp/B01JUSTFD0")
        self.assertEqual(first.product_key, second.product_key)
        self.assertNotEqual(first.product_key, other.product_key)

    def test_amzn_to_follows_redirect_chain(self):
        seen = []
        destination = "https://www.amazon.com.br/dp/B0DXR6MKR8?psc=1&tag=old"

        def handler(request):
            seen.append(str(request.url))
            if request.url.host == "amzn.to":
                return httpx.Response(302, headers={"location": destination})
            if request.url.path == "/dp/B0DXR6MKR8":
                return httpx.Response(
                    301, headers={"location": "/gp/product/B0DXR6MKR8?th=1"}
                )
            self.assertEqual(request.url.host, "www.amazon.com.br")
            self.assertEqual(request.url.path, "/gp/product/B0DXR6MKR8")
            return httpx.Response(200)

        link = self.make_client(handler).create_link("https://amzn.to/example")
        self.assertEqual(seen[0], "https://amzn.to/example")
        self.assertIn(destination, seen)
        self.assertEqual(
            link.origin_url, "https://www.amazon.com.br/gp/product/B0DXR6MKR8?th=1"
        )
        self.assertEqual(
            link.short_url,
            "https://www.amazon.com.br/gp/product/B0DXR6MKR8?th=1&tag=mytag-20",
        )
        self.assertEqual(link.long_url, link.short_url)
        self.assertEqual(link.product_key, "AMZN:B0DXR6MKR8")

    def test_link_amazon_asin_normalizes_without_http_preserving_query(self):
        for host in ("link.amazon", "www.link.amazon"):
            with self.subTest(host=host):
                link = self.make_client().create_link(
                    f"{host}/b01justfd0?th=1&psc=1&tag=old&linkId=abc"
                )
                self.assertEqual(
                    link.long_url,
                    "https://www.amazon.com.br/dp/B01JUSTFD0?th=1&psc=1&tag=mytag-20",
                )
                self.assertEqual(link.short_url, link.long_url)
                self.assertEqual(link.product_key, "AMZN:B01JUSTFD0")

    def test_link_amazon_campaign_expands_over_http(self):
        seen = []
        destination = "https://www.amazon.com.br/b?node=123&tag=old"

        def handler(request):
            seen.append(str(request.url))
            if request.url.host == "link.amazon":
                return httpx.Response(302, headers={"location": destination})
            self.assertEqual(str(request.url), destination)
            return httpx.Response(200)

        link = self.make_client(handler).create_link("https://link.amazon/sale")
        self.assertEqual(seen[0], "https://link.amazon/sale")
        self.assertEqual(link.origin_url, destination)
        self.assertEqual(
            link.long_url, "https://www.amazon.com.br/b?node=123&tag=mytag-20"
        )
        self.assertEqual(link.short_url, link.long_url)
        self.assertTrue(link.product_key.startswith("AMZN:URL:"))

    def test_rejects_external_destinations_and_unresolved_short_links(self):
        for destination in (
            "https://example.com/dp/B0DXR6MKR8",
            "https://www.amazon.com/dp/B0DXR6MKR8",
            "https://amazon.com.br.example.com/dp/B0DXR6MKR8",
            "https://amzn.to/unresolved",
            "https://link.amazon/sale-unresolved",
        ):
            with self.subTest(destination=destination):

                def handler(request):
                    if str(request.url) == "https://amzn.to/start":
                        return httpx.Response(302, headers={"location": destination})
                    self.assertIn(request.url.host, {"amzn.to", "link.amazon"})
                    return httpx.Response(200)

                with self.assertRaises(RuntimeError):
                    self.make_client(handler).create_link("https://amzn.to/start")
                if urlparse(destination).hostname not in {"amzn.to", "link.amazon"}:
                    with self.assertRaises(RuntimeError):
                        self.make_client().create_link(destination)

    def test_redirect_loop_is_bounded(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(302, headers={"location": "/loop"})

        with self.assertRaisesRegex(RuntimeError, "Too many redirects"):
            self.make_client(handler).create_link("https://amzn.to/loop")
        self.assertEqual(len(seen), 10)

    def test_http_failures_propagate(self):
        for status in (403, 500):
            with self.subTest(status=status):
                client = self.make_client(lambda request: httpx.Response(status))
                with self.assertRaises(httpx.HTTPStatusError):
                    client.create_link("https://amzn.to/failure")

        def timeout(request):
            raise httpx.ReadTimeout("Expansion timed out", request=request)

        with self.assertRaises(httpx.ReadTimeout):
            self.make_client(timeout).create_link("https://amzn.to/timeout")

    def test_products_and_campaigns_do_not_fetch_images(self):
        client = self.make_client()
        for url in (
            "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=old",
            "https://www.amazon.com.br/b?node=123",
        ):
            with self.subTest(url=url):
                self.assertIsNone(client.create_link(url).image_url)


if __name__ == "__main__":
    unittest.main()
