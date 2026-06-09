import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.db.session import get_db
from backend.app.models.user import User, UserConfig
from backend.app.schemas.user import UserConfigCreate, UserConfigRead
from backend.app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


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
