from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from importlib import import_module
import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from alembic.migration import MigrationContext
from alembic.operations import Operations
import httpx
import requests
from sqlalchemy import create_engine, inspect

from backend.worker import x_offers


NOW = datetime(2026, 11, 24, 15, tzinfo=timezone.utc)
LANDING = "https://ofertas.example.com/?utm_source=x"
LINK = "https://store.example.com/item"


def deal(identity, amount, title="Cafeteira de Inox", suffix=""):
    return (
        identity,
        "Amazon",
        f"{title}\n\n💰 R$ {amount}{suffix}\n\n🔗 Link do produto:\n{LINK}\n\n- Anúncio",
        LINK,
        NOW + timedelta(minutes=3),
    )


class XOfferTests(unittest.TestCase):
    def test_fresh_selection_does_not_need_history_or_promote_miscellaneous_items(self):
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [
            deal("random", "8,99", "Pacote de adesivos decorativos"),
            deal("accessory", "29,90", "Capa para Smartphone Galaxy"),
            deal("replacement", "45,00", "Cafeteira Filtro de Reposição"),
            deal("first", "299,00", "Cafeteira de Inox", suffix=" no Pix"),
            deal("repeat", "300,00", "Cafeteira de Inox", suffix=" no Pix"),
        ]
        [(offer, text)] = x_offers.candidates(
            conn, x_offers.Settings(1, "chosen", LANDING), NOW
        )
        self.assertEqual(offer.delivery_id, "first")
        self.assertIn("R$ 299,00 no Pix", text)
        self.assertNotIn("menor preço", text)
        conn.execute.assert_called_once()

    def test_ranks_against_lowest_matching_price_and_omits_repeats(self):
        fresh = [
            deal("new", "20,00", "Produto sem histórico"),
            deal("weak", "100,00", "Secador"),
            deal("first", "999,90", suffix=" no Pix"),
            deal("second", "1.100,00", suffix=" no Pix"),
        ]
        history = [
            deal("old1", "300,00", "Secador"),
            deal("old2", "110,00", "Secador"),
            deal("old3", "1.300,00", suffix=" via Pix"),
            deal("old4", "1.000,00"),
        ]
        [(offer, text, _, _)] = x_offers.rank(fresh, history, LANDING)
        self.assertEqual(offer.delivery_id, "first")
        self.assertTrue(text.startswith("Cafeteira de Inox\n"))
        self.assertIn("R$ 999,90 no Pix", text)
        self.assertIn(
            "R$ 300,10 abaixo do menor preço que vimos de 1 a 30 dias atrás.", text
        )
        self.assertIn("links de afiliado", text)
        self.assertTrue(text.endswith(LANDING))
        self.assertNotIn(LINK, text)

    def test_drops_uncomparable_terms_and_conditional_prices(self):
        for suffix in (" com cupom", "\nExclusivo Prime", "\nFrete grátis"):
            with self.subTest(suffix=suffix):
                self.assertIsNone(
                    x_offers.parse_offer(deal("deceptive", "90,00", suffix=suffix))
                )
        self.assertEqual(
            x_offers.rank(
                [deal("new", "75,00", suffix=" no Pix")],
                [deal("old", "150,00")],
                LANDING,
            ),
            [],
        )

    @patch.object(x_offers.requests, "post")
    def test_write_uses_official_endpoint_once_and_never_retries_timeout(self, post):
        post.side_effect = requests.ReadTimeout()
        self.assertEqual(x_offers.publish("copy", "auth"), ("uncertain", None))
        post.assert_called_once_with(
            "https://api.x.com/2/tweets",
            json={"text": "copy"},
            auth="auth",
            timeout=(3, 10),
            allow_redirects=False,
        )

    @patch.object(x_offers.requests, "post", return_value=Mock(status_code=201))
    def test_success_returns_post_id(self, post):
        post.return_value.json.return_value = {"data": {"id": "12345"}}
        self.assertEqual(x_offers.publish("copy", "auth"), ("sent", "12345"))
        post.return_value.json.return_value = {"data": None}
        self.assertEqual(x_offers.publish("copy", "auth"), ("uncertain", None))

    def test_migration_upgrade_and_downgrade(self):
        migration = import_module("backend.alembic.versions.0026_x_offer_attempts")
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with (
            engine.begin() as conn,
            Operations.context(MigrationContext.configure(conn)),
        ):
            migration.upgrade()
            self.assertEqual(
                inspect(conn).get_pk_constraint("x_offer_attempts")[
                    "constrained_columns"
                ],
                ["delivery_id"],
            )
            migration.downgrade()
            self.assertFalse(inspect(conn).has_table("x_offer_attempts"))


class XOfferDraftTests(unittest.IsolatedAsyncioTestCase):
    @patch.object(x_offers.requests, "post")
    @patch.object(x_offers, "record_attempt")
    @patch.object(x_offers, "reserve")
    async def test_draft_sends_private_review_button_without_calling_x(
        self, reserve, record, x_post
    ):
        offer = x_offers.parse_offer(deal("fresh", "100,00"))
        text = x_offers.render(offer, LANDING)
        reserve.return_value = (offer, text)
        received = []

        def telegram(request):
            received.append(request)
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

        settings = x_offers.Settings(1, "chosen", LANDING)
        env = {
            "X_OFFERS_DRAFT_TELEGRAM_CHAT_ID": "42",
            "TELEGRAM_BOT_TOKEN": "mock-token",
        }
        client = httpx.AsyncClient(transport=httpx.MockTransport(telegram))
        with (
            patch.dict(os.environ, env, clear=True),
            patch("backend.worker.poster.httpx.AsyncClient", return_value=client),
            patch.object(x_offers, "datetime", wraps=datetime) as clock,
        ):
            clock.now.return_value = NOW
            await x_offers.configure_action("draft", settings)()

        [request] = received
        self.assertEqual(request.url.host, "api.telegram.org")
        self.assertTrue(request.url.path.endswith("/sendMessage"))
        payload = json.loads(request.content)
        self.assertEqual(payload["chat_id"], "42")
        self.assertIn(text, payload["text"])
        [[button]] = payload["reply_markup"]["inline_keyboard"]
        url = urlsplit(button["url"])
        self.assertEqual((url.netloc, url.path), ("x.com", "/intent/tweet"))
        self.assertEqual(parse_qs(url.query), {"text": [text]})
        record.assert_called_once_with(offer, "draft_sent")
        x_post.assert_not_called()

    def test_group_chat_is_rejected(self):
        with patch.dict(os.environ, {"X_OFFERS_DRAFT_TELEGRAM_CHAT_ID": "-100123"}):
            with self.assertRaisesRegex(ValueError, "private Telegram user ID"):
                x_offers.configure_action(
                    "draft", x_offers.Settings(1, "chosen", LANDING)
                )


@unittest.skipUnless(
    os.getenv("X_OFFERS_TEST_DATABASE_URL"),
    "PostgreSQL integration requires a test URL",
)
class XOfferPostgresTests(unittest.TestCase):
    def test_priority_source_wins_and_other_sources_are_the_fallback(self):
        import psycopg

        preferred = "https://t.me/preferred"
        settings = x_offers.Settings(
            1, "chosen", LANDING, priority_source_url=preferred
        )
        with psycopg.connect(os.environ["X_OFFERS_TEST_DATABASE_URL"]) as conn:
            conn.execute("""CREATE TEMP TABLE promotion_deliveries (
                id text, platform text, text text, affiliate_url text, expires_at timestamptz,
                user_id int DEFAULT 1, chat_id text DEFAULT 'chosen', status text DEFAULT 'sent',
                manual bool DEFAULT false, category text DEFAULT 'home', coupon text,
                created_at timestamptz, updated_at timestamptz, source_group_url text)""")
            conn.execute(
                "CREATE TEMP TABLE destination_channels (user_id int, chat_id text, enabled bool)"
            )
            conn.execute("INSERT INTO destination_channels VALUES (1, 'chosen', true)")
            for identity, title, age, source in (
                ("other", "Smartphone Galaxy", 2, "https://t.me/other"),
                ("priority", "Cafeteira de Inox", 3, preferred),
                ("accessory", "Capa para Smartphone Galaxy", 1, preferred),
            ):
                stamp = NOW - timedelta(minutes=age)
                conn.execute(
                    """INSERT INTO promotion_deliveries
                    (id, platform, text, affiliate_url, expires_at, created_at, updated_at, source_group_url)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (*deal(identity, "100,00", title), stamp, stamp, source),
                )
            self.assertEqual(
                [
                    offer.delivery_id
                    for offer, _ in x_offers.candidates(conn, settings, NOW)
                ],
                ["priority", "other"],
            )
            conn.execute(
                "UPDATE promotion_deliveries SET expires_at=%s WHERE id=%s",
                (NOW, "priority"),
            )
            self.assertEqual(
                [
                    offer.delivery_id
                    for offer, _ in x_offers.candidates(conn, settings, NOW)
                ],
                ["other"],
            )

    def test_sent_scope_freshness_and_durable_spend_limit(self):
        import psycopg

        settings = x_offers.Settings(1, "chosen", LANDING)
        with psycopg.connect(os.environ["X_OFFERS_TEST_DATABASE_URL"]) as conn:
            conn.execute("""CREATE TEMP TABLE promotion_deliveries (
                id text, platform text, text text, affiliate_url text, expires_at timestamptz,
                title text, user_id int, chat_id text, status text, manual bool,
                category text, coupon text, created_at timestamptz, updated_at timestamptz)""")
            conn.execute(
                "CREATE TEMP TABLE destination_channels (user_id int, chat_id text, enabled bool)"
            )
            conn.execute("INSERT INTO destination_channels VALUES (1, 'chosen', true)")
            conn.execute("""CREATE TEMP TABLE x_offer_attempts (
                delivery_id text PRIMARY KEY, product_key text, attempted_at timestamptz,
                status text, post_id text)""")

            def add(
                identity,
                price,
                created,
                expires=None,
                user=1,
                chat="chosen",
                manual=False,
                status="sent",
            ):
                values = deal(identity, price)
                conn.execute(
                    "INSERT INTO promotion_deliveries VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'home',null,%s,%s)",
                    (
                        *values[:4],
                        expires or values[4],
                        "Cafeteira de Inox",
                        user,
                        chat,
                        status,
                        manual,
                        created,
                        created,
                    ),
                )

            add("history", "300,00", NOW - timedelta(days=2))
            past = NOW - timedelta(minutes=2)
            add("valid", "100,00", past)
            add("expired", "1,00", past, expires=NOW)
            add("pending", "1,00", past, status="queued")
            add("other-user", "1,00", past, user=2)
            add("other-chat", "1,00", past, chat="other")
            add("manual", "1,00", past, manual=True)

            @contextmanager
            def connection():
                with conn.transaction():
                    yield conn

            with patch.object(x_offers, "connect", connection):
                self.assertEqual(
                    x_offers.reserve(settings, NOW)[0].delivery_id, "valid"
                )
                self.assertIsNone(x_offers.reserve(settings, NOW))
                self.assertEqual(
                    conn.execute(
                        "SELECT delivery_id, status FROM x_offer_attempts"
                    ).fetchall(),
                    [("valid", "reserved")],
                )
