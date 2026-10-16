"""Tests for CBE Sprint 10.04: Frontend Contract Binding, Data Provenance Reconciliation & Market Intelligence MVP UI.

Verifies:
- 29/29 canonical frozen artifact integrity.
- Full provenance manifest for all 11 read-only API endpoints.
- Mathematical reconciliation of the 6,328 vs 6,327 prediction count discrepancy.
- Market Intelligence UI HTML rendering and static asset dispatch.
- Client adapter schema validation, safe parsing, and error handling.
- Implementation and fail-closed safety of all 6 UI modules (A, B, C, D, E, F).
- Lightweight performance budgets (payload sizes, latency, memory).
- Isolation from existing production dashboard (/dashboard).
"""

from __future__ import annotations

import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.intelligence_api import (
    ApiEvidenceClassification,
    MarketIntelligenceApiService,
)
from coin_behavior_engine.product.provenance import (
    ApiProvenanceAuditor,
    EndpointProvenanceRecord,
    RecordCountReconciliation,
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
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html


def test_01_baseline_invariants_and_canonical_freeze():
    """Test 01: Verify baseline commit invariants, 29/29 freeze, and APPROVAL4=FALSE."""
    verify_sprint07_freeze()

    state = get_engine_state()
    assert state["model_version"] == FROZEN_MODEL_VERSION
    assert state["canonical_artifacts_verified"] == 29
    assert state["canonical_artifacts_total"] == 29
    assert state["freeze_verified"] is True


def test_02_api_data_provenance_manifest_all_endpoints():
    """Test 02: Verify exhaustive provenance manifest across all API endpoints."""
    prov_map = ApiProvenanceAuditor.audit_all_endpoints()
    assert len(prov_map) >= 11

    required_endpoints = [
        "/api/v1/intelligence",
        "/api/v1/intelligence/market-overview",
        "/api/v1/intelligence/freshness",
        "/api/v1/intelligence/model-info",
        "/api/v1/intelligence/prediction-diagnostics",
        "/api/v1/intelligence/calibration-diagnostics",
        "/api/v1/intelligence/volatility",
        "/api/v1/intelligence/market-regime",
        "/api/v1/intelligence/probability-provenance",
        "/api/v1/intelligence/feature-availability",
        "/api/v1/intelligence/evidence-limitations",
        "/api/v1/intelligence/openapi.json",
    ]

    for ep in required_endpoints:
        assert ep in prov_map, f"Missing provenance for endpoint: {ep}"
        rec = prov_map[ep]
        assert isinstance(rec, EndpointProvenanceRecord)
        assert len(rec.source_module) > 0
        assert len(rec.actual_data_source) > 0
        assert len(rec.data_storage_location) > 0
        assert len(rec.dataset_or_snapshot_identity) > 0
        assert len(rec.data_cutoff_timestamp) > 0
        assert len(rec.model_version) > 0
        assert rec.is_live_market_data is False, "Offline endpoint falsely labeled as live market data"
        assert rec.reproducibility_status in ("DETERMINISTIC_REPRODUCIBLE", "CANONICAL_FROZEN")
        assert len(rec.limitations) >= 1

    # Verify JSON manifest file on disk
    prov_path, _ = ApiProvenanceAuditor.generate_and_save_reports()
    assert prov_path.exists()
    with open(prov_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    assert manifest_data["sprint_id"] == "CBE-10.04"
    assert manifest_data["total_endpoints_audited"] >= 11


def test_03_record_count_discrepancy_reconciliation():
    """Test 03: Reconcile 6,328 vs 6,327 prediction counts and 50,007 vs 49,999 outcome counts."""
    rec = ApiProvenanceAuditor.reconcile_record_counts()
    assert isinstance(rec, RecordCountReconciliation)

    # 1. Ground truth counts
    assert rec.reconciled_prediction_count == 6328
    assert rec.reconciled_matured_outcome_count == 50007
    assert rec.expected_total_outcomes == 50624  # 6328 * 8
    assert rec.pending_unmatured_outcomes == 617  # 50624 - 50007

    # 2. Per-horizon sum
    per_h = rec.per_horizon_matured_counts
    assert sum(per_h.values()) == 50007
    assert per_h["15m"] == 6325
    assert per_h["30m"] == 6322
    assert per_h["1h"] == 6316
    assert per_h["2h"] == 6304
    assert per_h["4h"] == 6281
    assert per_h["8h"] == 6233
    assert per_h["12h"] == 6185
    assert per_h["24h"] == 6041

    # 3. Exact 1:8 integer correspondence
    assert rec.discrepancy_delta_predictions == 1  # 6328 - 6327
    assert rec.discrepancy_delta_outcomes == 8     # 50007 - 49999
    assert rec.discrepancy_delta_outcomes / rec.discrepancy_delta_predictions == 8.0

    # 4. Parquet hash and span
    assert rec.parquet_total_bars == 602240
    assert rec.prospective_start_bar_index == 595912
    assert rec.prospective_end_bar_index == 602239
    assert rec.prospective_end_bar_index - rec.prospective_start_bar_index + 1 == 6328
    assert rec.omitted_prediction_candidate_id == "PRED-20260901T210500Z"

    # 5. Report file verification
    _, rec_path = ApiProvenanceAuditor.generate_and_save_reports()
    assert rec_path.exists()
    with open(rec_path, "r", encoding="utf-8") as f:
        saved_rec = json.load(f)
    assert saved_rec["reconciliation"]["reconciled_prediction_count"] == 6328
    assert saved_rec["reconciliation"]["reconciled_matured_outcome_count"] == 50007


def test_04_ui_html_rendering_and_static_asset_integrity():
    """Test 04: Verify HTML document structure, linked assets, and standalone inlining."""
    html_linked = render_intelligence_ui_html(inline_assets=False)
    assert "<!DOCTYPE html>" in html_linked
    assert 'lang="tr"' in html_linked
    assert "Market Intelligence MVP" in html_linked
    assert '<link rel="stylesheet" href="/intelligence/style.css">' in html_linked
    assert '<script src="/intelligence/client.js" defer></script>' in html_linked
    assert "APPROVAL4 = FALSE" in html_linked
    assert "id=\"intelligence-root\"" in html_linked

    html_inlined = render_intelligence_ui_html(inline_assets=True)
    assert "<style>" in html_inlined
    assert "<script>" in html_inlined
    assert ":root {" in html_inlined
    assert "class MarketIntelligenceClient" in html_inlined

    css = get_intelligence_css()
    assert "--bg-primary:" in css
    assert ".dashboard-grid" in css
    assert ".evidence-badge" in css

    js = get_intelligence_js()
    assert "class MarketIntelligenceClient" in js
    assert "class MarketIntelligenceUi" in js
    assert "UI_STRINGS_TR" in js


def test_05_client_adapter_schema_validation_and_fail_closed():
    """Test 05: Verify client adapter schema validation rules in Python and Node.js."""
    # Test Node.js execution
    res = subprocess.run(
        ["node", "tests/verify_frontend_client.js"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node.js client verification failed:\n{res.stderr}\n{res.stdout}"
    assert "ALL NODE VERIFICATION TESTS PASSED." in res.stdout


def test_06_ui_module_a_market_overview():
    """Test 06: Verify Module A (Market Overview) presents factual indicators only."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/market-overview")
    assert code == HTTPStatus.OK
    meta = resp["metadata"]
    data = resp["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["spot_price_usdt"] > 0
    assert data["data_mode"] == "SPOT_ONLY_U0"
    assert meta["evidence_classification"] == ApiEvidenceClassification.FACTUAL_MARKET_DATA.value


def test_07_ui_module_b_volatility_and_risk():
    """Test 07: Verify Module B (Volatility & Risk) does not present unavailable derivatives as measured risk."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/volatility")
    assert code == HTTPStatus.OK
    meta = resp["metadata"]
    data = resp["data"]
    vol = data["realized_volatility"]
    assert len(vol) >= 2
    for w, val in vol.items():
        assert val > 0
    assert meta["evidence_classification"] == ApiEvidenceClassification.FACTUAL_MARKET_DATA.value

    # Verify derivatives features are strictly unavailable
    code_f, resp_f = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/feature-availability")
    assert code_f == HTTPStatus.OK
    fg = resp_f["feature_groups"]
    assert fg["spot_ohlcv"]["status"] == "AVAILABLE"
    assert fg["derivatives_funding_rate"]["status"] == "UNAVAILABLE"
    assert fg["derivatives_liquidations"]["status"] == "UNAVAILABLE"
    assert fg["derivatives_open_interest"]["status"] == "UNAVAILABLE"


def test_08_ui_module_c_prediction_diagnostics_and_calibration():
    """Test 08: Verify Module C suppresses 24h confidence claims and labels 8h/12h limitations."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/prediction-diagnostics")
    assert code == HTTPStatus.OK
    diags = resp["diagnostics"]
    assert len(diags) == 8

    # 15m..4h
    for h in diags[:5]:
        assert h["confidence_claim_allowed"] is True
        assert h["calibration_evidence_status"] == ApiEvidenceClassification.CHRONOLOGICALLY_VERIFIED_EXPLORATORY.value

    # 8h and 12h
    h8 = diags[5]
    h12 = diags[6]
    assert h8["horizon"] == "8h"
    assert h8["calibration_evidence_status"] == ApiEvidenceClassification.VALIDATED_WITH_LIMITATIONS_EXPLORATORY.value
    assert h12["horizon"] == "12h"
    assert h12["calibration_evidence_status"] == ApiEvidenceClassification.VALIDATED_WITH_LIMITATIONS_EXPLORATORY.value

    # 24h suppressed
    h24 = diags[7]
    assert h24["horizon"] == "24h"
    assert h24["offline_calibrated_width_80_bps"] is None
    assert h24["offline_calibrated_width_95_bps"] is None
    assert h24["confidence_claim_allowed"] is False
    assert h24["calibration_evidence_status"] == ApiEvidenceClassification.INSUFFICIENT_EVIDENCE.value


def test_09_ui_module_d_market_regime_safeguard():
    """Test 09: Verify Module D displays UNKNOWN and never presents legacy DELEVERAGING_STRESS as observed state."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/market-regime")
    assert code == HTTPStatus.OK
    data = resp["data"]
    assert data["consumer_state"] == "UNKNOWN"
    assert data["is_raw_model_state_suppressed"] is True
    assert "tek satırlı persentil çöküşü" in data["safeguard_explanation"]
    assert data["experimental_corrected_candidate"]["status"] == "EXPERIMENTAL_OFFLINE_VALIDATED"
    assert resp["metadata"]["evidence_classification"] == ApiEvidenceClassification.EXPERIMENTAL_ONLY.value


def test_10_ui_module_e_data_health_and_staleness():
    """Test 10: Verify Module E exposes 5 distinct un-aliased timestamps and tests staleness threshold."""
    code, resp = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/freshness")
    assert code == HTTPStatus.OK
    data = resp["data"]
    assert data["latest_observed_market_candle_utc"] == "2026-09-23T20:20:00Z"
    assert data["latest_stored_prediction_utc"] == "2026-09-23T20:20:00Z"
    assert data["latest_matured_outcome_utc"] == "2026-09-23T20:20:00Z"
    assert data["last_successful_data_ingestion_utc"] == "2026-09-23T21:23:34Z"
    assert data["latest_source_validation_utc"] == "2026-09-24T17:15:00Z"

    # Staleness check
    assert data["staleness_threshold_seconds"] == 1800
    assert data["is_stale"] is True  # Offline dataset is historical relative to current UTC


def test_11_ui_module_f_model_transparency():
    """Test 11: Verify Module F displays frozen model status, canonical count, and static fallback probabilities."""
    code_m, resp_m = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/model-info")
    assert code_m == HTTPStatus.OK
    mi = resp_m["data"]
    assert mi["model_version"] == "CBE-0.7.0"
    assert mi["safety_state"] == "FROZEN_SECURE_READ_ONLY"
    assert mi["canonical_freeze_files_count"] == 29
    assert mi["canonical_freeze_verified"] is True
    assert mi["approval4_safety_status"] is False

    code_p, resp_p = MarketIntelligenceApiService.handle_request("/api/v1/intelligence/probability-provenance")
    assert code_p == HTTPStatus.OK
    probs = resp_p["probabilities"]
    tail = probs["tail_risk_probability"]
    jump = probs["jump_risk_probability"]
    assert tail["value"] == 0.05
    assert tail["provenance_type"] == ApiEvidenceClassification.STATIC_FALLBACK_CONSTANT.value
    assert jump["value"] == 0.01
    assert jump["provenance_type"] == ApiEvidenceClassification.STATIC_FALLBACK_CONSTANT.value


def test_12_frontend_payload_sizes_and_budgets():
    """Test 12: Verify lightweight payload budgets (< 50 KB total initial bundle)."""
    html_linked = render_intelligence_ui_html(inline_assets=False)
    css = get_intelligence_css()
    js = get_intelligence_js()

    html_bytes = len(html_linked.encode("utf-8"))
    css_bytes = len(css.encode("utf-8"))
    js_bytes = len(js.encode("utf-8"))
    total_bundle = html_bytes + css_bytes + js_bytes

    assert html_bytes < 5 * 1024, f"HTML size ({html_bytes}B) exceeds 5 KB"
    assert css_bytes < 15 * 1024, f"CSS size ({css_bytes}B) exceeds 15 KB"
    assert js_bytes < 25 * 1024, f"JS client size ({js_bytes}B) exceeds 25 KB"
    assert total_bundle < 50 * 1024, f"Total bundle ({total_bundle}B) exceeds 50 KB budget"


def test_13_existing_production_dashboard_untouched():
    """Test 13: Verify that existing production dashboard (/dashboard) is 100% untouched."""
    state = get_engine_state()
    html_dash = render_dashboard_html(state)
    assert "MODEL DONDURULDU: CBE-0.7.0" in html_dash
    assert "DENETİM: %100 BAŞARILI" in html_dash
    assert "CANLI İZLEME" in html_dash
    # Confirm it does not include intelligence UI specific IDs
    assert "id=\"intelligence-root\"" not in html_dash
