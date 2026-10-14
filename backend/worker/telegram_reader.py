"""One operator-owned Telethon session for the platform source catalog."""

import os
import asyncio
import logging
from pathlib import Path

from telethon import utils
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest

from backend.app.core.source_groups import DEFAULT_SOURCE_GROUP_URLS
from offers_bot.postgres_store import PostgresSessionStore as SessionStore
from offers_bot.telegram_bot import TelegramOfferBot

LOGGER = logging.getLogger(__name__)


class TelegramSourceReader:
    def __init__(self, source_chats: list[str] | None = None):
        self._desired_sources = (
            DEFAULT_SOURCE_GROUP_URLS if source_chats is None else source_chats
        )
        self._sources: dict[str, str] = {}
        self._ready = False
        self._refresh_lock = asyncio.Lock()
        self._store = SessionStore()
        self._bot = TelegramOfferBot(
            api_id=int(os.environ["TELEGRAM_API_ID"]),
            api_hash=os.environ["TELEGRAM_API_HASH"],
            session_name="platform-reader",
            session_string=os.getenv("TELEGRAM_SESSION_STRING")
            or self._store.get_session(),
            source_chats=[],
            listen_all_chats=True,
            phone=os.getenv("TELEGRAM_PHONE") or None,
            qr_auth_port=int(os.getenv("QR_AUTH_PORT", "8081")),
        )

    async def listen(self, handler):
        try:
            await self._bot.start()
            if self._bot.session_string:
                await asyncio.to_thread(
                    self._store.save_session, self._bot.session_string
                )
            self._ready = True
            await self.refresh_sources(self._desired_sources)

            async def receive(chat_id, message_id, text, media_path):
                try:
                    source = self._sources.get(chat_id)
                    if source:
                        await handler(source, message_id, text, media_path)
                finally:
                    if media_path:
                        Path(media_path).unlink(missing_ok=True)

            await self._bot.listen(receive)
            raise RuntimeError("Shared Telegram reader disconnected")
        finally:
            await self._bot.client.disconnect()
            self._store.close()

    async def refresh_sources(self, urls: list[str]) -> None:
        """Apply enabled catalog changes without restarting or reauthenticating."""
        self._desired_sources = list(urls)
        if not self._ready:
            return
        async with self._refresh_lock:
            sources = {peer: url for peer, url in self._sources.items() if url in urls}
            self._sources = sources.copy()
            self._bot.set_allowed_source_ids(set(sources))
            for url in urls:
                if url in sources.values():
                    continue
                try:
                    entity = await self._bot.client.get_entity(url)
                    try:
                        await self._bot.client(JoinChannelRequest(entity))
                    except UserAlreadyParticipantError:
                        pass
                    sources[str(utils.get_peer_id(entity))] = url
                except Exception:
                    LOGGER.exception(
                        "Cannot read catalog group %s; will retry next refresh", url
                    )
            self._sources = sources
            self._bot.set_allowed_source_ids(set(sources))
