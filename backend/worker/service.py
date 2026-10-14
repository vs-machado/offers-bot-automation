import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import AsyncSessionLocal
from backend.app.core.source_groups import enabled_source_groups
from backend.app.models.user import UserConfig
from backend.worker.manager import UserBotInstance
from backend.worker.telegram_reader import TelegramSourceReader

LOGGER = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 30


class WorkerService:
    """Listen through shared Telethon account and route catalog subscriptions."""

    def __init__(self):
        self._bots: dict[int, UserBotInstance] = {}
        self._source_catalog: list[str] = []
        self._reader: TelegramSourceReader | None = None

    async def start(self) -> None:
        """Listen continuously and refresh user configuration every 30 seconds."""
        LOGGER.info("Worker service starting")
        await self._sync_bots()
        reader = TelegramSourceReader(self._source_catalog)
        self._reader = reader
        sync_task = asyncio.create_task(self._sync_loop())
        try:
            await reader.listen(self._receive_message)
        finally:
            sync_task.cancel()
            await asyncio.gather(sync_task, return_exceptions=True)

    async def _sync_loop(self) -> None:
        while True:
            try:
                await self._sync_bots()
            except Exception:
                LOGGER.exception("Error during worker sync")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _receive_message(self, source_chat, message_id, text, media_path):
        for bot in list(self._bots.values()):
            if source_chat not in bot.source_chats:
                continue
            try:
                await bot.process_message(
                    source_chat, message_id, text, source_image_url=media_path
                )
            except Exception:
                LOGGER.exception(
                    "Failed to deliver source message to user %s", bot.user_id
                )

    async def _sync_bots(self) -> None:
        async with AsyncSessionLocal() as db:
            self._source_catalog = [
                group.url for group in await enabled_source_groups(db)
            ]
            if self._reader:
                await self._reader.refresh_sources(self._source_catalog)
            candidate_user_ids = await self._get_candidate_user_ids(db)
            next_bots: dict[int, UserBotInstance] = {}
            for user_id in candidate_user_ids:
                bot = self._bots.get(user_id) or UserBotInstance(
                    user_id, AsyncSessionLocal
                )
                try:
                    await bot.configure(db, self._source_catalog)
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
