from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

import httpx

from backend.worker.buffer_publisher import BufferPublisher


def response(data):
    result = Mock()
    result.json.return_value = {"data": data}
    return result


class BufferPublisherTests(unittest.TestCase):
    def setUp(self):
        self.publisher = BufferPublisher("secret", "vsm-channel")
        self.expires = datetime.now(timezone.utc) + timedelta(minutes=2)
        self.channel = {
            "id": "vsm-channel",
            "service": "twitter",
            "isLocked": False,
            "isDisconnected": False,
            "isQueuePaused": False,
        }

    @patch("backend.worker.buffer_publisher.httpx.post")
    def test_share_now_attaches_the_product_image(self, post):
        post.side_effect = [
            response({"channel": self.channel}),
            response(
                {
                    "createPost": {
                        "__typename": "PostActionSuccess",
                        "post": {"id": "receipt-1", "status": "sent"},
                    }
                }
            ),
        ]
        caption = "iPhone 16e\n\n💰 R$ 2.969,00\n\n🔗 Link do produto:\nhttps://amzn.to/deal\n\n- Anúncio"
        photo = "https://cdn.example.com/offer.jpg"
        status = self.publisher.publish(caption, self.expires, image_url=photo)

        self.assertEqual(status, "buffer_sent")
        payload = post.call_args.kwargs["json"]["variables"]["input"]
        self.assertEqual(payload["text"], caption)
        self.assertEqual(payload["assets"], [{"image": {"url": photo}}])

    @patch("backend.worker.buffer_publisher.httpx.post")
    def test_share_now_acceptance_is_not_reported_as_published(self, post):
        post.side_effect = [
            response({"channel": self.channel}),
            response(
                {
                    "createPost": {
                        "__typename": "PostActionSuccess",
                        "post": {"id": "receipt-1", "status": "sending"},
                    }
                }
            ),
        ]
        copy = "Oferta: R$ 99,90\nhttps://vsm.example/ofertas"
        self.assertEqual(self.publisher.publish(copy, self.expires), "buffer_accepted")
        preflight, mutation = post.call_args_list
        self.assertEqual(preflight.kwargs["json"]["variables"], {"id": "vsm-channel"})
        self.assertEqual(mutation.args, ("https://api.buffer.com",))
        self.assertEqual(
            mutation.kwargs["json"]["variables"]["input"],
            {
                "channelId": "vsm-channel",
                "text": copy,
                "schedulingType": "automatic",
                "mode": "shareNow",
            },
        )

    @patch("backend.worker.buffer_publisher.httpx.post")
    def test_wrong_platform_never_gets_a_write(self, post):
        post.return_value = response(
            {"channel": {**self.channel, "service": "linkedin"}}
        )
        self.assertEqual(
            self.publisher.publish("offer", self.expires), "buffer_blocked"
        )
        post.assert_called_once()

    @patch("backend.worker.buffer_publisher.httpx.post")
    def test_uncertain_write_is_not_retried(self, post):
        post.side_effect = [
            response({"channel": self.channel}),
            httpx.ReadTimeout("timed out"),
        ]
        self.assertEqual(
            self.publisher.publish("offer", self.expires), "buffer_uncertain"
        )
        self.assertEqual(post.call_count, 2)
