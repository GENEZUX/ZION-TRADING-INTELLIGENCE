"""DB-01 / DB-02: transactional integrity and JSONL/SQLite parity."""

import json
import sqlite3
import tempfile
from pathlib import Path

from src.store.init import init_db


def test_failed_transaction_leaves_no_partial_rows():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        init_db(db)
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                conn.execute(
                    "INSERT INTO raw_records "
                    "(source_id, run_id, raw_payload, raw_payload_hash, ingested_at_utc) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("s", "missing-run", b"x", "h", "2026-01-01T00:00:00Z"),
                )
                conn.commit()
                assert False, "insert should have failed"
            except sqlite3.IntegrityError:
                conn.rollback()
            count = conn.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0]
            assert count == 0
        finally:
            conn.close()


def test_jsonl_matches_sqlite_count():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        jsonl = Path(tmp) / "export.jsonl"
        init_db(db)

        rows = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}]
        with jsonl.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "INSERT INTO runs (run_id, kind, started_at_utc, code_version, "
                "params_json, status) VALUES (?,?,?,?,?,?)",
                ("r1", "ingest", "2026-01-01T00:00:00Z", "test", "{}", "ok"),
            )
            for i, _ in enumerate(rows):
                conn.execute(
                    "INSERT INTO raw_records "
                    "(source_id, run_id, raw_payload, raw_payload_hash, "
                    "ingested_at_utc) VALUES (?,?,?,?,?)",
                    ("s", "r1", b"x", f"h{i}", "2026-01-01T00:00:00Z"),
                )
            conn.commit()
            db_count = conn.execute("SELECT COUNT(*) FROM raw_records").fetchone()[0]
        finally:
            conn.close()

        with jsonl.open(encoding="utf-8") as fh:
            jsonl_count = sum(1 for _ in fh)

        assert db_count == jsonl_count == 2
