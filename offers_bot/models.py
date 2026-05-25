from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProductUrlResolver(Protocol):
    def resolve(self, url: str) -> str | None: ...

    def get_image(self, url: str) -> str | None: ...


@dataclass(frozen=True)
class AffiliateLink:
    short_url: str
    long_url: str | None
    origin_url: str
    raw_text: str | None
    product_key: str
    image_url: str | None = None
