"""CBE — Sprint 11.02C: Live Capture Snapshot Integration & Offline Validation.

Comprehensive Automated Test Suite:
1. Valid closed candle generates snapshot (both live_market_state.json and snapshots/btcusdt_factual_latest.json).
2. Open candle (is_closed=False) is strictly rejected and does not publish a snapshot.
3. Malformed / missing fields rejected by candle validator.
4. Snapshot atomicity (AtomicSnapshotIO writes atomically with zero temp file leakage).
5. Fresh live candle (< 30m) from LIVE_BINANCE_SPOT is classified as LIVE_OBSERVED (is_live=True).
6. Stale candle (> 30m) is automatically demoted to HISTORICAL_SNAPSHOT (is_live=False).
7. Stale heartbeat (> 120s) is automatically demoted to HISTORICAL_SNAPSHOT (is_live=False).
8. Periodic writer heartbeat update via update_writer_heartbeat() updates heartbeat without mutating candle data.
9. Missing snapshot safe fallback (returns 63,842.15 USDT canonical baseline without error).
10. Schema and contract compatibility between capture snapshot and FactualMarketDataAdapter.
11. 24h price change calculation when rolling buffer has >= 288 bars (24 hours).
12. Startup reconstruction from existing raw candles emits snapshot immediately on engine boot.
13. SQLite, WAL, and JSONL ledger integrity preserved; reader performs zero writes to capture storage.
14. Capture compose and staging compose volume parity (zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data).
15. Frozen CBE-0.7.0 canonical integrity (29/29 hashes intact).
16. APPROVAL4 strictly FALSE.
17. Trading permanently disabled (trading_enabled=False).
18. Prospective scoring permanently disabled (CBE_PROSPECTIVE_OBSERVATION_ENABLED=false).
19. LiveCaptureService preflight validation and safety interlocks.
20. Full HTTP routing contract with Market Intelligence API (/api/v1/intelligence/market-overview).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict
import urllib.request
import yaml

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
from coin_behavior_engine.shadow_v080.live_capture_service import (
    LiveCaptureService,
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
from coin_behavior_engine.web.server import EngineRequestHandler


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_CAPTURE_COMPOSE = REPO_ROOT / "deploy" / "shadow_v080" / "docker-compose.coolify-live-capture.yaml"
STAGING_COMPOSE = REPO_ROOT / "deploy" / "staging" / "docker-compose.market-intelligence-staging.yaml"


def _make_sample_candle(
    offset_minutes: int = 5,
    open_price: str = "64000.00",
    close_price: str = "64250.00",
    is_closed: bool = True,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    bars_back = max(1, (offset_minutes + 4) // 5) if is_closed else 0
    open_ts = ((now_ms // 300_000) - bars_back) * 300_000
    close_ts = open_ts + 299_999
    o_val = float(open_price)
    c_val = float(close_price)
    h_str = f"{max(o_val, c_val) + 40.0:.2f}"
    l_str = f"{min(o_val, c_val) - 40.0:.2f}"
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
            "v": "110.25",
            "q": "7083562.50",
            "n": 1250,
            "V": "55.00",
            "x": is_closed,
        },
    }


# ==============================================================================
# 1. Valid Closed Candle Generates Snapshot
# ==============================================================================

def test_01_valid_closed_candle_generates_snapshot():
    """Verify that a valid closed candle persisted by engine creates both snapshot files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            msg = _make_sample_candle(offset_minutes=5, close_price="64250.00", is_closed=True)
            res = engine.process_raw_message(msg)
            assert res["status"] == "PERSISTED"

            snap_file = cfg.snapshot_dir / "btcusdt_factual_latest.json"
            alt_file = cfg.shadow_data_dir / "live_market_state.json"

            assert snap_file.exists(), f"Missing primary snapshot: {snap_file}"
            assert alt_file.exists(), f"Missing alt snapshot: {alt_file}"

            with open(alt_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["spot_price_usdt"] == 64250.0
            assert data["is_closed"] is True
            assert data["symbol"] == "BTCUSDT"
            assert data["exchange_source"] == "BINANCE_SPOT"
            assert "writer_heartbeat_utc" in data
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 2. Open Candle Rejection
# ==============================================================================

def test_02_open_candle_rejected_and_no_snapshot():
    """Verify that open/in-progress candle (is_closed=False) is rejected and never published."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            msg = _make_sample_candle(offset_minutes=1, close_price="64300.00", is_closed=False)
            res = engine.process_raw_message(msg)
            assert res["status"] == "VALIDATION_FAILED"
            assert any("OPEN_CANDLE_REJECTED" in v for v in res["violations"])

            snap_file = cfg.snapshot_dir / "btcusdt_factual_latest.json"
            alt_file = cfg.shadow_data_dir / "live_market_state.json"
            assert not snap_file.exists()
            assert not alt_file.exists()
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 3. Malformed / Missing Fields Rejection
# ==============================================================================

def test_03_malformed_fields_rejected():
    """Verify that malformed or incomplete payload is quarantined and does not publish snapshot."""
    validator = BinanceSpotCandleValidator()
    bad_msg = {"s": "BTCUSDT", "k": {"s": "BTCUSDT", "i": "5m", "x": True}}  # missing OHLCV
    candle, violations = validator.validate_raw(bad_msg, provenance="LIVE_BINANCE_SPOT")
    assert candle is None
    assert len(violations) > 0


# ==============================================================================
# 4. Snapshot Atomicity
# ==============================================================================

def test_04_snapshot_atomicity_clean_replace():
    """Verify AtomicSnapshotIO replaces target atomically with zero leftover temp files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "live_market_state.json"
        for i in range(15):
            payload = {"symbol": "BTCUSDT", "index": i, "spot_price_usdt": 64000.0 + i}
            AtomicSnapshotIO.atomic_write(target, payload)

            ok, read_data, err = AtomicSnapshotIO.safe_read(target)
            assert ok is True
            assert read_data["index"] == i

        temp_files = list(Path(tmpdir).glob("*.tmp.*"))
        assert len(temp_files) == 0, f"Leaked temp files found: {temp_files}"


# ==============================================================================
# 5. Fresh Candle LIVE_OBSERVED Classification
# ==============================================================================

def test_05_fresh_live_candle_classified_as_live_observed():
    """Verify fresh candle (<30m) from LIVE_BINANCE_SPOT qualifies as LIVE_OBSERVED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg, default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
        try:
            msg = _make_sample_candle(offset_minutes=2, close_price="64400.00", is_closed=True)
            res = engine.process_raw_message(msg)
            assert res["status"] == "PERSISTED"

            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

            assert rec.spot_price_usdt == 64400.0
            assert rec.is_live is True
            assert rec.classification == DataClassification.LIVE_OBSERVED
            assert rec.freshness_status == MarketDataFreshnessStatus.FRESH
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 6. Stale Candle Demotion
# ==============================================================================

def test_06_stale_candle_demoted_to_historical_snapshot():
    """Verify candle older than 30m is demoted to HISTORICAL_SNAPSHOT with is_live=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg, default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
        try:
            # Candle from 45 minutes ago (> 30m)
            msg = _make_sample_candle(offset_minutes=45, close_price="63900.00", is_closed=True)
            res = engine.process_raw_message(msg)
            assert res["status"] == "PERSISTED"

            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

            assert rec.spot_price_usdt == 63900.0
            assert rec.is_live is False
            assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 7. Stale Heartbeat Demotion
# ==============================================================================

def test_07_stale_heartbeat_demoted_to_historical_snapshot():
    """Verify heartbeat > 120s old demotes state to HISTORICAL_SNAPSHOT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "live_market_state.json"
        now_dt = datetime.now(timezone.utc)

        # Heartbeat 150s ago (> 120s)
        stale_hb = (now_dt - timedelta(seconds=150)).isoformat()
        fresh_close = (now_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": fresh_close,
            "spot_price_usdt": 64550.0,
            "is_closed": True,
            "is_live": True,
            "writer_heartbeat_utc": stale_hb,
        }
        AtomicSnapshotIO.atomic_write(snap_file, payload)

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        rec = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)

        assert rec.is_live is False
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT


# ==============================================================================
# 8. Periodic Writer Heartbeat Update
# ==============================================================================

def test_08_periodic_writer_heartbeat_update():
    """Verify update_writer_heartbeat refreshes heartbeat without altering candle data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            msg = _make_sample_candle(offset_minutes=5, close_price="64600.00", is_closed=True)
            engine.process_raw_message(msg)

            alt_file = cfg.shadow_data_dir / "live_market_state.json"
            with open(alt_file, "r", encoding="utf-8") as f:
                data1 = json.load(f)
            hb1 = data1["writer_heartbeat_utc"]

            time.sleep(0.05)
            # Heartbeat update
            success = engine.update_writer_heartbeat()
            assert success is True

            with open(alt_file, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            hb2 = data2["writer_heartbeat_utc"]

            assert data2["spot_price_usdt"] == 64600.0  # Candle data preserved
            assert hb2 >= hb1  # Heartbeat refreshed
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 9. Missing Snapshot Fallback
# ==============================================================================

def test_09_missing_snapshot_safe_fallback():
    """Verify that absent snapshot safely returns canonical historical fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        missing_file = tmp_path / "nonexistent.json"
        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=missing_file)
        rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

        assert rec.spot_price_usdt == 63842.15
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT
        assert rec.is_live is False
        assert rec.source_availability == "AVAILABLE"


# ==============================================================================
# 10. Schema and Contract Compatibility
# ==============================================================================

def test_10_schema_and_contract_compatibility():
    """Verify that snapshot fields match validate_snapshot_schema contract."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            msg = _make_sample_candle(offset_minutes=3, close_price="64700.00", is_closed=True)
            engine.process_raw_message(msg)

            alt_file = cfg.shadow_data_dir / "live_market_state.json"
            with open(alt_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(data)
            assert is_valid is True, f"Schema validation failed: {err}"
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 11. 24h Price Change Percentage Calculation
# ==============================================================================

def test_11_24h_price_change_calculation():
    """Verify that 24h price change is computed when rolling buffer contains >= 288 bars."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
            max_buffer_candles=350,
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            now_ms = int(time.time() * 1000)
            t0 = (now_ms // 300_000) * 300_000 - (300 * 300_000)

            # Seed 289 sequential bars
            for i in range(289):
                open_ts = t0 + (i * 300_000)
                close_ts = open_ts + 299_999
                price = "60000.00" if i == 0 else f"{60000.0 + (i * 10):.2f}"
                bar_dict = {
                    "s": "BTCUSDT",
                    "k": {
                        "s": "BTCUSDT",
                        "i": "5m",
                        "t": open_ts,
                        "T": close_ts,
                        "o": price,
                        "h": f"{float(price) + 20:.2f}",
                        "l": f"{float(price) - 20:.2f}",
                        "c": price,
                        "v": "10.0",
                        "q": "600000.0",
                        "n": 100,
                        "V": "5.0",
                        "x": True,
                    },
                }
                engine.process_raw_message(bar_dict)

            alt_file = cfg.shadow_data_dir / "live_market_state.json"
            with open(alt_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["price_change_24h_pct"] is not None
            assert isinstance(data["price_change_24h_pct"], float)
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 12. Startup Reconstruction Emits Snapshot
# ==============================================================================

def test_12_startup_reconstruction_emits_snapshot():
    """Verify engine re-plays existing ledger and immediately writes snapshot on boot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()

        # Phase 1: create ledger with 2 candles
        e1 = MarketCaptureEngineV080(config=cfg)
        e1.process_raw_message(_make_sample_candle(offset_minutes=10, close_price="64100.00"))
        e1.process_raw_message(_make_sample_candle(offset_minutes=5, close_price="64200.00"))
        e1.evidence_store.close()

        # Delete snapshot files to simulate fresh boot on existing storage volume
        snap_file = cfg.snapshot_dir / "btcusdt_factual_latest.json"
        alt_file = cfg.shadow_data_dir / "live_market_state.json"
        if snap_file.exists():
            snap_file.unlink()
        if alt_file.exists():
            alt_file.unlink()

        assert not snap_file.exists()
        assert not alt_file.exists()

        # Phase 2: Start new engine instance on same directory
        e2 = MarketCaptureEngineV080(config=cfg)
        try:
            assert e2.total_persisted == 2
            # Startup reconstruction must immediately emit snapshot
            assert snap_file.exists()
            assert alt_file.exists()

            with open(alt_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["spot_price_usdt"] == 64200.0
        finally:
            e2.evidence_store.close()


# ==============================================================================
# 13. SQLite, WAL, and JSONL Ledger Immutability
# ==============================================================================

def test_13_sqlite_and_jsonl_ledger_immutability():
    """Verify reader never acquires write handles or alters evidence store files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            engine.process_raw_message(_make_sample_candle(offset_minutes=5, close_price="64300.00"))
            engine.evidence_store.close()

            ev_file = cfg.raw_market_dir / f"raw_candles_{cfg.symbol}_{cfg.interval}.jsonl"
            idx_file = cfg.raw_market_dir / f"index_{cfg.symbol}_{cfg.interval}.sqlite3"

            mtime_ev_before = ev_file.stat().st_mtime
            mtime_idx_before = idx_file.stat().st_mtime

            # Reader reads snapshot
            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)
            assert rec.spot_price_usdt == 64300.0

            assert ev_file.stat().st_mtime == mtime_ev_before
            assert idx_file.stat().st_mtime == mtime_idx_before
        finally:
            if engine.evidence_store._index_conn:
                engine.evidence_store.close()


# ==============================================================================
# 14. Capture Compose & Staging Compose Volume Parity
# ==============================================================================

def test_14_compose_volume_parity():
    """Verify that both live-capture and staging compose files target the exact shared volume."""
    assert LIVE_CAPTURE_COMPOSE.exists()
    assert STAGING_COMPOSE.exists()

    with open(LIVE_CAPTURE_COMPOSE, "r", encoding="utf-8") as f:
        cap_data = yaml.safe_load(f)

    with open(STAGING_COMPOSE, "r", encoding="utf-8") as f:
        stg_data = yaml.safe_load(f)

    cap_vol = cap_data["volumes"]["cbe_080_live_capture_data"]["name"]
    stg_vol = stg_data["volumes"]["cbe_live_capture_data"]["name"]

    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in cap_vol
    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in stg_vol


# ==============================================================================
# 15. Frozen CBE-0.7.0 Canonical Integrity
# ==============================================================================

def test_15_frozen_cbe_070_canonical_integrity():
    """Verify all 29 CBE-0.7.0 frozen canonical files match cryptographic checksums."""
    res = verify_sprint07_freeze()
    assert res["verified"] is True
    assert res["canonical_hashes_verified"] == 29


# ==============================================================================
# 16. APPROVAL4 Strictly False
# ==============================================================================

def test_16_approval_4_strictly_false():
    """Verify APPROVAL4 remains false in environment and config."""
    assert os.environ.get("CBE_APPROVAL_4_AUTHORIZED") != "true"
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ShadowCollectorConfig(shadow_data_dir=Path(tmpdir) / "shadow")
        assert cfg.approval_4_authorized is False


# ==============================================================================
# 17. Trading Permanently Disabled
# ==============================================================================

def test_17_trading_permanently_disabled():
    """Verify that trading_enabled cannot be True."""
    with pytest.raises(ValueError, match="TRADING_ENABLED cannot be True"):
        ShadowCollectorConfig(trading_enabled=True)


# ==============================================================================
# 18. Prospective Scoring Permanently Disabled
# ==============================================================================

def test_18_prospective_scoring_permanently_disabled():
    """Verify that prospective scoring remains disabled in config and engine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ShadowCollectorConfig(shadow_data_dir=Path(tmpdir) / "shadow")
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            assert engine.verify_approval_4_isolation() is True
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 19. LiveCaptureService Preflight & Safety Interlocks
# ==============================================================================

def test_19_live_capture_service_preflight_interlocks():
    """Verify verify_live_capture_preflight enforces strict fail-closed safety."""
    old_env = dict(os.environ)
    try:
        os.environ["CBE_APPROVAL_3_AUTHORIZED"] = "false"
        is_ok, violations = verify_live_capture_preflight()
        assert is_ok is False
        assert any("APPROVAL_3" in v for v in violations)

        os.environ["CBE_APPROVAL_3_AUTHORIZED"] = "true"
        os.environ["CBE_BINANCE_COLLECTION_ENABLED"] = "true"
        os.environ["CBE_TRADING_DISABLED"] = "true"
        os.environ["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] = "false"
        os.environ["CBE_RECORD_LABEL"] = "LIVE_BINANCE_SPOT"
        os.environ.pop("CBE_APPROVAL_4_AUTHORIZED", None)

        is_ok2, violations2 = verify_live_capture_preflight()
        assert is_ok2 is True
        assert len(violations2) == 0
    finally:
        os.environ.clear()
        os.environ.update(old_env)


# ==============================================================================
# 20. Full HTTP Routing Contract with Market Intelligence API
# ==============================================================================

def test_20_http_routing_contract_with_intelligence_api():
    """Verify /api/v1/intelligence/market-overview integration with live snapshot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            shadow_data_dir=tmp_path / "live_capture",
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg, default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
        try:
            engine.process_raw_message(_make_sample_candle(offset_minutes=2, close_price="64850.25", is_closed=True))
        finally:
            engine.evidence_store.close()

        old_env = os.environ.get("CBE_FACTUAL_SNAPSHOT_PATH")
        server = ThreadingHTTPServer(("127.0.0.1", 0), EngineRequestHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = str(cfg.shadow_data_dir / "live_market_state.json")
            url = f"http://127.0.0.1:{port}/api/v1/intelligence/market-overview"
            with urllib.request.urlopen(url, timeout=5.0) as resp:
                assert resp.status == HTTPStatus.OK
                data = json.loads(resp.read().decode("utf-8"))
                assert "data" in data
                assert data["data"]["spot_price_usdt"] == 64850.25
                assert data["data"]["symbol"] == "BTCUSDT"
        finally:
            if old_env:
                os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = old_env
            else:
                os.environ.pop("CBE_FACTUAL_SNAPSHOT_PATH", None)
            server.shutdown()
            server.server_close()
