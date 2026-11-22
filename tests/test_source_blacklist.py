import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from cryptography.fernet import Fernet
from fastapi import HTTPException

from backend.app.api.v1.endpoints.users import _validate_config, update_config
from backend.app.schemas.user import UserConfigCreate
from backend.worker.manager import UserBotInstance

SOURCE = "https://t.me/promotom"
OTHER_SOURCE = "https://t.me/promochina"
BLACKLISTS = [{"source": SOURCE, "terms": ["sacos", "papel toalha"]}]


def source_config(**data):
    return UserConfigCreate(config_type="source_chats", config_data=data)


class SourceBlacklistConfigTests(unittest.IsolatedAsyncioTestCase):
    def test_normalizes_terms_and_rejects_unavailable_sources(self):
        config = source_config(
            source_chats=[SOURCE],
            source_blacklists=[
                {"source": "@PROMOTOM", "terms": [" sacos ", "SÁCOS", "papel   toalha"]}
            ],
        )
        _validate_config(config)
        self.assertEqual(config.config_data["source_blacklists"], BLACKLISTS)

        for entry in (
            {"source": "@notincatalog", "terms": ["sacos"]},
            {"source": SOURCE, "terms": "sacos"},
            {"source": SOURCE, "terms": ["***"]},
        ):
            with self.subTest(entry=entry), self.assertRaises(HTTPException):
                _validate_config(
                    source_config(source_chats=[SOURCE], source_blacklists=[entry])
                )

    async def test_selection_only_update_preserves_blacklist_and_empty_list_clears_it(
        self,
    ):
        saved = SimpleNamespace(
            id=1,
            user_id=7,
            config_type="source_chats",
            config_data=json.dumps(
                {"source_chats": [SOURCE], "source_blacklists": BLACKLISTS}
            ),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = saved
        db = AsyncMock()
        db.execute.return_value = result
        with (
            patch.dict(
                "os.environ",
                {"CREDENTIALS_ENCRYPTION_KEY": Fernet.generate_key().decode()},
            ),
            patch(
                "backend.app.api.v1.endpoints.users.enabled_source_groups",
                return_value=[SimpleNamespace(url=SOURCE)],
            ),
        ):
            response = await update_config(
                1, source_config(source_chats=[]), SimpleNamespace(id=7), db
            )
            self.assertEqual(response["config_data"]["source_blacklists"], BLACKLISTS)
            response = await update_config(
                1,
                source_config(source_chats=[SOURCE], source_blacklists=[]),
                SimpleNamespace(id=7),
                db,
            )
            self.assertNotIn("source_blacklists", response["config_data"])


class SourceBlacklistWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_skips_matching_products_only_for_their_source(self):
        bot = UserBotInstance(user_id=7, db_factory=MagicMock())
        self.addCleanup(bot.close)
        with (
            patch.object(
                bot,
                "_load_configs",
                return_value={
                    "source_chats": [SOURCE, OTHER_SOURCE],
                    "source_blacklists": BLACKLISTS,
                },
            ),
            patch.object(bot, "_load_destination_chat_ids", return_value=[]),
        ):
            await bot.configure(AsyncMock())

        offers = [
            SimpleNamespace(title="Kit de SÁCOS reforçados", url="blocked-word"),
            SimpleNamespace(title="Papel-toalha", url="blocked-phrase"),
            SimpleNamespace(title="Casacos de inverno", url="allowed"),
        ]
        store = SimpleNamespace(seen=AsyncMock(return_value=True))
        with (
            patch("backend.worker.manager.extract_offers_async", return_value=offers),
            patch("backend.worker.manager.PgOfferStore", return_value=store),
        ):
            await bot.process_message(SOURCE, 1, "post de múltiplas ofertas")
            await bot.process_message(OTHER_SOURCE, 2, "mesmas ofertas de outra origem")

        self.assertEqual(
            store.seen.await_args_list,
            [
                call(SOURCE, 1, "allowed"),
                call(OTHER_SOURCE, 2, "blocked-word"),
                call(OTHER_SOURCE, 2, "blocked-phrase"),
                call(OTHER_SOURCE, 2, "allowed"),
            ],
        )
