# Storefront attachments

Set `STOREFRONT_MEDIA_USER_ID` in Coolify to the ID of the account whose product
images are approved for the public storefront. The same setting reaches `posting`
and `worker`. Capture is disabled by default. Deploy backend, posting, worker,
and frontend together; the backend applies migration `0025_storefront_thumbnails`.

After a successful automatic WhatsApp delivery, the posting worker reuses the
attachment already present in the task when the delivery has no image URL. It
re-encodes the attachment as metadata-free WebP, up to 384 px and 48 KiB. Failure
to cache a thumbnail does not change the delivery status or retry the send.
Existing shop image URLs still work; there is no backfill of discarded attachments.

The VPS database holds at most 120 thumbnails (under 6 MiB of image payload),
each for up to 24 hours. Saves evict old entries; periodic worker cleanup removes
expired entries when there are no new offers. The media route also checks expiry
on every origin read. The public frontend path is:

```text
https://BOT-FRONTEND/storefront/images/DELIVERY_ID
```

An exporter should only use a thumbnail URL when it finds an unexpired matching
row in `storefront_thumbnails`. It can emit the URL as `image_url` in the
storefront JSON and continue serving the site on Cloudflare Pages. The private VPS
preview uses this path as a fallback and selects up to 20 offers. Configure edge
cache rules for the exact image path if traffic grows; keep the public cache TTL
short enough for evictions (the frontend sends `max-age=300`).
