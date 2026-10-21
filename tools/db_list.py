"""List tables in the ZION SQLite database.

Usage (from the repo root):

    py -3.12 tools/db_list.py

Does not create the database. If it is missing, prints a clear message
pointing at the init script. No network. No credentials.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "zion.db"


def main() -> int:
    if not DB_PATH.is_file():
        print(f"No database yet: {DB_PATH}")
        print("Initialize it with:")
        print("    py -3.12 -m src.store.init")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("Database exists but contains no tables.")
        print("Initialize it with:")
        print("    py -3.12 -m src.store.init")
        return 1

    print(f"Tables in {DB_PATH}:")
    for (name,) in rows:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
