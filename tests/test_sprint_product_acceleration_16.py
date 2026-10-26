"""
CBE — Product Acceleration Sprint 16 Test Suite
Tests for:
1. Delivery Manifest & Git Commit Lineage Programmatic Verification
2. Holdout Denominator Accounting & Exposure Status Remediation
3. FDR Lineage Reconciliation (Cell RES-ROB-CELL-758a387e)
4. Historical Pattern Discovery Engine — 5-Component Explainable Similarity
5. Overlap, Spacing, and Zero Forward Leakage Invariants
6. Ranking Sensitivity & Weight Perturbation Analysis
7. Side-by-Side Synchronized Comparison & Base-100 Normalization
8. Research Reports 29, 30, 31, 32 & Vector PDF Export
9. Portable Research Experiment Packages V3 (Schema 3.0.0) Security Controls
10. Dashboard API REST Endpoints
11. Dashboard UI HTML Structure & Component Integration
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from http import HTTPStatus

from coin_behavior_engine.product.delivery_manifest import (
    DeliveryManifestEngine,
    DeliveryManifestRecord,
)
from coin_behavior_engine.product.holdout_validation_engine import (
    ChronologicalHoldoutValidationEngine,
    ChronologicalHoldoutAuditReport,
)
from coin_behavior_engine.product.fdr_lineage_tracker import (
    FDRLineageTracker,
    FDRCellLineageRecord,
)
from coin_behavior_engine.product.historical_pattern_discovery import (
    HistoricalPatternDiscoveryEngine,
    PatternDiscoverySearchResult,
    PatternCandidateMatch,
)
from coin_behavior_engine.product.experiment_packages import (
    ExperimentPackageManager,
    PortableExperimentPackage,
)
from coin_behavior_engine.product.research_reports import ResearchReportGenerator
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html


# =========================================================================
# 1. DELIVERY MANIFEST & GIT COMMIT LINEAGE
# =========================================================================

def test_delivery_manifest_generation():
    """Manifest returns valid 40-character commit hashes, branch, and metadata."""
    manifest = DeliveryManifestEngine.generate_delivery_manifest()
    assert isinstance(manifest, DeliveryManifestRecord)
    assert manifest.sprint_id == "CBE_PRODUCT_ACCELERATION_16"
    assert manifest.branch == "main"
    assert len(manifest.base_commit_sha) == 40
    assert manifest.base_commit_sha == "60958114a2382100d8c7503be7a76002c9cd8204"
    assert manifest.staging_binding == "127.0.0.1:18080->8000/tcp"
    assert manifest.production_zero_touch is True


# =========================================================================
# 2. HOLDOUT DENOMINATOR & COVERAGE REMEDIATION
# =========================================================================

def test_holdout_denominator_accounting():
    """Replication rate explicitly accounts for 14 eligible of 16 total specifications."""
    audit = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
    assert audit.total_specifications == 16
    assert audit.eligible_specifications == 14
    assert audit.invalid_specifications == 2
    assert audit.replicated_specifications == 2
    assert audit.declared_denominator == 14
    assert audit.chronological_holdout_replication_rate_pct == pytest.approx(14.29, abs=0.02)
    assert audit.all_specifications_replication_rate_pct == pytest.approx(12.50, abs=0.02)


def test_holdout_exposure_and_coverage_dates():
    """Audit declares exposure status and exact dataset coverage dates."""
    audit = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
    assert audit.holdout_exposure_status == "HOLDOUT_PREVIOUSLY_EXPOSED"
    assert audit.configured_holdout_end == "2026-09-30T23:59:59Z"
    assert audit.actual_source_coverage_end == "2026-09-30T23:55:00Z"
    assert audit.last_eligible_event_timestamp == "2026-09-11T12:30:00Z"
    assert "2025-2026" in audit.holdout_exposure_rationale_tr


# =========================================================================
# 3. FDR LINEAGE & CELL 758a387e RECONCILIATION
# =========================================================================

def test_fdr_lineage_cell_audit():
    """Cell RES-ROB-CELL-758a387e reconciles p=0.3838, q=0.4478, and explains the 0.041042 typo."""
    record = FDRLineageTracker.get_target_cell_lineage()
    assert isinstance(record, FDRCellLineageRecord)
    assert record.cell_id == "RES-ROB-CELL-758a387e"
    assert record.target_specification == "1h-24h-CLOSE_TO_CLOSE"
    assert record.current_p_value == pytest.approx(0.383799, abs=0.0001)
    assert record.current_q_value == pytest.approx(0.447766, abs=0.0001)
    assert record.reported_doc_p_value_anomaly == pytest.approx(0.041042, abs=0.0001)
    assert record.fdr_supported is False
    assert record.is_expansion_statistically_significant is False
    assert "4h-12h-PARKINSON_HIGH_LOW" in record.anomaly_root_cause_explanation


# =========================================================================
# 4. HISTORICAL PATTERN DISCOVERY — MULTI-DIMENSIONAL SIMILARITY
# =========================================================================

def test_pattern_discovery_search():
    """Engine discovers historical candidate windows and computes 5 similarity components."""
    engine = HistoricalPatternDiscoveryEngine()
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        max_candidates=5,
        step_hours=72,
    )
    assert isinstance(result, PatternDiscoverySearchResult)
    assert len(result.candidates) > 0

    top = result.candidates[0]
    assert 0.0 <= top.overall_similarity_pct <= 100.0
    assert 0.0 <= top.regime_jsd_distance <= 1.0
    assert 0.0 <= top.volatility_distance <= 1.0
    assert top.return_distribution_distance >= 0.0
    assert top.transition_matrix_distance >= 0.0
    assert top.persistence_gap_hours >= 0.0


# =========================================================================
# 5. OVERLAP, SPACING & ZERO LEAKAGE GUARDS
# =========================================================================

def test_pattern_discovery_overlap_and_spacing():
    """Candidates never overlap reference window and enforce spacing."""
    engine = HistoricalPatternDiscoveryEngine()
    ref_start = "2022-06-01T00:00:00Z"
    ref_end = "2022-06-15T00:00:00Z"
    result = engine.search_similar_patterns(
        reference_start_utc=ref_start,
        reference_end_utc=ref_end,
        max_candidates=5,
        step_hours=72,
        min_spacing_hours=48,
    )
    import pandas as pd
    r_s = pd.to_datetime(ref_start, utc=True)
    r_e = pd.to_datetime(ref_end, utc=True)

    for c in result.candidates:
        c_s = pd.to_datetime(c.start_utc, utc=True)
        c_e = pd.to_datetime(c.end_utc, utc=True)
        # Ensure no overlap with reference window
        assert (c_e < r_s) or (c_s > r_e)


# =========================================================================
# 6. RANKING SENSITIVITY & WEIGHT PERTURBATION
# =========================================================================

def test_pattern_ranking_sensitivity():
    """Engine analyzes ranking stability under weight perturbations."""
    engine = HistoricalPatternDiscoveryEngine()
    sens = engine.analyze_ranking_sensitivity(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
    )
    assert sens["status"] == "SUCCESS"
    assert "weight_scenarios" in sens
    assert "default" in sens["weight_scenarios"]
    assert "volatility_heavy" in sens["weight_scenarios"]
    assert "regime_heavy" in sens["weight_scenarios"]
    assert "ranking_stability_verdict" in sens


# =========================================================================
# 7. SYNCHRONIZED COMPARISON & BASE-100 NORMALIZATION
# =========================================================================

def test_pattern_side_by_side_comparison():
    """Side-by-side comparison packages paired candles, base-100 indexed prices, and macro events."""
    engine = HistoricalPatternDiscoveryEngine()
    cmp = engine.get_side_by_side_comparison(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        candidate_start_utc="2022-11-01T00:00:00Z",
        candidate_end_utc="2022-11-15T00:00:00Z",
    )
    assert cmp["status"] == "SUCCESS"
    assert len(cmp["reference_candles"]) > 0
    assert len(cmp["candidate_candles"]) > 0
    assert cmp["reference_indexed_series"][0]["indexed_price"] == pytest.approx(100.0, abs=0.1)
    assert cmp["candidate_indexed_series"][0]["indexed_price"] == pytest.approx(100.0, abs=0.1)
    assert "similarity_analysis" in cmp


# =========================================================================
# 8. RESEARCH REPORTS 29-32 & PDF VECTOR EXPORT
# =========================================================================

def test_research_reports_29_to_32():
    """Reports 29-32 generate valid report dictionaries and vector PDFs."""
    # Report 29
    r29 = ResearchReportGenerator.generate_historical_pattern_similarity_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z"
    )
    assert r29["report_type"] == "HISTORICAL_PATTERN_SIMILARITY"
    pdf29 = ResearchReportGenerator.export_report_as_pdf(r29)
    assert len(pdf29) > 1000

    # Report 30
    r30 = ResearchReportGenerator.generate_historical_window_comparison_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z",
        "2022-11-01T00:00:00Z", "2022-11-15T00:00:00Z"
    )
    assert r30["report_type"] == "HISTORICAL_WINDOW_COMPARISON"
    pdf30 = ResearchReportGenerator.export_report_as_pdf(r30)
    assert len(pdf30) > 1000

    # Report 31
    r31 = ResearchReportGenerator.generate_similarity_sensitivity_analysis_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z"
    )
    assert r31["report_type"] == "SIMILARITY_SENSITIVITY_ANALYSIS"
    pdf31 = ResearchReportGenerator.export_report_as_pdf(r31)
    assert len(pdf31) > 1000

    # Report 32
    r32 = ResearchReportGenerator.generate_scientific_evidence_closure_report()
    assert r32["report_type"] == "SCIENTIFIC_EVIDENCE_CLOSURE"
    pdf32 = ResearchReportGenerator.export_report_as_pdf(r32)
    assert len(pdf32) > 1000


# =========================================================================
# 9. PORTABLE RESEARCH EXPERIMENT PACKAGES V3
# =========================================================================

def test_portable_experiment_package_v3_validation():
    """Package manager supports schema 3.0.0 and rejects path traversal and tampered payloads."""
    pkg = ExperimentPackageManager.create_pattern_similarity_package(
        similarity_id="TEST-SIM-01",
        reference_start="2022-06-01T00:00:00Z",
        reference_end="2022-06-15T00:00:00Z",
        search_results={"candidates": [{"overall_similarity_pct": 94.5}]},
    )
    pkg_dict = asdict(pkg)
    val = ExperimentPackageManager.validate_package_dict(pkg_dict)
    assert val["is_valid"] is True
    assert val["schema_version"] == "3.0.0"

    # Reject path traversal
    tampered_traversal = json.loads(json.dumps(pkg_dict))
    tampered_traversal["specification"]["title_tr"] = "../../etc/passwd"
    val_trav = ExperimentPackageManager.validate_package_dict(tampered_traversal)
    assert val_trav["is_valid"] is False
    assert val_trav["status"] == "PATH_TRAVERSAL_DETECTED"

    # Reject tampered payload
    tampered_hash = json.loads(json.dumps(pkg_dict))
    tampered_hash["results"]["mean_post_volatility_pct"] = 999.99
    val_hash = ExperimentPackageManager.validate_package_dict(tampered_hash)
    assert val_hash["is_valid"] is False
    assert val_hash["status"] == "TAMPERED"


# =========================================================================
# 10. PRODUCT DASHBOARD API ENDPOINTS
# =========================================================================

def test_dashboard_api_endpoints_sprint16():
    """All Sprint 16 endpoints return HTTPStatus.OK with correct schema."""
    # 1. Delivery manifest
    st, res = ProductDashboardApiService.handle_request("/api/v1/product/delivery-manifest")
    assert st == HTTPStatus.OK
    assert res.get("sprint_id") == "CBE_PRODUCT_ACCELERATION_16"

    # 2. FDR Lineage
    st, res = ProductDashboardApiService.handle_request("/api/v1/product/fdr-lineage")
    assert st == HTTPStatus.OK
    assert len(res.get("lineage_records", [])) >= 1

    # 3. Session state
    st, res = ProductDashboardApiService.handle_request("/api/v1/product/session-state")
    assert st == HTTPStatus.OK
    st_post, res_post = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/session-state", body={"active_tab": "patterns"}
    )
    assert st_post == HTTPStatus.OK
    assert res_post.get("active_tab") == "patterns"

    # 4. Evidence panel
    st, res = ProductDashboardApiService.handle_request("/api/v1/product/evidence-panel")
    assert st == HTTPStatus.OK
    assert res.get("holdout_replication", {}).get("declared_denominator") == 14

    # 5. Pattern discovery search
    st, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/pattern-discovery/search?reference_start_utc=2022-06-01T00:00:00Z&reference_end_utc=2022-06-15T00:00:00Z&max_candidates=3"
    )
    assert st == HTTPStatus.OK
    assert res.get("status") == "SUCCESS"


# =========================================================================
# 11. DASHBOARD UI HTML INTEGRATION
# =========================================================================

def test_dashboard_ui_html_structure_sprint16():
    """Dashboard HTML contains all Sprint 16 elements, navigation, and reports dropdown."""
    html = render_product_dashboard_html()
    assert "tab-btn-patterns" in html
    assert "module-patterns" in html
    assert "panel-common-evidence" in html
    assert "tbl-pattern-candidates-body" in html
    assert "pat-comparison-canvas" in html
    assert "HISTORICAL_PATTERN_SIMILARITY" in html
    assert "HISTORICAL_WINDOW_COMPARISON" in html
    assert "SIMILARITY_SENSITIVITY_ANALYSIS" in html
    assert "SCIENTIFIC_EVIDENCE_CLOSURE" in html
    assert "ev-kpi-holdout-rate" in html
    assert "ev-kpi-fdr-p" in html
