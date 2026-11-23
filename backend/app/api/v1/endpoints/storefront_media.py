"""Serve only published and unexpired storefront thumbnails."""

import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import get_db
from backend.app.models.worker import StorefrontThumbnail

router = APIRouter(tags=["Public storefront"])


@router.get("/public/storefront/images/{delivery_id}", response_class=Response)
async def get_thumbnail(delivery_id: str, db: AsyncSession = Depends(get_db)):
    """Return the re-encoded WebP for a cached delivery, or 404 if absent."""
    if not re.fullmatch(r"[0-9a-f]{64}", delivery_id):
        raise HTTPException(404)
    body = await db.scalar(
        select(StorefrontThumbnail.body).where(
            StorefrontThumbnail.delivery_id == delivery_id,
            StorefrontThumbnail.expires_at > func.now(),
        )
    )
    if body is None:
        raise HTTPException(404)
    return Response(
        body, media_type="image/webp", headers={"X-Content-Type-Options": "nosniff"}
    )
