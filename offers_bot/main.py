from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import tempfile
import httpx

from .amazon import AmazonClient
from .aliexpress import AliExpressClient
from .config import load_settings
from .browser_resolver import PlaywrightProductResolver
from .mercado_livre import MercadoLivreClient, UnsupportedOfferError
from .parser import (
    Offer,
    URL_RE,
    extract_coupon_codes,
    extract_offers_async,
    is_amazon_url,
    is_mercado_livre_url,
    is_shopee_url,
    is_aliexpress_url,
)
from .shopee import ShopeeClient
from .store import OfferStore
from .telegram_bot import TelegramOfferBot


AMAZON_COUPON_HEADER_RE = re.compile(r"\bcup(?:om|ons)\s+amazon\b", re.IGNORECASE)
ML_COUPON_HEADER_RE = re.compile(r"\bcup(?:om|ons)\s+mercado\s+livre\b", re.IGNORECASE)
SHOPEE_COUPON_HEADER_RE = re.compile(r"\bcup(?:om|ons)\b.*\bshopee\b", re.IGNORECASE)
ALIEXPRESS_COUPON_HEADER_RE = re.compile(
    r"\bcup(?:om|ons)\b.*\baliexpress\b", re.IGNORECASE
)
NOVO_ML_COUPON_RE = re.compile(r"\bnovo\s+cupom\s+mercado\s+livre\b", re.IGNORECASE)
DETAIL_AND_CODE_RE = re.compile(r"(.+?)\s*:\s*([A-Za-z0-9]{4,})\s*$", re.IGNORECASE)
CODE_LABEL_RE = re.compile(
    r"\b(?:c[oó]digo|cupom)\b\s*:\s*([A-Za-z0-9]{4,})", re.IGNORECASE
)
RESGATE_ANUNCIO_RE = re.compile(
    r"\bresgate\s+(?:o\s+)?(?:cupom\s+)?(?:do|no)?\s*an[uú]ncio\b",
    re.IGNORECASE,
)


def _normalize_money_spacing(text: str) -> str:
    return re.sub(r"R\$\s*(\d)", r"R$ \1", text)


def _normalize_coupon_detail(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip(" -:|!\t")
    return _normalize_money_spacing(clean)


DISCOUNT_LINE_RE = re.compile(r"\d+%\s*(?:OFF|desconto)", re.IGNORECASE)
R_DISCOUNT_LINE_RE = re.compile(r"R\$\s*\d+(?:[\d.,]*)\s+OFF", re.IGNORECASE)


def _is_generic_coupon_bulletin(offer: Offer, text: str) -> bool:
    if not offer.coupon or "cupom" not in text.lower():
        return False

    # Check parsed title for discount patterns
    if offer.title:
        if DISCOUNT_LINE_RE.search(offer.title):
            return True
        if "%" in offer.title and re.search(
            r"(?:acima|limitado)", offer.title, re.IGNORECASE
        ):
            return True
        if R_DISCOUNT_LINE_RE.search(offer.title):
            return True

    # Check raw text for discount patterns
    for raw_line in text.splitlines():
        line = re.sub(r"^[^\w\dR$%]+", "", raw_line).strip()
        if not line:
            continue
        if DISCOUNT_LINE_RE.search(line):
            return True
        if R_DISCOUNT_LINE_RE.search(line):
            return True
        if re.search(r"\d+%\s*OFF", line, re.IGNORECASE):
            return True

    return False


MOEDAS_RE = re.compile(r"\s*\+\s*moedas?\s*$", re.IGNORECASE)
COUPON_SUFFIX_RE = re.compile(
    r"\s*\+\s*(?:(?:\d+|[\d.,]+)\s+)?(?:moedas?|resgate\b).*$",
    re.IGNORECASE,
)


def _wrap_coupons_in_text(text: str) -> str:
    def _process_line(m: re.Match) -> str:
        prefix = m.group(1)
        content = m.group(2)
        return prefix + wrap_coupon_codes(content)

    text = re.sub(
        r"((?:cup(?:om|ons)?\s*[:：]?\s*)|(?:.*?(?:off|desconto).*?)\s*[:：]\s*)([^\n]+)",
        _process_line,
        text,
        flags=re.IGNORECASE,
    )
    return text


def wrap_coupon_codes(coupon_text: str) -> str:
    if not coupon_text:
        return ""
    suffix = ""
    m = COUPON_SUFFIX_RE.search(coupon_text)
    if m:
        suffix = coupon_text[m.start() :]
        coupon_text = coupon_text[: m.start()]
    coupon_text = coupon_text.strip()
    coupon_text = re.sub(r"[`*]+", "", coupon_text)

    codes = extract_coupon_codes(coupon_text)
    if codes:
        result = coupon_text
        for code in codes:
            result = result.replace(code, f"`{code}`")
        return result + suffix

    m = MOEDAS_RE.search(coupon_text)
    if m:
        suffix = coupon_text[m.start() :]
        coupon_text = coupon_text[: m.start()]
    parts = [p.strip() for p in re.split(r"\s+(?:ou|e)\s+|\s*\+\s*", coupon_text)]
    return " ou ".join(f"`{p}`" for p in parts if p) + suffix


def _format_generic_coupon(offer: Offer, affiliate_url: str, text: str) -> str:
    discount_line = ""
    for raw_line in text.splitlines():
        line = re.sub(r"^[^\w\dR$%]+", "", raw_line).strip()
        if not line:
            continue
        if DISCOUNT_LINE_RE.search(line):
            discount_line = URL_RE.sub("", line).strip()
            break
        if R_DISCOUNT_LINE_RE.search(line):
            discount_line = URL_RE.sub("", line).strip()
            break
    if not discount_line:
        discount_line = offer.title or ""
    parts = [
        discount_line,
        f"🎟️ Cupom: {wrap_coupon_codes(offer.coupon)}",
        f"🔗 {affiliate_url}",
    ]
    return "\n\n".join(p for p in parts if p)


def extract_resgate_anuncio_note(text: str) -> str | None:
    match = RESGATE_ANUNCIO_RE.search(text)
    if not match:
        return None
    note = re.sub(r"\s+", " ", match.group(0)).strip(" -:|!\t")
    note = note[0].upper() + note[1:].lower()
    return note


def _format_novo_ml_coupon(offer: Offer, affiliate_url: str, text: str) -> str:
    discount_line = ""
    coupon_code = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "⚠️" in line or "*" in line:
            continue

        if "▪️" in line:
            discount_line = line.replace("▪️", "🤑").strip()
            discount_line = URL_RE.sub("", discount_line).strip()
        elif not discount_line and "%" in line and "OFF" in line.upper():
            clean = re.sub(r"^[^\w\dR$%]+", "", line).strip()
            if clean:
                discount_line = URL_RE.sub("", clean).strip()

        if "cupom" in line.lower() and ":" in line:
            code_match = CODE_LABEL_RE.search(line)
            if code_match:
                coupon_code = code_match.group(1).upper()

    if not coupon_code and offer.coupon:
        coupon_code = offer.coupon

    parts = []
    if discount_line:
        parts.append(discount_line)
    if coupon_code:
        parts.append(f"🎟️ Cupom: {wrap_coupon_codes(coupon_code)}")
    parts.append(f"🔗 {affiliate_url}")

    return "\n\n".join(parts)


def format_coupon_bulletin_offer(offer: Offer, affiliate_url: str) -> str | None:
    text = offer.original_text
    is_amazon_coupon = bool(AMAZON_COUPON_HEADER_RE.search(text))
    is_ml_coupon = bool(ML_COUPON_HEADER_RE.search(text))
    is_shopee_coupon = bool(SHOPEE_COUPON_HEADER_RE.search(text))
    is_aliexpress_coupon = bool(ALIEXPRESS_COUPON_HEADER_RE.search(text))

    if is_amazon_coupon or is_ml_coupon:
        if is_ml_coupon and NOVO_ML_COUPON_RE.search(text):
            return _format_novo_ml_coupon(offer, affiliate_url, text)

        coupon_lines: list[str] = []
        pending_detail: str | None = None
        for raw_line in text.splitlines():
            line = re.sub(r"^[^\w\dR$%]+", "", raw_line).strip()
            if not line:
                continue

            detail_and_code = DETAIL_AND_CODE_RE.match(line)
            if detail_and_code and (
                "%" in detail_and_code.group(1) or "R$" in detail_and_code.group(1)
            ):
                detail = _normalize_coupon_detail(detail_and_code.group(1))
                detail = URL_RE.sub("", detail).strip()
                code = detail_and_code.group(2).upper()
                coupon_lines.append(f"🎟 {detail}: {wrap_coupon_codes(code)}")
                pending_detail = None
                continue

            if DISCOUNT_LINE_RE.search(line) or R_DISCOUNT_LINE_RE.search(line):
                pending_detail = _normalize_coupon_detail(line.rstrip(":"))
                pending_detail = URL_RE.sub("", pending_detail).strip()
                continue

            code_match = CODE_LABEL_RE.search(line)
            if code_match:
                code = code_match.group(1).upper()
                if pending_detail:
                    coupon_lines.append(
                        f"🎟 {pending_detail}: {wrap_coupon_codes(code)}"
                    )
                    pending_detail = None
                else:
                    coupon_lines.append(f"🎟 Cupom: {wrap_coupon_codes(code)}")

        if not coupon_lines and offer.coupon and is_amazon_coupon:
            coupon_lines.append(f"🎟 Cupom: {wrap_coupon_codes(offer.coupon)}")

        if coupon_lines:
            title = (
                "☑️ Cupom Amazon!" if is_amazon_coupon else "🔥 Cupons Mercado Livre!"
            )
            return "\n\n".join(
                [
                    title,
                    "\n".join(coupon_lines),
                    f"🛒 Resgate aqui: {affiliate_url}",
                ]
            )

    if is_shopee_coupon or is_aliexpress_coupon:
        lines_output: list[str] = []
        for raw_line in text.splitlines():
            line = re.sub(r"^[^\w\dR$%]+", "", raw_line).strip()
            if not line:
                continue
            detail_and_code = DETAIL_AND_CODE_RE.match(line)
            if detail_and_code and (
                "%" in detail_and_code.group(1) or "R$" in detail_and_code.group(1)
            ):
                detail = _normalize_coupon_detail(detail_and_code.group(1))
                detail = URL_RE.sub("", detail).strip()
                code = detail_and_code.group(2).upper()
                lines_output.append(f"🎟 {detail}: {wrap_coupon_codes(code)}")
        if lines_output:
            title = "☑️ Cupom Shopee!" if is_shopee_coupon else "☑️ Cupom AliExpress!"
            return "\n\n".join(
                [
                    title,
                    "\n".join(lines_output),
                    f"🔗 {affiliate_url}",
                ]
            )

    if _is_generic_coupon_bulletin(offer, text):
        return _format_generic_coupon(offer, affiliate_url, text)

    return None


def format_llm_offer(offer: Offer, affiliate_url: str) -> str:
    if not offer.llm_result:
        return ""

    llm = offer.llm_result
    classification = llm.get("classification")

    if classification == "coupon":
        coupon_data = llm.get("coupon", {})
        if not isinstance(coupon_data, dict):
            coupon_data = {}
        platform = coupon_data.get("platform", "Generic")
        novo_ml = coupon_data.get("novo_ml_format", False)
        coupons = coupon_data.get("coupons", [])

        if platform == "Amazon":
            title = "☑️ Cupom Amazon!"
            lines = []
            for c in coupons:
                detail = c.get("detail", "")
                code = c.get("code", "")
                if detail and code:
                    detail_clean = re.sub(r"\s+", " ", detail).strip(" -:|!\t")
                    detail_clean = re.sub(r"R\$\s*(\d)", r"R$ \1", detail_clean)
                    lines.append(f"🎟 {detail_clean}: {wrap_coupon_codes(code)}")
            if lines:
                return (
                    f"{title}\n\n"
                    + "\n".join(lines)
                    + f"\n\n🛒 Resgate aqui: {affiliate_url}"
                )

        elif platform == "Mercado Livre":
            if novo_ml:
                detail = coupons[0].get("detail", "") if coupons else ""
                code = coupons[0].get("code", "") if coupons else ""
                detail_clean = re.sub(r"\s+", " ", detail).strip(" -:|!\t")
                detail_clean = re.sub(r"R\$\s*(\d)", r"R$ \1", detail_clean)
                if detail_clean.startswith("▪️"):
                    detail_clean = detail_clean.replace("▪️", "🤑").strip()
                elif not detail_clean.startswith("🤑"):
                    detail_clean = f"🤑 {detail_clean}"
                return f"{detail_clean}\n\n🎟️ Cupom: {wrap_coupon_codes(code)}\n\n🔗 {affiliate_url}"
            else:
                title = "🔥 Cupons Mercado Livre!"
                lines = []
                for c in coupons:
                    detail = c.get("detail", "")
                    code = c.get("code", "")
                    if detail and code:
                        detail_clean = re.sub(r"\s+", " ", detail).strip(" -:|!\t")
                        detail_clean = re.sub(r"R\$\s*(\d)", r"R$ \1", detail_clean)
                        lines.append(f"🎟 {detail_clean}: {wrap_coupon_codes(code)}")
                if lines:
                    return (
                        f"{title}\n\n"
                        + "\n".join(lines)
                        + f"\n\n🛒 Resgate aqui: {affiliate_url}"
                    )

        elif platform == "Shopee" or platform == "AliExpress":
            lines = []
            for c in coupons:
                detail = c.get("detail", "")
                code = c.get("code", "")
                if detail and code:
                    detail_clean = re.sub(r"\s+", " ", detail).strip(" -:|!\t")
                    detail_clean = re.sub(r"R\$\s*(\d)", r"R$ \1", detail_clean)
                    lines.append(f"🎟 {detail_clean}: {wrap_coupon_codes(code)}")
            if lines:
                title_header = f"☑️ Cupom {platform}!"
                return (
                    f"{title_header}\n\n" + "\n".join(lines) + f"\n\n🔗 {affiliate_url}"
                )

        else:  # Generic
            detail = coupons[0].get("detail", "") if coupons else ""
            code = coupons[0].get("code", "") if coupons else ""
            if not detail and not code:
                return ""
            detail_clean = re.sub(r"\s+", " ", detail).strip(" -:|!\t")
            detail_clean = re.sub(r"R\$\s*(\d)", r"R$ \1", detail_clean)
            detail_clean = re.sub(r"^[^\w\dR$%]+", "", detail_clean).strip()
            return f"{detail_clean}\n\n🎟️ Cupom: {wrap_coupon_codes(code)}\n\n🔗 {affiliate_url}"

    elif classification == "product":
        prod = offer.llm_product
        if prod is None:
            prod = llm.get("product", {})
            if not isinstance(prod, dict) or not prod:
                products = llm.get("products", [])
                prod = products[0] if products and isinstance(products[0], dict) else {}
        title = prod.get("title") or offer.title or ""
        price = prod.get("price") or offer.price or ""
        card_price = prod.get("card_price") or offer.card_price or ""
        installment = prod.get("installment_info") or offer.installment_info or ""
        shipping = prod.get("shipping_info") or offer.shipping_info or ""
        coupon = prod.get("coupon") or offer.coupon or ""
        resgate_note = prod.get("resgate_anuncio_note") or ""
        meli_plus = prod.get("meli_plus_only", False) or offer.meli_plus_only

        parts = []
        if title:
            t = URL_RE.sub("", title).strip()
            if installment:
                t = f"[{installment.upper()}] {t}"
            parts.append(t)

        if price:
            price_block = f"💰 {price}"
            if card_price:
                price_block += f"\n💳 {card_price}"
            if shipping:
                price_block += f"\n{shipping.upper()}"
            parts.append(price_block)

        if coupon:
            parts.append(f"🎟️ CUPOM: {wrap_coupon_codes(coupon)}")

        if resgate_note:
            parts.append(f"🏷️ {resgate_note}")

        if meli_plus:
            parts.append("⭐ Exclusivo para clientes Meli+")

        parts.append(f"🔗 Link do produto:\n{affiliate_url}")
        return "\n\n".join(parts)

    return ""


def format_offer(offer: Offer, affiliate_url: str) -> str:
    llm_formatted = format_llm_offer(offer, affiliate_url)
    if llm_formatted:
        return llm_formatted

    coupon_offer = format_coupon_bulletin_offer(offer, affiliate_url)
    if coupon_offer:
        return coupon_offer

    parts = []
    resgate_anuncio_note = extract_resgate_anuncio_note(offer.original_text)
    if offer.title:
        title = URL_RE.sub("", offer.title).strip()
        if offer.installment_info:
            title = f"[{offer.installment_info}] {title}"
        parts.append(f"{title}")
    if offer.price:
        price_block = f"💰 {offer.price}"
        if offer.card_price:
            price_block = f"{price_block}\n💳 {offer.card_price}"
        if offer.shipping_info:
            price_block = f"{price_block}\n{offer.shipping_info}"
        parts.append(price_block)
    if offer.coupon:
        parts.append(f"🎟️ CUPOM: {wrap_coupon_codes(offer.coupon)}")
    if resgate_anuncio_note:
        parts.append(f"🏷️ {resgate_anuncio_note}")
    if offer.meli_plus_only:
        parts.append("⭐ Exclusivo para clientes Meli+")
    parts.append(f"🔗 Link do produto:\n{affiliate_url}")
    return "\n\n".join(parts)


def _build_url_replacements(
    offer: Offer,
    affiliate_url: str,
    affiliate_client: ShopeeClient | AliExpressClient | None,
) -> dict[str, str]:
    if not (offer.all_urls and len(offer.all_urls) > 1):
        return {offer.url: affiliate_url}

    replacements: dict[str, str] = {}
    replacements[offer.url] = affiliate_url

    for url in offer.all_urls:
        if url == offer.url or url in replacements:
            continue
        try:
            aff = (
                asyncio.run(asyncio.to_thread(affiliate_client.create_link, url))
                if affiliate_client
                else None
            )
            if aff:
                replacements[url] = aff.short_url
            else:
                replacements[url] = url
        except Exception:
            replacements[url] = url

    return replacements


def format_outgoing_offer(
    offer: Offer,
    affiliate_url: str,
    *,
    is_ali: bool = False,
    url_replacements: dict[str, str] | None = None,
    affiliate_client: ShopeeClient | AliExpressClient | None = None,
) -> str:
    formatted_text = format_offer(offer, affiliate_url)

    # Multi-link AliExpress handling
    if is_ali and offer.all_urls and len(offer.all_urls) > 1:
        replacements = _build_url_replacements(offer, affiliate_url, affiliate_client)
        new_text = offer.original_text
        for orig, aff in replacements.items():
            new_text = new_text.replace(orig, aff)
        new_text = _wrap_coupons_in_text(new_text)
        new_text = re.sub(r"\s*\(?an[uú]ncio\)?\s*$", "", new_text, flags=re.IGNORECASE)
        new_text = re.sub(r"\s*-\s*$", "", new_text, flags=re.IGNORECASE)
        new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip()
        formatted_text = new_text

    if is_ali and not (offer.all_urls and len(offer.all_urls) > 1):
        formatted_text += (
            "\n\nObs: Abra o link pelo celular e clique no anúncio do produto desejado."
        )

    if is_shopee_url(offer.url) and "resgate" in offer.original_text.lower():
        replacements = _build_url_replacements(offer, affiliate_url, affiliate_client)
        if url_replacements:
            replacements.update(url_replacements)
        new_text = offer.original_text
        for orig, aff in replacements.items():
            new_text = new_text.replace(orig, aff)
        new_text = _wrap_coupons_in_text(new_text)
        new_text = re.sub(r"\s*\(?an[uú]ncio\)?\s*$", "", new_text, flags=re.IGNORECASE)
        new_text = re.sub(r"\s*-\s*$", "", new_text, flags=re.IGNORECASE)
        new_text = re.sub(r"\n{3,}", "\n\n", new_text).strip()
        return f"{new_text}\n\n- Anúncio"

    return f"{formatted_text}\n\n- Anúncio"


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = load_settings()

    # Ensure directories exist before attempting to create SQLite files
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    session_path = pathlib.Path(settings.telegram_session)
    if str(session_path.parent) != ".":
        session_path.parent.mkdir(parents=True, exist_ok=True)

    store = OfferStore(settings.database_path)
    product_url_resolver = None
    if settings.browser_resolver_enabled:
        product_url_resolver = PlaywrightProductResolver(
            headless=settings.browser_headless,
            timeout_ms=settings.browser_timeout_ms,
            cookie_header=settings.ml_cookie_header,
            cookie_domains=(".mercadolivre.com.br",),
            debug_dir=settings.browser_debug_dir,
        )
    amazon_image_resolver = None
    if settings.browser_resolver_enabled:
        amazon_image_resolver = PlaywrightProductResolver(
            headless=settings.browser_headless,
            timeout_ms=settings.browser_timeout_ms,
            cookie_header=settings.amazon_cookie_header,
            cookie_domains=(".amazon.com.br",),
            debug_dir=settings.browser_debug_dir,
        )
    ml = MercadoLivreClient(
        tag=settings.ml_affiliate_tag,
        cookie_header=settings.ml_cookie_header,
        csrf_token=settings.ml_csrf_token,
        product_url_resolver=product_url_resolver,
    )
    amazon = AmazonClient(
        tag=settings.amazon_affiliate_tag,
        cookie_header=settings.amazon_cookie_header,
        marketplace_id=settings.amazon_marketplace_id,
        image_resolver=amazon_image_resolver,
    )
    shopee = ShopeeClient(
        app_id=settings.shopee_app_id,
        app_secret=settings.shopee_app_secret,
    )
    aliexpress = AliExpressClient(
        app_key=settings.aliexpress_app_key,
        app_secret=settings.aliexpress_app_secret,
        tracking_id=settings.aliexpress_tracking_id,
    )
    telegram = TelegramOfferBot(
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
        session_name=settings.telegram_session,
        source_chats=settings.source_chats,
        target_chat=settings.target_chat,
        phone=settings.telegram_phone,
        tech_chat=settings.tech_chat,
        home_chat=settings.home_chat,
        clothes_chat=settings.clothes_chat,
    )

    async def handle_message(
        source_chat: str, message_id: int, text: str, original_media: str | None = None
    ) -> None:
        offers = await extract_offers_async(text)
        logging.info(
            "Parsed message chat=%s message=%s offers=%s",
            source_chat,
            message_id,
            len(offers),
        )
        processed_product_keys = set()
        for offer in offers:
            if store.seen(source_chat, message_id, offer.url):
                logging.info("Skipped already posted offer %s", offer.url)
                continue
            try:
                is_ali = is_aliexpress_url(offer.url)
                affiliate_client = (
                    ml
                    if is_mercado_livre_url(offer.url)
                    else amazon
                    if is_amazon_url(offer.url)
                    else shopee
                    if is_shopee_url(offer.url)
                    else aliexpress
                    if is_ali
                    else None
                )
                if affiliate_client is None:
                    logging.info("Skipped unsupported offer URL %s", offer.url)
                    continue
                affiliate = await asyncio.to_thread(
                    affiliate_client.create_link, offer.url
                )

                if affiliate.product_key in processed_product_keys:
                    logging.info(
                        "Skipped duplicate product in same message: %s",
                        affiliate.product_key,
                    )
                    continue
                processed_product_keys.add(affiliate.product_key)

                if store.seen_affiliate_url(affiliate.short_url):
                    logging.info(
                        "Skipped already posted affiliate offer %s", affiliate.short_url
                    )
                    store.mark(
                        source_chat,
                        message_id,
                        offer.url,
                        affiliate.short_url,
                        affiliate.product_key,
                    )
                    continue
                if store.seen_product_key(affiliate.product_key):
                    logging.info(
                        "Skipped already posted product offer %s", affiliate.product_key
                    )
                    store.mark(
                        source_chat,
                        message_id,
                        offer.url,
                        affiliate.short_url,
                        affiliate.product_key,
                    )
                    continue

                formatted_text = format_outgoing_offer(
                    offer,
                    affiliate.short_url,
                    is_ali=is_ali,
                    affiliate_client=affiliate_client,
                )

                # Extract category from LLM result if available
                category = None
                if offer.llm_result and "category" in offer.llm_result:
                    category = offer.llm_result["category"]

                temp_image_path = None
                try:
                    image_url = None if is_ali else affiliate.image_url
                    image_to_send = (
                        original_media if (is_ali and original_media) else None
                    )

                    if not image_to_send and image_url:
                        # Download the image to a temporary file
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(image_url)
                            resp.raise_for_status()
                            fd, temp_image_path = tempfile.mkstemp(suffix=".jpg")
                            with os.fdopen(fd, "wb") as f:
                                f.write(resp.content)
                            image_to_send = temp_image_path

                    await telegram.send_offer(
                        formatted_text, image_file=image_to_send, category=category
                    )
                except Exception as e:
                    logging.warning("Failed to send image: %s", e)
                    await telegram.send_offer(formatted_text, category=category)
                finally:
                    if temp_image_path and os.path.exists(temp_image_path):
                        os.remove(temp_image_path)

                store.mark(
                    source_chat,
                    message_id,
                    offer.url,
                    affiliate.short_url,
                    affiliate.product_key,
                )
                logging.info("Posted affiliate offer for %s", offer.url)
            except UnsupportedOfferError as exc:
                logging.warning("Skipped unsupported offer %s: %s", offer.url, exc)
                store.mark(source_chat, message_id, offer.url, None)
            except Exception:
                logging.exception("Failed to process offer %s", offer.url)

        # Cleanup original media if it was downloaded
        if original_media and os.path.exists(original_media):
            try:
                os.remove(original_media)
            except Exception as exc:
                logging.warning(
                    "Failed to remove original media %s: %s", original_media, exc
                )

    try:
        await telegram.start()
        await telegram.listen(
            handle_message, poll_existing=settings.poll_existing_messages
        )
    finally:
        store.close()


def main() -> None:
    asyncio.run(run())
