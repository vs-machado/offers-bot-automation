"""Authenticated Magalu generation using only the caller's persisted account."""

import asyncio
import time
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.credentials import decrypt_config
from backend.app.core.db.session import get_db
from backend.app.models.user import User, UserConfig
from offers_bot.magalu import MagaluClient, MagaluError

router = APIRouter()
_slots = asyncio.Semaphore(8)
_active: set[int] = set()
_recent: dict[int, float] = {}


class MagaluLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2000)
    channel: Literal["lucreator", "whatsapp"] = "lucreator"


@router.post("/affiliate/magalu")
async def generate_magalu_link(
    request: MagaluLinkRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate one link with owned saved settings; bound concurrent use and rate.

    Never accept account identifiers from callers or expose external error bodies.
    Limits apply per backend process, with a five-second interval per user.
    """
    response.headers["Cache-Control"] = "no-store"
    now = time.monotonic()
    for user_id, timestamp in list(_recent.items()):
        if now - timestamp >= 5:
            del _recent[user_id]
    if current_user.id in _active or current_user.id in _recent or _slots.locked():
        raise HTTPException(429, "Aguarde alguns segundos antes de gerar outro link.")
    _active.add(current_user.id)
    _recent[current_user.id] = now
    try:
        async with _slots:
            result = await db.execute(
                select(UserConfig)
                .where(
                    UserConfig.user_id == current_user.id,
                    UserConfig.config_type == "magalu",
                )
                .order_by(UserConfig.id)
            )
            config = result.scalars().first()
            if config is None:
                raise HTTPException(
                    400, "Configure sua conta Magalu na tela Afiliados."
                )
            values = decrypt_config(config.config_data, current_user.id, "magalu")
            client = MagaluClient(
                values.get("magalu_partner_id", ""),
                values.get("magalu_promoter_id", ""),
                values.get("magalu_store_name", ""),
                values.get("magalu_utm_campaign", "divulgacao_influencer"),
            )
            data = await asyncio.to_thread(
                client.generate, request.url, request.channel
            )
            return {
                key: data.get(key)
                for key in (
                    "affiliate_url",
                    "shortlink_url",
                    "web_affiliate_url",
                    "canonical_product_url",
                    "sku",
                    "title",
                    "image_url",
                    "current_price",
                    "original_price",
                    "discount_pct",
                    "installment",
                    "source",
                )
            }
    except ValueError:
        raise HTTPException(
            400, "URL de produto ou configuração Magalu inválida."
        ) from None
    except (MagaluError, httpx.HTTPError) as exc:
        cause = exc.__cause__ or exc
        code = 504 if isinstance(cause, httpx.TimeoutException) else 502
        if (
            isinstance(cause, httpx.HTTPStatusError)
            and cause.response.status_code == 429
        ):
            code = 429
        raise HTTPException(
            code, "Não foi possível gerar o link Magalu. Tente novamente mais tarde."
        ) from None
    finally:
        _active.discard(current_user.id)
