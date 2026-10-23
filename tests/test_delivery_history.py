import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.core.delivery_history import get_delivery_history
from backend.app.models.user import DestinationChannel
from backend.app.models.worker import PromotionDelivery


class GroupedDeliveryHistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        PromotionDelivery.__table__.create(self.engine)
        DestinationChannel.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.db = AsyncMock()
        self.db.execute.side_effect = self.session.execute
        self.db.scalar.side_effect = self.session.scalar
        self.now = datetime.now(timezone.utc)

    def add_delivery(self, identity, key, status="sent", user_id=1, age=0):
        self.session.add(
            PromotionDelivery(
                id=identity,
                user_id=user_id,
                dedup_key=key,
                title="Same product title",
                platform="amazon",
                chat_id=f"chat-{identity}",
                status=status,
                stage="posting",
                attempts=1,
                expires_at=self.now + timedelta(hours=1),
                created_at=self.now - timedelta(minutes=age),
                updated_at=self.now,
            )
        )
        self.session.commit()

    async def test_pages_include_every_destination_and_exclude_other_users(self):
        self.add_delivery("a1", "offer-a", age=1)
        self.add_delivery("b1", "offer-b", age=2)
        self.add_delivery("a2", "offer-a", age=3)
        self.add_delivery("foreign", "offer-a", user_id=2)

        first = await get_delivery_history(self.db, 1, 1, 1, None, True)
        second = await get_delivery_history(self.db, 1, 2, 1, None, True)

        self.assertEqual(first["total"], 2)
        self.assertEqual(first["counts"], {"sent": 3})
        self.assertEqual([row["id"] for row in first["items"]], ["a1", "a2"])
        self.assertEqual({row["offer_id"] for row in first["items"]}, {"offer-a"})
        self.assertEqual([row["id"] for row in second["items"]], ["b1"])

    async def test_status_filter_retains_other_outcomes_for_matching_offer(self):
        self.add_delivery("sent", "mixed")
        self.add_delivery("failed", "mixed", status="failed", age=1)
        self.add_delivery("other", "success", age=2)

        history = await get_delivery_history(self.db, 1, 1, 20, "failed", True)

        self.assertEqual(history["total"], 1)
        self.assertEqual(
            {row["status"] for row in history["items"]}, {"sent", "failed"}
        )
        self.assertEqual(history["counts"], {"sent": 2, "failed": 1})

    async def test_legacy_rows_with_identical_titles_stay_separate(self):
        self.add_delivery("legacy-a", None)
        self.add_delivery("legacy-b", None)

        history = await get_delivery_history(self.db, 1, 1, 20, None, True)

        self.assertEqual(history["total"], 2)
        self.assertEqual(
            {row["offer_id"] for row in history["items"]}, {"legacy-a", "legacy-b"}
        )

    async def test_filter_uses_effective_expiry_and_handles_empty_pages(self):
        self.add_delivery("stale", "expired-offer", status="queued")
        delivery = self.session.get(PromotionDelivery, "stale")
        delivery.expires_at = self.now - timedelta(hours=1)
        self.session.commit()

        history = await get_delivery_history(self.db, 1, 1, 20, "expired", True)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["status"], "expired")
        self.assertTrue(history["items"][0]["reason_message"])
        empty = await get_delivery_history(self.db, 1, 2, 20, "expired", True)
        self.assertEqual(empty["total"], 1)
        self.assertEqual(empty["items"], [])

    async def test_default_history_keeps_delivery_pagination(self):
        self.add_delivery("a", "same-offer")
        self.add_delivery("b", "same-offer", age=1)

        history = await get_delivery_history(self.db, 1, 1, 1, None)

        self.assertEqual(history["total"], 2)
        self.assertEqual(len(history["items"]), 1)

    async def test_store_filter_applies_to_counts_and_grouped_pages(self):
        self.add_delivery("amazon", "amazon-offer")
        self.add_delivery("shopee", "shopee-offer", status="failed")
        self.session.get(PromotionDelivery, "shopee").platform = "shopee"
        self.session.commit()

        history = await get_delivery_history(self.db, 1, 1, 20, None, True, "shopee")

        self.assertEqual(history["total"], 1)
        self.assertEqual(history["counts"], {"failed": 1})
        self.assertEqual([row["id"] for row in history["items"]], ["shopee"])

    async def test_repeated_product_has_separate_publication_episodes(self):
        self.add_delivery("today-a", "repeated", age=0)
        self.add_delivery("today-b", "repeated", age=2)
        self.add_delivery("earlier", "repeated", age=60)
        self.add_delivery("yesterday", "repeated", age=1440)

        history = await get_delivery_history(self.db, 1, 1, 1, None, True)

        self.assertEqual(history["total"], 3)
        self.assertEqual(history["counts"], {"sent": 4})
        self.assertEqual(
            [row["id"] for row in history["items"]], ["today-a", "today-b"]
        )
        self.assertEqual(len({row["offer_id"] for row in history["items"]}), 1)

    async def test_source_timestamp_keeps_delayed_destinations_together(self):
        self.add_delivery("fast", "delayed", age=30)
        self.add_delivery("slow", "delayed", age=0)
        for identity in ("fast", "slow"):
            self.session.get(PromotionDelivery, identity).source_at = (
                self.now - timedelta(minutes=30)
            )
        self.session.commit()

        history = await get_delivery_history(self.db, 1, 1, 20, None, True)

        self.assertEqual(history["total"], 1)
        self.assertEqual(len(history["items"]), 2)

    async def test_store_filters_match_saved_labels_and_canonical_names(self):
        stores = {
            "amazon": "Amazon",
            "shopee": "Shopee",
            "mercado_livre": "Mercado Livre",
            "aliexpress": "AliExpress",
        }
        for platform, label in stores.items():
            self.add_delivery(f"{platform}-label", f"{platform}-offer")
            self.session.get(PromotionDelivery, f"{platform}-label").platform = label
            self.add_delivery(
                f"{platform}-canonical", f"{platform}-offer", status="failed"
            )
            self.session.get(
                PromotionDelivery, f"{platform}-canonical"
            ).platform = platform
            self.add_delivery(f"{platform}-foreign", f"{platform}-offer", user_id=2)
            self.session.get(PromotionDelivery, f"{platform}-foreign").platform = label
        self.session.commit()

        for platform in stores:
            with self.subTest(platform=platform):
                grouped = await get_delivery_history(
                    self.db, 1, 1, 20, "failed", True, platform
                )
                self.assertEqual(grouped["total"], 1)
                self.assertEqual(grouped["counts"], {"sent": 1, "failed": 1})
                self.assertEqual(
                    {row["id"] for row in grouped["items"]},
                    {f"{platform}-label", f"{platform}-canonical"},
                )
                ungrouped = await get_delivery_history(
                    self.db, 1, 1, 20, None, False, platform
                )
                self.assertEqual(ungrouped["total"], 2)
                self.assertEqual(len(ungrouped["items"]), 2)

    async def test_search_matches_all_words_and_pages_complete_owned_offers(self):
        rows = [
            ("a-sent", "a", "Samsung Galaxy A55 128GB", "sent", 1, 1),
            ("a-failed", "a", None, "failed", 1, 2),
            ("b", "b", "Galaxy S24 128GB", "sent", 1, 3),
            ("different-capacity", "c", "Samsung Galaxy 256GB", "sent", 1, 0),
            ("different-product", "d", "iPhone 128GB", "sent", 1, 0),
            ("foreign", "a", "Galaxy 128GB", "sent", 2, 0),
        ]
        for identity, key, title, status, user_id, age in rows:
            self.add_delivery(identity, key, status, user_id, age)
            self.session.get(PromotionDelivery, identity).title = title
        self.session.commit()

        first = await get_delivery_history(
            self.db, 1, 1, 1, None, True, search="  gALAxY   128  "
        )
        second = await get_delivery_history(
            self.db, 1, 2, 1, None, True, search="galaxy 128"
        )

        self.assertEqual(first["total"], 2)
        self.assertEqual(first["counts"], {"sent": 2, "failed": 1})
        self.assertEqual({row["id"] for row in first["items"]}, {"a-sent", "a-failed"})
        self.assertEqual([row["id"] for row in second["items"]], ["b"])

    async def test_search_combines_with_store_and_status_filters(self):
        for identity, title, platform, status in [
            ("match", "Monitor LG 27", "Amazon", "failed"),
            ("other-store", "Monitor LG 27", "Shopee", "failed"),
            ("other-product", "Notebook LG", "Amazon", "failed"),
            ("other-status", "Monitor LG 27", "Amazon", "sent"),
        ]:
            self.add_delivery(identity, identity, status=status)
            delivery = self.session.get(PromotionDelivery, identity)
            delivery.title = title
            delivery.platform = platform
        self.session.commit()

        history = await get_delivery_history(
            self.db, 1, 1, 20, "failed", True, "amazon", "monitor 27"
        )

        self.assertEqual(history["total"], 1)
        self.assertEqual([row["id"] for row in history["items"]], ["match"])
        self.assertEqual(history["counts"], {"failed": 1, "sent": 1})

    async def test_search_treats_sql_wildcards_as_literal_product_text(self):
        self.add_delivery("literal", "literal")
        self.add_delivery("wildcard", "wildcard")
        self.session.get(PromotionDelivery, "literal").title = "100% Whey_pro / Special"
        self.session.get(PromotionDelivery, "wildcard").title = "1000 WheyXpro"
        self.session.commit()

        for search in ("100%", "Whey_pro", "/"):
            with self.subTest(search=search):
                history = await get_delivery_history(
                    self.db, 1, 1, 20, None, True, search=search
                )
                self.assertEqual(history["total"], 1)
                self.assertEqual([row["id"] for row in history["items"]], ["literal"])

    async def test_search_keeps_repeated_product_episodes_separate(self):
        self.add_delivery("old", "repeated", age=1440)
        self.add_delivery("new", "repeated")
        self.session.get(PromotionDelivery, "old").title = "Galaxy 128GB"
        self.session.get(PromotionDelivery, "new").title = "Galaxy 256GB"
        self.session.commit()

        history = await get_delivery_history(
            self.db, 1, 1, 20, None, True, search="128GB"
        )

        self.assertEqual(history["total"], 1)
        self.assertEqual([row["id"] for row in history["items"]], ["old"])

    async def test_blank_search_clears_filter_and_missing_search_returns_empty(self):
        self.add_delivery("product", "offer")
        for search, expected in ((" \t ", 1), ("not-in-history", 0)):
            with self.subTest(search=search):
                for grouped in (True, False):
                    history = await get_delivery_history(
                        self.db, 1, 1, 20, None, grouped, search=search
                    )
                    self.assertEqual(history["total"], expected)
                    self.assertEqual(len(history["items"]), expected)
