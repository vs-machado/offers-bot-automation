import os

# Disable LLM parsing by default for all tests (test_llm_parser.py will explicitly re-enable it)
os.environ["DISABLE_LLM"] = "true"
