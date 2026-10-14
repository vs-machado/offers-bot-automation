import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.models.user import DestinationChannel, UserConfig
from backend.app.core.source_groups import approved_source
from backend.worker.poster import BotPoster
from backend.worker.store import PgOfferStore
from offers_bot.aliexpress import AliExpressClient
from offers_bot.amazon import AmazonClient
from offers_bot.browser_resolver import PlaywrightProductResolver
from offers_bot.main import format_outgoing_offer
from offers_bot.mercado_livre import MercadoLivreClient, UnsupportedOfferError
from offers_bot.parser import (
    PLATFORM_ALIEXPRESS,
    PLATFORM_AMAZON,
    PLATFORM_MERCADO_LIVRE,
    PLATFORM_SHOPEE,
    extract_offers_async,
)
from offers_bot.shopee import ShopeeClient

LOGGER = logging.getLogger(__name__)

PLATFORM_LABELS = {
    PLATFORM_ALIEXPRESS: "AliExpress",
    PLATFORM_AMAZON: "Amazon",
    PLATFORM_MERCADO_LIVRE: "Mercado Livre",
    PLATFORM_SHOPEE: "Shopee",
}


class UserBotInstance:
    """One user's persisted routing and affiliate configuration."""

    def __init__(
        self,
        user_id: int,
        db_factory: async_sessionmaker[AsyncSession],
        poster: BotPoster | None = None,
    ):
        self.user_id = user_id
        self._db_factory = db_factory
        self._poster = poster or BotPoster()
        self._source_chats: tuple[str, ...] = ()
        self._destination_chat_ids: tuple[str, ...] = ()
        self._ml: MercadoLivreClient | None = None
        self._amazon: AmazonClient | None = None
        self._shopee: ShopeeClient | None = None
        self._aliexpress: AliExpressClient | None = None
        self._config_signature: str | None = None

    @property
    def source_chats(self) -> tuple[str, ...]:
        """Return normalized public source chats currently assigned to user."""
        return self._source_chats

    @property
    def active(self) -> bool:
        """Return whether user has sources, destinations, and ready affiliate client."""
        return bool(
            self._source_chats
            and self._destination_chat_ids
            and any(
                client and client.ready()
                for client in (self._ml, self._amazon, self._shopee, self._aliexpress)
            )
        )

    async def configure(
        self, db: AsyncSession, source_catalog: list[str] | None = None
    ) -> None:
        """Reload persisted routing and provider clients when configuration changes."""
        configs = await self._load_configs(db)
        approved = []
        for chat in self._parse_chats(configs.get("source_chats", [])):
            try:
                approved.append(approved_source(chat, source_catalog))
            except ValueError:
                LOGGER.warning("Ignoring non-catalog source for user %s", self.user_id)
        source_chats = tuple(dict.fromkeys(approved))
        destination_chat_ids = tuple(await self._load_destination_chat_ids(db))
        config_signature = json.dumps(
            {
                "configs": configs,
                "destinations": destination_chat_ids,
                "sources": source_chats,
            },
            sort_keys=True,
            default=str,
        )
        if config_signature == self._config_signature:
            return

        self.close()
        self._source_chats = source_chats
        self._destination_chat_ids = destination_chat_ids

        browser_enabled = self._as_bool(configs.get("browser_resolver_enabled", True))
        browser_headless = self._as_bool(configs.get("browser_headless", True))
        browser_timeout = int(configs.get("browser_timeout_ms", 15000))
        browser_debug_value = configs.get("browser_debug_dir")
        browser_debug = Path(str(browser_debug_value)) if browser_debug_value else None

        ml_cookie = str(configs.get("ml_cookie_header", ""))
        amazon_cookie = str(configs.get("amazon_cookie_header", ""))

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
            tag=str(configs.get("ml_affiliate_tag", "")),
            cookie_header=ml_cookie,
            csrf_token=str(configs.get("ml_csrf_token", "")),
            product_url_resolver=product_url_resolver,
        )
        self._amazon = AmazonClient(
            tag=str(configs.get("amazon_affiliate_tag", "")),
            cookie_header=amazon_cookie,
            marketplace_id=str(configs.get("amazon_marketplace_id", "526970")),
            image_resolver=amazon_image_resolver,
        )
        self._shopee = ShopeeClient(
            app_id=str(configs.get("shopee_app_id", "")),
            app_secret=str(configs.get("shopee_app_secret", "")),
        )
        self._aliexpress = AliExpressClient(
            app_key=str(configs.get("aliexpress_app_key", "")),
            app_secret=str(configs.get("aliexpress_app_secret", "")),
            tracking_id=str(configs.get("aliexpress_tracking_id", "")),
        )
        self._config_signature = config_signature

    def close(self) -> None:
        """Close provider HTTP and browser clients owned by this user instance."""
        closed_clients: set[int] = set()
        for affiliate_client in (
            self._ml,
            self._amazon,
            self._shopee,
            self._aliexpress,
        ):
            if affiliate_client is None:
                continue
            for attribute in ("_client", "_resolver_client"):
                client = getattr(affiliate_client, attribute, None)
                if client is None or id(client) in closed_clients:
                    continue
                close = getattr(client, "close", None)
                if close:
                    close()
                closed_clients.add(id(client))

    async def process_message(
        self,
        source_chat: str,
        message_id: int,
        text: str,
        source_image_url: str | None = None,
    ) -> None:
        """Parse, deduplicate, affiliate, format, and post one source message.

        Uses the optional source image when provider output requires it.
        """
        if source_chat not in self._source_chats:
            return

        offers = await extract_offers_async(text)
        LOGGER.info(
            "User %s: parsed chat=%s message=%s offers=%s",
            self.user_id,
            source_chat,
            message_id,
            len(offers),
        )
        processed_product_keys: set[str] = set()

        async with self._db_factory() as db:
            store = PgOfferStore(db, self.user_id)
            for offer in offers:
                if await store.seen(source_chat, message_id, offer.url):
                    continue

                try:
                    affiliate_client = self._affiliate_client_for_platform(
                        offer.platform
                    )
                    if affiliate_client is None:
                        LOGGER.warning(
                            "User %s: unsupported platform=%s url=%s",
                            self.user_id,
                            offer.platform or "unknown",
                            offer.url,
                        )
                        await store.mark(source_chat, message_id, offer.url)
                        continue
                    if not affiliate_client.ready():
                        LOGGER.warning(
                            "User %s: missing %s affiliate credentials for url=%s",
                            self.user_id,
                            PLATFORM_LABELS.get(offer.platform, offer.platform),
                            offer.url,
                        )
                        continue

                    affiliate = await asyncio.to_thread(
                        affiliate_client.create_link, offer.url
                    )
                    if affiliate.product_key in processed_product_keys:
                        continue
                    processed_product_keys.add(affiliate.product_key)

                    if await store.seen_affiliate_url(affiliate.short_url):
                        await store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue
                    if await store.seen_product_key(affiliate.product_key):
                        await store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue

                    is_ali = offer.platform == PLATFORM_ALIEXPRESS
                    formatted_text = await format_outgoing_offer(
                        offer,
                        affiliate.short_url,
                        is_ali=is_ali,
                        affiliate_client=affiliate_client,
                    )
                    # TODO: Persist destination categories and route each offer to all
                    # destinations matching offer.llm_result["category"].
                    await self._send_offer_with_image(
                        formatted_text,
                        affiliate.image_url,
                        source_image_url if is_ali else None,
                    )
                    await store.mark(
                        source_chat,
                        message_id,
                        offer.url,
                        affiliate.short_url,
                        affiliate.product_key,
                    )
                    LOGGER.info("User %s: processed offer %s", self.user_id, offer.url)
                except UnsupportedOfferError as exc:
                    LOGGER.warning(
                        "User %s: unsupported %s: %s", self.user_id, offer.url, exc
                    )
                    await store.mark(source_chat, message_id, offer.url)
                except Exception:
                    LOGGER.exception(
                        "User %s: failed to process %s", self.user_id, offer.url
                    )

    async def _send_offer_with_image(
        self,
        text: str,
        affiliate_image_url: str | None,
        source_image_url: str | None,
    ) -> None:
        image_url = source_image_url or affiliate_image_url
        from backend.worker.posting_queue import QueuePoster

        if isinstance(self._poster, QueuePoster):
            await self._send_offer(text, image_file=image_url)
            return
        temp_image_path = None
        try:
            if image_url:
                if os.path.isfile(image_url):
                    await self._send_offer(text, image_file=image_url)
                    return
                temp_image_path = await self._download_image(image_url)
            await self._send_offer(text, image_file=temp_image_path)
        except Exception as exc:
            if temp_image_path:
                LOGGER.warning("User %s: failed to send image: %s", self.user_id, exc)
                await self._send_offer(text)
            else:
                raise
        finally:
            if temp_image_path and os.path.exists(temp_image_path):
                os.remove(temp_image_path)

    async def _download_image(self, image_url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            response = await client.get(image_url)
            response.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".jpg")
        with os.fdopen(fd, "wb") as image_file:
            image_file.write(response.content)
        return path

    async def _send_offer(self, text: str, image_file: str | None = None) -> None:
        from backend.worker.posting_queue import QueuePoster

        if isinstance(self._poster, QueuePoster):
            results = await asyncio.gather(
                *(
                    self._poster.send_offer(chat_id, text, image_file=image_file)
                    for chat_id in self._destination_chat_ids
                ),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            return
        for chat_id in self._destination_chat_ids:
            await self._poster.send_offer(chat_id, text, image_file=image_file)

    async def _load_configs(self, db: AsyncSession) -> dict[str, object]:
        stmt = select(UserConfig).where(UserConfig.user_id == self.user_id)
        result = await db.execute(stmt)
        configs: dict[str, object] = {}
        for row in result.scalars().all():
            try:
                data = json.loads(row.config_data)
            except (json.JSONDecodeError, TypeError):
                data = row.config_data
            if isinstance(data, dict):
                configs.update(
                    {
                        key: value
                        for key, value in data.items()
                        if key != "source_chats" or row.config_type == "source_chats"
                    }
                )
            else:
                configs[row.config_type] = data
        return configs

    async def _load_destination_chat_ids(self, db: AsyncSession) -> list[str]:
        stmt = select(DestinationChannel).where(
            DestinationChannel.user_id == self.user_id,
            DestinationChannel.enabled.is_(True),
        )
        result = await db.execute(stmt)
        return [destination.chat_id for destination in result.scalars().all()]

    @staticmethod
    def _parse_chats(raw: object) -> list[str]:
        if isinstance(raw, list):
            return [str(chat).strip() for chat in raw if str(chat).strip()]
        if isinstance(raw, str):
            return [chat.strip() for chat in raw.split(",") if chat.strip()]
        return []

    @staticmethod
    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"

    def _affiliate_client_for_platform(self, platform: str):
        if platform == PLATFORM_MERCADO_LIVRE:
            return self._ml
        if platform == PLATFORM_AMAZON:
            return self._amazon
        if platform == PLATFORM_SHOPEE:
            return self._shopee
        if platform == PLATFORM_ALIEXPRESS:
            return self._aliexpress
        return None
