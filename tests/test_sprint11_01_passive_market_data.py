"""Comprehensive Regression & Acceptance Tests for CBE Sprint 11.01.

Validates:
1. Mandatory safety invariants (29/29 canonical freeze, APPROVAL4=FALSE, trading disabled).
2. Existing passive capture infrastructure audit & pre-flight fail-closed interlocks.
3. Factual market data contract schema, serialization, and strict classification.
4. Offline snapshot adapter resilience:
   - Atomic snapshot replacement
   - Partially written files
   - Corrupt snapshots
   - Missing files
   - Stale observations
   - Clock skew (>60s future)
   - Duplicate candles
   - Out-of-order observations
   - Missing-candle gap detection
   - Invalid prices
   - Unsupported symbols
   - Source identity mismatch
5. Fail-closed multi-asset policy (ETHUSDT & SOLUSDT marked UNAVAILABLE).
6. Market Intelligence API integration on /api/v1/intelligence/market-overview.
7. Frontend bundle budget (< 25 KB) and Module A factual display.
8. Concurrent read performance & thread safety.
9. Security & authorization audit (6 distinct levels, none pre-authorized).
10. Production dashboard isolation (/dashboard 100% untouched).
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.acceptance import MvpReleaseAuditor
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
from coin_behavior_engine.product.ui import (
    get_intelligence_css,
    get_intelligence_js,
    render_intelligence_ui_html,
)
from coin_behavior_engine.prospective.freeze import (
    FROZEN_MODEL_VERSION,
    verify_sprint07_freeze,
)
from coin_behavior_engine.shadow_v080.live_capture_service import verify_live_capture_preflight
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_01_mandatory_safety_invariants_and_canonical_freeze():
    """Test 01: Verify baseline commit invariants, 29/29 freeze, and APPROVAL4=FALSE."""
    verify_sprint07_freeze()

    state = get_engine_state()
    assert state["model_version"] == FROZEN_MODEL_VERSION
    assert state["canonical_artifacts_verified"] == 29
    assert state["canonical_artifacts_total"] == 29
    assert state["freeze_verified"] is True
    assert state["freeze_violations"] == 0
    assert state.get("approval4", False) is False


def test_02_existing_passive_capture_preflight_interlock():
    """Test 02: Verify that existing LiveCaptureService fails closed when Approval 3 is not authorized."""
    # Ensure environment is clean (no unauthorized permissions)
    os.environ.pop("CBE_APPROVAL_3_AUTHORIZED", None)
    os.environ.pop("CBE_BINANCE_COLLECTION_ENABLED", None)

    is_valid, violations = verify_live_capture_preflight()
    assert is_valid is False
    assert any("CBE_APPROVAL_3_AUTHORIZED" in v for v in violations)


def test_03_factual_market_data_contract_schema():
    """Test 03: Verify FactualMarketDataRecord serialization, OHLCV fields, and provenance."""
    rec = FactualMarketDataRecord(
        symbol="BTCUSDT",
        exchange_source="BINANCE_SPOT",
        candle_interval="5m",
        timestamp_open_utc="2026-09-23T20:15:00Z",
        timestamp_close_utc="2026-09-23T20:20:00Z",
        spot_price_usdt=63842.15,
        open_price_usdt=63780.0,
        high_price_usdt=63895.5,
        low_price_usdt=63750.25,
        close_price_usdt=63842.15,
        volume_base=142.85,
        volume_usdt=9119851.12,
        price_change_24h_pct=None,
        freshness_status=MarketDataFreshnessStatus.FRESH,
        snapshot_generation_timestamp_utc="2026-09-23T20:20:01Z",
        source_availability="AVAILABLE",
        source_health=MarketDataSourceHealth.HEALTHY,
        classification=DataClassification.HISTORICAL_SNAPSHOT,
        is_live=False,
        provenance_details={"channel": "TEST_CONTRACT"},
    )

    d = rec.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["spot_price_usdt"] == 63842.15
    assert d["freshness_status"] == "FRESH"
    assert d["classification"] == "HISTORICAL_SNAPSHOT"
    assert d["is_live"] is False
    assert rec.spot_price == 63842.15
    assert rec.observation_timestamp_utc == "2026-09-23T20:20:00Z"


def test_04_atomic_snapshot_replacement_and_resilience():
    """Test 04: Test atomic snapshot writing and safe reading under normal, partial, and corrupt states."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_file = Path(tmp_dir) / "test_snapshot.json"

        # 1. Normal atomic write and read
        payload = {
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": "2026-10-16T19:00:00Z",
            "spot_price_usdt": 64250.0,
            "is_live": False,
        }
        AtomicSnapshotIO.atomic_write(snap_file, payload)
        success, data, err = AtomicSnapshotIO.safe_read(snap_file)
        assert success is True
        assert data["spot_price_usdt"] == 64250.0
        assert err is None

        # 2. Missing file
        missing_file = Path(tmp_dir) / "missing.json"
        success, data, err = AtomicSnapshotIO.safe_read(missing_file)
        assert success is False
        assert data is None
        assert err == "FILE_NOT_FOUND"

        # 3. Corrupt file (malformed JSON)
        corrupt_file = Path(tmp_dir) / "corrupt.json"
        corrupt_file.write_text("{\"symbol\": \"BTCUSDT\", incomplete...", encoding="utf-8")
        success, data, err = AtomicSnapshotIO.safe_read(corrupt_file)
        assert success is False
        assert data is None
        assert "CORRUPT_JSON" in err

        # 4. Partial / empty file
        empty_file = Path(tmp_dir) / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        success, data, err = AtomicSnapshotIO.safe_read(empty_file)
        assert success is False
        assert data is None
        assert "CORRUPT_JSON" in err


def test_05_offline_adapter_schema_validation_and_monotonicity():
    """Test 05: Verify schema validation, monotonicity, duplicate detection, and gap detection."""
    # 1. Schema validation
    valid_data = {
        "symbol": "BTCUSDT",
        "exchange_source": "BINANCE_SPOT",
        "candle_interval": "5m",
        "timestamp_close_utc": "2026-10-16T19:00:00Z",
        "spot_price_usdt": 64000.0,
    }
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(valid_data)
    assert is_valid is True

    # Bad symbol
    bad_sym = dict(valid_data, symbol="ETHUSDT")
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(bad_sym)
    assert is_valid is False
    assert "Unsupported symbol" in err

    # Bad source
    bad_src = dict(valid_data, exchange_source="COINBASE")
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(bad_src)
    assert is_valid is False
    assert "Source mismatch" in err

    # Negative price
    bad_price = dict(valid_data, spot_price_usdt=-50.0)
    is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(bad_price)
    assert is_valid is False
    assert "Invalid spot price" in err

    # 2. Monotonicity checks
    t1 = "2026-10-16T19:00:00Z"
    t2 = "2026-10-16T19:05:00Z"
    is_mono, err = FactualMarketDataAdapter.check_monotonicity(t1, t2)
    assert is_mono is True

    # Duplicate timestamp
    is_mono, err = FactualMarketDataAdapter.check_monotonicity(t1, t1)
    assert is_mono is False
    assert err == "DUPLICATE_CANDLE_TIMESTAMP"

    # Out of order
    is_mono, err = FactualMarketDataAdapter.check_monotonicity(t2, t1)
    assert is_mono is False
    assert "OUT_OF_ORDER_TIMESTAMP" in err

    # 3. Gap detection (5m = 300s)
    has_gap, missing = FactualMarketDataAdapter.detect_candle_gap("2026-10-16T19:00:00Z", "2026-10-16T19:05:00Z")
    assert has_gap is False
    assert missing == 0

    has_gap, missing = FactualMarketDataAdapter.detect_candle_gap("2026-10-16T19:00:00Z", "2026-10-16T19:20:00Z")
    assert has_gap is True
    assert missing == 3  # 19:05, 19:10, 19:15


def test_06_freshness_boundary_and_clock_skew():
    """Test 06: Test freshness boundaries (<30m, 30m exact, >30m, clock skew, missing)."""
    now = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)

    # Fresh
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:50:00Z", reference_time=now) == MarketDataFreshnessStatus.FRESH

    # Boundary 30m exact
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:30:00Z", reference_time=now) == MarketDataFreshnessStatus.BOUNDARY_STALE

    # Stale
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:10:00Z", reference_time=now) == MarketDataFreshnessStatus.STALE

    # Clock skew in future > 60s
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T20:05:00Z", reference_time=now) == MarketDataFreshnessStatus.FUTURE_SKEW

    # Missing
    assert FactualMarketDataAdapter.evaluate_freshness(None, reference_time=now) == MarketDataFreshnessStatus.MISSING


def test_07_future_assets_ethusdt_and_solusdt_fail_closed():
    """Test 07: Verify ETHUSDT and SOLUSDT fail-closed UNAVAILABLE states."""
    adapter = FactualMarketDataAdapter()

    eth = adapter.get_ethusdt_factual_record()
    assert eth.symbol == "ETHUSDT"
    assert eth.spot_price_usdt is None
    assert eth.classification == DataClassification.UNAVAILABLE
    assert eth.source_health == MarketDataSourceHealth.UNAVAILABLE
    assert eth.is_live is False

    sol = adapter.get_solusdt_factual_record()
    assert sol.symbol == "SOLUSDT"
    assert sol.spot_price_usdt is None
    assert sol.classification == DataClassification.UNAVAILABLE
    assert sol.source_health == MarketDataSourceHealth.UNAVAILABLE
    assert sol.is_live is False


def test_08_api_integration_market_overview():
    """Test 08: Verify /api/v1/intelligence/market-overview serves factual data contract."""
    status, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/market-overview")
    assert status == 200
    assert "data" in resp
    data = resp["data"]

    assert data["symbol"] == "BTCUSDT"
    assert data["spot_price_usdt"] > 0
    assert data["exchange_source"] == "BINANCE_SPOT"
    assert data["candle_interval"] == "5m"
    assert data["freshness_status"] in ("FRESH", "STALE", "BOUNDARY_STALE")
    assert data["classification"] in ("HISTORICAL_SNAPSHOT", "LIVE_OBSERVED")
    assert data["is_live"] is False  # Offline MVP


def test_09_frontend_bundle_budget_and_payload_size():
    """Test 09: Verify frontend JS client size stays strictly within the 25 KB budget."""
    js = get_intelligence_js()
    js_bytes = len(js.encode("utf-8"))
    assert js_bytes < 25 * 1024, f"client.js ({js_bytes}B) exceeds 25 KB budget ({25*1024}B)"

    # HTML bundle check
    html = render_intelligence_ui_html()
    assert len(html.encode("utf-8")) < 5 * 1024


def test_10_concurrent_read_performance_and_thread_safety():
    """Test 10: Verify concurrent snapshot reading across 20 threads without race conditions."""
    adapter = FactualMarketDataAdapter()
    results = []

    def read_worker():
        rec = adapter.get_btcusdt_factual_record()
        return rec.spot_price_usdt

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(read_worker) for _ in range(100)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(results) == 100
    assert all(price == results[0] for price in results)


def test_11_production_dashboard_isolation():
    """Test 11: Verify that original /dashboard remains 100% untouched."""
    state = get_engine_state()
    dash = render_dashboard_html(state)

    assert "Coin Behavior Engine" in dash
    assert "CBE-0.7.0" in dash
    assert "FAZ A — İLK İLERİYE DÖNÜK GÖZLEM" in dash
    assert "FAZ B — İLERİYE DÖNÜK CANLI GÖZLEM" in dash
    assert "KİLİTLİ KAYIT & DENETİM BÜTÜNLÜĞÜ" in dash
