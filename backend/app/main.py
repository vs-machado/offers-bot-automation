from fastapi import FastAPI
from backend.app.api.v1.endpoints import admin, auth, users
from backend.app.core.db.migrations import run_migrations
from backend.app.core.security import validate_auth_config

app = FastAPI(
    title="Offers Bot API",
    description="Backend for the Telegram Offers Bot Automation",
    version="1.0.0",
)


@app.on_event("startup")
async def validate_config_on_startup():
    """Validate auth settings and apply pending database migrations."""
    validate_auth_config()
    await run_migrations()


@app.get("/health")
async def health_check():
    """Return liveness status after application startup completes."""
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(admin.router, prefix="/admin", tags=["Administration"])
