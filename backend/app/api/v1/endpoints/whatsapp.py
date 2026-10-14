"""Authenticated WhatsApp connection endpoints; no client-supplied session names."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp import WahaClient
from backend.app.models.user import DestinationChannel, User
from backend.worker.poster import BotPosterError

router = APIRouter(prefix="/users/me/whatsapp", tags=["WhatsApp"])


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
