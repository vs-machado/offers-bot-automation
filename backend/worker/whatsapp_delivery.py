"""Transactional WhatsApp admission: one account lock coordinates all workers."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re

from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, promotion_ttl
from offers_bot.postgres_store import connect

PENDING = ("queued", "retrying")


def lock_account(conn, user_id: int) -> None:
    """Serialize enqueue, selection and send reservations within a transaction."""
    conn.execute("SELECT pg_advisory_xact_lock(81273, %s)", (user_id,))


def load_policy(conn, user_id: int) -> WhatsAppPolicy:
    row = conn.execute(
        "SELECT config_data FROM whatsapp_delivery_policies WHERE user_id=%s",
        (user_id,),
    ).fetchone()
    return WhatsAppPolicy.model_validate_json(row[0]) if row else WhatsAppPolicy()


def offer_key(context: dict, text: str) -> str:
    """Use resolved product identity plus price; fallback text retains all URL params."""
    product = context.get("product_key")
    price = "|".join(
        normalize_price(part) for part in str(context.get("price") or "").split("|")
    )
    value = f"{product}\0{price}" if product else text
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_price(value: str) -> str:
    """Canonicalize BRL amount formatting without guessing non-price expressions."""
    value = value.strip()
    if value in ("", "None"):
        return "?"
    match = re.fullmatch(r"(?:R\$\s*)?(\d[\d.,]*)", value)
    if not match:
        return value
    amount = match[1]
    if "," in amount:
        amount = amount.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", amount):
        amount = amount.replace(".", "")
    try:
        return format(Decimal(amount).quantize(Decimal("0.01")), "f")
    except InvalidOperation:
        return value


def trim_burst(
    conn, user_id: int, chat_id: str, policy: WhatsAppPolicy, now: datetime
) -> None:
    """Keep newest five pending offers on burst/backlog; never touch active sends."""
    ttl = min(policy.ttl_seconds, promotion_ttl())
    conn.execute(
        """UPDATE promotion_deliveries SET expires_at=LEAST(expires_at,
        COALESCE(source_at,created_at)+make_interval(secs => %s))
        WHERE user_id=%s AND chat_id=%s AND status IN ('queued','retrying')""",
        (ttl, user_id, chat_id),
    )
    conn.execute(
        """UPDATE promotion_deliveries SET status='expired', reason='promotion_expired',
        updated_at=%s WHERE user_id=%s AND chat_id=%s AND status IN ('queued','retrying')
        AND expires_at<=%s""",
        (now, user_id, chat_id, now),
    )
    arrivals = conn.execute(
        """SELECT count(*) FROM promotion_deliveries WHERE user_id=%s AND chat_id=%s
        AND created_at>=%s AND expires_at>%s
        AND COALESCE(source_at,created_at)+make_interval(secs => %s)>%s
        AND (status IN ('queued','retrying','sending','sent','uncertain')
        OR (status='cancelled' AND reason='burst_superseded'))""",
        (
            user_id,
            chat_id,
            now - timedelta(seconds=policy.burst_window_seconds),
            now,
            ttl,
            now,
        ),
    ).fetchone()[0]
    pending = conn.execute(
        """SELECT id FROM promotion_deliveries WHERE user_id=%s AND chat_id=%s
        AND status IN ('queued','retrying') AND expires_at>%s
        ORDER BY COALESCE(source_at,created_at) DESC, created_at DESC, id DESC""",
        (user_id, chat_id, now),
    ).fetchall()
    if max(arrivals, len(pending)) >= policy.burst_threshold:
        for (identity,) in pending[5:]:
            conn.execute(
                """UPDATE promotion_deliveries SET status='cancelled', reason='burst_superseded',
                updated_at=%s WHERE id=%s AND status IN ('queued','retrying')""",
                (now, identity),
            )


def next_slot(
    policy: WhatsAppPolicy, now: datetime, attempts: list[tuple], chat_id: str
) -> datetime:
    """Compute rolling account quotas and account/channel spacing, in UTC."""
    slot = now
    for period, limit in ((3600, policy.max_per_hour), (86400, policy.max_per_day)):
        recent = sorted(
            at for _, at in attempts if at > now - timedelta(seconds=period)
        )
        if len(recent) >= limit:
            slot = max(slot, recent[-limit] + timedelta(seconds=period))
    for target, at in attempts:
        interval = policy.account_interval_seconds
        if target == chat_id:
            interval = max(interval, policy.channel_interval_seconds)
        slot = max(slot, at + timedelta(seconds=interval))
    start = slot.replace(hour=policy.start_hour_utc, minute=0, second=0, microsecond=0)
    end = slot.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        hours=policy.end_hour_utc
    )
    if slot < start:
        slot = start
    elif slot >= end:
        slot = start + timedelta(days=1)
    return slot


def reserve_delivery(
    identity: str, user_id: int, chat_id: str, deadline: float
) -> tuple[str, float]:
    """Atomically trim pending work, revalidate destination, and reserve one send.

    Returns send/wait/stop and wait seconds. Locks are released before HTTP I/O;
    the sending audit acts as a bounded in-flight reservation across workers.
    """
    with connect() as conn:
        lock_account(conn, user_id)
        now = datetime.now(timezone.utc)
        policy = load_policy(conn, user_id)
        row = conn.execute(
            "SELECT status,source_at,created_at,expires_at FROM promotion_deliveries WHERE id=%s AND user_id=%s AND chat_id=%s",
            (identity, user_id, chat_id),
        ).fetchone()
        if not row or row[0] not in PENDING:
            return "stop", 0
        source = row[1] or row[2]
        expiry = min(
            row[3],
            source + timedelta(seconds=policy.ttl_seconds),
            datetime.fromtimestamp(deadline, timezone.utc),
        )
        allowed = conn.execute(
            "SELECT chat_type FROM destination_channels WHERE user_id=%s AND chat_id=%s AND platform='whatsapp' AND enabled=true",
            (user_id, chat_id),
        ).fetchone()
        if not allowed:
            conn.execute(
                "UPDATE promotion_deliveries SET status='cancelled', reason='destination_disabled_or_removed', updated_at=%s WHERE id=%s",
                (now, identity),
            )
            return "stop", 0
        if allowed[0] == "channel":
            trim_burst(conn, user_id, chat_id, policy, now)
            state = conn.execute(
                "SELECT status FROM promotion_deliveries WHERE id=%s", (identity,)
            ).fetchone()[0]
            if state not in PENDING:
                return "stop", 0
        if expiry <= now + timedelta(seconds=25):
            conn.execute(
                "UPDATE promotion_deliveries SET status='expired',reason='promotion_expired', updated_at=%s WHERE id=%s",
                (now, identity),
            )
            return "stop", 0
        pauses = conn.execute(
            "SELECT paused_until FROM whatsapp_delivery_states WHERE user_id=%s AND chat_id IN ('',%s) AND paused_until>%s",
            (user_id, chat_id, now),
        ).fetchall()
        attempts = conn.execute(
            "SELECT chat_id,attempted_at FROM whatsapp_send_attempts WHERE user_id=%s AND attempted_at>%s",
            (user_id, now - timedelta(days=1)),
        ).fetchall()
        slot = next_slot(policy, now, attempts, chat_id)
        # A short collection window allows burst selection before the first send.
        if allowed[0] == "channel":
            slot = max(slot, row[2] + timedelta(seconds=policy.burst_window_seconds))
        if pauses:
            slot = max(slot, *(pause[0] for pause in pauses))
        active = conn.execute(
            "SELECT max(updated_at) FROM promotion_deliveries WHERE user_id=%s AND status='sending' AND chat_id ~ '@(newsletter|g[.]us)$' AND updated_at>%s",
            (user_id, now - timedelta(seconds=60)),
        ).fetchone()[0]
        if active:
            slot = max(slot, now + timedelta(seconds=5))
        if slot + timedelta(seconds=25) >= expiry:
            conn.execute(
                "UPDATE promotion_deliveries SET status='expired',reason='policy_deadline', updated_at=%s WHERE id=%s",
                (now, identity),
            )
            return "stop", 0
        if slot > now:
            reason = "whatsapp_paused" if pauses else "delivery_throttled"
            conn.execute(
                "UPDATE promotion_deliveries SET reason=%s,updated_at=%s WHERE id=%s",
                (reason, now, identity),
            )
            return "wait", min((slot - now).total_seconds(), 60)
        conn.execute(
            "UPDATE promotion_deliveries SET status='sending', reason=NULL, attempts=attempts+1, updated_at=%s, expires_at=%s WHERE id=%s",
            (now, expiry, identity),
        )
        conn.execute(
            "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at) VALUES (%s,%s,%s)",
            (user_id, chat_id, now),
        )
        conn.execute(
            "DELETE FROM whatsapp_send_attempts WHERE user_id=%s AND attempted_at<%s",
            (user_id, now - timedelta(days=2)),
        )
        return "send", 0


def record_outcome(
    user_id: int, chat_id: str, reason: str | None, retry_after: int | None = None
) -> None:
    """Persist circuit state: restrictions pause immediately, three failures pause 15m."""
    with connect() as conn:
        lock_account(conn, user_id)
        scope = (
            chat_id if reason in ("whatsapp_permission", "whatsapp_destination") else ""
        )
        if reason is None:
            conn.execute(
                "UPDATE whatsapp_delivery_states SET failures=0 WHERE user_id=%s AND chat_id IN ('',%s)",
                (user_id, chat_id),
            )
            return
        conn.execute(
            """INSERT INTO whatsapp_delivery_states(user_id,chat_id,failures) VALUES (%s,%s,1)
            ON CONFLICT(user_id,chat_id) DO UPDATE SET failures=whatsapp_delivery_states.failures+1""",
            (user_id, scope),
        )
        failures = conn.execute(
            "SELECT failures FROM whatsapp_delivery_states WHERE user_id=%s AND chat_id=%s",
            (user_id, scope),
        ).fetchone()[0]
        immediate = reason in (
            "whatsapp_authentication",
            "whatsapp_permission",
            "whatsapp_destination",
            "whatsapp_rate_limit",
        )
        if immediate or failures >= 3:
            seconds = (
                max(60, retry_after or 60) if reason == "whatsapp_rate_limit" else 900
            )
            until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            conn.execute(
                "UPDATE whatsapp_delivery_states SET paused_until=%s,pause_reason=%s WHERE user_id=%s AND chat_id=%s",
                (until, reason, user_id, scope),
            )
