"""Source media must avoid browser image lookup without breaking affiliate links."""

import unittest
from unittest.mock import Mock, patch

from offers_bot.amazon import AmazonClient
from offers_bot.mercado_livre import MercadoLivreClient
from offers_bot.models import AffiliateLink


class SourceImageFallbackTests(unittest.TestCase):
    def test_amazon_generates_link_without_browser_image_lookup(self):
        resolver = Mock()
        product_url = "https://www.amazon.com.br/dp/B0DXR6MKR8"
        client = AmazonClient("example-20", "session-id=test", image_resolver=resolver)
        self.addCleanup(client._client.close)
        with (
            patch.object(client, "_resolve_url", return_value=product_url),
            patch.object(
                client,
                "_fetch_short_url",
                return_value=("https://amzn.to/example", product_url),
            ),
            patch.object(client, "_resolve_short_url", return_value=product_url),
        ):
            link = client.create_link(product_url, resolve_image=False)

        self.assertEqual(link.short_url, "https://amzn.to/example")
        self.assertEqual(link.product_key, "AMZN:B0DXR6MKR8")
        self.assertIsNone(link.image_url)
        resolver.get_image.assert_not_called()

    def test_ml_preserves_product_resolution_when_skipping_image_lookup(self):
        resolver = Mock()
        source_url = "https://www.mercadolivre.com.br/social/example"
        product_url = "https://www.mercadolivre.com.br/product/p/MLB23997577"
        resolver.resolve.return_value = product_url
        client = MercadoLivreClient(
            "example", "ssid=test", "csrf", product_url_resolver=resolver
        )
        self.addCleanup(client._client.close)
        result = AffiliateLink(
            short_url="https://meli.la/example",
            long_url=product_url,
            origin_url=product_url,
            raw_text=None,
            product_key="MLB23997577",
        )
        with (
            patch.object(client, "_resolve_url", return_value=source_url),
            patch.object(
                client, "_create_link_from_product_url", return_value=result
            ) as create_link,
        ):
            link = client.create_link(source_url, resolve_image=False)

        resolver.resolve.assert_called_once_with(source_url)
        create_link.assert_called_once_with(product_url)
        resolver.get_image.assert_not_called()
        self.assertEqual(link.short_url, result.short_url)
        self.assertIsNone(link.image_url)
