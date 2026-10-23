# WAHA: channel implementation recommendations

[Documentation index](README.md) · [WhatsApp operator and user guide](whatsapp.md)

## Objective

Connect WhatsApp accounts and publish to **channels**, integrated into the UI,
tutorial, and bot settings. Offers still originate from the Telegram catalog;
distribution uses each user's enabled destinations.

This document guides implementation, review, and validation of the feature.
The measures below reduce abuse and operational failures but do not guarantee
protection from bans: WAHA is an unofficial client.

## Implementation requirements

### Posting frequency per account and channel

- Space out and serialize posts to the same channel, including with concurrent workers.
- Also control aggregate account volume: multiple channels share the same session.
- Allow configuration of minimum intervals, hourly/daily caps, and posting windows.
  Document the chosen values and their editorial/operational rationale.
- Do not present values as "safe" quotas: there is no publicly proven limit that
  prevents bans for channels using WAHA.
- When a limit is reached, defer only offers that are still valid; do not build an unlimited backlog.

### Deduplication and validity

- Deduplicate the same offer received from different sources using normalized products/links.
- Preserve product variations and parameters required for affiliate links.
- Apply deduplication per destination and time window, including under concurrency.
- Allow reposting after a relevant change, such as price, through an explicit rule.
- Preserve validity from ingestion through sending, and recheck that the destination
  is enabled before delivery.
- **Maximum defined lifetime: 10 minutes (600 seconds).** Offers at or beyond this
  age must expire without being published. Count from the source message timestamp,
  using queue entry time only when the source has no timestamp. Reprocessing,
  retries, reconnection, and restarts do not renew this deadline.
- Configuration may set a shorter lifetime, never longer than 600 seconds.
  Align `PROMOTION_TTL_SECONDS`, broker expiration, and the check immediately
  before sending with this limit.
- After an outage or restart, discard expired offers and resume with spacing,
  without dumping the backlog in a burst.

### Bursts: prioritize the 5 most recent offers

- When many offers arrive within a short interval, reduce each channel's backlog
  to the **5 most recent eligible offers**, discarding older pending offers from
  that burst. Concentrated volume indicates a risk that offers may already be
  sold out; it does not confirm that stock is unavailable.
- Make the detection window and minimum number of offers that defines a burst
  configurable. Define and document values before implementation; initially
  retain 5 offers.
- Use eligible offers' arrival times in the system to detect concentration;
  sort by source timestamp, falling back to queue entry time, to select the
  most recent offers. Use deterministic tie-breaking.
- Apply deduplication and validity checks before selection: duplicates and expired
  offers must not occupy the 5 slots. Do not recover discarded offers to fill gaps.
- Select per channel and across sources, preserving user isolation. Also apply
  this to the backlog accumulated when resuming after an outage.
- Selecting 5 offers does not authorize posting them together: maintain account/channel
  limits and spacing. A selected offer that expires while waiting must be discarded.
- Discard only deliveries that are still pending; do not cancel sends already started
  or resend completed or uncertain deliveries. Coordinate selection and the start of
  sending to avoid races between workers.
- Record a specific burst-discard reason, distinct from expiration or confirmed
  out-of-stock status. Discarded jobs must not return through retries.

### Automatic pauses and recovery

- Distinguish temporary restrictions, authentication failures, missing permissions,
  invalid destinations, and transport failures when the upstream service allows it.
- Pause the account/channel after a restriction or repeated failures; show the reason
  and state in settings.
- Use progressive backoff and honor `Retry-After` when available.
- Do not loop through restarts, logouts, or pairing attempts to remove restrictions.
- Do not automatically retry sends with uncertain outcomes: a timeout may occur after
  a post was accepted. Record the uncertain state for investigation.
- WAHA errors `463` and `475` concern new contacts; do not assume they are channel
  quotas or correspond to identical HTTP status codes.

### Account, session, and UI

- Isolate sessions by authenticated user; do not accept arbitrary sessions from the browser.
- Keep the operator API key server-side and make the QR accessible only to its owner.
- List and accept only channels where the account has the `OWNER` or `ADMIN` role.
- Persist sessions and avoid unnecessary pairing.
- Validate version/engine compatibility with channels, text, and images when updating.
- Allow pausing each destination and disconnecting the account in settings.
- Disconnecting disables WhatsApp destinations; resuming requires reconnection and explicit enabling.
- Show connection, failure, pause, and recovery states in the tutorial/settings.
- Do not let group-listing failures block channels.
- Log attempts, destination, outcome, and failure/expiration reason without API keys or QR data.

### Content and channel-specific behavior

- Publish product images as custom high-quality link previews through
  `POST /api/send/link-custom-preview`, not as photo attachments. The first
  purchase URL in the offer is the clickable target; retain affiliate parameters
  and the full formatted description. Support both image URLs and base64 images.
- Require an engine/version supporting custom previews, such as NOWEB; the
  previously documented WEBJS installation does not implement this endpoint.
  Validate image rendering above the description and click-through in both groups
  and channels on real clients. Missing images use automatic text previews;
  missing links use text only. Do not retry a failed preview as a separate photo.
- Prioritize relevant offers, trustworthy links, and affiliate-link disclosure.
- Avoid misleading, repetitive, or expired content, and volume inconsistent with the channel's purpose.
- Do not send private messages or bulk invitations to followers in this flow.
- One channel post does not equal one send call per follower.
- Do not automatically apply private-chat recommendations, such as marking messages
  as read or simulating typing, to channels.
- Do not treat random delays, "warm-up," proxies, or artificial text changes as
  guaranteed protection against bans.

## Validation criteria

- User isolation and selection of administered channels only.
- Real text and image delivery to a test channel.
- Product previews display the supplied image above the description, and tapping
  the card opens the original affiliate link in test groups and channels.
- Limits maintained with concurrent jobs and multiple channels on the same account.
- Deduplication across sources and reprocessing.
- Bursts retain only the 5 most recent eligible offers per channel; verify ordering,
  multiple sources, isolation, concurrency, and recovery after an outage.
- Offers discarded during bursts do not reappear through retries; selected offers
  continue to respect spacing and the maximum 600-second lifetime.
- Expired offers are discarded and recovery after an outage does not cause a burst.
- Offers are discarded at the 600-second boundary, including offers already old when
  entering the queue and retries/reconnections that must not renew their validity.
- Restrictions/failures trigger pauses, and disabling a destination cancels delivery.
- No automatic resending when the delivery outcome is uncertain.
- Tutorial and settings reflect connection, destination, and pause states consistently.

## Observed state and next steps

Telegram and WhatsApp destinations have independent category selection in setup
and settings. `categories = NULL` accepts everything; an empty list accepts no
offers. Rules are checked before queue entry and again before delivery, including
after deferral due to limits. Required migration: `0013_destination_categories`.
Blocked categories do not occupy slots in new bursts when the rule is already saved.

Existing foundation: user-owned sessions, QR pairing, administered channels,
destinations, and delivery through the Celery queue, with expiration and
conservative retry handling, integrated into the UI and setup tutorial.

Implemented: a maximum 600-second lifetime, account and destination
limits, transactional cross-source deduplication by product/variation and price
(30-minute window), retention of the 5 most recent offers during bursts and backlog
recovery, automatic pauses, and UI/tutorial controls. Price changes permit a new
post; destinations and users have independent deduplication.

Default values, defined as editorial policy rather than guarantees against bans:

| Control | Default |
| --- | --- |
| Lifetime | 600 seconds, also capped by the operator's `PROMOTION_TTL_SECONDS` |
| Aggregate account interval | 20 seconds |
| Destination interval | 45 seconds |
| Account attempts | 90/hour and 600/24h, in rolling windows |
| Burst | 6 eligible offers in 60 seconds; retain the 5 most recent pending offers |
| Initial collection period per channel offer | 60 seconds (matches the configured burst window) |
| Posting window | 0–24h UTC (all day), configurable without crossing midnight |
| Consecutive failures | 3 failures: pause the account for 15 minutes |
| Authentication/permission/destination rejection | Immediate 15-minute pause |
| Explicit HTTP 429 rate limit | Pause for at least 60 seconds or `Retry-After`, whichever is longer |

Account quotas are shared by all WhatsApp groups and channels on the same account.
The shorter spacing and higher quotas reduce policy-driven expiration when both
types of destination receive offers. These defaults apply when no saved policy
exists; saved settings retain their configured values. The API and workers must
also use `PROMOTION_TTL_SECONDS=600` to allow the full ten-minute lifetime: a lower
operator value still takes precedence over the policy's lifetime.

Permission/destination failures pause only the destination; authentication,
rate limits, and repeated failures pause the account. Internal error responses
and statuses are not assumed to match HTTP codes. Manual recovery clears pauses
without enabling destinations or recovering discarded offers. Offers expire early
when there is insufficient time to start a request before the deadline.

Workers use a per-connection PostgreSQL transaction lock to coordinate deduplication,
burst trimming, and send reservations across processes. An active reservation
prevents concurrent WhatsApp sends on the same account; each attempt counts
toward limits, including failed attempts. No credentials are interpolated into SQL.

Telegram enqueue deduplication uses a separate advisory-lock namespace. WhatsApp
account locks, pauses, quotas, collection windows, and policy-specific lifetimes
must not delay or suppress Telegram deliveries. Both platforms retain the shared
operator validity ceiling (`PROMOTION_TTL_SECONDS`, at most 600 seconds).

Deployment requires migration `0010_whatsapp_delivery_policy` before starting
updated workers. **Still pending:** an end-to-end test with QR pairing and real
text/image delivery to a channel after deployment. Automated tests use disposable
PostgreSQL databases and do not send real messages.

## Multiple WhatsApp connections per user

Migration **`0016_whatsapp_connections`** adds owned connections and associates
destinations, delivery audits, send attempts, and group-creation receipts with
their responsible connection. Apply this migration before starting updated API
and workers. Deploy the API, posting workers, and frontend together; enable new
connections only after all posting workers run the updated version. Older workers
cannot route additional sessions correctly.

The existing session remains **`offers-user-{user_id}`**, labeled **Principal**.
Migration preserves pairing, saved policy, pauses, quotas, and pending work.
Additional sessions use server-generated
`offers-user-{user_id}-connection-{connection_id}`. Clients submit only an owned
numeric connection ID; arbitrary session names and operator credentials remain
unavailable to browsers. The installed WAHA edition/engine must support multiple
simultaneous sessions. Creating a connection record does not start pairing.

Primary policies and circuit state retain their existing tables for compatibility;
additional policies are stored on `whatsapp_connections`, with circuit state in
`whatsapp_connection_states`. This does not share primary pauses or quotas with
additional accounts. Send attempts store their connection and a persistent
`next_send_at`: random spacing is sampled **once per reserved attempt**, never
again during polling, broker redelivery, or process restart. Failed attempts also
consume spacing and quota. Advisory namespaces are 81273 for primary accounts,
81275 for additional connections, and 81274 for Telegram deduplication.

Each user's WhatsApp destination has one responsible connection. The API serializes
routing edits on the user row and rejects duplicate destinations across connections.
The panel supports adding/renaming/selecting accounts, their own QR/status,
connection-specific groups/channels, and connection-specific publication controls.
Transferring a destination pauses its publication; explicitly enable it after
checking membership/permissions on the new number. Queued deliveries keep their
original connection snapshot and are cancelled if routing changes before sending.
Deduplication, destination spacing and destination daily quotas survive transfer.
Disconnecting disables only that connection's destinations. Reconnecting or
clearing its circuit pauses does not enable destinations or replay old offers.
The dashboard requests `all_whatsapp_accounts=true` to aggregate owned connection
health; the legacy health endpoint mode continues to inspect the primary account.

### Editorial defaults for newly created connections

| Control | New connection default |
| --- | --- |
| Account spacing | Uniform random integer from 30 through 90 seconds |
| Destination spacing | At least 60 seconds |
| Account attempts | 90/hour and 600/24h, rolling windows |
| Additional destination quota | 100 attempts/24h, rolling window |
| Enabled groups | At most 6 per connection; configurable down to 1 |
| Posting window | 07:00–23:00, `America/Sao_Paulo` |
| Validity and channel burst collection | Existing 600-second ceiling and 60-second collection |

The 100/destination quota is our editorial choice (600 aggregate attempts divided
among six groups), **not a published Manda Boa quota**. Channels share account
limits and have their own destination quota, but do not count toward the six-group
activation limit. Disabled groups do not consume activation capacity. Existing
saved primary policy values are preserved; migration does not automatically
disable groups if an existing account exceeds the new activation limit.

Policy fields `account_interval_max_seconds` and `destination_max_per_day` accept
`null` for fixed spacing and no additional destination quota, respectively. Legacy
hour field names `start_hour_utc`/`end_hour_utc` remain wire-compatible; their hours
are now interpreted in `posting_timezone` (IANA name, default `UTC`). The window
cannot cross midnight; 0–24 permits all day. Configurations outside the window
defer only valid offers, without extending their original deadline.

These WhatsApp controls do not apply to Telegram. The shared operator validity
ceiling remains at most 600 seconds. Existing primary defaults in the earlier table
describe legacy policies without saved values, not additional-connection defaults.

### Operational references behind these choices

- Manda Boa's public page describes one offer/minute from 07:00–23:00 in Standard
  mode, configurable intervals/windows, and Telegram delivery as offers arrive:
  <https://mandaboa.com/blog/enviar-ofertas-no-whatsapp-e-telegram-ao-mesmo-tempo/>.
- Its consulted public pages do not specify an exact random inter-group delay
  range or a numeric default daily group quota. Do not attribute our 30–90s range
  or 100/day quota to Manda Boa.
- The 30–90s inter-group range appears in another supplier's operational guide:
  <https://blog.geekacademy.site/blog/anti-ban-whatsapp-mencionar-grupos-geekzap/>.
- Six enabled groups per number follows the developer guidance supplied by the
  user. These are configurable editorial controls, not proven ban-prevention limits.

Targeted multi-account validation:

```bash
python -m unittest tests.test_whatsapp_connections tests.test_whatsapp_delivery_policy tests.test_whatsapp tests.test_whatsapp_management tests.test_integration_health
```

Set `WAHA_POLICY_TEST_DATABASE_URL` to a disposable PostgreSQL database for migration,
concurrent activation, independent account locks, persisted random spacing,
destination quota transfer, and delivery-session routing tests. After deployment,
pair two distinct test numbers and validate real group/channel text/image delivery
through each number; automated tests do not contact WhatsApp.

## Automated tests

### Group and channel management

The **Destinations** screen (`/settings/destinations#whatsapp`) combines account
connection, a single group/channel management list, and collapsible publication
controls. The old `/whatsapp` route redirects here. Saved destinations remain
visible while disconnected; reconnecting never enables them automatically.
The dashboard checks connection health on entry, every minute while visible,
and when returning to the page. Disconnected sessions show an explicit alert
linking to `/settings/destinations#whatsapp`; upstream outages are shown as
unconfirmed status rather than confirmed disconnections. Checks never restart
sessions or enable destinations.
Removing a destination deletes routing only, not the group or channel in WhatsApp.
Category rules are shared with setup. Groups show member counts and
capacity; when WAHA provides no specific capacity, the 1,024-member reference is
identified in the UI. Missing counts are not treated as zero. Refreshing is explicit,
without frequent calls to `/groups/refresh`. Channels support follower-count
queries, with no group capacity limit applied. Opening the destinations page or
switching the selected connection fetches each administered channel's current
details, at most three requests concurrently. Failed detail requests preserve the
list entry and show a retry message; group-list failures do not block channels.
Manual refresh remains available; there is no recurring follower polling.

**Create next group** suggests the next available number in the series and opens
a form for explicit creation. It reuses the selected group's description,
categories, and optionally photo; uploading replaces the photo. New groups
default to admin-only messages. Participants are not copied or invited.
Editing the name/description/photo/permissions requires confirmed administrator
access in the user's session. Channels retain category/publication controls;
their profiles are edited in WhatsApp because the documented channel API does
not provide an update operation.

Migration `0015_whatsapp_group_management` records attempts by user and UUID
before external side effects. Retrying the same attempt does not create another
group. Partial failures keep the destination disabled and report which settings
need completion. An uncertain result requires checking the list before another
attempt. Existing delivery limits, validity, and rules remain unchanged.

Offline tests: `python -m unittest tests.test_whatsapp_management tests.test_whatsapp tests.test_destination_categories`.
After deployment, validate member counts, creation, photo reuse/upload,
description, and message restrictions with a test group on the installed WAHA engine.

Targeted validation:

```bash
python -m unittest tests.test_whatsapp_delivery_policy tests.test_whatsapp tests.test_backend_worker
```

To include concurrency tests, set `WAHA_POLICY_TEST_DATABASE_URL` to a disposable
PostgreSQL test database, never production. Each test creates and removes its own
schema. Pull request CI provides this database automatically.

## References

Consulted on October 15, 2026:

- [WAHA — How to Avoid Blocking](https://waha.devlike.pro/docs/overview/how-to-avoid-blocking/)
- [WAHA — Channels](https://waha.devlike.pro/docs/how-to/channels/)

The blocking guide primarily contains recommendations for private messages and
heuristic reports. Do not treat intervals, report counts, or supposed "reputation
points" as official rules or evidence of safety for channels.
