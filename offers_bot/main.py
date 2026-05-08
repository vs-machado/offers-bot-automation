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
    extract_offers,
    is_amazon_url,
    is_mercado_livre_url,
    is_shopee_url,
    is_aliexpress_url,
)
from .shopee import ShopeeClient
from .store import OfferStore
from .telegram_bot import TelegramOfferBot


AMAZON_COUPON_HEADER_RE = re.compile(r"\bcupom\s+amazon\b", re.IGNORECASE)
ML_COUPON_HEADER_RE = re.compile(r"\bcupons?\s+mercado\s+livre\b", re.IGNORECASE)
DETAIL_AND_CODE_RE = re.compile(r"(.+?)\s*:\s*([A-Za-z0-9]{4,})\s*$", re.IGNORECASE)
CODE_LABEL_RE = re.compile(
    r"\b(?:c[oó]digo|cupom)\b\s*:\s*([A-Za-z0-9]{4,})", re.IGNORECASE
)
RESGATE_ANUNCIO_RE = re.compile(
    r"\bresgate\s+(?:cupom\s+)?(?:do|no)?\s*an[uú]ncio\b",
    re.IGNORECASE,
)


def _normalize_money_spacing(text: str) -> str:
    return re.sub(r"R\$\s*(\d)", r"R$ \1", text)


def _normalize_coupon_detail(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip(" -:|!\t")
    return _normalize_money_spacing(clean)


def extract_resgate_anuncio_note(text: str) -> str | None:
    match = RESGATE_ANUNCIO_RE.search(text)
    if not match:
        return None
    note = re.sub(r"\s+", " ", match.group(0)).strip(" -:|!\t")
    note = note[0].upper() + note[1:].lower()
    return note


def format_coupon_bulletin_offer(offer: Offer, affiliate_url: str) -> str | None:
    text = offer.original_text
    is_amazon_coupon = bool(AMAZON_COUPON_HEADER_RE.search(text))
    is_ml_coupon = bool(ML_COUPON_HEADER_RE.search(text))
    if not is_amazon_coupon and not is_ml_coupon:
        return None

    coupon_lines: list[str] = []
    pending_detail: str | None = None
    for raw_line in text.splitlines():
        line = re.sub(r"^[^\w\dR$%]+", "", raw_line).strip()
        if not line:
            continue

        detail_and_code = DETAIL_AND_CODE_RE.match(line)
        if detail_and_code and "%" in detail_and_code.group(1):
            detail = _normalize_coupon_detail(detail_and_code.group(1))
            code = detail_and_code.group(2).upper()
            coupon_lines.append(f"🎟 {detail}: {code}")
            pending_detail = None
            continue

        detail_candidate = line.lower()
        if (
            "%" in line
            and "off" in detail_candidate
            and ("acima" in detail_candidate or "compras" in detail_candidate)
        ):
            pending_detail = _normalize_coupon_detail(line.rstrip(":"))
            continue

        code_match = CODE_LABEL_RE.search(line)
        if code_match:
            code = code_match.group(1).upper()
            if pending_detail:
                coupon_lines.append(f"🎟 {pending_detail}: {code}")
                pending_detail = None
            else:
                coupon_lines.append(f"🎟 Cupom: {code}")

    if not coupon_lines and offer.coupon and is_amazon_coupon:
        coupon_lines.append(f"🎟 Cupom: {offer.coupon}")

    if not coupon_lines:
        return None

    title = "☑️ Cupom Amazon!" if is_amazon_coupon else "🔥 Cupons Mercado Livre!"

    return "\n\n".join(
        [
            title,
            "\n".join(coupon_lines),
            f"🛒 Resgate aqui: {affiliate_url}",
        ]
    )


def format_offer(offer: Offer, affiliate_url: str) -> str:
    coupon_offer = format_coupon_bulletin_offer(offer, affiliate_url)
    if coupon_offer:
        return coupon_offer

    parts = []
    resgate_anuncio_note = extract_resgate_anuncio_note(offer.original_text)
    if offer.title:
        title = offer.title
        if offer.installment_info:
            title = f"[{offer.installment_info}] {title}"
        parts.append(f"🛍️ {title}")
    if offer.price:
        price_block = f"💰 {offer.price}"
        if offer.shipping_info:
            price_block = f"{price_block}\n{offer.shipping_info}"
        parts.append(price_block)
    if offer.coupon:
        parts.append(f"🎟️ CUPOM: {offer.coupon}")
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
