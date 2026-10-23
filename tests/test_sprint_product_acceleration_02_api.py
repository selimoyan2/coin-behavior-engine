"""Unit & Integration Tests for Sprint Product Acceleration 02:
Historical Candlestick Explorer, Market Regime Timeline & Analog Research Explorer.

Verifies:
1. GET /api/v1/product/historical-candles loads local multi-year Parquet files.
2. Validates intervals (5m, 15m, 1h, 4h, 1d) and rejects invalid intervals (HTTP 400).
3. Attaches historical regime overlays from market_regime_timeline.csv.
4. Bounded pagination (limit, offset) and available months discovery.
5. GET /api/v1/product/historical-regimes returns distribution and recent transitions.
6. GET /api/v1/product/analogs returns top-5 nearest analogs with trajectory dispersion.
7. Enforces STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC research classification.
8. GET /api/v1/product/analogs/patterns returns curated reference patterns list.
9. Live HTTP integration test on ephemeral port verifying end-to-end server responses.
"""

from __future__ import annotations

from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
import threading
import time
import urllib.error
import urllib.request
import pytest

from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.web.server import EngineRequestHandler


@pytest.fixture(scope="module")
def api() -> ProductDashboardApiService:
    return ProductDashboardApiService()


@pytest.fixture(scope="module")
def test_server():
    server_address = ("127.0.0.1", 0)
    httpd = ThreadingHTTPServer(server_address, EngineRequestHandler)
    port = httpd.server_port
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"

    httpd.shutdown()
    httpd.server_close()


# ==============================================================================
# 1. Historical Candlestick Explorer Tests
# ==============================================================================

def test_01_historical_candles_default_1h(api):
    status_code, data = api.handle_request("/api/v1/product/historical-candles", {"limit": ["50"]})
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["symbol"] == "BTCUSDT"
    assert data["interval"] == "1h"
    assert data["contamination_status"] == "RESEARCH_CONTAMINATED"
    assert "available_months" in data
    assert len(data["available_months"]) > 0
    assert len(data["candles"]) <= 50

    candle0 = data["candles"][0]
    assert "time" in candle0
    assert "open" in candle0
    assert "high" in candle0
    assert "low" in candle0
    assert "close" in candle0
    assert "volume" in candle0
    assert "regime" in candle0
    assert candle0["high"] >= candle0["low"]


def test_02_historical_candles_intervals(api):
    # Test 4h
    status_code, data_4h = api.handle_request("/api/v1/product/historical-candles", {"interval": ["4h"], "limit": ["10"]})
    assert status_code == HTTPStatus.OK
    assert data_4h["interval"] == "4h"
    assert len(data_4h["candles"]) <= 10

    # Test 1d
    status_code, data_1d = api.handle_request("/api/v1/product/historical-candles", {"interval": ["1d"], "limit": ["10"]})
    assert status_code == HTTPStatus.OK
    assert data_1d["interval"] == "1d"

    # Test invalid interval
    status_code, err = api.handle_request("/api/v1/product/historical-candles", {"interval": ["2h"]})
    assert status_code == HTTPStatus.BAD_REQUEST
    assert "Geçersiz zaman aralığı" in err["message"]


def test_03_historical_candles_month_selection(api):
    # Request a specific historical month
    status_code, data = api.handle_request(
        "/api/v1/product/historical-candles",
        {"interval": ["1h"], "month": ["2026-08"], "limit": ["20"]},
    )
    assert status_code == HTTPStatus.OK
    assert data["month"] == "2026-08"
    assert "2026-08" in data["candles"][0]["datetime_utc"]


# ==============================================================================
# 2. Historical Regimes Summary Tests
# ==============================================================================

def test_04_historical_regimes_summary(api):
    status_code, data = api.handle_request("/api/v1/product/historical-regimes")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_bars_analyzed"] > 10000

    dist = data["regime_distribution"]
    assert len(dist) >= 4
    reg_names = [d["regime"] for d in dist]
    assert "SIDEWAYS" in reg_names or "NORMAL" in reg_names

    transitions = data["recent_transitions"]
    assert len(transitions) > 0
    t0 = transitions[0]
    assert "transition_from" in t0
    assert "transition_to" in t0
    assert "close_price" in t0


# ==============================================================================
# 3. Historical Analog Similarity Explorer Tests
# ==============================================================================

def test_05_analog_patterns_list(api):
    status_code, data = api.handle_request("/api/v1/product/analogs/patterns")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["count"] > 0
    assert len(data["patterns"]) > 0

    p0 = data["patterns"][0]
    assert "id" in p0
    assert "decision_datetime_utc" in p0
    assert "label" in p0
    assert "regime" in p0


def test_06_analogs_retrieval_and_dispersion(api):
    status_code, data = api.handle_request("/api/v1/product/analogs", {"limit": ["5"]})
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["analogs_count"] <= 5
    assert len(data["analogs"]) <= 5

    # Check top analog record
    a0 = data["analogs"][0]
    assert a0["rank"] == 1
    assert "analogue_datetime_utc" in a0
    assert "similarity_distance" in a0
    assert "similarity_score_percent" in a0
    assert a0["similarity_score_percent"] > 0.0
    assert "fwd_ret_24h_percent" in a0
    assert "trajectory_points" in a0
    assert len(a0["trajectory_points"]) == 5  # [0, 15m, 1h, 4h, 24h]

    # Check dispersion
    disp = data["trajectory_dispersion"]
    assert "mean_24h_return_percent" in disp
    assert "median_24h_return_percent" in disp
    assert "min_24h_return_percent" in disp
    assert "max_24h_return_percent" in disp

    # Verify research limitation contract
    contract = data["research_contract"]
    assert contract["classification"] == "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC"
    assert contract["directional_edge"] == "NOT_ESTABLISHED"


# ==============================================================================
# 4. Live HTTP Server Integration Tests
# ==============================================================================

def test_07_http_live_historical_candles(test_server):
    req = urllib.request.Request(f"{test_server}/api/v1/product/historical-candles?interval=1h&limit=5")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert len(data["candles"]) <= 5


def test_08_http_live_analogs(test_server):
    req = urllib.request.Request(f"{test_server}/api/v1/product/analogs?limit=3")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert len(data["analogs"]) == 3
        assert data["research_contract"]["classification"] == "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC"


def test_09_http_live_analog_patterns(test_server):
    req = urllib.request.Request(f"{test_server}/api/v1/product/analogs/patterns")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert len(data["patterns"]) >= 5
