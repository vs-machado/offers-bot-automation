from __future__ import annotations

import argparse

from .config import load_settings
from .mercado_livre import MercadoLivreClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one Mercado Livre affiliate link.")
    parser.add_argument("url", help="Mercado Livre product URL")
    args = parser.parse_args()

    settings = load_settings()
    client = MercadoLivreClient(
        tag=settings.ml_affiliate_tag,
        cookie_header=settings.ml_cookie_header,
        csrf_token=settings.ml_csrf_token,
    )
    link = client.create_link(args.url)
    print(link.short_url)


if __name__ == "__main__":
    main()
