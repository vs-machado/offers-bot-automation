# WhatsApp and WAHA

[Documentation index](README.md)

## Overview

WhatsApp is a publication destination in the multi-tenant platform, alongside
Telegram. Offers come from the same Telegram catalog with user-specific
affiliate links. WAHA provides account connections, group/channel discovery and
management, and text/image delivery. It is provisioned separately from the
Offers Bot Compose files.

## Operator setup

1. Run WAHA with persistent storage, API-key authentication, and support for
   multiple sessions, channels, and `sendImage`. WEBJS `2026.9.2` was the reference
   for the documented installation; check your version/edition's capabilities.
2. Ensure backend, worker, and posting can reach WAHA.
3. Configure `WAHA_BASE_URL` and `WAHA_API_KEY` server-side and deploy.
4. Verify QR pairing, discovery, and real text/image delivery to test destinations.

In Coolify, one option is to attach WAHA to the same external network declared
as `DATABASE_NETWORK`, with alias `waha`. Example **in WAHA's Compose file**,
replacing the network name with your installation's:

```yaml
services:
  waha:
    networks:
      default:
      offers:
        aliases: [waha]
networks:
  offers:
    external: true
    name: postgres_network_name
```

Then configure:

```dotenv
WAHA_BASE_URL=http://waha:3000
WAHA_API_KEY=operator_api_key
```

Declare the network in Compose so recreation preserves it. Do not use
`localhost` to reach WAHA from another container.

## Accounts, QR pairing, and routing

Management lives at `/settings/destinations#whatsapp`, also integrated into
setup. `/whatsapp` redirects to that screen.

Each user can add, rename, and select connections. The primary keeps
`offers-user-{user_id}`; additional connections use
`offers-user-{user_id}-connection-{connection_id}`. The server constructs these
names. The browser submits only an owned connection ID. Creating a connection
does not start pairing automatically.

Scan the QR through **WhatsApp → Linked devices**. The WAHA key stays server-side;
the browser receives status, its own QR, and destination data. QR responses use
`Cache-Control: no-store`.

- Groups must allow the connected account to send messages.
- Channels are selectable only with the `OWNER` or `ADMIN` role.
- Group discovery failures do not block channels, and vice versa.
- Each destination has one responsible connection per user and cannot be
  duplicated across that user's connections.
- Transferring a destination pauses publication. Check permissions and explicitly
  enable it on the new account. Tasks for the previous route are cancelled.
- Disconnecting disables only that connection's destinations. Reconnecting or
  clearing pauses does not enable destinations or recover old offers.

The dashboard checks health on entry, every minute while visible, and on return
to the page. Upstream outages appear as unconfirmed status; checks do not restart
sessions or enable destinations.

## Groups and channels

The list supports search, filtering, and pause/resume actions. Saved destinations
remain visible when discovery is unavailable.

Groups show member counts and capacity; without WAHA-specific capacity, the
screen labels the **1,024-member** reference limit. Unknown counts are not treated
as zero. Channels show follower counts when available, without a group capacity
limit. Refreshing these counts is explicit.

**Create next group** suggests the next available number in the series and opens
a draft. For example, groups `#2` and `#4` suggest `#5`. Users confirm creation
and can inherit description, categories, and photo, or replace the image.

Users can also create a group from scratch and edit administered groups' names,
descriptions, photos, and permissions. Photos accept JPEG/PNG/WebP up to 5 MB.
New groups default to admin-only messages. Participants are not copied or invited.

Creation attempts have per-user UUID receipts to prevent duplicates during
browser retries. If the outcome is uncertain, refresh the list before creating
again. Partial failures keep the destination disabled and identify unfinished settings.

Channel profiles are edited in WhatsApp itself; the documented channel API has
no equivalent update operation. Removing a destination in the dashboard deletes
routing only, not the WhatsApp group/channel.

## Publication policies

Each connection has independent limits and pauses. Groups and channels on the
same connection share account volume. Categories are destination-specific and
rechecked before delivery.

### Defaults for new connections

| Control | Default |
| --- | --- |
| Account interval between attempts | Uniform random integer from 30 to 90 seconds |
| Minimum destination interval | 60 seconds |
| Account attempts | 90/hour and 600/24h, rolling windows |
| Additional destination quota | 100 attempts/24h |
| Enabled groups | Up to 6 per connection, configurable downward |
| Posting window | 07:00–23:00, `America/Sao_Paulo` |
| Maximum lifetime | 600 seconds, also capped by the operator |
| Channel burst | 6 eligible offers in 60 seconds; retain the 5 newest pending offers |
| Initial channel offer collection | 60 seconds |

Channels share account quotas and have destination quotas, but do not count
toward the six-group limit. Disabled groups do not consume that capacity.
Failed attempts also consume quota and spacing.

Older primary-account policies preserve saved values. Legacy defaults include
different fixed intervals and an all-day UTC window; the
[technical specification](whatsapp-implementation.md) distinguishes these cases.
Do not interpret the table as an automatic update to existing accounts.

The posting window uses an IANA timezone and cannot cross midnight; `0–24`
allows all day. Deferral due to windows, limits, or collection does not extend
the original lifetime. These values are product editorial policies, not official
limits or guarantees against WhatsApp restrictions.

### Deduplication, pauses, and recovery

- Product/variation and price are deduplicated per destination over 30 minutes.
  Price changes allow a new publication.
- Bursts discard older pending offers; duplicates and expired offers do not
  occupy the five slots. Discarded offers do not return through retries.
- Permission/destination rejection pauses the destination; authentication, 429,
  and repeated failures pause the account. The default consecutive-failure threshold
  is three.
- Default pauses last 15 minutes; 429 respects at least 60 seconds or `Retry-After`,
  whichever is longer.
- Uncertain send outcomes are not automatically retried.
- Clearing a pause does not enable destinations, resend offers, or remove the
  need to fix the underlying cause.

PostgreSQL locks and persisted reservations coordinate concurrency. Random
spacing is sampled once per reserved attempt, not again during polling or
restart. These policies do not delay or suppress Telegram destinations.

## Formatting

Delivery adapts formatting in both message text and captions:

| Shared format | WhatsApp |
| --- | --- |
| `**bold**` | `*bold*` |
| `__italic__` | `_italic_` |
| `~~old price~~` | `~old price~` |
| Labeled Markdown link | Label followed by visible URL, preserving parameters |

Coupons retain individual triple-backtick monospace spans. This does not create
a copy button: selection/copy behavior depends on the recipient's WhatsApp client.

## Validation and technical reference

Automated tests mock WAHA and do not send real messages. After deployment,
validate two numbers, isolation, groups/channels, photos, permissions, transfers,
and policies on the installed engine.

See [Development](development.md) for targeted tests and the
[technical specification](whatsapp-implementation.md) for complete requirements,
limits, migrations, and validation criteria.
