# Backend Technical Context

## Overview
This is the high-performance, multi-tenant backend for the Telegram Offers Bot. It is built with **FastAPI** and designed for high concurrency and strict data isolation.

## Tech Stack
- **Framework**: FastAPI (Asynchronous)
- **Database**: PostgreSQL (via `asyncpg` and `SQLAlchemy 2.0` async engine)
- **ORM**: SQLAlchemy 2.x (using `Mapped` and `mapped_column`)
- **Schema/Validation**: Pydantic v2
- **Authentication**: Better Auth in Next.js, with PostgreSQL sessions checked independently by FastAPI.
- **Task Architecture**: Designed for individual bot instances per user.

## Architecture & Security
- **Multi-Tenancy**: All user-specific data (Configs, Offers, Destination Channels, Sessions) is isolated via a `user_id` foreign key. 
- **Shared Ingestion**: Use a shared listener account/pool for source groups so users select catalog groups instead of authenticating their own Telegram accounts.
- **Bot-Based Posting**: Offers are posted via a Telegram bot added to each user's destination group/channel, avoiding user-account posting sessions.
- **Concurrency**: Utilizes an asynchronous connection pool (`pool_size=20`, `max_overflow=10`) to prevent connection exhaustion.
- **Data Integrity**: Enforced via SQLAlchemy `relationship` cascades (`all, delete-orphan`) to ensure no orphaned data remains when a user is deleted.
- **Identity Isolation**: `get_current_user` checks the opaque session in `auth_sessions` and maps its immutable identity to `users.auth_user_id`. It never selects ownership from request fields or email claims.
- **Administrator RBAC**: `/admin/source-groups` requires the database `admin` role on every request. Registration creates `user` accounts; operators promote/revoke via `python -m backend.set_admin`.
- **Source Catalog**: Admins manage PostgreSQL `source_groups`; user validation and the live Telethon reader use only enabled catalog entries. Changes apply within the next 30-second worker refresh.

## Implemented Features
- [x] **Asynchronous DB Engine**: Configured SQLAlchemy 2.0 with `asyncpg` and connection pooling.
- [x] **User Management**:
    - Registration and login through Better Auth (`/api/auth/*`) in Next.js.
    - Google login, database sessions, password recovery and session revocation.
    - Legacy FastAPI login, registration and session exchange routes retired.
- [x] **Multi-Tenant User Configs**: 
    - Securely store platform-specific API credentials (JSON format) linked to the authenticated user.
- [x] **Pydantic v2 Schemas**: Full implementation of modern Pydantic v2 `model_config` patterns.

## Roadmap
### Phase 1: Core API Expansion (Current)
- [x] **User Config Management**: Implement `GET`, `POST`, `PUT`, and `DELETE` for `/users/me/configs`.
- [x] **Offer Management**: Implement CRUD for user's found offers.
- [x] **Background Worker Integration**: Implement the bridge between the API and the Telegram bot loop.

### Phase 2: Bot Logic & Automation
- [x] **Shared Telegram Ingestion**: Listen to catalog sources through one operator Telethon session and fan messages out to subscribed users, deduplicating per user in PostgreSQL.
- [x] **Destination Bot Posting**: Replace user-account posting with Telegram Bot API posting to user destination groups/channels where the bot has permission.
- [x] **Destination Management**: Implement CRUD for `/users/me/destinations` and verify bot access before enabling posting.
- [x] **Platform Parsers**: Integrate Ling-first OpenRouter parsing through Novita, Qwen via OpenRouter and direct Gemini fallbacks, regex fallback, and canonical platform detection.
- [x] **Affiliate Conversion**: Implement Amazon, Shopee, AliExpress, and Mercado Livre link generators.

### Phase 2 Follow-Ups
- [x] **Worker Observability**: Improve per-platform missing-credential errors, structured conversion logs, and user-facing config validation before enabling sources/destinations.
- [x] **Persisted Worker Configuration**: Load source selection, enabled destinations, and affiliate credentials from `user_configs` instead of legacy bot environment variables.

### Phase 3: Frontend Integration
- [ ] **Next.js Dashboard**: Implementation of the user dashboard.
- [x] **Better Auth Integration**: Next.js and FastAPI validate PostgreSQL sessions; RBAC stays in the application database.
