# Per-user websites and automatic WhatsApp group rotation

Users configure their own Cloudflare Pages origin under **Settings → Destinations
→ WhatsApp → Site e rotação automática de grupos**. A draft may omit the URL until
Pages is available. Enabling requires an owned connection, HTTPS website origin,
and a 32–256 character random update token (`A-Z`, `a-z`, digits, `_`, `-`).

## Implementation

- Migration **`0020_whatsapp_websites`** follows `0019_llm_requests` and stores
  owner-scoped encrypted settings, active/pending destination, durable creation
  intent, observed count, timestamps, revision, failures and next check time.
- API routes: `GET/PUT /users/me/whatsapp/website` and
  `POST /users/me/whatsapp/website/recover` (`{"destination_id":123}`). All require
  the user's existing authenticated session. Tokens are masked on reads; saving
  `********` preserves the encrypted stored value. Do not use generic config routes.
- The continuous `WorkerService` explicitly schedules the monitor independently
  from offer subscriptions. No Celery Beat is required. Due users are checked
  every 60s, with a 10s scheduling tick; errors back off to 15 minutes.
- PostgreSQL session advisory namespace **81276**, keyed by user, serializes API
  edits, recovery and monitoring across replicas. A dedicated connection holds
  the session lock across HTTP calls, without holding a database transaction.
- The monitor calls WAHA's group participants and metadata endpoints. It does not
  refresh the global group catalog on each poll. Catalog/profile queries are
  limited to creating/configuring a successor. Participants are never persisted.
- The entry threshold is the configured `entry_limit` (default 1000), additionally
  capped at provider-reported capacity minus `safety_margin` (default 24), when
  capacity is reported. No unreported capacity is treated as guaranteed. Unknown,
  empty or malformed participant responses never mean zero members.

## Creation and rotation

Enabling without an active group creates the first group. An optional owned
template copies description, photo and category routing. Without a template,
the configured description is used and categories accept all offers. Groups
always start with admin-only messages; no participants are copied or invited.
Names advance using the existing numbered-series helper.

The monitor first confirms the website can accept an unavailable update. Before
WAHA creation, it checks the existing account group quota and commits a durable
`WhatsAppGroupCreation` receipt and pending request ID. A timeout or crash before
the returned group ID is durably stored blocks new creation. It must be resolved
by explicitly adopting a verified group, not by retrying the POST to WAHA.

A known created destination remains disabled until configuration, count, invite
and routing checks succeed. Interrupted configuration resumes the same group.
Activation is persisted atomically; invite delivery retries do not create another
group. Old destinations keep their enabled state and categories. No previous
group is automatically selected again when members leave.

When the active group reaches its entry threshold, the website is first sent
`invite_url: null`, then a successor is prepared and activated. Disabled,
removed/transferred groups or confirmed disconnections also withdraw entry when
the site is reachable. Transient failures never renew an old observation.

The existing maximum enabled-group policy still applies (up to six per account).
At that quota the monitor reports an actionable error and keeps earlier groups
publishing. It does not silently disable old groups to make space. Offer delivery
continues using existing validity, deduplication, spacing, quota and pause rules.

## Website contract

The separate `vsm_ofertas` repository provides Cloudflare Pages Functions and D1.
The landing button points to same-origin `/whatsapp`. The VPS sends:

```http
POST https://USER-SITE.pages.dev/api/whatsapp
Authorization: Bearer USER_SITE_TOKEN
Content-Type: application/json

{"revision":42,"invite_url":"https://chat.whatsapp.com/ABCDEFGHIJKLMNOPQRSTUV","expires_at":1794571380}
```

The bot persists an increasing revision before sending. Pages uses an atomic D1
conditional UPSERT to reject out-of-order updates. A successful response must be
`200` with the exact revision. HTTP redirects are not followed. Network, token,
storage, response-shape and revision failures appear as synchronization errors.

Observations expire after **180s**, measured from the WAHA count query. D1 serves
`302` and `Cache-Control: no-store` for a valid invite; missing/expired/withdrawn
invites produce an HTML `503`, including HEAD parity. Clicks never call WAHA or
the VPS. The only public data sent is the invite, revision and expiration.
Update tokens stay encrypted on the VPS and in Pages runtime secrets, never
in Vite public variables or generated assets.

One site/database/token belongs to one bot integration. Isolate preview and
production bindings. The website README documents D1 creation, schema migration,
Pages Functions deployment, the `WHATSAPP_DB` binding and secret
`WHATSAPP_UPDATE_TOKEN`.

## Deployment

1. Apply migration `0020_whatsapp_websites` before updated API/worker startup.
   The API's existing startup migration runner applies pending migrations.
2. Deploy API, continuous worker and frontend together. This is new code requiring
   a deployment; editing source alone does not update running VPS containers.
3. Publish the website Functions and D1 schema, configure its runtime secret and
   retrieve the actual Pages URL. No separate public VPS redirect host is needed.
4. Save settings in the bot. `*.pages.dev` HTTPS origins are accepted by default.
   Custom domains require an operator-managed comma-separated exact-host allowlist
   **`WEBSITE_ALLOWED_HOSTS`** on API and continuous worker. Approve only public
   website domains; do not allow internal/private-network hosts. Paths, query
   strings, userinfo, non-HTTPS URLs and alternate ports are rejected.
5. To reuse an existing publishing group, save disabled settings, adopt the owned
   admin group, and enable. Otherwise enabling intentionally creates a new group.
6. Validate with an authorized test account and low entry limit. Check the actual
   installed WAHA engine's participant and invite-code responses, profile settings,
   invite, website revision acknowledgement and preserved offers in prior groups.

No real WhatsApp groups are created by automated tests. No production migration,
service restart or deployment is performed by the local implementation workflow.
Redirects do not reserve member slots: monitoring and safety margins reduce but
cannot eliminate races or entries through shared invites outside the website.

## Recovery and operations

The panel shows active destination, count, last website confirmation and sanitized
failure. Use **Atualizar estado** after the monitor runs. Uncertain creations show
explicit recovery instructions. Finish settings and enable offers on the correct
group, then use **Adotar grupo**. Recovery validates ownership, connection and
WAHA administrator access. It clears only campaign state; creation receipts stay
as an audit trail. Changing connections with active/pending state is rejected.

Disabling the campaign withdraws the site's invite on the next poll and stops
creation/monitoring of groups; it does not disable offer publishing. If the site
is unreachable, previously published entries expire within their original 180s.
Keep D1 and VPS revisions consistent when restoring backups. Never reset the D1
revision while old webhook requests may still be in flight.

## Targeted validation

```bash
python -m unittest tests.test_whatsapp_website tests.test_whatsapp_website_postgres
```

Set `WAHA_POLICY_TEST_DATABASE_URL` to disposable PostgreSQL to include the real
migration, foreign-key behavior, cross-connection exclusion, cancellation and
lock-release tests. Offline tests cover tenant isolation, encrypted tokens,
creation receipts, uncertain outcomes, resumable partial settings, unknown counts,
valid invites, preserved old publishing and enabled-group quota enforcement.
The website's `npm run test:functions` exercises real local Cloudflare/D1 storage.
