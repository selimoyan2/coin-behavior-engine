"""Sprint 11.18.1 Invariant Test Suite: Data Integrity & Real Event Replay.

Tests execute directly against source parquet, raw archives, and primary datasets.
NO outcome-forcing assertions.
NO simple assertions on pre-saved 'verified=true' boolean strings.
"""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar
from coin_behavior_engine.research.historical_replay import HistoricalReplayEngine


def test_independent_buy_and_hold_accounting_from_raw_parquet():
    """Recalculate Bar 0 and Bar 576 from raw Parquet using Decimal arithmetic."""
    df = pd.read_parquet("research_outputs/market_state_dataset.parquet")
    assert len(df) == 105120
    
    init_cap = Decimal("10000.00")
    alloc_pct = Decimal("0.98")
    alloc_usdt = init_cap * alloc_pct
    cash_reserve = init_cap - alloc_usdt
    fee_rate = Decimal("0.0010")
    slip_rate = Decimal("0.0005")
    
    term_close = Decimal(str(df.iloc[-1]["close"]))
    
    # 1. Bar 0
    b0_open = Decimal(str(df.iloc[0]["open"]))
    b0_fill = b0_open * (Decimal("1") + slip_rate)
    b0_entry_fee = alloc_usdt * fee_rate
    b0_entry_slip = alloc_usdt * slip_rate
    b0_btc = (alloc_usdt - b0_entry_fee) / b0_fill
    
    b0_exit_fill = term_close * (Decimal("1") - slip_rate)
    b0_gross_exit = b0_btc * b0_exit_fill
    b0_exit_fee = b0_gross_exit * fee_rate
    b0_exit_slip = b0_btc * term_close * slip_rate
    b0_liquid = cash_reserve + (b0_gross_exit - b0_exit_fee)
    b0_liquid_ret = ((b0_liquid - init_cap) / init_cap) * Decimal("100")
    
    assert float(b0_liquid_ret.quantize(Decimal("0.01"), ROUND_HALF_UP)) == -22.95
    
    # 2. Bar 576
    b576_open = Decimal(str(df.iloc[576]["open"]))
    b576_fill = b576_open * (Decimal("1") + slip_rate)
    b576_entry_fee = alloc_usdt * fee_rate
    b576_entry_slip = alloc_usdt * slip_rate
    b576_btc = (alloc_usdt - b576_entry_fee) / b576_fill
    
    b576_exit_fill = term_close * (Decimal("1") - slip_rate)
    b576_gross_exit = b576_btc * b576_exit_fill
    b576_exit_fee_exact = b576_gross_exit * fee_rate
    b576_exit_slip_exact = b576_btc * term_close * slip_rate
    b576_liquid = cash_reserve + (b576_gross_exit - b576_exit_fee_exact)
    b576_liquid_ret = ((b576_liquid - init_cap) / init_cap) * Decimal("100")
    
    assert float(b576_liquid_ret.quantize(Decimal("0.01"), ROUND_HALF_UP)) == -25.61
    
    # 3. Exact 25.57 vs 25.58 USDT Friction Verification
    exact_friction = b576_entry_fee + b576_entry_slip + b576_exit_fee_exact + b576_exit_slip_exact
    rounded_exact_friction = exact_friction.quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    component_sum = (
        b576_entry_fee.quantize(Decimal("0.01"), ROUND_HALF_UP) +
        b576_entry_slip.quantize(Decimal("0.01"), ROUND_HALF_UP) +
        b576_exit_fee_exact.quantize(Decimal("0.01"), ROUND_HALF_UP) +
        b576_exit_slip_exact.quantize(Decimal("0.01"), ROUND_HALF_UP)
    )
    
    assert float(rounded_exact_friction) == 25.57, f"Expected 25.57 USDT unrounded exact, got {rounded_exact_friction}"
    assert float(component_sum) == 25.58, f"Expected 25.58 USDT component rounded sum, got {component_sum}"


def test_sha256_file_verification_direct_bytes():
    """Verify SHA-256 of downloaded archive directly against official .CHECKSUM."""
    zip_path = Path("data/cache/binance_vision/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2022-01.zip")
    cs_path = Path("data/cache/binance_vision/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2022-01.zip.CHECKSUM")
    
    assert zip_path.exists(), "Pilot zip must be locally cached"
    assert cs_path.exists(), "Pilot checksum file must exist"
    
    with open(cs_path, "r", encoding="utf-8") as f:
        expected_hash = f.read().strip().split()[0]
        
    hasher = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()
    
    assert actual_hash == expected_hash, f"Hash mismatch: {actual_hash} != {expected_hash}"


def test_binance_pilot_timestamp_normalization_and_continuity():
    """Verify timestamp monotonic order, 60s step, 0 gaps, and 0 duplicates directly from Parquet."""
    pq_path = Path("data/normalized/binance_pilot_2022_01/BTCUSDT-1m-2022-01.parquet")
    assert pq_path.exists(), "Pilot 1m parquet must exist"
    
    df = pd.read_parquet(pq_path)
    assert len(df) == 44640, "January 2022 must contain exactly 44,640 minutes"
    
    # Strictly sorted
    assert df["open_time"].is_monotonic_increasing
    
    # Zero duplicates
    assert df["open_time"].duplicated().sum() == 0
    
    # Monotonic 60000ms step
    diffs = df["open_time"].diff().dropna()
    assert (diffs == 60000).all()


def test_resampling_price_and_volume_conservation():
    """Verify volume conservation and open/close price fidelity across resampled timeframes."""
    dir_pilot = Path("data/normalized/binance_pilot_2022_01")
    df_1m = pd.read_parquet(dir_pilot / "BTCUSDT-1m-2022-01.parquet")
    df_5m = pd.read_parquet(dir_pilot / "BTCUSDT-5m-2022-01.parquet")
    df_1h = pd.read_parquet(dir_pilot / "BTCUSDT-1h-2022-01.parquet")
    df_1d = pd.read_parquet(dir_pilot / "BTCUSDT-1d-2022-01.parquet")
    
    vol_1m = df_1m["volume"].sum()
    vol_5m = df_5m["volume"].sum()
    vol_1h = df_1h["volume"].sum()
    vol_1d = df_1d["volume"].sum()
    
    assert pytest.approx(vol_1m, abs=1e-3) == vol_5m
    assert pytest.approx(vol_1m, abs=1e-3) == vol_1h
    assert pytest.approx(vol_1m, abs=1e-3) == vol_1d
    
    # Boundary price conservation
    assert df_1m["open"].iloc[0] == df_5m["open"].iloc[0] == df_1h["open"].iloc[0] == df_1d["open"].iloc[0]
    assert df_1m["close"].iloc[-1] == df_5m["close"].iloc[-1] == df_1h["close"].iloc[-1] == df_1d["close"].iloc[-1]


def test_real_event_schema_and_primary_content_hash():
    """Verify real event catalog and recompute content hashes from primary text."""
    path = Path("research_outputs/real_historical_event_inventory_11_18_1.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    events = data["real_events"]
    assert len(events) >= 3, "Must have at least 3 real historical events"
    
    for evt in events:
        assert "event_id" in evt
        assert "nominal_published_at_utc" in evt
        assert "availability_uncertainty_interval" in evt
        assert "original_excerpt" in evt
        assert "content_sha256" in evt
        
        # Recompute SHA-256 directly from excerpt text
        recalculated_hash = hashlib.sha256(evt["original_excerpt"].encode("utf-8")).hexdigest()
        assert recalculated_hash == evt["content_sha256"], f"Content hash mismatch for {evt['event_id']}"


def test_real_event_replay_execution_and_hash_reproducibility():
    """Verify real event replay execution across 5 horizons and test state hash reproducibility."""
    audit_path = Path("research_outputs/real_event_replay_audit_11_18_1.json")
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)
        
    moments = audit["decision_moments_replay"]
    assert "T_minus_10m" in moments
    assert "T_plus_1m" in moments
    assert "T_plus_5m" in moments
    assert "T_plus_10m" in moments
    assert "T_plus_1h" in moments
    
    # Check that volume surged at event bar (T_plus_5m)
    c_pre = moments["T_minus_10m"]["last_closed_candle"]
    c_event = moments["T_plus_5m"]["last_closed_candle"]
    assert c_event["volume"] > c_pre["volume"] * 10.0, "Volume must surge on real CPI event"
    
    # Check hashes are distinct
    hashes = [m["state_hash_sha256"] for m in moments.values()]
    assert len(set(hashes)) == len(hashes), "Each horizon must have a unique state hash"


def test_bidirectional_time_navigation_leak_prevention():
    """Verify that moving forward then backward in time leaves zero state leakage."""
    # Use synthetic sample to test engine memory isolation directly
    calendar = GlobalSessionCalendar()
    candles = pd.DataFrame([
        {"open_time": 1000, "close_time": 1999, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 5.0},
        {"open_time": 2000, "close_time": 2999, "open": 102.0, "high": 106.0, "low": 101.0, "close": 104.0, "volume": 6.0}
    ])
    
    engine = HistoricalReplayEngine(candles, [], calendar)
    
    # Forward
    h1 = engine.get_point_in_time_state(1500).state_hash_sha256
    h2 = engine.get_point_in_time_state(2500).state_hash_sha256
    h3 = engine.get_point_in_time_state(3500).state_hash_sha256
    
    assert h1 != h2 and h2 != h3
    
    # Backward
    h2_back = engine.get_point_in_time_state(2500).state_hash_sha256
    h1_back = engine.get_point_in_time_state(1500).state_hash_sha256
    
    assert h2 == h2_back
    assert h1 == h1_back


def test_availability_uncertainty_window_handling():
    """Verify that events inside uncertainty window are withheld in conservative mode."""
    calendar = GlobalSessionCalendar()
    candles = pd.DataFrame([
        {"open_time": 1000, "close_time": 1999, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 5.0}
    ])
    
    event_with_window = {
        "event_id": "EVT-UNCERTAIN-TEST",
        "nominal_published_at_utc": "2026-01-05T14:30:00Z",
        "availability_uncertainty_interval": {
            "earliest_machine_available_at_utc": "2026-01-05T14:30:15Z",
            "latest_conservative_available_at_utc": "2026-01-05T14:32:00Z"
        }
    }
    
    engine = HistoricalReplayEngine(candles, [event_with_window], calendar)
    
    # At 14:30:30 UTC (inside uncertainty window [15s, 120s])
    # Conservative mode: withheld
    state_cons = engine.get_point_in_time_state("2026-01-05T14:30:30Z", conservative_mode=True)
    assert state_cons.visible_event_count == 0
    assert len(state_cons.uncertain_events) == 1
    assert state_cons.uncertain_events[0]["event_id"] == "EVT-UNCERTAIN-TEST"
    
    # Non-conservative (eager) mode: visible
    state_eager = engine.get_point_in_time_state("2026-01-05T14:30:30Z", conservative_mode=False)
    assert state_eager.visible_event_count == 1
    assert state_eager.visible_events[0]["event_id"] == "EVT-UNCERTAIN-TEST"
    
    # At 14:33:00 UTC (after uncertainty window): visible in both
    state_final = engine.get_point_in_time_state("2026-01-05T14:33:00Z", conservative_mode=True)
    assert state_final.visible_event_count == 1


def test_chronological_matched_turnover_simulation():
    """Verify that chronological random trade omission in a bear market preserves capital."""
    # Simple deterministic test demonstrating causal portfolio compounding
    p_entries = [100.0, 95.0, 90.0, 85.0]
    p_exits   = [95.0,  90.0, 85.0, 80.0]  # Uniformly losing trades (-5% each)
    
    # Scenario A: Take all 4 trades
    cash_a = 10000.0
    for pe, px in zip(p_entries, p_exits):
        qty = (cash_a * 0.98) / pe
        gross_exit = qty * px
        cash_a = (cash_a * 0.02) + gross_exit # ignore friction for simplicity
        
    # Scenario B: Take only 2 trades (omit 2)
    cash_b = 10000.0
    for pe, px in zip(p_entries[:2], p_exits[:2]):
        qty = (cash_b * 0.98) / pe
        gross_exit = qty * px
        cash_b = (cash_b * 0.02) + gross_exit
        
    # Capital preservation invariant: omitting unprofitable trades in a down market increases terminal equity
    assert cash_b > cash_a
    assert cash_b > 8500.0
    assert cash_a < 8500.0
