# Migrations and legacy compatibility

[Documentation index](README.md)

## Current schema

The backend applies `alembic upgrade head` on startup before its health check
becomes healthy. Alembic is the schema's source of truth, including Better Auth
tables. Do not run a separate migrator against those tables.

To apply migrations manually in the running environment:

```bash
docker compose exec backend alembic -c backend/alembic.ini upgrade head
```

In a local Windows Python environment:

```powershell
.\venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

Back up before upgrades and run API/workers compatible with the schema.
Relevant migrations are summarized below; this does not replace applying the
entire chain through `head`.

| Migration | Effect and notes |
| --- | --- |
| `0004_admin_source_catalog` | User roles and catalog; seeds the seven original sources once |
| `0005_platform_persistence` | Shared PostgreSQL persistence |
| `0007_delivery_details` | Title, store, and stage in history |
| `0008_better_auth` | Authentication tables and existing account links |
| `0009_whatsapp_destinations` | WhatsApp destinations; existing destinations remain Telegram |
| `0010_whatsapp_delivery_policy` | WhatsApp policies, audit records, and send coordination |
| `0011_encrypt_user_configs` | Encryption of existing settings |
| `0012_delivery_retention` | Index for history retention |
| `0013_destination_categories` | Per-destination categories; existing destinations accept all (`NULL`) |
| `0015_whatsapp_group_management` | Group creation receipts per user/attempt |
| `0016_whatsapp_connections` | Multiple WhatsApp connections and destination/attempt associations |
| `0017_delivery_affiliate_url` | Affiliate link in history |
| `0018_delivery_coupon` | Offer coupon in history, including pre-queue failures |

Full files live in [`backend/alembic/versions`](../backend/alembic/versions).

## Upgrades requiring special attention

### Better Auth

Migration preserves existing account IDs, settings, and roles. Older bcrypt
passwords keep working; new ones use Better Auth's default hash. NextAuth sessions
stop working and require a new login. Legacy emails that collide after conversion
to lowercase must be corrected before migration.

The old FastAPI routes `/auth/register`, `/auth/login`, and
`/auth/session/exchange` were removed. See [Security](security.md) for the current flow.

### Encrypted settings

Before `0011_encrypt_user_configs`, configure and preserve
`CREDENTIALS_ENCRYPTION_KEY`. The migration encrypts existing records in a single
transaction. Stop older instances during the upgrade: they cannot read ciphertext.
Rollback preserves encrypted data rather than converting it back to plaintext.

Older backups and row versions retained by PostgreSQL may still contain plaintext.
The migration does not rewrite backups or guarantee physical erasure.
See [Security](security.md) for key backups and rotation.

### Multiple WhatsApp accounts

Migration `0016` preserves the primary session, pairing, policies, pauses, quotas,
and pending work. Additional connections have independent sessions and state.
Update API, frontend, and all posting workers before enabling new connections:
older workers cannot route additional sessions correctly.

Saved primary policy values are preserved. Defaults for new connections do not
automatically reconfigure existing accounts. See [WhatsApp](whatsapp.md) and
the [technical specification](whatsapp-implementation.md).

### History

Records from before coupon/link persistence remain without those fields.
The original coupon cannot be reliably reconstructed. Apply migrations before
running API/workers that write the new fields.

## Importing an older SQLite installation

The platform uses PostgreSQL. The operator session and token usage history can
be imported from an older installation.

1. Stop the worker.
2. Make database/backend available and configure `DATABASE_URL` locally.
3. Run the importer through the project's Python environment.
4. Restart the worker.

PowerShell example:

```powershell
docker compose stop worker
docker compose up -d db backend
.\venv\Scripts\python.exe -m backend.import_sqlite data/offers.sqlite3
docker compose up -d worker
```

The import is transactional and repeatable for the same file. It does not modify
SQLite or overwrite existing PostgreSQL sessions. Source IDs identify one legacy
database: do not use this command to combine independent files.

Old offers are not imported: the older bot's global deduplication does not
identify the user required by the multi-tenant model.

## Older standalone runtime

Standalone code, including `run.py`, remains for compatibility. It uses SQLite
and publishes only to Telegram. It is not the web platform's entry point and
does not provide multi-tenant WhatsApp connections.

`DATABASE_PATH` and older settings such as `SOURCE_CHATS`, `TARGET_CHAT`, and
affiliate environment variables belong to that mode. In the current platform,
use `python -m backend.worker`, PostgreSQL, and dashboard-persisted settings.

For Awin in standalone mode, set `AWIN_PUBLISHER_ID` and `AWIN_ACCESS_TOKEN`.
Dashboard workers instead use each user's saved Awin configuration.
