"""Bounded delivery queue with per-destination state and conservative retries."""

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import tempfile
import time

import httpx
from celery.signals import task_revoked

from backend.worker.celery_app import app
from backend.worker.poster import BotPoster, BotPosterError
from offers_bot.message_context import source_timestamp
from offers_bot.postgres_store import connect

LOGGER = logging.getLogger(__name__)


class PromotionExpired(Exception):
    """The absolute source deadline passed before an HTTP send began."""


@task_revoked.connect
def record_expiration(request=None, expired=False, **kwargs):
    """Record broker-side expiration without replaying the promotion."""
    if expired and request and request.name == "promotions.post":
        try:
            update_status(request.id, "expired")
        except Exception:
            LOGGER.warning("Could not record expiration for promotion %s", request.id)


def promotion_ttl() -> int:
    """Return operator-configured validity; reject unsafe configuration."""
    value = int(os.getenv("PROMOTION_TTL_SECONDS", "180"))
    if not 1 <= value <= 3600:
        raise ValueError("PROMOTION_TTL_SECONDS must be between 1 and 3600")
    return value


def update_status(identity: str, status: str, reason: str | None = None) -> None:
    """Record a delivery outcome without storing credentials or response bodies."""
    with connect() as conn:
        conn.execute(
            "UPDATE promotion_deliveries SET status=%s, reason=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
            (status, reason, identity),
        )


class QueuePoster:
    """Queue prepared offers; copy local media before ingestion removes it."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def send_offer(
        self,
        chat_id: str,
        text: str,
        image_file: str | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        """Publish one destination task without blocking the event loop."""
        deadline = (source_timestamp.get() or time.time()) + promotion_ttl()
        return await asyncio.to_thread(
            self._publish, chat_id, text, image_file, parse_mode, deadline
        )

    def _publish(
        self,
        chat_id: str,
        text: str,
        image_file: str | None,
        parse_mode: str | None,
        deadline: float,
    ) -> dict:
        if time.time() >= deadline:
            LOGGER.info("Discarded expired promotion for user %s", self.user_id)
            return {"status": "expired"}
        identity = hashlib.sha256(
            f"{self.user_id}\0{chat_id}\0{text}\0{source_timestamp.get()}".encode()
        ).hexdigest()
        image_data = None
        image_url = None
        if image_file:
            if image_file.startswith(("https://", "http://")):
                image_url = image_file
            elif Path(image_file).stat().st_size <= 8 * 1024 * 1024:
                image_data = base64.b64encode(Path(image_file).read_bytes()).decode(
                    "ascii"
                )
            else:
                LOGGER.warning(
                    "Oversized promotion image omitted for user %s", self.user_id
                )
        with connect() as conn:
            inserted = conn.execute(
                """INSERT INTO promotion_deliveries (id, user_id, chat_id, status, expires_at)
                VALUES (%s, %s, %s, 'queued', %s) ON CONFLICT (id) DO NOTHING RETURNING id""",
                (
                    identity,
                    self.user_id,
                    chat_id,
                    datetime.fromtimestamp(deadline, timezone.utc),
                ),
            ).fetchone()
        if not inserted:
            return {"status": "duplicate"}
        try:
            post_promotion.apply_async(
                kwargs={
                    "identity": identity,
                    "user_id": self.user_id,
                    "chat_id": chat_id,
                    "text": text,
                    "deadline": deadline,
                    "image_data": image_data,
                    "image_url": image_url,
                    "parse_mode": parse_mode,
                },
                task_id=identity,
                expires=datetime.fromtimestamp(deadline, timezone.utc),
                retry=False,
            )
        except Exception:
            update_status(identity, "failed", "broker_unavailable")
            raise
        return {"status": "queued", "id": identity}


async def deliver(
    chat_id: str,
    text: str,
    deadline: float,
    image_data: str | None,
    image_url: str | None,
    parse_mode: str | None,
) -> None:
    """Send before deadline; only explicit photo rejection permits text fallback."""
    path = None
    try:
        if image_data:
            fd, path = tempfile.mkstemp(suffix=".jpg")
            with os.fdopen(fd, "wb") as stream:
                stream.write(base64.b64decode(image_data, validate=True))
        if time.time() >= deadline:
            raise PromotionExpired
        poster = BotPoster()
        try:
            await poster.send_offer(
                chat_id,
                text,
                image_file=path or image_url,
                parse_mode=parse_mode,
                request_timeout=min(20, deadline - time.time()),
            )
        except BotPosterError as exc:
            if (
                (path or image_url)
                and exc.status_code == 400
                and time.time() < deadline
            ):
                await poster.send_offer(
                    chat_id,
                    text,
                    parse_mode=parse_mode,
                    request_timeout=min(20, deadline - time.time()),
                )
            else:
                raise
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


@app.task(
    bind=True, max_retries=2, name="promotions.post", soft_time_limit=40, time_limit=45
)
def post_promotion(
    self,
    identity: str,
    user_id: int,
    chat_id: str,
    text: str,
    deadline: float,
    image_data: str | None = None,
    image_url: str | None = None,
    parse_mode: str | None = None,
):
    """Claim once, revalidate destination ownership, retry only definite non-delivery."""
    if time.time() >= deadline:
        update_status(identity, "expired")
        return
    with connect() as conn:
        claimed = conn.execute(
            """UPDATE promotion_deliveries SET status='sending', attempts=attempts+1,
            updated_at=CURRENT_TIMESTAMP WHERE id=%s AND status IN ('queued', 'retrying') RETURNING id""",
            (identity,),
        ).fetchone()
        if not claimed:
            return
        allowed = conn.execute(
            "SELECT 1 FROM destination_channels WHERE user_id=%s AND chat_id=%s AND enabled=true",
            (user_id, chat_id),
        ).fetchone()
    if not allowed:
        update_status(identity, "cancelled", "destination_disabled_or_removed")
        return
    # Reserve enough time for the HTTP request; no fresh send near expiry.
    if deadline - time.time() < 25:
        update_status(identity, "expired")
        return
    try:
        asyncio.run(deliver(chat_id, text, deadline, image_data, image_url, parse_mode))
    except PromotionExpired:
        update_status(identity, "expired")
    except (BotPosterError, httpx.HTTPError) as exc:
        safe_retry = isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)) or (
            isinstance(exc, BotPosterError) and exc.status_code == 429
        )
        delay = max(
            1, getattr(exc, "retry_after", None) or 3 * (self.request.retries + 1)
        )
        if (
            safe_retry
            and self.request.retries < self.max_retries
            and time.time() + delay + 25 < deadline
        ):
            update_status(identity, "retrying", type(exc).__name__)
            raise self.retry(
                countdown=delay, expires=datetime.fromtimestamp(deadline, timezone.utc)
            )
        status = (
            "expired"
            if safe_retry and time.time() + delay + 25 >= deadline
            else "failed"
        )
        if isinstance(
            exc,
            (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError, httpx.WriteError),
        ):
            status = "uncertain"
        update_status(identity, status, type(exc).__name__)
        LOGGER.warning("Promotion %s ended with status %s", identity, status)
    except Exception:
        update_status(identity, "uncertain", "unexpected_delivery_error")
        raise
    else:
        update_status(identity, "sent")
