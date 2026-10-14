from fastapi import FastAPI
from backend.app.api.v1.endpoints import admin, users, whatsapp
from backend.app.core.db.migrations import run_migrations

app = FastAPI(
    title="Offers Bot API",
    description="Backend for the Telegram Offers Bot Automation",
    version="1.0.0",
)


@app.on_event("startup")
async def validate_config_on_startup():
    """Apply Better Auth and application migrations before serving requests."""
    await run_migrations()


@app.get("/health")
async def health_check():
    """Return liveness status after application startup completes."""
    return {"status": "healthy"}


# Include routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(admin.router, prefix="/admin", tags=["Administration"])
app.include_router(whatsapp.router)
