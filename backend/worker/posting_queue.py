"""Bounded delivery queue with per-destination state and conservative retries."""

import asyncio
import base64
from datetime import datetime, timedelta, timezone
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
from backend.app.core.delivery_errors import classify_failure
from backend.app.core.offer_categories import accepts_category
from backend.app.schemas.whatsapp_policy import promotion_ttl
from offers_bot.message_context import source_timestamp, promotion_context
from offers_bot.postgres_store import connect

LOGGER = logging.getLogger(__name__)


class PromotionExpired(Exception):
    """The absolute source deadline passed before an HTTP send began."""


class DestinationChanged(Exception):
    """Routing was disabled or reassigned after the send reservation."""


@task_revoked.connect
def record_expiration(request=None, expired=False, **kwargs):
    """Record broker-side expiration without replaying the promotion."""
    if expired and request and request.name == "promotions.post":
        try:
            update_status(request.id, "expired", pending_only=True)
        except Exception:
            LOGGER.warning("Could not record expiration for promotion %s", request.id)


def update_status(
    identity: str, status: str, reason: str | None = None, *, pending_only: bool = False
) -> None:
    """Record a delivery outcome without storing credentials or response bodies."""
    with connect() as conn:
        conn.execute(
            """UPDATE promotion_deliveries SET status=%s, reason=%s, updated_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status IN ('queued','retrying','sending')
            AND (%s=false OR status IN ('queued','retrying'))""",
            (status, reason, identity, pending_only),
        )


class QueuePoster:
    """Queue prepared offers; copy local media before ingestion removes it."""

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def record_failure(
        self, chat_ids: tuple[str, ...], reason: str, stage: str
    ) -> None:
        """Audit pre-queue failures for each destination without scheduling a retry."""
        context = promotion_context.get()
        timestamp = source_timestamp.get() or time.time()

        def record():
            with connect() as conn:
                for chat_id in chat_ids:
                    identity = hashlib.sha256(
                        f"failure\0{self.user_id}\0{chat_id}\0{timestamp}\0{context.get('identity')}\0{stage}".encode()
                    ).hexdigest()
                    conn.execute(
                        """INSERT INTO promotion_deliveries
                        (id,user_id,chat_id,status,reason,expires_at,title,platform,stage,price,affiliate_url,coupon)
                        VALUES (%s,%s,%s,'failed',%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
                        (
                            identity,
                            self.user_id,
                            chat_id,
                            reason,
                            datetime.fromtimestamp(
                                timestamp + promotion_ttl(), timezone.utc
                            ),
                            context.get("title"),
                            context.get("platform"),
                            stage,
                            context.get("advertised_price"),
                            context.get("affiliate_url"),
                            context.get("coupon"),
                        ),
                    )

        await asyncio.to_thread(record)

    async def send_offer(
        self,
        chat_id: str,
        text: str,
        image_file: str | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        """Publish one destination task without blocking the event loop."""
        stamp = source_timestamp.get()
        deadline = (
            min(stamp if stamp is not None else time.time(), time.time())
            + promotion_ttl()
        )
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
        expired = time.time() >= deadline
        identity = hashlib.sha256(
            f"{self.user_id}\0{chat_id}\0{text}\0{source_timestamp.get()}\0{promotion_context.get().get('identity')}".encode()
        ).hexdigest()
        image_data = None
        image_url = None
        context = promotion_context.get()
        if image_file and not expired:
            if image_file.startswith(("https://", "http://")):
                image_url = image_file
            else:
                try:
                    if Path(image_file).stat().st_size <= 8 * 1024 * 1024:
                        image_data = base64.b64encode(
                            Path(image_file).read_bytes()
                        ).decode("ascii")
                    else:
                        LOGGER.warning(
                            "Oversized promotion image omitted for user %s",
                            self.user_id,
                        )
                except OSError:
                    LOGGER.warning(
                        "Unavailable promotion image omitted for user %s", self.user_id
                    )
        with connect() as conn:
            from backend.worker.whatsapp_delivery import (
                load_policy,
                lock_account,
                offer_key,
                trim_burst,
            )

            destination = conn.execute(
                "SELECT platform,chat_type,categories,enabled,connection_id FROM destination_channels WHERE user_id=%s AND chat_id=%s",
                (self.user_id, chat_id),
            ).fetchone()
            if not destination or not destination[3]:
                return {"status": "cancelled"}
            if not accepts_category(destination[2], context.get("category", "other")):
                return {"status": "filtered"}
            is_whatsapp = destination and destination[0] == "whatsapp"
            connection_id = None
            if is_whatsapp:
                from backend.worker.whatsapp_delivery import connection_scope

                connection_id, _ = connection_scope(conn, self.user_id, destination[4])
                lock_account(conn, self.user_id, connection_id)
            else:
                # Preserve concurrent deduplication without waiting on WhatsApp policy locks.
                lock_account(conn, self.user_id, None, "telegram")
            now = datetime.now(timezone.utc)
            stamp = source_timestamp.get()
            source_at = datetime.fromtimestamp(
                min(stamp if stamp is not None else now.timestamp(), now.timestamp()),
                timezone.utc,
            )
            key = offer_key(context, text)
            if is_whatsapp:
                policy = load_policy(conn, self.user_id, connection_id)
                deadline = min(
                    deadline,
                    (source_at + timedelta(seconds=policy.ttl_seconds)).timestamp(),
                )
                expired = now.timestamp() >= deadline
            duplicate = conn.execute(
                """SELECT id FROM promotion_deliveries WHERE user_id=%s AND chat_id=%s
                AND dedup_key=%s AND created_at>=%s AND ((status IN ('queued','retrying') AND expires_at>%s)
                OR status IN ('sending','sent','uncertain')
                OR (status='cancelled' AND reason='burst_superseded')) LIMIT 1""",
                (self.user_id, chat_id, key, now - timedelta(minutes=30), now),
            ).fetchone()
            if duplicate and not expired:
                return {"status": "duplicate"}
            inserted = conn.execute(
                """INSERT INTO promotion_deliveries (id, user_id, chat_id, status, expires_at, title, platform,source_at,dedup_key,price,connection_id,affiliate_url,coupon)
                VALUES (%s, %s, %s, %s, %s, %s, %s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING RETURNING id""",
                (
                    identity,
                    self.user_id,
                    chat_id,
                    "expired" if expired else "queued",
                    datetime.fromtimestamp(deadline, timezone.utc),
                    context.get("title"),
                    context.get("platform"),
                    source_at,
                    key,
                    context.get("advertised_price"),
                    connection_id,
                    context.get("affiliate_url"),
                    context.get("coupon"),
                ),
            ).fetchone()
            if inserted and is_whatsapp and destination[1] == "channel" and not expired:
                trim_burst(conn, self.user_id, chat_id, policy, now)
        if not inserted:
            return {"status": "duplicate"}
        if expired:
            return {"status": "expired"}
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
                    "category": context.get("category", "other"),
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
    user_id: int | None = None,
    platform: str = "telegram",
    connection_id: int | None = None,
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
        if platform == "whatsapp":
            from backend.app.core.whatsapp import WahaClient
            from backend.worker.whatsapp_delivery import connection_scope

            if connection_id is not None:
                with connect() as conn:
                    scope, primary = connection_scope(conn, user_id, connection_id)
                    routing = conn.execute(
                        "SELECT connection_id FROM destination_channels WHERE user_id=%s AND chat_id=%s AND platform='whatsapp' AND enabled=true",
                        (user_id, chat_id),
                    ).fetchone()
                    if not routing or (
                        routing[0] != scope and not (primary and routing[0] is None)
                    ):
                        raise DestinationChanged
                client = WahaClient(user_id) if primary else WahaClient(user_id, scope)
            else:
                client = WahaClient(user_id)

            if time.time() >= deadline:
                raise PromotionExpired
            await client.send_offer(
                chat_id,
                text,
                image_file=path or image_url,
                request_timeout=min(20, deadline - time.time()),
            )
            return
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
    category: str = "other",
):
    """Claim once, revalidate destination ownership, retry only definite non-delivery."""
    # Recheck operator validity and the ten-minute ceiling for older queued tasks.
    with connect() as conn:
        audit = conn.execute(
            "SELECT source_at,created_at,connection_id FROM promotion_deliveries WHERE id=%s AND user_id=%s AND chat_id=%s",
            (identity, user_id, chat_id),
        ).fetchone()
    if not audit:
        return
    deadline = min(deadline, (audit[0] or audit[1]).timestamp() + promotion_ttl())
    if time.time() >= deadline:
        update_status(identity, "expired", pending_only=True)
        return
    with connect() as conn:
        allowed = conn.execute(
            "SELECT platform,categories FROM destination_channels WHERE user_id=%s AND chat_id=%s AND enabled=true",
            (user_id, chat_id),
        ).fetchone()
    if allowed and not accepts_category(allowed[1], category):
        update_status(identity, "cancelled", "category_disabled", pending_only=True)
        return
    is_whatsapp = allowed and allowed[0] == "whatsapp"
    connection_id = None
    if is_whatsapp:
        from backend.worker.whatsapp_delivery import reserve_delivery

        action, delay = reserve_delivery(identity, user_id, chat_id, deadline)
        if action == "stop":
            return
        with connect() as conn:
            effective = conn.execute(
                "SELECT expires_at FROM promotion_deliveries WHERE id=%s", (identity,)
            ).fetchone()
        deadline = min(deadline, effective[0].timestamp())
        if action == "wait":
            try:
                self.apply_async(
                    kwargs={
                        "identity": identity,
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "text": text,
                        "deadline": deadline,
                        "image_data": image_data,
                        "image_url": image_url,
                        "parse_mode": parse_mode,
                        "category": category,
                    },
                    task_id=identity,
                    countdown=delay,
                    headers={
                        "delivery_retries": (self.request.headers or {}).get(
                            "delivery_retries", self.request.retries
                        )
                    },
                    expires=datetime.fromtimestamp(deadline, timezone.utc),
                    retry=False,
                )
            except Exception:
                update_status(identity, "failed", "broker_unavailable")
                raise
            return
        connection_id = audit[2]
    else:
        with connect() as conn:
            claimed = conn.execute(
                """UPDATE promotion_deliveries SET status='sending', attempts=attempts+1,
                updated_at=CURRENT_TIMESTAMP WHERE id=%s AND status IN ('queued', 'retrying') RETURNING id""",
                (identity,),
            ).fetchone()
            if not claimed:
                return
    if not allowed:
        update_status(identity, "cancelled", "destination_disabled_or_removed")
        return
    # Reserve enough time for the HTTP request; no fresh send near expiry.
    if deadline - time.time() < 25:
        update_status(identity, "expired")
        return
    try:
        asyncio.run(
            deliver(
                chat_id,
                text,
                deadline,
                image_data,
                image_url,
                parse_mode,
                user_id=user_id,
                platform=allowed[0],
                connection_id=connection_id,
            )
        )
    except PromotionExpired:
        update_status(identity, "expired")
    except DestinationChanged:
        update_status(identity, "cancelled", "destination_connection_changed")
    except (BotPosterError, httpx.HTTPError) as exc:
        reason = classify_failure(exc, "posting", "whatsapp" if is_whatsapp else None)
        if is_whatsapp:
            from backend.worker.whatsapp_delivery import record_outcome

            record_outcome(
                user_id,
                chat_id,
                reason,
                getattr(exc, "retry_after", None),
                connection_id=connection_id,
            )
        safe_retry = isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)) or (
            isinstance(exc, BotPosterError) and exc.status_code == 429
        )
        retries = (self.request.headers or {}).get(
            "delivery_retries", self.request.retries
        )
        delay = max(1, getattr(exc, "retry_after", None) or 3 * (2**retries))
        if (
            safe_retry
            and retries < self.max_retries
            and time.time() + delay + 25 < deadline
        ):
            update_status(identity, "retrying", reason)
            raise self.retry(
                countdown=delay,
                expires=datetime.fromtimestamp(deadline, timezone.utc),
                headers={"delivery_retries": retries + 1},
            )
        status = (
            "expired"
            if safe_retry and time.time() + delay + 25 >= deadline
            else "failed"
        )
        if reason == "delivery_uncertain" or isinstance(
            exc,
            (
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
            ),
        ):
            status = "uncertain"
        update_status(identity, status, reason)
        LOGGER.warning("Promotion %s ended with status %s", identity, status)
    except Exception:
        update_status(identity, "uncertain", "unexpected_delivery_error")
        if is_whatsapp:
            from backend.worker.whatsapp_delivery import record_outcome

            record_outcome(
                user_id,
                chat_id,
                "unexpected_delivery_error",
                connection_id=connection_id,
            )
        raise
    else:
        update_status(identity, "sent")
        if is_whatsapp:
            from backend.worker.whatsapp_delivery import record_outcome

            record_outcome(user_id, chat_id, None, connection_id=connection_id)
