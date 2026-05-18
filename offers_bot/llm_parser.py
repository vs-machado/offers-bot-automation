import json
import logging
import os
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_URL = f"{OLLAMA_HOST}/api/generate"
MODEL_NAME = "llama3.2:3b"

SYSTEM_PROMPT = """You are an expert assistant that parses shopping deals and coupons from Telegram messages.
Analyze the message and classify it into one of two categories:
1. "product": A product deal offering a specific product for a price.
2. "coupon": A generic coupon bulletin, a coupon list, or a coupon discount notice (not for one single specific product).

Extract the details precisely in Portuguese. Return ONLY a valid JSON object matching the schema below. Do not include any other text, markdown formatting, or comments outside the JSON.

JSON Schema:
{
  "classification": "product" | "coupon",
  "product": {
    "title": "Cleaned product title without pricing, coupon codes, URLs or noise. (e.g. 'Smartphone Motorola Moto g35 5G - 128GB')",
    "price": "Standardized price (e.g., 'R$ 844,90 no PIX' or 'R$ 49,90')",
    "card_price": "Card price if any (e.g., 'R$ 6.299,00 no cartão')",
    "installment_info": "Installment info in uppercase if any (e.g., '10X SEM JUROS')",
    "shipping_info": "Shipping info in uppercase if any (e.g., 'FRETE GRÁTIS')",
    "coupon": "Coupon code(s) (e.g., 'MELIMAISPROMO' or '10MELIMAIS ou MELIMAISPROMO')",
    "resgate_anuncio_note": "Redemption note if present, e.g. 'Resgate o cupom no anúncio do produto'",
    "meli_plus_only": true/false
  },
  "coupon": {
    "platform": "Amazon" | "Mercado Livre" | "Shopee" | "AliExpress" | "Generic",
    "novo_ml_format": true/false, // true if message mentions 'Novo Cupom Mercado Livre' or similar
    "generic_format": true/false, // true if it is a generic discount notice without platform header
    "coupons": [
      {
        "detail": "Detailed description of the coupon discount directly from the text (e.g. the percentage/value off and minimum purchase condition)",
        "code": "Coupon code"
      }
    ]
  }
}
"""


def save_token_usage(prompt_tokens: int, completion_tokens: int) -> None:
    db_path = os.getenv("DATABASE_PATH", "data/offers.sqlite3")
    try:
        import sqlite3
        from pathlib import Path

        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL
                )
                """
            )
            total = prompt_tokens + completion_tokens
            conn.execute(
                "INSERT INTO token_usage (prompt_tokens, completion_tokens, total_tokens) VALUES (?, ?, ?)",
                (prompt_tokens, completion_tokens, total),
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to save token usage to db: %s", e)


def parse_with_llm(text: str) -> Optional[Dict[str, Any]]:
    import os

    if os.getenv("DISABLE_LLM") == "true":
        return None
    try:
        payload = {
            "model": MODEL_NAME,
            "prompt": f"Analyze this Telegram message:\n\n{text}",
            "system": SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        resp = httpx.post(OLLAMA_URL, json=payload, timeout=120.0)
        resp.raise_for_status()
        result = resp.json()
        response_text = result.get("response", "")

        # Save token usage
        prompt_tokens = result.get("prompt_eval_count", 0)
        eval_tokens = result.get("eval_count", 0)
        save_token_usage(prompt_tokens, eval_tokens)

        # Extract JSON from response if it has thinking tags or extra text
        if "{" in response_text:
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx : end_idx + 1]

        return json.loads(response_text)
    except Exception as e:
        logger.warning(
            "LLM parsing failed or timed out: %s. Raw response: %s",
            e,
            locals().get("response_text", "None"),
        )
        return None
