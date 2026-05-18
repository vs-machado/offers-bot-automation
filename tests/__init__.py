import os
from unittest.mock import MagicMock

# Disable LLM parsing by default for all tests (test_llm_parser.py will explicitly re-enable it)
os.environ["DISABLE_LLM"] = "true"

# Set dummy environment variables for tests to avoid loading real configurations/sessions
os.environ["TELEGRAM_API_ID"] = "123456"
os.environ["TELEGRAM_API_HASH"] = "dummy_hash"
os.environ["TELEGRAM_SESSION"] = "data/offers_bot_test"
os.environ["SOURCE_CHATS"] = "chat1,chat2"
os.environ["TARGET_CHAT"] = "target_chat"

# Mock Telethon TelegramClient globally during tests to prevent real connections
import telethon

telethon.TelegramClient = MagicMock()
