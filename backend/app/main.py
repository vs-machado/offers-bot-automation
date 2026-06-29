from fastapi import FastAPI
from backend.app.api.v1.endpoints import auth, users
from backend.app.core.security import validate_auth_config

app = FastAPI(
    title="Offers Bot API",
    description="Backend for the Telegram Offers Bot Automation",
    version="1.0.0",
)


@app.on_event("startup")
async def validate_config_on_startup():
    validate_auth_config()


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
