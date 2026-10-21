"""DAT-04 / QAR-01: every structural quarantine code triggered by a fixture."""

from src.ingest.synthetic import broken_records, valid_records
from src.validate.quarantine import check_all_structural


def test_valid_record_passes():
    record = valid_records(count=1)[0]
    assert check_all_structural(record).ok


def test_each_structural_code_triggered():
    broken = broken_records()
    for code, record in broken.items():
        result = check_all_structural(record)
        assert not result.ok, f"{code} should have failed"
        assert result.reason_code == code, (
            f"expected {code}, got {result.reason_code}"
        )
