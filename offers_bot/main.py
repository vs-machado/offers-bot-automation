from __future__ import annotations

import asyncio
import logging

from .config import load_settings
from .browser_resolver import PlaywrightProductResolver
from .mercado_livre import MercadoLivreClient, UnsupportedOfferError
from .parser import Offer, extract_offers
from .store import OfferStore
from .telegram_bot import TelegramOfferBot


def format_offer(offer: Offer, affiliate_url: str) -> str:
    parts = []
    if offer.title:
        parts.append(offer.title)
    if offer.price:
        parts.append(offer.price)
    parts.append(affiliate_url)
    return "\n\n".join(parts)


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
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
                await telegram.send_offer(format_offer(offer, affiliate.short_url))
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
