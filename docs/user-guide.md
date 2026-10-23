# User guide

[Documentation index](README.md)

## First login

Sign in and follow guided setup. You need:

1. **An affiliate integration** with credentials for a store you use.
2. **Offer sources** selected from the platform catalog.
3. **At least one enabled destination** on Telegram or WhatsApp.

The operator may have closed registration; existing accounts can still sign in
and recover passwords. Google sign-in requires the installation to configure
that integration.

You can publish exclusively to WhatsApp. The platform reads Telegram sources;
you do not need to create a reader account or your own bot.

## Sources

At `/settings/sources`, select public catalog groups to feed your publications.
Administrators maintain the catalog; users cannot register custom sources.

Removed or disabled sources stop producing offers. Your selection may remain
saved and become active again when the source is available.

## Stores and credentials

At `/settings/affiliates`, add or update Amazon, Mercado Livre, Shopee,
AliExpress, and Awin for KaBuM. Use **Validate credentials** to test before saving.

Saving and validating are separate actions. Testing does not publish offers or
save data automatically. Saved credentials appear masked; leaving the mask
preserves the current secret. See each store's requirements in
[Integrations](integrations.md).

## Telegram destinations

At `/settings/destinations`:

1. Add the platform bot to the destination group or channel.
2. Grant the required permissions, including sending messages and photos.
3. Save the destination ID and enable publishing.

The platform checks permissions when enabling destinations. Permission failures
must be corrected in Telegram before trying again.

## WhatsApp destinations

At `/settings/destinations#whatsapp`:

1. Select an account or add a connection.
2. Scan the QR through **WhatsApp → Linked devices**.
3. Choose available groups or channels from that account.
4. Review categories and publishing controls, then enable the desired destinations.

Channels require the `OWNER` or `ADMIN` role; groups require membership and
permission to send. Each destination has one responsible connection.
Disconnecting disables that account's destinations; reconnecting does not
enable them automatically.

You can rename accounts, create/edit administered groups, and configure limits
per connection. The old `/whatsapp` address redirects to Destinations. See
[WhatsApp](whatsapp.md) for transfers, pauses, and group management.

## Categories per group or channel

Each destination on either platform can receive all offers or selected categories:

| Category | API key |
| --- | --- |
| Technology | `tech` |
| Home | `home` |
| Clothes and accessories | `clothes` |
| Other products | `other` |
| Generic coupons | `coupon` |

Select **All offers** for no restriction. An empty selection receives no offers.
In the API, `categories: null` means all and `categories: []` means none.

Product-specific coupons follow the product category; generic coupons use
`coupon`. Products without a recognized classification use `other`, including
regex-only parsing. Rules are checked before queueing and sending. Changing
them does not republish old offers.

## Dashboard history

The dashboard groups publications by offer and shows results per destination,
refreshing every 30 seconds. History remains available even before setup is complete.

- Filter by store and result.
- Enter a product name and press **Enter**; use **X** to clear it.
- Search matches all words case-insensitively across the entire history before
  pagination. Search and filters remain active during navigation.
- All destination outcomes for a matching publication stay together, including
  records without a title.
- Price, coupon, and affiliate link appear when available. You can copy the link
  or open the offer.
- Per-delivery totals and grouped-offer counts represent different measures.

History retains the last 60 days, with daily cleanup by the worker. Older records
may lack coupons or links because those fields were not previously persisted.

## When an offer does not arrive

Check selected sources, the store integration, and the enabled destination.
Allow up to 30 seconds after saving settings. On WhatsApp, check connection
health, posting window, pauses, and limits.

Offers expire within ten minutes of the original message; queue wait and
attempts count toward that deadline. Expired, discarded, and uncertain deliveries
are not automatically resent.

History displays failure reasons in Portuguese. Source reader failures require
operator investigation because they can occur before any offer record exists.
See [Operations](operations.md).
