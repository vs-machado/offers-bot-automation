from fastapi import FastAPI
from backend.app.api.v1.endpoints import auth, users
from backend.app.core.db.base import Base
from backend.app.core.db.session import engine
from backend.app.core.security import validate_auth_config
from backend.app.models import user, worker  # noqa: F401

app = FastAPI(
    title="Offers Bot API",
    description="Backend for the Telegram Offers Bot Automation",
    version="1.0.0",
)


@app.on_event("startup")
async def validate_config_on_startup():
    validate_auth_config()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
