"""
Automated Test Suite for CBE Product Acceleration Sprint 14.
Verifies:
- Runtime Identity Contract (/api/v1/product/runtime-identity)
- Scientific Consistency Engine & Dual Inferential Duality
- Robustness Matrix Recalculation & 7 Disaggregated Rates (Numerator/Denominator)
- Scientific Reproduction Classifications (Exact vs Numerical vs Explained)
- Evidence Quality Profile V2 (Testable Statements, FDR Separation)
- Historical Regime Transition Laboratory Engine:
  - 6 Canonical Regimes, Row Stochasticity
  - Dirichlet-Multinomial Bayesian Beta 95% Credible Intervals
  - Timestamp Continuity & Gap Rejection
  - Persistence & Duration Analysis with Right-Censoring
  - Regime Drift Analysis (Frobenius Distance, Occupancy PSI, JSD)
  - Macro Event-Conditioned Transitions & Lift
- Scientific Research Reports 21-24 JSON and PDF Generation
"""

from __future__ import annotations

from pathlib import Path
import pytest

from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.evidence_intelligence import EvidenceIntelligenceEngine
from coin_behavior_engine.product.historical_regime_transition_lab import (
    HistoricalRegimeTransitionLabEngine,
)
from coin_behavior_engine.product.independent_reproduction import (
    IndependentScientificReproductionEngine,
)
from coin_behavior_engine.product.research_reports import ResearchReportGenerator
from coin_behavior_engine.product.robustness_explorer import HistoricalRobustnessExplorer
from coin_behavior_engine.product.scientific_comparison_policy import (
    ReproductionClassification,
    ScientificComparisonPolicyCatalog,
)
from coin_behavior_engine.product.scientific_consistency_engine import (
    ScientificConsistencyStatus,
    ScientificConsistencyEngine,
)


class TestSprint14RuntimeIdentity:
    """Test suite for Runtime Identity Contract (Section 4)."""

    def test_runtime_identity_contract_fields(self):
        status, payload = ProductDashboardApiService.handle_request(
            "/api/v1/product/runtime-identity", {}
        )
        assert status == 200
        assert payload["status"] == "success"
        assert payload["application_name"] in ["Coin Behavior Engine", "coin-behavior-engine"]
        assert "CBE-0.7.0" in payload["canonical_model_version"]
        assert payload["schema_version"] == "1.0.0"
        assert payload["runtime_identity_verified"] is True
        assert len(payload["source_commit_sha"]) == 40
        assert len(payload["build_commit_sha"]) == 40
        assert payload["image_digest"].startswith("sha256:")
        assert len(payload["dataset_manifest_sha256"]) == 64
        assert "Bu rapor" in payload["legal_disclaimer_tr"] or "Bu kimlik" in payload["legal_disclaimer_tr"]

    def test_runtime_build_fallback_and_priority(self):
        build_info = ProductDashboardApiService.get_runtime_build()
        assert "source_commit_sha" in build_info or "source_commit" in build_info
        assert "build_commit_sha" in build_info or "build_commit" in build_info
        assert "image_digest" in build_info
        assert "manifest_hash" in build_info or "manifest_sha256" in build_info
        assert len(build_info["manifest_sha256"]) == 64


class TestSprint14ScientificConsistency:
    """Test suite for Scientific Consistency Engine & Dual Inference (Section 5)."""

    def test_dual_paired_inference_duality(self):
        # Case 1: Strong effect (post >> pre) -> CI excludes 1.0 AND p <= 0.05
        pre_vols = [0.010, 0.012, 0.011, 0.014, 0.013, 0.015, 0.012]
        post_vols = [0.022, 0.024, 0.025, 0.028, 0.026, 0.030, 0.025]
        res_sig = ScientificConsistencyEngine.dual_paired_inference(pre_vols, post_vols)
        assert res_sig["valid"] is True
        assert res_sig["ci_excludes_null"] is True
        assert res_sig["p_value_is_significant"] is True
        assert res_sig["p_value_dual"] < 0.05
        assert res_sig["individual_event_non_expansion_rate"] == 0.0

        # Case 2: Null effect (post ~= pre) -> CI includes 1.0 AND p > 0.05
        pre_null = [0.015, 0.014, 0.016, 0.015, 0.017]
        post_null = [0.015, 0.014, 0.016, 0.015, 0.016]
        res_null = ScientificConsistencyEngine.dual_paired_inference(pre_null, post_null)
        assert res_null["valid"] is True
        assert res_null["ci_excludes_null"] is False
        assert res_null["p_value_is_significant"] is False
        assert res_null["p_value_dual"] > 0.05

    def test_audit_all_product_results(self):
        audit = ScientificConsistencyEngine.audit_all_product_results()
        assert audit.total_results_evaluated >= 17
        assert audit.consistent_count >= 8
        assert audit.inconsistent_count == 0
        assert audit.unresolved_issues_count == 0
        assert audit.overall_system_consistency_pct >= 88.0
        assert "tavsiyesi" in audit.legal_disclaimer_tr.lower()


class TestSprint14RobustnessMatrixRecalculation:
    """Test suite for Robustness Grid Recalculation & Disaggregated Rates (Section 6)."""

    def test_sixteen_specifications_with_invalid_nulls(self):
        matrix = HistoricalRobustnessExplorer.compute_robustness_matrix(cohort="US_CPI")
        assert matrix.total_specifications_checked == 16
        assert matrix.valid_specifications_count == 14
        assert matrix.invalid_specifications_count == 2

        # Verify invalid cells use None and explicit status
        invalid_cells = [c for c in matrix.cells if not c.is_valid_specification]
        assert len(invalid_cells) == 2
        for cell in invalid_cells:
            assert cell.validity_status == "TEMPORALLY_INVALID_RESOLUTION"
            assert cell.mean_ratio is None
            assert cell.p_value_unadjusted is None
            assert cell.p_value_fdr_adjusted is None
            assert cell.ci_lower_95 is None
            assert cell.ci_upper_95 is None
            assert cell.interval == "4h"
            assert cell.window_hours == 6

    def test_seven_disaggregated_rates_structure(self):
        matrix = HistoricalRobustnessExplorer.compute_robustness_matrix(cohort="US_CPI")
        rates = matrix.disaggregated_rates

        required_rates = [
            "POINT_ESTIMATE_DIRECTION_RATE",
            "CI_BASED_SUPPORT_RATE",
            "P_VALUE_BASED_SUPPORT_RATE",
            "FDR_ADJUSTED_SUPPORT_RATE",
            "PRACTICAL_EFFECT_RATE",
            "HOLDOUT_REPLICATION_RATE",
            "VALID_SPECIFICATION_COVERAGE",
        ]
        for r_name in required_rates:
            assert r_name in rates, f"Missing rate {r_name}"
            r_obj = rates[r_name]
            assert "percentage" in r_obj
            assert "numerator" in r_obj
            assert "denominator" in r_obj
            assert "description_tr" in r_obj
            assert 0.0 <= r_obj["percentage"] <= 100.0
            assert r_obj["numerator"] <= r_obj["denominator"]

        # Check values
        assert rates["POINT_ESTIMATE_DIRECTION_RATE"]["percentage"] == 100.0
        assert rates["POINT_ESTIMATE_DIRECTION_RATE"]["numerator"] == 14
        assert rates["POINT_ESTIMATE_DIRECTION_RATE"]["denominator"] == 14

        assert 85.0 <= rates["CI_BASED_SUPPORT_RATE"]["percentage"] <= 86.0
        assert rates["CI_BASED_SUPPORT_RATE"]["numerator"] == 12
        assert rates["CI_BASED_SUPPORT_RATE"]["denominator"] == 14

        assert rates["VALID_SPECIFICATION_COVERAGE"]["percentage"] == 87.5
        assert rates["VALID_SPECIFICATION_COVERAGE"]["numerator"] == 14
        assert rates["VALID_SPECIFICATION_COVERAGE"]["denominator"] == 16


class TestSprint14ReproductionClassification:
    """Test suite for Scientific Reproduction Classification (Section 7)."""

    def test_no_exact_match_for_differing_means(self):
        audit = IndependentScientificReproductionEngine.run_full_reproduction_audit()
        summary = audit["reproduction_summary"]

        # Exact matches must exist only where values are strictly equal
        assert summary["exact_matches_count"] >= 4
        assert summary["numerical_agreements_count"] >= 2
        assert summary["explained_method_differences_count"] >= 4
        assert summary["unresolved_mismatches_count"] == 0

        # Check CPI Mean metric
        cpi_rep = [r for r in audit["reports"] if r["event_cohort"] == "US_CPI"][0]
        cpi_mean_metric = [m for m in cpi_rep["metrics"] if m["metric_name"] == "MEAN_VOLATILITY_SHIFT_RATIO"][0]
        # Claim 1.950 vs independent 1.913 -> must NOT be EXACT_MATCH
        assert cpi_mean_metric["classification"] != ReproductionClassification.EXACT_MATCH.value
        assert cpi_mean_metric["classification"] in [
            ReproductionClassification.NUMERICALLY_EQUIVALENT.value,
            ReproductionClassification.METHOD_DIFFERENCE_EXPLAINED.value,
        ]

    def test_inflation_cohort_classification(self):
        audit = IndependentScientificReproductionEngine.run_full_reproduction_audit()
        inf_rep = [r for r in audit["reports"] if r["event_cohort"] == "US_INFLATION"][0]
        inf_mean_metric = [m for m in inf_rep["metrics"] if m["metric_name"] == "MEAN_VOLATILITY_SHIFT_RATIO"][0]
        # Claim 1.817 vs independent 1.792 -> must NOT be EXACT_MATCH
        assert inf_mean_metric["classification"] != ReproductionClassification.EXACT_MATCH.value


class TestSprint14EvidenceQualityProfileV2:
    """Test suite for Evidence Quality Profile V2 (Section 8)."""

    def test_fdr_and_leakage_dimension_corrections(self):
        rep = EvidenceIntelligenceEngine.generate_intelligence_report()
        profile = rep.evidence_quality_profile

        dim_fdr = [d for d in profile.dimensions if d.dimension_id == "DIM-09-MULTIPLE-TESTING-CONTROL"][0]
        assert "surviving_hypotheses_fdr_05" in dim_fdr.supporting_calculations
        assert dim_fdr.supporting_calculations["total_valid_hypotheses"] == 14
        assert dim_fdr.supporting_calculations["surviving_hypotheses_fdr_05"] == 7

        dim_leak = [d for d in profile.dimensions if d.dimension_id == "DIM-11-DATA-CONTAMINATION"][0]
        # Must not contain absolute unverified claim "sıfır sızıntı garantilenmiştir"
        assert "sıfır sızıntı garantilenmiştir" not in dim_leak.findings_tr.lower()
        assert "embargo_bars" in dim_leak.findings_tr


class TestSprint14HistoricalRegimeTransitionLab:
    """Test suite for Historical Regime Transition Laboratory Engine (Sections 9-15)."""

    def test_six_canonical_regimes_and_stochasticity(self):
        mat = HistoricalRegimeTransitionLabEngine.compute_transition_matrix(interval="1h", period="ALL")
        assert len(mat.regimes) == 6
        assert mat.regimes == [
            "SIDEWAYS",
            "UNCERTAIN",
            "TRENDING_BULL",
            "TRENDING_BEAR",
            "POSSIBLE_REVERSAL",
            "HIGH_VOLATILITY",
        ]
        assert len(mat.probabilities_matrix) == 6
        assert len(mat.probabilities_matrix[0]) == 6

        # Row stochasticity: sum of each row must equal 1.0 (within roundoff)
        for row in mat.probabilities_matrix:
            assert abs(sum(row) - 1.0) < 0.001

    def test_dirichlet_bayesian_credible_intervals(self):
        mat = HistoricalRegimeTransitionLabEngine.compute_transition_matrix(interval="1h", period="ALL")
        for cell in mat.cells:
            p = cell.transition_probability
            low, high = cell.credible_interval_95
            assert 0.0 <= low <= high <= 1.0
            assert low <= p or abs(low - p) < 0.05
            assert high >= p or abs(high - p) < 0.05

    def test_timestamp_continuity_enforcement(self):
        mat = HistoricalRegimeTransitionLabEngine.compute_transition_matrix(interval="1h", period="ALL")
        assert mat.timestamp_continuity_verified is True
        assert mat.data_gap_count == 0
        assert mat.total_transitions_observed > 5000

    def test_regime_durations_and_censorship(self):
        durations = HistoricalRegimeTransitionLabEngine.compute_regime_durations(interval="1h", period="ALL")
        assert len(durations) == 6
        for regime_name, info in durations.items():
            assert info.completed_episodes_count > 0
            assert info.median_duration_hours > 0.0
            assert info.mean_duration_hours > 0.0
            assert info.censored_episodes_count >= 0

    def test_historical_regime_drift(self):
        drift = HistoricalRegimeTransitionLabEngine.compute_regime_drift(
            mode="TRAIN_VS_TEST",
            param_a="TRAIN_2022_2023",
            param_b="TEST_2025",
            interval="1h",
        )
        assert drift.frobenius_distance >= 0.0
        assert drift.occupancy_shift_psi >= 0.0
        assert drift.jensen_shannon_divergence >= 0.0
        assert len(drift.difference_matrix) == 6
        assert drift.drift_significance_tr != ""

    def test_macro_conditioned_transitions(self):
        macro_cpi = HistoricalRegimeTransitionLabEngine.compute_macro_conditioned_transitions(cohort="US_CPI")
        assert macro_cpi.events_analyzed_count > 0
        assert macro_cpi.window_hours == 12
        assert 0.0 <= macro_cpi.event_window_transition_rate <= 1.0
        assert 0.0 <= macro_cpi.baseline_non_event_transition_rate <= 1.0
        assert macro_cpi.transition_rate_lift > 0.0
        assert "yatırım tavsiyesi" in macro_cpi.disclaimer_tr.lower() or "tavsiyesi" in macro_cpi.disclaimer_tr.lower()


class TestSprint14ResearchReports21To24:
    """Test suite for Research Reports 21 through 24 (Section 16)."""

    def test_generate_report_21_transition_matrix(self):
        r21 = ResearchReportGenerator.generate_regime_transition_matrix_report()
        assert r21["report_type"] == "HISTORICAL_REGIME_TRANSITION_MATRIX"
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(r21)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 20000

    def test_generate_report_22_persistence_duration(self):
        r22 = ResearchReportGenerator.generate_regime_persistence_duration_report()
        assert r22["report_type"] == "REGIME_PERSISTENCE_AND_DURATION"
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(r22)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 20000

    def test_generate_report_23_regime_drift(self):
        r23 = ResearchReportGenerator.generate_historical_regime_drift_report()
        assert r23["report_type"] == "HISTORICAL_REGIME_DRIFT"
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(r23)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 20000

    def test_generate_report_24_macro_conditioned_transitions(self):
        r24 = ResearchReportGenerator.generate_macro_conditioned_regime_transitions_report()
        assert r24["report_type"] == "MACRO_CONDITIONED_REGIME_TRANSITIONS"
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(r24)
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 20000
