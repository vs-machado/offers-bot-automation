from __future__ import annotations

import argparse

from .amazon import AmazonClient
from .config import load_settings
from .mercado_livre import MercadoLivreClient
from .parser import is_amazon_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one affiliate link.")
    parser.add_argument("url", help="Mercado Livre or Amazon product URL")
    args = parser.parse_args()

    settings = load_settings()
    if is_amazon_url(args.url):
        client = AmazonClient(
            tag=settings.amazon_affiliate_tag,
            cookie_header=settings.amazon_cookie_header,
            marketplace_id=settings.amazon_marketplace_id,
        )
    else:
        client = MercadoLivreClient(
            tag=settings.ml_affiliate_tag,
            cookie_header=settings.ml_cookie_header,
            csrf_token=settings.ml_csrf_token,
        )
    link = client.create_link(args.url)
    print(link.short_url)


if __name__ == "__main__":
    main()
