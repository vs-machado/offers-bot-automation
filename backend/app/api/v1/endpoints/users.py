import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.db.session import get_db
from backend.app.models.user import DestinationChannel, Offer, User, UserConfig
from backend.app.schemas.user import (
    DestinationChannelCreate,
    DestinationChannelRead,
    UserConfigCreate,
    UserConfigRead,
)
from backend.app.schemas.offer import OfferCreate, OfferRead
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.worker.poster import BotPoster, BotPosterError

router = APIRouter()


async def _verify_destination_enabled(chat_id: str, enabled: bool) -> None:
    if not enabled:
        return
    try:
        can_post = await BotPoster().can_post(chat_id)
    except BotPosterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not can_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot cannot post to this destination",
        )


@router.get("/me/configs", response_model=list[UserConfigRead])
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(UserConfig).where(UserConfig.user_id == current_user.id)
    result = await db.execute(statement)
    configs = result.scalars().all()
    for c in configs:
        c.config_data = json.loads(c.config_data)
    return configs


@router.post(
    "/me/configs", response_model=UserConfigRead, status_code=status.HTTP_201_CREATED
)
async def create_config(
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_config = UserConfig(
        user_id=current_user.id,
        config_type=config_data.config_type,
        config_data=json.dumps(config_data.config_data),
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    new_config.config_data = json.loads(new_config.config_data)
    return new_config


@router.put("/me/configs/{config_id}", response_model=UserConfigRead)
async def update_config(
    config_id: int,
    config_data: UserConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Config not found"
        )

    config.config_type = config_data.config_type
    config.config_data = json.dumps(config_data.config_data)
    await db.commit()
    await db.refresh(config)
    config.config_data = json.loads(config.config_data)
    return config


@router.delete("/me/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    statement = select(UserConfig).where(
        UserConfig.id == config_id, UserConfig.user_id == current_user.id
    )
    result = await db.execute(statement)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Config not found"
        )

    await db.delete(config)
    await db.commit()


@router.get("/me/destinations", response_model=list[DestinationChannelRead])
async def list_destinations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    await _verify_destination_enabled(
        destination_data.chat_id, destination_data.enabled
    )
    new_destination = DestinationChannel(
        user_id=current_user.id,
        chat_id=destination_data.chat_id,
        title=destination_data.title,
        chat_type=destination_data.chat_type,
        enabled=destination_data.enabled,
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
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found"
        )

    await _verify_destination_enabled(
        destination_data.chat_id, destination_data.enabled
    )

    destination.chat_id = destination_data.chat_id
    destination.title = destination_data.title
    destination.chat_type = destination_data.chat_type
    destination.enabled = destination_data.enabled
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
    statement = select(DestinationChannel).where(
        DestinationChannel.id == destination_id,
        DestinationChannel.user_id == current_user.id,
    )
    result = await db.execute(statement)
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found"
        )

    await db.delete(destination)
    await db.commit()


@router.get("/me/offers", response_model=list[OfferRead])
async def list_offers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found"
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
    statement = select(Offer).where(
        Offer.id == offer_id, Offer.user_id == current_user.id
    )
    result = await db.execute(statement)
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found"
        )

    await db.delete(offer)
    await db.commit()
