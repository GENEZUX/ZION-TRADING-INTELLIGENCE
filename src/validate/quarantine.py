"""Quarantine reason codes and record-level checks (SPECIFICATION.md §5).

Every function here is pure: input -> (reason_code or None). No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

REASON_CODES = (
    "SCHEMA_MISSING",
    "NON_NUMERIC",
    "PRICE_NEGATIVE",
    "HIGH_LT_LOW",
    "DUPLICATE",
    "TZ_UNRESOLVED",
    "HASH_MISMATCH",
)

REQUIRED_FIELDS = (
    "source_id",
    "instrument_id",
    "asset_class",
    "event_time_utc",
    "ingested_at_utc",
    "quality_status",
    "raw_payload_hash",
)

NUMERIC_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class CheckResult:
    reason_code: Optional[str]
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.reason_code is None


def check_required_fields(record: dict) -> CheckResult:
    missing = [f for f in REQUIRED_FIELDS if record.get(f) in (None, "")]
    if missing:
        return CheckResult("SCHEMA_MISSING", f"missing: {','.join(missing)}")
    return CheckResult(None)


def check_numeric(record: dict) -> CheckResult:
    for field in NUMERIC_FIELDS:
        value = record.get(field)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return CheckResult("NON_NUMERIC", f"{field}={value!r}")
    return CheckResult(None)


def check_prices(record: dict) -> CheckResult:
    for field in ("open", "high", "low", "close"):
        value = record.get(field)
        if value is not None and value < 0:
            return CheckResult("PRICE_NEGATIVE", f"{field}={value}")
    return CheckResult(None)


def check_high_low(record: dict) -> CheckResult:
    high = record.get("high")
    low = record.get("low")
    if high is not None and low is not None and high < low:
        return CheckResult("HIGH_LT_LOW", f"high={high} low={low}")
    return CheckResult(None)


def check_all_structural(record: dict) -> CheckResult:
    """Run every structural check that does not require external state."""
    for check in (check_required_fields, check_numeric, check_prices, check_high_low):
        result = check(record)
        if not result.ok:
            return result
    return CheckResult(None)
