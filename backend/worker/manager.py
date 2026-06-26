import asyncio
import json
import logging
import os
import tempfile
from collections.abc import Awaitable, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.models.user import DestinationChannel, UserConfig

from offers_bot.amazon import AmazonClient
from offers_bot.aliexpress import AliExpressClient
from offers_bot.browser_resolver import PlaywrightProductResolver
from offers_bot.mercado_livre import MercadoLivreClient, UnsupportedOfferError
from offers_bot.parser import (
    extract_offers_async,
    is_amazon_url,
    is_mercado_livre_url,
    is_shopee_url,
    is_aliexpress_url,
)
from offers_bot.shopee import ShopeeClient
from offers_bot.telegram_bot import TelegramOfferBot
from offers_bot.main import format_outgoing_offer

from backend.worker.store import PgOfferStore
from backend.worker.session import PgSessionStore
from backend.worker.poster import BotPoster

LOGGER = logging.getLogger(__name__)

MessageHandler = Callable[[str, int, str, str | None], Awaitable[None]]


class UserBotInstance:
    """A single user's Telegram bot + affiliate clients + dedup store."""

    def __init__(self, user_id: int, db_factory: async_sessionmaker[AsyncSession]):
        self.user_id = user_id
        self._db_factory = db_factory
        self.telegram: TelegramOfferBot | None = None
        self._ml: MercadoLivreClient | None = None
        self._amazon: AmazonClient | None = None
        self._shopee: ShopeeClient | None = None
        self._aliexpress: AliExpressClient | None = None
        self._store: PgOfferStore | None = None
        self._session_store: PgSessionStore | None = None
        self._poster = BotPoster()
        self._destination_chat_ids: list[str] = []
        self._handle_message: MessageHandler | None = None
        self._task: asyncio.Task | None = None

    async def start(self, db: AsyncSession) -> None:
        configs = await self._load_configs(db)
        if not configs.get("telegram"):
            LOGGER.warning("User %s has no telegram config, skipping", self.user_id)
            return

        tg = configs["telegram"]
        tg_api_id = int(tg.get("api_id", 0))
        tg_api_hash = tg.get("api_hash", "")

        async with self._db_factory() as session:
            self._session_store = PgSessionStore(session, self.user_id)
            session_string = await self._session_store.get_session()

        source_chats = self._parse_chats(configs.get("source_chats", []))
        self._destination_chat_ids = await self._load_destination_chat_ids(db)
        target_chat = configs.get("target_chat", "")
        tech_chat = configs.get("tech_chat", "")
        home_chat = configs.get("home_chat", "")
        clothes_chat = configs.get("clothes_chat", "")
        phone = tg.get("phone", "")
        qr_port = int(tg.get("qr_auth_port", 8080))

        self.telegram = TelegramOfferBot(
            api_id=tg_api_id,
            api_hash=tg_api_hash,
            session_name=f"user_{self.user_id}",
            session_string=session_string,
            source_chats=source_chats,
            target_chat=target_chat,
            phone=phone,
            qr_auth_port=qr_port,
            tech_chat=tech_chat or None,
            home_chat=home_chat or None,
            clothes_chat=clothes_chat or None,
        )

        await self.telegram.start()

        new_session = self.telegram.session_string
        if new_session and new_session != session_string:
            async with self._db_factory() as session:
                store = PgSessionStore(session, self.user_id)
                await store.save_session(new_session)

        browser_enabled = (
            configs.get("browser_resolver_enabled", "true").lower() == "true"
        )
        browser_headless = configs.get("browser_headless", "true").lower() == "true"
        browser_timeout = int(configs.get("browser_timeout_ms", 15000))
        browser_debug = configs.get("browser_debug_dir")

        ml_cookie = configs.get("ml_cookie_header", "")
        ml_csrf = configs.get("ml_csrf_token", "")
        ml_tag = configs.get("ml_affiliate_tag", "")

        amazon_cookie = configs.get("amazon_cookie_header", "")
        amazon_tag = configs.get("amazon_affiliate_tag", "")
        amazon_marketplace = configs.get("amazon_marketplace_id", "526970")

        product_url_resolver = None
        if browser_enabled and ml_cookie:
            product_url_resolver = PlaywrightProductResolver(
                headless=browser_headless,
                timeout_ms=browser_timeout,
                cookie_header=ml_cookie,
                cookie_domains=(".mercadolivre.com.br",),
                debug_dir=browser_debug,
            )

        amazon_image_resolver = None
        if browser_enabled and amazon_cookie:
            amazon_image_resolver = PlaywrightProductResolver(
                headless=browser_headless,
                timeout_ms=browser_timeout,
                cookie_header=amazon_cookie,
                cookie_domains=(".amazon.com.br",),
                debug_dir=browser_debug,
            )

        self._ml = MercadoLivreClient(
            tag=ml_tag,
            cookie_header=ml_cookie,
            csrf_token=ml_csrf,
            product_url_resolver=product_url_resolver,
        )
        self._amazon = AmazonClient(
            tag=amazon_tag,
            cookie_header=amazon_cookie,
            marketplace_id=amazon_marketplace,
            image_resolver=amazon_image_resolver,
        )
        self._shopee = ShopeeClient(
            app_id=configs.get("shopee_app_id", ""),
            app_secret=configs.get("shopee_app_secret", ""),
        )
        self._aliexpress = AliExpressClient(
            app_key=configs.get("aliexpress_app_key", ""),
            app_secret=configs.get("aliexpress_app_secret", ""),
            tracking_id=configs.get("aliexpress_tracking_id", ""),
        )

        self._store = PgOfferStore(db, self.user_id)
        self._handle_message = self._build_handler()
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.telegram:
            await self.telegram.client.disconnect()
        LOGGER.info("Stopped bot for user %s", self.user_id)

    async def _load_configs(self, db: AsyncSession) -> dict[str, str]:
        stmt = select(UserConfig).where(UserConfig.user_id == self.user_id)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        configs: dict[str, str] = {}
        for row in rows:
            try:
                data = json.loads(row.config_data)
                if isinstance(data, dict):
                    configs.update(data)
                else:
                    configs[row.config_type] = row.config_data
            except json.JSONDecodeError:
                configs[row.config_type] = row.config_data
        return configs

    async def _load_destination_chat_ids(self, db: AsyncSession) -> list[str]:
        stmt = select(DestinationChannel).where(
            DestinationChannel.user_id == self.user_id,
            DestinationChannel.enabled.is_(True),
        )
        result = await db.execute(stmt)
        return [destination.chat_id for destination in result.scalars().all()]

    def _parse_chats(self, raw: list[str] | str) -> list[str]:
        if isinstance(raw, list):
            return raw
        return [c.strip() for c in raw.split(",") if c.strip()]

    def _build_handler(self) -> MessageHandler:
        async def handle_message(
            source_chat: str,
            message_id: int,
            text: str,
            original_media: str | None = None,
        ) -> None:
            offers = await extract_offers_async(text)
            LOGGER.info(
                "User %s: parsed chat=%s message=%s offers=%s",
                self.user_id,
                source_chat,
                message_id,
                len(offers),
            )
            processed_product_keys: set[str] = set()

            for offer in offers:
                if await self._store.seen(source_chat, message_id, offer.url):
                    continue

                try:
                    is_ali = is_aliexpress_url(offer.url)
                    affiliate_client = (
                        self._ml
                        if is_mercado_livre_url(offer.url)
                        else self._amazon
                        if is_amazon_url(offer.url)
                        else self._shopee
                        if is_shopee_url(offer.url)
                        else self._aliexpress
                        if is_ali
                        else None
                    )
                    if affiliate_client is None:
                        continue

                    affiliate = await asyncio.to_thread(
                        affiliate_client.create_link, offer.url
                    )

                    if affiliate.product_key in processed_product_keys:
                        continue
                    processed_product_keys.add(affiliate.product_key)

                    if await self._store.seen_affiliate_url(affiliate.short_url):
                        await self._store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue
                    if await self._store.seen_product_key(affiliate.product_key):
                        await self._store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue

                    formatted_text = await format_outgoing_offer(
                        offer,
                        affiliate.short_url,
                        is_ali=is_ali,
                        affiliate_client=affiliate_client,
                    )

                    category = None
                    if offer.llm_result and "category" in offer.llm_result:
                        category = offer.llm_result["category"]
                    if (
                        category is None
                        and offer.llm_result
                        and offer.llm_result.get("classification") == "product"
                    ):
                        category = "other"

                    temp_image_path = None
                    try:
                        image_url = None if is_ali else affiliate.image_url
                        image_to_send = (
                            original_media if (is_ali and original_media) else None
                        )

                        if not image_to_send and image_url:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(image_url)
                                resp.raise_for_status()
                                fd, temp_image_path = tempfile.mkstemp(suffix=".jpg")
                                with os.fdopen(fd, "wb") as f:
                                    f.write(resp.content)
                                image_to_send = temp_image_path

                        await self._send_offer(
                            formatted_text, image_file=image_to_send, category=category
                        )
                    except Exception as e:
                        LOGGER.warning(
                            "User %s: failed to send image: %s", self.user_id, e
                        )
                        await self._send_offer(formatted_text, category=category)
                    finally:
                        if temp_image_path and os.path.exists(temp_image_path):
                            os.remove(temp_image_path)

                    await self._store.mark(
                        source_chat,
                        message_id,
                        offer.url,
                        affiliate.short_url,
                        affiliate.product_key,
                    )
                    LOGGER.info("User %s: posted offer %s", self.user_id, offer.url)
                except UnsupportedOfferError as exc:
                    LOGGER.warning(
                        "User %s: unsupported %s: %s", self.user_id, offer.url, exc
                    )
                    await self._store.mark(source_chat, message_id, offer.url, None)
                except Exception:
                    LOGGER.exception(
                        "User %s: failed to process %s", self.user_id, offer.url
                    )

            if original_media and os.path.exists(original_media):
                try:
                    os.remove(original_media)
                except Exception as exc:
                    LOGGER.warning(
                        "User %s: failed to remove media %s: %s",
                        self.user_id,
                        original_media,
                        exc,
                    )

        return handle_message

    async def _send_offer(
        self,
        text: str,
        image_file: str | None = None,
        category: str | None = None,
    ) -> None:
        if self._destination_chat_ids:
            for chat_id in self._destination_chat_ids:
                await self._poster.send_offer(chat_id, text, image_file=image_file)
            return

        await self.telegram.send_offer(text, image_file=image_file, category=category)

    async def _listen(self) -> None:
        try:
            await self.telegram.listen(self._handle_message)
        except asyncio.CancelledError:
            LOGGER.info("Listener cancelled for user %s", self.user_id)
        except Exception:
            LOGGER.exception("Listener error for user %s", self.user_id)
