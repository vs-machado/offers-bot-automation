import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.worker import TelegramSession

LOGGER = logging.getLogger(__name__)


class PgSessionStore:
    def __init__(self, db: AsyncSession, user_id: int):
        self._db = db
        self._user_id = user_id

    async def get_session(self) -> str | None:
        stmt = select(TelegramSession).where(TelegramSession.user_id == self._user_id)
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        return row.session_string if row else None

    async def save_session(self, session_string: str) -> None:
        stmt = select(TelegramSession).where(TelegramSession.user_id == self._user_id)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.session_string = session_string
        else:
            self._db.add(
                TelegramSession(
                    user_id=self._user_id,
                    session_string=session_string,
                )
            )
        await self._db.commit()
        LOGGER.info("Session saved for user %s", self._user_id)
