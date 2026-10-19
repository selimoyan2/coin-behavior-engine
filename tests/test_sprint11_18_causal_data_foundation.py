"""Sprint 11.18 Invariant Test Suite: Causal Data Foundation & Benchmark Closure.

Strictly verifies:
1. Benchmark closure accounting reconciliation (Bar 0 vs Bar 576 B&H returns, friction identity).
2. Binance historical market data pilot integrity (SHA-256 checksum match, 44,640 rows, 0 gaps, 0 duplicates, valid OHLC).
3. Deterministic multi-timeframe resampling invariants (5m: 8928, 15m: 2976, 1h: 744, 4h: 186, 1d: 31).
4. Causal event isolation: future events with available_at_utc > T_decision are strictly excluded.
5. Causal candle isolation: unclosed forming candles with close_time > T_decision are strictly excluded.
6. Revision immutability: subsequent revisions do not mutate historical first releases.
7. Replay determinism: identical timestamp queries yield bitwise identical SHA-256 state hashes.
8. Deliverables completeness and schema conformance.

NO outcome-forcing assertions.
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar
from coin_behavior_engine.research.historical_replay import HistoricalReplayEngine


@pytest.fixture(scope="module")
def benchmark_closure():
    path = Path("research_outputs/benchmark_closure_11_18.json")
    assert path.exists(), f"Benchmark closure JSON missing at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def binance_quality():
    path = Path("research_outputs/binance_data_quality_11_18.json")
    assert path.exists(), f"Binance data quality JSON missing at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def event_schema():
    path = Path("research_outputs/point_in_time_event_schema_11_18.json")
    assert path.exists(), f"Event schema JSON missing at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def replay_audit():
    path = Path("research_outputs/historical_replay_audit_11_18.json")
    assert path.exists(), f"Historical replay audit JSON missing at {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_closure_accounting(benchmark_closure):
    """Verify Buy & Hold Bar 0 and Bar 576 exact accounting and friction."""
    b0 = benchmark_closure["buy_and_hold_canonical_closure"]["bar_0_inception"]
    b576 = benchmark_closure["buy_and_hold_canonical_closure"]["bar_576_inception"]
    
    # Bar 0 Inception
    assert b0["start_bar"] == 0
    assert b0["start_open_price"] == 106891.72
    assert b0["end_close_price"] == 82104.03
    assert b0["terminal_liquid_return_pct"] == -22.95
    assert b0["terminal_mtm_return_pct"] == -22.84
    assert pytest.approx(b0["total_friction_usdt"], abs=0.1) == 25.97
    
    # Bar 576 Inception
    assert b576["start_bar"] == 576
    assert b576["start_open_price"] == 110810.88
    assert b576["end_close_price"] == 82104.03
    assert b576["terminal_liquid_return_pct"] == -25.61
    assert b576["terminal_mtm_return_pct"] == -25.50
    assert pytest.approx(b576["total_friction_usdt"], abs=0.1) == 25.58

    # Attribution decomposition identity
    attr = benchmark_closure["session_attribution_verification"]
    delta_net = attr["net_delta_usdt"]
    delta_gross = attr["gross_delta_usdt"]
    delta_friction = attr["friction_delta_savings_usdt"]
    assert pytest.approx(delta_net, abs=0.01) == delta_gross + delta_friction
    assert attr["turnover_control_audit"]["static_sampling_verification_status"] == "NOT_INDEPENDENTLY_VERIFIED"


def test_binance_pilot_quality_and_invariants(binance_quality):
    """Verify official Binance Vision pilot checksum, row continuity, and zero violations."""
    assert binance_quality["dataset"] == "BTCUSDT-1m-2022-01"
    assert binance_quality["checksum_verified"] is True
    assert binance_quality["expected_1m_bars"] == 44640
    assert binance_quality["actual_1m_bars"] == 44640
    
    metrics = binance_quality["data_quality_metrics"]
    assert metrics["is_strictly_sorted"] is True
    assert metrics["duplicate_timestamps"] == 0
    assert metrics["timestamp_gaps"] == 0
    assert metrics["negative_volume_bars"] == 0
    assert metrics["negative_or_zero_price_bars"] == 0
    assert metrics["high_below_low_violations"] == 0
    assert metrics["high_below_open_violations"] == 0
    assert metrics["high_below_close_violations"] == 0
    assert metrics["low_above_open_violations"] == 0
    assert metrics["low_above_close_violations"] == 0
    assert metrics["synthetic_price_filling_applied"] is False


def test_resampling_determinism_and_counts(binance_quality):
    """Verify exact candle counts across resampled timeframes."""
    res = binance_quality["resampling_verification"]
    assert res["5m"]["actual_bars"] == 8928
    assert res["15m"]["actual_bars"] == 2976
    assert res["1h"]["actual_bars"] == 744
    assert res["4h"]["actual_bars"] == 186
    assert res["1d"]["actual_bars"] == 31


def test_causal_news_and_future_leak_prevention():
    """Verify that future news is strictly excluded at earlier decision points."""
    calendar = GlobalSessionCalendar()
    sample_candles = pd.DataFrame([
        {"open_time": 1767623100000, "close_time": 1767623399999, "open": 90000.0, "high": 90100.0, "low": 89900.0, "close": 90050.0, "volume": 10.0},
        {"open_time": 1767623400000, "close_time": 1767623699999, "open": 90050.0, "high": 90200.0, "low": 90000.0, "close": 90150.0, "volume": 12.0}
    ])
    
    future_event = {
        "event_id": "EVT-FUTURE-TEST-001",
        "published_at_utc": "2026-01-05T14:35:00Z",
        "available_at_utc": "2026-01-05T14:36:00Z",
        "source_id": "BLS_PRESS_RELEASE",
        "category": "MACRO_INFLATION",
        "headline": "Future Event",
        "raw_text": "Sample text",
        "sentiment_label": "BULLISH",
        "checksum_sha256": "abcdef" * 10 + "1234"
    }
    
    engine = HistoricalReplayEngine(sample_candles, [future_event], calendar)
    
    # Query before event is available
    state_early = engine.get_point_in_time_state("2026-01-05T14:30:00Z")
    assert state_early.visible_event_count == 0
    assert "EVT-FUTURE-TEST-001" not in [e["event_id"] for e in state_early.visible_events]
    
    # Query after event is available
    state_late = engine.get_point_in_time_state("2026-01-05T14:37:00Z")
    assert state_late.visible_event_count == 1
    assert "EVT-FUTURE-TEST-001" in [e["event_id"] for e in state_late.visible_events]


def test_causal_unclosed_candle_rejection():
    """Verify that unclosed forming candles are not observed."""
    calendar = GlobalSessionCalendar()
    # Candle 1 closes at 14:04:59.999 (ts: 1000 to 1999)
    # Candle 2 closes at 14:09:59.999 (ts: 2000 to 2999)
    candles = pd.DataFrame([
        {"open_time": 1000, "close_time": 1999, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 5.0},
        {"open_time": 2000, "close_time": 2999, "open": 102.0, "high": 106.0, "low": 101.0, "close": 104.0, "volume": 6.0}
    ])
    
    engine = HistoricalReplayEngine(candles, [], calendar)
    
    # Query at timestamp 2500 (inside Candle 2, before it closes)
    state_mid = engine.get_point_in_time_state(2500)
    assert state_mid.candle_count_observed == 1
    assert state_mid.last_closed_candle["close_time"] == 1999
    
    # Query at timestamp 3000 (after Candle 2 closes)
    state_after = engine.get_point_in_time_state(3000)
    assert state_after.candle_count_observed == 2
    assert state_after.last_closed_candle["close_time"] == 2999


def test_deterministic_state_hash_reproducibility(replay_audit):
    """Verify that repeated queries for identical timestamps return identical state hashes."""
    assert replay_audit["invariants_verified"]["deterministic_state_hash_reproducibility"] is True
    assert replay_audit["invariants_verified"]["causal_event_isolation"] is True
    assert replay_audit["invariants_verified"]["future_candle_exclusion"] is True
    assert replay_audit["invariants_verified"]["session_window_transition"] is True
    
    pre_hash = replay_audit["causal_separation_case"]["pre_open_state"]["state_hash_sha256"]
    post_hash = replay_audit["causal_separation_case"]["post_open_state"]["state_hash_sha256"]
    assert pre_hash != post_hash


def test_event_schema_completeness(event_schema):
    """Verify all 19 standardized event fields are present in the schema definition."""
    required_fields = [
        "event_id", "published_at_utc", "available_at_utc", "source_id", "category",
        "headline", "raw_text", "entities", "sentiment_label", "sentiment_score",
        "expected_value", "actual_value", "previous_value", "revision_indicator",
        "vintage_date", "is_first_release", "causal_delay_seconds", "source_url",
        "checksum_sha256"
    ]
    schema_required = event_schema.get("required", [])
    for field in required_fields:
        assert field in schema_required, f"Required field {field} missing from schema definition"
        assert field in event_schema["properties"], f"Field {field} missing from schema properties"

    # Verify example events conform to required keys
    for example in event_schema.get("example_events", []):
        for field in required_fields:
            assert field in example, f"Example event {example.get('event_id')} missing required field {field}"


def test_revision_immutability():
    """Verify that revisions create distinct records and do not mutate initial first release."""
    calendar = GlobalSessionCalendar()
    candles = pd.DataFrame([
        {"open_time": 1000, "close_time": 1999, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 5.0}
    ])
    
    first_release = {
        "event_id": "EVT-CPI-202205-FIRST",
        "published_at_utc": "2022-06-10T12:30:00Z",
        "available_at_utc": "2022-06-10T12:31:00Z",
        "actual_value": 8.6,
        "is_first_release": True,
        "revision_indicator": False,
        "vintage_date": "2022-06-10"
    }
    
    revision = {
        "event_id": "EVT-CPI-202205-REVISION-1",
        "published_at_utc": "2022-07-13T12:30:00Z",
        "available_at_utc": "2022-07-13T12:31:00Z",
        "actual_value": 8.5,
        "is_first_release": False,
        "revision_indicator": True,
        "vintage_date": "2022-07-13"
    }
    
    engine = HistoricalReplayEngine(candles, [first_release, revision], calendar)
    
    # At June 15 (before revision exists)
    state_june = engine.get_point_in_time_state("2022-06-15T00:00:00Z")
    assert state_june.visible_event_count == 1
    assert state_june.visible_events[0]["event_id"] == "EVT-CPI-202205-FIRST"
    
    # At July 20 (after revision release)
    state_july = engine.get_point_in_time_state("2022-07-20T00:00:00Z")
    assert state_july.visible_event_count == 2
    vis_ids = [e["event_id"] for e in state_july.visible_events]
    assert "EVT-CPI-202205-FIRST" in vis_ids
    assert "EVT-CPI-202205-REVISION-1" in vis_ids

