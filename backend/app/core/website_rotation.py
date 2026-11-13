"""Serialize website configuration/rotation across replicas without long DB transactions."""

from contextlib import asynccontextmanager

from sqlalchemy import text

from backend.app.core.db.session import engine


@asynccontextmanager
async def website_lock(user_id: int):
    """Hold a dedicated PostgreSQL session lock across WAHA calls; release before pooling."""
    async with engine.connect() as connection:
        acquired = False
        try:
            acquired = bool(
                (
                    await connection.execute(
                        text("SELECT pg_try_advisory_lock(81276, :user_id)"),
                        {"user_id": user_id},
                    )
                ).scalar()
            )
            await connection.commit()
            yield acquired
        finally:
            if acquired:
                try:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(81276, :user_id)"),
                        {"user_id": user_id},
                    )
                    await connection.commit()
                except BaseException:
                    await connection.invalidate()
                    raise
