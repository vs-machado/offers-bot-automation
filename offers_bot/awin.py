"""Awin Link Builder integration for KaBuM offers."""

import re
from urllib.parse import urlparse, urlunparse

import httpx

from .models import AffiliateLink
from .parser import is_kabum_url

# https://ui.awin.com/merchant-profile/17729
KABUM_ADVERTISER_ID = 17729
AWIN_LINK_DOMAINS = ("www.awin1.com", "awin1.com", "tidd.ly")


def valid_publisher_id(value: object) -> bool:
    """Accept only positive int64 IDs, safe for interpolation in Awin API paths."""
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9]{1,19}", value) is not None
        and 0 < int(value) <= 9223372036854775807
    )


def link_endpoint(publisher_id: str) -> str:
    """Build the fixed Awin endpoint, rejecting invalid publisher IDs."""
    if not valid_publisher_id(publisher_id):
        raise ValueError("Invalid Awin publisherId")
    return f"https://api.awin.com/publishers/{publisher_id}/linkbuilder/generate"


def is_tracking_link(value: object) -> bool:
    """Recognize HTTPS tracking links returned by Awin, without visiting them."""
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname in AWIN_LINK_DOMAINS
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


class AwinClient:
    def __init__(self, publisher_id: str = "", access_token: str = "") -> None:
        self._publisher_id = publisher_id.strip()
        self._access_token = access_token.strip()

    def ready(self) -> bool:
        return bool(
            valid_publisher_id(self._publisher_id)
            and self._access_token
            and self._access_token.isascii()
            and not any(char.isspace() for char in self._access_token)
        )

    def create_link(self, url: str) -> AffiliateLink:
        """Generate a KaBuM tracking link; reject missing credentials or invalid output.

        Product IDs provide stable deduplication across slugs and tracking queries.
        Tokens travel only in the Authorization header, never in request URLs.
        """
        if not self.ready():
            raise RuntimeError("Awin credentials missing or invalid")
        if not is_kabum_url(url):
            raise ValueError("Awin integration supports only KaBuM URLs")
        parsed = urlparse(url)
        destination = urlunparse(parsed._replace(fragment=""))
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(
                link_endpoint(self._publisher_id),
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={
                    "advertiserId": KABUM_ADVERTISER_ID,
                    "destinationUrl": destination,
                    "shorten": True,
                },
            )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError("Awin API returned invalid JSON") from None
        if not isinstance(data, dict) or not is_tracking_link(data.get("url")):
            raise RuntimeError("Awin API failed to generate a tracking link")
        short_url = data.get("shortUrl")
        if short_url and not is_tracking_link(short_url):
            raise RuntimeError("Awin API returned an invalid short link")
        product = re.search(r"/produto/(\d+)(?:/|$)", parsed.path, re.IGNORECASE)
        identity = (
            product.group(1)
            if product
            else urlunparse(parsed._replace(query="", fragment=""))
        )
        return AffiliateLink(
            short_url=short_url or data["url"],
            long_url=data["url"],
            origin_url=url,
            raw_text=None,
            product_key=f"KABUM:{identity}",
        )
