#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a WIR 0.1 SQLite database")
    parser.add_argument("database", type=Path)
    parser.add_argument("--migration", type=Path, default=Path("storage/migrations/0001_initial.sql"))
    args = parser.parse_args()
    sql = args.migration.read_text(encoding="utf-8")
    with sqlite3.connect(args.database) as connection:
        connection.executescript(sql)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, datetime('now'))",
            (1, "0001_initial"),
        )
        connection.commit()
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"{args.database}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
