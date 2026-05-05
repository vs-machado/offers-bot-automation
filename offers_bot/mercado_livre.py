from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

from .parser import extract_ml_ids

LOGGER = logging.getLogger(__name__)


class UnsupportedOfferError(RuntimeError):
    """Offer cannot be converted into this account's affiliate link."""


class ProductUrlResolver(Protocol):
    def resolve(self, url: str) -> str | None:
        ...

    def get_image(self, url: str) -> str | None:
        ...


@dataclass(frozen=True)
class AffiliateLink:
    short_url: str
    long_url: str | None
    origin_url: str
    raw_text: str | None
    image_url: str | None = None


class MercadoLivreClient:
    def __init__(
        self,
        tag: str,
        cookie_header: str,
        csrf_token: str,
        product_url_resolver: ProductUrlResolver | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._tag = tag
        self._cookie_header = cookie_header
        self._csrf_token = csrf_token
        self._product_url_resolver = product_url_resolver
        self._client = client or httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "accept": "application/json, text/plain, */*",
                "accept-language": "pt-BR,pt;q=0.9",
                "content-type": "application/json",
                "origin": "https://www.mercadolivre.com.br",
                "referer": "https://www.mercadolivre.com.br/afiliados/hub",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
            },
        )

    def ready(self) -> bool:
        return bool(self._tag and self._cookie_header and self._csrf_token)

    def create_link(self, url: str) -> AffiliateLink:
        if not self.ready():
            raise RuntimeError("Mercado Livre credentials missing: ML_AFFILIATE_TAG, ML_COOKIE_HEADER, ML_CSRF_TOKEN")

        normalized_url = self._normalize_url(url)
        resolved_url = self._resolve_url(normalized_url)
        resolved_url = self._resolve_product_url_if_needed(normalized_url, resolved_url) or resolved_url
        link = self._create_link_from_product_url(resolved_url)
        
        image_url = None
        if self._product_url_resolver:
            image_source_url = self._normalize_url(link.origin_url or resolved_url)
            image_url = self._product_url_resolver.get_image(image_source_url)
            
        return AffiliateLink(
            short_url=link.short_url,
            long_url=link.long_url,
            origin_url=link.origin_url,
            raw_text=link.raw_text,
            image_url=image_url
        )

    def _create_link_from_product_url(self, resolved_url: str) -> AffiliateLink:
        ids = self._discover_ids(resolved_url)
        if not ids:
            raise RuntimeError(f"Could not find Mercado Livre item id in URL/page: {resolved_url}")

        item_id = ids[0]
        item_add_to_list = ids[-1]
        payload = {
            "itemId": item_id,
            "itemAddToList": item_add_to_list,
            "tag": self._tag,
            "type": "product",
            "urls": [self._strip_scheme(resolved_url)],
            "extraCommission": "false",
        }

        response = self._client.post(
            "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink",
            headers={
                "cookie": self._cookie_header,
                "x-csrf-token": self._csrf_token,
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        urls = data.get("urls") or []
        if not urls or not urls[0].get("short_url"):
            first_error = urls[0] if urls else {}
            if first_error.get("error_code") == 111 and self._product_url_resolver:
                product_url = self._product_url_resolver.resolve(resolved_url)
                if product_url and product_url != resolved_url:
                    return self._create_link_from_product_url(product_url)
            if first_error.get("error_code") == 111:
                raise UnsupportedOfferError(first_error.get("message") or "URL not allowed in affiliates program")
            raise RuntimeError(f"Mercado Livre did not return short_url: {data}")

        first = urls[0]
        return AffiliateLink(
            short_url=first["short_url"],
            long_url=first.get("long_url"),
            origin_url=first.get("origin_url") or resolved_url,
            raw_text=first.get("text"),
        )

    def _resolve_product_url_if_needed(self, original_url: str, resolved_url: str) -> str | None:
        if not self._product_url_resolver:
            return None
        parsed = urlparse(resolved_url)
        if parsed.path.startswith("/social/") or "source=affiliate-profile" in resolved_url:
            product_url = self._product_url_resolver.resolve(resolved_url)
            if product_url:
                LOGGER.info("Resolved affiliate/profile URL to product URL: %s", product_url)
                return product_url
        if "meli.la" in original_url and not extract_ml_ids(resolved_url):
            product_url = self._product_url_resolver.resolve(resolved_url)
            if product_url:
                LOGGER.info("Resolved short affiliate URL to product URL: %s", product_url)
                return product_url
        return None

    def _resolve_url(self, url: str) -> str:
        response = self._client.get(url)
        response.raise_for_status()
        return str(response.url)

    def _discover_ids(self, url: str) -> list[str]:
        ids = extract_ml_ids(url)
        if len(ids) >= 2:
            return ids

        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            LOGGER.warning("Could not fetch product page for id discovery: %s", exc)
            return ids

        for item_id in extract_ml_ids(response.text):
            if item_id not in ids:
                ids.append(item_id)
            if len(ids) >= 2:
                break
        return ids

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"

    @staticmethod
    def _strip_scheme(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
