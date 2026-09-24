"""Timestamp utilities ensuring UTC consistency, unit auto-detection, and plausibility."""

from __future__ import annotations

import datetime
from typing import Union
import pandas as pd


def detect_timestamp_unit(ts: int | float) -> str:
    """Detect whether a numeric timestamp is in seconds, milliseconds, microseconds, or nanoseconds."""
    abs_ts = abs(float(ts))
    if abs_ts < 1e11:  # ~10 digits -> seconds (e.g. 1767225600 for 2026)
        return "s"
    elif abs_ts < 1e14:  # ~13 digits -> milliseconds (e.g. 1767225600000)
        return "ms"
    elif abs_ts < 1e17:  # ~16 digits -> microseconds
        return "us"
    else:  # ~19 digits -> nanoseconds
        return "ns"


def to_utc_datetime(ts: Union[int, float, str, datetime.datetime, pd.Timestamp]) -> pd.Timestamp:
    """Normalize any timestamp into a UTC-aware pd.Timestamp."""
    if isinstance(ts, pd.Timestamp):
        if ts.tz is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    if isinstance(ts, datetime.datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        return pd.Timestamp(ts).tz_convert("UTC")

    if isinstance(ts, (int, float)):
        unit = detect_timestamp_unit(ts)
        return pd.to_datetime(ts, unit=unit, utc=True)

    if isinstance(ts, str):
        return pd.to_datetime(ts, utc=True)

    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


def to_utc_ms(ts: Union[int, float, str, datetime.datetime, pd.Timestamp]) -> int:
    """Convert any timestamp representation to integer Unix epoch milliseconds (UTC)."""
    dt = to_utc_datetime(ts)
    return int(dt.timestamp() * 1000)


def validate_timestamp_plausibility(
    ts: Union[int, float, pd.Timestamp],
    min_year: int = 2000,
    max_year: int = 2100
) -> bool:
    """Verify that a timestamp falls within a reasonable calendar window."""
    try:
        dt = to_utc_datetime(ts)
        return min_year <= dt.year <= max_year
    except Exception:
        return False
