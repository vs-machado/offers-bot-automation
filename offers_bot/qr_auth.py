"""QR code authentication handler for headless/Docker environments.

Starts temporary HTTP server, serves HTML page with embedded QR code,
waits for scan, shuts down server after auth.

Usage (via TelegramOfferBot._qr_login):
    qr_login = await client.qr_login()
    await serve_qr_and_wait(
        login_url=qr_login.url,
        wait_coro=qr_login.wait(timeout=120),
        port=8080,
    )
"""

from __future__ import annotations

import asyncio
import base64
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from pathlib import Path

import qrcode

LOGGER = logging.getLogger(__name__)

QR_AUTH_TIMEOUT = 120  # Telethon QR login default timeout

_QR_SERVER: HTTPServer | None = None

_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
_QR_HTML_TEMPLATE: str | None = None


def _load_qr_template() -> str | None:
    """Load ``frontend/qr.html`` template, or ``None`` if missing."""
    path = _FRONTEND_DIR / "qr.html"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def _build_html_page(png_data: bytes) -> str:
    """Build QR login page from template (or inline fallback)."""
    global _QR_HTML_TEMPLATE  # noqa: PLW0603
    if _QR_HTML_TEMPLATE is None:
        _QR_HTML_TEMPLATE = _load_qr_template()

    qr_b64 = base64.b64encode(png_data).decode()

    if _QR_HTML_TEMPLATE:
        return _QR_HTML_TEMPLATE.replace("{{QR_B64}}", qr_b64).replace(
            "{{QR_AUTH_TIMEOUT}}", str(QR_AUTH_TIMEOUT)
        )

    return (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<meta http-equiv='refresh' content='30'>"
        "<title>QR Login</title>"
        "<style>body{font-family:sans-serif;display:flex;justify-content:center;"
        "align-items:center;min-height:100vh;background:#f0f2f5}</style>"
        "</head><body>"
        f"<img src='data:image/png;base64,{qr_b64}' alt='QR Code' "
        "style='width:300px;height:300px'>"
        "</body></html>"
    )


class _QRHandler(SimpleHTTPRequestHandler):
    """Serves HTML page with embedded QR code on every GET."""

    qr_png_data: bytes = b""
    html_page: str = ""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, max-age=0")
        if self.path.endswith(".png"):
            self.send_header("Content-Type", "image/png")
            body = self.qr_png_data
        else:
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = self.html_page.encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        LOGGER.debug("QR HTTP: %s", fmt % args)


def _generate_qr_png(login_url: str) -> bytes:
    """Generate QR code PNG bytes from Telethon login URL."""
    qr = qrcode.QRCode(border=1, box_size=10)
    qr.add_data(login_url)
    buf = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()


def build_qr_web_url(login_url: str) -> str:
    """Build a URL that renders the QR code via external service.

    Useful when the temporary HTTP server is not accessible (e.g. headless
    server without port exposure). The resulting URL can be opened in any
    browser.
    """
    from urllib.parse import quote

    return (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=300x300&data={quote(login_url, safe='')}"
    )


async def serve_qr_and_wait(
    login_url: str,
    wait_coro: asyncio.Future,
    port: int = 8080,
) -> None:
    """Serve QR code on HTTP, wait for scan or timeout.

    Args:
        login_url: Telethon QR login URL (``qr_login.url``).
        wait_coro: Coroutine/future that completes on scan
            (``qr_login.wait(timeout=120)``).
        port: HTTP server port (default 8080).

    Raises:
        asyncio.TimeoutError: If QR expires before scan.
        OSError: If port is already in use.
    """
    global _QR_SERVER  # noqa: PLW0603

    # Convert coroutine to Future/Task so we can poll .done()
    if asyncio.iscoroutine(wait_coro):
        wait_coro = asyncio.ensure_future(wait_coro)

    png_data = _generate_qr_png(login_url)
    _QRHandler.qr_png_data = png_data
    _QRHandler.html_page = _build_html_page(png_data)

    _QR_SERVER = HTTPServer(("0.0.0.0", port), _QRHandler)
    # Short timeout so we can poll for shutdown
    _QR_SERVER.timeout = 0.5

    web_url = build_qr_web_url(login_url)

    LOGGER.warning(
        "\n====== QR LOGIN REQUIRED ======\n"
        "Open in browser: http://localhost:%s\n"
        "Or scan QR via:  %s\n"
        "Expires in %s seconds.\n"
        "================================",
        port,
        web_url,
        QR_AUTH_TIMEOUT,
    )

    async def _poll_server() -> None:
        """Handle one HTTP request per iteration until done."""
        while not wait_coro.done():
            _QR_SERVER.handle_request()
            await asyncio.sleep(0.1)

    try:
        await asyncio.wait_for(
            asyncio.gather(wait_coro, _poll_server()),
            timeout=QR_AUTH_TIMEOUT + 10,
        )
        result = wait_coro.result()
        LOGGER.info("QR login successful!")
        return result
    except asyncio.TimeoutError:
        LOGGER.error("QR login timed out after %ss", QR_AUTH_TIMEOUT)
        raise
    finally:
        _QR_SERVER.server_close()
        _QR_SERVER = None
        LOGGER.info("QR auth server stopped")


def cleanup() -> None:
    """Cancel any active QR auth server. Safe to call multiple times."""
    global _QR_SERVER  # noqa: PLW0603
    if _QR_SERVER is not None:
        try:
            _QR_SERVER.server_close()
        except Exception:
            pass
        _QR_SERVER = None
        LOGGER.debug("QR auth server cleaned up")


if __name__ == "__main__":
    # Quick self-test
    logging.basicConfig(level=logging.DEBUG)

    async def _test():
        url = "tg://login?token=test_token_12345"
        print(f"Generated QR PNG: {len(_generate_qr_png(url))} bytes")
        print(f"Web URL: {build_qr_web_url(url)}")
        print("To test full flow, run the bot normally.")

    asyncio.run(_test())
