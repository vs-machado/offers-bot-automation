"""PostgreSQL persistence shared by the platform reader and LLM accounting."""

import os

from sqlalchemy.engine import make_url


def connect():
    """Open a transactional connection using the application's database URL."""
    import psycopg

    url = make_url(
        os.getenv(
            "DATABASE_URL", "postgresql://postgres:password@localhost:5434/offers_db"
        )
    )
    if url.get_backend_name() != "postgresql":
        raise ValueError("DATABASE_URL must point to PostgreSQL")
    return psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False),
        connect_timeout=10,
    )


class PostgresSessionStore:
    """Persist the operator session independently of user-owned sessions."""

    def get_session(self, user_id: str = "primary") -> str | None:
        with connect() as conn:
            row = conn.execute(
                "SELECT session_string FROM platform_telegram_sessions WHERE name = %s",
                (user_id,),
            ).fetchone()
            return row[0] if row else None

    def save_session(self, session_string: str, user_id: str = "primary") -> None:
        """Upsert the authenticated operator session in one transaction."""
        with connect() as conn:
            conn.execute(
                """INSERT INTO platform_telegram_sessions (name, session_string)
                VALUES (%s, %s) ON CONFLICT (name) DO UPDATE
                SET session_string = excluded.session_string, updated_at = CURRENT_TIMESTAMP""",
                (user_id, session_string),
            )

    def close(self) -> None:
        pass
