"""Promote or demote an existing account through trusted operator CLI access."""

import argparse
import asyncio

from dotenv import load_dotenv
from sqlalchemy import select


async def set_role(email: str, role: str) -> None:
    """Change an existing database role; never create or promote from signup data."""
    load_dotenv()
    # The database module reads DATABASE_URL at import time, after loading .env.
    from backend.app.core.db.session import AsyncSessionLocal, engine
    from backend.app.models.user import User

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                raise SystemExit("Account not found. Register the account first.")
            user.role = role
            await db.commit()
            print(f"Role for {email}: {role}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--role", choices=["admin", "user"], default="admin")
    args = parser.parse_args()
    asyncio.run(set_role(args.email, args.role))
