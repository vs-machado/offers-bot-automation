"""Periodic owner-isolated WhatsApp creation and authenticated website synchronization."""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import or_, select

from backend.app.core.credentials import decrypt_config
from backend.app.core.db.session import AsyncSessionLocal
from backend.app.core.website_rotation import website_lock
from backend.app.core.whatsapp_connections import owned_connection, validate_routing
from backend.app.core.whatsapp_management import WhatsAppManagement, next_group_name
from backend.app.models.user import DestinationChannel, WhatsAppGroupCreation
from backend.app.models.whatsapp_website import WhatsAppWebsite
from backend.app.schemas.whatsapp_management import GroupSettings
from backend.app.schemas.whatsapp_website import WebsiteSettings
from backend.worker.poster import BotPosterError

LOGGER = logging.getLogger(__name__)
MONITOR_SECONDS = 60
OBSERVATION_SECONDS = 180


def now():
    return datetime.now(timezone.utc)


def entry_threshold(settings, capacity=None):
    """Use provider capacity when known, otherwise the explicitly configured entry limit."""
    return (
        min(settings.entry_limit, capacity - settings.safety_margin)
        if capacity
        else settings.entry_limit
    )


async def group_observation(manager, chat_id):
    """Read only participant count and capacity; malformed/unknown data never means vacancies."""
    path = manager.path(chat_id)
    data = (await manager.client.request("GET", f"{path}/participants")).json()
    if (
        not isinstance(data, list)
        or not data
        or any(not isinstance(p, dict) or not p.get("id") for p in data)
    ):
        raise BotPosterError("Não foi possível confirmar a contagem de membros.")
    count = sum(p.get("role") != "left" for p in data)
    metadata = (await manager.client.request("GET", path)).json()
    if not isinstance(metadata, dict):
        raise BotPosterError("Não foi possível confirmar a capacidade do grupo.")
    meta = metadata.get("groupMetadata") or metadata
    if not isinstance(meta, dict):
        raise BotPosterError("Não foi possível confirmar a capacidade do grupo.")
    capacity = meta.get("maxParticipants")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
        capacity = None
    return count, capacity


async def group_invite(manager, chat_id):
    """Read, never regenerate, an invite code from WAHA and constrain its WhatsApp host."""
    data = (
        await manager.client.request("GET", f"{manager.path(chat_id)}/invite-code")
    ).json()
    code = data.get("code") if isinstance(data, dict) else data
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9]{20,32}", code):
        raise BotPosterError("Não foi possível confirmar o convite do grupo.")
    return f"https://chat.whatsapp.com/{code}"


async def destination_for(db, row, connection, destination_id):
    destination = (
        await db.execute(
            select(DestinationChannel).where(
                DestinationChannel.id == destination_id,
                DestinationChannel.user_id == row.user_id,
                DestinationChannel.platform == "whatsapp",
                DestinationChannel.chat_type == "group",
            )
        )
    ).scalar_one_or_none()
    if destination is None or not (
        destination.connection_id == connection.id
        or (connection.is_default and destination.connection_id is None)
    ):
        raise BotPosterError(
            "Grupo removido ou transferido. Adote um grupo desta conexão para continuar."
        )
    return destination


async def push_website(db, row, settings, invite=None):
    """Persist a monotonic revision before sending; retries cannot resurrect an older invite."""
    row.revision += 1
    await db.commit()
    expires_at = int((now() + timedelta(seconds=OBSERVATION_SECONDS)).timestamp())
    if invite:
        expires_at = int(
            (row.observed_at + timedelta(seconds=OBSERVATION_SECONDS)).timestamp()
        )
    payload = {"revision": row.revision, "invite_url": invite, "expires_at": expires_at}
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, trust_env=False
    ) as client:
        response = await client.post(
            f"{settings.website_url}/api/whatsapp",
            headers={"Authorization": f"Bearer {settings.update_token}"},
            json=payload,
        )
    if response.status_code != 200 or response.json().get("revision") != row.revision:
        raise BotPosterError(
            "Site não confirmou a atualização. Confira URL, token, Functions e banco D1."
        )
    row.last_synced_at = now()
    await db.commit()


async def prepare_successor(db, row, settings, connection, manager):
    """Persist creation intent before WAHA; resume known groups but never retry uncertain creates."""
    if row.pending_request_id and not row.pending_destination_id:
        raise BotPosterError(
            "Criação com resultado incerto. Confira os grupos e use Adotar grupo; criação automática bloqueada."
        )
    source_id = row.active_destination_id or settings.template_destination_id
    source = (
        await destination_for(db, row, connection, source_id) if source_id else None
    )
    await db.commit()
    if not row.pending_destination_id:
        # Capacity is checked before any external creation and again on activation.
        await validate_routing(db, row.user_id, connection, "", "group", True)
        await db.commit()
        if (await manager.client.status())["status"] != "WORKING":
            raise BotPosterError("Conecte seu WhatsApp antes de criar grupos.")
        names = [group["name"] for group in await manager.client.groups()]
        base = re.sub(r"\s*#\d+\s*$", "", settings.group_name).strip()
        name = (
            next_group_name(settings.group_name, names)
            if any(
                re.fullmatch(
                    re.escape(base) + r"(?:\s*#\d+)?", name.strip(), re.IGNORECASE
                )
                for name in names
            )
            else settings.group_name
        )
        row.pending_request_id = str(uuid4())
        receipt = WhatsAppGroupCreation(
            request_id=row.pending_request_id,
            user_id=row.user_id,
            connection_id=connection.id,
        )
        db.add(receipt)
        await db.commit()
        chat_id = await manager.create(name)
        destination = DestinationChannel(
            user_id=row.user_id,
            connection_id=connection.id,
            platform="whatsapp",
            chat_type="group",
            chat_id=chat_id,
            title=name,
            categories=source.categories if source else None,
            enabled=False,
        )
        db.add(destination)
        # Receipt + known destination commit together; interrupted configuration can safely resume.
        await db.flush()
        row.pending_destination_id = destination.id
        receipt.result = {
            "id": chat_id,
            "name": name,
            "destination_id": destination.id,
            "warnings": ["Configuração automática pendente."],
        }
        await db.commit()
    destination = await destination_for(db, row, connection, row.pending_destination_id)
    await db.commit()
    description = settings.description
    photo = None
    if source:
        template = await manager.group(source.chat_id, require_admin=True)
        description = template["description"]
        photo = await manager.source_photo(source.chat_id)
    draft = GroupSettings(
        name=destination.title,
        description=description,
        admins_only=True,
        categories=destination.categories,
        enabled=True,
    )
    warnings = await manager.apply_settings(destination.chat_id, draft, photo)
    if warnings:
        raise BotPosterError(
            "Grupo criado, mas configuração incompleta. Confira nome, descrição, foto e permissões."
        )
    observed_at = now()
    count, capacity = await group_observation(manager, destination.chat_id)
    invite = await group_invite(manager, destination.chat_id)
    if count >= entry_threshold(settings, capacity):
        raise BotPosterError(
            "Novo grupo não tem vagas verificadas. Confira o limite de entrada."
        )
    await validate_routing(
        db, row.user_id, connection, destination.chat_id, "group", True, destination.id
    )
    destination.enabled = True
    row.active_destination_id = destination.id
    row.pending_destination_id = None
    row.member_count = count
    row.observed_at = observed_at
    receipt = (
        (
            await db.execute(
                select(WhatsAppGroupCreation).where(
                    WhatsAppGroupCreation.user_id == row.user_id,
                    WhatsAppGroupCreation.request_id == row.pending_request_id,
                )
            )
        ).scalar_one_or_none()
        if row.pending_request_id
        else None
    )
    if receipt:
        receipt.result = {
            "id": destination.chat_id,
            "name": destination.title,
            "destination_id": destination.id,
            "enabled": True,
            "warnings": [],
        }
    row.pending_request_id = None
    await db.commit()
    LOGGER.info(
        "Website group activated user=%s destination=%s count=%s",
        row.user_id,
        destination.id,
        count,
    )
    return invite


async def reconcile(db, row, settings):
    """Keep publishing to prior groups while changing only the website's active entry group."""
    if not settings.website_url or not settings.update_token:
        return
    if not settings.enabled:
        await push_website(db, row, settings)
        return
    connection = await owned_connection(db, row.user_id, settings.connection_id)
    if connection is None:
        raise BotPosterError("Conexão WhatsApp não encontrada.")
    await db.commit()
    manager = WhatsAppManagement(
        row.user_id, None if connection.is_default else connection.id
    )
    if (await manager.client.status())["status"] != "WORKING":
        await push_website(db, row, settings)
        raise BotPosterError("Conexão WhatsApp indisponível. Reconecte a conta.")
    if row.pending_request_id:
        # Remove a full/uncertain previous entry before resuming any successor.
        await push_website(db, row, settings)
        invite = await prepare_successor(db, row, settings, connection, manager)
    elif row.active_destination_id:
        try:
            destination = await destination_for(
                db, row, connection, row.active_destination_id
            )
        except BotPosterError:
            await push_website(db, row, settings)
            raise
        if not destination.enabled:
            await push_website(db, row, settings)
            raise BotPosterError(
                "Ofertas desativadas no grupo ativo. Habilite o grupo ou adote outro."
            )
        await db.commit()
        observed_at = now()
        count, capacity = await group_observation(manager, destination.chat_id)
        row.member_count = count
        row.observed_at = observed_at
        await db.commit()
        if count < entry_threshold(settings, capacity):
            invite = await group_invite(manager, destination.chat_id)
        else:
            await push_website(db, row, settings)
            invite = await prepare_successor(db, row, settings, connection, manager)
    else:
        await push_website(db, row, settings)
        if row.observed_at is not None:
            raise BotPosterError(
                "Grupo ativo removido. Adote um grupo desta conexão para continuar."
            )
        invite = await prepare_successor(db, row, settings, connection, manager)
    await push_website(db, row, settings, invite)


async def monitor_once():
    """Poll due users independently; cross-process locks and persisted backoff suppress duplicates."""
    async with AsyncSessionLocal() as db:
        user_ids = list(
            (
                await db.execute(
                    select(WhatsAppWebsite.user_id).where(
                        or_(
                            WhatsAppWebsite.next_check_at.is_(None),
                            WhatsAppWebsite.next_check_at <= now(),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
    for user_id in user_ids:
        async with website_lock(user_id) as acquired:
            if not acquired:
                continue
            async with AsyncSessionLocal() as db:
                row = (
                    await db.execute(
                        select(WhatsAppWebsite).where(
                            WhatsAppWebsite.user_id == user_id
                        )
                    )
                ).scalar_one_or_none()
                if row is None or (row.next_check_at and row.next_check_at > now()):
                    continue
                try:
                    settings = WebsiteSettings.model_validate(
                        decrypt_config(row.config_data, user_id, "whatsapp_website")
                    )
                    await reconcile(db, row, settings)
                except Exception as exc:
                    # Roll back activation/validation locks before recording failure.
                    await db.rollback()
                    row = (
                        await db.execute(
                            select(WhatsAppWebsite).where(
                                WhatsAppWebsite.user_id == user_id
                            )
                        )
                    ).scalar_one()
                    row.failures += 1
                    row.last_error = (
                        str(exc.detail)
                        if isinstance(exc, HTTPException)
                        else str(exc)
                        if isinstance(exc, BotPosterError)
                        else "Falha na sincronização. Confira conexão, site e permissões."
                    )
                    row.next_check_at = now() + timedelta(
                        seconds=min(
                            900, MONITOR_SECONDS * 2 ** min(row.failures - 1, 4)
                        )
                    )
                    # Do not renew a stale invite. Site expires it independently after 180s.
                    LOGGER.warning(
                        "Website sync failed user=%s failure=%s",
                        user_id,
                        type(exc).__name__,
                    )
                else:
                    row.failures = 0
                    row.last_error = None
                    row.next_check_at = now() + timedelta(seconds=MONITOR_SECONDS)
                await db.commit()


async def website_monitor_loop():
    """Run even without active offer subscriptions; failures never stop Telegram ingestion."""
    while True:
        try:
            await monitor_once()
        except Exception:
            LOGGER.warning("Website monitor unavailable; will retry", exc_info=False)
        await asyncio.sleep(10)
