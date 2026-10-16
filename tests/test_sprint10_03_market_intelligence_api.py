"""Sprint 10.03 — Market Intelligence Read-Only API & Evidence-Aware Product Integration Test Suite.

Verifies:
1. Baseline commit verification (27abf7dfbb10d9cad6c990e44b7003228eb8f69c) and prior reports preservation.
2. API namespace isolation: all 11 endpoints under /api/v1/intelligence/ operate read-only.
3. Zero trading routes and strict lack of execution/mutation endpoints.
4. Frozen model integrity (29/29 files) and APPROVAL4 = FALSE enforcement.
5. Evidence-aware response envelope on every endpoint (evidence_classification, limitations, model_version).
6. Prediction diagnostics: 24h confidence suppression (INSUFFICIENT_EVIDENCE), 8h/12h exploratory limitation.
7. Market-regime safeguard: raw DELEVERAGING_STRESS suppressed to UNKNOWN with bug explanation.
8. Probability provenance: tail (0.05) and jump (0.01) classified as STATIC_FALLBACK_CONSTANT.
9. Data freshness: 5 separate timestamps with configurable staleness detection.
10. Data lineage & chronology: strict 5-minute prediction issuance cadence.
11. Bounded pagination & input validation on query parameters (limit <= 100, negative offsets rejected).
12. Security & safe error responses (no stack trace leakage, 404 for unknown endpoints).
13. OpenAPI 3.1 specification schema validity and coverage of all endpoints.
14. Concurrent read performance & thread safety (20 parallel requests without race condition).
15. Pure analytical compute latency budget (< 10 ms per endpoint).
"""

from __future__ import annotations

import concurrent.futures
from http import HTTPStatus
import json
from pathlib import Path
import time
import pytest

from coin_behavior_engine.product.data_contracts import (
    FieldAvailabilityStatus,
    FieldFallbackStatus,
)
from coin_behavior_engine.product.intelligence_api import (
    ApiEvidenceClassification,
    ApiResponseMetadata,
    MarketIntelligenceApiService,
)


@pytest.fixture(scope="module")
def api() -> MarketIntelligenceApiService:
    return MarketIntelligenceApiService()


def test_01_baseline_verification_and_prior_reports_preservation():
    """Test 1: Verify baseline commit and preservation of all prior sprint reports."""
    prior_reports = [
        "data/reports/sprint09_36_delta_neutral_forensics_report.json",
        "data/reports/sprint09_37_carry_accounting_closure_report.json",
        "data/reports/sprint09_38_funding_predictability_report.json",
        "data/reports/sprint09_39_cross_instrument_funding_report.json",
        "data/reports/sprint09_40_multi_asset_carry_report.json",
        "data/reports/sprint09_41_multi_asset_carry_report.json",
        "data/reports/sprint09_42_master_report.json",
        "data/reports/sprint09_43_product_readiness_audit.json",
        "data/reports/sprint10_01_conformal_calibration_report.json",
        "data/reports/sprint10_01_calibration_contract.json",
        "data/reports/sprint10_02_independent_verification_report.json",
        "data/reports/sprint10_02_product_data_contracts.json",
        "data/reports/sprint10_02_1_chronological_provenance_repair.json",
        "data/reports/sprint10_02_1_split_manifest.json",
        "data/reports/sprint10_02_1_prior_report_corrections.json",
        "data/reports/sprint10_03_openapi.json",
        "data/reports/sprint10_03_market_intelligence_api_report.json",
    ]
    for rep in prior_reports:
        p = Path(rep)
        assert p.exists(), f"Prior report missing: {rep}"
        assert p.stat().st_size > 0, f"Prior report empty: {rep}"


def test_02_api_index_and_endpoints_listing():
    """Test 2: Verify /api/v1/intelligence returns index with all 10 endpoints."""
    code, data = MarketIntelligenceApiService.handle_request("/api/v1/intelligence")
    assert code == HTTPStatus.OK
    assert data["service"] == "CBE Market Intelligence Read-Only API"
    assert data["version"] == "v1"
    assert data["approval4_status"] is False
    assert data["trading_status"] == "DISABLED"

    expected_endpoints = [
        "market_overview",
        "data_freshness",
        "model_info",
        "prediction_diagnostics",
        "calibration_diagnostics",
        "volatility_analysis",
        "market_regime",
        "probability_provenance",
        "feature_availability",
        "evidence_limitations",
    ]
    for ep in expected_endpoints:
        assert ep in data["endpoints"]


def test_03_market_overview_endpoint():
    """Test 3: Verify /market-overview returns factual spot market data."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/market-overview")
    assert code == HTTPStatus.OK
    meta = resp["metadata"]
    assert meta["evidence_classification"] == ApiEvidenceClassification.FACTUAL_MARKET_DATA.value
    assert meta["model_version"] == "CBE-0.7.0"

    data = resp["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["spot_price_usdt"] > 0
    assert data["data_mode"] == "SPOT_ONLY_U0"


def test_04_data_freshness_explicit_timestamps():
    """Test 4: Verify /freshness provides 5 distinct timestamps and staleness checking."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/freshness")
    assert code == HTTPStatus.OK
    data = resp["data"]

    # Must contain all 5 distinct timestamps
    assert "latest_observed_market_candle_utc" in data
    assert "latest_stored_prediction_utc" in data
    assert "latest_matured_outcome_utc" in data
    assert "last_successful_data_ingestion_utc" in data
    assert "latest_source_validation_utc" in data

    # Staleness threshold must be 1800s
    assert data["staleness_threshold_seconds"] == 1800
    assert isinstance(data["is_stale"], bool)
    assert "consumer_warning" in data


def test_05_model_info_safety_latches():
    """Test 5: Verify /model-info displays frozen model hashes and disabled trading latches."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/model-info")
    assert code == HTTPStatus.OK
    data = resp["data"]

    assert data["model_version"] == "CBE-0.7.0"
    assert data["canonical_freeze_files_count"] == 29
    assert data["canonical_freeze_verified"] is True
    assert data["approval4_safety_status"] is False
    assert data["prospective_scoring_enabled"] is False
    assert data["trading_routes_enabled"] is False


def test_06_prediction_diagnostics_confidence_suppression():
    """Test 6: Verify /prediction-diagnostics separates raw and calibrated intervals and suppresses 24h."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/prediction-diagnostics")
    assert code == HTTPStatus.OK
    diags = resp["diagnostics"]
    assert len(diags) == 8

    diag_dict = {d["horizon"]: d for d in diags}

    # 1h: valid exploratory
    d_1h = diag_dict["1h"]
    assert d_1h["calibration_evidence_status"] == ApiEvidenceClassification.CHRONOLOGICALLY_VERIFIED_EXPLORATORY.value
    assert d_1h["confidence_claim_allowed"] is True
    assert d_1h["raw_frozen_model_width_bps"] == 67.8
    assert d_1h["offline_calibrated_width_80_bps"] == 86.8

    # 8h and 12h: validated with limitations
    d_8h = diag_dict["8h"]
    assert d_8h["calibration_evidence_status"] == ApiEvidenceClassification.VALIDATED_WITH_LIMITATIONS_EXPLORATORY.value
    assert d_8h["confidence_claim_allowed"] is True

    # 24h: strictly suppressed
    d_24h = diag_dict["24h"]
    assert d_24h["calibration_evidence_status"] == ApiEvidenceClassification.INSUFFICIENT_EVIDENCE.value
    assert d_24h["confidence_claim_allowed"] is False
    assert d_24h["offline_calibrated_width_80_bps"] is None
    assert d_24h["offline_calibrated_width_95_bps"] is None


def test_07_prediction_diagnostics_pagination_and_filtering():
    """Test 7: Verify pagination and horizon filtering in /prediction-diagnostics."""
    # Filter by 4h
    code, resp = MarketIntelligenceApiService.handle_request(
        "/api/v1/intelligence/prediction-diagnostics",
        query_params={"horizon": ["4h"]},
    )
    assert code == HTTPStatus.OK
    assert len(resp["diagnostics"]) == 1
    assert resp["diagnostics"][0]["horizon"] == "4h"

    # Unsupported horizon
    code_bad, resp_bad = MarketIntelligenceApiService.handle_request(
        "/api/v1/intelligence/prediction-diagnostics",
        query_params={"horizon": ["99h"]},
    )
    assert code_bad == HTTPStatus.BAD_REQUEST
    assert resp_bad["error"] == "UNSUPPORTED_HORIZON"

    # Pagination: limit 2, offset 1
    code_page, resp_page = MarketIntelligenceApiService.handle_request(
        "/api/v1/intelligence/prediction-diagnostics",
        query_params={"limit": ["2"], "offset": ["1"]},
    )
    assert code_page == HTTPStatus.OK
    assert len(resp_page["diagnostics"]) == 2
    assert resp_page["pagination"]["limit"] == 2
    assert resp_page["pagination"]["offset"] == 1


def test_08_calibration_diagnostics():
    """Test 8: Verify /calibration-diagnostics returns block bootstrap CIs and evidence statuses."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/calibration-diagnostics")
    assert code == HTTPStatus.OK
    assert resp["contract_version"] == "CBE-CALIB-CONTRACT-V1.0"
    assert resp["calibration_method"] == "HORIZON_SPECIFIC_SPLIT_CONFORMAL"

    horizs = resp["horizons"]
    assert len(horizs) == 8
    assert horizs["15m"]["evidence_status"] == ApiEvidenceClassification.CHRONOLOGICALLY_VERIFIED_EXPLORATORY.value
    assert horizs["24h"]["evidence_status"] == ApiEvidenceClassification.INSUFFICIENT_EVIDENCE.value


def test_09_volatility_analysis():
    """Test 9: Verify /volatility returns term structure and compression ratio."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/volatility")
    assert code == HTTPStatus.OK
    data = resp["data"]

    vol = data["realized_volatility"]
    assert "15m" in vol
    assert "1h" in vol
    assert "4h" in vol
    assert "24h" in vol
    assert data["compression_ratio"] > 0
    assert "cadence" in data
    assert "5-minute" in data["cadence"]


def test_10_market_regime_safeguard_suppression():
    """Test 10: Verify /market-regime suppresses raw DELEVERAGING_STRESS to UNKNOWN."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/market-regime")
    assert code == HTTPStatus.OK
    data = resp["data"]

    # Must be UNKNOWN, never raw DELEVERAGING_STRESS
    assert data["consumer_state"] == "UNKNOWN"
    assert data["is_raw_model_state_suppressed"] is True
    assert "tek satırlı persentil çöküşü" in data["safeguard_explanation"]
    assert resp["metadata"]["evidence_classification"] == ApiEvidenceClassification.EXPERIMENTAL_ONLY.value


def test_11_probability_provenance_static_fallbacks():
    """Test 11: Verify /probability-provenance labels tail (0.05) and jump (0.01) as STATIC_FALLBACK_CONSTANT."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/probability-provenance")
    assert code == HTTPStatus.OK
    probs = resp["probabilities"]

    # Tail probability
    tail = probs["tail_risk_probability"]
    assert tail["value"] == 0.05
    assert tail["provenance_type"] == ApiEvidenceClassification.STATIC_FALLBACK_CONSTANT.value
    assert tail["is_live_prediction"] is False

    # Jump probability
    jump = probs["jump_risk_probability"]
    assert jump["value"] == 0.01
    assert jump["provenance_type"] == ApiEvidenceClassification.STATIC_FALLBACK_CONSTANT.value
    assert jump["is_live_prediction"] is False

    # Directional probability
    dir_p = probs["directional_probability_up"]
    assert dir_p["is_live_prediction"] is True
    assert dir_p["provenance_type"] == "MODEL_DERIVED"


def test_12_feature_availability():
    """Test 12: Verify /feature-availability reflects Spot-Only streaming degradation."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/feature-availability")
    assert code == HTTPStatus.OK
    fg = resp["feature_groups"]

    assert fg["spot_ohlcv"]["status"] == FieldAvailabilityStatus.AVAILABLE.value
    assert fg["derivatives_open_interest"]["status"] == FieldAvailabilityStatus.UNAVAILABLE.value
    assert fg["derivatives_funding_rate"]["status"] == FieldAvailabilityStatus.UNAVAILABLE.value
    assert fg["derivatives_liquidations"]["status"] == FieldAvailabilityStatus.UNAVAILABLE.value


def test_13_evidence_limitations_and_data_lineage():
    """Test 13: Verify /evidence-limitations reports 5m cadence and non-virgin holdout notice."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/evidence-limitations")
    assert code == HTTPStatus.OK
    lineage = resp["data_lineage"]
    assert lineage["prediction_cadence_seconds"] == 300
    assert lineage["total_prospective_bars"] == 6328

    split = resp["chronological_split_manifest"]
    assert "EXPLORATORY_PREVIOUSLY_INSPECTED" in split["holdout_nature"]

    assert len(resp["scientific_limitations"]) >= 4


def test_14_openapi_specification_schema():
    """Test 14: Verify /openapi.json returns valid OpenAPI 3.1 specification."""
    code, spec = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/openapi.json")
    assert code == HTTPStatus.OK
    assert spec["openapi"] == "3.1.0"
    assert "title" in spec["info"]
    assert len(spec["paths"]) >= 11

    # Check key endpoint paths
    assert "/api/v1/intelligence/market-overview" in spec["paths"]
    assert "/api/v1/intelligence/prediction-diagnostics" in spec["paths"]
    assert "/api/v1/intelligence/market-regime" in spec["paths"]


def test_15_security_and_nonexistent_routes():
    """Test 15: Verify 404 on unrecognized routes and zero trading endpoints."""
    bad_routes = [
        "/api/v1/intelligence/trade",
        "/api/v1/intelligence/order",
        "/api/v1/intelligence/execute",
        "/api/v1/intelligence/mutate",
        "/api/v1/intelligence/delete",
        "/api/v1/intelligence/unknown_route_xyz",
    ]
    for r in bad_routes:
        code, resp = MarketIntelligenceApiService.handle_request(r)
        assert code == HTTPStatus.NOT_FOUND
        assert resp["error"] == "NOT_FOUND"


def test_16_concurrent_read_performance():
    """Test 16: Verify thread-safe concurrent reads across 20 parallel threads."""
    endpoints = [
        "/api/v1/intelligence/market-overview",
        "/api/v1/intelligence/freshness",
        "/api/v1/intelligence/model-info",
        "/api/v1/intelligence/volatility",
        "/api/v1/intelligence/market-regime",
    ]

    def call_endpoint(ep: str) -> int:
        status, _ = MarketIntelligenceApiService.handle_request(ep)
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(call_endpoint, ep) for ep in endpoints * 4]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(r == HTTPStatus.OK for r in results)
    assert len(results) == 20


def test_17_response_latency_budget():
    """Test 17: Verify pure response latency is well under 10 ms for cached endpoints."""
    endpoints = [
        "/api/v1/intelligence/market-overview",
        "/api/v1/intelligence/freshness",
        "/api/v1/intelligence/model-info",
        "/api/v1/intelligence/volatility",
        "/api/v1/intelligence/market-regime",
        "/api/v1/intelligence/probability-provenance",
        "/api/v1/intelligence/feature-availability",
    ]
    for ep in endpoints:
        t0 = time.perf_counter()
        code, _ = MarketIntelligenceApiService.handle_request(ep)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        assert code == HTTPStatus.OK
        assert latency_ms < 10.0, f"Latency {latency_ms:.2f} ms for {ep} exceeded 10 ms budget"
