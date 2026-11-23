"""Best-effort thumbnail capture after a successful WhatsApp delivery."""

import base64
import binascii
from io import BytesIO
import logging
import os

from PIL import Image, ImageOps

from offers_bot.postgres_store import connect

LOGGER = logging.getLogger(__name__)
MAX_INPUT = 8 * 1024 * 1024
MAX_THUMBNAIL = 48 * 1024
MAX_IMAGES = 120
CACHE_LOCK = 81278


def thumbnail(image_data: str) -> bytes | None:
    """Re-encode bounded image data as WebP, without source metadata."""
    if len(image_data) > 4 * ((MAX_INPUT + 2) // 3):
        return None
    try:
        data = base64.b64decode(image_data, validate=True)
        if len(data) > MAX_INPUT:
            return None
        with Image.open(BytesIO(data), formats=("JPEG", "PNG", "WEBP", "GIF")) as image:
            if image.width * image.height > 12_000_000:
                return None
            image.thumbnail((384, 384))
            photo = ImageOps.exif_transpose(image).convert("RGBA")
            flat = Image.new("RGB", photo.size, "white")
            flat.paste(photo, mask=photo.getchannel("A"))
            for dimensions, quality in ((384, 78), (256, 72), (160, 68)):
                flat.thumbnail((dimensions, dimensions))
                output = BytesIO()
                flat.save(output, "WEBP", quality=quality)
                if output.tell() <= MAX_THUMBNAIL:
                    return output.getvalue()
    except (OSError, ValueError, binascii.Error, Image.DecompressionBombError):
        return None
    return None


def _prune(conn):
    conn.execute(
        "DELETE FROM storefront_thumbnails WHERE expires_at <= CURRENT_TIMESTAMP"
    )
    conn.execute(
        """DELETE FROM storefront_thumbnails WHERE delivery_id IN (
               SELECT delivery_id FROM storefront_thumbnails
               ORDER BY expires_at DESC, delivery_id DESC OFFSET %s
           )""",
        (MAX_IMAGES,),
    )


def prune_thumbnails():
    """Remove expired thumbnails even if new posts have stopped."""
    with connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (CACHE_LOCK,))
        _prune(conn)


def capture_thumbnail(delivery_id: str, user_id: int, image_data: str | None):
    """Cache an opted-in owner's product attachment without affecting delivery status."""
    if not image_data or os.getenv("STOREFRONT_MEDIA_USER_ID") != str(user_id):
        return
    try:
        body = thumbnail(image_data)
        if body is None:
            return
        with connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '2s'")
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (CACHE_LOCK,))
            conn.execute(
                """INSERT INTO storefront_thumbnails (delivery_id, body, expires_at)
                   SELECT id, %s, CURRENT_TIMESTAMP + interval '24 hours'
                   FROM promotion_deliveries
                   WHERE id=%s AND user_id=%s AND status='sent' AND NOT manual
                     AND connection_id IS NOT NULL AND image_url IS NULL
                     AND category IS DISTINCT FROM 'coupon'
                     AND title IS NOT NULL AND price IS NOT NULL AND affiliate_url IS NOT NULL
                   ON CONFLICT (delivery_id) DO NOTHING""",
                (body, delivery_id, user_id),
            )
            _prune(conn)
    except Exception:
        LOGGER.warning(
            "Storefront thumbnail capture failed for delivery %s", delivery_id
        )
