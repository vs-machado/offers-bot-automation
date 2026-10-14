import json
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.db.session import get_db
from backend.app.models.user import DestinationChannel, Offer, User, UserConfig
from backend.app.schemas.user import (
    DestinationChannelCreate,
    DestinationChannelRead,
    SourceGroupPreviewRequest,
    UserConfigCreate,
    UserConfigRead,
    UserRead,
)
from backend.app.schemas.offer import OfferCreate, OfferRead
from backend.app.schemas.delivery import DeliveryHistory
from backend.app.core.delivery_history import get_delivery_history
from backend.app.core.affiliate_validation import validate_credentials
from backend.app.schemas.affiliate_validation import (
    CredentialValidationRequest,
    CredentialValidationResult,
)
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.source_groups import approved_source, enabled_source_groups
from backend.app.core.telegram_sources import fetch_source_messages
from backend.worker.poster import BotPoster, BotPosterError

router = APIRouter()


@router.post(
    "/me/affiliate-credentials/validate", response_model=CredentialValidationResult
)
async def validate_affiliate_credentials(
    body: CredentialValidationRequest,
    current_user: User = Depends(get_current_user),
):
    """Probe the authenticated user's draft credentials without persisting them."""
    return await validate_credentials(body, current_user.id)


@router.get("/me/deliveries", response_model=DeliveryHistory)
async def list_deliveries(
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(20, ge=1, le=100),
    delivery_status: Literal[
        "queued",
        "retrying",
        "sending",
        "sent",
        "failed",
        "expired",
        "cancelled",
        "uncertain",
    ]
    | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return only the authenticated user's paginated delivery outcomes."""
    return await get_delivery_history(db, current_user.id, page, limit, delivery_status)


def _config_response(config: UserConfig) -> dict[str, object]:
    """Decode response data without marking the ORM's text column dirty."""
    return {
        "id": config.id,
        "user_id": config.user_id,
        "config_type": config.config_type,
        "config_data": json.loads(config.config_data)
        if isinstance(config.config_data, str)
        else config.config_data,
    }


REQUIRED_CONFIG_KEYS = {
    "amazon": ("amazon_affiliate_tag", "amazon_cookie_header"),
    "mercado_livre": ("ml_affiliate_tag", "ml_cookie_header", "ml_csrf_token"),
    "shopee": ("shopee_app_id", "shopee_app_secret"),
    "aliexpress": ("aliexpress_app_key", "aliexpress_app_secret"),
}


async def _preview_source_groups(
    source_chats: list[str],
    labels: dict[str, str] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Fetch recent public Telegram messages, returning empty groups on fetch errors."""
    try:
        messages_by_chat = await fetch_source_messages(source_chats)
    except Exception:
        messages_by_chat = {}

    return {
        "groups": [
            {
                "id": chat,
                "label": (labels or {}).get(chat, f"Source option {index + 1}"),
                "messages": [
                    {
                        "id": message.message_id,
                        "text": message.text,
                        "image_url": message.image_url,
                        "post_url": message.post_url,
                        "links": list(message.links),
                    }
                    for message in messages_by_chat.get(chat, [])
                ],
            }
            for index, chat in enumerate(source_chats)
        ]
    }


def _validate_config(
    config_data: UserConfigCreate, catalog: list[str] | None = None
) -> None:
    """Validate required credential fields for known affiliate providers."""
    if config_data.config_type == "source_chats":
        chats = config_data.config_data.get("source_chats")
        try:
            if not isinstance(chats, list) or any(
                not isinstance(chat, str) for chat in chats
            ):
                raise ValueError("Selecione os grupos de origem na lista disponível.")
            config_data.config_data = {
                "source_chats": list(
                    dict.fromkeys(approved_source(chat, catalog) for chat in chats)
                )
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    required_keys = REQUIRED_CONFIG_KEYS.get(config_data.config_type)
    if not required_keys:
        return

    missing = [
        key for key in required_keys if not str(config_data.config_data.get(key, ""))
    ]
    if missing:
        provider_name = {
            "amazon": "Amazon",
            "mercado_livre": "Mercado Livre",
            "shopee": "Shopee",
            "aliexpress": "AliExpress",
        }.get(config_data.config_type, "seu programa de afiliados")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Preencha os campos obrigatórios para configurar {provider_name}.",
                "missing_keys": missing,
            },
        )


async def _verify_destination_enabled(
    chat_id: str,
    enabled: bool,
    platform: str = "telegram",
    user_id: int | None = None,
    chat_type: str = "group",
) -> None:
    """Confirm platform bot can post before enabling a destination."""
    if not enabled:
        return
    try:
        if platform == "whatsapp":
            from backend.app.core.whatsapp import WahaClient

            await WahaClient(user_id).verify_destination(chat_id, chat_type)
            return
        can_post = await BotPoster().can_post(chat_id)
    except BotPosterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            400, "Não foi possível verificar conexão e permissões do destino."
        ) from exc
    if not can_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O bot não tem permissão para publicar neste grupo ou canal. Confira as permissões de administrador.",
        )


@router.get("/me/configs", response_model=list[UserConfigRead])
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return configuration records belonging to authenticated user."""
    statement = select(UserConfig).where(UserConfig.user_id == current_user.id)
    result = await db.execute(statement)
    configs = result.scalars().all()
    return [_config_response(config) for config in configs]


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: User = Depends(get_current_user),
):
    """Return authenticated user's profile."""
    return current_user


@router.get("/me/source-groups")
async def list_available_source_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the enabled operator catalog without fetching Telegram HTML previews."""
    return [
        {"url": group.url, "label": group.label}
        for group in await enabled_source_groups(db)
    ]


@router.get("/me/source-groups/messages")
async def list_source_group_messages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent messages from configured default source groups."""
    groups = await enabled_source_groups(db)
    return await _preview_source_groups(
        [group.url for group in groups], {group.url: group.label for group in groups}
    )


@router.post("/me/source-groups/preview")
async def preview_source_group(
    preview_data: SourceGroupPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview recent messages from one public Telegram source."""
    try:
        groups = await enabled_source_groups(db)
        chat = approved_source(preview_data.chat, [group.url for group in groups])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um grupo de origem do catálogo.",
        )

    response = await _preview_source_groups([chat])
    groups = response["groups"]
    if groups:
        groups[0]["label"] = "Catalog source"
    return response


@router.post(
    "/me/configs", response_model=UserConfigRead, status_code=status.HTTP_201_CREATED
)
async def create_config(
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist one configuration record for authenticated user."""
    catalog = (
        [group.url for group in await enabled_source_groups(db)]
        if config_data.config_type == "source_chats"
        else None
    )
    _validate_config(config_data, catalog)
    new_config = UserConfig(
        user_id=current_user.id,
        config_type=config_data.config_type,
        config_data=json.dumps(config_data.config_data),
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    return _config_response(new_config)


@router.put("/me/configs/{config_id}", response_model=UserConfigRead)
async def update_config(
    config_id: int,
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace owned configuration record after provider validation."""
    catalog = (
        [group.url for group in await enabled_source_groups(db)]
        if config_data.config_type == "source_chats"
        else None
    )
    _validate_config(config_data, catalog)
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Configuração não encontrada."
        )

    config.config_type = config_data.config_type
    config.config_data = json.dumps(config_data.config_data)
    await db.commit()
    await db.refresh(config)
    return _config_response(config)


@router.delete("/me/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete configuration record owned by authenticated user."""
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Configuração não encontrada."
        )

    await db.delete(config)
    await db.commit()


@router.get("/me/destinations", response_model=list[DestinationChannelRead])
async def list_destinations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return destination chats belonging to authenticated user."""
    statement = select(DestinationChannel).where(
        DestinationChannel.user_id == current_user.id
    )
    result = await db.execute(statement)
    return result.scalars().all()


@router.post(
    "/me/destinations",
    response_model=DestinationChannelRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_destination(
    destination_data: DestinationChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify and persist one destination chat for authenticated user."""
    await _verify_destination_enabled(
        destination_data.chat_id,
        destination_data.enabled,
        destination_data.platform,
        current_user.id,
        destination_data.chat_type,
    )
    new_destination = DestinationChannel(
        user_id=current_user.id,
        chat_id=destination_data.chat_id,
        title=destination_data.title,
        chat_type=destination_data.chat_type,
        enabled=destination_data.enabled,
        platform=destination_data.platform,
    )
    db.add(new_destination)
    await db.commit()
    await db.refresh(new_destination)
    return new_destination


@router.put("/me/destinations/{destination_id}", response_model=DestinationChannelRead)
async def update_destination(
    destination_id: int,
    destination_data: DestinationChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace owned destination details after posting-access verification."""
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo ou canal de publicação não encontrado.",
        )

    await _verify_destination_enabled(
        destination_data.chat_id,
        destination_data.enabled,
        destination_data.platform,
        current_user.id,
        destination_data.chat_type,
    )

    destination.chat_id = destination_data.chat_id
    destination.title = destination_data.title
    destination.chat_type = destination_data.chat_type
    destination.enabled = destination_data.enabled
    destination.platform = destination_data.platform
    await db.commit()
    await db.refresh(destination)
    return destination


@router.delete(
    "/me/destinations/{destination_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_destination(
    destination_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete destination chat owned by authenticated user."""
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grupo ou canal de publicação não encontrado.",
        )

    await db.delete(destination)
    await db.commit()


@router.get("/me/offers", response_model=list[OfferRead])
async def list_offers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return offer records belonging to authenticated user."""
    statement = select(Offer).where(Offer.user_id == current_user.id)
    result = await db.execute(statement)
    return result.scalars().all()


@router.post(
    "/me/offers", response_model=OfferRead, status_code=status.HTTP_201_CREATED
)
async def create_offer(
    offer_data: OfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist one offer record for authenticated user."""
    new_offer = Offer(
        user_id=current_user.id,
        platform=offer_data.platform,
        product_url=offer_data.product_url,
        title=offer_data.title,
        price=offer_data.price,
        currency=offer_data.currency,
        affiliate_url=offer_data.affiliate_url,
    )
    db.add(new_offer)
    await db.commit()
    await db.refresh(new_offer)
    return new_offer


@router.put("/me/offers/{offer_id}", response_model=OfferRead)
async def update_offer(
    offer_id: int,
    offer_data: OfferCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace offer record owned by authenticated user."""
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Oferta não encontrada."
        )

    offer.platform = offer_data.platform
    offer.product_url = offer_data.product_url
    offer.title = offer_data.title
    offer.price = offer_data.price
    offer.currency = offer_data.currency
    offer.affiliate_url = offer_data.affiliate_url
    await db.commit()
    await db.refresh(offer)
    return offer


@router.delete("/me/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(
    offer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete offer record owned by authenticated user."""
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Oferta não encontrada."
        )

    await db.delete(offer)
    await db.commit()
