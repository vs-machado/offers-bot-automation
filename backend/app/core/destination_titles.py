"""Best-effort, tenant-scoped Telegram destination name caching."""

import asyncio
import os

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import DestinationChannel
from backend.worker.poster import BotPoster


async def populate_destination_titles(
    db: AsyncSession,
    user_id: int,
    destinations: list[DestinationChannel] | None = None,
) -> None:
    """Cache up to ten missing Telegram names; preserve aliases and API availability.

    Existing names avoid network calls on subsequent history polls. Failed lookups
    leave the ID fallback intact and never affect posting permissions.
    """
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        return
    if destinations is None:
        result = await db.execute(
            select(DestinationChannel)
            .where(
                DestinationChannel.user_id == user_id,
                DestinationChannel.platform == "telegram",
                or_(
                    DestinationChannel.title.is_(None),
                    DestinationChannel.title == "",
                    DestinationChannel.title == DestinationChannel.chat_id,
                ),
            )
            .order_by(DestinationChannel.id)
            .limit(10)
        )
        destinations = list(result.scalars().all())
    missing = [
        destination
        for destination in destinations
        if destination.user_id == user_id
        and destination.platform == "telegram"
        and (not destination.title or destination.title == destination.chat_id)
    ][:10]
    semaphore = asyncio.Semaphore(5)

    async def lookup(chat_id: str) -> str | None:
        async with semaphore:
            return await BotPoster().get_chat_title(chat_id)

    titles = await asyncio.gather(
        *(lookup(destination.chat_id) for destination in missing)
    )
    changed = False
    for destination, title in zip(missing, titles):
        if title:
            destination.title = title
            changed = True
    if changed:
        await db.commit()
