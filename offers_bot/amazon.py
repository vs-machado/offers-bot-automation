from __future__ import annotations

import re
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from .models import AffiliateLink

ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)


class ImageResolver(Protocol):
    def get_image(self, url: str) -> str | None: ...


class AmazonClient:
    def __init__(
        self,
        tag: str,
        cookie_header: str,
        marketplace_id: str = "526970",
        image_resolver: ImageResolver | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._tag = tag
        self._cookie_header = cookie_header
        self._marketplace_id = marketplace_id
        self._image_resolver = image_resolver
        self._client = client or httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "accept": "application/json, text/javascript, */*; q=0.01",
                "accept-language": "pt-BR,pt;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
                "x-requested-with": "XMLHttpRequest",
            },
        )

    def ready(self) -> bool:
        return bool(self._tag and self._cookie_header)

    def create_link(self, url: str) -> AffiliateLink:
        if not self.ready():
            raise RuntimeError(
                "Amazon credentials missing: AMAZON_AFFILIATE_TAG, AMAZON_COOKIE_HEADER"
            )

        normalized_url = self._normalize_url(url)
        resolved_url = self._resolve_url(normalized_url)
        request_url = self._build_long_url(resolved_url)
        short_url, product_url = self._fetch_short_url(request_url, resolved_url)
        product_url = self._resolve_short_url(short_url) or product_url
        asin = self._extract_asin(product_url)
        if not asin:
            raise RuntimeError(f"Could not find Amazon ASIN in URL: {product_url}")
        image_url = (
            self._image_resolver.get_image(resolved_url)
            if self._image_resolver
            else None
        )

        return AffiliateLink(
            short_url=short_url,
            long_url=product_url,
            origin_url=resolved_url,
            raw_text=None,
            product_key=f"AMZN:{asin}",
            image_url=image_url,
        )

    def _fetch_short_url(self, request_url: str, referer: str) -> tuple[str, str]:
        response = self._client.get(
            "https://www.amazon.com.br/associates/sitestripe/getShortUrl",
            headers={
                "cookie": self._cookie_header,
                "referer": referer,
            },
            params={
                "longUrl": request_url,
                "marketplaceId": self._marketplace_id,
            },
        )
        response.raise_for_status()
        data = response.json()
        short_url = self._extract_short_url(data)
        if not short_url:
            raise RuntimeError(f"Amazon did not return shortUrl: {data}")
        product_url = self._extract_long_url(data) or request_url
        return short_url, product_url

    def _resolve_url(self, url: str) -> str:
        response = self._client.get(url)
        response.raise_for_status()
        return str(response.url)

    def _resolve_short_url(self, url: str) -> str | None:
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        resolved_url = str(response.url)
        parsed = urlparse(resolved_url)
        if resolved_url.startswith("http") and parsed.netloc.lower() != "amzn.to":
            return resolved_url
        return None

    def _build_long_url(self, url: str) -> str:
        parsed = urlparse(url)
        query_pairs = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in {"tag", "linkCode", "linkId"}
        ]
        query_pairs.append(("linkCode", "sl2"))
        query_pairs.append(("tag", self._tag))
        return urlunparse(parsed._replace(query=urlencode(query_pairs)))

    @staticmethod
    def _extract_short_url(data: Any) -> str | None:
        if isinstance(data, str) and data.startswith("http"):
            return data
        if isinstance(data, dict):
            for key in ("shortUrl", "shortURL", "amznShortUrl", "short_url"):
                value = data.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return value
                if isinstance(value, dict):
                    nested = AmazonClient._extract_short_url(value)
                    if nested:
                        return nested
            for value in data.values():
                nested = AmazonClient._extract_short_url(value)
                if nested:
                    return nested
        if isinstance(data, list):
            for value in data:
                nested = AmazonClient._extract_short_url(value)
                if nested:
                    return nested
        return None

    @staticmethod
    def _extract_long_url(data: Any) -> str | None:
        if isinstance(data, dict):
            for key in ("longUrl", "longURL", "amznLongUrl", "long_url"):
                value = data.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return value
                if isinstance(value, dict):
                    nested = AmazonClient._extract_long_url(value)
                    if nested:
                        return nested
            for value in data.values():
                nested = AmazonClient._extract_long_url(value)
                if nested:
                    return nested
        if isinstance(data, list):
            for value in data:
                nested = AmazonClient._extract_long_url(value)
                if nested:
                    return nested
        return None

    @staticmethod
    def _extract_asin(url: str) -> str | None:
        match = ASIN_RE.search(url)
        if not match:
            return None
        return match.group(1).upper()

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"
