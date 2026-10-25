"""
CBE — Product Acceleration Sprint 11 Test Suite
Tests for:
- Macro Event Taxonomy and Cohort Accounting
- Content Integrity (Streaming SHA-256 & Canonical Manifest)
- Walk-Forward Stability Semantics & Dynamic Embargo
- Statistical Validity & Event-Level Resampling
- Evidence Explorer & Robustness Matrix
- Hypothesis Research Studio & Deterministic Rerun Reproducibility
- All 12 PDF Research Reports
- Dashboard API Endpoints
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from coin_behavior_engine.product.macro_event_taxonomy import (
    MacroEventTaxonomyEngine,
    CANONICAL_SPECIFIC_TYPES,
    PARENT_COHORT_MAP,
)
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.walk_forward_validation import WalkForwardValidationEngine
from coin_behavior_engine.product.statistical_validity import StatisticalValidityEngine
from coin_behavior_engine.product.evidence_explorer import EvidenceExplorerEngine
from coin_behavior_engine.product.hypothesis_studio import HypothesisStudioEngine
from coin_behavior_engine.product.research_reports import ResearchReportGenerator
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


class TestSprint11MacroTaxonomy:
    """Test macro event taxonomy categorization and mathematical accounting."""

    def test_taxonomy_overview(self):
        overview = MacroEventTaxonomyEngine.get_taxonomy_overview()
        assert "specific_event_types" in overview
        assert "parent_cohorts" in overview
        assert len(overview["specific_event_types"]) >= 7
        assert "US_CPI" in overview["specific_event_types"]
        assert "US_INFLATION" in overview["parent_cohorts"]

    def test_cohort_accounting_reconciliation(self):
        engine = MacroEventTaxonomyEngine()
        manifest = engine.get_cohort_accounting("US_INFLATION")
        assert manifest.cohort_name == "US_INFLATION"
        assert manifest.is_parent_cohort is True
        assert manifest.total_discovered_events > 0
        # Mathematical identity: Total = Verified + Quarantined
        assert manifest.total_discovered_events == (
            manifest.verified_events_count + manifest.quarantined_events_count
        )
        assert manifest.mathematical_reconciliation_passed is True

    def test_specific_event_classification(self):
        engine = MacroEventTaxonomyEngine()
        cpi_type, cpi_parent = engine.classify_event_type("EVT-BLS-CPI-20220112", "US Consumer Price Index (CPI YoY)")
        assert cpi_type == "US_CPI"
        assert cpi_parent == "US_INFLATION"

        fomc_type, fomc_parent = engine.classify_event_type("EVT-FED-FOMC-20230503", "FOMC Rate Decision")
        assert fomc_type == "US_FOMC_RATE_DECISION"
        assert fomc_parent == "US_MONETARY_POLICY"


class TestSprint11ContentIntegrity:
    """Test streaming SHA-256 partition hashing and canonical manifest generation."""

    def test_canonical_manifest_generation(self):
        engine = ContentIntegrityEngine()
        manifest = engine.generate_canonical_manifest()
        assert "manifest_sha256" in manifest
        assert manifest["total_partitions"] >= 57 # 57 months of 5m + derived
        assert len(manifest["manifest_sha256"]) == 64
        assert "partitions" in manifest
        assert len(manifest["partitions"]) == manifest["total_partitions"]

    def test_quarantined_candidate_isolation(self):
        engine = ContentIntegrityEngine()
        intake_path = Path("data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet")
        if intake_path.exists():
            record = engine.audit_partition(intake_path, "5m", "2026-10", is_canonical=False)
            assert record.quarantine_status == "QUARANTINED"
            assert record.is_canonical is False
            assert len(record.sha256_content_hash) == 64


class TestSprint11WalkForwardSemantics:
    """Test dynamic embargo buffer calculation and semantic status separation."""

    def test_dynamic_embargo_calculation(self):
        engine = WalkForwardValidationEngine()
        # Embargo must be max(lookback, horizon, window)
        emb_1, _ = engine.calculate_required_embargo(feature_lookback_bars=24, label_horizon_bars=12, event_window_bars=6)
        assert emb_1 == 24

        emb_2, _ = engine.calculate_required_embargo(feature_lookback_bars=12, label_horizon_bars=48, event_window_bars=12)
        assert emb_2 == 48

    def test_regime_stability_experiment_semantics(self):
        engine = WalkForwardValidationEngine()
        res = engine.run_regime_stability_experiment(feature_lookback=24, label_horizon=12)
        assert res["status"] == "SUCCESS"
        assert res["stability_telemetry"]["distribution_status"] == "DISTRIBUTIONAL_STABILITY_OBSERVED"
        assert res["stability_telemetry"]["predictive_edge_status"] == "PREDICTIVE_EDGE_NOT_ESTABLISHED"
        assert res["stability_telemetry"]["replication_status"] == "OUT_OF_SAMPLE_REPLICATED"
        # Confirm model version and frozen status
        assert res["model_protection"]["canonical_model_version"] == "CBE-0.7.0"
        assert res["model_protection"]["canonical_model_status"] == "FROZEN_CANONICAL_MODEL"
        # Confirm zero leakage controls verified
        assert res["leakage_controls_verified"]["no_future_leakage_detected"] is True
        assert res["leakage_controls_verified"]["embargo_applied"] is True
        assert res["split_configuration"]["embargo_bars"] >= 24


class TestSprint11StatisticalValidity:
    """Test event-level cluster bootstrap and non-parametric effect sizes."""

    def test_event_level_bootstrap_ci(self):
        # Generate shift ratios
        ratios = [1.5, 1.8, 2.1, 1.9, 1.7, 2.3, 1.4, 2.0, 1.6, 2.2]
        ci = StatisticalValidityEngine.event_level_bootstrap_ci(ratios, num_resamples=500, random_seed=42)
        assert ci["point_estimate"] > 1.5
        assert ci["ci_lower"] < ci["point_estimate"] < ci["ci_upper"]
        assert ci["null_effect_included"] is False

    def test_cliffs_delta_non_parametric(self):
        pre = [0.01, 0.012, 0.009, 0.011, 0.010]
        post = [0.025, 0.030, 0.028, 0.022, 0.035]
        res = StatisticalValidityEngine.compute_cliffs_delta(pre, post)
        assert res["cliffs_delta"] > 0.8
        assert res["magnitude"] == "LARGE"

    def test_degenerate_zero_variance_handling(self):
        flat_pre = [0.01, 0.01, 0.01, 0.01]
        flat_post = [0.01, 0.01, 0.01, 0.01]
        res = StatisticalValidityEngine.compute_effect_size(flat_pre, flat_post)
        assert res["cohens_d"] == 0.0
        assert res["magnitude"] == "NEGLIGIBLE"

    def test_sample_adequacy_backward_compatibility(self):
        res = StatisticalValidityEngine.evaluate_sample_adequacy(sample_count=50, independent_units=45)
        assert res["is_adequate"] is True
        assert res["status"] == "SUFFICIENT_EVIDENCE"
        assert "adequacy_status" in res


class TestSprint11EvidenceExplorer:
    """Test Evidence Explorer catalog, filtering, and robustness matrix."""

    def test_canonical_evidence_cards(self):
        cards = EvidenceExplorerEngine.get_canonical_evidence_cards()
        assert len(cards) >= 4
        cpi_card = next((c for c in cards if "CPI" in c.finding_id or "CPI" in c.specific_event_type), None)
        assert cpi_card is not None
        assert cpi_card.specific_event_type == "US_CPI"
        assert cpi_card.event_category == "US_INFLATION"
        assert cpi_card.valid_events_count == 57

    def test_evidence_filter(self):
        all_cards = EvidenceExplorerEngine.filter_evidence({"category": "ALL"})
        assert len(all_cards["evidence_cards"]) >= 4

        inflation_cards = EvidenceExplorerEngine.filter_evidence({"category": "US_INFLATION"})
        assert len(inflation_cards["evidence_cards"]) >= 1

    def test_robustness_matrix(self):
        matrix = EvidenceExplorerEngine.get_robustness_matrix()
        assert matrix["status"] in ["success", "SUCCESS"]
        assert "matrix_cells" in matrix
        assert len(matrix["matrix_cells"]) >= 4
        assert "stability_verdict" in matrix


class TestSprint11HypothesisStudio:
    """Test Hypothesis Studio templates, execution, and deterministic reruns."""

    def test_get_templates(self):
        templates = HypothesisStudioEngine.get_templates()
        assert len(templates) >= 4
        tmpl = next((t for t in templates if "VOLATILITY" in t["template_id"]), None)
        assert tmpl is not None
        assert tmpl["default_cohort"] == "US_CPI"

    def test_execute_hypothesis_experiment(self):
        config = {
            "event_cohort": "US_CPI",
            "interval": "1h",
            "pre_hours": 12,
            "post_hours": 12,
            "outcome_metric": "volatility",
            "bootstrap_reps": 100
        }
        res = HypothesisStudioEngine.execute_hypothesis_experiment(config)
        assert res["status"] == "COMPLETED"
        assert "reproducibility_hash" in res
        assert "statistical_results" in res
        assert "scientific_interpretation_tr" in res
        assert "mandatory_disclaimer_tr" in res

    def test_deterministic_reproducibility(self):
        config = {
            "event_cohort": "US_CPI",
            "interval": "1h",
            "pre_hours": 12,
            "post_hours": 12,
            "outcome_metric": "volatility",
            "bootstrap_reps": 100,
            "random_seed": 42
        }
        res1 = HypothesisStudioEngine.execute_hypothesis_experiment(config)
        res2 = HypothesisStudioEngine.execute_hypothesis_experiment(config)

        # Reproducibility hash must be identical
        assert res1["reproducibility_hash"] == res2["reproducibility_hash"]
        # Point estimate within 1e-6 tolerance
        pe1 = res1["statistical_results"]["point_estimate_ratio"]
        pe2 = res2["statistical_results"]["point_estimate_ratio"]
        assert abs(pe1 - pe2) < 1e-6


class TestSprint11ResearchReports:
    """Test all 12 research report generators and PDF export."""

    @pytest.mark.parametrize("report_type_key,kwargs", [
        ("PERIOD_COMPARISON", {"month_a": "2026-08", "month_b": "2026-09", "interval": "1h"}),
        ("MACRO_EVENT", {"event_id_a": "EVT-BLS-CPI-20220112", "interval": "1h"}),
        ("REGIME_DRIFT", {"baseline_month": "2026-08", "target_month": "2026-09", "interval": "1h"}),
        ("DATA_QUALITY", {}),
        ("EVENT_CONDITIONED_REGIME_STUDY", {"category": "US_INFLATION", "window_hours": 12, "interval": "1h"}),
        ("WALK_FORWARD_VALIDATION", {"experiment_id": "EXP-WF-REGIME-STABILITY-01"}),
        ("SCIENTIFIC_EVIDENCE_SUMMARY", {}),
        ("EXPERIMENT_COMPARISON", {"exp_id_a": "CBE-EXP-01-CPI-VOLATILITY-SHIFT", "exp_id_b": "CBE-EXP-02-FOMC-RATE-REACTIONS"}),
        ("HYPOTHESIS_RESEARCH", {"cohort": "US_CPI", "interval": "1h", "window_hours": 12}),
        ("EVIDENCE_ROBUSTNESS", {}),
        ("DATASET_INTEGRITY", {}),
        ("REPRODUCIBILITY", {}),
    ])
    def test_generate_and_export_pdf(self, report_type_key, kwargs):
        generator_map = {
            "PERIOD_COMPARISON": ResearchReportGenerator.generate_period_comparison_report,
            "MACRO_EVENT": ResearchReportGenerator.generate_macro_event_report,
            "REGIME_DRIFT": ResearchReportGenerator.generate_regime_drift_report,
            "DATA_QUALITY": ResearchReportGenerator.generate_data_quality_report,
            "EVENT_CONDITIONED_REGIME_STUDY": ResearchReportGenerator.generate_event_regime_study_report,
            "WALK_FORWARD_VALIDATION": ResearchReportGenerator.generate_walk_forward_report,
            "SCIENTIFIC_EVIDENCE_SUMMARY": ResearchReportGenerator.generate_evidence_summary_report,
            "EXPERIMENT_COMPARISON": ResearchReportGenerator.generate_experiment_comparison_report,
            "HYPOTHESIS_RESEARCH": ResearchReportGenerator.generate_hypothesis_research_report,
            "EVIDENCE_ROBUSTNESS": ResearchReportGenerator.generate_evidence_robustness_report,
            "DATASET_INTEGRITY": ResearchReportGenerator.generate_dataset_integrity_report,
            "REPRODUCIBILITY": ResearchReportGenerator.generate_reproducibility_report,
        }

        fn = generator_map[report_type_key]
        report_data = fn(**kwargs)
        assert "report_type" in report_data
        assert "disclaimer_tr" in report_data or "mandatory_disclaimer_tr" in report_data

        # Export as PDF
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(report_data)
        assert len(pdf_bytes) > 10000
        assert pdf_bytes[:5] == b"%PDF-"


class TestSprint11DashboardApi:
    """Test REST API endpoints serving Evidence Explorer, Studio, and Taxonomy."""

    def test_evidence_explorer_endpoint(self):
        status, res = ProductDashboardApiService.handle_request("/api/v1/product/evidence-explorer")
        assert status == 200
        assert res.get("status") in ["success", "SUCCESS"]
        assert "evidence_cards" in res or "cards" in res

    def test_macro_taxonomy_endpoint(self):
        status, res = ProductDashboardApiService.handle_request("/api/v1/product/macro-event-taxonomy")
        assert status == 200
        assert res.get("status") in ["success", "SUCCESS"]
        assert "specific_event_types" in res

    def test_dataset_integrity_endpoint(self):
        status, res = ProductDashboardApiService.handle_request("/api/v1/product/dataset-content-integrity")
        assert status == 200
        assert "manifest_sha256" in res

    def test_reproducibility_status_endpoint(self):
        status, res = ProductDashboardApiService.handle_request("/api/v1/product/reproducibility-status")
        assert status == 200
        assert res.get("status") in ["success", "SUCCESS"]
        assert "reproducibility_audit" in res
