"""
CBE — Product Acceleration Sprint 15 Test Suite
Tests for:
1. Canonical Significance Contract & Benjamini-Hochberg FDR Control
2. Scientific Consistency Engine V2 & FDR Contradiction Elimination
3. True Chronological Holdout Validation (Train: 2022-2023 vs Holdout: 2025-2026)
4. Deterministic Dataset Manifest Hash & Source Integrity
5. Historical Regime Comparison Studio & Synchronized Chart Data
6. Historical Event Forensics Workspace & Side-by-Side Event Comparison
7. Regime Episode Forensics, Right-Censoring & Bounded Queries
8. Research Lineage & Provenance Explorer
9. Research Reporting V7 (Reports 25, 26, 27, 28) and Vector PDF Export
10. Portable Experiment Package V2 Security & Asset Constraints
11. Product Dashboard API & UI Integration
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.dataset_provenance import DatasetProvenanceEngine
from coin_behavior_engine.product.statistical_decision_engine import (
    StatisticalDecisionEngine,
    StatisticalDecisionRecord,
)
from coin_behavior_engine.product.scientific_consistency_engine import (
    ScientificConsistencyEngine,
    ScientificConsistencyStatus,
)
from coin_behavior_engine.product.robustness_explorer import HistoricalRobustnessExplorer
from coin_behavior_engine.product.holdout_validation_engine import (
    ChronologicalHoldoutValidationEngine,
)
from coin_behavior_engine.product.historical_regime_comparison_studio import (
    HistoricalRegimeComparisonStudio,
)
from coin_behavior_engine.product.historical_event_forensics import (
    HistoricalEventForensicsEngine,
)
from coin_behavior_engine.product.regime_episode_forensics import (
    RegimeEpisodeForensicsEngine,
)
from coin_behavior_engine.product.research_lineage_explorer import (
    ResearchLineageExplorer,
)
from coin_behavior_engine.product.research_reports import (
    ResearchReportGenerator,
)
from coin_behavior_engine.product.experiment_packages import (
    ExperimentPackageManager,
)
from coin_behavior_engine.product.dashboard_api import (
    ProductDashboardApiService,
)
from coin_behavior_engine.product.dashboard_ui import (
    render_product_dashboard_html,
)


# ==========================================
# 1. STATISTICAL DECISION ENGINE & FDR TESTS
# ==========================================

def test_benjamini_hochberg_monotonicity_and_bounds():
    p_values = [0.001, 0.015, 0.045, 0.20, 0.80]
    q_values = StatisticalDecisionEngine.compute_benjamini_hochberg_fdr(p_values, alpha=0.05)
    
    assert len(q_values) == 5
    for q in q_values:
        assert q is not None
        assert 0.0 <= q <= 1.0
        
    sorted_pairs = sorted(zip(p_values, q_values), key=lambda x: x[0])
    sorted_qs = [p[1] for p in sorted_pairs]
    for i in range(len(sorted_qs) - 1):
        assert sorted_qs[i] <= sorted_qs[i + 1]


def test_benjamini_hochberg_invalid_and_empty():
    res = StatisticalDecisionEngine.compute_benjamini_hochberg_fdr([])
    assert res == []
    
    res_none = StatisticalDecisionEngine.compute_benjamini_hochberg_fdr([0.01, None, 0.04])
    assert res_none[1] is None
    assert res_none[0] is not None
    assert res_none[2] is not None


def test_fdr_support_decision_rule():
    # p=0.04 with q=0.44 cannot be fdr_supported!
    record_non_sig = StatisticalDecisionEngine.evaluate_significance(
        experiment_id="EXP-ROBUSTNESS-01",
        hypothesis_id="HYP-NON-SIG",
        metric_id="VR",
        estimator_id="CLOSE_TO_CLOSE",
        null_hypothesis="VR <= 1.0",
        alternative_hypothesis="VR > 1.0",
        test_method="BOOTSTRAP",
        p_value=0.04,
        fdr_q_value=0.447766,
        multiple_testing_family_id="US_CPI_FAMILY",
        sample_size=57,
        source_data_hash="abc",
        alpha=0.05,
    )
    assert record_non_sig.unadjusted_supported is True
    assert record_non_sig.fdr_supported is False
    assert record_non_sig.decision_status == "VALID_NOT_SUPPORTED"

    # p=0.001 with q=0.005 is fdr_supported
    record_sig = StatisticalDecisionEngine.evaluate_significance(
        experiment_id="EXP-ROBUSTNESS-01",
        hypothesis_id="HYP-SIG",
        metric_id="VR",
        estimator_id="CLOSE_TO_CLOSE",
        null_hypothesis="VR <= 1.0",
        alternative_hypothesis="VR > 1.0",
        test_method="BOOTSTRAP",
        p_value=0.001,
        fdr_q_value=0.005,
        multiple_testing_family_id="US_CPI_FAMILY",
        sample_size=57,
        source_data_hash="abc",
        alpha=0.05,
    )
    assert record_sig.unadjusted_supported is True
    assert record_sig.fdr_supported is True
    assert record_sig.decision_status == "VALID_SUPPORTED"


# ==========================================
# 2. SCIENTIFIC CONSISTENCY ENGINE V2
# ==========================================

def test_scientific_consistency_eliminates_fdr_contradiction():
    matrix = HistoricalRobustnessExplorer.compute_robustness_matrix("US_CPI")
    target_cell = None
    for cell in matrix.cells:
        if "758a387e" in cell.cell_id:
            target_cell = cell
            break
            
    assert target_cell is not None
    assert target_cell.p_value_fdr_adjusted > 0.05
    assert target_cell.is_expansion_statistically_significant is False
    
    audit = ScientificConsistencyEngine.audit_all_product_results()
    assert audit.inconsistent_count == 0
    contradictions = [c for c in audit.evaluations if c.consistency_status == ScientificConsistencyStatus.INCONSISTENT]
    assert len(contradictions) == 0


# ==========================================
# 3. TRUE CHRONOLOGICAL HOLDOUT VALIDATION
# ==========================================

def test_chronological_holdout_partitions_and_separation():
    audit = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
    assert audit.audit_id.startswith("AUDIT-HOLDOUT-")
    assert audit.train_partition.start_utc.startswith("2022-01-01")
    assert audit.train_partition.end_utc.startswith("2023-12-31")
    assert audit.validation_partition.start_utc.startswith("2024-01-01")
    assert audit.validation_partition.end_utc.startswith("2024-12-31")
    assert audit.holdout_partition.start_utc.startswith("2025-01-01")

    assert audit.total_specifications_evaluated > 0
    assert audit.direction_agreement_rate_pct > 50.0  # ~71.4%
    assert audit.mean_cross_period_stability_score > 0.70  # ~87.3%
    # Crucial scientific check: Holdout replication rate is separated from stability score!
    assert audit.chronological_holdout_replication_rate_pct != audit.mean_cross_period_stability_score
    assert audit.chronological_holdout_replication_rate_pct == pytest.approx(14.29, abs=0.5)


def test_holdout_replication_verdict_classifications():
    audit = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
    verdicts = {s.replication_classification for s in audit.evaluations}
    assert "REPLICATED_WITH_PREDECLARED_CRITERIA" in verdicts
    assert "DIRECTION_ONLY_REPLICATED" in verdicts
    
    for s in audit.evaluations:
        if s.replication_classification == "REPLICATED_WITH_PREDECLARED_CRITERIA":
            assert s.direction_agreement is True
            assert s.holdout_mean_ratio >= 1.10
            assert s.holdout_statistically_supported is True


# ==========================================
# 4. DETERMINISTIC MANIFEST HASH INTEGRITY
# ==========================================

def test_deterministic_manifest_hash_reproducibility():
    manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
    hash_1 = manifest_data["manifest_sha256"]
    
    expected_hash = "7ed2e950dec317c54aef7f67f1799aa9ef5b9162a55b55aaee9f352ba2de1245"
    assert hash_1 == expected_hash

    manifest_data_2 = ContentIntegrityEngine.generate_canonical_manifest()
    assert manifest_data_2["manifest_sha256"] == expected_hash


def test_quarantine_enforcement_in_manifest():
    manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
    for p in manifest_data["partitions"]:
        assert "2026-10" not in p["file_name"]
    canonicals = [p for p in manifest_data["partitions"] if p["interval"] == "5m"]
    assert len(canonicals) > 0
    assert all(p["is_canonical"] for p in canonicals)


# ==========================================
# 5. HISTORICAL REGIME COMPARISON STUDIO
# ==========================================

def test_historical_regime_comparison_studio_year_vs_year():
    res = HistoricalRegimeComparisonStudio.compare_periods(
        mode="YEAR_VS_YEAR",
        param_a="2023",
        param_b="2025",
        interval="1h",
    )
    assert res.mode == "YEAR_VS_YEAR"
    assert "2023" in res.period_a.label
    assert "2025" in res.period_b.label
    assert res.deltas.frobenius_distance >= 0.0
    assert 0.0 <= res.deltas.jensen_shannon_divergence <= 1.0
    assert res.deltas.occupancy_psi >= 0.0
    assert res.period_a.candle_count > 100
    assert res.period_b.candle_count > 100


def test_synchronized_chart_data():
    chart_data = HistoricalRegimeComparisonStudio.get_synchronized_chart_data(
        start_utc="2024-01-01T00:00:00Z",
        end_utc="2024-01-07T00:00:00Z",
        interval="1h",
        max_candles=200,
    )
    assert chart_data["asset"] == "BTCUSDT"
    assert len(chart_data["candles"]) > 0
    c0 = chart_data["candles"][0]
    assert "time" in c0
    assert "open" in c0 and "close" in c0


# ==========================================
# 6. HISTORICAL EVENT FORENSICS
# ==========================================

def test_event_forensic_detail_verified():
    detail = HistoricalEventForensicsEngine.get_event_forensic_detail(
        event_id="EVT-FED-FOMC-20220126",
        window_hours=12,
    )
    assert detail["status"] == "SUCCESS"
    assert detail["event_id"] == "EVT-FED-FOMC-20220126"
    assert detail["source_verification"] == "VERIFIED_POINT_IN_TIME"
    assert detail["volatility_ratio"] > 0.0
    assert len(detail["price_candles"]) == 25
    assert detail["disclaimer_tr"] != ""


def test_event_forensic_detail_quarantine():
    detail = HistoricalEventForensicsEngine.get_event_forensic_detail(
        event_id="EVT-BLS-CPI-20261014-CANDIDATE",
        window_hours=12,
    )
    assert detail["status"] == "EVENT_QUARANTINED"
    assert detail["event_level_inclusion_status"] == "EXCLUDED_QUARANTINE"
    assert detail["data_integrity_status"] == "QUARANTINED"
    assert len(detail["price_candles"]) == 0


def test_side_by_side_event_comparison():
    cmp_res = HistoricalEventForensicsEngine.compare_two_events(
        event_a_id="EVT-FED-FOMC-20220126",
        event_b_id="EVT-FED-FOMC-20220316",
        window_hours=12,
    )
    assert cmp_res["status"] == "SUCCESS"
    assert "volatility_ratio_delta" in cmp_res["comparison_metrics"]
    assert "scientific_limitations" in cmp_res
    assert len(cmp_res["scientific_limitations"]) > 0


# ==========================================
# 7. REGIME EPISODE FORENSICS
# ==========================================

def test_regime_episode_segmentation_and_censoring():
    episodes = RegimeEpisodeForensicsEngine.get_all_episodes()
    assert len(episodes) > 1000
    assert episodes[0].censoring_status == "COMPLETED"
    
    last_ep = episodes[-1]
    assert last_ep.censoring_status == "RIGHT_CENSORED"
    assert last_ep.exit_transition is None


def test_regime_episode_bounded_query():
    query_res = RegimeEpisodeForensicsEngine.query_episodes(
        regime="HIGH_VOLATILITY",
        page=1,
        page_size=10,
    )
    assert query_res["status"] == "SUCCESS"
    assert query_res["total_count"] > 0
    assert len(query_res["episodes"]) <= 10
    for ep in query_res["episodes"]:
        assert ep["regime_id"] == "HIGH_VOLATILITY"


# ==========================================
# 8. RESEARCH LINEAGE & PROVENANCE EXPLORER
# ==========================================

def test_research_lineage_trace():
    trace = ResearchLineageExplorer.trace_research_result("RES-ROB-CELL-758a387e")
    assert trace["result_id"] == "RES-ROB-CELL-758a387e"
    assert trace["algorithm_version"] == "CBE-0.7.0"
    assert len(trace["lineage_nodes"]) == 8
    assert len(trace["lineage_edges"]) == 7
    for p in trace["source_partitions"]:
        assert "\\" not in p["partition_id"]
        assert "/" not in p["partition_id"]


# ==========================================
# 9. RESEARCH REPORTING V7 (ALL 28 REPORTS)
# ==========================================

def test_all_28_reports_available():
    methods = [m for m in dir(ResearchReportGenerator) if m.startswith("generate_")]
    assert len(methods) == 28


def test_reports_25_to_28_generation_and_pdf():
    # Report 25: Historical Regime Comparison
    r25 = ResearchReportGenerator.generate_historical_regime_comparison_report()
    assert r25["report_type"] == "HISTORICAL_REGIME_COMPARISON"
    pdf25 = ResearchReportGenerator.export_report_as_pdf(r25)
    assert len(pdf25) > 10000

    # Report 26: Historical Event Forensics
    r26 = ResearchReportGenerator.generate_historical_event_forensics_report()
    assert r26["report_type"] == "HISTORICAL_EVENT_FORENSICS"
    pdf26 = ResearchReportGenerator.export_report_as_pdf(r26)
    assert len(pdf26) > 10000

    # Report 27: Regime Episode Analysis
    r27 = ResearchReportGenerator.generate_regime_episode_analysis_report()
    assert r27["report_type"] == "REGIME_EPISODE_ANALYSIS"
    pdf27 = ResearchReportGenerator.export_report_as_pdf(r27)
    assert len(pdf27) > 10000

    # Report 28: Scientific Integrity and Holdout Validation
    r28 = ResearchReportGenerator.generate_scientific_integrity_and_holdout_validation_report()
    assert r28["report_type"] == "SCIENTIFIC_INTEGRITY_AND_HOLDOUT_VALIDATION"
    pdf28 = ResearchReportGenerator.export_report_as_pdf(r28)
    assert len(pdf28) > 10000


# ==========================================
# 10. PORTABLE EXPERIMENT PACKAGE V2
# ==========================================

def test_portable_experiment_package_v2():
    pkg = ExperimentPackageManager.create_regime_comparison_package(
        comparison_id="TEST-01",
        mode="YEAR_VS_YEAR",
        param_a="2023",
        param_b="2024",
        results_data={"period_a": {"realized_volatility": 40.0}, "period_b": {"realized_volatility": 50.0}},
    )
    val = ExperimentPackageManager.validate_package_dict(asdict(pkg))
    assert val["is_valid"] is True
    assert val["experiment_type"] == "HISTORICAL_REGIME_COMPARISON"


def test_portable_package_path_traversal_rejection():
    pkg = ExperimentPackageManager.create_package("HYP-SEC-01", "Title", "Desc", "US_CPI")
    pkg_dict = asdict(pkg)
    pkg_dict["specification"]["description_tr"] = "Attempting ../../etc/shadow"
    val = ExperimentPackageManager.validate_package_dict(pkg_dict)
    assert val["is_valid"] is False
    assert val["status"] == "PATH_TRAVERSAL_DETECTED"


def test_portable_package_unsupported_asset_rejection():
    with pytest.raises(ValueError, match="Sentetik veri yasaktır"):
        ExperimentPackageManager.create_package("HYP-ETH", "Title", "Desc", "US_CPI", target_asset="ETHUSDT")


# ==========================================
# 11. DASHBOARD API & UI
# ==========================================

def test_dashboard_api_new_endpoints():
    endpoints = [
        "/api/v1/product/statistical-decisions",
        "/api/v1/product/holdout-validation",
        "/api/v1/product/regime-comparison",
        "/api/v1/product/synchronized-chart",
        "/api/v1/product/event-forensics",
        "/api/v1/product/event-comparison",
        "/api/v1/product/regime-episodes",
        "/api/v1/product/research-lineage",
    ]
    for ep in endpoints:
        status, res = ProductDashboardApiService.handle_request(ep)
        assert status == 200, f"Endpoint {ep} failed with status {status}"


def test_dashboard_ui_html_structure():
    html = render_product_dashboard_html()
    assert "tab-btn-studio" in html
    assert "module-studio" in html
    assert "HISTORICAL_REGIME_COMPARISON" in html
    assert "SCIENTIFIC_INTEGRITY_AND_HOLDOUT_VALIDATION" in html
    assert "YATIRIM TAVSİYESİ DEĞİLDİR" in html.upper() or "YASAL VE BİLİMSEL UYARI" in html
