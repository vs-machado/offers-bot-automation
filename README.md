# Telegram Offers Bot

Bot user account listens to source Telegram groups, extracts Mercado Livre, Amazon, Shopee, and AliExpress URLs, generates your affiliate link, then posts to target group.

## Parsing Architecture

The bot now uses an AI parsing layer first. Telegram messages are sent to a structured Pydantic AI agent backed by Gemini (`gemini-2.5-flash-lite`), which classifies each message as either a product deal or a generic coupon bulletin and extracts clean fields such as title, price, installment info, shipping, coupon, and Meli+ restrictions.

The older regex parser is still present, but it is now the fallback path. It runs only when the AI layer is disabled, missing credentials, or fails/timeouts. URL extraction and platform-specific affiliate conversion still happen after parsing.

```mermaid
flowchart TD
    A[Telegram source message] --> B[Extract supported offer URLs]
    B --> C{AI parser enabled?}
    C -->|No: DISABLE_LLM=true| F[Regex fallback parser]
    C -->|Yes| D["Pydantic AI agent<br/>Gemini 2.5 Flash"]
    D --> E{Structured parse OK?}
    E -->|Yes| G["Use AI fields<br/>title, price, coupon, shipping"]
    E -->|No: error, timeout, missing key| F
    F --> H[Extract fields with regex heuristics]
    G --> I[Generate affiliate link]
    H --> I
    I --> J[Post formatted offer to target chat]
```

## Setup

1. Create Telegram API credentials at `https://my.telegram.org/apps`.
2. Copy `.env.example` to `.env`.
3. Fill:
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `SOURCE_CHATS` with comma-separated source groups/channels
   - `TARGET_CHAT` with your group id, `@name`, or invite link
   - `ML_AFFILIATE_TAG`
   - `ML_COOKIE_HEADER`
   - `ML_CSRF_TOKEN`
   - `SHOPEE_APP_ID`
   - `SHOPEE_APP_SECRET`
   - `AMAZON_AFFILIATE_TAG`
   - `AMAZON_COOKIE_HEADER`
   - `AMAZON_MARKETPLACE_ID`
   - `ALIEXPRESS_APP_KEY`
   - `ALIEXPRESS_APP_SECRET`
   - `ALIEXPRESS_TRACKING_ID`
   - `GEMINI_API_KEY` for the AI parsing layer
   - `LITELLM_API_BASE` only if routing Gemini through LiteLLM
   - `DISABLE_LLM=true` only when you want to force the regex fallback parser
4. Install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

5. Run:

```powershell
python run.py
```

First run in a terminal: enter phone + code interactively.
First run in Docker/headless: **QR login** — open `http://host:8080` in browser, scan QR code with Telegram app.

Session string is auto-saved to SQLite after first auth — no manual `.env` editing needed on restarts.

Test one link conversion alone:

```powershell
python -m offers_bot.check_link "https://www.mercadolivre.com.br/creatina-monohidratada-250g-growth-supplements-sem-sabor-em-po/p/MLB19603205"
```

```powershell
python -m offers_bot.check_link "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=yourtag-20"
```

```powershell
python -m offers_bot.check_link "https://s.shopee.com.br/LjpppnYGZ"
```

```powershell
python -m offers_bot.check_link "https://s.click.aliexpress.com/e/_c4LBE5wb"
```

## Deploying to Coolify (or Docker)

The bot supports QR login for headless environments. No need to pre-generate session files.

### First-time setup (Docker):

1. Set `TELEGRAM_PHONE` in your `.env` (required for QR login).
2. Make sure port `8080` (or your `QR_AUTH_PORT`) is exposed in docker-compose.
3. Start the container:
   ```bash
   docker compose up -d
   ```
4. Open `http://your-server:8080` in a browser — you'll see a QR page.
5. Open Telegram on your phone → Settings → Devices → Scan QR.
6. Bot connects automatically. Session string is saved to the database.
7. Restart the container. Auth is now automatic — no QR needed.

### Local dev (terminal):

```bash
python run.py
# Enter phone + code interactively (same as before)
# Session string auto-saved to DB — no manual steps needed
```

## Troubleshooting & Known Issues

### 1. `telethon.errors.rpcerrorlist.FloodWaitError`
*   **Cause:** Telegram has temporarily throttled your account for making too many requests (like joining too many groups or trying to login too many times).
*   **Fix:** You **must wait** the exact number of seconds specified in the error message. There is no workaround. Stop the bot and wait before trying again, or you risk longer bans.

### 2. QR Login fails / times out
*   **Cause:** QR code expired (120s window) or `TELEGRAM_PHONE` not set.
*   **Fix:** 
    1. Ensure `TELEGRAM_PHONE=+5511999999999` is in your `.env`.
    2. Restart the container — a new QR code is generated.
    3. Scan promptly within 2 minutes.

### 3. Session expired
*   **Cause:** Telegram revoked the session (password change, new device, etc.).
*   **Fix:** Delete the database file (`data/offers.sqlite3`) and restart. The bot will generate a new QR code for re-authentication.

## Mercado Livre Credentials

`task-context.md` shows browser request shape for `createLink`. Do not commit cookie or CSRF values. Put them in `.env`:

```env
ML_COOKIE_HEADER=_d2id=...; ssid=...; ...
ML_CSRF_TOKEN=...
ML_AFFILIATE_TAG=your-ml-tag
```

Cookies expire. When Mercado Livre starts returning 401/403, capture fresh cookie + CSRF from browser devtools while logged into affiliate hub.

## Amazon Credentials

Use the authenticated request to `associates/sitestripe/getShortUrl` while logged into your Amazon Associates account. Put the values in `.env`:

```env
AMAZON_COOKIE_HEADER=session-id=...; ubid-acbbr=...; ...
AMAZON_AFFILIATE_TAG=yourtag-20
AMAZON_MARKETPLACE_ID=526970
```

The bot resolves the incoming Amazon URL, replaces any existing `tag` with your own Associates tag, adds `linkCode=sl2`, then calls the same SiteStripe shortener endpoint.

## AliExpress Credentials

Use AliExpress Affiliate API credentials. Put them in `.env`:

```env
ALIEXPRESS_APP_KEY=...
ALIEXPRESS_APP_SECRET=...
ALIEXPRESS_TRACKING_ID=default
```

The bot resolves incoming AliExpress short URLs, extracts the product id when available, builds a BR coin-index product URL, then calls `aliexpress.affiliate.link.generate` to create your promotion link.

## Shopee Credentials

Use Shopee Affiliate Open API credentials. Put them in `.env`:

```env
SHOPEE_APP_ID=...
SHOPEE_APP_SECRET=...
```

Bot resolves incoming `https://s.shopee.com.br/...` short URL, extracts final `-i.<shop_id>.<item_id>` ids from redirected product URL when available, then calls Shopee Affiliate GraphQL API `generateShortLink` to create your short link. It also uses `productOfferV2` to fetch the product image when product ids are available.

## Notes

- Scraping other Telegram groups needs your user account to be member of those groups. Normal bot accounts cannot read arbitrary groups.
- `POLL_EXISTING_MESSAGES=true` processes latest 50 messages from each source at startup.
- SQLite dedupe lives at `data/offers.sqlite3`.
- AI parser token usage is stored in SQLite under the `token_usage` table.
- Private invite links can be joined/resolved by Telethon only when your account has access.
- `BROWSER_RESOLVER_ENABLED=true` uses headless Chromium to open affiliate/profile links, find the `Ir para produto` URL, then convert that real product URL into your affiliate link.
- `BROWSER_DEBUG_DIR=data/browser-debug` saves HTML/screenshot when Chromium cannot find the product URL.
