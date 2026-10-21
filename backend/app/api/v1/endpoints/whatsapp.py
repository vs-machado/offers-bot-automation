"""Authenticated WhatsApp connection endpoints; no client-supplied session names."""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp_connections import (
    client_for,
    ensure_primary,
    owned_connection,
)
from backend.app.models.whatsapp_connection import (
    WhatsAppConnection,
    WhatsAppConnectionState,
)
from backend.app.models.user import DestinationChannel, User
from backend.app.models.whatsapp_policy import (
    WhatsAppDeliveryPolicy,
    WhatsAppDeliveryState,
)
from backend.app.schemas.whatsapp_policy import (
    WhatsAppPolicy,
    promotion_ttl,
    new_connection_policy,
)
from backend.app.core.delivery_errors import REASONS
from backend.worker.poster import BotPosterError

router = APIRouter(prefix="/users/me/whatsapp", tags=["WhatsApp"])


class ConnectionName(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)


async def get_connection(
    connection_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve an owner-scoped selection before any upstream access."""
    return await owned_connection(db, user.id, connection_id)


def connection_summary(row):
    return {"id": row.id, "name": row.name, "is_default": row.is_default}


@router.get("/connections")
async def list_connections(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List owned connection labels, adopting the original session without pairing again."""
    response.headers["Cache-Control"] = "no-store"
    await ensure_primary(db, user.id)
    await db.commit()
    rows = (
        (
            await db.execute(
                select(WhatsAppConnection)
                .where(WhatsAppConnection.user_id == user.id)
                .order_by(WhatsAppConnection.id)
            )
        )
        .scalars()
        .all()
    )
    return [connection_summary(row) for row in rows]


@router.post("/connections", status_code=201)
async def create_connection(
    body: ConnectionName,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allocate a new isolated session; pairing remains an explicit operation."""
    await ensure_primary(db, user.id)
    row = WhatsAppConnection(
        user_id=user.id,
        name=body.name,
        is_default=False,
        config_data=new_connection_policy().model_dump_json(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return connection_summary(row)


@router.put("/connections/{connection_id}")
async def rename_connection(
    connection_id: int,
    body: ConnectionName,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename an owned connection without changing its session or routing."""
    row = await owned_connection(db, user.id, connection_id)
    row.name = body.name
    await db.commit()
    return connection_summary(row)


@router.get("/policy")
async def get_policy(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    connection=Depends(get_connection),
):
    """Return the owner's editorial limits and active circuit pauses, never upstream data."""
    response.headers["Cache-Control"] = "no-store"
    result = await db.execute(
        select(WhatsAppDeliveryPolicy).where(WhatsAppDeliveryPolicy.user_id == user.id)
    )
    stored = result.scalar_one_or_none()
    settings = (
        WhatsAppPolicy.model_validate_json(connection.config_data)
        if connection and not connection.is_default and connection.config_data
        else WhatsAppPolicy.model_validate_json(stored.config_data)
        if stored and (connection is None or connection.is_default)
        else WhatsAppPolicy()
    )
    state_model = (
        WhatsAppConnectionState
        if connection and not connection.is_default
        else WhatsAppDeliveryState
    )
    owner_filter = (
        state_model.connection_id == connection.id
        if state_model is WhatsAppConnectionState
        else state_model.user_id == user.id
    )
    result = await db.execute(
        select(state_model).where(
            owner_filter,
            state_model.paused_until > datetime.now(timezone.utc),
        )
    )
    return {
        "settings": settings.model_dump(),
        "effective_ttl_seconds": min(settings.ttl_seconds, promotion_ttl()),
        "burst_keep": 5,
        "pauses": [
            {
                "chat_id": item.chat_id or None,
                "paused_until": item.paused_until,
                "reason_message": REASONS.get(
                    item.pause_reason, "Envios temporariamente pausados."
                ),
            }
            for item in result.scalars().all()
        ],
    }


@router.put("/policy", response_model=WhatsAppPolicy)
async def save_policy(
    body: WhatsAppPolicy,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    connection=Depends(get_connection),
):
    """Validate and save account-wide limits; pending work uses the new limits on dispatch."""
    # Lock the owning row to serialize first-time policy creation as well as edits.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    if connection and not connection.is_default:
        connection.config_data = body.model_dump_json()
        await db.commit()
        return body
    result = await db.execute(
        select(WhatsAppDeliveryPolicy).where(WhatsAppDeliveryPolicy.user_id == user.id)
    )
    stored = result.scalar_one_or_none()
    if stored:
        stored.config_data = body.model_dump_json()
    else:
        db.add(
            WhatsAppDeliveryPolicy(user_id=user.id, config_data=body.model_dump_json())
        )
    await db.commit()
    return body


@router.post("/policy/resume", status_code=204)
async def resume_deliveries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    connection=Depends(get_connection),
):
    """Clear this user's circuit pauses without enabling destinations or replaying work."""
    state_model = (
        WhatsAppConnectionState
        if connection and not connection.is_default
        else WhatsAppDeliveryState
    )
    owner_filter = (
        state_model.connection_id == connection.id
        if state_model is WhatsAppConnectionState
        else state_model.user_id == user.id
    )
    await db.execute(
        update(state_model)
        .where(owner_filter)
        .values(failures=0, paused_until=None, pause_reason=None)
    )
    await db.commit()


async def call(operation):
    """Translate upstream failure without leaking credentials or response bodies."""
    try:
        return await operation
    except (BotPosterError, httpx.HTTPError) as exc:
        raise HTTPException(
            400,
            str(exc)
            if isinstance(exc, BotPosterError)
            else "Não foi possível conectar ao WhatsApp.",
        ) from exc


@router.get("")
async def status(
    response: Response,
    user: User = Depends(get_current_user),
    connection=Depends(get_connection),
):
    """Read only the current user's WhatsApp connection state."""
    response.headers["Cache-Control"] = "no-store"
    return await call(client_for(user.id, connection).status())


@router.post("")
async def start(
    user: User = Depends(get_current_user), connection=Depends(get_connection)
):
    """Start pairing for the authenticated user without altering other sessions."""
    return await call(client_for(user.id, connection).start())


@router.get("/qr")
async def qr(
    response: Response,
    user: User = Depends(get_current_user),
    connection=Depends(get_connection),
):
    """Deliver pairing QR only to its owner, with caching disabled."""
    response.headers["Cache-Control"] = "no-store"
    return {"qr": await call(client_for(user.id, connection).qr())}


@router.get("/groups")
async def groups(
    user: User = Depends(get_current_user), connection=Depends(get_connection)
):
    """List selectable groups from this user's connected WhatsApp account."""
    return await call(client_for(user.id, connection).groups())


@router.delete("", status_code=204)
async def disconnect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    connection=Depends(get_connection),
):
    """Unlink account and disable its destinations so queued sends are cancelled."""
    await db.execute(
        update(DestinationChannel)
        .where(
            DestinationChannel.user_id == user.id,
            DestinationChannel.platform == "whatsapp",
            (DestinationChannel.connection_id == connection.id)
            | DestinationChannel.connection_id.is_(None)
            if connection and connection.is_default
            else DestinationChannel.connection_id == connection.id
            if connection
            else DestinationChannel.connection_id.is_(None),
        )
        .values(enabled=False)
    )
    await db.commit()
    await call(client_for(user.id, connection).disconnect())


@router.get("/channels")
async def channels(
    user: User = Depends(get_current_user), connection=Depends(get_connection)
):
    """List only channels the current user is allowed to publish to."""
    return await call(client_for(user.id, connection).channels())
