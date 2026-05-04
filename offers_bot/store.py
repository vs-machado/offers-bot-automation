from __future__ import annotations

import sqlite3
from pathlib import Path


class OfferStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_offers (
                source_chat TEXT NOT NULL,
                source_message_id INTEGER NOT NULL,
                source_url TEXT NOT NULL,
                affiliate_url TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source_chat, source_message_id, source_url)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_processed_offers_source_url ON processed_offers(source_url)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_processed_offers_affiliate_url ON processed_offers(affiliate_url)"
        )
        self._conn.commit()

    def seen(self, source_chat: str, message_id: int, source_url: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM processed_offers
            WHERE source_url = ?
                AND affiliate_url IS NOT NULL
            """,
            (source_url,),
        ).fetchone()
        return row is not None

    def seen_affiliate_url(self, affiliate_url: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM processed_offers
            WHERE affiliate_url = ?
            """,
            (affiliate_url,),
        ).fetchone()
        return row is not None

    def mark(self, source_chat: str, message_id: int, source_url: str, affiliate_url: str | None) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO processed_offers
                (source_chat, source_message_id, source_url, affiliate_url)
            VALUES (?, ?, ?, ?)
            """,
            (source_chat, message_id, source_url, affiliate_url),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
