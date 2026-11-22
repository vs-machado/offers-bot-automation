import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.app.api.v1.endpoints.users import _validate_config
from backend.app.schemas.user import UserConfigCreate
from offers_bot import llm_parser
from offers_bot.nvidia_models import DEFAULT_MODELS, validate_models


class NvidiaPreferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_order_and_no_retry_after_secondary_success(self):
        primary, secondary = reversed(DEFAULT_MODELS)
        first = MagicMock(run=AsyncMock(side_effect=TimeoutError))
        second = MagicMock(run=AsyncMock())
        with (
            patch.dict(
                os.environ,
                {"NVIDIA_API_KEY": "test", "OPENROUTER_API_KEY": "router"},
                clear=True,
            ),
            patch.object(
                llm_parser, "_build_agent", side_effect=[first, second]
            ) as build,
            patch.object(
                llm_parser, "_dump_result", return_value={"classification": "product"}
            ),
        ):
            self.assertEqual(
                await llm_parser.parse_with_llm_async(
                    "Oferta", nvidia_models=(primary, secondary)
                ),
                {"classification": "product"},
            )
        self.assertEqual(
            [c.args[0] for c in build.call_args_list], [primary, secondary]
        )

    def test_dashboard_rejects_duplicate_or_unverified_models(self):
        primary, secondary = DEFAULT_MODELS
        self.assertEqual(
            validate_models({"primary": primary, "secondary": secondary}),
            DEFAULT_MODELS,
        )
        for invalid in (primary, "nvidia/embed-qa-4"):
            config = UserConfigCreate(
                config_type="nvidia_models",
                config_data={"primary": primary, "secondary": invalid},
            )
            with self.assertRaises(HTTPException):
                _validate_config(config)
