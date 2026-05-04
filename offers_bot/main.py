from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import httpx

from .config import load_settings
from .browser_resolver import PlaywrightProductResolver
from .mercado_livre import MercadoLivreClient, UnsupportedOfferError
from .parser import Offer, extract_offers
from .store import OfferStore
from .telegram_bot import TelegramOfferBot


def format_offer(offer: Offer, affiliate_url: str) -> str:
    parts = []
    if offer.title:
        parts.append(f"🛍️ {offer.title}")
    if offer.price:
        parts.append(f"💰 {offer.price}")
    if offer.coupon:
        parts.append(f"🎟️ CUPOM: {offer.coupon}")
    if offer.meli_plus_only:
        parts.append("⭐ Exclusivo para clientes Meli+")
    parts.append(f"🔗 Link do produto:\n{affiliate_url}")
    return "\n\n".join(parts)


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
            debug_dir=settings.browser_debug_dir,
        )
    ml = MercadoLivreClient(
        tag=settings.ml_affiliate_tag,
        cookie_header=settings.ml_cookie_header,
        csrf_token=settings.ml_csrf_token,
        product_url_resolver=product_url_resolver,
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
            "Parsed message chat=%s message=%s mercado_livre_offers=%s",
            source_chat,
            message_id,
            len(offers),
        )
        for offer in offers:
            if store.seen(source_chat, message_id, offer.url):
                logging.info("Skipped already posted offer %s", offer.url)
                continue
            try:
                affiliate = await asyncio.to_thread(ml.create_link, offer.url)
                affiliate = await asyncio.to_thread(ml.create_link, offer.url)
                if store.seen_affiliate_url(affiliate.short_url):
                    logging.info("Skipped already posted affiliate offer %s", affiliate.short_url)
                    store.mark(source_chat, message_id, offer.url, affiliate.short_url)
                    continue

                formatted_text = format_offer(offer, affiliate.short_url)
                
                temp_image_path = None
                if affiliate.image_url:
                    try:
                        # Download the image to a temporary file
                        async with httpx.AsyncClient() as client:
                            resp = await client.get(affiliate.image_url)
                            resp.raise_for_status()
                            fd, temp_image_path = tempfile.mkstemp(suffix=".jpg")
                            with os.fdopen(fd, 'wb') as f:
                                f.write(resp.content)
                    except Exception as e:
                        logging.warning("Failed to download image %s: %s", affiliate.image_url, e)
                        temp_image_path = None

                await telegram.send_offer(formatted_text, image_file=temp_image_path)
                
                if temp_image_path and os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
                    
                store.mark(source_chat, message_id, offer.url, affiliate.short_url)
                logging.info("Posted affiliate offer for %s", offer.url)
            except UnsupportedOfferError as exc:
                logging.warning("Skipped unsupported Mercado Livre offer %s: %s", offer.url, exc)
                store.mark(source_chat, message_id, offer.url, None)
            except Exception:
                logging.exception("Failed to process offer %s", offer.url)

    try:
        await telegram.start()
        await telegram.listen(handle_message, poll_existing=settings.poll_existing_messages)
    finally:
        store.close()


def main() -> None:
    asyncio.run(run())
