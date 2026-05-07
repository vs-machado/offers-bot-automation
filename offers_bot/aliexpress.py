import logging
import json
from .mercado_livre import AffiliateLink
from .iop import IopClient, IopRequest

LOGGER = logging.getLogger(__name__)

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
            raise RuntimeError("AliExpress credentials missing (ALIEXPRESS_APP_KEY/SECRET).")

        client = IopClient(self._endpoint, self._app_key, self._app_secret)
        request = IopRequest("aliexpress.affiliate.link.generate")
        
        request.add_api_param("ship_to_country", "BR")
        request.add_api_param("promotion_link_type", "0")
        request.add_api_param("source_values", url)
        request.add_api_param("tracking_id", self._tracking_id or "default")
        
        response = client.execute(request)
        
        # The response.body is the parsed JSON
        data = response.body
        LOGGER.info(f"AliExpress Response: {json.dumps(data)}")
        
        if response.code != "0" and response.code is not None:
            raise RuntimeError(f"AliExpress API error: {response.message} (code: {response.code})")

        # Parse resp_result according to the documentation
        # The structure is usually nested: 
        # aliexpress_affiliate_link_generate_response -> resp_result -> result -> promotion_links -> promotion_link
        
        root_key = "aliexpress_affiliate_link_generate_response"
        resp_result = data.get(root_key, {}).get("resp_result", {})
        
        if not resp_result:
            # Fallback for different response formats
            resp_result = data.get("resp_result", {})

        links = resp_result.get("result", {}).get("promotion_links", {}).get("promotion_link", [])
        
        if not links and "promotion_links" in resp_result:
            # Handle if it's directly under resp_result (Streamlined)
            links = resp_result.get("promotion_links", [])

        if not links:
            raise RuntimeError(f"AliExpress API returned no links. Response: {json.dumps(data)}")

        promotion_link = links[0].get("promotion_link")
        
        if not promotion_link:
            message = links[0].get("message", "Unknown error")
            raise RuntimeError(f"AliExpress API failed to generate link: {message}")
        
        return AffiliateLink(
            short_url=promotion_link,
            long_url=url,
            origin_url=url,
            raw_text=None,
            product_key=f"ALIEXPRESS:{url}",
        )
