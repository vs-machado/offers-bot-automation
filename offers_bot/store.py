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
                product_key TEXT,
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
        self._ensure_product_key_column()
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_processed_offers_product_key ON processed_offers(product_key)"
        )
        self._conn.commit()

    def _ensure_product_key_column(self) -> None:
        columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(processed_offers)").fetchall()
        }
        if "product_key" not in columns:
            self._conn.execute("ALTER TABLE processed_offers ADD COLUMN product_key TEXT")

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

    def seen_product_key(self, product_key: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM processed_offers
            WHERE product_key = ?
            """,
            (product_key,),
        ).fetchone()
        return row is not None

    def mark(
        self,
        source_chat: str,
        message_id: int,
        source_url: str,
        affiliate_url: str | None,
        product_key: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO processed_offers
                (source_chat, source_message_id, source_url, affiliate_url, product_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_chat, message_id, source_url, affiliate_url, product_key),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
