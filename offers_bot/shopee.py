from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import httpx

from .mercado_livre import AffiliateLink
from .parser import extract_shopee_ids

LOGGER = logging.getLogger(__name__)


class ShopeeClient:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        client: httpx.Client | None = None,
        resolver_client: httpx.Client | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._client = client or httpx.Client(timeout=30)
        self._resolver_client = resolver_client or httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
                ),
            },
        )
        self._endpoint = "https://open-api.affiliate.shopee.com.br/graphql"

    def ready(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def create_link(self, url: str) -> AffiliateLink:
        if not self.ready():
            raise RuntimeError(
                "Shopee credentials missing: SHOPEE_APP_ID, SHOPEE_APP_SECRET"
            )

        normalized_url = self._normalize_url(url)
        resolved_url = self._resolve_url(normalized_url)

        # Use the GraphQL API to generate the short link
        query = """
        mutation generateShortLink($input: ShortLinkInput!) {
          generateShortLink(input: $input) {
            shortLink
          }
        }
        """
        variables = {"input": {"originUrl": resolved_url}}

        data = self._api_request(query, variables)
        short_url = data.get("generateShortLink", {}).get("shortLink")

        if not short_url:
            raise RuntimeError(
                f"Shopee API did not return shortLink for {resolved_url}. Data: {data}"
            )

        ids = extract_shopee_ids(resolved_url) or extract_shopee_ids(normalized_url)
        if ids:
            shop_id, item_id = ids
            product_key = f"SHOPEE:{shop_id}:{item_id}"
            image_url = self._get_product_image(shop_id, item_id)
        else:
            product_key = f"SHOPEE:CUSTOM:{resolved_url}"
            image_url = None

        return AffiliateLink(
            short_url=short_url,
            long_url=resolved_url,
            origin_url=resolved_url,
            raw_text=None,
            product_key=product_key,
            image_url=image_url,
        )

    def _api_request(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        timestamp = int(time.time())
        payload = {
            "query": query.strip(),
            "variables": variables or {},
            "operationName": None,
        }
        body_str = json.dumps(payload, separators=(",", ":"))
        signature = self._generate_signature(timestamp, body_str)

        authorization = f"SHA256 Credential={self._app_id},Timestamp={timestamp},Signature={signature}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": authorization,
        }

        LOGGER.debug("Shopee API Request: %s", body_str)
        response = self._client.post(self._endpoint, headers=headers, content=body_str)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            LOGGER.error("Shopee API Errors: %s", result["errors"])
            raise RuntimeError(f"Shopee API error: {result['errors']}")

        return result.get("data", {})

    def _generate_signature(self, timestamp: int, body: str) -> str:
        factor = f"{self._app_id}{timestamp}{body}{self._app_secret}"
        return hashlib.sha256(factor.encode("utf-8")).hexdigest()

    def _get_product_image(self, shop_id: str, item_id: str) -> str | None:
        query = f"""
        {{
          productOfferV2(shopId: {shop_id}, itemId: {item_id}, page: 1, limit: 1) {{
            nodes {{
              imageUrl
            }}
          }}
        }}
        """
        try:
            data = self._api_request(query)
            nodes = data.get("productOfferV2", {}).get("nodes", [])
            if nodes:
                image_url = nodes[0].get("imageUrl")
                LOGGER.info("Shopee product image URL: %s", image_url)
                return image_url
        except Exception as exc:
            LOGGER.warning("Failed to fetch Shopee product image: %s", exc)
        return None

    def _resolve_url(self, url: str) -> str:
        try:
            response = self._resolver_client.get(url)
            response.raise_for_status()
            return str(response.url)
        except httpx.HTTPError as exc:
            LOGGER.warning("Could not resolve URL %s: %s", url, exc)
            return url

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"
