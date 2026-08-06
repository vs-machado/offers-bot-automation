from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.worker import ProcessedOffer


class PgOfferStore:
    """Track per-user processed offers for time-window deduplication."""

    def __init__(
        self, db: AsyncSession, user_id: int, duplicate_window_minutes: int = 30
    ):
        self._db = db
        self._user_id = user_id
        self._duplicate_window = timedelta(minutes=duplicate_window_minutes)

    async def seen(self, source_chat: str, message_id: int, source_url: str) -> bool:
        """Return whether source message URL was processed within deduplication window."""
        cutoff = datetime.utcnow() - self._duplicate_window
        stmt = select(ProcessedOffer).where(
            ProcessedOffer.user_id == self._user_id,
            ProcessedOffer.source_chat == source_chat,
            ProcessedOffer.source_message_id == message_id,
            ProcessedOffer.source_url == source_url,
            ProcessedOffer.created_at >= cutoff,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def seen_affiliate_url(self, affiliate_url: str) -> bool:
        """Return whether affiliate URL was processed within deduplication window."""
        cutoff = datetime.utcnow() - self._duplicate_window
        stmt = select(ProcessedOffer).where(
            ProcessedOffer.user_id == self._user_id,
            ProcessedOffer.affiliate_url == affiliate_url,
            ProcessedOffer.created_at >= cutoff,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def seen_product_key(self, product_key: str) -> bool:
        """Return whether normalized product key was processed within deduplication window."""
        cutoff = datetime.utcnow() - self._duplicate_window
        stmt = select(ProcessedOffer).where(
            ProcessedOffer.user_id == self._user_id,
            ProcessedOffer.product_key == product_key,
            ProcessedOffer.created_at >= cutoff,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark(
        self,
        source_chat: str,
        message_id: int,
        source_url: str,
        affiliate_url: str | None = None,
        product_key: str | None = None,
    ) -> None:
        """Record source and affiliate identity after processing attempt."""
        entry = ProcessedOffer(
            user_id=self._user_id,
            source_chat=source_chat,
            source_message_id=message_id,
            source_url=source_url,
            affiliate_url=affiliate_url,
            product_key=product_key,
        )
        self._db.add(entry)
        await self._db.commit()
