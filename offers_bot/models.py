from __future__ import annotations

from typing import Protocol

from backend.app.core.affiliate_link import AffiliateLink

__all__ = ["AffiliateLink", "ProductUrlResolver"]


class ProductUrlResolver(Protocol):
    def resolve(self, url: str) -> str | None: ...

    def get_image(self, url: str) -> str | None: ...
