"""Select unusually good offers from one sent channel and optionally post to X."""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from functools import partial
from hashlib import sha256
import logging
import os
import re
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

import httpx
import requests

from backend.app.core.credentials import decrypt_config
from backend.worker.buffer_publisher import BufferPublisher
from backend.worker.poster import BotPoster, BotPosterError
from offers_bot.postgres_store import connect

LOGGER = logging.getLogger(__name__)
BRAZIL = ZoneInfo("America/Sao_Paulo")
POLL_SECONDS = 60
ENDPOINT = "https://api.x.com/2/tweets"
PRICE = re.compile(
    r"R\$\s*((?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]{1,7})(?:,[0-9]{2})?)(?:\s+(?:no|via)\s+(Pix))?",
    re.I,
)


@dataclass(frozen=True)
class Settings:
    user_id: int
    chat_id: str
    landing_url: str
    daily_limit: int = 1

    @classmethod
    def from_env(cls):
        """Read and validate the operator's single approved source channel and URL."""
        try:
            user_id = int(os.getenv("X_OFFERS_USER_ID", ""))
            limit = int(os.getenv("X_OFFERS_DAILY_LIMIT", "1"))
            chat_id = os.getenv("X_OFFERS_CHAT_ID", "").strip()
            landing = os.getenv("X_OFFERS_LANDING_URL", "").strip()
            url = urlsplit(landing)
            if not (user_id > 0 and chat_id and 1 <= limit <= 2):
                raise ValueError
            if (
                url.scheme != "https"
                or not url.hostname
                or "." not in url.hostname
                or url.username is not None
                or not re.fullmatch(r"[!-~]+", landing)
            ):
                raise ValueError
        except ValueError:
            raise ValueError(
                "Check X_OFFERS_USER_ID, CHAT_ID, LANDING_URL and DAILY_LIMIT"
            ) from None
        return cls(user_id, chat_id, landing, limit)


@dataclass(frozen=True)
class Offer:
    delivery_id: str
    title: str
    platform: str
    price: Decimal
    pix: bool
    expires: datetime

    @property
    def key(self) -> str:
        return sha256(
            f"{self.platform.casefold()}\0{self.title.casefold()}".encode()
        ).hexdigest()


def parse_offer(row) -> Offer | None:
    """Accept only standalone, unconditional or explicitly Pix-priced product posts."""
    delivery_id, platform, text, link, expires = row
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if (
        len(lines) != 5
        or lines[2:] != ["🔗 Link do produto:", link, "- Anúncio"]
        or not link
        or not platform
        or not lines[1].startswith("💰 ")
    ):
        return None
    title = " ".join(lines[0].strip("*_`").split())
    if (
        not re.fullmatch(r"[\wÀ-ÿ ,.'’+()/&:–-]{5,160}", title)
        or not title[0].isalnum()
    ):
        return None
    amount = PRICE.fullmatch(lines[1][2:])
    if not amount:
        return None
    price = Decimal(amount[1].replace(".", "").replace(",", "."))
    if price <= 0:
        return None
    return Offer(delivery_id, title, platform, price, bool(amount[2]), expires)


def brl(amount: Decimal) -> str:
    return f"R$ {amount:,.2f}".translate(str.maketrans(",.", ".,"))


def render(offer: Offer, url: str, savings: Decimal | None = None) -> str | None:
    """Lead with the deal and include the bounded history comparison if it fits."""
    payment = " no Pix" if offer.pix else ""
    lead = f"{offer.title}\n{brl(offer.price)}{payment} • {offer.platform}"
    tail = "\n\nMais ofertas no WhatsApp (links de afiliado):\n"
    body = lead + tail

    # Conservative upper bound for X's weighted length; one recognized URL is 23.
    def fits(text):
        return sum(1 if ord(char) < 0x1100 else 2 for char in text) + 23 <= 280

    if savings is not None:
        detail = (
            f"\n{brl(savings)} abaixo do menor preço que vimos de 1 a 30 dias atrás."
        )
        if fits(lead + detail + tail):
            return lead + detail + tail + url
    return body + url if fits(body) else None


def rank(fresh, history, url: str):
    """Rank at least 20% and R$20 below the lowest like-for-like observed price."""
    lowest = {}
    for row in history:
        if offer := parse_offer(row):
            key = offer.key, offer.pix
            lowest[key] = min(lowest.get(key, offer.price), offer.price)
    results = []
    for row in fresh:
        if not (offer := parse_offer(row)):
            continue
        reference = lowest.get((offer.key, offer.pix))
        if reference is None:
            continue
        savings = reference - offer.price
        if savings >= 20 and savings / reference >= Decimal("0.20"):
            if text := render(offer, url, savings):
                results.append(
                    (savings / reference, savings, offer.delivery_id, offer, text)
                )
    unique = {}
    for discount, savings, _, offer, text in sorted(results, reverse=True):
        unique.setdefault(offer.key, (offer, text, discount, savings))
    return list(unique.values())


def candidates(conn, settings: Settings, now: datetime, min_remaining: int = 20):
    """Read only the configured destination's automatic sent deliveries; never replay expired rows."""
    base = """SELECT d.id, d.platform, d.text, d.affiliate_url, d.expires_at, d.title
              FROM promotion_deliveries d
              WHERE d.user_id=%s AND d.chat_id=%s AND d.status='sent'
              AND NOT d.manual AND d.category <> 'coupon' AND d.coupon IS NULL
              AND d.text IS NOT NULL AND d.affiliate_url IS NOT NULL AND d.title IS NOT NULL"""
    scope = (settings.user_id, settings.chat_id)
    fresh = conn.execute(
        base
        + """ AND d.created_at > %s AND d.expires_at > %s AND d.updated_at <= %s
                  AND EXISTS (SELECT 1 FROM destination_channels c
                      WHERE c.user_id=d.user_id AND c.chat_id=d.chat_id AND c.enabled)
                  ORDER BY d.created_at DESC LIMIT 150""",
        (
            *scope,
            now - timedelta(minutes=10),
            now + timedelta(seconds=min_remaining),
            now - timedelta(seconds=45),
        ),
    ).fetchall()
    fresh = [row for row in fresh if parse_offer(row[:5])]
    if not fresh:
        return []
    history = conn.execute(
        base
        + """ AND d.created_at BETWEEN %s AND %s
                  AND d.platform = ANY(%s) AND d.title = ANY(%s)
                  ORDER BY d.created_at DESC LIMIT 3000""",
        (
            *scope,
            now - timedelta(days=30),
            now - timedelta(days=1),
            sorted({row[1] for row in fresh}),
            sorted({row[5] for row in fresh}),
        ),
    ).fetchall()
    return rank(
        (row[:5] for row in fresh), (row[:5] for row in history), settings.landing_url
    )


def reserve(settings: Settings, now: datetime, min_remaining: int = 20):
    """Commit a single-account reservation before publishing or sending a draft."""
    local = now.astimezone(BRAZIL)
    if not 8 <= local.hour < 22:
        return None
    midnight = datetime.combine(local.date(), time.min, BRAZIL)
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (571406195092147,))
        recent = conn.execute(
            "SELECT product_key, attempted_at FROM x_offer_attempts WHERE attempted_at >= %s",
            (now - timedelta(days=7),),
        ).fetchall()
        if sum(stamp >= midnight for _, stamp in recent) >= settings.daily_limit or any(
            stamp > now - timedelta(hours=4) for _, stamp in recent
        ):
            return None
        seen = {key for key, _ in recent}
        for offer, text, _, _ in candidates(conn, settings, now, min_remaining):
            if offer.key in seen:
                continue
            claimed = conn.execute(
                """INSERT INTO x_offer_attempts (delivery_id, product_key, attempted_at, status)
                   VALUES (%s, %s, %s, 'reserved') ON CONFLICT DO NOTHING RETURNING delivery_id""",
                (offer.delivery_id, offer.key, now),
            ).fetchone()
            if claimed:
                return offer, text
    return None


def publish(text: str, auth) -> tuple[str, str | None]:
    """Make one signed X request; never retry ambiguous responses or log response bodies."""
    try:
        response = requests.post(
            ENDPOINT,
            json={"text": text},
            auth=auth,
            timeout=(3, 10),
            allow_redirects=False,
        )
    except requests.RequestException:
        return "uncertain", None
    if response.status_code == 201:
        try:
            post_id = response.json()["data"]["id"]
            if isinstance(post_id, str) and re.fullmatch(r"[0-9]{1,19}", post_id):
                return "sent", post_id
        except (ValueError, KeyError, TypeError):
            pass
    if 400 <= response.status_code < 500:
        LOGGER.warning("X rejected post: HTTP %s", response.status_code)
        return "rejected", None
    return "uncertain", None


def record_attempt(offer: Offer, status: str, post_id: str | None = None):
    """Record the outcome without storing the draft text or secrets."""
    with connect() as conn:
        conn.execute(
            "UPDATE x_offer_attempts SET status=%s, post_id=%s WHERE delivery_id=%s",
            (status, post_id, offer.delivery_id),
        )
    LOGGER.info(
        "X offer delivery=%s status=%s post_id=%s", offer.delivery_id, status, post_id
    )


def publish_once(settings: Settings, auth):
    """Send a fresh reserved offer, then record the outcome without replay on crash."""
    reserved = reserve(settings, datetime.now(timezone.utc))
    if not reserved:
        return
    offer, text = reserved
    if offer.expires > datetime.now(timezone.utc) + timedelta(seconds=15):
        status, post_id = publish(text, auth)
    else:
        status, post_id = "expired", None
    record_attempt(offer, status, post_id)


def buffer_once(settings: Settings, publisher: BufferPublisher):
    """Submit one reserved, fresh deal through Buffer with no automatic retry."""
    reserved = reserve(settings, datetime.now(timezone.utc), 60)
    if reserved:
        offer, text = reserved
        record_attempt(offer, publisher.publish(text, offer.expires))


def dashboard_buffer_once():
    """Reload enabled settings and an active destination before each polling attempt."""
    with connect() as conn:
        row = conn.execute(
            """SELECT d.user_id, d.chat_id, x.landing_url, x.daily_limit,
                      x.channel_id, x.encrypted_key
               FROM x_buffer_settings x
               JOIN destination_channels d ON d.id=x.destination_id AND d.enabled
               WHERE x.id=1 AND x.enabled"""
        ).fetchone()
    if row:
        user_id, chat_id, landing_url, limit, channel_id, secret = row
        settings = Settings(user_id, chat_id, landing_url, limit)
        publisher = BufferPublisher(decrypt_config(secret, 1, "x_buffer"), channel_id)
        buffer_once(settings, publisher)


def browser_once(settings: Settings, browser_settings) -> bool:
    """Publish one reserved offer via X's composer; request a pause if blocked or uncertain."""
    from backend.worker.x_browser import publish_with_browser

    reserved = reserve(settings, datetime.now(timezone.utc), 45)
    if not reserved:
        return False
    offer, text = reserved
    if offer.expires <= datetime.now(timezone.utc) + timedelta(seconds=20):
        record_attempt(offer, "expired")
        return False
    status, post_id = publish_with_browser(browser_settings, text, offer.expires)
    try:
        record_attempt(offer, status, post_id)
    except Exception as exc:
        LOGGER.error("X browser outcome could not be recorded: %s", type(exc).__name__)
        return True
    return status in ("browser_blocked", "browser_uncertain")


def composer_url(text: str) -> str:
    return "https://x.com/intent/tweet?" + urlencode({"text": text})


async def notify_draft_once(settings: Settings, recipient: str, poster: BotPoster):
    """Send a private review prompt with time to act; make no X API calls."""
    reserved = await asyncio.to_thread(
        reserve, settings, datetime.now(timezone.utc), 90
    )
    if not reserved:
        return
    offer, text = reserved
    status = "expired"
    if offer.expires > datetime.now(timezone.utc) + timedelta(seconds=60):
        deadline = offer.expires.astimezone(BRAZIL).strftime("%d/%m às %H:%M:%S")
        message = (
            f"Rascunho para o X • {deadline} (horário de Brasília)\n"
            "Confira preço e estoque antes de publicar. Ignore se já passou do horário.\n\n"
            f"{text}"
        )
        try:
            await poster.send_offer(
                recipient,
                message,
                request_timeout=10,
                disable_link_preview=True,
                reply_markup={
                    "inline_keyboard": [
                        [{"text": "Revisar no X", "url": composer_url(text)}]
                    ]
                },
            )
            status = "draft_sent"
        except BotPosterError as exc:
            status = (
                "draft_rejected"
                if exc.status_code and 400 <= exc.status_code < 500
                else "draft_uncertain"
            )
        except httpx.HTTPError:
            status = "draft_uncertain"
    await asyncio.to_thread(record_attempt, offer, status)


def configure_action(mode: str, settings: Settings):
    """Prepare only the credentials and send action needed by the chosen mode."""
    if mode == "buffer":
        return partial(
            asyncio.to_thread, buffer_once, settings, BufferPublisher.from_env()
        )
    if mode == "draft":
        recipient = os.getenv("X_OFFERS_DRAFT_TELEGRAM_CHAT_ID", "").strip()
        if not re.fullmatch(r"[1-9][0-9]{0,15}", recipient):
            raise ValueError(
                "X_OFFERS_DRAFT_TELEGRAM_CHAT_ID must be a private Telegram user ID"
            )
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required for draft mode")
        return partial(notify_draft_once, settings, recipient, BotPoster(token))
    if mode == "auto":
        credentials = [
            os.getenv(f"X_OFFERS_{name}", "").strip()
            for name in ("API_KEY", "API_SECRET", "ACCESS_TOKEN", "ACCESS_SECRET")
        ]
        if not all(credentials):
            raise ValueError("X Offers requires all four OAuth 1.0a credentials")
        from requests_oauthlib import OAuth1

        return partial(asyncio.to_thread, publish_once, settings, OAuth1(*credentials))
    if mode == "browser":
        from backend.worker.x_browser import BrowserSettings

        browser_settings = BrowserSettings.from_env()
        browser_settings.check_state()
        return partial(asyncio.to_thread, browser_once, settings, browser_settings)
    raise ValueError("X_OFFERS_MODE must be off, buffer, draft, auto, or browser")


async def x_offers_loop():
    """Opt-in publisher; configuration errors leave ingestion and other channels running."""
    mode = os.getenv("X_OFFERS_MODE", "dashboard")
    if mode == "off":
        return
    try:
        action = (
            partial(asyncio.to_thread, dashboard_buffer_once)
            if mode == "dashboard"
            else configure_action(mode, Settings.from_env())
        )
    except (ValueError, ImportError, OSError) as exc:
        LOGGER.error("X Offers disabled: %s", exc)
        return
    while True:
        try:
            if await action():
                LOGGER.warning(
                    "X browser publishing paused; verify the session and X timeline, then restart the worker"
                )
                return
        except Exception as exc:
            LOGGER.error("X Offers poll failed: %s", type(exc).__name__)
        await asyncio.sleep(POLL_SECONDS)


def main():
    """Print one ranked draft and composer link; never publish or write audit state."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.parse_args()
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        parser.error(str(exc))
    with connect() as conn:
        ranked = candidates(conn, settings, datetime.now(timezone.utc))
    if not ranked:
        print("Nenhuma oferta recente atingiu os critérios.")
        return
    offer, text, discount, savings = ranked[0]
    print(
        f"Entrega {offer.delivery_id} | {discount:.0%} abaixo do histórico | economia: R$ {savings:.2f}"
    )
    print(text)
    print("\nAbrir rascunho no X: " + composer_url(text))


if __name__ == "__main__":
    main()
