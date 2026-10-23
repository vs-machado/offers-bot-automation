"""Compatibility exports for the Magalu integration shared with the API."""

from backend.app.core.magalu import (
    CHANNEL_UTMS,
    MAGALU_ENDPOINT,
    PRODUCT_HOSTS,
    SAMPLE_PRODUCT_URL,
    SHORT_HOSTS,
    MagaluClient,
    MagaluError,
    httpx,
    is_magalu_url,
    resolve_product_url,
    valid_config,
    valid_url,
)

__all__ = [
    "CHANNEL_UTMS",
    "MAGALU_ENDPOINT",
    "PRODUCT_HOSTS",
    "SAMPLE_PRODUCT_URL",
    "SHORT_HOSTS",
    "MagaluClient",
    "MagaluError",
    "httpx",
    "is_magalu_url",
    "resolve_product_url",
    "valid_config",
    "valid_url",
]
