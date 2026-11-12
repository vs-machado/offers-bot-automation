import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx

from offers_bot import llm_parser


KEYS = {
    "NVIDIA_API_KEY": "nvidia-test",
    "NVIDIA_FALLBACK_MODEL": llm_parser.NVIDIA_FALLBACK_LLM_MODEL,
    "OPENROUTER_API_KEY": "router-test",
}
ATTEMPTS = [
    call(llm_parser.NVIDIA_LLM_MODEL, "nvidia-test"),
    call(llm_parser.NVIDIA_FALLBACK_LLM_MODEL, "nvidia-test"),
    call(llm_parser.PRIMARY_LLM_MODEL, "router-test"),
]


class LightningFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_and_async_advance_through_nvidia_then_ling(self):
        for asynchronous in (False, True):
            for success in (1, 2):
                with self.subTest(asynchronous=asynchronous, success=success):
                    agents = [MagicMock(run=AsyncMock()) for _ in range(3)]
                    for agent in agents[:success]:
                        agent.run.side_effect = RuntimeError("timeout")
                        agent.run_sync.side_effect = RuntimeError("timeout")
                    with (
                        patch.dict(os.environ, KEYS, clear=True),
                        patch.object(
                            llm_parser, "_build_agent", side_effect=agents
                        ) as build,
                        patch.object(
                            llm_parser,
                            "_dump_result",
                            return_value={"classification": "product"},
                        ),
                        patch.object(llm_parser, "logger"),
                    ):
                        if asynchronous:
                            result = await llm_parser.parse_with_llm_async("Oferta")
                        else:
                            result = llm_parser.parse_with_llm("Oferta")
                    self.assertEqual(result, {"classification": "product"})
                    self.assertEqual(build.call_args_list, ATTEMPTS[: success + 1])

    async def test_lightning_uses_prompted_json_and_records_its_model(self):
        bodies = []

        def respond(request):
            body = json.loads(request.content)
            bodies.append(body)
            return httpx.Response(
                200,
                json={
                    "id": "lightning-test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": llm_parser.NVIDIA_FALLBACK_LLM_MODEL,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "classification": "product",
                                        "products": [
                                            {
                                                "title": "Monitor LG",
                                                "price": "R$ 599,90",
                                                "meli_plus_only": False,
                                                "urls": [
                                                    "https://www.amazon.com.br/dp/B0C1234567"
                                                ],
                                            }
                                        ],
                                    }
                                ),
                            },
                        }
                    ],
                },
            )

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"DATABASE_PATH": str(Path(directory) / "usage.sqlite3")},
                clear=True,
            ),
        ):
            with patch.object(
                llm_parser,
                "DefaultAsyncHttpxClient",
                side_effect=lambda **kwargs: httpx.AsyncClient(
                    transport=httpx.MockTransport(respond), **kwargs
                ),
            ):
                agent = llm_parser._build_agent(
                    llm_parser.NVIDIA_FALLBACK_LLM_MODEL, "fake-key"
                )
                client = agent.model.provider.client
                self.assertEqual(client.timeout, 30.0)
                self.assertEqual(client.max_retries, 0)
                try:
                    result = await agent.run("Monitor LG R$ 599,90")
                    self.assertEqual(result.output.products[0].title, "Monitor LG")
                finally:
                    await client.close()
            with sqlite3.connect(os.environ["DATABASE_PATH"]) as conn:
                self.assertEqual(
                    conn.execute("SELECT provider,model FROM llm_requests").fetchall(),
                    [("nvidia", llm_parser.NVIDIA_FALLBACK_LLM_MODEL)],
                )
        body = bodies[0]
        self.assertNotIn("tools", body)
        self.assertNotEqual(body.get("response_format", {}).get("type"), "json_schema")
        self.assertFalse(body["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(body["thinking"], {"type": "disabled"})
