import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from offers_bot.llm_parser import (
    DealParseResult,
    _dump_result,
    _message_prompt,
    parse_with_llm,
    parse_with_llm_async,
)
from offers_bot.main import format_outgoing_offer
from offers_bot.parser import extract_offers
from offers_bot.source_cleanup import clean_source_advertising


class SourceAdvertisingLinesTest(unittest.TestCase):
    def result(self, **fields):
        return SimpleNamespace(
            output=DealParseResult(classification="product", **fields),
            usage=lambda: SimpleNamespace(input_tokens=0, output_tokens=0),
        )

    @patch("offers_bot.llm_parser.save_token_usage")
    def test_line_selection_removes_varied_promotions_without_copying_text(self, _save):
        for ad in (
            "**Receba avisos personalizados:**\n@servico_novo",
            "Quando baixar, avisamos!\n[Participar](https://example.org/convite)",
            "🤖 Acumule recompensas com nosso assistente:\nhttps://t.me/moedas?start=ref",
        ):
            with self.subTest(ad=ad):
                text = (
                    "SSD R$ 50 com moedas no AliExpress\n"
                    "https://s.click.aliexpress.com/e/itemA\n"
                    "https://s.click.aliexpress.com/e/itemB\n"
                    f"{ad}\n"
                    "CUPOM: SSD20"
                )
                parsed = _dump_result(
                    self.result(source_advertising_lines=[4, 5]), text
                )
                self.assertEqual(parsed["source_advertising_spans"], [ad])
                self.assertNotIn("source_advertising_lines", parsed)
                with patch("offers_bot.parser.parse_with_llm", return_value=parsed):
                    offer = extract_offers(text)[0]
                outgoing = asyncio.run(
                    format_outgoing_offer(
                        offer, "https://s.click.aliexpress.com/e/ours", is_ali=True
                    )
                )
                for line in ad.split("\n"):
                    self.assertNotIn(line, outgoing)
                self.assertIn("R$ 50 com moedas", outgoing)
                self.assertIn("SSD20", outgoing)
                self.assertIn("https://s.click.aliexpress.com/e/itemB", outgoing)

    @patch("offers_bot.llm_parser.save_token_usage")
    def test_mixed_line_spans_and_separate_ad_lines_preserve_deal(self, _save):
        text = "SSD R$ 50 | Siga: @canal\nResgate aqui:\nhttps://loja.example/cupom\nAvisos: @outro"
        parsed = _dump_result(
            self.result(
                source_advertising_lines=[0, 4, 4, 99],
                source_advertising_spans=[" | Siga: @canal"],
            ),
            text,
        )
        self.assertEqual(
            clean_source_advertising(text, parsed["source_advertising_spans"]),
            "SSD R$ 50\nResgate aqui:\nhttps://loja.example/cupom",
        )

    def test_numbered_prompt_preserves_blank_lines_and_markdown(self):
        self.assertEqual(
            _message_prompt("Produto\n\n**Avisos:**\n@novo"),
            "Analyze this Telegram message (numbered lines):\n\n"
            "1: Produto\n2: \n3: **Avisos:**\n4: @novo",
        )

    @patch("offers_bot.llm_parser.save_token_usage")
    @patch(
        "offers_bot.llm_parser._llm_configs", return_value=[("primary", "model", "key")]
    )
    @patch("offers_bot.llm_parser._build_agent")
    @patch.dict("os.environ", {"DISABLE_LLM": "false"})
    def test_sync_and_async_resolve_same_line_numbers(self, build, _configs, _save):
        text = "Produto\n\nReceba avisos:\n@novo"
        agent = Mock()
        agent.run_sync.return_value = self.result(source_advertising_lines=[3, 4])
        agent.run = AsyncMock(return_value=self.result(source_advertising_lines=[3, 4]))
        build.return_value = agent
        sync_result = parse_with_llm(text)
        async_result = asyncio.run(parse_with_llm_async(text))
        self.assertEqual(sync_result, async_result)
        self.assertEqual(
            sync_result["source_advertising_spans"], ["Receba avisos:\n@novo"]
        )
        agent.run_sync.assert_called_once_with(_message_prompt(text))
        agent.run.assert_awaited_once_with(_message_prompt(text))
