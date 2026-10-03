#!/usr/bin/env python3
"""Fill in stories.word_count and stories.reading_minutes.

Rows written before the reading-time columns existed store 0. The Go reader
derives the estimate on read for those, so the badge is never blank; this
script writes the values back so the stored data is correct for anything that
queries the database directly. It is idempotent and safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "readingtime.db"
WORDS_PER_MINUTE = 140
WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)


def measure(pages_json: str) -> tuple[int, int]:
    words = 0
    try:
        pages = json.loads(pages_json)
    except json.JSONDecodeError:
        return 0, 0
    if not isinstance(pages, list):
        return 0, 0
    for page in pages:
        if isinstance(page, dict) and isinstance(page.get("text"), str):
            words += len(WORD_RE.findall(page["text"]))
    return words, max(1, -(-words // WORDS_PER_MINUTE))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    db = args.db if args.db.is_absolute() else ROOT / args.db
    if not db.is_file():
        print(f"backfill_reading_time: database does not exist: {db}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(db, timeout=5)
    try:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(stories)")}
        missing = sorted({"word_count", "reading_minutes"} - columns)
        if missing:
            print(
                f"backfill_reading_time: stories table is missing columns: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

        updates: list[tuple[int, int, str]] = []
        for story_id, pages_json in connection.execute(
            "SELECT id, pages_json FROM stories WHERE reading_minutes = 0 OR word_count = 0"
        ):
            words, minutes = measure(pages_json)
            if words:
                updates.append((words, minutes, story_id))

        if not updates:
            print("backfill_reading_time: nothing to do")
            return 0
        if args.dry_run:
            print(f"would update {len(updates)} stories")
            return 0

        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "UPDATE stories SET word_count = ?, reading_minutes = ? WHERE id = ?", updates
        )
        connection.commit()
    except sqlite3.Error as exc:
        if connection.in_transaction:
            connection.rollback()
        print(f"backfill_reading_time: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()

    print(f"backfilled {len(updates)} stories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
