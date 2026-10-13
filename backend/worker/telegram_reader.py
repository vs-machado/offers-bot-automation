"""One operator-owned Telethon session for the platform source catalog."""

import os
from pathlib import Path

from telethon import utils
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest

from backend.app.core.source_groups import DEFAULT_SOURCE_GROUP_URLS
from offers_bot.session_store import SessionStore
from offers_bot.telegram_bot import TelegramOfferBot


class TelegramSourceReader:
    def __init__(self):
        self._store = SessionStore(
            Path(os.getenv("DATABASE_PATH", "data/offers.sqlite3"))
        )
        self._bot = TelegramOfferBot(
            api_id=int(os.environ["TELEGRAM_API_ID"]),
            api_hash=os.environ["TELEGRAM_API_HASH"],
            session_name="platform-reader",
            session_string=os.getenv("TELEGRAM_SESSION_STRING")
            or self._store.get_session(),
            source_chats=DEFAULT_SOURCE_GROUP_URLS,
            phone=os.getenv("TELEGRAM_PHONE") or None,
            qr_auth_port=int(os.getenv("QR_AUTH_PORT", "8081")),
        )

    async def listen(self, handler):
        try:
            await self._bot.start()
            if self._bot.session_string:
                self._store.save_session(self._bot.session_string)
            sources = {}
            for url in DEFAULT_SOURCE_GROUP_URLS:
                entity = await self._bot.client.get_entity(url)
                try:
                    await self._bot.client(JoinChannelRequest(entity))
                except UserAlreadyParticipantError:
                    pass
                sources[str(utils.get_peer_id(entity))] = url

            async def receive(chat_id, message_id, text, media_path):
                try:
                    source = sources.get(chat_id)
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
