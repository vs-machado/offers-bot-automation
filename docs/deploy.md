# Production deployment

[Documentation index](README.md)

## Coolify and external PostgreSQL

Use **only** [`docker-compose.coolify.yml`](../docker-compose.coolify.yml) as
the Docker Compose Location in Coolify. It does not create PostgreSQL or publish
ports directly on the host. The base and override Compose files are for local use.

### 1. Provision the database

Create a PostgreSQL resource on the same server. Configure its user, password,
database, and backups in that resource. Identify its Docker network; the network
must exist before deploying the application.

Point both URLs to **the same database**:

```dotenv
DATABASE_NETWORK=postgres_network_name
DATABASE_URL=postgresql+asyncpg://user:password@internal-host:5432/offers_db
AUTH_DATABASE_URL=postgresql://user:password@internal-host:5432/offers_db
BETTER_AUTH_URL=https://app.example.com
BETTER_AUTH_SECRET=random_secret_with_at_least_32_characters
```

URL-encode special characters in usernames/passwords. Do not use `localhost`
as the host. `POSTGRES_*` variables do not configure the external resource.
Changing URLs does not transfer data: restore a backup before moving an existing
installation to another database.

### 2. Configure secrets

In addition to database URLs and authentication, supply:

- `CREDENTIALS_ENCRYPTION_KEY`, generated once and preserved across deployments;
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and the operator's session or phone;
- `TELEGRAM_BOT_TOKEN` for Telegram publishing;
- `WAHA_BASE_URL` and `WAHA_API_KEY` for WhatsApp publishing;
- AI, Google, and SMTP credentials according to the desired features.

See [Configuration](configuration.md) and [Security](security.md).
Users configure their own affiliate tags and secrets through the dashboard.

### 3. Check networks and domain

- Assign the HTTPS domain to `frontend`, internal port **3000**.
- Backend and posting do not need public domains.
- For Telegram reader QR authentication, provide restricted access to worker
  port **8081** during setup.
- PostgreSQL must be reachable through `DATABASE_NETWORK`.
- WAHA must be reachable by backend, worker, and posting. A `waha` alias only
  works when services share a network; see [WhatsApp](whatsapp.md).
- The current file has an installation-specific `traefik.docker.network` label.
  Check that it matches the network used by your Coolify proxy.

Redis stays on the application's internal network with hostname `offers-redis`.

### 4. Deploy and configure first access

1. Deploy and check backend logs: migrations run before the service becomes healthy.
2. Check frontend, worker, and posting startup.
3. Authenticate the Telegram reader and verify source access.
4. If accounts need to be created, temporarily set
   `DISABLE_PUBLIC_REGISTRATION=false` and redeploy the frontend.
5. Register the account and promote the administrator in the backend terminal:

   ```bash
   python -m backend.set_admin admin@example.com
   ```

6. Review `/admin/source-groups` and configure the user in the dashboard.
7. Close registration again if required by the installation's policy.

SMTP is required for password recovery, not ordinary login.

## Updates

Deploy compatible frontend, backend, and worker versions. This is especially
important for WhatsApp routing and schema changes. The backend runs
`alembic upgrade head`; do not start updated workers against an older schema.

Before updating an old installation, read [Migrations](migrations.md), preserve
the database and encryption key, and follow version-specific compatibility steps.
The multiple-connections migration requires every posting worker to be updated
before enabling new accounts.

## Post-deployment checks

- Dashboard available over HTTPS; login and sessions working.
- Backend healthy and migrations complete.
- Reader connected and catalog accessible.
- A new offer appears in history and reaches an enabled test destination.
- WhatsApp QR, text, and image delivery verified on the installed WAHA
  version/engine; test multiple-connection routing with two distinct numbers.
- Restarts preserve PostgreSQL and WAHA sessions; the Fernet key stays unchanged.

CI validates code and does not merge or deploy automatically. See
[Operations](operations.md) for logs, retention, and troubleshooting.
