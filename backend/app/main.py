from fastapi import FastAPI
from backend.app.api.v1.endpoints import auth

app = FastAPI(
    title="Offers Bot API",
    description="Backend for the Telegram Offers Bot Automation",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# app.include_router(users.router, prefix="/users", tags=["Users"])
