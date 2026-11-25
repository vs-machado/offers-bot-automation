# VSM Ofertas on X

For unattended posting without X API credits or AI tokens, see
[Buffer publishing](#buffer-publishing-recommended). For a manual pilot,
`X_OFFERS_MODE=draft` sends offers to your private Telegram chat. Tap **Revisar no
X**, verify the deal and selected account, then click **Post** yourself.
Use a pinned welcome post explaining what followers will get and linking to
VSM's landing page. Lead with product and the advertised price. Skip generic
hooks, unverified savings claims, and trending hashtags. For a manual post,
one topical hashtag is reasonable if it helps people find the deal.

## Shared setup and draft preview

In the Offers Bot worker environment, set:

| Setting | Value |
| --- | --- |
| `X_OFFERS_USER_ID` | Internal numeric owner ID for VSM Ofertas |
| `X_OFFERS_CHAT_ID` | Exact destination ID of the enabled VSM offers channel whose deals people can find from the landing page |
| `X_OFFERS_LANDING_URL` | Public HTTPS VSM landing page that leads to that group/channel; optionally add `utm_source=x&utm_medium=social&utm_campaign=ofertas` |
| `X_OFFERS_MODE` | `buffer` for Share Now; `draft` for Telegram review prompts; `off` (default) for CLI previews only; `auto` for direct X API publishing; `browser` for Chromium publishing |
| `X_OFFERS_DRAFT_TELEGRAM_CHAT_ID` | Your numeric Telegram user ID, not a group, channel, or username |
| `TELEGRAM_BOT_TOKEN` | Existing Offers Bot token; needed for `draft` mode |
| `X_OFFERS_DAILY_LIMIT` | `1` (default) through `10` draft/send attempts per day |

For `draft` mode, open a private chat with the bot and tap **Start** so it
can message you. After deploying migration `0026_x_offer_attempts`, set the worker
variables and restart it. Draft mode needs no X credentials. A draft shows its
freshness deadline in Brasília time; ignore it if the deadline has passed.
Telegram delivery does not mean the draft was posted to X.

Run inside the deployed worker:

```sh
docker compose exec worker python -m backend.worker.x_offers
```

In Coolify, run `python -m backend.worker.x_offers` from the worker terminal.
The command prints one draft plus a link that opens the X composer. No post is
made by the command. Run it while offers come in: it only selects fresh
deliveries, and output can expire quickly. Use the group-click event on the
landing page (a click, not a confirmed join) and X follower growth to review the
pilot. Cap manual publishing at one post per day to start.

### What qualifies

- The offer must already be sent by Offers Bot to the configured destination,
  still be within its send deadline, and have been marked sent for at least 45
  seconds. No queued, failed, manual, or expired deliveries.
- Prefer eligible offers from the optional priority Telegram source selected in
  the dashboard. Fall back to other sources when none qualifies. This setting
  ranks offers already sent to the selected destination; it does not subscribe
  the bot to a new source.
- Pick the newest eligible offer from a product shortlist: phones, computers,
  TVs, monitors, gaming consoles, headphones, and recognizable home and kitchen
  appliances. Titles must identify the product itself; accessories, spare parts,
  and unknown product types do not qualify. If the shortlist is empty, skip.
- A first-time product can qualify; price history and minimum savings are not
  required. Posts show the advertised price without claiming a discount or
  independently verifying checkout or stock.
- The selector skips coupon offers, offers with extra purchase or
  shipping instructions, and ambiguous/multi-link posts. It keeps `no Pix`
  when applicable. If nothing qualifies, skip rather than weakening the filter.
- The copy links to the VSM landing page for the group, not directly to checkout.
  Verify the page actually leads to the same deal feed. It discloses that the
  group uses affiliate links.

## Buffer publishing (recommended)

1. Connect the VSM X profile to a [free Buffer account](https://buffer.com/pricing).
   Create a personal [Buffer API key](https://developers.buffer.com/guides/authentication.md)
   and use [Get Channels](https://developers.buffer.com/examples/get-channels.md)
   to find VSM's channel ID (`service: twitter`).
2. Deploy with migration `0028_x_source_priority` and `X_OFFERS_MODE=dashboard`
   (the default). Open **Publicação no X** from the admin sidebar. Select the
   destination, enter the landing URL, channel ID, and personal key, then save.
3. Use **Testar conexão salva** to verify the X account without publishing.
   Enable publishing and save when ready. The worker applies changes on its next
   poll (normally within one minute); an in-flight post can still finish. Check
   the first submission in Buffer and on X to measure the actual delay.

The dashboard stores the key encrypted and never shows it again. Leave the key
field empty to keep the saved key, or enter a replacement and save. For an
environment-managed installation, use `X_OFFERS_MODE=buffer` with the shared
source settings, `X_OFFERS_BUFFER_API_KEY`, and `X_OFFERS_BUFFER_CHANNEL_ID`.

The worker requests `shareNow` for fresh deals. `buffer_accepted` means Buffer
accepted the request but hasn't confirmed X publication in its response. Use
Buffer's Sent or Failed view and the receipt ID in worker logs to confirm it.
The dashboard's activity sidebar shows recent posts confirmed sent by Buffer,
with links to X when Buffer provides them.
The worker never retries an ambiguous submission. No direct X API keys or AI
calls are needed.

## Browser publishing (no API credits)

`browser` mode uses Offers Bot's existing Playwright/Chromium dependency. It
opens X's composer and clicks **Post** without daily approval, OpenBot/Luna, or
X API credentials. X's [developer guidelines](https://docs.x.com/developer-guidelines)
prohibit browser automation, which can result in account suspension.

1. On a machine with a graphical desktop, create the project's `data` directory
   and run `python -m playwright install chromium` in the project's Python environment.
   Set `X_OFFERS_BROWSER_HANDLE` to the VSM
   account, then run `python -m backend.worker.x_browser login`. Sign in directly
   in Chromium, complete any normal login prompts, and press Enter in the terminal.
   This saves `data/x-browser-session.json` without making a post.
2. Securely transfer the session file into the worker's mounted `data` directory
   (`/app/data` in Docker), with permissions `0600`, readable by the worker user.
   Keep the file private: it grants access to the account. Set
   `X_OFFERS_BROWSER_STATE` if using a different path.
3. Set `X_OFFERS_BROWSER_HANDLE` in the worker environment and run
   `python -m backend.worker.x_browser check` inside the worker. This verifies
   the signed-in account and composer without posting.
4. With migration `0026_x_offer_attempts` applied and the VSM source configured,
   set `X_OFFERS_MODE=browser` and restart the worker. Cadence and deduplication
   match the other automatic modes.

Browser mode pauses on an account mismatch, a login challenge, a missing
composer, or an unconfirmed submission. Verify the account timeline, refresh
the session if needed, run `check`, then restart. Unconfirmed clicks are never
retried. Browser mode depends on X's current UI; a layout change can break it.

## Official API publishing

X's [developer guidelines](https://docs.x.com/developer-guidelines) require
automated accounts to display the **Automated** profile label, identify the
operator in the bio, link to a human-managed account, and use the official API.
Confirm your X app is approved for this promotional use before enabling auto.

1. In X Developer Console, configure **OAuth 1.0a** with **Read and Write** and
   generate user access credentials for the VSM account after setting permission.
2. Store `X_OFFERS_API_KEY`, `X_OFFERS_API_SECRET`, `X_OFFERS_ACCESS_TOKEN`, and
   `X_OFFERS_ACCESS_SECRET` as worker secrets. Fund the app and set a Console
   spending limit; start without auto-recharge.
3. Deploy with database migration `0026_x_offer_attempts`, set `X_OFFERS_MODE=auto`,
   and restart the worker. Set it back to `off` and restart to disable posting.

In `buffer`, `browser`, `draft` and `auto`, the worker checks every minute from
08:00 until 22:00 São Paulo time. Attempts are spaced at least four hours apart
for limits of 1–3; for higher limits the minimum is the 14-hour window divided
by the limit. Repeat store/title offers are suppressed for seven days. Attempts count against the cap even
when rejected or uncertain. Drafts require at least 90 seconds of freshness at
selection so you have time to review them.
The database records reservations before sending; there is no automatic retry
after a timeout or crash. If a row stays `reserved` or is `uncertain`, check X
before considering a manual repost.

[X pricing](https://docs.x.com/x-api/getting-started/pricing) lists **US$0.20 per
linked post request**: up to **US$6.20 in a 31-day month** at one per day
(US$12.40 at two). The current Console rate applies. No X reads or trend lookups
are needed. OpenBot/Luna and the existing upstream parser are not used for any
additional model calls in this workflow.
