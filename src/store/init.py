"""Create and initialize data/zion.db according to SPECIFICATION.md §4.

Usage (from the repo root):

    py -3.12 -m src.store.init

Idempotent: running twice is safe. Existing tables are not modified.
No network access. No credentials. No trading operations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "zion.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    kind            TEXT NOT NULL
                    CHECK (kind IN ('ingest','analytics','backtest','report')),
    started_at_utc  TEXT NOT NULL,
    finished_at_utc TEXT,
    code_version    TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('running','ok','failed','aborted'))
);

CREATE TABLE IF NOT EXISTS raw_records (
    raw_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id        TEXT NOT NULL,
    run_id           TEXT NOT NULL REFERENCES runs(run_id),
    raw_payload      BLOB NOT NULL,
    raw_payload_hash TEXT NOT NULL,
    ingested_at_utc  TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_records_source_hash
    ON raw_records (source_id, raw_payload_hash);

CREATE TABLE IF NOT EXISTS normalized_records (
    norm_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id          INTEGER NOT NULL REFERENCES raw_records(raw_id),
    source_id       TEXT NOT NULL,
    instrument_id   TEXT NOT NULL,
    asset_class     TEXT NOT NULL,
    event_time_utc  TEXT NOT NULL,
    interval        TEXT,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    volume          REAL,
    volume_unit     TEXT,
    quality_status  TEXT NOT NULL
                    CHECK (quality_status IN ('ok','quarantined')),
    ingested_at_utc TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_normalized_identity
    ON normalized_records (source_id, instrument_id, event_time_utc, interval);

CREATE TABLE IF NOT EXISTS quarantine (
    q_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id          INTEGER REFERENCES raw_records(raw_id),
    reason_code     TEXT NOT NULL
                    CHECK (reason_code IN (
                        'SCHEMA_MISSING','NON_NUMERIC','PRICE_NEGATIVE',
                        'HIGH_LT_LOW','DUPLICATE','TZ_UNRESOLVED','HASH_MISMATCH'
                    )),
    detail          TEXT,
    detected_at_utc TEXT NOT NULL,
    replayable      INTEGER NOT NULL CHECK (replayable IN (0,1))
);

CREATE TABLE IF NOT EXISTS evidence_log (
    ev_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id   TEXT REFERENCES runs(run_id),
    kind     TEXT NOT NULL CHECK (kind IN ('check','decision','exception')),
    message  TEXT NOT NULL,
    at_utc   TEXT NOT NULL
);
"""


def init_db(db_path: Path = DB_PATH) -> Path:
    """Create the data directory and apply the schema. Returns the DB path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return db_path


def main() -> None:
    path = init_db()
    print(f"OK: {path}")
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (name,) in rows:
            print(f"  table: {name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
