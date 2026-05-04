from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session: str
    telegram_phone: str | None
    source_chats: list[str]
    target_chat: str
    ml_affiliate_tag: str
    ml_cookie_header: str
    ml_csrf_token: str
    poll_existing_messages: bool
    database_path: Path
    browser_resolver_enabled: bool
    browser_headless: bool
    browser_timeout_ms: int
    browser_debug_dir: Path | None


def load_settings() -> Settings:
    load_dotenv()

    missing = [
        name
        for name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "SOURCE_CHATS", "TARGET_CHAT")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    return Settings(
        telegram_api_id=int(os.environ["TELEGRAM_API_ID"]),
        telegram_api_hash=os.environ["TELEGRAM_API_HASH"],
        telegram_session=os.getenv("TELEGRAM_SESSION", "data/offers_bot"),
        telegram_phone=os.getenv("TELEGRAM_PHONE"),
        source_chats=_split_csv(os.environ["SOURCE_CHATS"]),
        target_chat=os.environ["TARGET_CHAT"].strip(),
        ml_affiliate_tag=os.getenv("ML_AFFILIATE_TAG", "").strip(),
        ml_cookie_header=os.getenv("ML_COOKIE_HEADER", "").strip(),
        ml_csrf_token=os.getenv("ML_CSRF_TOKEN", "").strip(),
        poll_existing_messages=os.getenv("POLL_EXISTING_MESSAGES", "false").lower() == "true",
        database_path=Path(os.getenv("DATABASE_PATH", "data/offers.sqlite3")),
        browser_resolver_enabled=os.getenv("BROWSER_RESOLVER_ENABLED", "true").lower() == "true",
        browser_headless=os.getenv("BROWSER_HEADLESS", "true").lower() == "true",
        browser_timeout_ms=int(os.getenv("BROWSER_TIMEOUT_MS", "15000")),
        browser_debug_dir=Path(os.environ["BROWSER_DEBUG_DIR"]) if os.getenv("BROWSER_DEBUG_DIR") else None,
    )
