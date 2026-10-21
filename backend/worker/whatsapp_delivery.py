"""Transactional WhatsApp admission: one account lock coordinates all workers."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
import secrets
from zoneinfo import ZoneInfo

from backend.app.schemas.whatsapp_policy import WhatsAppPolicy, promotion_ttl
from offers_bot.postgres_store import connect

PENDING = ("queued", "retrying")


def lock_account(
    conn, user_id: int, connection_id: int | None = None, platform: str = "whatsapp"
) -> None:
    """Serialize within one platform/account; Telegram never acquires WhatsApp locks."""
    if platform == "telegram":
        conn.execute("SELECT pg_advisory_xact_lock(81274, %s)", (user_id,))
        return
    scope, primary = connection_scope(conn, user_id, connection_id)
    conn.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        (81273 if primary else 81275, user_id if primary else scope),
    )


def connection_scope(conn, user_id: int, connection_id: int | None):
    """Validate persisted ownership; legacy rows map only to the primary connection."""
    if connection_id is None:
        row = conn.execute(
            "SELECT id,is_default FROM whatsapp_connections WHERE user_id=%s AND is_default=true",
            (user_id,),
        ).fetchone()
        return (row[0], True) if row else (None, True)
    row = conn.execute(
        "SELECT id,is_default FROM whatsapp_connections WHERE user_id=%s AND id=%s",
        (user_id, connection_id),
    ).fetchone()
    if not row:
        raise ValueError("WhatsApp connection does not belong to user")
    return row


def load_policy(conn, user_id: int, connection_id: int | None = None) -> WhatsAppPolicy:
    """Load this connection's validated policy; reject foreign IDs and invalid stored settings."""
    scope, primary = connection_scope(conn, user_id, connection_id)
    if not primary:
        row = conn.execute(
            "SELECT config_data FROM whatsapp_connections WHERE id=%s AND user_id=%s",
            (scope, user_id),
        ).fetchone()
        return (
            WhatsAppPolicy.model_validate_json(row[0])
            if row and row[0]
            else WhatsAppPolicy()
        )
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
    policy: WhatsAppPolicy,
    now: datetime,
    attempts: list[tuple],
    chat_id: str,
    destination_attempts: list[datetime] | None = None,
) -> datetime:
    """Apply rolling quotas, spacing and the local posting window; return a UTC slot."""
    slot = now
    for period, limit in ((3600, policy.max_per_hour), (86400, policy.max_per_day)):
        recent = sorted(
            at for _, at in attempts if at > now - timedelta(seconds=period)
        )
        if len(recent) >= limit:
            slot = max(slot, recent[-limit] + timedelta(seconds=period))
    if policy.destination_max_per_day is not None:
        recent = sorted(
            at
            for at in (
                destination_attempts
                if destination_attempts is not None
                else [at for target, at in attempts if target == chat_id]
            )
            if at > now - timedelta(days=1)
        )
        if len(recent) >= policy.destination_max_per_day:
            slot = max(
                slot, recent[-policy.destination_max_per_day] + timedelta(days=1)
            )
    for target, at in attempts:
        interval = policy.account_interval_seconds
        if target == chat_id:
            interval = max(interval, policy.channel_interval_seconds)
        slot = max(slot, at + timedelta(seconds=interval))
    for at in destination_attempts or []:
        slot = max(slot, at + timedelta(seconds=policy.channel_interval_seconds))
    local = slot.astimezone(ZoneInfo(policy.posting_timezone))
    start = local.replace(hour=policy.start_hour_utc, minute=0, second=0, microsecond=0)
    end = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        hours=policy.end_hour_utc
    )
    if local < start:
        slot = start
    elif local >= end:
        slot = start + timedelta(days=1)
    return slot.astimezone(timezone.utc)


def reserve_delivery(
    identity: str, user_id: int, chat_id: str, deadline: float
) -> tuple[str, float]:
    """Atomically trim pending work, revalidate destination, and reserve one send.

    Returns send/wait/stop and wait seconds. Locks are released before HTTP I/O;
    the sending audit acts as a bounded in-flight reservation across workers.
    """
    with connect() as conn:
        target = conn.execute(
            "SELECT connection_id FROM destination_channels WHERE user_id=%s AND chat_id=%s AND platform='whatsapp'",
            (user_id, chat_id),
        ).fetchone()
        connection_id, primary = connection_scope(
            conn, user_id, target[0] if target else None
        )
        lock_account(conn, user_id, connection_id)
        now = datetime.now(timezone.utc)
        policy = load_policy(conn, user_id, connection_id)
        row = conn.execute(
            "SELECT status,source_at,created_at,expires_at,connection_id FROM promotion_deliveries WHERE id=%s AND user_id=%s AND chat_id=%s",
            (identity, user_id, chat_id),
        ).fetchone()
        if not row or row[0] not in PENDING:
            return "stop", 0
        if row[4] != connection_id and not (row[4] is None and primary):
            conn.execute(
                "UPDATE promotion_deliveries SET status='cancelled',reason='destination_connection_changed',updated_at=%s WHERE id=%s",
                (now, identity),
            )
            return "stop", 0
        source = row[1] or row[2]
        expiry = min(
            row[3],
            source + timedelta(seconds=policy.ttl_seconds),
            datetime.fromtimestamp(deadline, timezone.utc),
        )
        allowed = conn.execute(
            "SELECT chat_type,connection_id FROM destination_channels WHERE user_id=%s AND chat_id=%s AND platform='whatsapp' AND enabled=true",
            (user_id, chat_id),
        ).fetchone()
        if not allowed or (
            allowed[1] != connection_id and not (allowed[1] is None and primary)
        ):
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
        state_table = (
            "whatsapp_delivery_states" if primary else "whatsapp_connection_states"
        )
        state_owner = "user_id" if primary else "connection_id"
        state_id = user_id if primary else connection_id
        pauses = conn.execute(
            f"SELECT paused_until FROM {state_table} WHERE {state_owner}=%s AND chat_id IN ('',%s) AND paused_until>%s",
            (state_id, chat_id, now),
        ).fetchall()
        attempts = conn.execute(
            "SELECT chat_id,attempted_at,next_send_at FROM whatsapp_send_attempts WHERE user_id=%s AND attempted_at>%s AND (connection_id=%s OR (%s AND connection_id IS NULL))",
            (user_id, now - timedelta(days=1), connection_id, primary),
        ).fetchall()
        destination_attempts = [
            row[0]
            for row in conn.execute(
                "SELECT attempted_at FROM whatsapp_send_attempts WHERE user_id=%s AND chat_id=%s AND attempted_at>%s",
                (user_id, chat_id, now - timedelta(days=1)),
            ).fetchall()
        ]
        slot = next_slot(
            policy,
            now,
            [(chat, at) for chat, at, _ in attempts],
            chat_id,
            destination_attempts,
        )
        # The random gap belongs to an attempt, never to a polling/retry invocation.
        slot = max([slot, *(at for _, _, at in attempts if at is not None)])
        # A short collection window allows burst selection before the first send.
        if allowed[0] == "channel":
            slot = max(slot, row[2] + timedelta(seconds=policy.burst_window_seconds))
        if pauses:
            slot = max(slot, *(pause[0] for pause in pauses))
        active = conn.execute(
            "SELECT max(updated_at) FROM promotion_deliveries WHERE user_id=%s AND status='sending' AND chat_id ~ '@(newsletter|g[.]us)$' AND updated_at>%s AND (connection_id=%s OR (%s AND connection_id IS NULL))",
            (user_id, now - timedelta(seconds=60), connection_id, primary),
        ).fetchone()[0]
        if active:
            slot = max(slot, now + timedelta(seconds=5))
        slot = next_slot(policy, slot, [], chat_id)
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
        minimum = policy.account_interval_seconds
        maximum = policy.account_interval_max_seconds or minimum
        gap = minimum + secrets.randbelow(maximum - minimum + 1)
        conn.execute(
            "INSERT INTO whatsapp_send_attempts(user_id,chat_id,attempted_at,connection_id,next_send_at) VALUES (%s,%s,%s,%s,%s)",
            (user_id, chat_id, now, connection_id, now + timedelta(seconds=gap)),
        )
        conn.execute(
            "DELETE FROM whatsapp_send_attempts WHERE user_id=%s AND attempted_at<%s",
            (user_id, now - timedelta(days=2)),
        )
        return "send", 0


def record_outcome(
    user_id: int,
    chat_id: str,
    reason: str | None,
    retry_after: int | None = None,
    connection_id: int | None = None,
) -> None:
    """Persist circuit state: restrictions pause immediately, three failures pause 15m."""
    with connect() as conn:
        connection_id, primary = connection_scope(conn, user_id, connection_id)
        lock_account(conn, user_id, connection_id)
        table = "whatsapp_delivery_states" if primary else "whatsapp_connection_states"
        owner = "user_id" if primary else "connection_id"
        owner_id = user_id if primary else connection_id
        scope = (
            chat_id if reason in ("whatsapp_permission", "whatsapp_destination") else ""
        )
        if reason is None:
            conn.execute(
                f"UPDATE {table} SET failures=0 WHERE {owner}=%s AND chat_id IN ('',%s)",
                (owner_id, chat_id),
            )
            return
        conn.execute(
            f"""INSERT INTO {table}({owner},chat_id,failures) VALUES (%s,%s,1)
            ON CONFLICT({owner},chat_id) DO UPDATE SET failures={table}.failures+1""",
            (owner_id, scope),
        )
        failures = conn.execute(
            f"SELECT failures FROM {table} WHERE {owner}=%s AND chat_id=%s",
            (owner_id, scope),
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
                f"UPDATE {table} SET paused_until=%s,pause_reason=%s WHERE {owner}=%s AND chat_id=%s",
                (until, reason, owner_id, scope),
            )
