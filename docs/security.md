# Authentication and credential protection

[Documentation index](README.md)

## Better Auth

Registration, password login, Google sign-in, and sessions are managed by Better
Auth in Next.js at `/api/auth/*`. The proxy validates the cookie and forwards
the opaque session to FastAPI, which checks validity in PostgreSQL on every
request. The administrator role lives in `users.role`, not browser variables.

Configure `BETTER_AUTH_SECRET` with at least 32 random characters,
`BETTER_AUTH_URL` with the trusted public URL, and `AUTH_DATABASE_URL` for the
same database as `DATABASE_URL`. The frontend waits for backend migrations.
Do not run Better Auth's migration CLI against these tables: Alembic owns the schema.

For Google, register `${BETTER_AUTH_URL}/api/auth/callback/google`.
Automatic account linking by matching email is disabled. Use HTTPS in production.

### Public registration

`DISABLE_PUBLIC_REGISTRATION=true` is the default. It blocks new password and
Google accounts, not existing login or recovery. Changing the flag requires
restarting/redeploying the frontend and does not grant administrator roles.
See [Operations](operations.md) for CLI promotion.

### Password recovery

The workflow starts at `/forgot-password`. The token expires after 15 minutes;
its identifier is stored as a hash. The link opens `/reset-password` with the
token in the URL fragment to keep it out of access logs. The user confirms the
new password twice, old sessions are revoked, and a new login is required.

The request response is identical for known and unknown email addresses.
The server also sends a notification after a password change. SMTP data and
recovery links are not recorded in application logs.

On Next.js, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and
`SMTP_FROM`. Use implicit TLS with `SMTP_SECURE=true` (usually port 465) or
STARTTLS with `SMTP_SECURE=false` and `SMTP_REQUIRE_TLS=true` (usually 587).
Without SMTP, the screen reports recovery as unavailable.

Rate limits are stored in PostgreSQL and shared across frontend instances:
up to three recovery requests per minute per IP; login, registration, and reset
allow five. The authentication database must be available.

## Encrypted settings

`user_configs.config_data` is fully encrypted with Fernet (`cryptography`):
AES-128-CBC + HMAC-SHA256 and a random IV. The authenticated payload includes
user and configuration type, preventing reuse of encrypted records for another
user/provider.

Generate the key **once** using the project's Python environment:

```powershell
.\venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save it as `CREDENTIALS_ENCRYPTION_KEY` in the environment or secret manager.
It is required even in development; there is no default key or automatic
generation. Compose passes it only to backend and worker.

**Losing the key makes credentials unrecoverable.** Keep a secure copy separate
from database backups and preserve the same key across deployments.

### Masking

The API returns `********` instead of cookies, tokens, keys, and secrets.
During updates/validation, the mask reuses the saved secret only for the
authenticated user/provider. Submitting a new value replaces the old one.
The frontend never receives the Fernet key or stored secret.

Infrastructure secrets — database, authentication, WAHA, Telegram, and AI —
remain in the environment, outside user business configuration.

## Fernet key rotation

1. Generate a new key and set it as `CREDENTIALS_ENCRYPTION_KEY`. Retain the old
   one in `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS`, a comma-separated list.
2. Recreate backend and worker with the same keys. Wait for all old instances
   to stop; new writes use the new key.
3. Re-encrypt records:

   ```bash
   docker compose exec backend python -m backend.app.core.db.credential_rotation
   ```

   In Coolify, run `python -m backend.app.core.db.credential_rotation` in the
   backend terminal. The operation is transactional; an incorrect key or invalid
   record aborts without partial writes.

4. After success, remove `CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS` and recreate both
   services. Keep old keys backed up while database backups still depend on them.

See [Migrations](migrations.md) for implications of the initial plaintext migration.

## WhatsApp isolation

The browser does not receive the WAHA API key or control arbitrary session names.
Each connection, QR, and destination belongs to the authenticated user; the API
derives session names. Channels require an administrative role. Jobs recheck
ownership, enabled state, and routing before sending.

See [WhatsApp](whatsapp.md) for reconnection, transfers, and pauses.
