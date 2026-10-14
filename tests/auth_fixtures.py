"""Database-backed fixtures for the shared Better Auth session contract."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.models.better_auth import AuthSession, AuthUser


class SQLiteAsyncSession:
    """Adapt synchronous test SQLAlchemy operations to the async API dependency."""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, item):
        self.session.add(item)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, item):
        self.session.refresh(item)

    async def delete(self, item):
        self.session.delete(item)


def create_identity(session, email, name="Test User", expires_in=timedelta(days=1)):
    """Persist an identity and opaque session as the Better Auth adapter would."""
    now = datetime.now(timezone.utc)
    identity = AuthUser(
        id=str(uuid4()),
        email=email,
        name=name,
        email_verified=False,
        created_at=now,
        updated_at=now,
    )
    session.add(identity)
    session.flush()
    login = AuthSession(
        id=str(uuid4()),
        token=uuid4().hex,
        user_id=identity.id,
        expires_at=now + expires_in,
        created_at=now,
        updated_at=now,
    )
    session.add(login)
    session.commit()
    return identity, login
