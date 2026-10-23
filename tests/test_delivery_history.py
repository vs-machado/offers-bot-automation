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
