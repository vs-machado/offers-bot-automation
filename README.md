# Telegram Offers Bot

Multi-tenant offers automation. Shared worker listens to the platform Telegram source catalog through Telethon, extracts supported product links, generates each user's affiliate links, and posts through platform bot to that user's enabled destinations.

## Runtime architecture

```mermaid
flowchart LR
    UI[Dashboard setup] --> DB[(PostgreSQL)]
    DB --> W[Shared worker]
    S[Public Telegram sources] --> W
    W --> P[Offer parser]
    P --> A[User affiliate client]
    A --> B[Platform Telegram bot]
    B --> D[User destinations]
```

- Dashboard saves `source_chats`, destinations, and Amazon/Shopee/Mercado Livre/AliExpress credentials in PostgreSQL.
- Worker reloads persisted config every 30 seconds.
- One operator-owned Telethon account receives catalog messages and fans them out to subscribed users. Users select catalog groups and cannot add their own sources.
- Real Telegram post IDs plus PostgreSQL records provide per-user deduplication.
- Destination posting uses one platform bot. Users do not create their own bots or Telegram sessions.

## Coolify with a separate PostgreSQL resource

Use only `docker-compose.coolify.yml` as the Docker Compose Location in Coolify.
This file does not create PostgreSQL or publish ports directly on the host.
`docker-compose.yml` and its override remain intended for local development.

1. Create and start a PostgreSQL resource on the same server. Configure its user,
   password, database, and backups in the database resource.
2. Identify the Docker network that PostgreSQL is connected to and set
   `DATABASE_NETWORK` to that name. The network must exist before deployment.
   Application services join it while retaining their own internal network
   for Redis and frontend-to-backend communication.
3. Copy the internal host, user, password, and database from the connection provided by Coolify:

```dotenv
DATABASE_NETWORK=postgres_network_name
DATABASE_URL=postgresql+asyncpg://user:password@internal-host:5432/offers_db
AUTH_DATABASE_URL=postgresql://user:password@internal-host:5432/offers_db
BETTER_AUTH_URL=https://app.example.com
BETTER_AUTH_SECRET=random_secret_with_at_least_32_characters
```

Both URLs must point to the same database. URL-encode special characters in the
username and password. Do not use `localhost` as the database host.
`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` do not configure the
separate resource; its credentials are managed by Coolify.

4. Assign the HTTPS domain to the frontend on internal port 3000. If using QR
   pairing for the Telegram operator account, provide restricted access to the
   worker on port 8081 during setup. Backend and posting do not need domains.
5. Deploy and check the backend logs: migrations run before it becomes healthy,
   and the other services wait for that initialization.

SMTP is optional for registration and login but required for password recovery.
If the previous database contains data, import a backup before switching connections.
Changing the URLs does not transfer data between databases.

## Parsing

Qwen 3.7 Flash (`qwen/qwen3.7-flash`) through OpenRouter is the primary structured parser. DeepSeek V4 Flash and Gemini 2.5 Flash Lite use direct provider APIs as fallbacks. Regex parser runs when AI credentials are absent or AI parsing fails.

The existing LLM parsing call identifies unrelated source advertising by meaning
and returns exact original substrings in `source_advertising_spans`. Code removes
only verbatim, unambiguous matches; no phrase or bot-username detection rules are
used. The same cleanup applies when Shopee redemption offers or multi-link
AliExpress offers reuse source formatting. The model is instructed to preserve
product/coupon links, prices, store coin discounts and advertising disclosures.
Without LLM results, source text is preserved rather than guessing what to remove.
Cleanup lives in `offers_bot/source_cleanup.py` and applies only to incoming
content; future platform-owned alert-bot promotions should be appended afterward.

URL routing and affiliate conversion support:

- Mercado Livre
- Amazon Brazil
- Shopee Brazil
- AliExpress

## Setup

1. Create platform bot with `@BotFather` and copy token.
2. Copy `.env.example` to `.env` and set platform infrastructure/auth secrets. User settings and affiliate credentials do not belong in `.env`.
3. Start stack:

```powershell
docker compose up --build
```

4. Register/login in frontend.
5. Complete dashboard setup:

   - add platform bot to destination group/channel;
   - grant bot permission to post messages and photos;
   - save destination chat ID;
   - save credentials for one or more affiliate providers;
   - select Telegram source groups from the platform catalog.

Worker begins processing after next 30-second refresh.

### Categories per destination

Setup and **Settings → Destinations** list registered Telegram and WhatsApp groups
and channels together under **Categorias por grupo ou canal**. Each destination
can receive all offers or only selected categories: technology, home, clothes and
accessories, other products, and generic coupons. Uncheck a category to block it
only in that destination, then select **Salvar categorias**. Select **Todas as
ofertas** for an unrestricted destination. An empty selection receives no offers.

Product-specific coupons follow the product category; standalone coupons use the
separate coupon selection. Products without a recognized category use `other`,
including regex-only parsing when AI classification is unavailable. Rules apply
independently across both platforms and are rechecked before queued deliveries.
Changing rules does not replay previously processed offers.

Migration `0013_destination_categories` must run before starting updated backend
and workers. Existing destinations keep receiving all offers (`categories = NULL`).
The destination API accepts `categories: null` for all, a category array for a
selection, or `[]` for none. Allowed keys: `tech`, `home`, `clothes`, `other`, `coupon`.

## Database migrations

Backend runs `alembic upgrade head` during startup.

Run migrations manually from repository root with project virtual environment:

```powershell
.\venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

## Credential encryption

User configurations (`user_configs.config_data`) are fully encrypted with
Fernet (`cryptography`): AES-128-CBC + HMAC-SHA256, with a random IV.
The authenticated payload also identifies the user and configuration type,
preventing an encrypted record from being reused for another user or provider.

Before the first deployment of this version, generate a key **once**:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the result as `CREDENTIALS_ENCRYPTION_KEY` in Coolify secrets/environment
variables or in the local `.env`. Compose passes this key only to the backend
and worker. The key is required, including in development; there is no default
key or automatic generation at startup. Keep a secure backup of the key
separate from database backups. Losing it makes credentials unrecoverable.

Migration `0011_encrypt_user_configs` encrypts existing records in a single
transaction before the backend becomes healthy. Back up the database and stop
old instances during the upgrade: older versions cannot read ciphertext.
Rolling back the migration preserves encrypted data. Old backups and row
versions retained by PostgreSQL may still contain plaintext; the migration
does not rewrite backups or guarantee physical erasure of that data.

The API returns `********` instead of cookies, tokens, keys, and secrets. When
updating or testing an integration, this marker reuses the saved value only for
the authenticated user/provider. To replace a credential, submit its new value.
The frontend never receives the encryption key or stored secret.
Traffic must remain protected by HTTPS.

### Key rotation

1. Generate a new key. Set it in `CREDENTIALS_ENCRYPTION_KEY` and retain the old
   key in `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS` (a comma-separated list).
2. Recreate the backend and worker with the same keys. Wait for all old instances
   to stop; new writes will use the new key.
3. Re-encrypt existing records with the command below. This is transactional:
   any invalid record or incorrect key aborts the operation without partial writes.

   ```bash
   docker compose exec backend python -m backend.app.core.db.credential_rotation
   ```

   In Coolify, run `python -m backend.app.core.db.credential_rotation` in the
   backend service terminal.

4. After success, remove `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS` and recreate both
   services. Keep old keys in a separate backup for as long as database backups
   depend on them.

Infrastructure secrets (WAHA, Telegram, AI, database, and authentication) remain
managed through the environment/secret manager, outside the configuration database.

## Configuration boundaries

User-owned business configuration is stored only in PostgreSQL through authenticated `/users/me` endpoints:

- destination chat IDs and enabled state;
- selected source chats;
- affiliate tags, API keys, cookies, CSRF tokens, and tracking IDs;
- optional browser resolver settings if later exposed by dashboard/API.

`.env` contains platform infrastructure only:

- shared `TELEGRAM_BOT_TOKEN`;
- database/auth/OAuth secrets;
- optional shared AI parser credentials.

The operator reader uses `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and its shared session/QR settings. `SOURCE_CHATS`, `TARGET_CHAT`, and affiliate environment variables are legacy CLI settings; the shared worker takes catalog subscriptions, destinations, and affiliate settings from PostgreSQL.

## Provider credentials

### Mercado Livre

Save affiliate tag, authenticated cookie header, and CSRF token in dashboard. Cookies expire; update provider config when API begins returning 401/403.

### Amazon

Save only your Amazon Associates tag (for example, `yourtag-20`) in setup or settings. Product links use expanded Amazon URLs with your tag, not SiteStripe short links. Cookies, marketplace ID, and SiteStripe access are not required. Validation checks only the tag format; it does not authenticate with Amazon or confirm account ownership, eligibility, or commissions.

Amazon affiliate link generation through an API is planned but not yet implemented. The current flow expands short links, removes previous affiliate tracking, and adds the user's tag to the destination URL.

Amazon does not use Playwright or fetch product images. Posts reuse source-message media when available; otherwise they are published without an image.

### Shopee

Save Affiliate Open Platform app ID and app secret.

### AliExpress

Save Affiliate API app key, app secret, and optional tracking ID.

## Local quality checks

### CI for pull requests targeting master

There is no pre-commit hook. Local commits do not run repository-wide checks or
the test suite. The `.github/workflows/pr-quality.yml` workflow runs Ruff,
ESLint (with no warnings), TypeScript, and `python -m unittest discover tests`
when a pull request targeting `master` is opened, updated, or reopened. New
pushes to the PR cancel outdated runs. Pushes without a PR do not trigger this
workflow. Checks do not modify files; the default checkout tests the result of
merging the PR into its target branch.

Branch protection for `master` must require a pull request and a passing
`quality` status check, with the branch up to date before merging, including
for administrators. Additional approval from another reviewer is not required.
Deployment remains a post-merge step; the workflow does not merge or deploy
automatically. In other repositories, configure these rules in GitHub: the
workflow file alone does not block merging.

In clones that still have the old hook installed, remove it once:

```powershell
.\venv\Scripts\python.exe -m pre_commit uninstall
```

During development, run targeted checks on changed files when needed; do not
run the full suite as a commit prerequisite. Install tools with
`python -m pip install -r requirements-dev.txt` and `npm --prefix frontend ci`.
Manual examples:

```powershell
.\venv\Scripts\ruff.exe format path/to/file.py
.\venv\Scripts\ruff.exe check --fix --ignore-noqa path/to/file.py
npm --prefix frontend run lint
```

ESLint also checks canonical Tailwind 4 classes using
`better-tailwindcss/enforce-canonical-classes`, with the theme from `app/globals.css`.
Ruff checks suppressions with `RUF100`; CI uses `--ignore-noqa`. ESLint does not
allow rule-disable comments. Fix the cause of diagnostics rather than hiding
problems with suppressions.

## Troubleshooting

- Destination save fails: confirm platform bot is administrator and can post messages/photos.
- User stays inactive: confirm enabled destination, at least one complete affiliate provider, and saved source selection all exist.
- Source returns no messages: check the operator Telethon account can access every catalog group.
- New config is not active: allow one 30-second worker cycle.
- AI keys missing: regex parsing continues automatically.

### Shared Telegram reader

Set `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` for the operator account. Supply `TELEGRAM_SESSION_STRING` or set `TELEGRAM_PHONE` and scan the QR served on port 8081. Operator sessions, LLM accounting, catalog sources, user destinations and affiliate credentials are persisted in PostgreSQL. Docker mounts `data` for temporary media and legacy import files. Set `OPENROUTER_API_KEY` to enable the primary Qwen parser.

### Platform persistence migration

Set `DATABASE_URL` according to `.env.example`. The default local port is 5434;
inside Docker, services use `db:5432`. Install the updated dependencies.
The backend applies migration `0005_platform_persistence` at startup.

To import the operator session and token usage history from a previous installation,
stop the worker and run the following with the database and backend available:

```powershell
docker compose up -d db backend
.\venv\Scripts\python.exe -m backend.import_sqlite data/offers.sqlite3
docker compose up -d worker
```

The import is transactional and can be repeated using the same file. It does not
modify SQLite or overwrite existing sessions in PostgreSQL. Source IDs identify
a single legacy database; do not use this command to combine independent SQLite
files. Offers from the old bot are not imported: their global deduplication does
not identify the user required by the platform model.

The standalone legacy bot remains compatible with SQLite. The platform uses
PostgreSQL; `DATABASE_PATH` is used only for legacy mode and imports.

### Authentication with Better Auth

Registration, password login, Google sign-in, and sessions are managed by Better
Auth in Next.js (`/api/auth/*`). The old FastAPI routes `/auth/register`,
`/auth/login`, and `/auth/session/exchange` have been removed. The proxy validates
the cookie with Better Auth and forwards the opaque session to FastAPI, which
checks its validity in PostgreSQL on every request. Administrator roles remain
in `users.role`, without relying on variables sent by the browser.

Migration `0008_better_auth` creates the authentication tables and links existing
accounts without changing their IDs, settings, or permissions. Existing bcrypt
passwords continue to work; new passwords use Better Auth's default hash.
NextAuth sessions stop working, requiring users to sign in again. The migration
is managed by Alembic; do not run Better Auth's migration CLI against the same
tables. Legacy email addresses that collide after conversion to lowercase must
be corrected before migration.

Set `BETTER_AUTH_SECRET` (at least 32 random characters), `BETTER_AUTH_URL`
(a trusted public URL), and `AUTH_DATABASE_URL` (PostgreSQL). In Docker, Compose
configures the internal database URL. To run Next.js locally, put these variables
in `frontend/.env.local`. Register the callback
`${BETTER_AUTH_URL}/api/auth/callback/google` with Google.
Automatic linking of accounts with the same email address is disabled.

### Password recovery

The **Forgot password** link opens `/forgot-password`. Better Auth generates a
temporary token whose identifier is stored as a hash and which expires after
15 minutes. The email points to `/reset-password`, with the token in the URL
fragment to keep it out of access logs. The user enters the new password twice;
after the change, all old sessions are revoked and the user must sign in again.
The request response is the same for known and unknown email addresses.

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM`
on the Next.js server. For implicit TLS, use `SMTP_SECURE=true` (usually port
465); for STARTTLS, use `SMTP_SECURE=false` and `SMTP_REQUIRE_TLS=true` (usually
port 587). Without SMTP configured, the screen reports that recovery is
unavailable. The server also sends a notification after a password change.
SMTP data and recovery links are not recorded in application logs.

Rate limits are stored in PostgreSQL and shared across frontend instances.
Recovery requests allow up to three attempts per minute per IP; login,
registration, and password reset allow five. The authentication database must be
available before the frontend starts. Run the migration through the backend;
in Docker, the frontend waits for the backend health check.

### Settings after the setup tutorial

The authenticated `/settings` route remains available through the Settings,
Groups, and Affiliates menus on desktop and mobile. Users can add, edit, disable,
and remove destinations, select groups from the administrator-managed catalog,
and update or remove Amazon, Mercado Livre, Shopee, and AliExpress integrations.
Each change uses the user's own protected APIs. Enabling a destination checks the
bot's permissions. Saved credentials are masked in the form; saving does not
validate authentication with the store.

### Affiliate credential validation

The **Validate credentials** button is available for all four stores in the
tutorial and in `/settings`. It calls the authenticated route
`POST /users/me/affiliate-credentials/validate` with the data entered in the form,
even before saving it. The check generates a reference link for the store
without posting to Telegram or persisting credentials or test links.

Results are passed, credentials rejected, or inconclusive. Timeouts, captchas,
rate limits, and API failures are not treated as invalid credentials.
Mercado Livre requires the full link to an eligible product with an MLB ID;
the address is sent only to the fixed affiliate API and is not visited by the
backend. The other stores use their home pages as references.

Changing the data hides the previous result. Validation confirms that a link can
be generated at that moment; it does not prove tag ownership, future commissions,
or eligibility of every offer. Saving remains a separate action. Responses
contain only the result, reason, and timestamp, never secrets or the store's raw
response. External requests have a total timeout of 20 seconds, with a limit of
eight concurrent validations per process and one per user.

### Delivery history

The dashboard calls `GET /users/me/deliveries`, which requires authentication and
is limited to the user's own records. It includes pagination, filtering by
result, and refreshes every 30 seconds. Displayed totals come from the database,
not sample data. History is also shown while setup is incomplete.

The worker automatically deletes `promotion_deliveries` records older than
60 days on startup and every 24 hours afterward. Cleanup commits batches of 1,000
records and leaves `processed_offers` and deduplication rules unchanged. Failures
are logged and retried after 30 seconds without interrupting offer ingestion.
The `worker` service must be running; records can remain until the next daily
cleanup. Migration `0012_delivery_retention` adds a creation-time index for this
routine.

Migration `0007_delivery_details` adds a title, store, and stage to new records.
Reasons are classified and displayed in Portuguese: authentication, API key,
bot permissions, sending limits, connectivity, API failure, unavailable queue,
and expiration. Raw responses, cookies, tokens, and keys are not sent to the
browser. When the response does not identify the cause, history shows a generic
failure without assuming that the key is invalid.

Link conversion failures are recorded per destination before queueing.
An LLM failure recovered through fallback is not treated as a failed post.
A reader disconnection prevents new offers from being received and therefore
does not produce per-offer records; diagnosis depends on operational logs.

### Offer posting queue

The listener prepares links and publishes one task per destination to Redis.
The `posting` service executes these tasks with Celery. The default and maximum
lifetime is 600 seconds from the original Telegram message timestamp, including
processing; set `PROMOTION_TTL_SECONDS` (1–600) in the listener and API environment.
Expired offers are discarded. There is no Celery Beat: sending is triggered by
messages, without periodic scheduling.

```powershell
docker compose up -d --build db redis backend worker posting
```

Redis does not write snapshots or AOF. Restarting Redis loses pending tasks;
they are not rebuilt from the database. Memory is limited to 256 MB with
`noeviction`: reaching the limit causes task publication to fail rather than
silently evicting messages. `POSTING_CONCURRENCY` controls sending processes
(default: 2).

`promotion_deliveries` records state per user and destination. Before sending,
the consumer confirms that the destination is still registered and enabled.
A duplicate task does not repeat a send that has already started. Up to two
retries are allowed for connection failures before sending and 429 responses,
respecting `retry_after` and the remaining lifetime. Ambiguous failures are marked
as `uncertain`, without automatic retries. Telegram does not provide an
idempotency key for this send; the system prioritizes avoiding duplicates and
may lose a post after a crash.

Local images are copied into the queue message before the listener cleans them
up, with an 8 MB limit; larger images are omitted. Image URLs are sent to Telegram.
An explicit photo rejection (400) allows a text-only attempt.

History does not contain offer content or act as a persistent queue. After Redis
data loss, `queued` or `retrying` records may remain in the database; once
`expires_at` passes, they should be interpreted as expired. A `sending` record
without completion indicates an uncertain outcome. Do not automatically resend
these records.

Local execution requires Redis to be reachable at `REDIS_URL`. On Windows, use
Docker for the Celery consumer; for development without Docker, `--pool=solo`
avoids the process pool, but Celery does not officially support Windows.

### Administrator access and source catalog

Public registration is temporarily disabled by default. The server-only flag
`DISABLE_PUBLIC_REGISTRATION=true` blocks new email/password and Google accounts,
but existing accounts can still sign in and recover passwords. Set it to `false`
and restart/redeploy the frontend to reopen registration. This flag does not grant
admin roles or block existing non-admin accounts from signing in. New administrator
accounts must be registered while signup is open, then promoted using the CLI below.

The `/admin/source-groups` screen and every `/admin/source-groups` API operation require the `admin` role. The API checks the current database role on every request; changing or revoking a role applies even to existing tokens. Public registration always creates a `user` account.

Apply migration `0004_admin_source_catalog` (automatically on backend startup). It gives existing users the `user` role and seeds the seven original Telegram sources once. Register your administrator account, then promote it through trusted operator access:

```powershell
.\venv\Scripts\python.exe -m backend.set_admin admin@example.com
# Revoke administrator access:
.\venv\Scripts\python.exe -m backend.set_admin admin@example.com --role user
```

With Docker, run `docker compose exec backend python -m backend.set_admin admin@example.com` after the account is registered. No public API grants administrator roles.

Administrators can add, edit, enable, disable, and remove public Telegram groups. Only enabled groups are selectable by users and accepted by configuration endpoints. The shared Telethon reader refreshes catalog changes every 30 seconds without restarting; removed or disabled groups stop delivering offers. Saved selections for unavailable groups stay stored but inactive until the group becomes available again. An empty catalog disables all sources. The operator Telegram account must be able to join/read each source.

### WhatsApp destinations (WAHA)

Implementation requirements and channel delivery recommendations:
[`WAHA_IMPLEMENTATION.md`](WAHA_IMPLEMENTATION.md).

Users can connect their own WhatsApp account in **Settings → Publish to WhatsApp**,
scan the QR from **WhatsApp → Linked devices**, and select a group or channel from their account.
The same QR and destination picker is available in the setup tutorial. Telegram
group/channel configuration remains available alongside WhatsApp in both screens.
Each user receives a separate WAHA session (`offers-user-<application-user-id>`).
The API derives that name from the authenticated identity, never from browser input.
The connected account must participate in the group and have permission to send;
only WhatsApp channels with the `OWNER` or `ADMIN` role are selectable. If the WAHA
engine cannot list channels, the interface reports this while keeping groups available.
Messages are sent in that account's name, with the same prepared affiliate text/photo.
WhatsApp delivery adapts shared offer Markdown automatically: `**bold**` becomes
`*bold*`, `__italic__` becomes `_italic_`, and `~~old price~~` becomes `~old price~`.
Labeled Markdown links become a label followed by the visible URL, preserving
affiliate parameters. Conversion applies to both text messages and image captions.
Coupon codes retain their individual triple-backtick monospace spans. This is
formatting, not a copy button: long-press selection/copy behavior depends on the
recipient's WhatsApp client and must be checked on the devices in use.
See [WhatsApp text formatting](https://www.twilio.com/docs/whatsapp/message-features#formatting-in-whatsapp-messages)
and [WAHA text/image payloads](https://waha.devlike.pro/docs/how-to/send-messages/).
Source selection remains the platform's Telegram catalog: each user's selected sources
feed all their enabled Telegram and WhatsApp destinations through the same queue.
Manage each destination independently in Settings; disabling one leaves the others active.
Group and channel discovery fail independently, so an unavailable listing does not
block the other destination type. After unlinking and pairing again, explicitly
enable saved destinations in Settings to resume their deliveries.

Operator setup:

1. Run WAHA with persistent session storage, API-key authentication, and support for
   multiple sessions and `sendImage`. The installed WAHA `2026.9.2` WEBJS build has
   these implementations; older builds may have different edition restrictions.
2. Make WAHA reachable from backend and posting containers. For the existing Coolify
   installation, attach its service to the external `coolify` Docker network with
   alias `waha`. Declare the network in WAHA's Compose file so recreation preserves it:

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
       name: coolify
   ```

3. Set `WAHA_BASE_URL=http://waha:3000` and `WAHA_API_KEY=<operator WAHA API key>`
   in Offers Bot's Coolify environment, then deploy. Do not use `localhost`: from
   a container it points to that container, not WAHA. Backend startup applies
   migration `0009_whatsapp_destinations`, keeping existing destinations on Telegram.

WAHA credentials stay server-side; the browser receives only status, its own QR,
and group names/IDs. Pairing QR responses use `Cache-Control: no-store`. Unlinking
disables the user's WhatsApp destinations; queued jobs recheck enabled state and
ownership before delivery. WhatsApp sends use the existing Celery queue and expiry
rules. Text/photo sends with uncertain results are not automatically replayed.
The standalone legacy bot remains Telegram-only; WhatsApp is part of the multiuser
backend worker. Validate a real QR connection and test group after deployment.
