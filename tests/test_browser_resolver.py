import unittest
from playwright.sync_api import sync_playwright

from offers_bot.browser_resolver import PlaywrightProductResolver


class _FakeLocator:
    def __init__(self, href: str | None) -> None:
        self._href = href

    @property
    def first(self) -> "_FakeLocator":
        return self

    def count(self) -> int:
        return 1 if self._href else 0

    def get_attribute(self, name: str) -> str | None:
        if name != "href":
            return None
        return self._href


class _FakePage:
    def __init__(self, selectors: dict[str, str | None]) -> None:
        self._selectors = selectors

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self._selectors.get(selector))

    def evaluate(self, _script: str):
        return []

    def content(self) -> str:
        return ""


class BrowserResolverTest(unittest.TestCase):
    def test_extract_product_href_accepts_hyphenated_mlb_url(self):
        resolver = PlaywrightProductResolver()
        page = _FakePage(
            {
                "a.poly-component__link--action-link": (
                    "https://produto.mercadolivre.com.br/MLB-4222666581-"
                    "sapato-masculino-casual-couro-legitimo-calce-facil-macio-_JM"
                )
            }
        )

        href = resolver._extract_product_href(page)

        self.assertEqual(
            href,
            "https://produto.mercadolivre.com.br/MLB-4222666581-"
            "sapato-masculino-casual-couro-legitimo-calce-facil-macio-_JM",
        )

    def test_extract_product_image_prefers_featured_list_card_image(self):
        resolver = PlaywrightProductResolver()
        html = """
        <html>
          <body>
            <div class="poly-card poly-card--list poly-card--xlarge">
              <div class="poly-card__portada">
                <img class="poly-component__picture" data-testid="picture"
                  src="https://http2.mlstatic.com/D_Q_NP_2X_featured-MLB1111111111-V.webp"
                  alt="Featured product">
              </div>
            </div>
            <div class="poly-card poly-card--grid poly-card--xlarge">
              <div class="poly-card__portada">
                <img class="poly-component__picture" data-testid="picture"
                  src="https://http2.mlstatic.com/D_Q_NP_2X_grid-MLB2222222222-V.webp"
                  alt="Grid product">
              </div>
            </div>
            <meta property="og:image" content="https://http2.mlstatic.com/D_Q_NP_2X_meta-MLB3333333333-V.webp">
          </body>
        </html>
        """

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html)

            image_url = resolver._extract_product_image(page)

            browser.close()

        self.assertEqual(
            image_url,
            "https://http2.mlstatic.com/D_Q_NP_2X_featured-MLB1111111111-V.webp",
        )

    def test_extract_product_image_prefers_amazon_data_old_hires(self):
        resolver = PlaywrightProductResolver()
        html = """
        <html>
          <body>
            <li class="image item itemNo0 selected maintain-height cursorPointer variant-MAIN">
              <span class="a-list-item">
                <span class="a-declarative">
                  <div id="imgTagWrapperId" class="imgTagWrapper">
                    <img
                      id="landingImage"
                      data-a-image-name="landingImage"
                      src="https://m.media-amazon.com/images/I/41Zguc9CziL._AC_SX522_.jpg"
                      data-old-hires="https://m.media-amazon.com/images/I/41Zguc9CziL._AC_SL1000_.jpg"
                      alt="Apple iPhone 16e de 128 GB - Branco"
                    >
                  </div>
                </span>
              </span>
            </li>
          </body>
        </html>
        """

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html)

            image_url = resolver._extract_product_image(page)

            browser.close()

        self.assertEqual(
            image_url,
            "https://m.media-amazon.com/images/I/41Zguc9CziL._AC_SL1000_.jpg",
        )


if __name__ == "__main__":
    unittest.main()
