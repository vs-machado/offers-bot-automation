import logging
import os
from pathlib import Path
import sqlite3
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from typing import List, Literal

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.litellm import LiteLLMProvider

logger = logging.getLogger(__name__)


# Pydantic models for structured output validation
class CouponItem(BaseModel):
    detail: str = Field(
        description="Detailed description of the coupon discount directly from the text (e.g. the percentage/value off and minimum purchase condition)"
    )
    code: str = Field(description="Coupon code")


class CouponSection(BaseModel):
    platform: Literal["Amazon", "Mercado Livre", "Shopee", "AliExpress", "Generic"]
    novo_ml_format: bool = Field(
        description="true if message mentions 'Novo Cupom Mercado Livre' or similar"
    )
    generic_format: bool = Field(
        description="true if it is a generic discount notice without platform header"
    )
    coupons: List[CouponItem]


class ProductSection(BaseModel):
    title: str = Field(
        description="Cleaned product title without pricing, coupon codes, URLs or noise. (e.g. 'Smartphone Motorola Moto g35 5G - 128GB')"
    )
    price: Optional[str] = Field(
        None, description="Standardized price (e.g., 'R$ 844,90 no PIX' or 'R$ 49,90')"
    )
    card_price: Optional[str] = Field(
        None, description="Card price if any (e.g., 'R$ 6.299,00 no cartão')"
    )
    installment_info: Optional[str] = Field(
        None, description="Installment info in uppercase if any (e.g., '10X SEM JUROS')"
    )
    shipping_info: Optional[str] = Field(
        description="Shipping info in uppercase if any (e.g., 'FRETE GRÁTIS')"
    )
    coupon: Optional[str] = Field(
        None,
        description="Coupon code(s) (e.g., 'MELIMAISPROMO' or '10MELIMAIS ou MELIMAISPROMO')",
    )
    resgate_anuncio_note: Optional[str] = Field(
        None,
        description="Redemption note if present, e.g. 'Resgate o cupom no anúncio do produto'",
    )
    meli_plus_only: bool


class DealParseResult(BaseModel):
    classification: Literal["product", "coupon"]
    product: Optional[ProductSection] = None
    coupon: Optional[CouponSection] = None
    category: Optional[Literal["tech", "home", "clothes", "other"]] = None


SYSTEM_PROMPT = """You are an expert assistant that parses shopping deals and coupons from Telegram messages.
Analyze the message and classify it into one of two categories:
1. "product": A product deal offering a specific product for a price (even if a coupon code is also provided for that product).
2. "coupon": A generic coupon bulletin, a coupon list, or a coupon discount notice (not for one single specific product).

CRITICAL CLASSIFICATION RULE: If the message names a specific, single product (e.g. a monitor, laptop, smartphone, etc.) with a specific price, you MUST classify it as "product", even if the message also features coupon codes. Classify as "coupon" ONLY when the message is a list/bulletin of general coupons or a discount event without one main specific product.

CRITICAL TITLE EXTRACTION RULE: For "product" classification, you must extract a clean product title. The title must represent the main product being sold. E.g. 'Smartphone Motorola Moto g35 5G - 128GB'. Do not leave it null or empty if there is a product name. Clean the title by removing all emojis, pricing details, discount percentages, coupon codes, and URLs.

CATEGORY CLASSIFICATION RULE: After classifying as "product" or "coupon", determine the product category:
- "tech": For electronic devices like smartphones, laptops, tablets, smart watches, headphones, etc.
- "home": For home items like furniture, appliances, decor, kitchenware, etc.
- "clothes": For clothing items, accessories, shoes, etc.
- "other": For products that don't fit any of the above categories.

If the classification is "coupon" (not "product"), the category should be set to None, as coupons are not product-specific.

Extract the details precisely in Portuguese. Return a valid JSON matching the schema of DealParseResult.
"""


def save_token_usage(prompt_tokens: int, completion_tokens: int) -> None:
    db_path = os.getenv("DATABASE_PATH", "data/offers.sqlite3")
    try:
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


def _build_agent(gemini_key: str) -> Agent:
    lite_api_base = os.getenv("LITELLM_API_BASE")
    if lite_api_base:
        model = OpenAIChatModel(
            "gemini/gemini-2.5-flash-lite",
            provider=LiteLLMProvider(api_base=lite_api_base, api_key=gemini_key),
        )
    else:
        model = GoogleModel(
            model_name="gemini-2.5-flash-lite",
            provider=GoogleProvider(api_key=gemini_key),
        )

    return Agent(
        model=model,
        output_type=DealParseResult,
        system_prompt=SYSTEM_PROMPT,
    )


def _dump_result(result) -> Dict[str, Any]:
    # Save token usage
    prompt_tokens = result.usage().input_tokens or 0
    eval_tokens = result.usage().output_tokens or 0
    save_token_usage(prompt_tokens, eval_tokens)

    # Return dictionary matching previous Ollama outputs
    return result.output.model_dump()


def parse_with_llm(text: str) -> Optional[Dict[str, Any]]:
    if os.getenv("DISABLE_LLM") == "true":
        return None
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            logger.warning("GEMINI_API_KEY environment variable is not set!")
            return None

        agent = _build_agent(gemini_key)
        result = agent.run_sync(f"Analyze this Telegram message:\n\n{text}")
        return _dump_result(result)
    except Exception as e:
        logger.warning("LLM parsing failed or timed out: %s", e)
        return None


async def parse_with_llm_async(text: str) -> Optional[Dict[str, Any]]:
    if os.getenv("DISABLE_LLM") == "true":
        return None
    try:
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            logger.warning("GEMINI_API_KEY environment variable is not set!")
            return None

        agent = _build_agent(gemini_key)
        result = await agent.run(f"Analyze this Telegram message:\n\n{text}")
        return _dump_result(result)
    except Exception as e:
        logger.warning("LLM parsing failed or timed out: %s", e)
        return None
