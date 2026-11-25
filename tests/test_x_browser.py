from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock

from playwright.sync_api import TimeoutError

from backend.worker import x_browser


class BrowserPublishingTests(unittest.TestCase):
    def setUp(self):
        self.text = "Achado do dia:\nCafeteira • R$ 100,00"
        self.page = Mock(url=x_browser.COMPOSE)
        self.account = Mock()
        self.account.inner_text.return_value = "VSM Ofertas\n@vsmofertas"
        self.editor = Mock()
        self.editor.inner_text.side_effect = ["", self.text]
        self.button = Mock()
        self.toast = Mock()
        self.toast.get_attribute.return_value = "/vsmofertas/status/12345"
        self.page.locator.side_effect = lambda selector: {
            x_browser.ACCOUNT: self.account,
            x_browser.EDITOR: self.editor,
            x_browser.SUBMIT: self.button,
            '[data-testid="toast"] a[href*="/status/"]': self.toast,
        }[selector]

    def submit(self, remaining=60):
        return x_browser.submit_offer(
            self.page,
            "vsmofertas",
            self.text,
            datetime.now(timezone.utc) + timedelta(seconds=remaining),
        )

    def live_clicks(self):
        return [
            call
            for call in self.button.click.call_args_list
            if not call.kwargs.get("trial")
        ]

    def test_only_one_click_and_status_link_confirms_post(self):
        self.assertEqual(self.submit(), ("sent", "12345"))
        self.assertEqual(len(self.live_clicks()), 1)

    def test_display_name_cannot_override_wrong_signed_in_handle(self):
        self.account.inner_text.return_value = "@vsmofertas\n@otheraccount"
        self.assertEqual(self.submit(), ("browser_blocked", None))
        self.editor.fill.assert_not_called()
        self.button.click.assert_not_called()

    def test_uncertain_submission_never_clicks_again(self):
        self.toast.get_attribute.side_effect = TimeoutError("no confirmation")
        self.assertEqual(self.submit(), ("browser_uncertain", None))
        self.assertEqual(len(self.live_clicks()), 1)

    def test_expired_offer_does_not_submit(self):
        self.assertEqual(self.submit(remaining=0), ("expired", None))
        self.assertEqual(self.live_clicks(), [])
