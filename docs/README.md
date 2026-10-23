# Offers Bot documentation

Offers Bot is a multi-tenant offer automation platform with a web dashboard,
user-specific affiliate links, and publishing to Telegram and WhatsApp. Offer
sources are selected from a catalog of public Telegram groups.

## Where to start

- **Platform users:** [User guide](user-guide.md),
  [affiliate integrations](integrations.md), and [WhatsApp](whatsapp.md).
- **Operators setting up an installation:** [Local setup](local-setup.md) or
  [production deployment](deploy.md), followed by [Configuration](configuration.md).
- **Maintenance:** [Operations](operations.md), [Security](security.md), and
  [Migrations](migrations.md).
- **Development:** [Architecture](architecture.md),
  [Development](development.md), and the
  [WhatsApp technical specification](whatsapp-implementation.md).

## Guides

| Document | Contents |
| --- | --- |
| [User guide](user-guide.md) | First login, sources, destinations, categories, and history |
| [Local setup](local-setup.md) | Prerequisites, Docker Compose, first administrator, and reader authentication |
| [Deployment](deploy.md) | Coolify, external PostgreSQL, networking, services, and post-deployment checks |
| [Configuration](configuration.md) | Environment variables, limits, and infrastructure/user configuration boundaries |
| [Integrations](integrations.md) | Store credentials, validation, and AI extraction |
| [WhatsApp and WAHA](whatsapp.md) | WAHA setup, multiple accounts, groups, channels, and policies |
| [Architecture](architecture.md) | Components, tenant isolation, and offer processing |
| [Operations](operations.md) | Source administration, queue, history, logs, and troubleshooting |
| [Security](security.md) | Better Auth, password recovery, encryption, and key rotation |
| [Development](development.md) | Environment, code structure, local checks, and CI |
| [Migrations and legacy](migrations.md) | Alembic, upgrades, SQLite imports, and standalone runtime |
| [WhatsApp technical specification](whatsapp-implementation.md) | Requirements, concurrency, policies, and validation criteria |

## Conventions

- Commands run from the repository root unless stated otherwise.
- Local Compose examples use `docker compose`; in Coolify, use the corresponding
  service terminal and the dedicated deployment file.
- Affiliate credentials and publishing preferences are saved through the dashboard.
  `.env` files contain platform infrastructure settings.
- Telegram is the current offer source; Telegram and WhatsApp are destinations.
- The [main README](../README.md) introduces the product; operational and technical
  details live in this directory.
