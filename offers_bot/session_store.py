"""Persistent session storage via SQLite.

Saves Telegram session strings so users don't re-scan QR on every restart.
Single-user for now; ``user_id`` column ready for multi-user SaaS Phase 3+.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class SessionStore:
    """Stores and retrieves Telegram session strings from SQLite.

    Args:
        path: Path to the SQLite database file.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_sessions (
                user_id TEXT PRIMARY KEY,
                session_string TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    # ── Public API ──────────────────────────────────────────

    def get_session(self, user_id: str = "primary") -> str | None:
        """Return saved session string for *user_id*, or ``None``."""
        row = self._conn.execute(
            "SELECT session_string FROM telegram_sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else None

    def save_session(self, session_string: str, user_id: str = "primary") -> None:
        """Upsert *session_string* for *user_id*."""
        self._conn.execute(
            """
            INSERT INTO telegram_sessions (user_id, session_string, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                session_string = excluded.session_string,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, session_string),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
