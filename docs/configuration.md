# Configuration

[Documentation index](README.md)

## Configuration boundaries

| Location | Settings |
| --- | --- |
| Environment / secret manager | Database, authentication, platform Telegram, WAHA, and AI providers |
| Dashboard / PostgreSQL | Selected sources, destinations, categories, and each user's affiliate credentials |
| Dashboard / PostgreSQL | WhatsApp connections, routing, limits, and publication pauses |

Use [`.env.example`](../.env.example) as the starting reference. Do not put user
affiliate tags, cookies, or keys in the shared worker's environment. Authenticated
settings are saved through `/users/me` endpoints.

## Database and internal services

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Asynchronous SQLAlchemy URL: `postgresql+asyncpg://...` |
| `AUTH_DATABASE_URL` | Better Auth PostgreSQL URL: `postgresql://...`, pointing to the same database |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL initialization in local Compose |
| `POSTGRES_PORT` | Local PostgreSQL host port; default `5434` |
| `DATABASE_NETWORK` | External Docker network shared with PostgreSQL in Coolify |
| `REDIS_URL` | Celery broker; set internally by Compose |
| `API_BASE_URL` | API address used by the Next.js server; `http://backend:8000` in Docker |
| `FRONTEND_PORT`, `BACKEND_PORT`, `QR_AUTH_PORT` | Local ports; defaults `3000`, `8000`, and `8081` |

Local Compose replaces database URLs with internal URLs using `db:5432`.
`DATABASE_URL` and `AUTH_DATABASE_URL` in `.env.example` are for host access.
In Coolify, both URLs must be supplied explicitly.

The Coolify Compose file does not create PostgreSQL. `POSTGRES_*` does not
change the external resource's credentials. Do not use `localhost` to reach
another container.

## Authentication and encryption

| Variable | Purpose |
| --- | --- |
| `BETTER_AUTH_URL` | Trusted public frontend URL; HTTPS in production |
| `BETTER_AUTH_SECRET` | Random secret with at least 32 characters |
| `DISABLE_PUBLIC_REGISTRATION` | Default `true`: blocks new accounts while preserving existing login and recovery |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional Google sign-in |
| `CREDENTIALS_ENCRYPTION_KEY` | Required persistent Fernet key used by backend and worker |
| `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS` | Comma-separated previous keys, used only during rotation |

The Google callback is `${BETTER_AUTH_URL}/api/auth/callback/google`.
When running Next.js directly on the host, supply authentication variables in
`frontend/.env.local`. See [Security](security.md) for generation and rotation.

## Email

| Variable | Purpose |
| --- | --- |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server; default port `587` |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Authentication and sender |
| `SMTP_SECURE` | `true` for implicit TLS, usually on port `465` |
| `SMTP_REQUIRE_TLS` | `true` to require STARTTLS when `SMTP_SECURE=false` |

SMTP is optional for login/registration and required for password recovery.
These variables are consumed by the Next.js server.

## Telegram and WhatsApp

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Shared bot for Telegram destinations |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Operator reader's Telegram application |
| `TELEGRAM_SESSION_STRING` | Preauthenticated reader session |
| `TELEGRAM_PHONE` | Alternative for QR reader authentication |
| `WAHA_BASE_URL` | WAHA address reachable by application services, such as `http://waha:3000` |
| `WAHA_API_KEY` | Operator WAHA key, kept server-side |

WhatsApp sessions are derived from the user's connections, not a global variable
or an arbitrary browser-supplied name. See [WhatsApp](whatsapp.md).

## Extraction and publishing

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Ling and Qwen structured extraction |
| `GEMINI_API_KEY` | Gemini fallback through Google's API |
| `OPENROUTER_CACHE_ENABLED` | Cache control; default `true` |
| `OPENROUTER_CACHE_TTL` | Optional parser setting; not forwarded by the current Compose files |
| `PROMOTION_TTL_SECONDS` | Maximum offer lifetime; `1–600`, default `600` |
| `POSTING_CONCURRENCY` | Celery posting processes; default `2` |

Without AI keys, regex parsing continues. WhatsApp policies can shorten validity
and limit sends without exceeding the operator's ceiling.

## Compatibility

`DATABASE_PATH`, `SOURCE_CHATS`, `TARGET_CHAT`, and older affiliate environment
variables belong to the standalone/SQLite runtime. They do not configure the
multi-tenant runtime. See [Migrations and legacy](migrations.md).
