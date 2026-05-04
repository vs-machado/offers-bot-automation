from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


MELI_SHORT_RE = re.compile(r"https?://meli\.la/[A-Za-z0-9]{7}", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
ML_HOST_RE = re.compile(r"(^|\.)mercadolivre\.com\.br$|(^|\.)meli\.la$", re.IGNORECASE)
ML_ID_RE = re.compile(r"\bMLB\d{6,13}\b", re.IGNORECASE)
PRICE_RE = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)", re.IGNORECASE)
PROMO_PRICE_RE = re.compile(r"\bpor\s+R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+(?:,\d{2})?)", re.IGNORECASE)
COUPON_RE = re.compile(
    r"(?:^|\n)\s*(?:[^\w\s]\s*)*(?:[🎟️]\s*)?(?:usem?\s+o\s+)?cupom\s*:\s*([^\s\n]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Offer:
    original_text: str
    url: str
    title: str | None
    price: str | None
    coupon: str | None


def extract_offers(text: str) -> list[Offer]:
    offers: list[Offer] = []
    seen_urls: set[str] = set()
    for url in [*MELI_SHORT_RE.findall(text), *URL_RE.findall(text)]:
        clean_url = clean_offer_url(url)
        if not is_mercado_livre_url(clean_url):
            continue
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)
        offers.append(
            Offer(
                original_text=text.strip(),
                url=clean_url,
                title=extract_title(text),
                price=extract_price(text),
                coupon=extract_coupon(text),
            )
        )
    return offers


def clean_offer_url(url: str) -> str:
    clean_url = url.rstrip(".,;:!?)\"]}'")
    parsed = urlparse(clean_url)
    if parsed.netloc.lower() == "meli.la":
        short_id_match = re.match(r"/([A-Za-z0-9]{7})", parsed.path)
        if short_id_match:
            return f"{parsed.scheme}://{parsed.netloc}/{short_id_match.group(1)}"
    return clean_url


def is_mercado_livre_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return bool(parsed.netloc and ML_HOST_RE.search(parsed.netloc))


def extract_ml_ids(text: str) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for match in ML_ID_RE.findall(text):
        item_id = match.upper()
        if item_id not in seen:
            ids.append(item_id)
            seen.add(item_id)
    return ids


def extract_title(text: str) -> str | None:
    for line in text.splitlines():
        line = URL_RE.sub("", line).strip()
        line = PRICE_RE.sub("", line).replace("R$", "").strip(" -:|")
        if line:
            return line[:180]
    return None


def extract_price(text: str) -> str | None:
    match = PROMO_PRICE_RE.search(text) or PRICE_RE.search(text)
    if not match:
        return None
    return f"R$ {match.group(1)}"


def extract_coupon(text: str) -> str | None:
    match = COUPON_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()
