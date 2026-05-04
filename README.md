# Telegram Offers Bot

Bot user account listens to source Telegram groups, extracts Mercado Livre URLs, generates your affiliate link, then posts to target group.

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

First run asks Telegram login code. Session stored as `TELEGRAM_SESSION`.

Test Mercado Livre link generation alone:

```powershell
python -m offers_bot.check_link "https://www.mercadolivre.com.br/creatina-monohidratada-250g-growth-supplements-sem-sabor-em-po/p/MLB19603205"
```

## Mercado Livre Credentials

`task-context.md` shows browser request shape for `createLink`. Do not commit cookie or CSRF values. Put them in `.env`:

```env
ML_COOKIE_HEADER=_d2id=...; ssid=...; ...
ML_CSRF_TOKEN=...
ML_AFFILIATE_TAG=axdxs2
```

Cookies expire. When Mercado Livre starts returning 401/403, capture fresh cookie + CSRF from browser devtools while logged into affiliate hub.

## Notes

- Scraping other Telegram groups needs your user account to be member of those groups. Normal bot accounts cannot read arbitrary groups.
- `POLL_EXISTING_MESSAGES=true` processes latest 50 messages from each source at startup.
- SQLite dedupe lives at `data/offers.sqlite3`.
- Private invite links can be joined/resolved by Telethon only when your account has access.
- `BROWSER_RESOLVER_ENABLED=true` uses headless Chromium to open affiliate/profile links, find the `Ir para produto` URL, then convert that real product URL into your affiliate link.
- `BROWSER_DEBUG_DIR=data/browser-debug` saves HTML/screenshot when Chromium cannot find the product URL.
