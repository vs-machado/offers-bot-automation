"""Independent collection timing and observable admission constraints."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from backend.app.core.delivery_errors import REASONS
from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, new_connection_policy
from backend.worker.whatsapp_delivery import (
    load_policy,
    next_slot_with_reason,
    reserve_delivery,
)


class QueueLatencyTests(unittest.TestCase):
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    chat = "123@newsletter"

    def test_saved_policies_gain_collection_without_replacing_limits(self):
        for primary in (True, False):
            with self.subTest(primary=primary):
                conn = MagicMock()
                conn.execute.return_value.fetchone.return_value = (
                    '{"account_interval_seconds":42,"burst_window_seconds":120}',
                )
                with patch(
                    "backend.worker.whatsapp_delivery.connection_scope",
                    return_value=(7, primary),
                ):
                    policy = load_policy(conn, 1, 7)
                self.assertEqual(policy.collection_seconds, 10)
                self.assertEqual(policy.burst_window_seconds, 120)
                self.assertEqual(policy.account_interval_seconds, 42)
        policy = new_connection_policy()
        self.assertEqual(policy.collection_seconds, 10)
        self.assertEqual(policy.account_interval_seconds, 30)
        self.assertEqual(policy.account_interval_max_seconds, 90)

    def test_collection_validation_and_round_trip(self):
        policy = WhatsAppPolicy(collection_seconds=20, burst_window_seconds=90)
        self.assertEqual(
            WhatsAppPolicy.model_validate_json(policy.model_dump_json()), policy
        )
        for settings in (
            {"collection_seconds": 4},
            {"collection_seconds": 301},
            {"ttl_seconds": 120, "collection_seconds": 100},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                WhatsAppPolicy(**settings)

    def test_policy_constraints_report_specific_reasons(self):
        cases = (
            (
                WhatsAppPolicy(),
                [("other", self.now)],
                None,
                20,
                "whatsapp_account_spacing",
            ),
            (
                WhatsAppPolicy(),
                [(self.chat, self.now)],
                None,
                45,
                "whatsapp_destination_spacing",
            ),
            (
                WhatsAppPolicy(max_per_hour=1),
                [("other", self.now)],
                None,
                3600,
                "whatsapp_hourly_quota",
            ),
            (
                WhatsAppPolicy(max_per_hour=1, max_per_day=1),
                [("other", self.now)],
                None,
                86400,
                "whatsapp_daily_quota",
            ),
            (
                WhatsAppPolicy(destination_max_per_day=1),
                [],
                [self.now],
                86400,
                "whatsapp_destination_quota",
            ),
            (
                WhatsAppPolicy(start_hour_utc=13),
                [],
                None,
                3600,
                "whatsapp_posting_window",
            ),
        )
        for policy, attempts, destination_attempts, seconds, reason in cases:
            with self.subTest(reason=reason):
                slot, actual_reason = next_slot_with_reason(
                    policy, self.now, attempts, self.chat, destination_attempts
                )
                self.assertEqual(slot, self.now + timedelta(seconds=seconds))
                self.assertEqual(actual_reason, reason)
                self.assertIn(reason, REASONS)

    def reserve(
        self,
        *,
        age=0,
        chat_type="channel",
        policy=None,
        attempts=(),
        pauses=(),
        active=None,
    ):
        conn = MagicMock()
        created = self.now - timedelta(seconds=age)
        expiry = self.now + timedelta(seconds=500)

        def execute(query, params=None):
            result = MagicMock()
            if query.startswith("SELECT connection_id FROM destination_channels"):
                result.fetchone.return_value = (7,)
            elif query.startswith("SELECT status,source_at"):
                result.fetchone.return_value = ("queued", created, created, expiry, 7)
            elif query.startswith("SELECT chat_type"):
                result.fetchone.return_value = (chat_type, 7)
            elif query.startswith("SELECT status FROM promotion_deliveries"):
                result.fetchone.return_value = ("queued",)
            elif query.startswith("SELECT paused_until"):
                result.fetchall.return_value = [(at,) for at in pauses]
            elif query.startswith("SELECT chat_id,attempted_at"):
                result.fetchall.return_value = list(attempts)
            elif query.startswith("SELECT attempted_at"):
                result.fetchall.return_value = []
            elif query.startswith("SELECT max(updated_at)"):
                result.fetchone.return_value = (active,)
            return result

        conn.execute.side_effect = execute
        with (
            patch("backend.worker.whatsapp_delivery.connect") as connect,
            patch(
                "backend.worker.whatsapp_delivery.connection_scope",
                return_value=(7, False),
            ),
            patch("backend.worker.whatsapp_delivery.lock_account"),
            patch(
                "backend.worker.whatsapp_delivery.load_policy",
                return_value=policy or WhatsAppPolicy(),
            ),
            patch("backend.worker.whatsapp_delivery.trim_burst") as trim,
            patch("backend.worker.whatsapp_delivery.datetime", wraps=datetime) as clock,
            patch("backend.worker.whatsapp_delivery.LOGGER") as logger,
        ):
            connect.return_value.__enter__.return_value = conn
            clock.now.return_value = self.now
            action = reserve_delivery("offer", 1, self.chat, expiry.timestamp())
        updates = [
            call.args[1][0]
            for call in conn.execute.call_args_list
            if call.args[0].startswith("UPDATE promotion_deliveries SET reason=")
        ]
        return action, updates, trim, logger, conn

    def test_channel_waits_ten_seconds_independent_of_burst_detection(self):
        policy = WhatsAppPolicy(burst_window_seconds=120)
        action, reasons, trim, logger, conn = self.reserve(policy=policy)
        self.assertEqual(action, ("wait", 10))
        self.assertEqual(reasons, ["whatsapp_collection"])
        self.assertEqual(trim.call_args.args[3].burst_window_seconds, 120)
        log = logger.info.call_args.args
        self.assertIn("wait_seconds=%.3f queued_seconds=%.3f", log[0])
        self.assertIn("whatsapp_collection", log)
        self.assertFalse(
            any(
                "INSERT INTO whatsapp_send_attempts" in call.args[0]
                for call in conn.execute.call_args_list
            )
        )

    def test_channel_can_send_after_ten_seconds_while_group_has_no_hold(self):
        for age, chat_type in ((10, "channel"), (11, "channel"), (0, "group")):
            with self.subTest(age=age, chat_type=chat_type):
                action, reasons, trim, logger, _ = self.reserve(
                    age=age, chat_type=chat_type
                )
                self.assertEqual(action, ("send", 0))
                self.assertEqual(reasons, [])
                self.assertEqual(trim.call_count, int(chat_type == "channel"))
                self.assertIn("admitted", logger.info.call_args.args[0])

    def test_recheck_uses_original_queue_entry_instead_of_restarting_collection(self):
        action, reasons, _, _, _ = self.reserve(age=6)
        self.assertEqual(action, ("wait", 4))
        self.assertEqual(reasons, ["whatsapp_collection"])

    def test_random_spacing_pauses_and_active_sends_still_take_precedence(self):
        cases = (
            (
                {"attempts": [("other", self.now, self.now + timedelta(seconds=90))]},
                60,
                "whatsapp_account_spacing",
            ),
            ({"pauses": [self.now + timedelta(seconds=30)]}, 30, "whatsapp_paused"),
            ({"age": 8, "active": self.now}, 5, "whatsapp_in_flight"),
            (
                {"policy": WhatsAppPolicy(collection_seconds=25)},
                25,
                "whatsapp_collection",
            ),
        )
        for settings, seconds, reason in cases:
            with self.subTest(reason=reason):
                action, reasons, _, _, _ = self.reserve(**settings)
                self.assertEqual(action, ("wait", seconds))
                self.assertEqual(reasons, [reason])

    def test_quota_beyond_deadline_logs_blocker_and_expires(self):
        action, _, _, logger, conn = self.reserve(
            policy=WhatsAppPolicy(max_per_hour=1),
            attempts=[("other", self.now, None)],
        )
        self.assertEqual(action, ("stop", 0))
        self.assertIn("whatsapp_hourly_quota", logger.info.call_args.args)
        self.assertTrue(
            any(
                "reason='policy_deadline'" in call.args[0]
                for call in conn.execute.call_args_list
            )
        )
