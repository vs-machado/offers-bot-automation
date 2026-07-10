import json
import unittest

from backend.app.core.telegram_sources import (
    TelegramMessageHTMLParser,
    public_telegram_url,
)
from backend.app.models.user import DestinationChannel, UserConfig
from backend.worker.manager import UserBotInstance
from backend.worker.service import WorkerService


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self, configs, destinations):
        self._configs = configs
        self._destinations = destinations

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is UserConfig:
            return _FakeResult(self._configs)
        if entity is DestinationChannel:
            return _FakeResult(self._destinations)
        raise AssertionError(f"Unexpected query entity: {entity}")


class TelegramSourceTests(unittest.TestCase):
    def test_public_telegram_url_accepts_supported_forms(self):
        self.assertEqual(public_telegram_url("@promotom"), "https://t.me/s/promotom")
        self.assertEqual(
            public_telegram_url("https://t.me/s/promotom/123"),
            "https://t.me/s/promotom",
        )
        self.assertIsNone(public_telegram_url("https://example.com/promotom"))

    def test_parser_keeps_real_message_id_and_hidden_link(self):
        parser = TelegramMessageHTMLParser()
        parser.feed(
            """
            <div class="tgme_widget_message_wrap">
              <div class="tgme_widget_message" data-post="promotom/98765">
                <div class="tgme_widget_message_text js-message_text">
                  Deal <a href="https://amzn.to/example">buy now</a>
                </div>
              </div>
            </div>
            """
        )

        self.assertEqual(parser.messages[0]["message_id"], 98765)
        self.assertEqual(
            parser.messages[0]["links"],
            [{"url": "https://amzn.to/example", "text": "buy now"}],
        )

    def test_hidden_links_are_added_to_worker_message_text(self):
        text = WorkerService._message_text(
            "Deal: buy now",
            ({"url": "https://amzn.to/example", "text": "buy now"},),
        )
        self.assertEqual(text, "Deal: buy now\nhttps://amzn.to/example")


class UserBotConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_configure_uses_database_settings_without_telegram_config(self):
        configs = [
            UserConfig(
                user_id=7,
                config_type="source_chats",
                config_data=json.dumps({"source_chats": ["https://t.me/promotom"]}),
            ),
            UserConfig(
                user_id=7,
                config_type="amazon",
                config_data=json.dumps(
                    {
                        "amazon_affiliate_tag": "example-20",
                        "amazon_cookie_header": "session-id=test",
                    }
                ),
            ),
        ]
        destinations = [DestinationChannel(user_id=7, chat_id="-100123", enabled=True)]
        bot = UserBotInstance(user_id=7, db_factory=None)

        await bot.configure(_FakeSession(configs, destinations))

        self.assertTrue(bot.active)
        self.assertEqual(bot.source_chats, ("https://t.me/promotom",))


if __name__ == "__main__":
    unittest.main()
