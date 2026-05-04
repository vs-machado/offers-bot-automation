from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from telethon import TelegramClient, events
from telethon.errors import UserAlreadyParticipantError
from telethon.tl.functions.messages import CheckChatInviteRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import ChatInviteAlready

LOGGER = logging.getLogger(__name__)
INVITE_HASH_RE = re.compile(r"t\.me/(?:joinchat/|\+)([^/?#]+)")


MessageHandler = Callable[[str, int, str], Awaitable[None]]


class TelegramOfferBot:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        source_chats: list[str],
        target_chat: str,
    ) -> None:
        self.client = TelegramClient(session_name, api_id, api_hash)
        self._source_chats = source_chats
        self._target_chat = target_chat
        self._target_entity = None

    async def start(self) -> None:
        await self.client.start()
        self._target_entity = await self._resolve_chat(self._target_chat)

    async def listen(self, handler: MessageHandler, poll_existing: bool = False) -> None:
        source_entities = [await self._resolve_chat(chat) for chat in self._source_chats]
        for entity in source_entities:
            title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)
            LOGGER.info("Resolved source chat %s -> id=%s", title, entity.id)

        if poll_existing:
            for entity in source_entities:
                async for message in self.client.iter_messages(entity, limit=50):
                    if message.message:
                        await handler(str(entity.id), message.id, message.message)

        @self.client.on(events.NewMessage(chats=source_entities))
        async def on_new_message(event: events.NewMessage.Event) -> None:
            text = event.message.message or ""
            LOGGER.info(
                "Received Telegram message chat_id=%s message_id=%s chars=%s",
                event.chat_id,
                event.message.id,
                len(text),
            )
            if text:
                await handler(str(event.chat_id), event.message.id, text)

        LOGGER.info("Listening to %s source chats", len(source_entities))
        await self.client.run_until_disconnected()

    async def send_offer(self, text: str) -> None:
        if self._target_entity is None:
            self._target_entity = await self._resolve_chat(self._target_chat)
        await self.client.send_message(self._target_entity, text, link_preview=True)

    async def _resolve_chat(self, chat: str):
        chat = chat.strip()
        invite_match = INVITE_HASH_RE.search(chat)
        if invite_match:
            invite_hash = invite_match.group(1)
            try:
                updates = await self.client(ImportChatInviteRequest(invite_hash))
                return updates.chats[0]
            except UserAlreadyParticipantError:
                invite = await self.client(CheckChatInviteRequest(invite_hash))
                if isinstance(invite, ChatInviteAlready):
                    return invite.chat
                return await self.client.get_entity(chat)
        return await self.client.get_entity(int(chat) if chat.lstrip("-").isdigit() else chat)
