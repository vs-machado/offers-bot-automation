from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from .mercado_livre import AffiliateLink
from .parser import extract_shopee_ids

LOGGER = logging.getLogger(__name__)


class ShopeeClient:
    def __init__(
        self,
        cookie_header: str,
        csrf_token: str,
        af_ac_enc_dat: str,
        af_ac_enc_sz_token: str,
        x_sap_ri: str,
        x_sap_sec: str,
        client: httpx.Client | None = None,
        resolver_client: httpx.Client | None = None,
        headless: bool = True,
        timeout_ms: int = 15000,
        debug_dir: Path | None = None,
    ) -> None:
        self._cookie_header = cookie_header
        self._csrf_token = csrf_token
        self._af_ac_enc_dat = af_ac_enc_dat
        self._af_ac_enc_sz_token = af_ac_enc_sz_token
        self._x_sap_ri = x_sap_ri
        self._x_sap_sec = x_sap_sec
        self._client = client
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._debug_dir = debug_dir
        self._resolver_client = resolver_client or client or httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
                ),
            },
        )

    def ready(self) -> bool:
        return bool(self._cookie_header)

    def create_link(self, url: str) -> AffiliateLink:
        if not self.ready():
            raise RuntimeError("Shopee credentials missing: SHOPEE_COOKIE_HEADER")

        normalized_url = self._normalize_url(url)
        resolved_url = self._resolve_url(normalized_url)
        ids = extract_shopee_ids(resolved_url) or extract_shopee_ids(normalized_url)

        if ids:
            shop_id, item_id = ids
            short_url = self._fetch_offer_link_via_browser(item_id)
            product_key = f"SHOPEE:{shop_id}:{item_id}"
        else:
            LOGGER.info("No product IDs found. Falling back to Custom Link flow for: %s", resolved_url)
            short_url = self._fetch_custom_link_via_browser(resolved_url)
            product_key = f"SHOPEE:CUSTOM:{resolved_url}"

        return AffiliateLink(
            short_url=short_url,
            long_url=resolved_url,
            origin_url=resolved_url,
            raw_text=None,
            product_key=product_key,
        )

    def _fetch_custom_link_via_browser(self, target_url: str) -> str:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        custom_link_url = "https://affiliate.shopee.com.br/offer/custom_link"
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            context = browser.new_context(
                locale="pt-BR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
                ),
            )
            self._add_cookie_header(context)
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            try:
                page.goto(custom_link_url, wait_until="networkidle")
                
                # Fill the long URL in the first textarea
                page.locator("textarea").first.fill(target_url)
                
                # Click "Obter link" (or similar button in custom link tab)
                # Usually there's a primary button to generate
                page.get_by_role("button", name="Obter link").click()
                
                # Wait for the result textarea (usually the second one on this page)
                result_textarea = page.locator("textarea").last
                
                page.wait_for_function(
                    r"""
                    (target) => {
                        const textareas = document.querySelectorAll('textarea');
                        const last = textareas[textareas.length - 1];
                        return !!last && /^https?:\/\//.test(last.value || '') && last.value !== target;
                    }
                    """,
                    arg=target_url,
                    timeout=self._timeout_ms,
                )
                
                short_url = result_textarea.evaluate("element => element.value").strip()
                if short_url.startswith("http"):
                    return short_url
            except PlaywrightTimeoutError:
                self._write_debug(page)
                raise RuntimeError(f"Timed out generating Shopee custom link for {target_url}")
            except Exception:
                self._write_debug(page)
                raise
            finally:
                browser.close()

        raise RuntimeError(f"Shopee custom link flow failed for {target_url}")

    def _fetch_offer_link_via_browser(self, item_id: str) -> str:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        offer_page_url = self._build_offer_page_url(item_id)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            context = browser.new_context(
                locale="pt-BR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
                ),
            )
            self._add_cookie_header(context)
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            try:
                page.goto(offer_page_url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=self._timeout_ms)
                page.get_by_role("button", name="Obter link").click()
                textarea = page.locator("textarea").first
                textarea.wait_for(state="visible", timeout=self._timeout_ms)
                page.wait_for_function(
                    r"""
                    () => {
                        const textarea = document.querySelector('textarea');
                        return !!textarea && /^https?:\/\//.test(textarea.value || '');
                    }
                    """,
                    timeout=self._timeout_ms,
                )
                short_url = textarea.evaluate("element => element.value").strip()
                if short_url.startswith("http"):
                    return short_url
            except PlaywrightTimeoutError:
                self._write_debug(page)
                raise RuntimeError(f"Timed out generating Shopee affiliate link for item {item_id}")
            except Exception:
                self._write_debug(page)
                raise
            finally:
                browser.close()

        raise RuntimeError(f"Shopee browser flow did not return affiliate link for item {item_id}")

    def _resolve_url(self, url: str) -> str:
        response = self._resolver_client.get(url)
        response.raise_for_status()
        return str(response.url)

    @staticmethod
    def _build_offer_page_url(item_id: str) -> str:
        return f"https://affiliate.shopee.com.br/offer/product_offer/{item_id}"

    @staticmethod
    def _normalize_url(url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"

    def _add_cookie_header(self, context) -> None:
        cookies = []
        for raw_cookie in self._cookie_header.split(";"):
            if "=" not in raw_cookie:
                continue
            name, value = raw_cookie.strip().split("=", 1)
            if not name:
                continue
            for domain in (".affiliate.shopee.com.br", ".shopee.com.br"):
                cookies.append(
                    {
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": "/",
                        "secure": True,
                        "sameSite": "Lax",
                    }
                )
        if cookies:
            context.add_cookies(cookies)

    def _write_debug(self, page) -> None:
        if not self._debug_dir:
            return
        self._debug_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9]+", "-", page.url)[-120:].strip("-") or "page"
        html_path = self._debug_dir / f"{safe_name}.html"
        png_path = self._debug_dir / f"{safe_name}.png"
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(png_path), full_page=True)
        LOGGER.info("Shopee browser debug written: %s and %s", html_path, png_path)
