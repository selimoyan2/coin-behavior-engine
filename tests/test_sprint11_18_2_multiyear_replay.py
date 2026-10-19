"""Sprint 11.18.2 Invariant Test Suite: Multi-Year Dataset & Evidence-Grade Event Replay.

Tests execute directly against source archives, multi-year partitioned parquets,
and point-in-time causal historical replay engine.
NO outcome-forcing assertions.
NO simple assertions on pre-saved boolean flags.
"""

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar
from coin_behavior_engine.research.historical_replay import HistoricalReplayEngine


@pytest.fixture(scope="module")
def calendar():
    return GlobalSessionCalendar()


@pytest.fixture(scope="module")
def real_events():
    events_path = Path("research_outputs/historical_event_evidence_audit_11_18_2.json")
    with open(events_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Transform to format accepted by HistoricalReplayEngine
    events_list = []
    for evt in data["audited_events"]:
        events_list.append({
            "event_id": evt["event_id"],
            "title": evt["title"],
            "category": evt["category"],
            "nominal_published_at_utc": evt["publication_time"]["nominal_published_at_utc"],
            "availability_uncertainty_interval": {
                "earliest_machine_available_at_utc": evt["availability_evidence"]["earliest_machine_available_at_utc"],
                "latest_conservative_available_at_utc": evt["availability_evidence"]["latest_conservative_available_at_utc"],
                "min_delay_seconds": evt["availability_evidence"]["dissemination_uncertainty_interval_seconds"][0],
                "max_delay_seconds": evt["availability_evidence"]["dissemination_uncertainty_interval_seconds"][1]
            },
            "economic_data": {
                "actual_value": evt["macroeconomic_surprise_audit"]["official_published_actual"]["value"]
            },
            "content_sha256": evt["content_verification"]["original_excerpt_sha256"]
        })
    return events_list


def test_source_checksum_verification_sample():
    """Verify SHA-256 of downloaded archives directly against official .CHECKSUM files."""
    cache_dir = Path("data/cache/binance_vision/spot/monthly/klines/BTCUSDT/1m")
    assert cache_dir.exists(), "Cache directory must exist"
    
    sample_months = ["2022-01", "2023-06", "2024-01", "2025-01", "2026-09"]
    for m in sample_months:
        zip_path = cache_dir / f"BTCUSDT-1m-{m}.zip"
        cs_path = cache_dir / f"BTCUSDT-1m-{m}.zip.CHECKSUM"
        
        assert zip_path.exists(), f"Zip for {m} must be present"
        assert cs_path.exists(), f"Checksum for {m} must be present"
        
        with open(cs_path, "r", encoding="utf-8") as f:
            expected_hash = f.read().strip().split()[0]
            
        hasher = hashlib.sha256()
        with open(zip_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        assert actual_hash == expected_hash, f"Checksum failure for {m}: {actual_hash} != {expected_hash}"


def test_complete_monthly_coverage_57_months():
    """Verify all 57 continuous months from 2022-01 through 2026-09 exist in multiyear dataset."""
    tf_5m_dir = Path("data/binance_spot_multiyear/5m")
    assert tf_5m_dir.exists(), "5m dataset dir must exist"
    
    expected_months = []
    for y in range(2022, 2027):
        for m in range(1, 13):
            if y == 2026 and m >= 10:
                continue
            expected_months.append(f"{y}-{m:02d}")
            
    assert len(expected_months) == 57
    for period in expected_months:
        pq = tf_5m_dir / f"BTCUSDT-5m-{period}.parquet"
        assert pq.exists(), f"Missing 5m parquet partition for {period}"


def test_cross_partition_boundary_continuity_2024_to_2025():
    """Verify exact 60,000 ms step continuity across year transition (2024-12 to 2025-01)."""
    dir_1m = Path("data/binance_spot_multiyear/1m")
    df_202412 = pd.read_parquet(dir_1m / "BTCUSDT-1m-2024-12.parquet")
    df_202501 = pd.read_parquet(dir_1m / "BTCUSDT-1m-2025-01.parquet")
    
    last_open_202412 = int(df_202412.iloc[-1]["open_time"])
    first_open_202501 = int(df_202501.iloc[0]["open_time"])
    
    diff_ms = first_open_202501 - last_open_202412
    assert diff_ms == 60000, f"Boundary gap detected across 2024-2025 transition: {diff_ms} ms (expected 60000)"


def test_multitimeframe_aggregation_volume_conservation():
    """Verify volume and extreme price conservation between 1m and 5m partitions."""
    dir_1m = Path("data/binance_spot_multiyear/1m")
    dir_5m = Path("data/binance_spot_multiyear/5m")
    
    df_1m = pd.read_parquet(dir_1m / "BTCUSDT-1m-2022-06.parquet")
    df_5m = pd.read_parquet(dir_5m / "BTCUSDT-5m-2022-06.parquet")
    
    # Volume conservation
    vol_1m = df_1m["volume"].sum()
    vol_5m = df_5m["volume"].sum()
    assert abs(vol_1m - vol_5m) < 1e-4, f"Volume mismatch: {vol_1m} != {vol_5m}"
    
    # High / Low extreme price conservation
    max_high_1m = df_1m["high"].max()
    max_high_5m = df_5m["high"].max()
    assert max_high_1m == max_high_5m, f"Max high mismatch: {max_high_1m} != {max_high_5m}"
    
    min_low_1m = df_1m["low"].min()
    min_low_5m = df_5m["low"].min()
    assert min_low_1m == min_low_5m, f"Min low mismatch: {min_low_1m} != {min_low_5m}"


def test_independent_replay_execution_all_three_events(calendar, real_events):
    """Run HistoricalReplayEngine on all 3 events directly from multi-year parquets."""
    # Event 1: BLS CPI May 2022
    df_202206 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2022-06.parquet")
    engine_2022 = HistoricalReplayEngine(df_202206, real_events, calendar)
    
    state_cpi = engine_2022.get_point_in_time_state("2022-06-10T12:35:00Z", conservative_mode=True)
    cpi_vis = [e["event_id"] for e in state_cpi.visible_events]
    assert "REAL-EVT-20220610-BLS-CPI" in cpi_vis
    assert state_cpi.candle_count_observed == 2743
    
    # Event 2: FOMC June 2022
    state_fomc = engine_2022.get_point_in_time_state("2022-06-15T18:05:00Z", conservative_mode=True)
    fomc_vis = [e["event_id"] for e in state_fomc.visible_events]
    assert "REAL-EVT-20220610-BLS-CPI" in fomc_vis
    assert "REAL-EVT-20220615-FOMC-STATEMENT" in fomc_vis
    assert state_fomc.candle_count_observed == 4249
    
    # Event 3: SEC ETF Approval Jan 2024
    df_202401 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2024-01.parquet")
    engine_2024 = HistoricalReplayEngine(df_202401, real_events, calendar)
    
    state_sec = engine_2024.get_point_in_time_state("2024-01-10T20:55:00Z", conservative_mode=True)
    sec_vis = [e["event_id"] for e in state_sec.visible_events]
    assert "REAL-EVT-20240110-SEC-ETF-APPROVAL" in sec_vis
    assert state_sec.candle_count_observed == 2843


def test_future_candle_and_news_exclusion(calendar, real_events):
    """Verify that unclosed candles and future events are strictly invisible at T."""
    df_202206 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2022-06.parquet")
    engine = HistoricalReplayEngine(df_202206, real_events, calendar)
    
    # Query at exactly 12:20:00 UTC (T-10m before CPI release at 12:30:00 UTC)
    state = engine.get_point_in_time_state("2022-06-10T12:20:00Z", conservative_mode=True)
    q_ms = state.query_timestamp_ms
    
    # Assert last closed candle close_time <= q_ms
    assert state.last_closed_candle is not None
    assert state.last_closed_candle["close_time"] <= q_ms
    
    # Assert zero events visible
    assert state.visible_event_count == 0
    assert len(state.uncertain_events) == 0


def test_conservative_vs_eager_uncertainty_handling(calendar, real_events):
    """Verify conservative mode withholds uncertain events while eager mode reveals them."""
    df_202206 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2022-06.parquet")
    engine = HistoricalReplayEngine(df_202206, real_events, calendar)
    
    # At T + 1m (12:31:00 UTC): inside [12:30:15Z, 12:32:00Z]
    ts = "2022-06-10T12:31:00Z"
    state_cons = engine.get_point_in_time_state(ts, conservative_mode=True)
    state_eager = engine.get_point_in_time_state(ts, conservative_mode=False)
    
    # Conservative withholds
    assert len(state_cons.visible_events) == 0
    assert len(state_cons.uncertain_events) == 1
    assert state_cons.uncertain_events[0]["event_id"] == "REAL-EVT-20220610-BLS-CPI"
    
    # Eager reveals
    assert len(state_eager.visible_events) == 1
    assert state_eager.visible_events[0]["event_id"] == "REAL-EVT-20220610-BLS-CPI"
    
    # Hashes must diverge
    assert state_cons.state_hash_sha256 != state_eager.state_hash_sha256


def test_provenance_downgrade_on_missing_evidence():
    """Verify that unevidenced events are downgraded rather than given false point-in-time status."""
    audit_path = Path("research_outputs/historical_event_evidence_audit_11_18_2.json")
    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for evt in data["audited_events"]:
        tier = evt["provenance_classification"]
        # Scientifically, none of the 3 can be VERIFIED_POINT_IN_TIME because packet capture logs are missing
        assert tier != "VERIFIED_POINT_IN_TIME", f"Event {evt['event_id']} must not claim unproven point-in-time"
        assert tier == "BOUNDED_WITH_EVIDENCE", f"Event {evt['event_id']} must be BOUNDED_WITH_EVIDENCE"
        assert "unverified_assumptions" in evt
        assert len(evt["unverified_assumptions"]) > 0


def test_deterministic_reproducibility_bidirectional(calendar, real_events):
    """Verify that reversing query order yields identical state hashes (zero state mutation)."""
    df_202206 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2022-06.parquet")
    engine = HistoricalReplayEngine(df_202206, real_events, calendar)
    
    moments = [
        "2022-06-10T12:20:00Z",
        "2022-06-10T12:31:00Z",
        "2022-06-10T12:35:00Z",
        "2022-06-10T12:40:00Z",
        "2022-06-10T13:30:00Z"
    ]
    
    fwd_hashes = [engine.get_point_in_time_state(m).state_hash_sha256 for m in moments]
    bwd_hashes = [engine.get_point_in_time_state(m).state_hash_sha256 for m in reversed(moments)]
    bwd_hashes_reversed = list(reversed(bwd_hashes))
    
    assert fwd_hashes == bwd_hashes_reversed, "Bidirectional replay state hashes must match perfectly"


def test_future_mutation_invariance(calendar, real_events):
    """Verify that altering future candles does not mutate state hash at historical decision moment."""
    df_202206 = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2022-06.parquet")
    engine = HistoricalReplayEngine(df_202206, real_events, calendar)
    
    eval_ts = "2022-06-10T12:20:00Z"
    eval_ms = engine._parse_timestamp_ms(eval_ts)
    state_original = engine.get_point_in_time_state(eval_ts)
    
    # Mutate only future candles
    df_mut = df_202206.copy()
    mask_future = df_mut["open_time"] > eval_ms
    df_mut.loc[mask_future, "close"] = df_mut.loc[mask_future, "close"] * 5.0
    df_mut.loc[mask_future, "volume"] = df_mut.loc[mask_future, "volume"] + 10000.0
    
    engine_mut = HistoricalReplayEngine(df_mut, real_events, calendar)
    state_mutated = engine_mut.get_point_in_time_state(eval_ts)
    
    assert state_original.state_hash_sha256 == state_mutated.state_hash_sha256, "Future data changes must not alter past state hash"


def test_resource_telemetry_invariants():
    """Verify resource usage metrics conform to bounded memory and processing limits."""
    manifest_path = Path("research_outputs/multiyear_market_dataset_manifest_11_18_2.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    telem = manifest["resource_telemetry"]
    assert telem["network_downloaded_mb"] < 100.0, "Total download must be bounded (<100MB)"
    assert telem["disk_parquet_datasets_mb"] < 500.0, "Parquet dataset size must be bounded (<500MB)"
    assert manifest["dataset_summary"]["total_months_verified"] == 57
    assert manifest["quality_invariants"]["total_ohlc_violations_across_all_bars"] == 0
    assert manifest["quality_invariants"]["cross_partition_boundary_gaps"] == 0
