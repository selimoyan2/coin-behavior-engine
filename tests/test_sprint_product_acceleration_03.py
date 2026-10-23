"""Unit and Integration Tests for CBE Sprint Product Acceleration 03.

Verifies:
1. Dynamic runtime metadata resolution (no hardcoded git revisions).
2. Verified dataset catalog across all 5 intervals (5m, 15m, 1h, 4h, 1d).
3. Macroeconomic and regulatory event reaction ledger integration.
4. Historical candles query attaching event markers.
5. Operations environment separation (Linux VPS vs Windows WSL2 benchmarks).
6. Overview research workspace metadata.
7. Dockerfile copy and dataset inclusion integrity.
"""

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.dashboard_api import (
    ProductDashboardApiService,
    get_runtime_git_revision,
)


@pytest.fixture
def api():
    return ProductDashboardApiService


def test_01_runtime_metadata_dynamic_resolution():
    """Verify runtime git revision resolves dynamically without hardcoded obsolete hashes."""
    rev = get_runtime_git_revision()
    assert isinstance(rev, str)
    assert len(rev) >= 7
    # Must not be the old Sprint 01 hardcoded value
    assert rev != "2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9"


def test_02_dataset_catalog_endpoint(api):
    """Verify dataset catalog returns multiyear spot archives across all 5 intervals."""
    code, data = api.handle_request("/api/v1/product/dataset-catalog")
    assert code == HTTPStatus.OK
    assert data["status"] == "success"
    ds = data["datasets"]
    spot = ds["binance_spot_multiyear"]
    assert spot["symbol"] == "BTCUSDT"
    assert spot["total_partitions"] >= 285

    intervals = spot["supported_intervals"]
    for intv in ("5m", "15m", "1h", "4h", "1d"):
        assert intv in intervals
        assert intervals[intv]["months_count"] == 57

    # Regime and analog datasets
    assert ds["canonical_regime_timeline"]["total_bars"] == 105120
    assert ds["historical_analogues"]["total_analogs"] == 1530
    assert ds["historical_analogues"]["distinct_decision_points"] == 306


def test_03_macro_reactions_endpoint(api):
    """Verify audited macro reactions ledger endpoint returns empirical metrics."""
    code, data = api.handle_request("/api/v1/product/macro-reactions")
    assert code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_events"] >= 200
    events = data["events"]
    assert len(events) > 0

    first = events[0]
    assert "event_id" in first
    assert "event_name" in first
    assert "event_category" in first
    assert "published_at_utc" in first
    assert "exec_open_price" in first
    assert "ret_post_15m_pct" in first
    assert "ret_post_1h_pct" in first
    assert "ret_post_24h_pct" in first
    assert "icon" in first


def test_04_macro_reactions_filtering(api):
    """Verify category filtering on macro reactions."""
    code, data = api.handle_request("/api/v1/product/macro-reactions", {"category": ["US_INFLATION"]})
    assert code == HTTPStatus.OK
    for e in data["events"]:
        assert e["event_category"] == "US_INFLATION"

    code_fed, data_fed = api.handle_request("/api/v1/product/macro-reactions", {"category": ["US_MONETARY_POLICY"]})
    assert code_fed == HTTPStatus.OK
    for e in data_fed["events"]:
        assert e["event_category"] == "US_MONETARY_POLICY"


def test_05_historical_candles_event_markers_attached(api):
    """Verify event markers are attached to candle queries for months with macro events."""
    code, data = api.handle_request("/api/v1/product/historical-candles", {"interval": ["1h"], "month": ["2026-09"]})
    assert code == HTTPStatus.OK
    assert "event_markers" in data
    markers = data["event_markers"]
    # 2026-09 has verified events in ledger
    assert len(markers) > 0
    m = markers[0]
    assert "event_id" in m
    assert "icon" in m
    assert "timestamp_ms" in m


def test_06_operations_environment_separation(api):
    """Verify operations telemetry strictly separates running Linux VPS from WSL2 benchmarks."""
    code, data = api.handle_request("/api/v1/product/operations")
    assert code == HTTPStatus.OK
    assert "current_runtime_environment" in data
    assert "historical_test_environments" in data

    rt = data["current_runtime_environment"]
    assert "Linux VPS" in rt["environment_name"]
    assert "storage_dataset_status" in rt
    assert rt["storage_dataset_status"]["multiyear_parquet_available"] is True
    assert rt["storage_dataset_status"]["research_outputs_available"] is True

    hist = data["historical_test_environments"]
    assert "WSL2" in hist["environment_name"]
    assert hist["fsync_serialization_failures"] == 5
    assert "ZERO" in hist["production_impact"]


def test_07_overview_research_workspace_metadata(api):
    """Verify overview endpoint exposes research workspace status and dynamic revision."""
    code, data = api.handle_request("/api/v1/product/overview")
    assert code == HTTPStatus.OK
    assert "git_revision" in data
    assert len(data["git_revision"]) >= 7
    assert "research_workspace" in data
    ws = data["research_workspace"]
    assert ws["regimes_classified"] == 105120
    assert ws["analog_patterns_count"] == 306
    assert ws["verified_macro_events_count"] == 40
    assert ws["macro_reactions_audited"] >= 200


def test_08_all_intervals_parquet_availability(api):
    """Verify all 5 supported intervals can query candles without 404."""
    for intv in ("5m", "15m", "1h", "4h", "1d"):
        code, data = api.handle_request(
            "/api/v1/product/historical-candles",
            {"interval": [intv], "month": ["2026-09"], "limit": ["10"]},
        )
        assert code == HTTPStatus.OK, f"Interval {intv} failed with status {code}"
        assert data["interval"] == intv
        assert len(data["candles"]) > 0


def test_09_dockerfile_and_compose_inclusion():
    """Verify Dockerfile copies research_outputs and .gitignore tracks 5m-1d parquets."""
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY research_outputs/ ./research_outputs/" in dockerfile

    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    # 1m is ignored, but binance_spot_multiyear general directory is tracked
    assert "data/binance_spot_multiyear/1m/" in gitignore
    assert "data/binance_spot_multiyear/\n" not in gitignore
