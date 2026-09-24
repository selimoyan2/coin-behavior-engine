"""Tests for data validation pipeline."""

import pandas as pd
import pytest

from coin_behavior_engine.validation.validator import DataValidator, IssueSeverity


@pytest.fixture
def clean_sample_5m():
    return pd.DataFrame({
        "timestamp_open": [1767225600000, 1767225900000, 1767226200000, 1767226500000],
        "timestamp_close": [1767225899999, 1767226199999, 1767226499999, 1767226799999],
        "open": [90000.0, 90100.0, 90200.0, 90150.0],
        "high": [90150.0, 90250.0, 90300.0, 90200.0],
        "low": [89950.0, 90050.0, 90100.0, 90100.0],
        "close": [90100.0, 90200.0, 90150.0, 90180.0],
        "volume": [10.5, 12.0, 14.2, 9.8],
        "trade_count": [100, 120, 140, 95],
    })


def test_validation_passes_on_clean_data(clean_sample_5m):
    validator = DataValidator()
    report = validator.validate(clean_sample_5m)
    assert report["validation_passed"] is True
    assert report["missing_candles_count"] == 0
    assert report["severity_summary"]["CRITICAL"] == 0


def test_validation_detects_gap(clean_sample_5m):
    df_gap = clean_sample_5m.copy()
    # Skip one 5m interval between row 1 and row 2 (add 600,000 ms instead of 300,000 ms)
    df_gap.loc[2, "timestamp_open"] += 300_000
    df_gap.loc[3, "timestamp_open"] += 300_000

    validator = DataValidator()
    report = validator.validate(df_gap)
    assert report["missing_candles_count"] == 1
    assert any(iss["issue_type"] == "MISSING_CANDLES_GAP" for iss in report["issues"])


def test_validation_detects_inverted_ohlc(clean_sample_5m):
    df_corrupted = clean_sample_5m.copy()
    df_corrupted.loc[1, "high"] = 89000.0  # high < low
    df_corrupted.loc[1, "low"] = 90500.0

    validator = DataValidator()
    report = validator.validate(df_corrupted)
    assert report["validation_passed"] is False
    assert report["severity_summary"]["CRITICAL"] > 0
    assert any(iss["issue_type"] == "OHLC_HIGH_LESS_THAN_LOW" for iss in report["issues"])


def test_validation_detects_open_close_out_of_bounds(clean_sample_5m):
    df_bad = clean_sample_5m.copy()
    df_bad.loc[0, "close"] = 99999.0  # close > high

    validator = DataValidator()
    report = validator.validate(df_bad)
    assert report["validation_passed"] is False
    assert any(iss["issue_type"] == "OHLC_CLOSE_OUT_OF_BOUNDS" for iss in report["issues"])


def test_validation_detects_negative_volume(clean_sample_5m):
    df_bad = clean_sample_5m.copy()
    df_bad.loc[2, "volume"] = -5.0

    validator = DataValidator()
    report = validator.validate(df_bad)
    assert report["validation_passed"] is False
    assert any(iss["issue_type"] == "NEGATIVE_VOLUME" for iss in report["issues"])
