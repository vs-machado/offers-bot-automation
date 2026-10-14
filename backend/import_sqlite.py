"""Import legacy operator state without deleting or modifying the SQLite source."""

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3

from dotenv import load_dotenv

from offers_bot.postgres_store import connect


def import_state(path: Path) -> None:
    """Copy sessions and accounting atomically; repeated imports are idempotent."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        with connect() as target:
            if "telegram_sessions" in tables:
                for name, session in source.execute(
                    "SELECT user_id, session_string FROM telegram_sessions"
                ):
                    target.execute(
                        "INSERT INTO platform_telegram_sessions (name, session_string) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                        (name, session),
                    )
            if "token_usage" in tables:
                for row in source.execute(
                    "SELECT id, timestamp, prompt_tokens, completion_tokens, total_tokens FROM token_usage"
                ):
                    legacy_id, timestamp, prompt, completion, total = row
                    target.execute(
                        """INSERT INTO token_usage (legacy_id, timestamp, prompt_tokens, completion_tokens, total_tokens)
                        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (legacy_id) DO NOTHING""",
                        (
                            legacy_id,
                            datetime.fromisoformat(timestamp),
                            prompt,
                            completion,
                            total,
                        ),
                    )
    print("Import completed. SQLite source preserved.")


def main() -> None:
    """Load operator configuration and import a single legacy database."""
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    import_state(parser.parse_args().source)


if __name__ == "__main__":
    main()
