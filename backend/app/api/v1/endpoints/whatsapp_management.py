"""Owner-scoped group management and existing destination category routing."""

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.api.v1.endpoints.whatsapp import call
from backend.app.core.db.session import get_db
from backend.app.core.whatsapp_management import WhatsAppManagement, uploaded_photo
from backend.app.models.user import DestinationChannel, User, WhatsAppGroupCreation
from backend.app.schemas.whatsapp_management import (
    GroupCreate,
    GroupSettings,
    RoutingSettings,
)
from backend.worker.poster import BotPosterError

router = APIRouter(prefix="/users/me/whatsapp/manage", tags=["WhatsApp management"])


async def destinations(db, user_id):
    result = await db.execute(
        select(DestinationChannel)
        .where(
            DestinationChannel.user_id == user_id,
            DestinationChannel.platform == "whatsapp",
        )
        .order_by(DestinationChannel.id)
    )
    return list(result.scalars().all())


def routing(destination):
    return {
        "destination_id": destination.id if destination else None,
        "categories": destination.categories if destination else None,
        "enabled": bool(destination and destination.enabled),
    }


async def destination_for(db, user_id, chat_id):
    return next(
        (row for row in await destinations(db, user_id) if row.chat_id == chat_id), None
    )


@router.get("/{kind}")
async def list_chats(
    kind: Literal["groups", "channels"],
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return capacity summaries and the same saved routing rules used by delivery workers."""
    response.headers["Cache-Control"] = "no-store"
    manager = WhatsAppManagement(user.id)
    chats = await call(manager.groups() if kind == "groups" else manager.channels())
    saved = {row.chat_id: row for row in await destinations(db, user.id)}
    return [{**chat, **routing(saved.get(chat["id"]))} for chat in chats]


@router.get("/{kind}/{chat_id}")
async def get_chat(
    kind: Literal["groups", "channels"],
    chat_id: str,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh live member/subscriber counts and verified settings for one owned chat."""
    response.headers["Cache-Control"] = "no-store"
    manager = WhatsAppManagement(user.id)
    chat = await call(
        manager.group(chat_id) if kind == "groups" else manager.channel(chat_id)
    )
    return {**chat, **routing(await destination_for(db, user.id, chat_id))}


@router.post("/groups", status_code=201)
async def create_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create once, inherit an owned template, and retain disabled destinations on partial failure."""
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    receipt = (
        await db.execute(
            select(WhatsAppGroupCreation).where(
                WhatsAppGroupCreation.user_id == user.id,
                WhatsAppGroupCreation.request_id == str(body.request_id),
            )
        )
    ).scalar_one_or_none()
    if receipt:
        if receipt.result is not None:
            return receipt.result
        raise HTTPException(
            409,
            "Criação já iniciada. Atualize os grupos para conferir o resultado; não repita a criação.",
        )
    manager = WhatsAppManagement(user.id)
    photo = uploaded_photo(body.photo)
    if body.source_id:
        source = await call(manager.group(body.source_id, require_admin=True))
        if "description" not in body.model_fields_set:
            body.description = source["description"]
        stored_source = await destination_for(db, user.id, body.source_id)
        if "categories" not in body.model_fields_set:
            body.categories = stored_source.categories if stored_source else None
        if body.reuse_photo and not photo:
            photo = await call(manager.source_photo(body.source_id))
    elif (await call(manager.client.status()))["status"] != "WORKING":
        raise HTTPException(400, "Conecte seu WhatsApp antes de criar grupos.")

    receipt = WhatsAppGroupCreation(user_id=user.id, request_id=str(body.request_id))
    db.add(receipt)
    # Durable before external side effects: retry never creates a second group.
    await db.commit()
    try:
        chat_id = await manager.create(body.name)
    except (BotPosterError, httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            400,
            "Não foi possível confirmar a criação. Atualize a lista de grupos antes de tentar novamente.",
        ) from exc
    destination = DestinationChannel(
        user_id=user.id,
        chat_id=chat_id,
        platform="whatsapp",
        chat_type="group",
        title=body.name,
        categories=body.categories,
        enabled=False,
    )
    db.add(destination)
    await db.commit()
    await db.refresh(destination)
    result = {
        "id": chat_id,
        "name": body.name,
        **routing(destination),
        "warnings": [
            "Grupo criado. Configuração interrompida; edite o grupo para concluir antes de habilitar publicações."
        ],
    }
    receipt.result = result
    await db.commit()
    warnings = await manager.apply_settings(chat_id, body, photo)
    destination.enabled = body.enabled and not warnings
    result = {
        "id": chat_id,
        "name": body.name,
        **routing(destination),
        "warnings": warnings,
    }
    receipt.result = result
    await db.commit()
    return result


@router.put("/groups/{chat_id}")
async def update_group(
    chat_id: str,
    body: GroupSettings,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit verified admin-owned group settings; report partial WAHA failures explicitly."""
    manager = WhatsAppManagement(user.id)
    await call(manager.group(chat_id, require_admin=True))
    warnings = await manager.apply_settings(chat_id, body, uploaded_photo(body.photo))
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    destination = await destination_for(db, user.id, chat_id)
    if not destination:
        destination = DestinationChannel(
            user_id=user.id, chat_id=chat_id, platform="whatsapp", chat_type="group"
        )
        db.add(destination)
    destination.title = body.name if not warnings else destination.title
    destination.categories = body.categories
    destination.enabled = body.enabled and not warnings
    await db.commit()
    await db.refresh(destination)
    return {
        "id": chat_id,
        "name": destination.title or chat_id,
        **routing(destination),
        "warnings": warnings,
    }


@router.put("/{kind}/{chat_id}/routing")
async def save_routing(
    kind: Literal["groups", "channels"],
    chat_id: str,
    body: RoutingSettings,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save shared category tags and publishing state, allowing owned destinations to pause offline."""
    manager = WhatsAppManagement(user.id)
    try:
        manager.path(chat_id, kind)
    except BotPosterError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    destination = await destination_for(db, user.id, chat_id)
    title = destination.title if destination else None
    if destination is None or (body.enabled and not destination.enabled):
        if kind == "groups":
            chat = await call(manager.group(chat_id))
            if (
                body.enabled
                and chat.get("admins_only") is not False
                and not chat["can_manage"]
            ):
                raise HTTPException(
                    400,
                    "Sua conta precisa ser administradora para publicar neste grupo.",
                )
        else:
            chat = await call(manager.channel(chat_id))
        title = chat["name"]
    if destination is None:
        destination = DestinationChannel(
            user_id=user.id,
            chat_id=chat_id,
            platform="whatsapp",
            chat_type="group" if kind == "groups" else "channel",
            title=title,
        )
        db.add(destination)
    destination.categories = body.categories
    destination.enabled = body.enabled
    await db.commit()
    await db.refresh(destination)
    return routing(destination)
