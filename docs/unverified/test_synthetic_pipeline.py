"""PIPE-01: synthetic fixtures are validated and stored, append-only."""

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from src.pipeline.synthetic_run import run_synthetic

REASON_COLUMNS = (
    "reason_code",
    "quarantine_code",
    "violation_code",
    "error_code",
    "reason",
)
EXPECTED = {"SCHEMA_MISSING", "NON_NUMERIC", "PRICE_NEGATIVE", "HIGH_LT_LOW"}


def test_pipeline_stores_valid_rows_and_quarantines_broken_fixtures():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "zion.db"
        summary = run_synthetic(db, count=5, include_broken=True)
        assert summary["valid"] == 5
        assert summary["quarantine"] == 4
        assert summary["normalized"] == 5
        assert summary["evidence"] == 1
        assert summary["raw"] >= 5

        conn = sqlite3.connect(db)
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(quarantine)")]
            reason_col = next((name for name in REASON_COLUMNS if name in cols), None)
            assert reason_col, cols
            got = {
                row[0]
                for row in conn.execute(
                    'SELECT "' + reason_col + '" FROM quarantine WHERE run_id = ?',
                    (summary["run_id"],),
                )
            }
        finally:
            conn.close()
        assert got == EXPECTED


def test_second_run_appends_without_deleting_the_first():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "zion.db"
        first = run_synthetic(db, count=5, include_broken=True)
        second = run_synthetic(
            db,
            count=3,
            include_broken=False,
            start_utc=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        assert first["run_id"] != second["run_id"]
        assert second["valid"] == 3
        assert second["quarantine"] == 0

        conn = sqlite3.connect(db)
        try:
            total_norm = conn.execute("SELECT COUNT(*) FROM normalized_records").fetchone()[0]
            total_quar = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        finally:
            conn.close()
        assert total_norm == 8
        assert total_quar == 4
