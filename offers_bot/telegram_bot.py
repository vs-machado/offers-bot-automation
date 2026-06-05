"""Telegram client wrapper with QR-first authentication.

Auth decision tree:
1. Session string passed in (from DB or env) → StringSession → authorized? → skip
2. TTY attached → interactive input() (local dev, backward compat)
3. Headless (Docker/server) → QR login via temporary HTTP server
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from collections.abc import Awaitable, Callable

from telethon import TelegramClient, events
from telethon.errors import AuthTokenExpiredError, UserAlreadyParticipantError
from telethon.sessions import StringSession
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest,
)
from telethon.tl.types import ChatInviteAlready, MessageMediaDocument, MessageMediaPhoto

from offers_bot.qr_auth import serve_qr_and_wait

LOGGER = logging.getLogger(__name__)
INVITE_HASH_RE = re.compile(r"t\.me/(?:joinchat/|\+)([^/?#]+)")

MessageHandler = Callable[[str, int, str, str | None], Awaitable[None]]


class TelegramOfferBot:
    """Telegram user-bot client for monitoring and posting affiliate offers."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        session_string: str | None = None,
        source_chats: list[str] | None = None,
        target_chat: str = "",
        phone: str | None = None,
        qr_auth_port: int = 8080,
        tech_chat: str | None = None,
        home_chat: str | None = None,
        clothes_chat: str | None = None,
    ) -> None:
        # Always use StringSession — portable, no disk I/O, Docker-safe
        session = StringSession(session_string) if session_string else StringSession()
        self.client = TelegramClient(session, api_id, api_hash)
        self._session_string = session_string
        self._qr_auth_port = qr_auth_port
        self._source_chats = source_chats or []
        self._target_chat = target_chat
        self._tech_chat = tech_chat
        self._home_chat = home_chat
        self._clothes_chat = clothes_chat
        self._target_entity = None
        self._tech_entity = None
        self._home_entity = None
        self._clothes_entity = None
        self._phone = phone

    @property
    def session_string(self) -> str | None:
        """The active Telegram session string, or ``None`` before login."""
        return self._session_string

    # ── Public API ──────────────────────────────────────────────

    async def start(self) -> None:
        """Authenticate (if needed) and resolve target chats.

        Auth strategy:
        - If ``StringSession`` already loaded and authorized → skip.
        - If ``TELEGRAM_PHONE`` is set → QR login (via HTTP server on ``qr_auth_port``).
        - If ``sys.stdin`` is a TTY → interactive ``input()`` prompts.
        - Otherwise → error (headless, no phone configured).
        """
        await self.client.connect()
        if not await self.client.is_user_authorized():
            if self._phone:
                await self._qr_login()
            elif sys.stdin.isatty():
                await self._interactive_login()
            else:
                raise RuntimeError(
                    "TELEGRAM_PHONE is required for QR login in headless mode. "
                    "Set it in your .env file."
                )

        # Export session string for persistence (unless already set)
        if not self._session_string:
            self._session_string = self.client.session.save()
            LOGGER.info("New session string acquired (saved to database automatically)")

        self._target_entity = await self._resolve_chat(self._target_chat)
        if self._tech_chat:
            self._tech_entity = await self._resolve_chat(self._tech_chat)
        if self._home_chat:
            self._home_entity = await self._resolve_chat(self._home_chat)
        if self._clothes_chat:
            self._clothes_entity = await self._resolve_chat(self._clothes_chat)

    async def listen(
        self, handler: MessageHandler, poll_existing: bool = False
    ) -> None:
        """Register a handler for new messages in source chats."""
        source_entities = [
            await self._resolve_chat(chat) for chat in self._source_chats
        ]
        for entity in source_entities:
            title = (
                getattr(entity, "title", None)
                or getattr(entity, "username", None)
                or str(entity.id)
            )
            LOGGER.info("Resolved source chat %s -> id=%s", title, entity.id)

        if poll_existing:
            for entity in source_entities:
                async for message in self.client.iter_messages(entity, limit=50):
                    if message.message:
                        media_path = await self._download_media(message)
                        await handler(
                            str(entity.id), message.id, message.message, media_path
                        )

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
                media_path = await self._download_media(event.message)
                await handler(str(event.chat_id), event.message.id, text, media_path)

        LOGGER.info("Listening to %s source chats", len(source_entities))
        await self.client.run_until_disconnected()

    async def send_offer(
        self, text: str, image_file: str | None = None, category: str | None = None
    ) -> None:
        """Send a formatted offer to the target chat (and category chats)."""
        if self._target_entity is None:
            self._target_entity = await self._resolve_chat(self._target_chat)

        if category == "tech":
            targets = [self._target_entity]
            if self._tech_entity is not None:
                targets.append(self._tech_entity)
        elif category == "home":
            targets = [self._target_entity]
            if self._home_entity is not None:
                targets.append(self._home_entity)
        elif category == "clothes":
            targets = [self._target_entity]
            if self._clothes_entity is not None:
                targets.append(self._clothes_entity)
        else:
            targets = [self._target_entity]

        for entity in targets:
            if image_file:
                await self.client.send_message(
                    entity, text, file=image_file, link_preview=False
                )
            else:
                await self.client.send_message(entity, text, link_preview=True)

    # ── Auth helpers ────────────────────────────────────────────

    async def _interactive_login(self) -> None:
        """Interactive login via terminal ``input()``. Backward-compatible."""
        LOGGER.info("Interactive login (TTY detected)")
        phone = self._phone or input("Enter phone number: ")

        def _code_callback() -> str:
            return input("Enter Telegram code: ")

        def _password_callback() -> str | None:
            return input("Enter 2FA password (or empty): ") or None

        await self.client.start(
            phone=phone,
            code_callback=_code_callback,
            password=_password_callback,
        )

    async def _qr_login(self) -> None:
        """QR login for headless environments (Docker/server).

        Requires ``TELEGRAM_PHONE`` to be set in environment.
        Starts a temporary HTTP server serving the QR code.
        """
        LOGGER.info("QR login (headless mode)")

        if not self._phone:
            raise RuntimeError(
                "TELEGRAM_PHONE is required for QR login in headless mode. "
                "Set it in your .env file."
            )

        while True:
            qr_login = await self.client.qr_login()
            try:
                await serve_qr_and_wait(
                    login_url=qr_login.url,
                    wait_coro=qr_login.wait(120),
                    port=self._qr_auth_port,
                )
                return  # success
            except AuthTokenExpiredError:
                LOGGER.warning("QR token expired, generating a new one...")
                continue
            except asyncio.TimeoutError:
                raise RuntimeError(
                    "QR login timed out after 120 seconds. "
                    "Restart the container to generate a new QR code."
                ) from None

    # ── Internal helpers ────────────────────────────────────────

    async def _download_media(self, message) -> str | None:
        if message.media and (
            isinstance(message.media, MessageMediaPhoto)
            or isinstance(message.media, MessageMediaDocument)
        ):
            try:
                return await self.client.download_media(message, file="/tmp/")
            except Exception as exc:
                LOGGER.warning("Failed to download media: %s", exc)
        return None

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
        return await self.client.get_entity(
            int(chat) if chat.lstrip("-").isdigit() else chat
        )
