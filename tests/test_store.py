import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
