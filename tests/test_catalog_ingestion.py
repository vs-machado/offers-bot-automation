import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.app.api.v1.endpoints.users import _validate_config
from backend.app.core.source_groups import approved_source
from backend.app.schemas.user import UserConfigCreate
from backend.worker.service import WorkerService
from offers_bot.telegram_bot import TelegramOfferBot


class CatalogTests(unittest.TestCase):
    def test_only_catalog_sources_are_accepted(self):
        self.assertEqual(approved_source("@PROMOTOM"), "https://t.me/promotom")
        for chat in (
            "@mygroup",
            "https://evil.example/promotom",
            "https://t.me/+invite",
            "-100123",
        ):
            with self.subTest(chat=chat), self.assertRaises(ValueError):
                approved_source(chat)

    def test_config_validation_blocks_custom_and_malformed_sources(self):
        for chats in (["@mygroup"], "@promotom", [123], None):
            config = UserConfigCreate(
                config_type="source_chats", config_data={"source_chats": chats}
            )
            with self.subTest(chats=chats), self.assertRaises(HTTPException):
                _validate_config(config)

    def test_config_normalizes_catalog_selections(self):
        config = UserConfigCreate(
            config_type="source_chats",
            config_data={"source_chats": ["@promotom", "https://t.me/promotom"]},
        )
        _validate_config(config)
        self.assertEqual(
            config.config_data, {"source_chats": ["https://t.me/promotom"]}
        )

    def test_telethon_hidden_links_survive_ingestion(self):
        message = SimpleNamespace(
            message="Deal: buy now",
            entities=[SimpleNamespace(url="https://amzn.to/example")],
        )
        self.assertEqual(
            TelegramOfferBot._message_text(message),
            "Deal: buy now\nhttps://amzn.to/example",
        )


class FanoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_message_reaches_only_subscribed_users(self):
        service = WorkerService()
        subscribed = SimpleNamespace(
            source_chats=("https://t.me/promotom",),
            process_message=AsyncMock(),
            user_id=1,
        )
        other = SimpleNamespace(
            source_chats=("https://t.me/promochina",),
            process_message=AsyncMock(),
            user_id=2,
        )
        service._bots = {1: subscribed, 2: other}
        await service._receive_message("https://t.me/promotom", 123, "Deal", None)
        subscribed.process_message.assert_awaited_once_with(
            "https://t.me/promotom", 123, "Deal", source_image_url=None
        )
        other.process_message.assert_not_awaited()

    async def test_listener_persists_shared_session_and_cleans_download(self):
        from backend.worker.telegram_reader import TelegramSourceReader

        bot = MagicMock()
        bot.start = AsyncMock()
        bot.session_string = "operator-session"
        bot.client.get_entity = AsyncMock(return_value=SimpleNamespace(id=7))
        bot.client.disconnect = AsyncMock()
        bot.client = AsyncMock(wraps=bot.client)

        async def listen(callback):
            await callback("-1007", 42, "Deal", "temporary.jpg")

        bot.listen = listen
        handler = AsyncMock()
        with (
            patch.dict(
                "os.environ", {"TELEGRAM_API_ID": "123", "TELEGRAM_API_HASH": "hash"}
            ),
            patch("backend.worker.telegram_reader.SessionStore") as store,
            patch("backend.worker.telegram_reader.TelegramOfferBot", return_value=bot),
            patch(
                "backend.worker.telegram_reader.DEFAULT_SOURCE_GROUP_URLS",
                ["https://t.me/promotom"],
            ),
            patch(
                "backend.worker.telegram_reader.utils.get_peer_id", return_value=-1007
            ),
            patch("backend.worker.telegram_reader.Path.unlink") as unlink,
        ):
            reader = TelegramSourceReader()
            with self.assertRaises(RuntimeError):
                await reader.listen(handler)
            store.return_value.save_session.assert_called_once_with("operator-session")
            store.return_value.close.assert_called_once()
            handler.assert_awaited_once_with(
                "https://t.me/promotom", 42, "Deal", "temporary.jpg"
            )
            unlink.assert_called_once_with(missing_ok=True)
            bot.client.disconnect.assert_awaited_once()
