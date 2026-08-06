import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import AsyncSessionLocal
from backend.app.core.telegram_sources import fetch_source_messages
from backend.app.models.user import UserConfig
from backend.worker.manager import UserBotInstance

LOGGER = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 30


class WorkerService:
    """Poll shared sources once, then fan messages out to subscribed users."""

    def __init__(self):
        self._bots: dict[int, UserBotInstance] = {}

    async def start(self) -> None:
        """Run 30-second config-sync and shared-source polling loop indefinitely."""
        LOGGER.info("Worker service starting")
        while True:
            try:
                await self._sync_bots()
                await self._poll_sources()
            except Exception:
                LOGGER.exception("Error during worker sync")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _sync_bots(self) -> None:
        async with AsyncSessionLocal() as db:
            candidate_user_ids = await self._get_candidate_user_ids(db)
            next_bots: dict[int, UserBotInstance] = {}
            for user_id in candidate_user_ids:
                bot = self._bots.get(user_id) or UserBotInstance(
                    user_id, AsyncSessionLocal
                )
                try:
                    await bot.configure(db)
                except Exception:
                    LOGGER.exception("Failed to configure bot for user %s", user_id)
                    continue
                if bot.active:
                    next_bots[user_id] = bot
                else:
                    LOGGER.info(
                        "User %s inactive: source, destination, or affiliate config missing",
                        user_id,
                    )
            for user_id, bot in self._bots.items():
                if user_id not in next_bots:
                    bot.close()
            self._bots = next_bots

    async def _get_candidate_user_ids(self, db: AsyncSession) -> set[int]:
        stmt = (
            select(UserConfig.user_id)
            .where(UserConfig.config_type == "source_chats")
            .distinct()
        )
        result = await db.execute(stmt)
        return {row[0] for row in result.fetchall()}

    async def _poll_sources(self) -> None:
        subscriptions: dict[str, list[UserBotInstance]] = {}
        for bot in self._bots.values():
            for source_chat in bot.source_chats:
                subscriptions.setdefault(source_chat, []).append(bot)

        if not subscriptions:
            return

        messages_by_chat = await fetch_source_messages(list(subscriptions), limit=20)
        for source_chat, messages in messages_by_chat.items():
            for message in messages:
                text = self._message_text(message.text, message.links)
                if not text:
                    continue
                for bot in subscriptions.get(source_chat, []):
                    await bot.process_message(
                        source_chat,
                        message.message_id,
                        text,
                        source_image_url=message.image_url,
                    )

    @staticmethod
    def _message_text(text: str, links: tuple[dict[str, str], ...]) -> str:
        hidden_urls = [link["url"] for link in links if link["url"] not in text]
        if not hidden_urls:
            return text
        return "\n".join([text, *hidden_urls]).strip()

    async def shutdown(self) -> None:
        """Close active per-user clients and clear worker state."""
        LOGGER.info("Worker service shutting down")
        for bot in self._bots.values():
            bot.close()
        self._bots.clear()
