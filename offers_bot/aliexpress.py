import logging
import json
import httpx
from .mercado_livre import AffiliateLink
from .iop import IopClient, IopRequest
from .parser import extract_aliexpress_product_id

LOGGER = logging.getLogger(__name__)


COIN_INDEX_URL = (
    "https://m.aliexpress.com/p/coin-index/index.html"
    "?_immersiveMode=true&from=syicon&productIds={product_id}"
)


def _resolve_ali_url(url: str) -> str:
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0, connect=10.0), follow_redirects=True
        ) as client:
            resp = client.get(url)
            return str(resp.url)
    except Exception as exc:
        LOGGER.warning("Failed to resolve AliExpress URL %s: %s", url, exc)
        return url


class AliExpressClient:
    """AliExpress Affiliate API Client using official IOP SDK"""

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        tracking_id: str | None = None,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._tracking_id = tracking_id
        # Standard Global Gateway
        self._endpoint = "https://api-sg.aliexpress.com/sync"

    def ready(self) -> bool:
        return bool(self._app_key and self._app_secret)

    def create_link(self, url: str) -> AffiliateLink:
        if not self.ready():
            raise RuntimeError(
                "AliExpress credentials missing (ALIEXPRESS_APP_KEY/SECRET)."
            )

        resolved = _resolve_ali_url(url)
        product_id = extract_aliexpress_product_id(resolved)
        if product_id:
            target_url = COIN_INDEX_URL.format(product_id=product_id)
            LOGGER.info(
                "Using coin-index URL for product %s: %s", product_id, target_url
            )
        else:
            LOGGER.warning(
                "Could not extract product ID from resolved URL: %s", resolved
            )
            target_url = url

        client = IopClient(self._endpoint, self._app_key, self._app_secret)
        request = IopRequest("aliexpress.affiliate.link.generate")

        request.add_api_param("ship_to_country", "BR")
        request.add_api_param("promotion_link_type", "0")
        request.add_api_param("source_values", target_url)
        request.add_api_param("tracking_id", self._tracking_id or "default")

        response = client.execute(request)

        # The response.body is the parsed JSON
        data = response.body
        LOGGER.info(f"AliExpress Response: {json.dumps(data)}")

        if response.code != "0" and response.code is not None:
            raise RuntimeError(
                f"AliExpress API error: {response.message} (code: {response.code})"
            )

        # Parse resp_result according to the documentation
        # The structure is usually nested:
        # aliexpress_affiliate_link_generate_response -> resp_result -> result -> promotion_links -> promotion_link

        root_key = "aliexpress_affiliate_link_generate_response"
        resp_result = data.get(root_key, {}).get("resp_result", {})

        if not resp_result:
            # Fallback for different response formats
            resp_result = data.get("resp_result", {})

        links = (
            resp_result.get("result", {})
            .get("promotion_links", {})
            .get("promotion_link", [])
        )

        if not links and "promotion_links" in resp_result:
            # Handle if it's directly under resp_result (Streamlined)
            links = resp_result.get("promotion_links", [])

        if not links:
            raise RuntimeError(
                f"AliExpress API returned no links. Response: {json.dumps(data)}"
            )

        promotion_link = links[0].get("promotion_link")

        if not promotion_link:
            message = links[0].get("message", "Unknown error")
            raise RuntimeError(f"AliExpress API failed to generate link: {message}")

        image_url = self._get_product_image(product_id) if product_id else None

        key = f"ALIEXPRESS:{product_id}" if product_id else f"ALIEXPRESS:{url}"

        return AffiliateLink(
            short_url=promotion_link,
            long_url=target_url,
            origin_url=url,
            raw_text=None,
            product_key=key,
            image_url=image_url,
        )

    def _get_product_image(self, product_id: str) -> str | None:
        try:
            client = IopClient(self._endpoint, self._app_key, self._app_secret)
            request = IopRequest("aliexpress.affiliate.product.query")
            request.add_api_param("product_ids", product_id)
            request.add_api_param("ship_to_country", "BR")
            request.add_api_param("target_currency", "BRL")
            request.add_api_param("target_language", "PT")

            response = client.execute(request)
            data = response.body

            root_key = "aliexpress_affiliate_product_query_response"
            resp_result = data.get(root_key, {}).get("resp_result", {})
            if not resp_result:
                resp_result = data.get("resp_result", {})

            products = (
                resp_result.get("result", {}).get("products", {}).get("product", [])
            )

            if products:
                product = products[0]
                return product.get("product_main_image_url") or product.get("image_url")
        except Exception as exc:
            LOGGER.warning(
                "Failed to fetch AliExpress product image for %s: %s", product_id, exc
            )
        return None
