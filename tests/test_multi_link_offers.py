import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from backend.worker.manager import UserBotInstance
from backend.worker.posting_queue import QueuePoster
from offers_bot.main import format_outgoing_offer
from offers_bot.parser import PLATFORM_AMAZON, _extract_offers


class MultiLinkOfferTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_queues_one_whatsapp_delivery_for_three_links(self):
        links = [f"https://s.shopee.com.br/coupon{i}" for i in range(1, 4)]
        source = "Cupons Shopee\n\nResgate aqui:\n" + "\n".join(links)
        poster = QueuePoster(1)
        poster.send_offer = AsyncMock()
        bot = UserBotInstance(1, MagicMock(), poster=poster)
        bot._source_chats = ("source",)
        bot._destination_chat_ids = ("whatsapp",)
        bot._shopee = Mock()
        bot._shopee.create_link.side_effect = lambda url: SimpleNamespace(
            short_url=url.replace("coupon", "affiliate"),
            product_key=url,
            image_url=None,
        )
        store = AsyncMock()
        store.seen.return_value = False
        with (
            patch("backend.worker.manager.PgOfferStore", return_value=store),
            patch(
                "offers_bot.parser.parse_with_llm_async", AsyncMock(return_value=None)
            ),
        ):
            await bot.process_message("source", 1, source)

        poster.send_offer.assert_awaited_once_with(
            "whatsapp",
            source.replace("coupon", "affiliate") + "\n\n- Anúncio",
            image_file=None,
            parse_mode="Markdown",
        )
        store.mark.assert_awaited_once()

    async def test_shopee_bulletin_keeps_three_redemption_links_in_one_post(self):
        links = [f"https://s.shopee.com.br/original{i}" for i in range(1, 4)]
        source = "Cupons Shopee\n\n-Resgate aqui:\n" + "\n".join(
            f"{i} {link}" for i, link in enumerate(links, 1)
        )
        misleading_llm_result = {
            "classification": "coupon",
            "coupon": {
                "platform": "Shopee",
                "coupons": [{"detail": "Resgate aqui", "code": "Resgate aqui"}],
            },
        }
        client = Mock()
        client.create_link.side_effect = lambda url: SimpleNamespace(
            short_url=url.replace("original", "affiliate")
        )

        for result in (None, misleading_llm_result):
            with self.subTest(llm=bool(result)):
                offers = _extract_offers(source, result)
                self.assertEqual(len(offers), 1)
                self.assertEqual(offers[0].all_urls, tuple(links))
                post = await format_outgoing_offer(
                    offers[0],
                    links[0].replace("original", "affiliate"),
                    affiliate_client=client,
                )
                self.assertEqual(
                    post,
                    source.replace("-Resgate", "Resgate").replace(
                        "original", "affiliate"
                    )
                    + "\n\n- Anúncio",
                )

    async def test_mixed_links_use_their_own_affiliate_provider(self):
        shopee = "https://s.shopee.com.br/example"
        amazon = "https://amzn.to/example"
        (offer,) = _extract_offers(
            f"Ofertas\nShopee: {shopee}\nAmazon: {amazon}.", None
        )
        shopee_client = Mock()
        amazon_client = Mock()
        amazon_client.create_link.return_value = SimpleNamespace(
            short_url="https://amzn.to/affiliate"
        )

        post = await format_outgoing_offer(
            offer,
            "https://s.shopee.com.br/affiliate",
            affiliate_client=shopee_client,
            affiliate_client_for_platform={PLATFORM_AMAZON: amazon_client}.get,
        )

        self.assertIn("Shopee: https://s.shopee.com.br/affiliate", post)
        self.assertIn("Amazon: https://amzn.to/affiliate.", post)
        shopee_client.create_link.assert_not_called()
        amazon_client.create_link.assert_called_once_with(amazon)
