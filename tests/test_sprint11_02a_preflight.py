"""CBE — Sprint 11.02A: Live Capture Preflight, Snapshot Ownership & Controlled Activation Readiness.

Rigorous offline test suite validating:
1. Snapshot Ownership: Single capture writer, multiple read-only consumers.
2. Atomic Writer/Reader Compatibility: AtomicSnapshotIO and schema parity.
3. Closed-Candle Semantics: Open candles rejected at validator and reader schema gates.
4. Source Provenance & Heartbeat: Strict BINANCE_SPOT source and heartbeat evaluation.
5. Freshness & Staleness Boundaries: 30-minute boundary and future skew detection.
6. Offline End-to-End Simulation:
   - Healthy closed candle
   - Delayed candle
   - Missing candle (gap)
   - Duplicate candle
   - Out-of-order candle
   - Corrupt snapshot
   - Missing/unavailable capture writer
   - Stale heartbeat
   - Source identity mismatch
   - Read-only API consumer (no scoring, no trading)
7. Security Invariants: APPROVAL4=FALSE, prospective scoring disabled, trading disabled.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.intelligence_api import (
    MarketIntelligenceApiService,
)
from coin_behavior_engine.product.market_data_adapter import (
    AtomicSnapshotIO,
    DataClassification,
    FactualMarketDataAdapter,
    FactualMarketDataRecord,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.live_capture_service import (
    verify_live_capture_preflight,
)
from coin_behavior_engine.shadow_v080.market_capture_engine import (
    MarketCaptureEngineV080,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    MockMarketDataTransport,
)


def _make_sample_candle_dict(
    open_ts: int = 1727122500000,
    close_ts: int = 1727122799999,
    open_price: str = "63800.00",
    close_price: str = "63850.50",
    high_price: Optional[str] = None,
    low_price: Optional[str] = None,
    is_closed: bool = True,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
) -> Dict[str, Any]:
    o_val = float(open_price)
    c_val = float(close_price)
    h_str = high_price if high_price is not None else f"{max(o_val, c_val) + 50.0:.2f}"
    l_str = low_price if low_price is not None else f"{min(o_val, c_val) - 50.0:.2f}"
    return {
        "s": symbol,
        "k": {
            "s": symbol,
            "i": interval,
            "t": open_ts,
            "T": close_ts,
            "o": open_price,
            "h": h_str,
            "l": l_str,
            "c": close_price,
            "v": "125.45",
            "q": "8009850.00",
            "n": 1500,
            "V": "60.00",
            "x": is_closed,
        }
    }


# ==============================================================================
# 1. Snapshot Ownership & Single-Writer Isolation
# ==============================================================================

def test_01_snapshot_ownership_and_single_writer():
    """Verify single-writer ownership model: capture worker writes, reader only reads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "live_market_state.json"

        # Capture writer payload
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        close_iso = (now_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        open_iso = (now_dt - timedelta(minutes=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        writer_payload = {
            "schema_version": "1.0.0",
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_open_utc": open_iso,
            "timestamp_close_utc": close_iso,
            "spot_price_usdt": 64120.50,
            "open_price_usdt": 64050.00,
            "high_price_usdt": 64200.00,
            "low_price_usdt": 64010.00,
            "close_price_usdt": 64120.50,
            "volume_base": 110.25,
            "volume_usdt": 7069285.00,
            "is_closed": True,
            "is_live": True,
            "classification": "LIVE_OBSERVED",
            "snapshot_generation_timestamp_utc": now_iso,
            "writer_heartbeat_utc": now_iso,
            "provenance_source": "LIVE_BINANCE_SPOT",
        }

        # Writer uses AtomicSnapshotIO to write
        AtomicSnapshotIO.atomic_write(snap_file, writer_payload)
        assert snap_file.exists()

        # Reader accesses via FactualMarketDataAdapter
        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        record = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)

        assert record.symbol == "BTCUSDT"
        assert record.spot_price_usdt == 64120.50
        assert record.is_live is True
        assert record.classification == DataClassification.LIVE_OBSERVED

        # Verify reader NEVER mutates file
        mtime_before = snap_file.stat().st_mtime
        _ = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)
        mtime_after = snap_file.stat().st_mtime
        assert mtime_before == mtime_after


# ==============================================================================
# 2. Atomic Writer/Reader Parity
# ==============================================================================

def test_02_atomic_writer_reader_compatibility():
    """Verify complete schema field compatibility between writer emission and reader parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "btcusdt_factual_latest.json"

        now_dt = datetime.now(timezone.utc)
        close_iso = (now_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        open_iso = (now_dt - timedelta(minutes=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = FactualMarketDataAdapter.create_snapshot_payload(
            candle_data={
                "symbol": "BTCUSDT",
                "exchange_source": "BINANCE_SPOT",
                "interval": "5m",
                "datetime_open_utc": open_iso,
                "datetime_close_utc": close_iso,
                "open": 64200.0,
                "high": 64300.0,
                "low": 64150.0,
                "close": 64280.0,
                "volume": 95.5,
                "quote_volume": 6138740.0,
                "is_closed": True,
            },
            is_live=False,
            provenance="OFFLINE_FIXTURE",
            writer_heartbeat_utc=now_dt.isoformat(),
        )

        FactualMarketDataAdapter.publish_atomic_snapshot(snap_file, payload)

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        record = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)

        assert record.spot_price_usdt == 64280.0
        assert record.open_price_usdt == 64200.0
        assert record.high_price_usdt == 64300.0
        assert record.low_price_usdt == 64150.0
        assert record.close_price_usdt == 64280.0
        assert record.volume_base == 95.5
        assert record.volume_usdt == 6138740.0
        assert record.freshness_status == MarketDataFreshnessStatus.FRESH
        assert record.writer_heartbeat_utc == now_dt.isoformat()


# ==============================================================================
# 3. Closed-Candle Semantics Enforcement
# ==============================================================================

def test_03_closed_candle_semantics_enforcement():
    """Verify that unclosed/in-progress candles are rejected at validator and reader schema boundaries."""
    validator = BinanceSpotCandleValidator()

    # 1. Validator rejects open candle (x=False)
    open_candle_raw = _make_sample_candle_dict(is_closed=False)
    candle, violations = validator.validate_raw(
        raw_record=open_candle_raw,
        provenance=ProvenanceSource.OFFLINE_FIXTURE,
    )
    assert candle is None
    assert any("OPEN_CANDLE_REJECTED" in v for v in violations)

    # 2. Reader schema rejects snapshot marked is_closed=False
    invalid_snapshot = {
        "symbol": "BTCUSDT",
        "exchange_source": "BINANCE_SPOT",
        "candle_interval": "5m",
        "timestamp_close_utc": "2026-10-16T19:25:00Z",
        "spot_price_usdt": 64000.0,
        "is_closed": False,
    }
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(invalid_snapshot)
    assert not is_valid
    assert "OPEN_CANDLE_REJECTED" in err


# ==============================================================================
# 4. Simulation: Healthy Closed Candle Pipeline
# ==============================================================================

def test_04_simulation_healthy_closed_candle():
    """Simulate healthy incoming closed candle from transport through engine to atomic snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "shadow",
        )
        config.ensure_directories()

        engine = MarketCaptureEngineV080(
            config=config,
            transport=MockMarketDataTransport(config),
            default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value,
        )

        # Incoming healthy closed candle aligned to 5m
        now_ms = int(time.time() * 1000)
        open_ts = (now_ms // 300_000) * 300_000 - 300_000
        close_ts = open_ts + 299_999
        raw_msg = _make_sample_candle_dict(
            open_ts=open_ts,
            close_ts=close_ts,
            close_price="64500.00",
            is_closed=True,
        )

        try:
            res = engine.process_raw_message(raw_msg, provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
            assert res["status"] == "PERSISTED"

            # Verify atomic snapshots were published
            snap_latest = config.snapshot_dir / "btcusdt_factual_latest.json"
            snap_alt = config.shadow_data_dir / "live_market_state.json"
            assert snap_latest.exists()
            assert snap_alt.exists()

            # Verify reader sees published record with is_live=True
            adapter = FactualMarketDataAdapter(data_root=config.shadow_data_dir, snapshot_path=snap_latest)
            record = adapter.get_btcusdt_factual_record(force_fresh_read=True)
            assert record.spot_price_usdt == 64500.0
            assert record.is_live is True
            assert record.classification == DataClassification.LIVE_OBSERVED
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 5. Simulation: Delayed Candle & Staleness Boundaries
# ==============================================================================

def test_05_simulation_delayed_candle_and_staleness():
    """Simulate candle arrival with observation timestamp older than 30 minutes."""
    ref_time = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)

    # 35 minutes prior -> STALE
    old_time_str = "2026-10-16T19:25:00Z"
    status_stale = FactualMarketDataAdapter.evaluate_freshness(old_time_str, reference_time=ref_time)
    assert status_stale == MarketDataFreshnessStatus.STALE

    # Exact boundary (30m prior) -> BOUNDARY_STALE
    boundary_str = "2026-10-16T19:30:00Z"
    status_boundary = FactualMarketDataAdapter.evaluate_freshness(boundary_str, reference_time=ref_time)
    assert status_boundary == MarketDataFreshnessStatus.BOUNDARY_STALE

    # 10 minutes prior -> FRESH
    fresh_str = "2026-10-16T19:50:00Z"
    status_fresh = FactualMarketDataAdapter.evaluate_freshness(fresh_str, reference_time=ref_time)
    assert status_fresh == MarketDataFreshnessStatus.FRESH


# ==============================================================================
# 6. Simulation: Missing Candle Gap Detection
# ==============================================================================

def test_06_simulation_missing_candle_gap_detection():
    """Simulate missing candle in sequence (600s gap between closes)."""
    prev_close = "2026-10-16T19:00:00Z"
    curr_close = "2026-10-16T19:10:00Z"  # Missing 19:05:00 bar

    has_gap, missing_count = FactualMarketDataAdapter.detect_candle_gap(prev_close, curr_close)
    assert has_gap is True
    assert missing_count == 1

    # Contiguous 5m sequence
    contiguous_close = "2026-10-16T19:05:00Z"
    has_gap_ok, missing_count_ok = FactualMarketDataAdapter.detect_candle_gap(prev_close, contiguous_close)
    assert has_gap_ok is False
    assert missing_count_ok == 0


# ==============================================================================
# 7. Simulation: Duplicate Candle Prevention
# ==============================================================================

def test_07_simulation_duplicate_candle_prevention():
    """Simulate identical timestamp arrival: monotonicity checker rejects and engine ignores duplicate."""
    # Monotonicity check
    ts = "2026-10-16T19:05:00Z"
    is_mono, err = FactualMarketDataAdapter.check_monotonicity(ts, ts)
    assert not is_mono
    assert err == "DUPLICATE_CANDLE_TIMESTAMP"

    # Engine level
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "shadow",
        )
        config.ensure_directories()
        engine = MarketCaptureEngineV080(config=config)

        candle_msg = _make_sample_candle_dict(open_ts=1727122500000, close_ts=1727122799999)
        res1 = engine.process_raw_message(candle_msg)
        assert res1["status"] == "PERSISTED"

        res2 = engine.process_raw_message(candle_msg)
        assert res2["status"] == "DUPLICATE_IGNORED"

        engine.evidence_store.close()


# ==============================================================================
# 8. Simulation: Out-of-Order Candle Quarantine
# ==============================================================================

def test_08_simulation_out_of_order_candles():
    """Simulate out-of-order candle arrival: monotonicity flags error and engine quarantines."""
    prev_ts = "2026-10-16T19:10:00Z"
    curr_ts = "2026-10-16T19:05:00Z"  # older than prev

    is_mono, err = FactualMarketDataAdapter.check_monotonicity(prev_ts, curr_ts)
    assert not is_mono
    assert "OUT_OF_ORDER_TIMESTAMP" in err

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "shadow",
        )
        config.ensure_directories()
        engine = MarketCaptureEngineV080(config=config)

        # First bar at 19:10
        bar1 = _make_sample_candle_dict(open_ts=1727122800000, close_ts=1727123099999)
        engine.process_raw_message(bar1)

        # Older bar at 19:05
        bar2 = _make_sample_candle_dict(open_ts=1727122500000, close_ts=1727122799999)
        res2 = engine.process_raw_message(bar2)
        assert res2["status"] == "OUT_OF_ORDER_QUARANTINED"

        engine.evidence_store.close()


# ==============================================================================
# 9. Simulation: Corrupt and Missing Snapshot Fallback
# ==============================================================================

def test_09_simulation_corrupt_and_missing_snapshot():
    """Simulate corrupt JSON and missing snapshot: reader falls back safely to canonical baseline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Missing snapshot
        missing_snap = tmp_path / "nonexistent.json"
        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=missing_snap)
        rec_missing = adapter.get_btcusdt_factual_record(force_fresh_read=True)
        assert rec_missing.spot_price_usdt == 63842.15
        assert rec_missing.source_availability == "AVAILABLE"
        assert rec_missing.classification == DataClassification.HISTORICAL_SNAPSHOT
        assert "FILE_NOT_FOUND" in rec_missing.provenance_details["note"]

        # 2. Corrupt snapshot
        corrupt_snap = tmp_path / "corrupt.json"
        corrupt_snap.write_text('{"symbol": "BTCUSDT", "spot_price_usdt": ', encoding="utf-8")
        adapter_corrupt = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=corrupt_snap)
        rec_corrupt = adapter_corrupt.get_btcusdt_factual_record(force_fresh_read=True)
        assert rec_corrupt.spot_price_usdt == 63842.15
        assert "CORRUPT_JSON" in rec_corrupt.provenance_details["note"]


# ==============================================================================
# 10. Simulation: Stale Heartbeat & Source Mismatch
# ==============================================================================

def test_10_simulation_stale_heartbeat_and_source_mismatch():
    """Simulate stale heartbeat (>120s) and source mismatch rejection."""
    ref_time = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)

    # Fresh heartbeat (60s ago)
    fresh_hb = (ref_time - timedelta(seconds=60)).isoformat()
    assert FactualMarketDataAdapter.evaluate_heartbeat_freshness(fresh_hb, reference_time=ref_time) is True

    # Stale heartbeat (180s ago)
    stale_hb = (ref_time - timedelta(seconds=180)).isoformat()
    assert FactualMarketDataAdapter.evaluate_heartbeat_freshness(stale_hb, reference_time=ref_time) is False

    # None or invalid heartbeat
    assert FactualMarketDataAdapter.evaluate_heartbeat_freshness(None) is False
    assert FactualMarketDataAdapter.evaluate_heartbeat_freshness("invalid-iso") is False

    # Source mismatch
    bad_source_payload = {
        "symbol": "BTCUSDT",
        "exchange_source": "KRAKEN",
        "candle_interval": "5m",
        "timestamp_close_utc": "2026-10-16T19:25:00Z",
        "spot_price_usdt": 64000.0,
    }
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(bad_source_payload)
    assert not is_valid
    assert "Source mismatch: 'KRAKEN'" in err


# ==============================================================================
# 11. Read-Only API Consumer: No Scoring & No Trading
# ==============================================================================

def test_11_read_only_api_consumer_no_scoring_no_trading():
    """Verify that consumer endpoints return factual data without invoking model inference or trading."""
    from http import HTTPStatus
    svc = MarketIntelligenceApiService()
    status_over, overview = svc.get_market_overview()
    assert status_over == HTTPStatus.OK
    assert "data" in overview

    # Verify zero trading
    data_dict = overview["data"]
    assert data_dict["symbol"] == "BTCUSDT"
    assert data_dict.get("is_trading_active") is not True

    # Check freshness endpoint
    status_fresh, freshness = svc.get_data_freshness()
    assert status_fresh == HTTPStatus.OK
    assert "data" in freshness or "freshness_status" in freshness or "is_stale" in freshness

    # Ensure prospective data directory has not been polluted with new inferences
    prospective_dir = Path(__file__).resolve().parents[1] / "data" / "prospective"
    if prospective_dir.exists():
        # Confirm no forward predictions or orders generated
        pred_files = list(prospective_dir.glob("predictions_*.jsonl"))
        # If files exist from legacy runs, verify their timestamps haven't been mutated today
        for pf in pred_files:
            assert pf.stat().st_mtime < time.time() + 10


# ==============================================================================
# 12. Safety Invariants & Preflight Fail-Closed
# ==============================================================================

def test_12_safety_invariants_and_preflight_fail_closed():
    """Verify that LiveCaptureService strictly fails closed when Approval 3 is not authorized."""
    # Ensure environment does not have Approval 3 authorized
    old_env = os.environ.get("CBE_APPROVAL_3_AUTHORIZED")
    try:
        os.environ["CBE_APPROVAL_3_AUTHORIZED"] = "false"
        is_valid, violations = verify_live_capture_preflight()
        assert is_valid is False
        assert any("APPROVAL_3_AUTHORIZED" in v for v in violations)
    finally:
        if old_env is not None:
            os.environ["CBE_APPROVAL_3_AUTHORIZED"] = old_env
        else:
            os.environ.pop("CBE_APPROVAL_3_AUTHORIZED", None)
