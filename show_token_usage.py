#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def show_stats():
    db_path = os.getenv("DATABASE_PATH", "data/offers.sqlite3")
    if not Path(db_path).exists():
        print(f"Database not found at: {db_path}")
        print("No requests registered yet.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'"
        )
        if not cursor.fetchone():
            print("No token usage history table found in database yet.")
            return

        # Today's stats
        cursor.execute(
            """
            SELECT 
                COUNT(*),
                SUM(prompt_tokens),
                SUM(completion_tokens),
                SUM(total_tokens)
            FROM token_usage
            WHERE date(timestamp, 'localtime') = date('now', 'localtime')
            """
        )
        today = cursor.fetchone()
        count, prompt, completion, total = today
        count = count or 0
        prompt = prompt or 0
        completion = completion or 0
        total = total or 0

        print("=" * 50)
        print("📊 TODAY'S TOKEN USAGE STATS")
        print("=" * 50)
        print(f"Requests:          {count}")
        print(f"Prompt Tokens:     {prompt:,}")
        print(f"Response Tokens:   {completion:,}")
        print(f"Total Tokens:      {total:,}")
        print()

        # Daily history stats
        print("=" * 50)
        print("📅 DAILY TOKEN USAGE HISTORY")
        print("=" * 50)
        cursor.execute(
            """
            SELECT 
                date(timestamp, 'localtime') as day,
                COUNT(*),
                SUM(prompt_tokens),
                SUM(completion_tokens),
                SUM(total_tokens)
            FROM token_usage
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """
        )
        rows = cursor.fetchall()
        print(
            f"{'Date':<12} | {'Requests':<8} | {'Prompt':<10} | {'Response':<10} | {'Total':<10}"
        )
        print("-" * 60)
        for row in rows:
            day, reqs, p, c, t = row
            print(
                f"{day:<12} | {reqs:<8} | {p or 0:<10,} | {c or 0:<10,} | {t or 0:<10,}"
            )
        print()

        # Last 5 requests
        print("=" * 50)
        print("⏱️ LAST 5 REQUESTS DETAIL")
        print("=" * 50)
        cursor.execute(
            """
            SELECT timestamp, prompt_tokens, completion_tokens, total_tokens
            FROM token_usage
            ORDER BY timestamp DESC
            LIMIT 5
            """
        )
        rows = cursor.fetchall()
        for idx, row in enumerate(rows, 1):
            ts, p, c, t = row
            print(f"{idx}. {ts} | Prompt: {p} | Response: {c} | Total: {t}")
        print("=" * 50)

        conn.close()
    except Exception as e:
        print(f"Error querying token usage: {e}")


if __name__ == "__main__":
    show_stats()
