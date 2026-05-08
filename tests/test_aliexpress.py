import os
import sys
import logging
from pathlib import Path

# Add the project root to sys.path to allow importing offers_bot
# Since this file is in 'tests/', the root is the parent directory
sys.path.append(str(Path(__file__).parent.parent))

from offers_bot.aliexpress import AliExpressClient, COIN_INDEX_URL
from offers_bot.parser import extract_offers, extract_aliexpress_product_id
from offers_bot.main import format_offer
from dotenv import load_dotenv

# Set up logging to see SDK errors
logging.basicConfig(level=logging.INFO)


def test_extract_aliexpress_product_id():
    cases = [
        (
            "https://pt.aliexpress.com/item/1005010496774905.html?invitationCode=xxx",
            "1005010496774905",
        ),
        ("https://pt.aliexpress.com/item/1005010496774905.html", "1005010496774905"),
        (
            "https://best.aliexpress.com/?productIds=1005009410346733&aff_fcid=xxx",
            "1005009410346733",
        ),
        (
            "https://best.aliexpress.com/?_immersiveMode=true&from=syicon&productIds=1005008745104996",
            "1005008745104996",
        ),
        ("https://s.click.aliexpress.com/e/_c4LBE5wb", None),
        ("https://a.aliexpress.com/_c3iwj7Qj", None),
    ]
    for url, expected in cases:
        result = extract_aliexpress_product_id(url)
        assert result == expected, f"FAIL: {url} → {result!r}, expected {expected!r}"
    print("[OK] All product ID extractions passed!")


def test_build_coin_index_url():
    expected = "https://m.aliexpress.com/p/coin-index/index.html?_immersiveMode=true&from=syicon&productIds=1005010142532174"
    result = COIN_INDEX_URL.format(product_id="1005010142532174")
    assert result == expected, f"Mismatch: {result} != {expected}"
    print("[OK] Coin-index URL format correct!")


def test_aliexpress_message_parsing():
    """Test real message parsing and Telegram formatting"""
    test_cases = [
        {
            "id": "Standard with multiple coupons",
            "text": """🇧🇷  Aliexpress

 LibreTx Processador Ryzen 5 5600 6Core CPU para Jogos Soquete AM4 Estoque no Brasil
⚠️🛒Produto no Brasil

💵🔥 Valor : R$ 717,51 9x de 79,72 sem juros
🏷 Cupom:  LIBRETX5600 + IFPAF7UN ou  MAES5

🥇 Link com moedas:
🔗 https://s.click.aliexpress.com/e/_c4LBE5wb""",
            "expected_price": "R$ 717,51",
            "expected_coupon": "LIBRETX5600 ou IFPAF7UN ou MAES5",
            "expected_installment": "9X SEM JUROS",
        },
        {
            "id": "Projector (No spacing in price)",
            "text": """Projetor portátil TOPTRO Full HD 1080P
R$279,72
Moedas No APP + MAES3
Link¹: https://s.click.aliexpress.com/e/_c3Goue9Z""",
            "expected_price": "R$ 279,72",
            "expected_coupon": "MAES3",
            "expected_installment": None,
        },
        {
            "id": "UGREEN Hub (Inline coupon with data)",
            "text": """🛍️ UGREEN USB-C HUB 9-in-1
💹 R$ 179 com cupom: ZH5533 + IFPIQRSZ + Moedas no App
Link App: https://a.aliexpress.com/_c3iwj7Qj""",
            "expected_price": "R$ 179",
            "expected_coupon": "ZH5533 ou IFPIQRSZ",
            "expected_installment": None,
        },
        {
            "id": "Tronsmart (Coupon + Announcement rescue)",
            "text": """Caixa de Som Tronsmart T8 Mini 16w
R$ 110~~
-CUPOM: MAES2 + Resgate cupom do anúncio + moedas no APP
https://s.click.aliexpress.com/e/_c2Q2ElYr""",
            "expected_price": "R$ 110",
            "expected_coupon": "MAES2",
            "expected_installment": None,
        },
        {
            "id": "SSD (Multiple coupon variants)",
            "text": """SSD Nvme M2 2TB 7000mbs
R$ 948
-CUPOM: KOOTION40 ou KOOTION401 + MAES6 + 1040 moedas no APP
https://s.click.aliexpress.com/e/_c3a2kGc3""",
            "expected_price": "R$ 948",
            "expected_coupon": "KOOTION40 ou KOOTION401 ou MAES6",
            "expected_installment": None,
        },
    ]

    for case in test_cases:
        print(f"Testing case: {case['id']}")
        offers = extract_offers(case["text"])
        assert len(offers) >= 1, f"Failed to find offer in {case['id']}"

        offer = offers[0]
        simulated_url = "https://s.click.aliexpress.com/e/_SIMULATED"
        formatted = format_offer(offer, simulated_url)

        # Assertions
        if case["expected_price"]:
            assert case["expected_price"] in formatted, (
                f"Price mismatch in {case['id']}. Found: {offer.price}"
            )
        if case["expected_coupon"]:
            assert case["expected_coupon"] in formatted, (
                f"Coupon mismatch in {case['id']}. Found: {offer.coupon}"
            )
        if case["expected_installment"]:
            assert case["expected_installment"] in formatted, (
                f"Installment mismatch in {case['id']}. Found: {offer.installment_info}"
            )

        # Display the formatted message
        print(f"\n--- FORMATTED MESSAGE: {case['id']} ---")
        safe_display = (
            formatted.replace("🛍️", "[SHOP]")
            .replace("💰", "[CASH]")
            .replace("🎟️", "[COUPON]")
            .replace("🔗", "[LINK]")
            .replace("🏷️", "[LABEL]")
        )
        print(safe_display)
        print("-" * (25 + len(case["id"])) + "\n")

        print(f"  [OK] {case['id']} passed.")

    print("\n[OK] All message patterns verified successfully!")


def test_aliexpress_api():
    """Test real API integration"""
    load_dotenv()

    app_key = os.getenv("ALIEXPRESS_APP_KEY")
    app_secret = os.getenv("ALIEXPRESS_APP_SECRET")
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID", "default")

    if not app_key or not app_secret:
        print("\n[SKIP] API Key not configured in .env")
        return

    client = AliExpressClient(app_key, app_secret, tracking_id)
    test_url = "https://a.aliexpress.com/_mMNsFKn"

    try:
        affiliate_link = client.create_link(test_url)
        assert affiliate_link.short_url is not None
        print(f"[OK] Link converted: {affiliate_link.short_url}")
    except Exception as e:
        print(f"[ERROR] API failure: {e}")


if __name__ == "__main__":
    print("Starting AliExpress tests...")
    test_extract_aliexpress_product_id()
    test_build_coin_index_url()
    test_aliexpress_message_parsing()
    test_aliexpress_api()
