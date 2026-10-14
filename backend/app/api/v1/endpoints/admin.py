from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.endpoints.auth import require_admin
from backend.app.core.db.session import get_db
from backend.app.models.user import SourceGroup
from backend.app.schemas.source_group import SourceGroupRead, SourceGroupWrite

router = APIRouter(dependencies=[Depends(require_admin)])


async def _save(db: AsyncSession, group: SourceGroup) -> SourceGroup:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Este grupo do Telegram já está cadastrado."
        ) from exc
    await db.refresh(group)
    return group


async def _find(db: AsyncSession, group_id: int) -> SourceGroup:
    result = await db.execute(select(SourceGroup).where(SourceGroup.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Grupo de origem não encontrado.")
    return group


@router.get("/source-groups", response_model=list[SourceGroupRead])
async def list_source_groups(db: AsyncSession = Depends(get_db)):
    """Return the complete catalog, including disabled sources, to admins only."""
    result = await db.execute(select(SourceGroup).order_by(SourceGroup.id))
    return result.scalars().all()


@router.post("/source-groups", response_model=SourceGroupRead, status_code=201)
async def create_source_group(
    body: SourceGroupWrite, db: AsyncSession = Depends(get_db)
):
    """Add an admin-approved source to the catalog used by selection and ingestion."""
    group = SourceGroup(**body.model_dump())
    db.add(group)
    return await _save(db, group)


@router.put("/source-groups/{group_id}", response_model=SourceGroupRead)
async def update_source_group(
    group_id: int, body: SourceGroupWrite, db: AsyncSession = Depends(get_db)
):
    """Update source URL, display name, or availability after an admin role check."""
    group = await _find(db, group_id)
    for key, value in body.model_dump().items():
        setattr(group, key, value)
    return await _save(db, group)


@router.delete("/source-groups/{group_id}", status_code=204)
async def delete_source_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a source; saved subscriptions to it become inactive on worker refresh."""
    group = await _find(db, group_id)
    await db.delete(group)
    await db.commit()
    return Response(status_code=204)
