# Backend Technical Context

## Overview
This is the high-performance, multi-tenant backend for the Telegram Offers Bot. It is built with **FastAPI** and designed for high concurrency and strict data isolation.

## Tech Stack
- **Framework**: FastAPI (Asynchronous)
- **Database**: PostgreSQL (via `asyncpg` and `SQLAlchemy 2.0` async engine)
- **ORM**: SQLAlchemy 2.x (using `Mapped` and `mapped_column`)
- **Schema/Validation**: Pydantic v2
- **Authentication**: OAuth2 with JWT (using `python-jose` and `passlib[bcrypt]`)
- **Task Architecture**: Designed for individual bot instances per user.

## Architecture & Security
- **Multi-Tenancy**: All user-specific data (Configs, Offers, Destination Channels, Sessions) is isolated via a `user_id` foreign key. 
- **Shared Ingestion**: Use a shared listener account/pool for source groups so users provide source links instead of authenticating their own Telegram accounts.
- **Bot-Based Posting**: Offers are posted via a Telegram bot added to each user's destination group/channel, avoiding user-account posting sessions.
- **Concurrency**: Utilizes an asynchronous connection pool (`pool_size=20`, `max_overflow=10`) to prevent connection exhaustion.
- **Data Integrity**: Enforced via SQLAlchemy `relationship` cascades (`all, delete-orphan`) to ensure no orphaned data remains when a user is deleted.
- **Identity Isolation**: The `get_current_user` dependency ensures that the user's identity is derived exclusively from a validated JWT, preventing ID-spoofing attacks.

## Implemented Features
- [x] **Asynchronous DB Engine**: Configured SQLAlchemy 2.0 with `asyncpg` and connection pooling.
- [x] **User Management**:
    - User Registration (`/auth/register`)
    - Secure Login (`/auth/login`) via OAuth2 standard.
- [x] **Multi-Tenant User Configs**: 
    - Securely store platform-specific API credentials (JSON format) linked to the authenticated user.
- [x] **Pydantic v2 Schemas**: Full implementation of modern Pydantic v2 `model_config` patterns.

## Roadmap
### Phase 1: Core API Expansion (Current)
- [x] **User Config Management**: Implement `GET`, `POST`, `PUT`, and `DELETE` for `/users/me/configs`.
- [x] **Offer Management**: Implement CRUD for user's found offers.
- [x] **Background Worker Integration**: Implement the bridge between the API and the Telegram bot loop.

### Phase 2: Bot Logic & Automation
- [ ] **Shared Telegram Listener**: Implement one shared listener account/pool for subscribed source groups, deduplicating source ingestion across users.
- [x] **Destination Bot Posting**: Replace user-account posting with Telegram Bot API posting to user destination groups/channels where the bot has permission.
- [x] **Destination Management**: Implement CRUD for `/users/me/destinations` and verify bot access before enabling posting.
- [x] **Platform Parsers**: Integrate DeepSeek-first AI parsing, Gemini fallback, regex fallback, and canonical platform detection.
- [ ] **Affiliate Conversion**: Implement Amazon, Shopee, AliExpress, and Mercado Livre link generators.

### Phase 3: Frontend Integration
- [ ] **Next.js Dashboard**: Implementation of the user dashboard.
- [ ] **NextAuth.js Integration**: Connect Next.js to the FastAPI JWT provider.
