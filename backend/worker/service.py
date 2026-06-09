import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import AsyncSessionLocal
from backend.app.models.user import UserConfig
from backend.worker.manager import UserBotInstance

LOGGER = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 60


class WorkerService:
    def __init__(self):
        self._bots: dict[int, UserBotInstance] = {}

    async def start(self) -> None:
        LOGGER.info("Worker service starting")
        while True:
            try:
                await self._sync_bots()
            except Exception:
                LOGGER.exception("Error during bot sync")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _sync_bots(self) -> None:
        async with AsyncSessionLocal() as db:
            active_user_ids = await self._get_active_user_ids(db)

        to_start = active_user_ids - self._bots.keys()
        to_stop = self._bots.keys() - active_user_ids

        for user_id in to_stop:
            bot = self._bots.pop(user_id)
            await bot.stop()

        for user_id in to_start:
            bot = UserBotInstance(user_id, AsyncSessionLocal)
            try:
                async with AsyncSessionLocal() as db:
                    await bot.start(db)
                self._bots[user_id] = bot
                LOGGER.info("Started bot for user %s", user_id)
            except Exception:
                LOGGER.exception("Failed to start bot for user %s", user_id)

    async def _get_active_user_ids(self, db: AsyncSession) -> set[int]:
        stmt = (
            select(UserConfig.user_id)
            .where(UserConfig.config_type == "telegram")
            .distinct()
        )
        result = await db.execute(stmt)
        return {row[0] for row in result.fetchall()}

    async def shutdown(self) -> None:
        LOGGER.info("Worker service shutting down")
        for user_id, bot in list(self._bots.items()):
            await bot.stop()
        self._bots.clear()
