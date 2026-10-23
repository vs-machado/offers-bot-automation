from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from .models import AffiliateLink

ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)
LINK_AMAZON_ASIN_RE = re.compile(r"^/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)


class AmazonClient:
    def __init__(
        self,
        tag: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._tag = tag.strip()
        self._client = client or httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "accept": "text/html, */*; q=0.9",
                "accept-language": "pt-BR,pt;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
            },
        )

    def ready(self) -> bool:
        return bool(self._tag)

    def create_link(self, url: str) -> AffiliateLink:
        """Expand short links and replace affiliate tracking without SiteStripe.

        Preserve destination parameters; reject unresolved or non-Brazilian Amazon
        destinations. HTTP failures while expanding links propagate to the caller.
        """
        if not self.ready():
            raise RuntimeError("Amazon credentials missing: AMAZON_AFFILIATE_TAG")

        normalized_url = self._normalize_url(url)
        parsed = urlparse(normalized_url)
        host = parsed.hostname or ""
        if host in {"amzn.to", "link.amazon"} or host.endswith(".link.amazon"):
            normalized_url = self._normalize_url(self._resolve_url(normalized_url))
        parsed = urlparse(normalized_url)
        host = parsed.hostname or ""
        if (
            parsed.scheme not in {"http", "https"}
            or not (host == "amazon.com.br" or host.endswith(".amazon.com.br"))
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
        ):
            raise RuntimeError("Could not resolve a Brazilian Amazon destination")

        resolved_url = normalized_url
        product_url = self._build_long_url(resolved_url)
        asin = self._extract_asin(urlparse(product_url).path)
        destination = urlparse(product_url)
        destination_query = sorted(
            (key, value)
            for key, value in parse_qsl(destination.query, keep_blank_values=True)
            if key != "tag"
        )
        destination_key = urlunparse(
            destination._replace(query=urlencode(destination_query), fragment="")
        )
        product_key = (
            f"AMZN:{asin}"
            if asin
            else f"AMZN:URL:{hashlib.sha256(destination_key.encode()).hexdigest()}"
        )
        return AffiliateLink(
            short_url=product_url,
            long_url=product_url,
            origin_url=resolved_url,
            raw_text=None,
            product_key=product_key,
        )

    def _resolve_url(self, url: str) -> str:
        """Follow bounded HTTP redirects, rejecting external hosts before fetching."""
        for _ in range(10):
            parsed = urlparse(url)
            host = parsed.hostname or ""
            if (
                parsed.scheme not in {"http", "https"}
                or not (
                    host in {"amzn.to", "link.amazon", "amzlinks.in", "amazon.com.br"}
                    or host.endswith((".amazon.com.br", ".link.amazon"))
                )
                or parsed.username
                or parsed.password
                or parsed.port not in (None, 80, 443)
            ):
                raise RuntimeError(
                    "Amazon link redirected to an unsupported destination"
                )
            response = self._client.get(url, follow_redirects=False)
            if response.has_redirect_location:
                url = str(response.url.join(response.headers["location"]))
                continue
            response.raise_for_status()
            return str(response.url)
        raise RuntimeError("Too many redirects while expanding Amazon link")

    def _build_long_url(self, url: str) -> str:
        parsed = urlparse(url)
        query_pairs = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key
            not in {
                "tag",
                "linkCode",
                "linkId",
                "ref",
                "ref_",
                "creative",
                "camp",
                "creativeASIN",
            }
            and not key.lower().startswith("utm_")
        ]
        query_pairs.append(("tag", self._tag))
        path = re.sub(r"/ref=[^/]*$", "", parsed.path)
        return urlunparse(parsed._replace(path=path, query=urlencode(query_pairs)))

    @staticmethod
    def _extract_asin(url: str) -> str | None:
        match = ASIN_RE.search(url)
        if not match:
            return None
        return match.group(1).upper()

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            normalized_url = url
        else:
            normalized_url = f"https://{url}"

        parsed = urlparse(normalized_url)
        host = parsed.hostname or ""
        if host == "link.amazon" or host.endswith(".link.amazon"):
            asin_match = LINK_AMAZON_ASIN_RE.match(parsed.path)
            if asin_match:
                return urlunparse(
                    parsed._replace(
                        scheme="https",
                        netloc="www.amazon.com.br",
                        path=f"/dp/{asin_match.group(1).upper()}",
                    )
                )
        return normalized_url
