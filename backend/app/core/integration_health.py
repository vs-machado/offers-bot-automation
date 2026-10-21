"""Read-only connection checks for dashboard alerts; never expose credentials."""

import asyncio
import re

import httpx

from backend.app.core.affiliate_validation import ProbeFailure, check_response
from backend.app.core.whatsapp import WahaClient
from backend.worker.poster import BotPosterError


async def whatsapp_health(
    user_id: int, has_destinations: bool, connection_id: int | None = None
) -> str:
    """Inspect the owned session without starting pairing or changing destinations."""
    try:
        client = (
            WahaClient(user_id)
            if connection_id is None
            else WahaClient(user_id, connection_id)
        )
        state = await asyncio.wait_for(client.status(include_session=True), timeout=10)
    except (BotPosterError, httpx.HTTPError, asyncio.TimeoutError):
        return "unknown" if has_destinations else "not_configured"
    if state["status"] == "WORKING":
        return "connected"
    if has_destinations or state.get("session_exists"):
        return "unknown" if state["status"] == "UNCONFIGURED" else "disconnected"
    return "not_configured"


async def mercado_livre_health(values: dict | None) -> str:
    """Check the affiliate hub without generating links; only explicit auth rejection expires a session."""
    if values is None:
        return "not_configured"
    if not all(
        isinstance(values.get(key), str) and values[key].strip()
        for key in ("ml_affiliate_tag", "ml_cookie_header", "ml_csrf_token")
    ):
        return "incomplete"
    if any(
        not values[key].isascii() or "\r" in values[key] or "\n" in values[key]
        for key in ("ml_cookie_header", "ml_csrf_token")
    ):
        return "incomplete"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(
                "https://www.mercadolivre.com.br/afiliados/hub",
                headers={
                    "cookie": values["ml_cookie_header"],
                    "x-csrf-token": values["ml_csrf_token"],
                },
            )
        if response.status_code == 401 or 300 <= response.status_code < 400:
            check_response(response, "mercado_livre")
        if "application/json" in response.headers.get("content-type", ""):
            check_response(response, "mercado_livre")
        if response.status_code == 200 and "text/html" in response.headers.get(
            "content-type", ""
        ):
            text = response.text.lower()
            if any(marker in text for marker in ("captcha", "challenge-platform")):
                return "unknown"
            if re.search(r"<input\b[^>]*\btype\s*=\s*['\"]password['\"]", text):
                return "expired"
            return "connected"
        return "unknown"
    except ProbeFailure as exc:
        return "expired" if exc.reason == "authentication" else "unknown"
    except httpx.HTTPError:
        return "unknown"
