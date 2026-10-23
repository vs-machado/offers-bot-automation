"""Dependency-free Awin contract shared by the API and affiliate worker."""

import re
from urllib.parse import urlparse

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


def valid_credentials(publisher_id: object, access_token: object) -> bool:
    """Validate normalized IDs and header-safe tokens without network requests."""
    return bool(
        valid_publisher_id(publisher_id)
        and isinstance(access_token, str)
        and access_token
        and access_token.isascii()
        and not any(char.isspace() for char in access_token)
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
