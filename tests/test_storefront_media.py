import base64
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.v1.endpoints.storefront_media import get_db, router
from backend.worker.storefront_media import MAX_THUMBNAIL, capture_thumbnail, thumbnail


def attachment() -> str:
    stream = BytesIO()
    Image.new("RGBA", (800, 500), (80, 100, 120, 255)).save(stream, "PNG")
    return base64.b64encode(stream.getvalue()).decode()


class StorefrontMediaTests(unittest.TestCase):
    def test_attachment_becomes_small_webp(self):
        body = thumbnail(attachment())
        self.assertIsNotNone(body)
        self.assertLessEqual(len(body), MAX_THUMBNAIL)
        with Image.open(BytesIO(body)) as photo:
            self.assertEqual(photo.format, "WEBP")
            self.assertEqual(photo.width, 384)
        self.assertIsNone(thumbnail("not-an-attachment"))

    def test_capture_requires_explicit_owner_and_db_failure_is_nonfatal(self):
        with (
            patch.dict("os.environ", {"STOREFRONT_MEDIA_USER_ID": "4"}),
            patch("backend.worker.storefront_media.connect", side_effect=OSError) as db,
        ):
            capture_thumbnail("a" * 64, 3, attachment())
            db.assert_not_called()
            with self.assertLogs("backend.worker.storefront_media", level="WARNING"):
                capture_thumbnail("a" * 64, 4, attachment())
            db.assert_called_once()

    def test_public_route_serves_only_cached_images(self):
        app = FastAPI()
        app.include_router(router)
        db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            self.assertEqual(
                client.get("/public/storefront/images/invalid").status_code, 404
            )
            db.scalar.assert_not_awaited()
            db.scalar.return_value = None
            path = "/public/storefront/images/" + "a" * 64
            self.assertEqual(client.get(path).status_code, 404)
            body = thumbnail(attachment())
            db.scalar.return_value = body
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/webp")
            self.assertEqual(response.content, body)
