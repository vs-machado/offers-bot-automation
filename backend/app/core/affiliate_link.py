"""Affiliate conversion result shared by provider clients and posting workers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AffiliateLink:
    short_url: str
    long_url: str | None
    origin_url: str
    raw_text: str | None
    product_key: str
    image_url: str | None = None
