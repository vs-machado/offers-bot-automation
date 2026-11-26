import asyncio
import os
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr, StringConstraints, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import require_admin
from backend.app.core.credentials import decrypt_config, encrypt_config
from backend.app.core.db.session import get_db
from backend.app.core.source_groups import enabled_source_groups
from backend.app.models.user import DestinationChannel, SourceGroup
from backend.app.models.worker import XBufferSettings, XOfferAttempt
from backend.worker.buffer_publisher import BufferPublisher

router = APIRouter(dependencies=[Depends(require_admin)])


class BufferWrite(BaseModel):
    enabled: bool
    destination_id: int | None = Field(default=None, gt=0)
    landing_url: str = Field(max_length=1000)
    channel_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{0,128}$")]
    daily_limit: int = Field(ge=1, le=10, strict=True)
    priority_source_id: int | None = Field(default=None, gt=0)
    api_key: SecretStr | None = None

    @field_validator("landing_url")
    @classmethod
    def validate_landing_url(cls, value: str):
        if not value:
            return value
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or "." not in url.hostname
            or url.username is not None
            or any(not 33 <= ord(char) <= 126 for char in value)
        ):
            raise ValueError("Informe uma URL pública HTTPS.")
        return value


async def _state(db):
    settings = await db.get(XBufferSettings, 1, populate_existing=True)
    sources = await enabled_source_groups(db)
    destinations = (
        (
            await db.execute(
                select(
                    DestinationChannel.id,
                    DestinationChannel.title,
                    DestinationChannel.chat_id,
                    DestinationChannel.platform,
                    DestinationChannel.user_id,
                )
                .where(DestinationChannel.enabled)
                .order_by(DestinationChannel.title, DestinationChannel.id)
            )
        )
        .mappings()
        .all()
    )
    attempts = (
        (
            await db.execute(
                select(XOfferAttempt.attempted_at, XOfferAttempt.status)
                .order_by(XOfferAttempt.attempted_at.desc())
                .limit(10)
            )
        )
        .mappings()
        .all()
    )
    return {
        "settings": {
            "enabled": settings.enabled if settings else False,
            "destination_id": settings.destination_id if settings else None,
            "landing_url": settings.landing_url if settings else "",
            "channel_id": settings.channel_id if settings else "",
            "daily_limit": settings.daily_limit if settings else 1,
            "priority_source_id": settings.priority_source_id if settings else None,
            "has_api_key": bool(settings and settings.encrypted_key),
        },
        "dashboard_managed": os.getenv("X_OFFERS_MODE", "dashboard") == "dashboard",
        "destinations": [dict(item) for item in destinations],
        "source_groups": [
            {"id": source.id, "label": source.label} for source in sources
        ],
        "attempts": [dict(item) for item in attempts],
    }


@router.get("/x-buffer")
async def get_buffer_settings(db: AsyncSession = Depends(get_db)):
    """Show settings, eligible destinations, and recent outcomes without exposing the key."""
    return await _state(db)


@router.put("/x-buffer")
async def put_buffer_settings(body: BufferWrite, db: AsyncSession = Depends(get_db)):
    """Save singleton settings, encrypt a replacement key, and preserve omitted keys."""
    token = body.api_key.get_secret_value().strip() if body.api_key else ""
    if token and (
        len(token) > 4096 or any(not 33 <= ord(char) <= 126 for char in token)
    ):
        raise HTTPException(422, "Chave do Buffer inválida.")
    if body.destination_id is not None:
        dest = await db.get(DestinationChannel, body.destination_id)
        if not dest or not dest.enabled:
            raise HTTPException(422, "Selecione um destino ativo.")
    if body.priority_source_id is not None:
        source = await db.get(SourceGroup, body.priority_source_id)
        if not source or not source.enabled:
            raise HTTPException(422, "Selecione um grupo de origem ativo.")
    current = await db.get(XBufferSettings, 1)
    if body.enabled and not (
        body.destination_id
        and body.channel_id
        and (token or (current and current.encrypted_key))
    ):
        raise HTTPException(
            422, "Preencha o destino, o canal e a chave antes de ativar."
        )
    values = body.model_dump(exclude={"api_key"})
    encrypted_key = encrypt_config(token, 1, "x_buffer") if token else ""
    updates = {**values, **({"encrypted_key": encrypted_key} if token else {})}
    statement = insert(XBufferSettings).values(
        id=1, encrypted_key=encrypted_key, **values
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[XBufferSettings.id], set_=updates
        )
    )
    await db.commit()
    return await _state(db)


@router.post("/x-buffer/check")
async def check_buffer_settings(db: AsyncSession = Depends(get_db)):
    """Validate the saved Buffer key and destination account with a read-only request."""
    settings = await db.get(XBufferSettings, 1)
    if not settings or not settings.encrypted_key or not settings.channel_id:
        raise HTTPException(422, "Salve a chave e o canal do Buffer antes de testar.")
    publisher = BufferPublisher(
        decrypt_config(settings.encrypted_key, 1, "x_buffer"), settings.channel_id
    )
    account = await asyncio.to_thread(publisher.check_connection)
    if not account:
        raise HTTPException(
            400,
            "Não foi possível validar o perfil do X. Confira a chave, o canal e a conexão no Buffer.",
        )
    return {"account": account}


@router.get("/x-buffer/posts")
async def get_recent_x_posts(db: AsyncSession = Depends(get_db)):
    """Read recent published posts without blocking settings or issuing a write to Buffer."""
    settings = await db.get(XBufferSettings, 1)
    if not settings or not settings.encrypted_key or not settings.channel_id:
        return {"configured": False, "posts": []}
    publisher = BufferPublisher(
        decrypt_config(settings.encrypted_key, 1, "x_buffer"), settings.channel_id
    )
    try:
        posts = await asyncio.to_thread(publisher.recent_posts)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            502, "Não foi possível carregar as publicações do Buffer."
        ) from exc
    return {"configured": True, "posts": posts}
