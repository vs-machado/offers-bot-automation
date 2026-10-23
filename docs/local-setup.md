# Local setup

[Documentation index](README.md)

## Prerequisites

- Docker with Compose v2.
- Operator Telegram credentials: `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.
- A bot token created through `@BotFather` for Telegram destinations.
- A separate WAHA service for WhatsApp publishing; see [WhatsApp and WAHA](whatsapp.md).
- Credentials for at least one affiliate store to configure the first user.

Docker installs Python and Node dependencies in the images. For development
outside containers, see [Development](development.md).

## 1. Prepare the environment

Copy `.env.example` to `.env` in the repository root and configure the variables
described in [Configuration](configuration.md). In PowerShell:

```powershell
Copy-Item .env.example .env
```

In Linux/macOS shells:

```bash
cp .env.example .env
```

At minimum, configure:

| Variable | Purpose |
| --- | --- |
| `CREDENTIALS_ENCRYPTION_KEY` | Persistent Fernet key for user settings |
| `BETTER_AUTH_SECRET` | Random secret with at least 32 characters |
| `BETTER_AUTH_URL` | `http://localhost:3000` for default local access |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | Shared source reader |
| `TELEGRAM_SESSION_STRING` or `TELEGRAM_PHONE` | Reader account authentication |
| `TELEGRAM_BOT_TOKEN` | Telegram publishing bot |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local database created by Compose |

Generate the Fernet key using the project's Python environment:

```powershell
.\venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Without a local Python environment, build the backend image and generate the key
in a disposable container before starting the application:

```bash
docker build -t offers-bot-backend -f backend/Dockerfile .
docker run --rm offers-bot-backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the output in `.env`. Preserve the generated key: replacing it on every
startup makes saved data unreadable. To generate `BETTER_AUTH_SECRET`, you can
use `openssl rand -base64 32` where OpenSSL is available.

Public registration is closed by default. To create the first user, set
`DISABLE_PUBLIC_REGISTRATION=false` before starting the frontend. You can close
registration again after creating the necessary accounts.

## 2. Start the services

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 backend worker posting frontend
```

Compose loads `docker-compose.yml` and `docker-compose.override.yml` by default.
The override runs the frontend in development mode with mounted source code.
To use only the base definition:

```bash
docker compose -f docker-compose.yml up -d --build
```

The backend applies migrations before becoming healthy. The worker, posting
consumer, and frontend wait for that initialization.

| Service | Default host address |
| --- | --- |
| Dashboard | `http://localhost:3000` |
| API | `http://localhost:8000` |
| Health check | `http://localhost:8000/health` |
| Telegram reader QR | `http://localhost:8081`, during authentication |
| PostgreSQL | `localhost:5434` |

Redis does not publish a host port in the supplied Compose file. Between
containers, use internal names: PostgreSQL at `db:5432`, Redis at `redis:6379`,
and the API at `backend:8000`. Compose builds database URLs from `POSTGRES_*`.

## 3. Authenticate the source reader

The operator supplies `TELEGRAM_SESSION_STRING` or uses `TELEGRAM_PHONE` and the
QR served by the worker on port 8081. This authenticates the shared account
that reads sources, not dashboard users' accounts.

The account must be able to access catalog groups. The operational session is
persisted in PostgreSQL; `data/` is not a replacement for a database backup.

## 4. Create the administrator and configure the catalog

1. Open the dashboard and register an account while registration is enabled.
2. Promote the account through the terminal:

   ```bash
   docker compose exec backend python -m backend.set_admin admin@example.com
   ```

3. Open `/admin/source-groups` and review enabled sources.
4. To close registration, set `DISABLE_PUBLIC_REGISTRATION=true` and recreate
   the frontend:

   ```bash
   docker compose up -d --force-recreate frontend
   ```

## 5. Configure the user

In the dashboard, save an affiliate integration, select sources, and enable at
least one Telegram or WhatsApp destination. Configure destination categories
if needed.

Users can publish only to WhatsApp; sources are still read by the operator's
Telegram account. Allow up to 30 seconds for configuration refresh. Follow the
[User guide](user-guide.md) for this workflow.

## Persistence

- The `postgres_data` volume stores the local database.
- Redis is temporary: restarting it loses pending tasks.
- WAHA needs its own persistent session storage.
- Preserve the Fernet key as part of recovery planning, separately from the
  database backup.

For startup or delivery problems, see [Operations](operations.md).
