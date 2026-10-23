# Operations and troubleshooting

[Documentation index](README.md)

## Administration and source catalog

The `admin` role is required for `/admin/source-groups` and all corresponding
API operations. The API reads the current role from PostgreSQL on every request;
revocations affect existing sessions. Public registration always creates `user`.

Promote or revoke access through a trusted terminal:

```bash
docker compose exec backend python -m backend.set_admin admin@example.com
docker compose exec backend python -m backend.set_admin admin@example.com --role user
```

In Coolify, run `python -m backend.set_admin ...` in the backend service.
No public API grants administrator roles.

Administrators add, edit, enable, disable, and remove public Telegram sources.
The reader refreshes the catalog every 30 seconds. Only enabled sources are
selectable; an empty catalog disables ingestion. The operator's Telegram account
must be able to join/read every source.

## Posting queue

The listener prepares links and publishes one task per destination to Redis.
The `posting` service consumes the `promotions` queue through Celery; there is
no Celery Beat. `POSTING_CONCURRENCY` sets posting processes, defaulting to `2`.

```bash
docker compose up -d --build db redis backend worker posting
docker compose ps
docker compose logs --tail=100 backend worker posting
```

In Coolify, Redis is named `offers-redis`; use the deployment file's service names.

### Validity and attempts

The default and maximum lifetime is **600 seconds from the original message**,
including processing. `PROMOTION_TTL_SECONDS` accepts 1–600. WhatsApp policies
may shorten it. Waits and retries do not renew the deadline.

Before sending, the consumer checks enabled state, category, and validity.
On WhatsApp, it also checks the responsible connection, pauses, and limits.
Duplicate tasks do not repeat a send that has already started.

Up to two retries are allowed for connection failures before sending and 429
responses, respecting `retry_after` and remaining lifetime. Ambiguous outcomes
are marked `uncertain`, without automatic retry. Telegram does not provide an
idempotency key for this send; avoiding duplicates may mean losing a delivery
after a crash.

### Redis is not persistent

The supplied Redis does not write snapshots or AOF. Restarting it loses pending
tasks, which are not reconstructed from the database. Memory is limited to 256 MB
with `noeviction`: reaching the limit causes task publication to fail rather
than silently evicting another message.

History does not store the full payload or act as a recoverable queue. After
Redis data loss:

- `queued`/`retrying` records past their deadline appear as `expired` when queried;
- unfinished `sending` records past their deadline appear as `uncertain`;
- these records must not be automatically resent.

### Media

Local images are copied into the task before temporary cleanup, with an 8 MB
limit; larger images are omitted. Image URLs can be sent to Telegram.
An explicit photo rejection with 400 permits a text-only attempt.

## History and retention

`GET /users/me/deliveries` returns only the authenticated user's records.
It supports pagination, offer grouping, store/result filters, and title search
up to 200 characters. Search requires all words and treats `%` and `_` literally.
Grouping keeps publication destinations together.

Price, coupon, and affiliate link are returned when persisted. Conversion failures
are recorded before queueing; a recovered parser fallback is not a send failure.
Reader failures may occur without any offer record. User-facing error messages
are classified in Portuguese and do not expose raw responses, tokens, cookies,
or keys.

The worker removes `promotion_deliveries` older than **60 days** on startup and
every 24 hours. Cleanup commits batches of 1,000 and does not change
`processed_offers` or deduplication rules. Failures are logged and retried after
30 seconds without interrupting ingestion. Cleanup does not run without an
active worker.

## Quick diagnosis

| Symptom | Check |
| --- | --- |
| Services will not start | Database connectivity, valid Fernet key, migrations, and backend logs |
| Registration unavailable | `DISABLE_PUBLIC_REGISTRATION`; restart frontend after changing it |
| Password recovery unavailable | SMTP on the Next.js server; see [Security](security.md) |
| User has no publications | Selected source, store integration, enabled destination, and allowed category |
| Saved settings not yet applied | Allow one refresh cycle of up to 30 seconds |
| No source produces offers | Telethon session, enabled catalog, and operator account access |
| Telegram destination rejected | Bot administrator status and message/photo permissions |
| WhatsApp account disconnected | QR and correct connection status in Destinations; re-enable destinations after reconnecting |
| WhatsApp connected without delivery | Pauses, window, quotas, categories, validity, and responsible connection |
| Partial WhatsApp discovery | Engine compatibility; groups and channels fail independently |
| Amazon conversion fails | Brazilian Amazon destination and allowed redirect chain; see [Integrations](integrations.md) |
| Mercado Livre returns 401/403 | Refresh the user's cookies and CSRF token |
| AI unavailable | Regex continues; check keys and logs if structured extraction is required |
| Tasks do not reach consumers | Redis and posting service; broker restart loses pending tasks |
| Uncertain result | Investigate the destination and logs before any manual resend |

## Backups and recovery

Preserve PostgreSQL, the Fernet key, and WAHA session storage. Keep the key
separate from database backups; both are needed to recover credentials.
Redis does not need a backup in the current design because its contents are
temporary, but losing it means losing pending work.

During recovery, apply migrations and discard expired offers. WhatsApp recovery
must respect policies rather than dump the backlog in a burst. See
[Migrations](migrations.md), [Security](security.md), and [WhatsApp](whatsapp.md).
