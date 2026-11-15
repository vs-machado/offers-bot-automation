# Per-user websites and PostgreSQL-backed WhatsApp entry

Each user configures a website under **Settings → Destinations → WhatsApp → Site
e rotação automática de grupos**. Save the website origin, owned WhatsApp
connection, group-series name, optional template and entry rules. Saving creates
a stable public campaign UUID and displays an entry link on the panel's origin:

```text
https://BOT-DOMAIN/join/whatsapp/CAMPAIGN-UUID
```

The website owner configures this public link once in their site's
`site.config.json` (`whatsappEntryUrl`) and deploys the static site. Subsequent
group changes require no website rebuild, webhook, D1 database or update token.
The website URL is metadata, not an outbound HTTP target or redirect destination.
Public HTTPS custom domains work without an operator allowlist.

## Data and migrations

- `0020_whatsapp_websites` creates owner-scoped campaign and creation state.
- **`0021_whatsapp_public_entry`** adds unique public IDs, campaign enabled state,
  responsible connection, observed entry limit, validated invite and expiry.
  It preserves active/pending groups and creation receipts, removes obsolete D1
  tokens from encrypted settings, and schedules fresh monitoring. Old revision and
  website-acknowledgement columns are removed. No cached D1 data is imported.
- Settings remain encrypted with the existing credential key. Public requests do
  not decrypt settings or require access to that key.
- The downgrade cannot recover deleted tokens; returning to the old D1 version
  requires reconfiguration. Deploy API, continuous worker and frontend together.

## Public entry

`GET/HEAD /join/whatsapp/{publicId}` is an unauthenticated, narrow Next.js route.
It uses existing server-only `API_BASE_URL` to call
`GET/HEAD /public/whatsapp/{publicId}` on FastAPI. It forwards no visitor cookies,
authorization, arbitrary path or query parameters. It does not follow upstream
redirects, validates the returned WhatsApp invite, and handles network failures
with a sanitized `503` page. Administrative backend proxy authentication remains
unchanged. No separate public API hostname or database port is required.

FastAPI uses one PostgreSQL query and no WAHA calls per click. It requires:

- matching campaign UUID and enabled campaign;
- active, owned WhatsApp group with offer publishing enabled;
- an owned responsible connection matching the destination's connection;
- no unresolved pending creation;
- a nonnegative observed count below the recorded operational threshold;
- a valid observation and invite expiry, both within the 180s observation window;
- a validated `https://chat.whatsapp.com/CODE` invite.

Success is `302` with `Cache-Control: no-store`. Unknown, disabled, full, stale,
removed/transferred or unavailable entries return HTML `503` and `Retry-After: 60`.
HEAD returns matching status/headers without a body. Database errors never expose
SQL, credentials or internal hostnames. Parameters cannot override the destination.

Configure proxy/edge rate limiting appropriate to public traffic and avoid cache
rules overriding `no-store` on `/join/whatsapp/*`. Each click reads PostgreSQL;
the static landing page remains available when the VPS is unavailable, while
group entry depends on the VPS/database.

## Creation and rotation

The continuous `WorkerService` explicitly schedules the monitor independently
from offer subscriptions. A 10s scheduling tick processes users due every 60s;
errors back off to 15 minutes. PostgreSQL advisory namespace **81276**, keyed by
user, serializes configuration, recovery and monitoring across replicas. The lock
uses a dedicated connection without holding transactions open during WAHA calls.

Enabling without an active group creates the first group. An optional owned admin
template supplies description, photo and category routing. Otherwise configured
description and all offer categories are used. Groups use admin-only messages;
participants are never copied, invited or persisted. Names advance in the series.

The threshold is `entry_limit` (default 1000), capped at provider-reported capacity
minus `safety_margin` (default 24), when reported. Unknown/empty/malformed counts
never mean zero members. No default capacity is treated as guaranteed.

Before creating a successor, the monitor commits entry withdrawal, verifies group
quota, and persists a `WhatsAppGroupCreation` receipt and pending request ID.
Uncertain WAHA creation is never retried automatically. Known partial creation
resumes the same group. Only after configuration, vacancy, invite and routing
validation does it atomically enable the new destination, replace the active
group and publish the invite snapshot in PostgreSQL.

Earlier groups keep their enabled state/categories and continue offer delivery
under existing expiry, deduplication, spacing, quota and pause rules. The monitor
never returns to older groups automatically. The existing enabled-group maximum
(up to six per account) blocks further creation with an actionable panel error;
old groups are not silently disabled to make room.

Snapshots expire 180s after the count query begins, not after later retries.
Transient failures cannot renew stale observations. Known full/disabled groups or
confirmed disconnections withdraw entry. Disabling/changing campaign settings
clears the public snapshot immediately; it does not disable offer publishing.
Recovery also clears the snapshot until the monitor verifies the adopted group.

## Setup and recovery

1. Apply both migrations and deploy API, worker and frontend together.
2. Save per-user website settings. URL can be omitted in a disabled draft.
3. Configure the displayed public link in the website once and publish it.
4. Enable creation, or save disabled, adopt an existing enabled admin group and
   then enable the campaign. Use an authorized test account for live validation.

The panel shows active destination, member count, observation time and sanitized
failures. **Atualizar estado** refreshes the view. For uncertain creation, inspect
WhatsApp, finish settings and enable the correct group's offers, then **Adotar
grupo**. Adoption checks ownership, connection and admin role; receipts remain as
audit history. Changing connections with active/pending state is rejected.

Public UUIDs are shareable identifiers, not administrative secrets. Preserve them
when restoring PostgreSQL so website links continue working. Redirects do not
reserve member slots; margins and periodic checks cannot eliminate concurrent
entries or joins through invites shared outside the website.

## Targeted validation

```bash
python -m unittest tests.test_whatsapp_website tests.test_whatsapp_website_postgres
```

Set `WAHA_POLICY_TEST_DATABASE_URL` to disposable PostgreSQL to include actual
migrations, config-token removal, UUID generation, FK behavior and replica locks.
Offline API/rotation tests cover tenant isolation, public GET/HEAD, expiry,
capacity, disabled/transferred groups, database failures and durable creation.
No automated test creates a real WhatsApp group.

From `frontend/`, `node --test tests/whatsapp-entry.test.mjs` starts a real Next.js
public route against a mock backend and checks redirects, credential/query
isolation, HEAD, invalid targets and outages. The website repository uses
`npm run test:config` and Playwright for static builds and no-JavaScript links.
