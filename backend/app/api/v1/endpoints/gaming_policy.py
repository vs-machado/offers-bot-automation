"""Authenticated editorial controls shared by Telegram and WhatsApp destinations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.core.credentials import decrypt_config, encrypt_config
from backend.app.core.db.session import get_db
from backend.app.core.gaming_policy import CONFIG_TYPE, GamingPolicy
from backend.app.models.user import DestinationChannel, User, UserConfig

router = APIRouter()


@router.get("/me/gaming-policy", response_model=GamingPolicy)
async def get_gaming_policy(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Return this user's gaming controls; missing policy permits all offers."""
    row = (
        (
            await db.execute(
                select(UserConfig)
                .where(
                    UserConfig.user_id == current_user.id,
                    UserConfig.config_type == CONFIG_TYPE,
                )
                .order_by(UserConfig.id)
            )
        )
        .scalars()
        .first()
    )
    return (
        GamingPolicy.model_validate(
            decrypt_config(row.config_data, current_user.id, CONFIG_TYPE)
        )
        if row
        else GamingPolicy()
    )


@router.put("/me/gaming-policy", response_model=GamingPolicy)
async def save_gaming_policy(
    body: GamingPolicy,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist owned platform/destination rules, serializing concurrent updates per user."""
    await db.execute(
        select(User.id).where(User.id == current_user.id).with_for_update()
    )
    owned = set(
        (
            await db.execute(
                select(DestinationChannel.chat_id).where(
                    DestinationChannel.user_id == current_user.id
                )
            )
        )
        .scalars()
        .all()
    )
    if set(body.destinations) - owned:
        raise HTTPException(400, "Selecione somente destinos da sua conta.")
    row = (
        (
            await db.execute(
                select(UserConfig)
                .where(
                    UserConfig.user_id == current_user.id,
                    UserConfig.config_type == CONFIG_TYPE,
                )
                .order_by(UserConfig.id)
            )
        )
        .scalars()
        .first()
    )
    encrypted = encrypt_config(body.model_dump(), current_user.id, CONFIG_TYPE)
    if row:
        row.config_data = encrypted
    else:
        db.add(
            UserConfig(
                user_id=current_user.id, config_type=CONFIG_TYPE, config_data=encrypted
            )
        )
    await db.commit()
    return body
