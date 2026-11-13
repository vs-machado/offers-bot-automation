"""Authenticated per-user configuration and explicit recovery of uncertain creations."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.api.v1.endpoints.whatsapp import call
from backend.app.core.credentials import MASK, decrypt_config, encrypt_config
from backend.app.core.db.session import get_db
from backend.app.core.website_rotation import website_lock
from backend.app.core.whatsapp_connections import owned_connection
from backend.app.core.whatsapp_management import WhatsAppManagement
from backend.app.models.user import DestinationChannel, User
from backend.app.models.whatsapp_website import WhatsAppWebsite
from backend.app.schemas.whatsapp_website import WebsiteRecovery, WebsiteSettings

router = APIRouter(prefix="/users/me/whatsapp/website", tags=["WhatsApp website"])
CONFIG_TYPE = "whatsapp_website"


def stored_settings(row):
    return (
        decrypt_config(row.config_data, row.user_id, CONFIG_TYPE)
        if row
        else WebsiteSettings().model_dump()
    )


def representation(row):
    settings = stored_settings(row)
    settings["update_token"] = MASK if settings["update_token"] else ""
    return {
        "settings": settings,
        "active_destination_id": row.active_destination_id if row else None,
        "pending_destination_id": row.pending_destination_id if row else None,
        "needs_recovery": bool(
            row and row.pending_request_id and not row.pending_destination_id
        ),
        "member_count": row.member_count if row else None,
        "observed_at": row.observed_at if row else None,
        "last_synced_at": row.last_synced_at if row else None,
        "last_error": row.last_error if row else None,
    }


async def owned_group(db, user_id, destination_id, connection):
    row = (
        await db.execute(
            select(DestinationChannel).where(
                DestinationChannel.id == destination_id,
                DestinationChannel.user_id == user_id,
                DestinationChannel.platform == "whatsapp",
                DestinationChannel.chat_type == "group",
            )
        )
    ).scalar_one_or_none()
    if row is None or not (
        row.connection_id == connection.id
        or (connection.is_default and row.connection_id is None)
    ):
        raise HTTPException(404, "Grupo não encontrado nesta conexão.")
    return row


@router.get("")
async def get_website(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read only this owner's configuration; never expose the stored update token."""
    response.headers["Cache-Control"] = "no-store"
    row = (
        await db.execute(
            select(WhatsAppWebsite).where(WhatsAppWebsite.user_id == user.id)
        )
    ).scalar_one_or_none()
    return representation(row)


@router.put("")
async def save_website(
    body: dict,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save encrypted settings under the rotation lock; creation runs asynchronously."""
    from pydantic import ValidationError

    response.headers["Cache-Control"] = "no-store"
    async with website_lock(user.id) as acquired:
        if not acquired:
            raise HTTPException(
                409, "Monitor em execução. Tente salvar novamente em instantes."
            )
        row = (
            await db.execute(
                select(WhatsAppWebsite).where(WhatsAppWebsite.user_id == user.id)
            )
        ).scalar_one_or_none()
        previous = stored_settings(row)
        data = dict(body)
        if data.get("update_token") == MASK:
            data["update_token"] = previous["update_token"]
        try:
            settings = WebsiteSettings.model_validate(data)
        except ValidationError:
            raise HTTPException(
                422,
                "Verifique URL HTTPS aprovada, conexão, token, nome e limites do site.",
            ) from None
        connection = (
            await owned_connection(db, user.id, settings.connection_id)
            if settings.connection_id
            else None
        )
        if settings.template_destination_id:
            if not connection:
                raise HTTPException(400, "Selecione a conexão do grupo modelo.")
            await owned_group(db, user.id, settings.template_destination_id, connection)
        if (
            row
            and settings.connection_id != previous["connection_id"]
            and (row.active_destination_id or row.pending_request_id)
        ):
            raise HTTPException(
                409,
                "Mantenha a conexão atual; adote um grupo dessa conexão para recuperar a campanha.",
            )
        if row is None:
            row = WhatsAppWebsite(user_id=user.id)
            db.add(row)
        row.config_data = encrypt_config(settings.model_dump(), user.id, CONFIG_TYPE)
        row.next_check_at = None
        row.failures = 0
        await db.commit()
        return representation(row)


@router.post("/recover")
async def recover_website(
    body: WebsiteRecovery,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly adopt a verified saved group after an uncertain creation; never recreate it."""
    async with website_lock(user.id) as acquired:
        if not acquired:
            raise HTTPException(
                409, "Monitor em execução. Tente novamente em instantes."
            )
        row = (
            await db.execute(
                select(WhatsAppWebsite).where(WhatsAppWebsite.user_id == user.id)
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(404, "Configure o site primeiro.")
        settings = WebsiteSettings.model_validate(stored_settings(row))
        connection = await owned_connection(db, user.id, settings.connection_id)
        if not connection:
            raise HTTPException(400, "Selecione a conexão WhatsApp.")
        destination = await owned_group(db, user.id, body.destination_id, connection)
        manager = WhatsAppManagement(
            user.id, None if connection.is_default else connection.id
        )
        await call(manager.group(destination.chat_id, require_admin=True))
        if not destination.enabled:
            raise HTTPException(
                400,
                "Conclua as configurações e habilite ofertas no grupo antes de adotá-lo.",
            )
        row.active_destination_id = destination.id
        row.pending_destination_id = None
        row.pending_request_id = None
        row.member_count = None
        row.observed_at = None
        row.next_check_at = None
        row.last_error = None
        row.failures = 0
        await db.commit()
        return representation(row)
