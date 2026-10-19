import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
from openai import AsyncOpenAI

from offers_bot import llm_parser


KEYS = {"OPENROUTER_API_KEY": "openrouter-key", "GEMINI_API_KEY": "gemini-key"}
RESULT = {"classification": "product", "products": []}
EXPECTED_ATTEMPTS = [
    call("inclusionai/ling-3.0-flash", "openrouter-key"),
    call("qwen/qwen3.7-flash", "openrouter-key"),
    call("google/gemini-2.5-flash-lite", "gemini-key"),
]


class ParserFallbackTests(unittest.TestCase):
    def test_sync_falls_back_in_order_and_stops_on_success(self):
        for successful_index in range(3):
            with self.subTest(successful_index=successful_index):
                agents = [MagicMock() for _ in range(3)]
                for agent in agents[:successful_index]:
                    agent.run_sync.side_effect = RuntimeError("Provider unavailable")
                with (
                    patch.dict(os.environ, KEYS, clear=True),
                    patch.object(
                        llm_parser, "_build_agent", side_effect=agents
                    ) as build,
                    patch.object(llm_parser, "_dump_result", return_value=RESULT),
                    patch.object(llm_parser, "logger"),
                ):
                    self.assertEqual(llm_parser.parse_with_llm("Oferta"), RESULT)
                self.assertEqual(
                    build.call_args_list, EXPECTED_ATTEMPTS[: successful_index + 1]
                )


class AsyncParserFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_tries_gemini_after_both_openrouter_models_fail(self):
        agents = [MagicMock(run=AsyncMock()) for _ in range(3)]
        for agent in agents[:2]:
            agent.run.side_effect = RuntimeError("Provider unavailable")
        with (
            patch.dict(os.environ, KEYS, clear=True),
            patch.object(llm_parser, "_build_agent", side_effect=agents) as build,
            patch.object(llm_parser, "_dump_result", return_value=RESULT),
            patch.object(llm_parser, "logger"),
        ):
            self.assertEqual(await llm_parser.parse_with_llm_async("Oferta"), RESULT)
        self.assertEqual(build.call_args_list, EXPECTED_ATTEMPTS)

    async def test_missing_openrouter_key_skips_ling_and_qwen(self):
        agent = MagicMock(run=AsyncMock())
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key"}, clear=True),
            patch.object(llm_parser, "_build_agent", return_value=agent) as build,
            patch.object(llm_parser, "_dump_result", return_value=RESULT),
            patch.object(llm_parser, "logger"),
        ):
            self.assertEqual(await llm_parser.parse_with_llm_async("Oferta"), RESULT)
        build.assert_called_once_with("google/gemini-2.5-flash-lite", "gemini-key")

    async def test_all_provider_failures_return_none_for_regex_fallback(self):
        agent = MagicMock(
            run=AsyncMock(side_effect=RuntimeError("Provider unavailable"))
        )
        with (
            patch.dict(os.environ, KEYS, clear=True),
            patch.object(llm_parser, "_build_agent", return_value=agent) as build,
            patch.object(llm_parser, "logger"),
        ):
            self.assertIsNone(await llm_parser.parse_with_llm_async("Oferta"))
        self.assertEqual(build.call_args_list, EXPECTED_ATTEMPTS)

    async def test_openrouter_request_routes_ling_only_to_novita(self):
        for model_name in ("inclusionai/ling-3.0-flash", "qwen/qwen3.7-flash"):
            with self.subTest(model=model_name):
                requests = []

                def respond(request):
                    body = json.loads(request.content)
                    requests.append(body)
                    tool_name = body["tools"][0]["function"]["name"]
                    return httpx.Response(
                        200,
                        json={
                            "id": "test-completion",
                            "object": "chat.completion",
                            "created": 0,
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "finish_reason": "tool_calls",
                                    "message": {
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [
                                            {
                                                "id": "test-call",
                                                "type": "function",
                                                "function": {
                                                    "name": tool_name,
                                                    "arguments": json.dumps(RESULT),
                                                },
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                    )

                async with AsyncOpenAI(
                    api_key="fake-key",
                    base_url=llm_parser.OPENROUTER_BASE_URL,
                    http_client=httpx.AsyncClient(
                        transport=httpx.MockTransport(respond)
                    ),
                ) as client:
                    with patch.object(llm_parser, "AsyncOpenAI", return_value=client):
                        agent = llm_parser._build_agent(model_name, "fake-key")
                        result = await agent.run("Oferta")
                self.assertEqual(result.output.classification, "product")
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["model"], model_name)
                if model_name == "inclusionai/ling-3.0-flash":
                    self.assertEqual(
                        requests[0]["provider"],
                        {"only": ["novita"], "allow_fallbacks": False},
                    )
                else:
                    self.assertNotIn("provider", requests[0])
