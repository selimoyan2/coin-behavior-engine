"""CBE — Sprint 11.02B: Deployment Compatibility, Persistent Data Protection & Safe Integration.

Mandatory Test Coverage Suite (20 Tests):
1. Existing raw-market compatibility (replaying ledger without mutation).
2. Snapshot generation from closed candles.
3. Snapshot atomicity (AtomicSnapshotIO with os.replace).
4. Writer/reader compatibility (schema parity).
5. Volume path resolution (Docker volume & candidate search).
6. Read-only consumer permissions (safe read on immutable directories).
7. Missing snapshot fallback (canonical baseline).
8. Corrupt snapshot fallback (graceful recovery).
9. Stale heartbeat (demotion to HISTORICAL_SNAPSHOT).
10. Out-of-order candle handling.
11. Duplicate candle handling.
12. Binance source mismatch rejection.
13. Unsupported symbols fail-closed (ETHUSDT, SOLUSDT).
14. Production baseline isolation (separate from ff731ac container).
15. No prospective scoring enforcement.
16. No trading capability enforcement.
17. Frozen CBE-0.7.0 integrity (29/29).
18. APPROVAL4 remains FALSE.
19. API backward compatibility (legacy keys preserved).
20. Frontend source labeling (strict classification rules).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.data_contracts import FieldAvailabilityStatus
from coin_behavior_engine.product.intelligence_api import (
    ApiEvidenceClassification,
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
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
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


def _make_aligned_candle_dict(
    offset_minutes: int = 5,
    open_price: str = "63800.00",
    close_price: str = "63850.50",
    is_closed: bool = True,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    open_ts = (now_ms // 300_000) * 300_000 - (offset_minutes * 60_000)
    close_ts = open_ts + 299_999
    o_val = float(open_price)
    c_val = float(close_price)
    h_str = f"{max(o_val, c_val) + 50.0:.2f}"
    l_str = f"{min(o_val, c_val) - 50.0:.2f}"
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
# 1. Existing Raw-Market Compatibility
# ==============================================================================

def test_01_existing_raw_market_compatibility():
    """Verify that existing ledger structure with 5m candles replays and initializes snapshot on boot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        config.ensure_directories()

        # Pre-seed engine with initial candles
        engine1 = MarketCaptureEngineV080(config=config)
        msg1 = _make_aligned_candle_dict(offset_minutes=15, close_price="63500.00")
        msg2 = _make_aligned_candle_dict(offset_minutes=10, close_price="63600.00")
        engine1.process_raw_message(msg1)
        engine1.process_raw_message(msg2)
        engine1.evidence_store.close()

        # Restart engine simulating container startup on existing volume
        engine2 = MarketCaptureEngineV080(config=config)
        try:
            assert engine2.total_persisted == 2
            assert len(engine2.rolling_buffer) == 2

            # Confirm snapshot was materialized upon startup reconstruction
            snap_file = config.snapshot_dir / "btcusdt_factual_latest.json"
            assert snap_file.exists()

            alt_file = config.shadow_data_dir / "live_market_state.json"
            assert alt_file.exists()

            adapter = FactualMarketDataAdapter(data_root=config.shadow_data_dir, snapshot_path=snap_file)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)
            assert rec.spot_price_usdt == 63600.0
        finally:
            engine2.evidence_store.close()


# ==============================================================================
# 2. Snapshot Generation from Closed Candles
# ==============================================================================

def test_02_snapshot_generation_from_closed_candles():
    """Verify factual snapshot emission on every accepted closed candle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        config.ensure_directories()
        engine = MarketCaptureEngineV080(config=config)
        try:
            msg = _make_aligned_candle_dict(offset_minutes=5, close_price="64100.00")
            res = engine.process_raw_message(msg)
            assert res["status"] == "PERSISTED"

            snap_file = config.snapshot_dir / "btcusdt_factual_latest.json"
            assert snap_file.exists()

            with open(snap_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["spot_price_usdt"] == 64100.0
            assert data["is_closed"] is True
            assert "timestamp_close_utc" in data
            assert "writer_heartbeat_utc" in data
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 3. Snapshot Atomicity
# ==============================================================================

def test_03_snapshot_atomicity():
    """Verify AtomicSnapshotIO replaces target atomically with fsync and temp-file cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        target = tmp_path / "live_market_state.json"

        # Rapid consecutive atomic writes
        for i in range(10):
            payload = {"symbol": "BTCUSDT", "counter": i, "spot_price_usdt": 64000.0 + i}
            AtomicSnapshotIO.atomic_write(target, payload)

            # File must be valid JSON at all times
            ok, data, err = AtomicSnapshotIO.safe_read(target)
            assert ok is True
            assert data["counter"] == i

        # Verify no temp files leaked
        tmp_leftovers = list(tmp_path.glob("*.tmp.*"))
        assert len(tmp_leftovers) == 0


# ==============================================================================
# 4. Writer/Reader Compatibility
# ==============================================================================

def test_04_writer_reader_compatibility():
    """Verify that snapshot fields match FactualMarketDataAdapter expectation with exact types."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        target = tmp_path / "live_market_state.json"
        now_dt = datetime.now(timezone.utc)
        payload = FactualMarketDataAdapter.create_snapshot_payload(
            candle_data={
                "symbol": "BTCUSDT",
                "exchange_source": "BINANCE_SPOT",
                "interval": "5m",
                "datetime_open_utc": (now_dt - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_close_utc": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": 64000.0,
                "high": 64200.0,
                "low": 63950.0,
                "close": 64150.0,
                "volume": 80.0,
                "quote_volume": 5132000.0,
                "is_closed": True,
            },
            is_live=True,
            provenance="LIVE_BINANCE_SPOT",
            writer_heartbeat_utc=now_dt.isoformat(),
        )
        AtomicSnapshotIO.atomic_write(target, payload)

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=target)
        rec = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)
        assert rec.spot_price_usdt == 64150.0
        assert rec.open_price_usdt == 64000.0
        assert rec.high_price_usdt == 64200.0
        assert rec.low_price_usdt == 63950.0
        assert rec.is_live is True
        assert rec.classification == DataClassification.LIVE_OBSERVED


# ==============================================================================
# 5. Volume Path Resolution
# ==============================================================================

def test_05_volume_path_resolution():
    """Verify candidate search prioritizes live_capture and environment override."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Environment variable override
        custom_snap = tmp_path / "custom_snap.json"
        custom_snap.write_text('{"symbol": "BTCUSDT", "spot_price_usdt": 65000.0, "timestamp_close_utc": "2026-10-16T20:00:00Z", "exchange_source": "BINANCE_SPOT", "candle_interval": "5m"}')

        old_env = os.environ.get("CBE_FACTUAL_SNAPSHOT_PATH")
        try:
            os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = str(custom_snap)
            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            assert adapter.snapshot_path == custom_snap
        finally:
            if old_env:
                os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = old_env
            else:
                os.environ.pop("CBE_FACTUAL_SNAPSHOT_PATH", None)

        # 2. Candidate auto-detection in live_capture
        live_dir = tmp_path / "live_capture"
        live_dir.mkdir(parents=True, exist_ok=True)
        live_file = live_dir / "live_market_state.json"
        live_file.write_text('{"symbol": "BTCUSDT"}')

        adapter_auto = FactualMarketDataAdapter(data_root=tmp_path)
        assert adapter_auto.snapshot_path == live_file


# ==============================================================================
# 6. Read-Only Consumer Permissions
# ==============================================================================

def test_06_read_only_consumer_permissions():
    """Verify that reader accesses snapshot safely without any disk write operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "live_market_state.json"
        snap_file.write_text(json.dumps({
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": "2026-10-16T20:00:00Z",
            "spot_price_usdt": 64200.0,
            "is_closed": True,
        }))

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        mtime1 = snap_file.stat().st_mtime
        rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)
        mtime2 = snap_file.stat().st_mtime

        assert rec.spot_price_usdt == 64200.0
        assert mtime1 == mtime2  # Untouched


# ==============================================================================
# 7. Missing Snapshot Fallback
# ==============================================================================

def test_07_missing_snapshot_fallback():
    """Verify graceful fallback to canonical baseline on missing snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        missing = tmp_path / "absent.json"
        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=missing)
        rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

        assert rec.spot_price_usdt == 63842.15
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT
        assert "FILE_NOT_FOUND" in rec.provenance_details["note"]


# ==============================================================================
# 8. Corrupt Snapshot Fallback
# ==============================================================================

def test_08_corrupt_snapshot_fallback():
    """Verify graceful fallback on truncated/corrupted JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        corrupt = tmp_path / "bad.json"
        corrupt.write_text('{"symbol": "BTCUSDT", "spot_price_usdt": 64000.0,')  # Truncated
        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=corrupt)
        rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

        assert rec.spot_price_usdt == 63842.15
        assert "CORRUPT_JSON" in rec.provenance_details["note"]


# ==============================================================================
# 9. Stale Heartbeat Demotion
# ==============================================================================

def test_09_stale_heartbeat_demotion():
    """Verify that is_live=True is demoted to HISTORICAL_SNAPSHOT if heartbeat exceeds 120s."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "live_market_state.json"
        ref_time = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)

        # Heartbeat 180s old (> 120s)
        stale_hb = (ref_time - timedelta(seconds=180)).isoformat()
        fresh_close = (ref_time - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": fresh_close,
            "spot_price_usdt": 64300.0,
            "is_closed": True,
            "is_live": True,
            "writer_heartbeat_utc": stale_hb,
        }
        AtomicSnapshotIO.atomic_write(snap_file, payload)

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        rec = adapter.get_btcusdt_factual_record(reference_time=ref_time, force_fresh_read=True)

        # Must demote to HISTORICAL_SNAPSHOT because heartbeat is stale
        assert rec.is_live is False
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT


# ==============================================================================
# 10. Out-of-Order Candle Handling
# ==============================================================================

def test_10_out_of_order_candle_handling():
    """Verify out-of-order candle is quarantined and does not overwrite current state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        config.ensure_directories()
        engine = MarketCaptureEngineV080(config=config)
        try:
            bar1 = _make_aligned_candle_dict(offset_minutes=5, close_price="64200.00")
            res1 = engine.process_raw_message(bar1)
            assert res1["status"] == "PERSISTED"

            # Older bar arrives
            bar2 = _make_aligned_candle_dict(offset_minutes=10, close_price="64000.00")
            res2 = engine.process_raw_message(bar2)
            assert res2["status"] == "OUT_OF_ORDER_QUARANTINED"
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 11. Duplicate Candle Handling
# ==============================================================================

def test_11_duplicate_candle_handling():
    """Verify duplicate candle is ignored idempotently."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        config.ensure_directories()
        engine = MarketCaptureEngineV080(config=config)
        try:
            bar = _make_aligned_candle_dict(offset_minutes=5, close_price="64200.00")
            res1 = engine.process_raw_message(bar)
            assert res1["status"] == "PERSISTED"

            res2 = engine.process_raw_message(bar)
            assert res2["status"] == "DUPLICATE_IGNORED"
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 12. Binance Source Mismatch
# ==============================================================================

def test_12_binance_source_mismatch():
    """Verify rejection of non-Binance sources."""
    bad_payload = {
        "symbol": "BTCUSDT",
        "exchange_source": "COINBASE",
        "candle_interval": "5m",
        "timestamp_close_utc": "2026-10-16T20:00:00Z",
        "spot_price_usdt": 64000.0,
    }
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(bad_payload)
    assert not is_valid
    assert "Source mismatch: 'COINBASE'" in err


# ==============================================================================
# 13. Unsupported Symbols Fail-Closed
# ==============================================================================

def test_13_unsupported_symbols_fail_closed():
    """Verify ETHUSDT and SOLUSDT fail closed with UNAVAILABLE."""
    adapter = FactualMarketDataAdapter()
    eth = adapter.get_ethusdt_factual_record()
    assert eth.symbol == "ETHUSDT"
    assert eth.source_availability == "UNAVAILABLE"
    assert eth.spot_price_usdt is None

    sol = adapter.get_solusdt_factual_record()
    assert sol.symbol == "SOLUSDT"
    assert sol.source_availability == "UNAVAILABLE"
    assert sol.spot_price_usdt is None


# ==============================================================================
# 14. Production Baseline Isolation
# ==============================================================================

def test_14_production_baseline_isolation():
    """Verify that staging compose points to isolated container and separate volume."""
    staging_compose = Path(__file__).resolve().parents[1] / "deploy" / "staging" / "docker-compose.market-intelligence-staging.yaml"
    assert staging_compose.exists()
    content = staging_compose.read_text(encoding="utf-8")

    assert "cbe-market-intelligence-staging" in content
    assert "cbe_market_intelligence_staging" in content
    assert ":ro" in content  # Read-only mount enforced
    assert "external: true" in content  # External volume reference
    assert "CBE_TRADING_DISABLED=true" in content


# ==============================================================================
# 15. No Prospective Scoring Enforcement
# ==============================================================================

def test_15_no_prospective_scoring_enforcement():
    """Verify that prospective scoring remains disabled and isolated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ShadowCollectorConfig(shadow_data_dir=Path(tmpdir) / "shadow_v080")
        assert config.approval_4_authorized is False
        assert config.trading_enabled is False

        engine = MarketCaptureEngineV080(config=config)
        try:
            assert engine.verify_approval_4_isolation() is True
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 16. No Trading Capability Enforcement
# ==============================================================================

def test_16_no_trading_capability_enforcement():
    """Verify that trading capability is permanently disabled."""
    # Config prohibits trading_enabled=True
    with pytest.raises(ValueError, match="TRADING_ENABLED cannot be True"):
        ShadowCollectorConfig(trading_enabled=True)


# ==============================================================================
# 17. Frozen CBE-0.7.0 Integrity
# ==============================================================================

def test_17_frozen_cbe_070_integrity():
    """Verify all 29 frozen CBE-0.7.0 canonical files are intact."""
    result = verify_sprint07_freeze()
    assert result["verified"] is True
    assert result["canonical_hashes_verified"] == 29


# ==============================================================================
# 18. APPROVAL4 Remains FALSE
# ==============================================================================

def test_18_approval4_remains_false():
    """Hard check that APPROVAL4 is not authorized in environment or config."""
    assert os.environ.get("CBE_APPROVAL_4_AUTHORIZED") != "true"
    with tempfile.TemporaryDirectory() as tmpdir:
        config = ShadowCollectorConfig(shadow_data_dir=Path(tmpdir) / "shadow_v080")
        assert config.approval_4_authorized is False


# ==============================================================================
# 19. API Backward Compatibility
# ==============================================================================

def test_19_api_backward_compatibility():
    """Verify market-overview preserves all legacy fields."""
    svc = MarketIntelligenceApiService()
    status, res = svc.get_market_overview()
    assert status == HTTPStatus.OK
    data = res["data"]
    assert "spot_price_usdt" in data
    assert "bar_timestamp_utc" in data
    assert "symbol" in data
    assert "data_mode" in data


# ==============================================================================
# 20. Frontend Source Labeling
# ==============================================================================

def test_20_frontend_source_labeling():
    """Verify client JS strings contain accurate badges for historical vs live vs unavailable."""
    client_js = Path(__file__).resolve().parents[1] / "src" / "coin_behavior_engine" / "web" / "static" / "intelligence" / "client.js"
    assert client_js.exists()
    js_text = client_js.read_text(encoding="utf-8")

    assert "TARİHSEL SNAPSHOT" in js_text
    assert "CANLI İZLEME" in js_text
    assert "(VERİ YOK)" in js_text
