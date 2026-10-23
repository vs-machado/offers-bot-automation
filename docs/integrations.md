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

1. **Ling 3.0 Flash** — `inclusionai/ling-3.0-flash`, through OpenRouter, pinned to Novita.
2. **Qwen 3.7 Flash** — `qwen/qwen3.7-flash`, through OpenRouter.
3. **Gemini 2.5 Flash Lite** — Google's direct API.
4. **Regex** — fallback when credentials are missing or configured parsers fail.

Set `OPENROUTER_API_KEY` and/or `GEMINI_API_KEY` in the worker environment.
A Novita route failure advances to Qwen rather than another Ling provider.
DeepSeek is not part of the current chain. Provider prices may change.

An AI failure recovered by fallback is not recorded as a publication failure.

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
