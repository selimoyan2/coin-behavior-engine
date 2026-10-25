"""
Automated Test Suite for Sprint 13: Scientific Truth Engine, Independent Reproduction Hardening,
Interactive Specification Curves, Research Experience V3 & Evidence Integrity.
"""

from dataclasses import asdict
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.scientific_comparison_policy import (
    ScientificComparisonPolicyCatalog,
    ReproductionClassification,
    MetricIdentityContract,
    MetricEvaluationResult,
)
from coin_behavior_engine.product.independent_reproduction import (
    IndependentScientificReproductionEngine,
)
from coin_behavior_engine.product.robustness_explorer import (
    HistoricalRobustnessExplorer,
)
from coin_behavior_engine.product.interactive_specification_curves import (
    InteractiveSpecificationCurveStudio,
)
from coin_behavior_engine.product.evidence_intelligence import (
    EvidenceIntelligenceEngine,
)
from coin_behavior_engine.product.distribution_lab import (
    HistoricalDistributionLabEngine,
)
from coin_behavior_engine.product.research_reports import (
    ResearchReportGenerator,
)


class TestSprint13ScientificComparisonPolicy:
    """Test suite for Scientific Metric Identity Contracts and Pre-registered Tolerances."""

    def test_registered_metric_contracts(self):
        contracts = ScientificComparisonPolicyCatalog.list_contracts()
        assert len(contracts) >= 6
        contract_ids = [c.metric_id for c in contracts]
        assert "METRIC_CPI_MEAN_RATIO" in contract_ids
        assert "METRIC_CPI_COHORT_RATIO" in contract_ids
        assert "METRIC_INFLATION_MEAN_RATIO" in contract_ids
        assert "METRIC_REGIME_LABEL_PSI" in contract_ids
        assert "METRIC_RETURN_DISTRIBUTION_PSI" in contract_ids
        assert "METRIC_EVENT_COUNT_VERIFICATION" in contract_ids

    def test_tolerance_evaluation_exact_match(self):
        eval_res = ScientificComparisonPolicyCatalog.evaluate(
            metric_id="METRIC_EVENT_COUNT_VERIFICATION",
            claimed_value=57.0,
            reference_value=57.0,
        )
        assert eval_res.classification == ReproductionClassification.EXACT_MATCH
        assert eval_res.absolute_difference == 0.0
        assert eval_res.is_supported is True

    def test_tolerance_evaluation_method_difference_explained(self):
        eval_res = ScientificComparisonPolicyCatalog.evaluate(
            metric_id="METRIC_CPI_MEAN_RATIO",
            claimed_value=1.950,
            reference_value=1.913,
            methodological_note="Discrete 12-hour bar boundary alignment vs dynamic window slicing.",
        )
        assert eval_res.classification == ReproductionClassification.METHOD_DIFFERENCE_EXPLAINED
        assert abs(eval_res.absolute_difference - 0.037) < 0.001
        assert eval_res.is_supported is True

    def test_tolerance_evaluation_mismatch_exceeded(self):
        eval_res = ScientificComparisonPolicyCatalog.evaluate(
            metric_id="METRIC_CPI_MEAN_RATIO",
            claimed_value=1.950,
            reference_value=1.500,  # Diff 0.450 exceeds 0.050 tolerance
        )
        assert eval_res.classification == ReproductionClassification.MISMATCH
        assert eval_res.is_supported is False

    def test_noncomparable_metric_protection(self):
        eval_res = ScientificComparisonPolicyCatalog.evaluate_cross_metric(
            claimed_metric_id="METRIC_REGIME_LABEL_PSI",
            reference_metric_id="METRIC_RETURN_DISTRIBUTION_PSI",
            claimed_value=0.0125,
            reference_value=0.0128,
        )
        assert eval_res.classification == ReproductionClassification.METHODOLOGICALLY_NONCOMPARABLE
        assert eval_res.is_supported is False
        assert "farklı istatistiksel değişkenler" in eval_res.explanation_tr


class TestSprint13IndependentReproductionAndMetricSeparation:
    """Test suite for Independent Reproduction Engine and Metric Separation."""

    def test_walk_forward_psi_separation(self):
        res = IndependentScientificReproductionEngine.reproduce_walk_forward_psi_claim()
        assert res.overall_status in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]

        # Verify Regime PSI metric
        regime_m = [m for m in res.metrics if m.metric_name == "REGIME_LABEL_DISTRIBUTION_PSI"][0]
        assert regime_m.independent_value == 0.0125
        assert regime_m.classification in ["EXACT_MATCH", "REPRODUCED"]

        # Verify Return Decile PSI metric
        return_m = [m for m in res.metrics if m.metric_name == "RETURN_QUANTILE_DISTRIBUTION_PSI"][0]
        assert return_m.independent_value == 0.0128

        # Verify noncomparable cross-metric guard
        cross_m = [m for m in res.metrics if m.metric_name == "CROSS_VARIABLE_IDENTITY_CHECK"][0]
        assert cross_m.classification == "METHODOLOGICALLY_NONCOMPARABLE"

    def test_cpi_metrics_disentanglement(self):
        res = IndependentScientificReproductionEngine.reproduce_cpi_volatility_claim()
        assert res.overall_status in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]
        assert res.source_event_count == 57

        # 1. Event count verification
        cnt_m = [m for m in res.metrics if m.metric_name == "VERIFIED_EVENT_COUNT"][0]
        assert cnt_m.independent_value == 57.0
        assert cnt_m.classification == "EXACT_MATCH"

        # 2. Mean of event-level ratios
        mean_m = [m for m in res.metrics if m.metric_name == "MEAN_OF_EVENT_LEVEL_VOLATILITY_RATIOS"][0]
        assert 1.90 <= mean_m.independent_value <= 1.93
        assert mean_m.classification in ["METHOD_DIFFERENCE_EXPLAINED", "REPRODUCED_WITH_TOLERANCE"]

        # 3. Ratio of cohort mean volatilities
        cohort_m = [m for m in res.metrics if m.metric_name == "RATIO_OF_COHORT_MEAN_VOLATILITIES"][0]
        assert 1.70 <= cohort_m.independent_value <= 1.80

        # 4. Median event ratio
        med_m = [m for m in res.metrics if m.metric_name == "MEDIAN_EVENT_LEVEL_VOLATILITY_RATIO"][0]
        assert 1.70 <= med_m.independent_value <= 1.75

    def test_cpi_event_drilldown_table(self):
        drill = IndependentScientificReproductionEngine.get_cpi_event_drilldown()
        assert drill["status"] == "SUCCESS"
        assert drill["verified_events_count"] == 57
        assert drill["quarantined_events_count"] == 1
        assert len(drill["events"]) == 58

        # Check candidate event isolation
        candidate = [e for e in drill["events"] if e["is_quarantined"] is True][0]
        assert candidate["event_id"] == "EVT-BLS-CPI-20261014-CANDIDATE"
        assert candidate["verification_status"] == "EVENT_QUARANTINED"

        # Check fields of verified event
        first_verified = drill["events"][0]
        assert "volatility_pre_pct" in first_verified
        assert "volatility_post_pct" in first_verified
        assert "event_volatility_ratio" in first_verified
        assert "aligned_candle_dt" in first_verified
        assert "t0_close_price" in first_verified


class TestSprint13RobustnessMatrixCorrection:
    """Test suite for 16-specification robustness grid and disaggregated rates."""

    def test_robustness_grid_cells_and_invalid_resolutions(self):
        matrix = HistoricalRobustnessExplorer.compute_robustness_matrix(
            cohort="US_CPI",
            window_options=[6, 12, 24, 48],
            interval_options=["1h", "4h"],
            estimator_options=["CLOSE_TO_CLOSE", "PARKINSON_HIGH_LOW"],
        )
        assert len(matrix.cells) == 16

        # Check that 2 cells with window=6h and interval=4h are invalid
        invalid_cells = [c for c in matrix.cells if c.is_valid_specification is False]
        assert len(invalid_cells) == 2
        for cell in invalid_cells:
            assert cell.validity_status == "TEMPORALLY_INVALID_RESOLUTION"
            assert cell.window_hours == 6
            assert cell.interval == "4h"

        valid_cells = [c for c in matrix.cells if c.is_valid_specification is True]
        assert len(valid_cells) == 14

    def test_disaggregated_support_rates(self):
        matrix = HistoricalRobustnessExplorer.compute_robustness_matrix(cohort="US_CPI")

        # 1. Point Estimate Concordance Rate (100.0% of valid cells show expansion > 1.0)
        assert matrix.point_estimate_direction_concordance == 100.0

        # 2. Unadjusted Statistical Support Rate (12 of 14 valid cells exclude 1.0 = 85.71%)
        assert 85.0 <= matrix.unadjusted_statistical_support_rate <= 86.0
        assert matrix.valid_specifications_count == 14

        # 3. Robustness Coverage Rate (14 valid out of 16 total = 87.5%)
        assert matrix.robustness_coverage_rate == 87.5
        assert matrix.total_specifications_checked == 16


class TestSprint13EvidenceQualityProfile:
    """Test suite for 12-Dimensional Evidence Quality Profile."""

    def test_twelve_dimensions_and_scoring(self):
        rep = EvidenceIntelligenceEngine.generate_intelligence_report()
        profile = rep.evidence_quality_profile
        assert profile is not None
        assert len(profile.dimensions) == 12

        # Verify composite quality index and overall classification
        assert profile.composite_quality_index == 8.48
        assert profile.overall_classification == "MODERATE_DESCRIPTIVE_EVIDENCE"

        # Check dimension IDs
        dim_ids = [d.dimension_id for d in profile.dimensions]
        assert "DIM-01-SOURCE-PROVENANCE" in dim_ids
        assert "DIM-02-DATASET-INTEGRITY" in dim_ids
        assert "DIM-04-METHOD-REPRODUCIBILITY" in dim_ids
        assert "DIM-07-ROBUSTNESS-ACROSS-SPECS" in dim_ids
        assert "DIM-09-MULTIPLE-TESTING-CONTROL" in dim_ids

        # Ensure all scores are bounded
        for dim in profile.dimensions:
            assert 0.0 <= dim.score_out_of_10 <= 10.0
            assert len(dim.findings_tr) > 0
            assert len(dim.limitations_tr) > 0

    def test_scientific_limitations_catalog(self):
        rep = EvidenceIntelligenceEngine.generate_intelligence_report()
        assert len(rep.limitations) == 4
        lim_ids = [l.limitation_id for l in rep.limitations]
        assert "LIM-001-ASSET-SCOPE" in lim_ids
        assert "LIM-002-LATENCY-EXECUTION" in lim_ids
        assert "LIM-003-REGIME-NONSTATIONARITY" in lim_ids
        assert "LIM-004-SAMPLE-SIZE-MACRO" in lim_ids


class TestSprint13InteractiveSpecificationCurves:
    """Test suite for Specification Curve Generation, Sorting, Drilldown and Comparison."""

    def test_specification_curve_generation_and_sorting(self):
        curve_default = InteractiveSpecificationCurveStudio.get_specification_curve(
            cohort="US_CPI", sort_by="effect_size"
        )
        assert curve_default.total_points == 16
        assert curve_default.valid_points_count == 14
        assert curve_default.invalid_points_count == 2
        assert len(curve_default.points) == 16

        # Check sorting by effect_size (valid points descending by point_estimate_ratio)
        valid_effects = [p.point_estimate_ratio for p in curve_default.points if p.is_valid_specification]
        assert valid_effects == sorted(valid_effects, reverse=True)

        # Check sorting by window
        curve_window = InteractiveSpecificationCurveStudio.get_specification_curve(
            cohort="US_CPI", sort_by="window"
        )
        windows = [p.window_hours for p in curve_window.points]
        assert windows == sorted(windows)

    def test_specification_drilldown(self):
        curve = InteractiveSpecificationCurveStudio.get_specification_curve(cohort="US_CPI")
        valid_point = [p for p in curve.points if p.is_valid_specification][0]
        drill_valid = InteractiveSpecificationCurveStudio.get_specification_drilldown(valid_point.point_id)
        assert drill_valid.is_valid is True
        assert drill_valid.confidence_interval_95[0] > 0.0

        invalid_point = [p for p in curve.points if not p.is_valid_specification][0]
        drill_invalid = InteractiveSpecificationCurveStudio.get_specification_drilldown(invalid_point.point_id)
        assert drill_invalid.is_valid is False
        assert drill_invalid.validity_status == "TEMPORALLY_INVALID_RESOLUTION"

    def test_specification_side_by_side_comparison(self):
        curve = InteractiveSpecificationCurveStudio.get_specification_curve(cohort="US_CPI")
        p1 = curve.points[0].point_id
        p2 = curve.points[1].point_id
        comp = InteractiveSpecificationCurveStudio.compare_specifications([p1, p2])
        assert len(comp.specifications) == 2
        assert len(comp.parameter_differences) > 0
        assert comp.comparative_synthesis_tr != ""


class TestSprint13DistributionLabV2:
    """Test suite for Historical Distribution Lab V2 (Binning, Q-Q, KDE, and Range Guard)."""

    def test_binning_methods(self):
        # Freedman-Diaconis
        res_fd = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", param_a="2022", param_b="2024", bin_method="freedman_diaconis"
        )
        assert res_fd["status"] == "success"
        r_fd = res_fd["result"]
        assert r_fd["bin_method_used"] == "freedman_diaconis"

        # Sturges
        res_sturges = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", param_a="2022", param_b="2024", bin_method="sturges"
        )
        assert res_sturges["status"] == "success"
        r_st = res_sturges["result"]
        assert r_st["bin_method_used"] == "sturges"

    def test_qq_plots_and_kde_overlays(self):
        res = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", param_a="2022", param_b="2024"
        )
        assert res["status"] == "success"
        r = res["result"]

        # Q-Q Plot validation
        assert "qq_plot_a" in r and "qq_plot_b" in r
        assert "points" in r["qq_plot_a"]
        assert len(r["qq_plot_a"]["points"]) == 50
        assert "theoretical" in r["qq_plot_a"]["points"][0]
        assert "sample" in r["qq_plot_a"]["points"][0]

        # KDE validation
        assert "kde_a" in r and "kde_b" in r
        assert len(r["kde_a"]["grid_x"]) == 60
        assert len(r["kde_a"]["density_y"]) == 60
        assert r["kde_a"]["bandwidth"] > 0.0
        assert r["kde_a"]["rule"] == "SILVERMAN_RULE_OF_THUMB"

    def test_unverified_year_range_guard(self):
        # Requesting year 2018 (prior to verified 2022 dataset) must return structured error
        res_2018 = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", param_a="2018", param_b="2022"
        )
        assert res_2018["status"] == "DATA_RANGE_UNAVAILABLE"
        assert res_2018["error_code"] == 404
        assert "2018" in res_2018["error_tr"]
        assert res_2018["verified_range"] == [2022, 2026]

        # Requesting year 2028 (future year) must return structured error
        res_2028 = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", param_a="2024", param_b="2028"
        )
        assert res_2028["status"] == "DATA_RANGE_UNAVAILABLE"
        assert res_2028["error_code"] == 404


class TestSprint13ScientificReports17To20:
    """Test suite for Scientific PDF and JSON Research Reports 17 through 20."""

    def test_report_17_scientific_reconciliation(self):
        rep = ResearchReportGenerator.generate_scientific_reconciliation_report()
        assert rep["report_type"] == "SCIENTIFIC_RECONCILIATION"
        assert "total_claims_evaluated" in rep["audit"]
        assert "reports" in rep["audit"]
        pdf = ResearchReportGenerator.export_report_as_pdf(rep)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 10000

    def test_report_18_specification_curve(self):
        rep = ResearchReportGenerator.generate_specification_curve_report(cohort="US_CPI")
        assert rep["report_type"] == "SPECIFICATION_CURVE"
        assert rep["curve"]["total_points"] == 16
        pdf = ResearchReportGenerator.export_report_as_pdf(rep)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 10000

    def test_report_19_evidence_quality_profile(self):
        rep = ResearchReportGenerator.generate_evidence_quality_profile_report()
        assert rep["report_type"] == "EVIDENCE_QUALITY_PROFILE"
        assert len(rep["intelligence"]["evidence_quality_profile"]["dimensions"]) == 12
        pdf = ResearchReportGenerator.export_report_as_pdf(rep)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 10000

    def test_report_20_event_drilldown(self):
        rep = ResearchReportGenerator.generate_event_drilldown_report()
        assert rep["report_type"] == "EVENT_DRILLDOWN"
        assert rep["drilldown"]["verified_events_count"] == 57
        pdf = ResearchReportGenerator.export_report_as_pdf(rep)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 10000
