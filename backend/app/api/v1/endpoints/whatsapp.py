"""Authenticated WhatsApp connection endpoints; no client-supplied session names."""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp import WahaClient
from backend.app.models.user import DestinationChannel, User
from backend.app.models.whatsapp_policy import (
    WhatsAppDeliveryPolicy,
    WhatsAppDeliveryState,
)
from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, promotion_ttl
from backend.app.core.delivery_errors import REASONS
from backend.worker.poster import BotPosterError

router = APIRouter(prefix="/users/me/whatsapp", tags=["WhatsApp"])


@router.get("/policy")
async def get_policy(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the owner's editorial limits and active circuit pauses, never upstream data."""
    response.headers["Cache-Control"] = "no-store"
    result = await db.execute(
        select(WhatsAppDeliveryPolicy).where(WhatsAppDeliveryPolicy.user_id == user.id)
    )
    stored = result.scalar_one_or_none()
    settings = (
        WhatsAppPolicy.model_validate_json(stored.config_data)
        if stored
        else WhatsAppPolicy()
    )
    result = await db.execute(
        select(WhatsAppDeliveryState).where(
            WhatsAppDeliveryState.user_id == user.id,
            WhatsAppDeliveryState.paused_until > datetime.now(timezone.utc),
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
):
    """Validate and save account-wide limits; pending work uses the new limits on dispatch."""
    # Lock the owning row to serialize first-time policy creation as well as edits.
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
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
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Clear this user's circuit pauses without enabling destinations or replaying work."""
    await db.execute(
        update(WhatsAppDeliveryState)
        .where(WhatsAppDeliveryState.user_id == user.id)
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
async def status(response: Response, user: User = Depends(get_current_user)):
    """Read only the current user's WhatsApp connection state."""
    response.headers["Cache-Control"] = "no-store"
    return await call(WahaClient(user.id).status())


@router.post("")
async def start(user: User = Depends(get_current_user)):
    """Start pairing for the authenticated user without altering other sessions."""
    return await call(WahaClient(user.id).start())


@router.get("/qr")
async def qr(response: Response, user: User = Depends(get_current_user)):
    """Deliver pairing QR only to its owner, with caching disabled."""
    response.headers["Cache-Control"] = "no-store"
    return {"qr": await call(WahaClient(user.id).qr())}


@router.get("/groups")
async def groups(user: User = Depends(get_current_user)):
    """List selectable groups from this user's connected WhatsApp account."""
    return await call(WahaClient(user.id).groups())


@router.delete("", status_code=204)
async def disconnect(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Unlink account and disable its destinations so queued sends are cancelled."""
    await db.execute(
        update(DestinationChannel)
        .where(
            DestinationChannel.user_id == user.id,
            DestinationChannel.platform == "whatsapp",
        )
        .values(enabled=False)
    )
    await db.commit()
    await call(WahaClient(user.id).disconnect())


@router.get("/channels")
async def channels(user: User = Depends(get_current_user)):
    """List only channels the current user is allowed to publish to."""
    return await call(WahaClient(user.id).channels())
