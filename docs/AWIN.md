# Awin / KaBuM integration

In **Afiliados**, select **Awin (KaBuM)** and enter:

- `publisherId`: the numeric ID of your Awin publisher account.
- `accessToken`: your personal API token from <https://ui.awin.com/awin-api>.

Your publisher account must be approved for the KaBuM program. The advertiser ID
is fixed to `17729`, as listed at <https://ui.awin.com/merchant-profile/17729>.
Use the credential validation action to generate a test link, then save the
configuration. Saved tokens are encrypted and masked using the existing credential
storage. Changes are picked up by the worker on its next configuration refresh.

The worker recognizes direct `kabum.com.br` links, requests an Awin tracking link,
and uses `shortUrl` when returned, falling back to the API's long `url`. Failed
requests or malformed responses do not publish the original unaffiliated link.
KaBuM product IDs are used for deduplication, independent of query parameters or
product slugs. Existing source images remain available to the posting pipeline.

The dashboard store filter includes **KaBuM**, including delivery counts and
grouped publication history. Awin appears as the credential provider; KaBuM is
the store recorded in delivery history.

For the legacy standalone bot, set `AWIN_PUBLISHER_ID` and `AWIN_ACCESS_TOKEN` in
its environment. Dashboard workers use each user's saved configuration instead.

## API contract

`POST https://api.awin.com/publishers/{publisherId}/linkbuilder/generate`

Authentication: `Authorization: Bearer <accessToken>` (token never in query string).

```json
{
  "advertiserId": 17729,
  "destinationUrl": "https://www.kabum.com.br/produto/123456/example",
  "shorten": true
}
```

References:
- <https://help.awin.com/apidocs/generatelink>
- <https://help.awin.com/apidocs/api-authentication>

Targeted checks:

```bash
python -m unittest tests.test_awin tests.test_backend_affiliate_validation tests.test_backend_worker tests.test_delivery_history tests.test_parser
```

These checks mock Awin responses. Validating a real account requires its publisher
ID, API token, and KaBuM program access.
