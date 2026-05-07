from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


MELI_SHORT_RE = re.compile(r"https?://meli\.la/[A-Za-z0-9]{7}", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
ML_HOST_RE = re.compile(r"(^|\.)mercadolivre\.com\.br$|(^|\.)meli\.la$", re.IGNORECASE)
AMAZON_HOST_RE = re.compile(r"(^|\.)amazon\.com\.br$|(^|\.)amzn\.to$", re.IGNORECASE)
SHOPEE_HOST_RE = re.compile(
    r"(^|\.)shopee\.com\.br$|(^|\.)s\.shopee\.com\.br$", re.IGNORECASE
)
ALIEXPRESS_HOST_RE = re.compile(
    r"(^|\.)aliexpress\.com$|(^|\.)aliexpress\.com\.br$|(^|\.)s\.click\.aliexpress\.com$",
    re.IGNORECASE,
)
ML_ID_RE = re.compile(r"\bMLB-?\d{6,13}\b", re.IGNORECASE)
SHOPEE_ID_RE = re.compile(
    r"-i\.(\d+)\.(\d+)(?:[/?#]|$)|/opaanlp/(\d+)/(\d+)(?:[/?#]|$)", re.IGNORECASE
)
PRICE_RE = re.compile(r"R\$\s?((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)", re.IGNORECASE)
PROMO_PRICE_RE = re.compile(
    r"\bpor\s*:?\s*R\$\s*((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)", re.IGNORECASE
)
INSTALLMENT_RE = re.compile(
    r"\b(\d{1,2})\s*x\s*(?:de\s+(?:R\$\s*)?[\d.,]+\s+)?sem\s+juros\b", re.IGNORECASE
)
FREE_SHIPPING_RE = re.compile(
    r"\bfrete\s+gr[áa]tis(?:\s+para\s+[A-Za-zÀ-ÿ\s]+)?\b", re.IGNORECASE
)
COUPON_RE = re.compile(
    r"(?:^|\n)\s*(?:[^\w\s]\s*)*(?:[🎟️]\s*)?(?:usem?\s+o\s+)?cupom\s*:\s*([^\s\n]+)",
    re.IGNORECASE,
)
INLINE_COUPON_RE = re.compile(
    r"(?:^|\s|-)(?:usem?\s+o\s+)?cupom\s*:\s*[^\s\n]+", re.IGNORECASE
)
COUPON_CODE_RE = re.compile(r"\*+([A-Za-z0-9]{4,})\*+|\b([A-Za-z0-9]{4,})\b")
MELI_PLUS_RE = re.compile(
    r"\bmeli\+\b|clientes?\s+meli\+|assinantes?\s+meli\+", re.IGNORECASE
)
LEADING_NOISE_RE = re.compile(
    r"^(?:[^\w\n]*)(?:(?:ainda\s+ativo|ativo|aproveita|imperd[ií]vel|oferta|promo[cç][aã]o|corre|urgente)\b[!:\-\s]*)+",
    re.IGNORECASE,
)
TRAILING_NOISE_RE = re.compile(
    r"(?:\s*[-|]\s*)?(?:an[uú]ncio|link\s+do\s+produto|compre\s+aqui|produto|oferta)\s*$",
    re.IGNORECASE,
)
TITLE_TOKEN_RE = re.compile(
    r"\b(?:[A-Za-z]+\d+[A-Za-z\d-]*|\d+(?:[\.,]\d+)?(?:gb|tb|hz|ml|pol|w|v)|i[3579]-\d+[A-Za-z]*|rtx\s*\d{3,4}|ssd|notebook|smartphone|gamer|full\s*hd|oled|intel|amd|nvidia|lenovo|samsung|apple|motorola|philips|electrolux|brastemp|consul|asus|acer|dell|vaio)\b",
    re.IGNORECASE,
)
NOISE_LINE_RE = re.compile(
    r"\b(?:cupom|link\s+do\s+produto|compre\s+aqui|an[uú]ncio|assinantes|ativo|aproveita|imperd[ií]vel|corre|promo[cç][aã]o|cuide\s+tamb[ée]m|o\s+que\s+voc[êe]\s+achou|amiguinhos?|patas)\b",
    re.IGNORECASE,
)
PROMO_LINE_RE = re.compile(
    r"\b(?:hoje|amanh[aã]|come[cç]a|comeca|carrinho|oferta(?:s)?|prepara|tempo\s+limitado|pre[cç]o\s+baixo|loja\s+oficial|entrega\s+full|v[aá]lido)\b|\b\d{1,2}h\b|\b\d{1,2}\.\d{1,2}\b",
    re.IGNORECASE,
)
COUPON_STATUS_RE = re.compile(
    r"\b(?:esgot\w*|acab\w*|encerr\w*|expir\w*|ativo\w*)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Offer:
    original_text: str
    url: str
    title: str | None
    price: str | None
    installment_info: str | None
    shipping_info: str | None
    coupon: str | None
    meli_plus_only: bool


def extract_offers(text: str) -> list[Offer]:
    offers: list[Offer] = []
    seen_urls: set[str] = set()
    for url in [*MELI_SHORT_RE.findall(text), *URL_RE.findall(text)]:
        clean_url = clean_offer_url(url)
        if not is_supported_offer_url(clean_url):
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
                installment_info=extract_installment_info(text),
                shipping_info=extract_shipping_info(text),
                coupon=extract_coupon(text),
                meli_plus_only=is_meli_plus_only(text),
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


def is_amazon_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return bool(parsed.netloc and AMAZON_HOST_RE.search(parsed.netloc))


def is_shopee_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return bool(parsed.netloc and SHOPEE_HOST_RE.search(parsed.netloc))


def is_aliexpress_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return bool(parsed.netloc and ALIEXPRESS_HOST_RE.search(parsed.netloc))


def is_shopee_product_url(url: str) -> bool:
    return is_shopee_url(url) and bool(SHOPEE_ID_RE.search(url))


def is_supported_offer_url(url: str) -> bool:
    return (
        is_mercado_livre_url(url)
        or is_amazon_url(url)
        or is_shopee_url(url)
        or is_aliexpress_url(url)
    )


def extract_ml_ids(text: str) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for match in ML_ID_RE.findall(text):
        item_id = match.upper().replace("-", "")
        if item_id not in seen:
            ids.append(item_id)
            seen.add(item_id)
    return ids


def extract_shopee_ids(text: str) -> tuple[str, str] | None:
    match = SHOPEE_ID_RE.search(text)
    if not match:
        return None
    return match.group(1) or match.group(3), match.group(2) or match.group(4)


def extract_title(text: str) -> str | None:
    best_title = None
    best_score = float("-inf")
    for raw_line in text.splitlines():
        line = clean_title_candidate(raw_line)
        if not line:
            continue
        score = score_title_candidate(line)
        if score > best_score:
            best_score = score
            best_title = line[:180]
    return best_title if best_score >= 0 else None


def clean_title_candidate(text: str) -> str:
    line = URL_RE.sub("", text)
    line = INLINE_COUPON_RE.sub("", line)

    # Also remove common promo noise that stays after regex
    lower_line = line.lower()
    if "cupom" in lower_line or "maes" in lower_line or "moedas" in lower_line:
        line = ""

    line = PRICE_RE.sub("", line).replace("R$", "")
    line = INSTALLMENT_RE.sub("", line)
    line = TRAILING_NOISE_RE.sub("", line)
    previous = None
    while line != previous:
        previous = line
        line = LEADING_NOISE_RE.sub("", line).strip()
        line = TRAILING_NOISE_RE.sub("", line).strip()
    line = re.sub(r"^[^\wÀ-ÿ]+", "", line)
    line = re.sub(r"[^\wÀ-ÿ]+$", "", line)
    return re.sub(r"\s+", " ", line).strip(" -:|!\t")


def score_title_candidate(line: str) -> int:
    score = 0
    length = len(line)

    if 25 <= length <= 180:
        score += 4
    elif 12 <= length < 25:
        score += 1
    else:
        score -= 3

    if "," in line:
        score += 3
    if re.search(r"\d", line):
        score += 2

    token_hits = TITLE_TOKEN_RE.findall(line)
    score += min(len(token_hits), 6) * 2

    uppercase_words = re.findall(r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{4,}\b", line)
    if uppercase_words and len(uppercase_words) >= max(2, len(line.split()) // 2):
        score -= 4

    if NOISE_LINE_RE.search(line):
        score -= 6

    if PROMO_LINE_RE.search(line):
        score -= 8

    if re.fullmatch(r"[^A-Za-zÀ-ÿ0-9]*", line):
        score -= 10

    return score


def extract_price(text: str) -> str | None:
    for line in text.splitlines():
        promo_match = PROMO_PRICE_RE.search(line)
        if not promo_match:
            continue
        price = f"R$ {promo_match.group(1)}"
        if "pix" in line.lower():
            return f"{price} no PIX"
        return price

    match = PRICE_RE.search(text)
    if not match:
        return None

    # Standardize spacing to "R$ XXX"
    return f"R$ {match.group(1)}"


def extract_installment_info(text: str) -> str | None:
    match = INSTALLMENT_RE.search(text)
    if not match:
        return None
    return f"{match.group(1)}X SEM JUROS"


def extract_shipping_info(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -:|!\t")
        if not line:
            continue
        match = FREE_SHIPPING_RE.search(line)
        if not match:
            continue
        start = match.start()
        return line[start:]
    return None


def extract_coupon(text: str) -> str | None:
    best_coupon = None
    best_score = float("-inf")

    for line in text.splitlines():
        lower_line = line.lower()
        if "cupom" not in lower_line and "maes" not in lower_line:
            continue

        # If line has "cupom", take everything after it.
        # If not (but has "maes"), take the whole line.
        if "cupom" in lower_line:
            coupon_segment = line[lower_line.index("cupom") :]
        else:
            coupon_segment = line

        codes = extract_coupon_codes(URL_RE.sub("", coupon_segment))
        if codes:
            score = 0
            if ":" in coupon_segment:
                score += 4
            if re.search(r"\busem?\b", line, re.IGNORECASE):
                score += 2
            if any(any(char.isdigit() for char in code) for code in codes):
                score += 2
            if " ou " in coupon_segment.lower():
                score += 1
            if COUPON_STATUS_RE.search(coupon_segment):
                score -= 5
            if score > best_score:
                best_score = score
                best_coupon = " ou ".join(codes)

    if best_coupon and best_score >= 0:
        return best_coupon

    match = COUPON_RE.search(text)
    if not match:
        return None
    codes = extract_coupon_codes(match.group(1))
    if not codes:
        return None
    return " ou ".join(codes)


def extract_coupon_codes(text: str) -> list[str]:
    ignored_tokens = {
        "CUPOM",
        "CUPONS",
        "USE",
        "USEM",
        "O",
        "OU",
        "PARA",
        "CLIENTE",
        "CLIENTES",
        "ASSINANTE",
        "ASSINANTES",
        "EXCLUSIVO",
        "EXCLUSIVA",
        "MELI",
    }
    codes: list[str] = []
    seen: set[str] = set()
    for match in COUPON_CODE_RE.finditer(text):
        code = (match.group(1) or match.group(2) or "").upper()
        if not code or code in ignored_tokens:
            continue
        if any(char.isdigit() for char in code) or len(code) >= 8:
            if code not in seen:
                codes.append(code)
                seen.add(code)
    return codes


def is_meli_plus_only(text: str) -> bool:
    return bool(MELI_PLUS_RE.search(text))
