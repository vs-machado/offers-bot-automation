import re
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import SourceGroup


DEFAULT_SOURCE_GROUP_URLS = [
    "https://t.me/promotom",
    "https://t.me/fumotom",
    "https://t.me/promochina",
    "https://t.me/promotop",
    "https://t.me/peperaiohardware",
    "https://t.me/achadinhomily",
    "https://t.me/achadinhossdamily1",
]


def normalize_source(chat: str) -> str:
    """Canonicalize a public Telegram username; reject invites and external URLs."""
    value = chat.strip()
    if value.startswith("@"):
        name = value[1:]
    elif "://" in value:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc.lower() != "t.me"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use a public Telegram group URL or @username")
        name = parsed.path.strip("/")
    else:
        name = value
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", name):
        raise ValueError("Use a public Telegram group URL or @username")
    return f"https://t.me/{name.lower()}"


async def enabled_source_groups(db: AsyncSession) -> list[SourceGroup]:
    """Read enabled catalog entries; an empty catalog enables no sources."""
    result = await db.execute(
        select(SourceGroup)
        .where(SourceGroup.enabled.is_(True))
        .order_by(SourceGroup.id)
    )
    return list(result.scalars().all())


def approved_source(chat: str, catalog: list[str] | None = None) -> str:
    """Return canonical catalog URL; reject user-supplied sources."""
    url = normalize_source(chat)
    if url in (DEFAULT_SOURCE_GROUP_URLS if catalog is None else catalog):
        return url
    raise ValueError("Select a source group from the platform catalog")
