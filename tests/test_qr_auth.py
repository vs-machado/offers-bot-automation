"""Tests for QR code authentication module."""

import asyncio
import socket
import unittest

import httpx

from offers_bot.qr_auth import (
    _generate_qr_png,
    build_qr_web_url,
    cleanup,
    serve_qr_and_wait,
)


class TestQRGeneration(unittest.TestCase):
    """Tests for QR code PNG generation and URL building."""

    def test_generate_qr_png_returns_png_bytes(self):
        """_generate_qr_png should produce valid PNG bytes."""
        png = _generate_qr_png("tg://login?token=test_token_42")
        self.assertGreater(len(png), 50)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")  # PNG magic

    def test_generate_qr_png_deterministic(self):
        """Same URL should produce same PNG bytes."""
        url = "tg://login?token=test"
        self.assertEqual(_generate_qr_png(url), _generate_qr_png(url))

    def test_generate_qr_png_different_urls(self):
        """Different URLs should produce different PNGs."""
        self.assertNotEqual(
            _generate_qr_png("tg://login?token=aaa"),
            _generate_qr_png("tg://login?token=bbb"),
        )

    def test_build_qr_web_url_full_encoding(self):
        """All special chars should be percent-encoded."""
        result = build_qr_web_url("tg://login?token=test")
        self.assertIn("data=tg%3A%2F%2Flogin%3Ftoken%3Dtest", result)
        self.assertIn("api.qrserver.com", result)

    def test_build_qr_web_url_plus_encoded(self):
        """'+' in login URL should be percent-encoded."""
        result = build_qr_web_url("tg://login?token=a+b")
        self.assertNotIn("token=a+b", result)
        self.assertIn("%3Ftoken%3Da", result)


class TestQRHttpServer(unittest.TestCase):
    """Integration tests for QR HTTP server lifecycle."""

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def test_server_serves_qr_on_first_request(self):
        """Server starts, serves PNG, shuts down on timeout."""
        port = self._free_port()
        png = _generate_qr_png("tg://login?token=test")

        async def _run():
            loop = asyncio.get_running_loop()
            fut = loop.create_future()

            async def _timeout():
                await asyncio.sleep(2)
                fut.set_exception(asyncio.TimeoutError())

            async def _fetch():
                await asyncio.sleep(0.3)
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"http://localhost:{port}/", timeout=5)
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.headers["content-type"], "image/png")
                    self.assertEqual(r.content, png)

            # Run all tasks; ignore TimeoutError from server
            results = await asyncio.gather(
                _timeout(),
                _fetch(),
                serve_qr_and_wait("tg://login?token=test", fut, port=port),
                return_exceptions=True,
            )
            self.assertIsInstance(results[2], asyncio.TimeoutError)

        asyncio.run(_run())

    def test_server_multiple_requests(self):
        """Server handles multiple HTTP requests before shutdown."""
        port = self._free_port()
        png = _generate_qr_png("tg://login?token=test")

        async def _run():
            loop = asyncio.get_running_loop()
            fut = loop.create_future()

            async def _timeout():
                await asyncio.sleep(3)
                fut.set_exception(asyncio.TimeoutError())

            async def _fetch_many():
                await asyncio.sleep(0.3)
                async with httpx.AsyncClient() as c:
                    for _ in range(3):
                        r = await c.get(f"http://localhost:{port}/", timeout=5)
                        self.assertEqual(r.status_code, 200)
                        self.assertEqual(r.content, png)

            results = await asyncio.gather(
                _timeout(),
                _fetch_many(),
                serve_qr_and_wait("tg://login?token=test", fut, port=port),
                return_exceptions=True,
            )
            self.assertIsInstance(results[2], asyncio.TimeoutError)

        asyncio.run(_run())

    def test_cleanup_noop_when_no_server(self):
        """cleanup() is safe when no server is running."""
        cleanup()

    def test_cleanup_after_server_shutdown(self):
        """cleanup() is safe after server already closed."""
        port = self._free_port()

        async def _run():
            loop = asyncio.get_running_loop()
            fut = loop.create_future()

            async def _timeout():
                await asyncio.sleep(1)
                fut.set_exception(asyncio.TimeoutError())

            results = await asyncio.gather(
                _timeout(),
                serve_qr_and_wait("tg://login?token=test", fut, port=port),
                return_exceptions=True,
            )
            self.assertIsInstance(results[1], asyncio.TimeoutError)

        asyncio.run(_run())
        cleanup()  # Should not raise


if __name__ == "__main__":
    unittest.main()
