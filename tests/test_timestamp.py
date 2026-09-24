"""Tests for timestamp normalization and plausibility."""

import datetime
import pandas as pd
import pytest

from coin_behavior_engine.utils.timestamp import (
    detect_timestamp_unit,
    to_utc_datetime,
    to_utc_ms,
    validate_timestamp_plausibility,
)


def test_detect_timestamp_unit():
    assert detect_timestamp_unit(1767225600) == "s"
    assert detect_timestamp_unit(1767225600000) == "ms"
    assert detect_timestamp_unit(1767225600000000) == "us"
    assert detect_timestamp_unit(1767225600000000000) == "ns"


def test_to_utc_datetime_from_ms():
    ms = 1767225600000  # 2026-01-01 00:00:00 UTC
    dt = to_utc_datetime(ms)
    assert dt.year == 2026
    assert dt.month == 1
    assert dt.day == 1
    assert dt.hour == 0
    assert dt.tz is not None
    assert str(dt.tz) == "UTC"


def test_to_utc_datetime_from_string():
    s = "2026-05-15T14:30:00Z"
    dt = to_utc_datetime(s)
    assert dt.year == 2026
    assert dt.month == 5
    assert dt.day == 15
    assert dt.hour == 14
    assert dt.minute == 30
    assert str(dt.tz) == "UTC"


def test_to_utc_ms_roundtrip():
    ms_original = 1767225600000
    dt = to_utc_datetime(ms_original)
    ms_converted = to_utc_ms(dt)
    assert ms_original == ms_converted


def test_validate_timestamp_plausibility():
    assert validate_timestamp_plausibility(1767225600000) is True
    assert validate_timestamp_plausibility("2026-01-01T00:00:00Z") is True
    # Year 1970 or 3000 outside [2000, 2100]
    assert validate_timestamp_plausibility(0) is False
    assert validate_timestamp_plausibility(50000000000000) is False
