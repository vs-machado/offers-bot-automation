import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.worker.manager import UserBotInstance
from backend.worker.posting_queue import QueuePoster


class ShopeeSourceImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_source_photo_reaches_queue_for_live_and_product_offers(self):
        source_photo = "/tmp/source-photo.jpg"
        product_photo = "https://cf.shopee.com.br/file/product-photo"
        for source_image, affiliate_image, expected in (
            (source_photo, None, source_photo),
            (source_photo, product_photo, source_photo),
            (None, product_photo, product_photo),
        ):
            with self.subTest(source=source_image, affiliate=affiliate_image):
                poster = QueuePoster(42)
                poster.send_offer = AsyncMock()
                bot = UserBotInstance(42, MagicMock(), poster=poster)
                bot._source_chats = ("source",)
                bot._destination_chat_ids = ("telegram", "whatsapp")
                bot._shopee = MagicMock()
                bot._shopee.create_link.return_value = SimpleNamespace(
                    short_url="https://s.shopee.com.br/affiliate",
                    product_key="SHOPEE:CUSTOM:live",
                    image_url=affiliate_image,
                )
                store = AsyncMock()
                store.seen.return_value = False
                offer = SimpleNamespace(
                    title="Mini System LG XBOOM",
                    platform="shopee",
                    url="https://s.shopee.com.br/live",
                    price="640",
                    card_price=None,
                    coupon=None,
                    llm_result=None,
                )
                with (
                    patch(
                        "backend.worker.manager.extract_offers_async",
                        new=AsyncMock(return_value=[offer]),
                    ),
                    patch("backend.worker.manager.PgOfferStore", return_value=store),
                    patch(
                        "backend.worker.manager.format_outgoing_offer",
                        new=AsyncMock(return_value="Formatted offer"),
                    ),
                ):
                    await bot.process_message(
                        "source", 123, "Offer", source_image_url=source_image
                    )
                self.assertEqual(poster.send_offer.await_count, 2)
                for destination in bot._destination_chat_ids:
                    poster.send_offer.assert_any_await(
                        destination,
                        "Formatted offer",
                        image_file=expected,
                        parse_mode="Markdown",
                    )
                store.mark.assert_awaited_once()
