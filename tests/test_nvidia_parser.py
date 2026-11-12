import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from openai import AsyncOpenAI

from offers_bot import llm_parser


class NvidiaParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_nvidia_failure_falls_back_to_ling(self):
        primary = MagicMock(run=AsyncMock(side_effect=RuntimeError("unavailable")))
        fallback = MagicMock(run=AsyncMock())
        with (
            patch.dict(
                os.environ,
                {"NVIDIA_API_KEY": "nvidia-test", "OPENROUTER_API_KEY": "router-test"},
                clear=True,
            ),
            patch.object(
                llm_parser, "_build_agent", side_effect=[primary, fallback]
            ) as build,
            patch.object(
                llm_parser, "_dump_result", return_value={"classification": "product"}
            ),
        ):
            self.assertEqual(
                (await llm_parser.parse_with_llm_async("Oferta"))["classification"],
                "product",
            )
        self.assertEqual(
            build.call_args_list[0].args, (llm_parser.NVIDIA_LLM_MODEL, "nvidia-test")
        )
        self.assertEqual(
            build.call_args_list[1].args, ("inclusionai/ling-3.0-flash", "router-test")
        )

    async def test_nvidia_structured_output_and_http_attempt_accounting(self):
        bodies = []

        def respond(request):
            body = json.loads(request.content)
            bodies.append(body)
            if len(bodies) == 1:
                return httpx.Response(503, json={"error": {"message": "unavailable"}})
            return httpx.Response(
                200,
                json={
                    "id": "test",
                    "object": "chat.completion",
                    "created": 0,
                    "model": llm_parser.NVIDIA_LLM_MODEL,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {"classification": "product", "products": []}
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
            async with AsyncOpenAI(
                api_key="test-key",
                base_url=llm_parser.NVIDIA_BASE_URL,
                max_retries=0,
                http_client=httpx.AsyncClient(
                    transport=httpx.MockTransport(respond),
                    event_hooks={"request": [llm_parser._record_llm_request]},
                ),
            ) as client:
                with patch.object(llm_parser, "AsyncOpenAI", return_value=client):
                    agent = llm_parser._build_agent(
                        llm_parser.NVIDIA_LLM_MODEL, "test-key"
                    )
                    with self.assertRaises(Exception):
                        await agent.run("Oferta")
                    result = await agent.run("Oferta")
                    self.assertEqual(result.output.classification, "product")
            with sqlite3.connect(os.environ["DATABASE_PATH"]) as conn:
                rows = conn.execute(
                    "SELECT provider, model, COUNT(*) FROM llm_requests GROUP BY provider, model"
                ).fetchall()
            self.assertEqual(rows, [("nvidia", llm_parser.NVIDIA_LLM_MODEL, 2)])
        self.assertEqual(bodies[1]["model"], llm_parser.NVIDIA_LLM_MODEL)
        self.assertNotIn("provider", bodies[1])
        schema = bodies[1]["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertIn("products", schema["schema"]["required"])
