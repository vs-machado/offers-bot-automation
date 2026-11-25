"""Direct browser publishing for one operator-owned X account."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

COMPOSE = "https://x.com/compose/post"
LOGIN = "https://x.com/i/flow/login"
ACCOUNT = '[data-testid="SideNav_AccountSwitcher_Button"]'
EDITOR = '[data-testid="tweetTextarea_0"][contenteditable="true"]'
SUBMIT = (
    '[data-testid="tweetButton"]:visible, [data-testid="tweetButtonInline"]:visible'
)
VIEWPORT = {"width": 1440, "height": 1000}


@dataclass(frozen=True)
class BrowserSettings:
    handle: str
    state: Path

    @classmethod
    def from_env(cls):
        """Require an intended X account and an explicit session file path."""
        handle = os.getenv("X_OFFERS_BROWSER_HANDLE", "").strip().removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
            raise ValueError("Set X_OFFERS_BROWSER_HANDLE to the intended X handle")
        return cls(
            handle,
            Path(os.getenv("X_OFFERS_BROWSER_STATE", "data/x-browser-session.json")),
        )

    def check_state(self):
        """Reject missing or group/world-accessible browser credentials."""
        if not self.state.is_file() or self.state.stat().st_mode & 0o077:
            raise ValueError(
                "X browser session file must exist and have owner-only permissions (0600)"
            )


def save_state(context, path: Path):
    """Atomically replace the X session file with an owner-only copy."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
    try:
        context.storage_state(path=str(temp))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def open_composer(page, handle: str):
    """Verify X origin, active account, and an empty composer before editing."""
    page.goto(COMPOSE, wait_until="domcontentloaded", timeout=15_000)
    url = urlsplit(page.url)
    if url.scheme != "https" or url.netloc != "x.com":
        raise ValueError("X composer redirected out of X")
    account = page.locator(ACCOUNT).inner_text(timeout=5_000).strip().splitlines()
    if not account or account[-1].strip().lower() != f"@{handle.lower()}":
        raise ValueError("Wrong X account or unable to verify active handle")
    editor = page.locator(EDITOR)
    if editor.inner_text(timeout=5_000).strip():
        raise ValueError("X composer was not empty")
    return editor


def submit_offer(
    page, handle: str, text: str, expires: datetime
) -> tuple[str, str | None]:
    """Click Post once; accept success only with X's confirmation link for this account."""
    try:
        editor = open_composer(page, handle)
        editor.fill(text, timeout=4_000)
        if editor.inner_text(timeout=2_000).strip() != text:
            return "browser_blocked", None
        button = page.locator(SUBMIT)
        button.click(trial=True, timeout=3_000)
    except Exception:
        return "browser_blocked", None
    if expires <= datetime.now(timezone.utc) + timedelta(seconds=4):
        return "expired", None
    try:
        button.click(timeout=3_000)
        href = page.locator('[data-testid="toast"] a[href*="/status/"]').get_attribute(
            "href", timeout=8_000
        )
        url = urlsplit(href or "")
        post = re.fullmatch(
            rf"/{re.escape(handle)}/status/([0-9]{{1,19}})/?",
            url.path,
            re.IGNORECASE | re.ASCII,
        )
        if post and url.netloc in ("", "x.com"):
            return "sent", post[1]
    except Exception:
        pass  # A click may already have reached X. Never retry it.
    return "browser_uncertain", None


def publish_with_browser(settings: BrowserSettings, text: str, expires: datetime):
    """Open an isolated browser, send once, and save refreshed session cookies on success."""
    result = ("browser_blocked", None)
    try:
        settings.check_state()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                storage_state=str(settings.state), viewport=VIEWPORT
            )
            result = submit_offer(context.new_page(), settings.handle, text, expires)
            if result[0] == "sent":
                save_state(context, settings.state)
    except Exception:
        # Do not log Playwright errors: they can contain session data or draft text.
        pass
    return result


def main():
    """Set up or validate the X browser session without submitting posts."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("action", choices=("login", "check"))
    action = parser.parse_args().action
    settings = BrowserSettings.from_env()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=action == "check")
        if action == "check":
            settings.check_state()
            context = browser.new_context(
                storage_state=str(settings.state), viewport=VIEWPORT
            )
        else:
            context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        if action == "login":
            page.goto(LOGIN, wait_until="domcontentloaded")
            input(f"Sign in to @{settings.handle} in Chromium, then press Enter here. ")
        open_composer(page, settings.handle)
        if action == "login":
            save_state(context, settings.state)
    print(f"X composer verified for @{settings.handle}. No post sent.")


if __name__ == "__main__":
    main()
