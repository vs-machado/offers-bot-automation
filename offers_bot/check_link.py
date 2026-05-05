from __future__ import annotations

import argparse

from .amazon import AmazonClient
from .config import load_settings
from .mercado_livre import MercadoLivreClient
from .parser import is_amazon_url, is_shopee_url
from .shopee import ShopeeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one affiliate link.")
    parser.add_argument("url", help="Mercado Livre, Amazon, or Shopee product URL")
    args = parser.parse_args()

    settings = load_settings()
    if is_amazon_url(args.url):
        client = AmazonClient(
            tag=settings.amazon_affiliate_tag,
            cookie_header=settings.amazon_cookie_header,
            marketplace_id=settings.amazon_marketplace_id,
        )
    elif is_shopee_url(args.url):
        client = ShopeeClient(
            cookie_header=settings.shopee_cookie_header,
            csrf_token=settings.shopee_csrf_token,
            af_ac_enc_dat=settings.shopee_af_ac_enc_dat,
            af_ac_enc_sz_token=settings.shopee_af_ac_enc_sz_token,
            x_sap_ri=settings.shopee_x_sap_ri,
            x_sap_sec=settings.shopee_x_sap_sec,
            headless=settings.browser_headless,
            timeout_ms=settings.browser_timeout_ms,
            debug_dir=settings.browser_debug_dir,
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
