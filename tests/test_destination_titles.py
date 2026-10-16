import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from backend.app.core.destination_titles import populate_destination_titles
from backend.worker.poster import BotPoster


class DestinationTitleTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_name_and_failed_lookup_fallback(self):
        for response, expected in [
            (
                httpx.Response(
                    200, json={"ok": True, "result": {"title": "  Ofertas VIP  "}}
                ),
                "Ofertas VIP",
            ),
            (httpx.Response(403, json={"ok": False}), None),
            (httpx.Response(200, text="invalid JSON"), None),
        ]:
            with self.subTest(expected=expected):
                client = AsyncMock()
                client.post.return_value = response
                with patch("backend.worker.poster.httpx.AsyncClient") as factory:
                    factory.return_value.__aenter__.return_value = client
                    self.assertEqual(
                        await BotPoster(token="test-token").get_chat_title("-100123"),
                        expected,
                    )
                self.assertTrue(client.post.call_args.args[0].endswith("/getChat"))
                self.assertEqual(
                    client.post.call_args.kwargs["json"], {"chat_id": "-100123"}
                )

    async def test_timeout_does_not_break_history(self):
        client = AsyncMock()
        client.post.side_effect = httpx.ReadTimeout("Telegram unavailable")
        with patch("backend.worker.poster.httpx.AsyncClient") as factory:
            factory.return_value.__aenter__.return_value = client
            self.assertIsNone(
                await BotPoster(token="test-token").get_chat_title("-100123")
            )

    async def test_cache_preserves_aliases_platform_and_tenant(self):
        def destination(user_id=1, platform="telegram", title=None, chat_id="-100123"):
            return SimpleNamespace(
                user_id=user_id, platform=platform, title=title, chat_id=chat_id
            )

        missing = destination()
        id_as_title = destination(title="-100456", chat_id="-100456")
        custom = destination(title="Minha seleção")
        other_user = destination(user_id=2)
        whatsapp = destination(platform="whatsapp")
        destinations = [missing, id_as_title, custom, other_user, whatsapp]
        db = AsyncMock()
        with (
            patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "test-token"}),
            patch.object(
                BotPoster,
                "get_chat_title",
                new_callable=AsyncMock,
                return_value="Ofertas VIP",
            ) as lookup,
        ):
            await populate_destination_titles(db, 1, destinations)
            self.assertEqual(lookup.await_count, 2)
            self.assertEqual(missing.title, "Ofertas VIP")
            self.assertEqual(id_as_title.title, "Ofertas VIP")
            self.assertEqual(custom.title, "Minha seleção")
            self.assertIsNone(other_user.title)
            self.assertIsNone(whatsapp.title)
            await populate_destination_titles(db, 1, destinations)
            self.assertEqual(lookup.await_count, 2)
        db.commit.assert_awaited_once()

    async def test_missing_token_does_not_query_database(self):
        db = AsyncMock()
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}):
            await populate_destination_titles(db, 1)
        db.execute.assert_not_awaited()
