from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from .parser import extract_ml_ids

LOGGER = logging.getLogger(__name__)
PRODUCT_HREF_RE = re.compile(r"href=[\"']([^\"']*(?:/p/MLB|wid=MLB)[^\"']*)[\"']", re.IGNORECASE)
MERCADO_LIVRE_IMAGE_HOST_RE = re.compile(r"^https://[^/]*mlstatic\.com/", re.IGNORECASE)
AMAZON_IMAGE_HOST_RE = re.compile(r"^https://m\.media-amazon\.com/", re.IGNORECASE)


class PlaywrightProductResolver:
    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 15000,
        cookie_header: str = "",
        cookie_domains: tuple[str, ...] = (".mercadolivre.com.br",),
        debug_dir: Path | None = None,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._cookie_header = cookie_header
        self._cookie_domains = cookie_domains
        self._debug_dir = debug_dir

    def resolve(self, url: str) -> str | None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            context = browser.new_context(
                locale="pt-BR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
            )
            self._add_cookie_header(context)
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded")

                product_url = self._extract_product_href(page)
                if product_url:
                    return product_url

                page.wait_for_load_state("networkidle", timeout=self._timeout_ms)
                product_url = self._extract_product_href(page)
                if product_url:
                    return product_url

                try:
                    page.get_by_role("link", name="Ir para produto").first.click()
                    page.wait_for_url(lambda current_url: bool(extract_ml_ids(current_url)), timeout=self._timeout_ms)
                    return page.url
                except PlaywrightTimeoutError:
                    self._write_debug(page)
                    LOGGER.warning("Browser resolver could not find product URL at %s", url)
                    return None
            finally:
                browser.close()

    def get_image(self, url: str) -> str | None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self._headless)
            context = browser.new_context(
                locale="pt-BR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
            )
            self._add_cookie_header(context)
            page = context.new_page()
            page.set_default_timeout(self._timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded")
                image_url = self._extract_product_image(page)
                if image_url:
                    return image_url

                try:
                    page.wait_for_load_state("networkidle", timeout=self._timeout_ms)
                except PlaywrightTimeoutError:
                    pass

                image_url = self._extract_product_image(page)
                if image_url:
                    return image_url

                page.evaluate("window.scrollTo(0, Math.min(document.body.scrollHeight, 1200))")
                page.wait_for_timeout(500)
                return self._extract_product_image(page)
            except Exception as exc:
                LOGGER.warning("Browser resolver could not extract image from %s: %s", url, exc)
                return None
            finally:
                browser.close()

    def _extract_product_image(self, page) -> str | None:
        image_url = page.evaluate(
            r"""
            () => {
                const absoluteUrl = (value) => {
                    if (!value) return null;
                    try {
                        return new URL(value, window.location.href).href;
                    } catch (_) {
                        return null;
                    }
                };

                const firstSrcsetUrl = (srcset) => {
                    if (!srcset) return null;
                    const first = srcset.split(',')[0]?.trim()?.split(/\s+/)[0];
                    return absoluteUrl(first);
                };

                const candidates = [];
                const add = (url, score) => {
                    const absolute = absoluteUrl(url);
                    if (absolute) candidates.push({ url: absolute, score });
                };
                const landingImage = document.querySelector('#landingImage');
                const oldHires = absoluteUrl(landingImage?.getAttribute('data-old-hires'));
                if (oldHires && /https:\/\/m\.media-amazon\.com\//i.test(oldHires)) {
                    return oldHires;
                }

                const landingSrc = absoluteUrl(landingImage?.currentSrc || landingImage?.src);
                if (landingSrc && /https:\/\/m\.media-amazon\.com\//i.test(landingSrc)) {
                    return landingSrc;
                }

                for (const selector of [
                    '#imgTagWrapperId img',
                    'img[data-a-image-name="landingImage"]',
                    'li.image.selected img',
                    '#imageBlock img',
                ]) {
                    const img = document.querySelector(selector);
                    add(img?.getAttribute('data-old-hires') || img?.currentSrc || img?.src, 10000000);
                }

                const imageSrc = (img) => img?.currentSrc || img?.src || img?.dataset?.src || firstSrcsetUrl(img?.srcset);
                const featuredImage = document.querySelector(
                    '.poly-card.poly-card--list .poly-card__portada img.poly-component__picture, ' +
                    '.poly-card.poly-card--list img[data-testid="picture"].poly-component__picture, ' +
                    '.poly-card--list .poly-card__portada img, ' +
                    '.poly-card--list img[data-testid="picture"]'
                );
                const featuredImageUrl = absoluteUrl(imageSrc(featuredImage));
                if (featuredImageUrl && /https:\/\/[^/]*mlstatic\.com\//i.test(featuredImageUrl)) {
                    return featuredImageUrl;
                }

                for (const img of document.querySelectorAll('.poly-card__portada img.poly-component__picture, img[data-testid="picture"].poly-component__picture')) {
                    add(imageSrc(img), 5000000);
                }

                for (const selector of [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    'link[rel="image_src"]',
                ]) {
                    const element = document.querySelector(selector);
                    add(element?.content || element?.href, 1000);
                }

                for (const img of document.images) {
                    const src = imageSrc(img);
                    const text = `${img.alt || ''} ${img.className || ''}`.toLowerCase();
                    let score = (img.naturalWidth || 0) * (img.naturalHeight || 0);
                    if (img.closest('.poly-card__portada')) score += 5000000;
                    if (img.dataset?.testid === 'picture') score += 2500000;
                    if (text.includes('ui-pdp') || text.includes('gallery')) score += 500000;
                    if (text.includes('logo') || text.includes('avatar') || text.includes('icon')) score -= 1000000;
                    add(src, score);
                }

                for (const source of document.querySelectorAll('source[srcset]')) {
                    add(firstSrcsetUrl(source.srcset), 100);
                }

                return candidates
                    .filter((candidate) => (
                        /https:\/\/[^/]*mlstatic\.com\//i.test(candidate.url) ||
                        /https:\/\/m\.media-amazon\.com\//i.test(candidate.url)
                    ))
                    .filter((candidate) => (
                        /https:\/\/m\.media-amazon\.com\//i.test(candidate.url) ||
                        /D_NQ|product|MLB/i.test(candidate.url)
                    ))
                    .sort((left, right) => right.score - left.score)[0]?.url || null;
            }
            """
        )
        if image_url and (MERCADO_LIVRE_IMAGE_HOST_RE.search(image_url) or AMAZON_IMAGE_HOST_RE.search(image_url)):
            return image_url
        return None

    def _extract_product_href(self, page) -> str | None:
        selectors = [
            "a.poly-component__link--action-link",
            "a:has-text('Ir para produto')",
            "a[href*='polycard_client']",
            "a[href*='source=affiliate-profile']",
            "a[href*='/p/MLB']",
            "a[href*='wid=MLB']",
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            if locator.count() == 0:
                continue
            href = locator.get_attribute("href")
            if href and extract_ml_ids(href):
                return href

        links = page.evaluate(
            """
            () => Array.from(document.links).map((link) => ({
                text: link.innerText || "",
                href: link.href || ""
            }))
            """
        )
        for link in links:
            href = link.get("href", "")
            text = link.get("text", "")
            if ("Ir para produto" in text or extract_ml_ids(href)) and extract_ml_ids(href):
                return href

        content = page.content()
        for match in PRODUCT_HREF_RE.findall(content):
            href = html.unescape(match)
            if extract_ml_ids(href):
                return href
        return None

    def _add_cookie_header(self, context) -> None:
        cookies = []
        for raw_cookie in self._cookie_header.split(";"):
            if "=" not in raw_cookie:
                continue
            name, value = raw_cookie.strip().split("=", 1)
            if not name:
                continue
            for domain in self._cookie_domains:
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
        LOGGER.info("Browser debug written: %s and %s", html_path, png_path)
