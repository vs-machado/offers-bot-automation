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
from backend.app.core.credentials import decrypt_config
from backend.app.core.offer_categories import accepts_category, offer_category
from backend.app.core.source_groups import approved_source
from backend.worker.poster import BotPoster
from backend.worker.store import PgOfferStore
from backend.app.core.delivery_errors import classify_failure
from offers_bot.message_context import promotion_context
from offers_bot.aliexpress import AliExpressClient
from offers_bot.amazon import AmazonClient
from offers_bot.awin import AwinClient
from offers_bot.magalu import MagaluClient
from offers_bot.browser_resolver import PlaywrightProductResolver
from offers_bot.main import format_outgoing_offer
from offers_bot.mercado_livre import MercadoLivreClient, UnsupportedOfferError
from offers_bot.parser import (
    PLATFORM_ALIEXPRESS,
    PLATFORM_AMAZON,
    PLATFORM_KABUM,
    PLATFORM_MAGALU,
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
    PLATFORM_KABUM: "KaBuM",
    PLATFORM_MAGALU: "Magalu",
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
        self._destination_categories: dict[str, list[str] | None] = {}
        self._ml: MercadoLivreClient | None = None
        self._amazon: AmazonClient | None = None
        self._shopee: ShopeeClient | None = None
        self._aliexpress: AliExpressClient | None = None
        self._awin: AwinClient | None = None
        self._magalu: MagaluClient | None = None
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
                for client in (
                    self._ml,
                    self._amazon,
                    self._shopee,
                    self._aliexpress,
                    self._awin,
                    self._magalu,
                )
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
                "categories": self._destination_categories,
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

        product_url_resolver = None
        if browser_enabled and ml_cookie:
            product_url_resolver = PlaywrightProductResolver(
                headless=browser_headless,
                timeout_ms=browser_timeout,
                cookie_header=ml_cookie,
                cookie_domains=(".mercadolivre.com.br",),
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
        self._awin = AwinClient(
            publisher_id=str(configs.get("awin_publisher_id", "")),
            access_token=str(configs.get("awin_access_token", "")),
        )
        self._magalu = MagaluClient(
            partner_id=str(configs.get("magalu_partner_id", "")),
            promoter_id=str(configs.get("magalu_promoter_id", "")),
            store_name=str(configs.get("magalu_store_name", "")),
            utm_campaign=str(
                configs.get("magalu_utm_campaign", "divulgacao_influencer")
            ),
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

        Prefer source media for Amazon, Mercado Livre, AliExpress, and Shopee.
        """
        if source_chat not in self._source_chats:
            return

        try:
            offers = await extract_offers_async(text)
        except Exception as exc:
            await self._record_failure(
                classify_failure(exc, "processing"), "processing"
            )
            raise
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
                category = offer_category(offer.llm_result)
                if not self._matching_destination_ids(category):
                    continue

                context_token = promotion_context.set(
                    {
                        "title": (offer.title or "Promoção sem título")[:200],
                        "advertised_price": offer.price[:200] if offer.price else None,
                        "coupon": (offer.coupon or "").strip()[:200] or None,
                        "platform": PLATFORM_LABELS.get(offer.platform),
                        "identity": f"{source_chat}:{message_id}:{offer.url}",
                        "category": category,
                    }
                )
                failure_stage = "affiliate"
                try:
                    affiliate_client = self._affiliate_client_for_platform(
                        offer.platform
                    )
                    if affiliate_client is None:
                        await self._record_failure("unsupported_offer", "affiliate")
                        LOGGER.warning(
                            "User %s: unsupported platform=%s url=%s",
                            self.user_id,
                            offer.platform or "unknown",
                            offer.url,
                        )
                        await store.mark(source_chat, message_id, offer.url)
                        continue
                    if not affiliate_client.ready():
                        await self._record_failure(
                            "affiliate_credentials_missing", "affiliate"
                        )
                        LOGGER.warning(
                            "User %s: missing %s affiliate credentials for url=%s",
                            self.user_id,
                            PLATFORM_LABELS.get(offer.platform, offer.platform),
                            offer.url,
                        )
                        continue

                    if isinstance(affiliate_client, MercadoLivreClient):
                        affiliate = await asyncio.to_thread(
                            affiliate_client.create_link,
                            offer.url,
                            resolve_image=not bool(source_image_url),
                        )
                    else:
                        affiliate = await asyncio.to_thread(
                            affiliate_client.create_link, offer.url
                        )
                    if affiliate.product_key in processed_product_keys:
                        continue
                    processed_product_keys.add(affiliate.product_key)

                    from backend.worker.posting_queue import QueuePoster

                    uses_delivery_dedup = isinstance(self._poster, QueuePoster)
                    if not uses_delivery_dedup and await store.seen_affiliate_url(
                        affiliate.short_url
                    ):
                        await store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue
                    if not uses_delivery_dedup and await store.seen_product_key(
                        affiliate.product_key
                    ):
                        await store.mark(
                            source_chat,
                            message_id,
                            offer.url,
                            affiliate.short_url,
                            affiliate.product_key,
                        )
                        continue

                    is_ali = offer.platform == PLATFORM_ALIEXPRESS
                    promotion_context.set(
                        {
                            **promotion_context.get(),
                            "product_key": affiliate.product_key,
                            "affiliate_url": affiliate.short_url,
                            "price": f"{offer.price}|{offer.card_price}",
                        }
                    )
                    failure_stage = "processing"
                    formatted_text = await format_outgoing_offer(
                        offer,
                        affiliate.short_url,
                        is_ali=is_ali,
                        affiliate_client=affiliate_client,
                    )
                    failure_stage = "posting"
                    await self._send_offer_with_image(
                        formatted_text,
                        affiliate.image_url,
                        source_image_url
                        if offer.platform
                        in (
                            PLATFORM_AMAZON,
                            PLATFORM_MERCADO_LIVRE,
                            PLATFORM_ALIEXPRESS,
                            PLATFORM_SHOPEE,
                        )
                        else None,
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
                    await self._record_failure("unsupported_offer", "affiliate")
                    LOGGER.warning(
                        "User %s: unsupported %s: %s", self.user_id, offer.url, exc
                    )
                    await store.mark(source_chat, message_id, offer.url)
                except Exception as exc:
                    if failure_stage != "posting":
                        await self._record_failure(
                            classify_failure(
                                exc, failure_stage, PLATFORM_LABELS.get(offer.platform)
                            ),
                            failure_stage,
                        )
                    LOGGER.exception(
                        "User %s: failed to process %s", self.user_id, offer.url
                    )
                finally:
                    promotion_context.reset(context_token)

    async def _record_failure(self, reason: str, stage: str) -> None:
        """Keep audit failures from interrupting other users' message processing."""
        from backend.worker.posting_queue import QueuePoster

        if isinstance(self._poster, QueuePoster):
            try:
                await self._poster.record_failure(
                    self._matching_destination_ids(
                        promotion_context.get().get("category", "other")
                    ),
                    reason,
                    stage,
                )
            except Exception:
                LOGGER.exception(
                    "Could not record processing failure for user %s", self.user_id
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

        destinations = self._matching_destination_ids(
            promotion_context.get().get("category", "other")
        )
        if isinstance(self._poster, QueuePoster):
            results = await asyncio.gather(
                *(
                    self._poster.send_offer(
                        chat_id, text, image_file=image_file, parse_mode="Markdown"
                    )
                    for chat_id in destinations
                ),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    raise result
            return
        for chat_id in destinations:
            await self._poster.send_offer(
                chat_id, text, image_file=image_file, parse_mode="Markdown"
            )

    def _matching_destination_ids(self, category: str) -> tuple[str, ...]:
        return tuple(
            chat_id
            for chat_id in self._destination_chat_ids
            if accepts_category(self._destination_categories.get(chat_id), category)
        )

    async def _load_configs(self, db: AsyncSession) -> dict[str, object]:
        stmt = select(UserConfig).where(UserConfig.user_id == self.user_id)
        result = await db.execute(stmt)
        configs: dict[str, object] = {}
        for row in result.scalars().all():
            data = decrypt_config(row.config_data, row.user_id, row.config_type)
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
        destinations = result.scalars().all()
        self._destination_categories = {
            destination.chat_id: getattr(destination, "categories", None)
            for destination in destinations
        }
        return [destination.chat_id for destination in destinations]

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
        if platform == PLATFORM_KABUM:
            return self._awin
        if platform == PLATFORM_MAGALU:
            return self._magalu
        return None
