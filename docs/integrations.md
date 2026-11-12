# Store integrations and extraction

[Documentation index](README.md)

## User-owned credentials

Enter credentials at `/settings/affiliates` or during setup. They are encrypted
in PostgreSQL and associated with the user, not the shared runtime's `.env`.

| Store | Required credentials |
| --- | --- |
| Amazon Brazil | Amazon Associates tag, such as `yourtag-20` |
| Mercado Livre | Affiliate tag, authenticated Cookie header, and CSRF token |
| Shopee Brazil | Affiliate Open Platform app ID and app secret |
| AliExpress | Affiliate API app key, app secret, and optional tracking ID |
| KaBuM through Awin | Numeric publisher ID and personal API access token; approval for the KaBuM program |
| Magalu / Magazine Você | Partner ID, promoter ID and store name; optional UTM campaign |

### Amazon

The converter expands short links, removes the affiliate tracking fields handled
by the client, and adds the user's tag while preserving destination parameters.
The result is a long Amazon Brazil URL; it does not use SiteStripe.

Cookies, marketplace ID, Playwright, and Amazon authentication are not required.
Validation checks tag format; it does not prove ownership, commissions, or
eligibility for every product. Amazon API-based link generation is not implemented.

`link.amazon` links may redirect through `amzlinks.in`; this intermediate host is
accepted during expansion. Final destinations outside Amazon Brazil are rejected,
and redirect chains are bounded.

Amazon does not fetch product images: posts reuse source media when available
or are published without an image.

### Mercado Livre

Cookies expire. Update the configuration when the provider rejects authentication
with 401/403. Validation requires a full eligible product link with an MLB ID.
The address is sent to the fixed affiliate API without the backend visiting it.

The runtime has optional browser resolution according to persisted settings.
This does not replace valid credentials.

### Shopee and AliExpress

Use credentials from the respective affiliate platforms. Each user generates
their own links; platform AI and Telegram credentials do not replace store app
keys, app secrets, or tracking IDs.

### KaBuM through Awin

Select **Awin (KaBuM)** in affiliate settings and enter your numeric `publisherId`
and personal `accessToken` from <https://ui.awin.com/awin-api>. The saved fields
are `awin_publisher_id` and `awin_access_token`. Your publisher account must be
approved for the KaBuM program, whose advertiser ID is fixed to `17729`:
<https://ui.awin.com/merchant-profile/17729>.

Validate the credentials, then save them. Tokens use the same encrypted and
masked storage as other integrations; worker configuration refresh picks up changes.

The worker recognizes direct `kabum.com.br` links and requests an Awin tracking
link, preferring `shortUrl` and falling back to the API's long `url`. Failed calls
or malformed responses never publish the original unaffiliated link. KaBuM
product IDs drive deduplication independently of query parameters or product
slugs, and source images remain available to the posting pipeline.

The dashboard store filter, counts, and grouped history identify the store as
**KaBuM**; **Awin** is the credential provider.

#### Awin API contract

`POST https://api.awin.com/publishers/{publisherId}/linkbuilder/generate`

Authentication uses `Authorization: Bearer <accessToken>`, never a query parameter.

```json
{
  "advertiserId": 17729,
  "destinationUrl": "https://www.kabum.com.br/produto/123456/example",
  "shorten": true
}
```

References: [Generate link](https://help.awin.com/apidocs/generatelink) and
[API authentication](https://help.awin.com/apidocs/api-authentication).

### Magalu / Magazine Você

Select **Magalu** in affiliate settings. Enter `magalu_partner_id`,
`magalu_promoter_id` and `magalu_store_name` from your Magazine Você account.
All three are account settings; no account IDs are embedded in the API endpoint.
`magalu_utm_campaign` is optional and defaults to `divulgacao_influencer`.
Settings use the existing encrypted per-user persistence and worker refresh.
The validation button generates one reference product link without saving or posting.

Before extraction, the bot expands approved HTTPS shorteners such as `cutt.ly`,
`bit.ly`, `tinyurl.com`, `t.co`, `rb.gy` and Magalu OneLink links. Only chains
ending on approved Magazine Luiza / Magazine Você hosts are accepted. Each URL
has at most five redirect requests and a 15-second resolution budget; up to
five unique short URLs are expanded before extraction. Redirects requiring JavaScript,
interstitial interaction or other domains are unsupported. Direct product URLs
do not require fetching the product page.

The converter preserves seller/product parameters and replaces previous account
IDs and default UTMs. Posting always uses `lucreator` / `link_afiliado`, including
when publishing to WhatsApp. It uses the returned `affiliate_url`, not a manually
constructed tracking fallback. Product identity plus seller drives deduplication.
API prices are exposed as metadata but do not replace prices advertised by sources.

Authenticated backend endpoint: `POST /affiliate/magalu`:

```json
{
  "url": "https://www.magazineluiza.com.br/product/p/240466500/te/ga07/",
  "channel": "lucreator"
}
```

The optional channel also accepts `whatsapp` explicitly for
`whatsapp` / `compartilhamento_social`. The endpoint loads only the caller's
saved Magalu settings, rejects account/endpoint overrides, and returns validated
links plus available product metadata. Limits per backend process: eight active
requests, one active request per user and a five-second user interval.
Provider failures return controlled errors; generation POSTs are not retried.

The external endpoint is an observed, **unofficial/unverified API** and may change.
A controlled HTTP test on 2026-10-23 succeeded outside a browser with Galaxy A07
and iPhone URLs without affiliate IDs. That does not establish official support or
guarantee commission attribution. Contract evidence: [implementation specification](../tasks/integracao_api_afiliados_magalu.md).

For the legacy standalone bot only, configure `MAGALU_PARTNER_ID`,
`MAGALU_PROMOTER_ID`, `MAGALU_STORE_NAME` and optionally `MAGALU_UTM_CAMPAIGN`
in its environment. The multi-tenant worker uses dashboard settings instead.

## Credential validation

The button calls `POST /users/me/affiliate-credentials/validate` with form data.
It does not save credentials, persist test links, or publish messages.

Results are passed, credentials rejected, or inconclusive. Timeouts, captchas,
rate limits, and API failures are not proof of an invalid secret. Editing the
form hides the previous result.

Validation uses a reference link; the other stores use their home pages.
Amazon checks format only. A successful check does not prove account ownership,
future commissions, or eligibility of every offer.

Responses contain result, reason, and timestamp, without secrets or raw provider
payloads. The total timeout is 20 seconds, with up to eight concurrent validations
per process and one per user.

## AI extraction

The structured parsing chain is:

1. **MiniMax M3.1 Flash** — `minimaxai/minimax-m3.1-flash`, through NVIDIA's `https://integrate.api.nvidia.com/v1` endpoint.
2. **Nemotron 3.5 Lightning** — `nvidia/nemotron-3.5-lightning-30b-a3b`, through NVIDIA, with thinking disabled and locally validated prompted JSON.
3. **Ling 3.0 Flash** — `inclusionai/ling-3.0-flash`, through OpenRouter, pinned to Novita.
4. **Qwen 3.7 Flash** — `qwen/qwen3.7-flash`, through OpenRouter.
5. **Gemini 2.5 Flash Lite** — Google's direct API.
6. **Regex** — fallback when credentials are missing or configured parsers fail.

Set `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, and/or `GEMINI_API_KEY` in the worker environment.
Set `NVIDIA_FALLBACK_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b` to enable
Lightning with the same NVIDIA key. Compose enables it by default; standalone
mode skips it when this variable is absent or empty. Daily request counts distinguish
both NVIDIA models. Provider-wide NVIDIA failures can affect both models.
Missing keys skip their providers. NVIDIA requests use a 30-second timeout;
OpenRouter requests use a 90-second timeout. SDK retries are disabled so errors
advance to the next provider.
A Novita route failure advances to Qwen rather than another Ling provider.
DeepSeek is not part of the current chain. Provider prices may change.

An AI failure recovered by fallback is not recorded as a publication failure.

### Daily model request counts

Run `python show_token_usage.py` inside the worker container. Its first table
shows the last 14 days of HTTP request attempts grouped by UTC date, provider,
and model. Counts include failed HTTP/network attempts and structured-output
validation retries. These are actual outbound attempts, not counts of parsed offers.
PostgreSQL persists them in `llm_requests`; standalone mode uses SQLite.
Historical requests before this feature are not attributed to a model.
Token totals remain in the existing separate report. Request logs also include
`LLM request provider=... model=...` without credentials or message content.

## Text, coupons, and media

The same LLM call identifies unrelated source advertising by meaning and returns
original substrings in `source_advertising_spans`. Code removes only exact,
unambiguous matches. There is no phrase list or bot-name detection for cleanup.

Product/coupon links, prices, coin discounts, and advertising disclosures must
be preserved. Without LLM results, text is retained rather than removed through
heuristics. Cleanup in `offers_bot/source_cleanup.py` also applies to Shopee
redemption offers and multi-link AliExpress offers.

Purchase quantity instructions required for the advertised price accompany
the offer. Source media is reused when available. WhatsApp delivery adapts the
shared formatting for text and captions; see [WhatsApp](whatsapp.md).
