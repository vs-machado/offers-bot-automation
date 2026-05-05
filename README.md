# Telegram Offers Bot

Bot user account listens to source Telegram groups, extracts Mercado Livre and Amazon URLs, generates your affiliate link, then posts to target group.

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
   - `AMAZON_AFFILIATE_TAG`
   - `AMAZON_COOKIE_HEADER`
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

Test one link conversion alone:

```powershell
python -m offers_bot.check_link "https://www.mercadolivre.com.br/creatina-monohidratada-250g-growth-supplements-sem-sabor-em-po/p/MLB19603205"
```

```powershell
python -m offers_bot.check_link "https://www.amazon.com.br/dp/B0DXR6MKR8?tag=promotom05-20"
```

## Deploying to Coolify (or Docker)

Because Telegram requires an interactive login code the first time you connect, you cannot perform the initial login directly inside a Coolify/Docker deployment. 

1. **Generate the session locally:**
   Run the bot on your local machine first (`python run.py`). Enter your phone number and the OTP code. This will generate a file named `offers_bot.session`.
2. **Upload the session file to your server:**
   Use SSH or SFTP to upload `offers_bot.session` to your server. Place it in the directory where your Coolify project stores its data (e.g., `/data/coolify/applications/<app_id>/`).
3. **Important Docker Pitfall:**
   You **MUST** ensure the `offers_bot.session` file exists on the host server **before** you start the Coolify deployment. 
   *Why?* If Docker tries to bind-mount a file that doesn't exist on the host, it will automatically create an empty **directory** with that name. When the bot starts, SQLite will try to open that directory as a database and crash with `sqlite3.OperationalError: unable to open database file`.
4. **Deploy:**
   Once the file is securely on the host server, deploy your app from Coolify.

## Mercado Livre Credentials

`task-context.md` shows browser request shape for `createLink`. Do not commit cookie or CSRF values. Put them in `.env`:

```env
ML_COOKIE_HEADER=_d2id=...; ssid=...; ...
ML_CSRF_TOKEN=...
ML_AFFILIATE_TAG=axdxs2
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

## Notes

- Scraping other Telegram groups needs your user account to be member of those groups. Normal bot accounts cannot read arbitrary groups.
- `POLL_EXISTING_MESSAGES=true` processes latest 50 messages from each source at startup.
- SQLite dedupe lives at `data/offers.sqlite3`.
- Private invite links can be joined/resolved by Telethon only when your account has access.
- `BROWSER_RESOLVER_ENABLED=true` uses headless Chromium to open affiliate/profile links, find the `Ir para produto` URL, then convert that real product URL into your affiliate link.
- `BROWSER_DEBUG_DIR=data/browser-debug` saves HTML/screenshot when Chromium cannot find the product URL.
