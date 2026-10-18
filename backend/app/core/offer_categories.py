"""Shared category semantics for ingestion and destination delivery rules."""

from typing import Literal

OfferCategory = Literal["tech", "home", "clothes", "other", "coupon"]
OFFER_CATEGORIES = ("tech", "home", "clothes", "other", "coupon")


def offer_category(result: dict | None) -> str:
    """Keep generic coupons separate; unclassified products fall back to other."""
    result = result or {}
    if result.get("classification") == "coupon":
        return "coupon"
    category = result.get("category")
    return category if category in OFFER_CATEGORIES[:-1] else "other"


def accepts_category(categories: list[str] | None, category: str) -> bool:
    """Null accepts all offers; an empty selection accepts none."""
    return categories is None or category in categories
