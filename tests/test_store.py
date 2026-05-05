import tempfile
import unittest
import sqlite3
from pathlib import Path

from offers_bot.store import OfferStore


class OfferStoreTest(unittest.TestCase):
    def test_marks_processed_offer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = OfferStore(Path(tmpdir) / "offers.sqlite3")

            self.assertFalse(store.seen("chat", 10, "https://meli.la/abc"))
            store.mark("chat", 10, "https://meli.la/abc", "https://meli.la/new")
            self.assertTrue(store.seen("chat", 10, "https://meli.la/abc"))

            store.close()

    def test_seen_deduplicates_same_source_url_across_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = OfferStore(Path(tmpdir) / "offers.sqlite3")

            store.mark("chat-a", 10, "https://meli.la/abc", "https://meli.la/new")

            self.assertTrue(store.seen("chat-b", 99, "https://meli.la/abc"))

            store.close()

    def test_seen_affiliate_url_detects_posted_product(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = OfferStore(Path(tmpdir) / "offers.sqlite3")

            store.mark("chat-a", 10, "https://meli.la/abc", "https://meli.la/final")

            self.assertTrue(store.seen_affiliate_url("https://meli.la/final"))
            self.assertFalse(store.seen_affiliate_url("https://meli.la/other"))

            store.close()

    def test_seen_product_key_detects_same_product_with_different_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = OfferStore(Path(tmpdir) / "offers.sqlite3")

            store.mark("chat-a", 10, "https://meli.la/abc", "https://meli.la/final", "MLB123456:MLB999999")

            self.assertTrue(store.seen_product_key("MLB123456:MLB999999"))
            self.assertFalse(store.seen_product_key("MLB123456:MLB888888"))

            store.close()

    def test_adds_product_key_column_to_existing_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "offers.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE processed_offers (
                    source_chat TEXT NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    affiliate_url TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_chat, source_message_id, source_url)
                )
                """
            )
            conn.commit()
            conn.close()

            store = OfferStore(db_path)
            store.mark("chat-a", 10, "https://meli.la/abc", "https://meli.la/final", "MLB123456")

            self.assertTrue(store.seen_product_key("MLB123456"))

            store.close()


if __name__ == "__main__":
    unittest.main()
