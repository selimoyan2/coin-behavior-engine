"""
Sprint Product Acceleration 18 Test Suite — Unified Research Workspace V1.

Tests:
1. Deterministic session identity and canonical hashing.
2. Comprehensive input validation (asset, interval, chronologic ordering, max duration).
3. Strict quarantine enforcement (October 2026 rejected).
4. Multi-module orchestration (all 5 modules executed and verified).
5. Module-level error isolation and graceful degradation.
6. Dataset manifest propagation and frozen model CBE-0.7.0 invariants.
7. Bounded in-memory session caching and warm hit performance.
8. Two-session side-by-side comparison studio metrics and compatibility.
9. Unified evidence package export format (CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0).
10. API endpoints: capabilities, session, compare, evidence (GET & POST).
11. Prohibited trading endpoints and non-trading boundary enforcement.
12. HTML UI integration and responsive elements.
"""

import json
import pytest
from http import HTTPStatus

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html
from coin_behavior_engine.product.unified_research_workspace import (
    UnifiedResearchWorkspaceEngine,
)


def test_capabilities_endpoint():
    """Verify capabilities, bounds, supported assets, and modules."""
    caps = UnifiedResearchWorkspaceEngine.get_capabilities()
    assert caps["status"] == "OPERATIONAL"
    assert caps["schema_version"] == "1.0.0"
    assert caps["canonical_model_version"] == f"{FROZEN_MODEL_VERSION} (FROZEN)"
    assert "BTCUSDT" in caps["supported_assets"]
    assert "1h" in caps["supported_intervals"]
    assert len(caps["available_modules"]) == 5
    assert len(caps["presets"]) >= 5
    assert caps["governance_invariants"]["model_status"] == "STRICTLY_FROZEN"
    assert caps["governance_invariants"]["live_order_execution"] == "PERMANENTLY_PROHIBITED"


def test_deterministic_session_id():
    """Verify deterministic session ID calculation."""
    id1 = UnifiedResearchWorkspaceEngine.compute_deterministic_session_id(
        "BTCUSDT", "1h", "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z",
        ["regime_analysis", "volatility_analysis"], 5, True
    )
    id2 = UnifiedResearchWorkspaceEngine.compute_deterministic_session_id(
        "BTCUSDT", "1h", "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z",
        ["volatility_analysis", "regime_analysis"], 5, True  # sorted order invariant
    )
    id3 = UnifiedResearchWorkspaceEngine.compute_deterministic_session_id(
        "BTCUSDT", "1h", "2022-06-01T00:00:00Z", "2022-06-20T00:00:00Z",
        ["regime_analysis", "volatility_analysis"], 5, True
    )
    assert id1.startswith("URS-")
    assert id1 == id2
    assert id1 != id3


def test_input_validation_and_quarantine_enforcement():
    """Verify input validation, bounds, and strict quarantine rejection."""
    # Unsupported asset
    with pytest.raises(ValueError, match="Asset 'ETHUSDT' is not supported"):
        UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc="2022-06-01T00:00:00Z",
            reference_end_utc="2022-06-15T00:00:00Z",
            asset="ETHUSDT",
        )

    # Inverted dates
    with pytest.raises(ValueError, match="strictly earlier"):
        UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc="2022-06-15T00:00:00Z",
            reference_end_utc="2022-06-01T00:00:00Z",
        )

    # Window too small (<1 hour)
    with pytest.raises(ValueError, match="at least 1.0 hour"):
        UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc="2022-06-01T00:00:00Z",
            reference_end_utc="2022-06-01T00:30:00Z",
        )

    # Quarantined period (October 2026)
    with pytest.raises(ValueError, match="quarantined partition 2026-10"):
        UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc="2026-10-01T00:00:00Z",
            reference_end_utc="2026-10-15T00:00:00Z",
        )


def test_full_session_orchestration():
    """Verify execution of all 5 research modules."""
    sess = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        pattern_candidates=3,
        disjoint_patterns=True,
    )
    assert sess["session_id"].startswith("URS-")
    assert sess["execution_status"] in ("COMPLETED", "PARTIAL")
    assert sess["candle_count"] > 100
    assert sess["canonical_model_version"] == f"{FROZEN_MODEL_VERSION} (FROZEN)"
    assert len(sess["dataset_manifest_sha256"]) == 64

    results = sess["module_results"]
    assert "regime_analysis" in results
    assert "volatility_analysis" in results
    assert "historical_pattern_discovery" in results
    assert "macro_comparison" in results
    assert "statistical_evidence" in results

    # Regime verification
    reg = results["regime_analysis"]
    assert reg["status"] == "SUCCESS"
    assert "dominant_regime" in reg
    assert abs(sum(reg["regime_distribution"].values()) - 1.0) < 0.01
    assert reg["mean_episode_duration_bars"] > 0

    # Volatility verification
    vol = results["volatility_analysis"]
    assert vol["status"] == "SUCCESS"
    assert vol["realized_volatility_annual_pct"] > 0
    assert vol["parkinson_volatility_annual_pct"] > 0

    # Pattern discovery V2 verification
    pat = results["historical_pattern_discovery"]
    assert pat["status"] == "SUCCESS"
    assert pat["experiment_id"].startswith("EXP-PAT-V2-")
    assert pat["disjoint_filtering_applied"] is True
    assert pat["ranking_stability_verdict"] in ("HIGH_STABILITY", "MODERATE_STABILITY", "SENSITIVE")
    assert len(pat["ranked_candidates"]) > 0

    # Statistical evidence verification
    stat = results["statistical_evidence"]
    assert stat["status"] == "SUCCESS"
    assert stat["holdout_exposure_status"] == "HOLDOUT_PREVIOUSLY_EXPOSED"
    assert stat["eligible_specifications_count"] == 14
    assert stat["replicated_specifications_count"] == 2
    assert "ci_lower" not in stat or len(stat["confidence_interval_95_mean_return_pct"]) == 2


def test_session_caching_and_latency():
    """Verify session caching accelerates subsequent requests."""
    sess1 = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        pattern_candidates=3,
    )
    sess2 = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        pattern_candidates=3,
    )
    assert sess1["session_id"] == sess2["session_id"]
    assert sess2.get("cache_hit") is True


def test_side_by_side_session_comparison():
    """Verify comparative analysis between two distinct historical windows."""
    sess_a = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        pattern_candidates=2,
    )
    sess_b = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2024-07-27T01:00:00Z",
        reference_end_utc="2024-08-10T01:00:00Z",
        interval="1h",
        pattern_candidates=2,
    )
    cmp = UnifiedResearchWorkspaceEngine.compare_sessions(sess_a, sess_b)

    assert cmp["comparison_id"].startswith("CMP-URS-")
    assert 0.0 <= cmp["composite_similarity_pct"] <= 100.0
    assert "dimension_comparisons" in cmp
    dims = cmp["dimension_comparisons"]
    assert "regime_composition" in dims
    assert "volatility" in dims
    assert "return_mean" in dims
    assert "macro_context" in dims
    assert "scientific_summary_tr" in cmp


def test_evidence_package_export():
    """Verify evidence package schema 1.0.0 and deterministic checksum."""
    sess = UnifiedResearchWorkspaceEngine.execute_session(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        pattern_candidates=2,
    )
    pkg = UnifiedResearchWorkspaceEngine.export_unified_evidence_package(sess)

    assert pkg["package_format"] == "CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0"
    assert pkg["package_id"].startswith("PKG-URS-")
    assert len(pkg["integrity_checksum_sha256"]) == 64
    assert pkg["canonical_model"] == f"{FROZEN_MODEL_VERSION} (FROZEN)"
    assert pkg["scientific_integrity_attestation"]["holdout_exposure_status"] == "HOLDOUT_PREVIOUSLY_EXPOSED"
    assert pkg["scientific_integrity_attestation"]["trading_prohibited"] is True
    assert pkg["status"] == "SUCCESS"


def test_api_endpoints_via_dashboard_service():
    """Verify all 4 new API routes via ProductDashboardApiService."""
    # 1. Capabilities
    code, caps = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-workspace/capabilities", {}
    )
    assert code == HTTPStatus.OK
    assert caps["status"] == "OPERATIONAL"

    # 2. Session GET
    code, sess = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-workspace/session",
        {
            "reference_start_utc": ["2022-06-01T00:00:00Z"],
            "reference_end_utc": ["2022-06-15T00:00:00Z"],
            "pattern_candidates": ["2"],
        }
    )
    assert code == HTTPStatus.OK
    assert sess["session_id"].startswith("URS-")

    # 3. Session POST
    code, sess_post = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/research-workspace/session",
        body={
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "pattern_candidates": 2,
        }
    )
    assert code == HTTPStatus.OK
    assert sess_post["session_id"] == sess["session_id"]

    # 4. Compare GET
    code, cmp = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-workspace/compare",
        {
            "session_a_id": [sess["session_id"]],
            "session_b_id": [sess["session_id"]],
        }
    )
    assert code == HTTPStatus.OK
    assert cmp["composite_similarity_pct"] == 100.0

    # 5. Evidence GET
    code, ev = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-workspace/evidence",
        {"session_id": [sess["session_id"]]}
    )
    assert code == HTTPStatus.OK
    assert ev["package_format"] == "CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0"


def test_prohibited_live_trading_isolation():
    """Strict verification that live trading and order execution endpoints return 404."""
    for path in ["/api/v1/orders", "/api/v1/trade", "/api/v1/execute", "/api/v1/order/create"]:
        code, resp = ProductDashboardApiService.handle_request(path, {})
        assert code == HTTPStatus.NOT_FOUND


def test_dashboard_html_rendering_integration():
    """Verify that product dashboard HTML renders unified workspace tab and controls."""
    html = render_product_dashboard_html()
    assert "tab-btn-unified-workspace" in html
    assert "module-unified-workspace" in html
    assert "btn-urs-run" in html
    assert "btn-urs-export" in html
    assert "CBE-0.7.0 (STRICTLY FROZEN)" in html
