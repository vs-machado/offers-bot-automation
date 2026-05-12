from __future__ import annotations

import asyncio
import logging
import os
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
    extract_offers,
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


def wrap_coupon_codes(coupon_text: str) -> str:
    if not coupon_text:
        return ""
    # Split by " ou " and wrap each part in backticks
    parts = [f"`{p.strip()}`" for p in coupon_text.split(" ou ")]
    return " ou ".join(parts)


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
            return "\n\n".join(["\n".join(lines_output), f"🔗 {affiliate_url}"])

    if _is_generic_coupon_bulletin(offer, text):
        return _format_generic_coupon(offer, affiliate_url, text)

    return None


def format_offer(offer: Offer, affiliate_url: str) -> str:
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


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = load_settings()

    # Ensure directories exist before attempting to create SQLite files
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    import pathlib

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
    )

    async def handle_message(source_chat: str, message_id: int, text: str) -> None:
        offers = extract_offers(text)
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
                affiliate_client = (
                    ml
                    if is_mercado_livre_url(offer.url)
                    else amazon
                    if is_amazon_url(offer.url)
                    else shopee
                    if is_shopee_url(offer.url)
                    else aliexpress
                    if is_aliexpress_url(offer.url)
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

                formatted_text = format_offer(offer, affiliate.short_url)
                if is_aliexpress_url(offer.url):
                    formatted_text += "\n\nObs: Abra o link pelo celular e clique no anúncio do produto desejado."
                formatted_text += "\n\n- Anúncio"

                temp_image_path = None
                try:
                    if affiliate.image_url:
                        # Download the image to a temporary file
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(affiliate.image_url)
                            resp.raise_for_status()
                            fd, temp_image_path = tempfile.mkstemp(suffix=".jpg")
                            with os.fdopen(fd, "wb") as f:
                                f.write(resp.content)

                    await telegram.send_offer(
                        formatted_text, image_file=temp_image_path
                    )
                except Exception as e:
                    if not affiliate.image_url:
                        raise
                    logging.warning(
                        "Failed to send image %s: %s", affiliate.image_url, e
                    )
                    await telegram.send_offer(formatted_text)
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

    try:
        await telegram.start()
        await telegram.listen(
            handle_message, poll_existing=settings.poll_existing_messages
        )
    finally:
        store.close()


def main() -> None:
    asyncio.run(run())
