import os
import sys
import logging
from pathlib import Path

# Add the project root to sys.path to allow importing offers_bot
# Since this file is in 'tests/', the root is the parent directory
sys.path.append(str(Path(__file__).parent.parent))

from offers_bot.aliexpress import AliExpressClient
from dotenv import load_dotenv

# Set up logging to see SDK errors
logging.basicConfig(level=logging.INFO)

def test_aliexpress():
    load_dotenv()
    
    app_key = os.getenv("ALIEXPRESS_APP_KEY")
    app_secret = os.getenv("ALIEXPRESS_APP_SECRET")
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID", "default")

    if not app_key or not app_secret:
        print("❌ Error: ALIEXPRESS_APP_KEY or ALIEXPRESS_APP_SECRET not found in .env")
        return

    client = AliExpressClient(
        app_key=app_key,
        app_secret=app_secret,
        tracking_id=tracking_id
    )

    # Example AliExpress product link (using a different one to avoid regional restrictions)
    test_url = "https://a.aliexpress.com/_mMNsFKn"
    
    print(f"Testing link conversion for: {test_url}")
    try:
        affiliate_link = client.create_link(test_url)
        print("Success!")
        print(f"Short URL: {affiliate_link.short_url}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_aliexpress()
