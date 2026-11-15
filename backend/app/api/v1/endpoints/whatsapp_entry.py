"""Public PostgreSQL-backed admission; a click never calls WAHA or decrypts user settings."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db.session import get_db
from backend.app.core.whatsapp_entry import INVITE_PATTERN, OBSERVATION_SECONDS
from backend.app.models.user import DestinationChannel
from backend.app.models.whatsapp_connection import WhatsAppConnection
from backend.app.models.whatsapp_website import WhatsAppWebsite

router = APIRouter(tags=["Public WhatsApp entry"])
HEADERS = {
    "Cache-Control": "no-store, max-age=0",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
UNAVAILABLE = '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grupo temporariamente indisponível</title><main><h1>Estamos preparando o próximo grupo</h1><p>Tente novamente em alguns instantes.</p></main></html>'


@router.api_route("/public/whatsapp/{public_id}", methods=["GET", "HEAD"])
async def enter_whatsapp(
    public_id: UUID, request: Request, db: AsyncSession = Depends(get_db)
):
    """Redirect only to this campaign's fresh, enabled, owned group; fail closed on DB errors."""
    now = datetime.now(timezone.utc)
    try:
        result = (
            await db.execute(
                select(WhatsAppWebsite.invite_url)
                .join(
                    DestinationChannel,
                    and_(
                        DestinationChannel.id == WhatsAppWebsite.active_destination_id,
                        DestinationChannel.user_id == WhatsAppWebsite.user_id,
                    ),
                )
                .join(
                    WhatsAppConnection,
                    and_(
                        WhatsAppConnection.id == WhatsAppWebsite.connection_id,
                        WhatsAppConnection.user_id == WhatsAppWebsite.user_id,
                    ),
                )
                .where(
                    WhatsAppWebsite.public_id == str(public_id),
                    WhatsAppWebsite.enabled.is_(True),
                    WhatsAppWebsite.pending_request_id.is_(None),
                    WhatsAppWebsite.invite_expires_at > now,
                    WhatsAppWebsite.observed_at <= now,
                    WhatsAppWebsite.observed_at
                    > now - timedelta(seconds=OBSERVATION_SECONDS),
                    WhatsAppWebsite.member_count >= 0,
                    WhatsAppWebsite.member_count < WhatsAppWebsite.observed_entry_limit,
                    DestinationChannel.enabled.is_(True),
                    DestinationChannel.platform == "whatsapp",
                    DestinationChannel.chat_type == "group",
                    or_(
                        DestinationChannel.connection_id == WhatsAppConnection.id,
                        and_(
                            DestinationChannel.connection_id.is_(None),
                            WhatsAppConnection.is_default.is_(True),
                        ),
                    ),
                )
            )
        ).scalar_one_or_none()
    except SQLAlchemyError:
        result = None
    if isinstance(result, str) and INVITE_PATTERN.fullmatch(result):
        return RedirectResponse(result, status_code=302, headers=HEADERS)
    return HTMLResponse(
        "" if request.method == "HEAD" else UNAVAILABLE,
        status_code=503,
        headers={
            **HEADERS,
            "Retry-After": "60",
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        },
    )
