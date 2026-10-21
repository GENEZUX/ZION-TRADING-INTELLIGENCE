"""Deterministic synthetic fixture generator.

Produces plausible OHLCV records that satisfy SPECIFICATION.md §3, plus a
deliberate set of broken records to exercise the quarantine codes.

No network. No disk writes. Caller receives lists in memory.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_records(
    source_id: str = "synthetic",
    instrument_id: str = "BTC/USD",
    asset_class: str = "crypto",
    start_utc: datetime = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    count: int = 10,
    interval: str = "1h",
) -> list[dict]:
    """Return `count` valid records, deterministic for the given arguments."""
    out: list[dict] = []
    price = 100.0
    for i in range(count):
        event = start_utc + timedelta(hours=i)
        open_ = price
        close = round(open_ + ((i * 7) % 5) - 2, 4)
        high = round(max(open_, close) + 1, 4)
        low = round(min(open_, close) - 1, 4)
        volume = round(10 + (i % 3), 4)
        payload = {
            "source_id": source_id,
            "instrument_id": instrument_id,
            "asset_class": asset_class,
            "event_time_utc": _iso_utc(event),
            "interval": interval,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        payload["raw_payload_hash"] = _sha256_hex(
            json.dumps(payload, sort_keys=True).encode()
        )
        payload["ingested_at_utc"] = _iso_utc(datetime.now(timezone.utc))
        payload["quality_status"] = "ok"
        out.append(payload)
        price = close
    return out


def broken_records() -> dict[str, dict]:
    """One record per structural quarantine code, for tests."""
    base = valid_records(count=1)[0]

    def variant(**overrides) -> dict:
        r = dict(base)
        r.update(overrides)
        return r

    return {
        "SCHEMA_MISSING":   variant(source_id=""),
        "NON_NUMERIC":      variant(close="not-a-number"),
        "PRICE_NEGATIVE":   variant(open=-1.0),
        "HIGH_LT_LOW":      variant(high=1.0, low=2.0),
    }


def iter_valid(records: Iterable[dict]) -> Iterable[dict]:
    """Convenience filter for tests."""
    for r in records:
        if r.get("quality_status") == "ok":
            yield r
