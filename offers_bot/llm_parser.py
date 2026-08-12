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
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.providers.google import GoogleProvider

logger = logging.getLogger(__name__)

PRIMARY_LLM_MODEL = "deepseek/deepseek-v4-flash"
FALLBACK_LLM_MODEL = "gemini/gemini-2.5-flash-lite"


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
        None,
        description=(
            "Card price only if explicitly different from the main price "
            "(e.g., 'R$ 6.299,00 no cartão' when Pix price differs). "
            "Do not duplicate the main price for installments."
        ),
    )
    installment_info: Optional[str] = Field(
        None, description="Installment info in uppercase if any (e.g., '10X SEM JUROS')"
    )
    shipping_info: Optional[str] = Field(
        None, description="Shipping info in uppercase if any (e.g., 'FRETE GRÁTIS')"
    )
    coupon: Optional[str] = Field(
        None,
        description=(
            "Only actual coupon code(s), e.g., 'MAES10' or "
            "'10MELIMAIS ou MELIMAISPROMO'. Do not include redemption "
            "instructions like 'Resgate cupom no anúncio'; put those in "
            "resgate_anuncio_note."
        ),
    )
    resgate_anuncio_note: Optional[str] = Field(
        None,
        description="Redemption note if present, e.g. 'Resgate o cupom no anúncio do produto'",
    )
    meli_plus_only: bool
    urls: List[str] = Field(
        default_factory=list,
        description="List of URLs from the message that belong to this specific product variant",
    )


class DealParseResult(BaseModel):
    classification: Literal["product", "coupon"]
    products: List[ProductSection] = Field(default_factory=list)
    coupon: Optional[CouponSection] = None
    category: Optional[Literal["tech", "home", "clothes", "other"]] = None


SYSTEM_PROMPT = """You are an expert assistant that parses shopping deals and coupons from Telegram messages.
Analyze the message and classify it into one of two categories:
1. "product": A product deal offering a specific product for a price (even if a coupon code is also provided for that product).
2. "coupon": A generic coupon bulletin, a coupon list, or a coupon discount notice (not for one single specific product).

CRITICAL CLASSIFICATION RULES:
- If the message names a specific, single product (e.g. a monitor, laptop, smartphone, etc.) with a specific price, you MUST classify it as "product", even if the message also features coupon codes.
- Classify as "coupon" ONLY when the message is a list/bulletin of general coupons or a discount event without one main specific product.
- If the message contains multiple product links (e.g. multiple meli.la or shopee links) but NO explicit coupon codes, classify it as "product".
- A "coupon" classification MUST have at least one actual coupon code in the coupons list.

MULTI-PRODUCT RULE: If the message describes MULTIPLE different products with DIFFERENT prices, list each product separately in the "products" array. For each product, populate its "urls" field with the URL(s) that belong to that specific product. If all URLs belong to the same product with the same price, put all URLs in a single product entry.

CRITICAL TITLE EXTRACTION RULE: You must extract a clean product title for each product. Do not leave it null or empty if there is a product name. Clean the title by removing all emojis, pricing details, discount percentages, coupon codes, and URLs.

FIELD RULES:
- product.coupon must contain ONLY real coupon code(s), e.g. "MAES10", "OFF20", "10MELIMAIS ou MELIMAISPROMO".
- Do NOT put redemption instructions in product.coupon.
- Phrases like "Resgate cupom no anúncio", "Resgate o cupom no anúncio do produto", "Cupom no anúncio", "Ative no anúncio" are NOT coupon codes.
- Put those phrases only in product.resgate_anuncio_note.
- If message says "Cupom: Resgate cupom no anúncio" and gives no actual code, set product.coupon = null and product.resgate_anuncio_note = "Resgate cupom no anúncio".
- product.card_price must be set only when text explicitly indicates a different card/parcelado price, e.g. "R$ 110 no cartão" while product.price is "R$ 100 no PIX".
- If same price is shown with installments, e.g. "R$ 680 em 10x sem juros", set product.price = "R$ 680", product.installment_info = "10X SEM JUROS", and product.card_price = null.

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


def _build_agent(model_name: str, api_key: str) -> Agent:
    if model_name == PRIMARY_LLM_MODEL:
        model = OpenAIChatModel(
            "deepseek-v4-flash",
            provider=DeepSeekProvider(api_key=api_key),
        )
    elif model_name == FALLBACK_LLM_MODEL:
        model = GoogleModel(
            "gemini-2.5-flash-lite",
            provider=GoogleProvider(api_key=api_key),
        )
    else:
        raise ValueError(f"Unsupported LLM model: {model_name}")

    return Agent(
        model=model,
        output_type=DealParseResult,
        system_prompt=SYSTEM_PROMPT,
    )


def _llm_configs() -> list[tuple[str, str, str]]:
    """Return configured providers in priority order, without exposing keys."""
    return [
        ("primary", PRIMARY_LLM_MODEL, os.getenv("DEEPSEEK_API_KEY", "")),
        ("fallback", FALLBACK_LLM_MODEL, os.getenv("GEMINI_API_KEY", "")),
    ]


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
    for label, model_name, api_key in _llm_configs():
        if not api_key:
            logger.warning(
                "%s API key for %s is not set", label.capitalize(), model_name
            )
            continue
        try:
            agent = _build_agent(model_name, api_key)
            result = agent.run_sync(f"Analyze this Telegram message:\n\n{text}")
            return _dump_result(result)
        except Exception as exc:
            logger.warning(
                "%s LLM parser failed with %s: %s", label.capitalize(), model_name, exc
            )

    return None


async def parse_with_llm_async(text: str) -> Optional[Dict[str, Any]]:
    if os.getenv("DISABLE_LLM") == "true":
        return None
    for label, model_name, api_key in _llm_configs():
        if not api_key:
            logger.warning(
                "%s API key for %s is not set", label.capitalize(), model_name
            )
            continue
        try:
            agent = _build_agent(model_name, api_key)
            result = await agent.run(f"Analyze this Telegram message:\n\n{text}")
            return _dump_result(result)
        except Exception as exc:
            logger.warning(
                "%s LLM parser failed with %s: %s", label.capitalize(), model_name, exc
            )

    return None
