import unittest

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

    def evaluate(self, script: str):
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


if __name__ == "__main__":
    unittest.main()
