"""HTTP-only Magalu affiliate generation and bounded short-link resolution."""

import logging
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

from .affiliate_link import AffiliateLink

LOGGER = logging.getLogger(__name__)
MAGALU_ENDPOINT = (
    "https://magalu-copilot-sdk-671556449740."
    "southamerica-east1.run.app/api/v1/links/generate"
)
PRODUCT_HOSTS = frozenset(
    {
        "www.magazineluiza.com.br",
        "magazineluiza.com.br",
        "www.magazinevoce.com.br",
        "magazinevoce.com.br",
    }
)
SHORT_HOSTS = frozenset(
    {
        "cutt.ly",
        "www.cutt.ly",
        "bit.ly",
        "tinyurl.com",
        "www.tinyurl.com",
        "t.co",
        "rb.gy",
        "magazineluiza.onelink.me",
        "divulgador.magalu.com",
    }
)
CHANNEL_UTMS = {
    "lucreator": ("lucreator", "link_afiliado"),
    "whatsapp": ("whatsapp", "compartilhamento_social"),
}
SAMPLE_PRODUCT_URL = (
    "https://www.magazineluiza.com.br/celular-samsung-galaxy-a07-128gb-preto-"
    "4gb-ram-tela-67-cam-dupla-selfie-8mp/p/240466500/te/ga07/"
    "?seller_id=magazineluiza"
)


class MagaluError(RuntimeError):
    """A bounded Magalu operation failed; message is safe for internal logs."""


def valid_url(value: object, hosts: frozenset[str]) -> bool:
    try:
        if (
            not isinstance(value, str)
            or len(value) > 8192
            or any(ord(char) < 33 for char in value)
        ):
            return False
        parsed = urlparse(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname in hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def valid_config(partner_id: str, promoter_id: str, store_name: str) -> bool:
    return bool(
        re.fullmatch(r"[0-9]{1,20}", partner_id)
        and re.fullmatch(r"[0-9]{1,20}", promoter_id)
        and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", store_name)
    )


def is_magalu_url(url: str) -> bool:
    return valid_url(
        url, PRODUCT_HOSTS | {"magazineluiza.onelink.me", "divulgador.magalu.com"}
    )


def resolve_product_url(url: str) -> str:
    """Follow at most five approved HTTPS redirects, never arbitrary destinations.

    Stream responses to avoid downloading product pages. Each hop is validated
    before requesting it; errors never fall back to another account's link.
    """
    if valid_url(url, PRODUCT_HOSTS):
        return url
    if not valid_url(url, SHORT_HOSTS):
        raise ValueError("Unsupported Magalu destination")
    deadline = time.monotonic() + 15
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        for hop in range(6):
            if not valid_url(url, PRODUCT_HOSTS | SHORT_HOSTS):
                raise ValueError("Unsupported Magalu destination")
            if valid_url(url, PRODUCT_HOSTS):
                return url
            if hop == 5:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MagaluError("Magalu redirect timeout")
            with client.stream("GET", url, timeout=min(10, remaining)) as response:
                location = response.headers.get("location")
                if response.is_redirect and location:
                    url = urljoin(url, location)
                else:
                    response.raise_for_status()
                    raise MagaluError("Short link did not redirect to a Magalu product")
    raise MagaluError("Magalu redirect limit exceeded")


class MagaluClient:
    def __init__(
        self,
        partner_id: str = "",
        promoter_id: str = "",
        store_name: str = "",
        utm_campaign: str = "divulgacao_influencer",
    ) -> None:
        self._ids = {
            "partner_id": partner_id.strip(),
            "promoter_id": promoter_id.strip(),
            "store_name": store_name.strip(),
        }
        self._campaign = utm_campaign.strip() or "divulgacao_influencer"

    def ready(self) -> bool:
        return valid_config(**self._ids) and len(self._campaign) <= 100

    def generate(self, url: str, channel: str = "lucreator") -> dict:
        """Generate once, replacing previous attribution and validating provider output.

        No POST retries or manually constructed affiliate fallback. Returns product
        metadata unchanged, after validating links and account/channel attribution.
        """
        if not self.ready():
            raise ValueError("Magalu configuration missing or invalid")
        if channel not in CHANNEL_UTMS:
            raise ValueError("Unsupported Magalu channel")
        url = resolve_product_url(url)
        parsed = urlparse(url)
        # Magazine Você prefixes product paths with the originating storefront.
        path = parsed.path
        if parsed.hostname in {"www.magazinevoce.com.br", "magazinevoce.com.br"}:
            path = re.sub(r"^/magazine[^/]+/", "/", path)
        product = re.search(r"/p/([A-Za-z0-9]+)(?:/|$)", path)
        if not product:
            raise ValueError("Magalu product URL required")
        source, medium = CHANNEL_UTMS[channel]
        tracking = {
            **self._ids,
            "utm_campaign": self._campaign,
            "utm_source": source,
            "utm_medium": medium,
        }
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in tracking
        ]
        query.extend(tracking.items())
        destination = urlunparse(
            ("https", "www.magazineluiza.com.br", path, "", urlencode(query), "")
        )
        started = time.monotonic()
        status = None
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                response = client.post(
                    MAGALU_ENDPOINT,
                    params=self._ids,
                    json={**tracking, "url": destination},
                    headers={"Accept": "application/json"},
                )
                status = response.status_code
                response.raise_for_status()
                data = response.json()
            if not isinstance(data, dict) or data.get("status") != "success":
                raise MagaluError("Magalu did not generate an affiliate link")
            if not valid_url(
                data.get("affiliate_url"), PRODUCT_HOSTS | {"magazineluiza.onelink.me"}
            ):
                raise MagaluError("Magalu returned an invalid affiliate link")
            for key, hosts in (
                ("shortlink_url", PRODUCT_HOSTS | {"magazineluiza.onelink.me"}),
                ("web_affiliate_url", PRODUCT_HOSTS),
                ("canonical_product_url", PRODUCT_HOSTS),
                ("image_url", frozenset({"a-static.mlcdn.com.br"})),
            ):
                if data.get(key) and not valid_url(data[key], hosts):
                    raise MagaluError("Magalu returned an invalid metadata URL")
            if any(str(data.get(key, "")) != value for key, value in self._ids.items()):
                raise MagaluError("Magalu returned mismatched account identifiers")
            web = data.get("web_affiliate_url")
            if web:
                returned = dict(parse_qsl(urlparse(web).query))
                if any(
                    returned.get(key) != value
                    for key, value in tracking.items()
                    if key != "store_name"
                ):
                    raise MagaluError("Magalu returned mismatched attribution")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            error = MagaluError("Magalu generation request failed")
            error.reason_code = (
                {
                    401: "affiliate_authentication",
                    403: "affiliate_permission",
                    429: "affiliate_rate_limit",
                }.get(status, "affiliate_api")
                if not isinstance(exc, httpx.RequestError)
                else "connection_failure"
            )
            raise error from exc
        finally:
            LOGGER.info(
                "Magalu generation status=%s elapsed_ms=%d",
                status,
                (time.monotonic() - started) * 1000,
            )

    def create_link(self, url: str) -> AffiliateLink:
        """Adapt generated link to posting/deduplication without using API prices."""
        data = self.generate(url)
        canonical = data.get("canonical_product_url") or data.get("web_affiliate_url")
        identity = data.get("sku") or data.get("navigation_id")
        if not identity:
            raise MagaluError("Magalu returned no product identity")
        seller = data.get("seller_id") or dict(
            parse_qsl(urlparse(canonical or "").query)
        ).get("seller_id", "")
        return AffiliateLink(
            short_url=data["affiliate_url"],
            long_url=data.get("web_affiliate_url"),
            origin_url=url,
            raw_text=None,
            product_key=f"MAGALU:{identity}:{seller}",
            image_url=data.get("image_url"),
        )
