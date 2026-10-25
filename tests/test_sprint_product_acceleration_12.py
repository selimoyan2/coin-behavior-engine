"""
Automated Test Suite for Sprint 12: Visual Research Builder, Independent Scientific Reproduction,
Evidence Intelligence, Historical Distribution Analytics & Portable Research Experiments.
"""

from dataclasses import asdict
import json
from pathlib import Path
import pytest
from coin_behavior_engine.product.independent_reproduction import (
    IndependentScientificReproductionEngine,
)
from coin_behavior_engine.product.distribution_lab import (
    HistoricalDistributionLabEngine,
)
from coin_behavior_engine.product.robustness_explorer import (
    HistoricalRobustnessExplorer,
)
from coin_behavior_engine.product.visual_research_builder import (
    VisualResearchBuilderEngine,
)
from coin_behavior_engine.product.evidence_intelligence import (
    EvidenceIntelligenceEngine,
)
from coin_behavior_engine.product.experiment_packages import (
    ExperimentPackageManager,
)
from coin_behavior_engine.product.notebook_export import (
    ResearchNotebookExporter,
)
from coin_behavior_engine.product.research_reports import (
    ResearchReportGenerator,
)


class TestSprint12IndependentReproduction:
    """Test suite for Independent Scientific Reproduction Engine."""

    def test_reference_math_routines(self):
        prices = [100.0, 102.0, 101.0, 105.0, 104.0]
        vol = IndependentScientificReproductionEngine.reference_realized_volatility(prices)
        assert vol > 0.0

        ci = IndependentScientificReproductionEngine.reference_bootstrap_ci([1.5, 1.6, 1.4, 1.7, 1.55], num_resamples=100)
        assert ci["ci_lower"] <= ci["point_estimate"] <= ci["ci_upper"]
        assert ci["null_effect_included"] is False

        d = IndependentScientificReproductionEngine.reference_cohens_d([1.0, 1.1, 1.2], [2.0, 2.1, 2.2])
        assert d > 1.0

        delta = IndependentScientificReproductionEngine.reference_cliffs_delta([1.0, 1.1, 1.2], [2.0, 2.1, 2.2])
        assert delta == 1.0

        psi = IndependentScientificReproductionEngine.reference_psi({"A": 0.5, "B": 0.5}, {"A": 0.51, "B": 0.49})
        assert 0.0 <= psi < 0.01

    def test_cpi_volatility_claim_reproduction(self):
        res = IndependentScientificReproductionEngine.reproduce_cpi_volatility_claim()
        assert res.overall_status in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]
        assert res.source_event_count == 57
        metric_rep = [m for m in res.metrics if m.metric_name == "MEAN_VOLATILITY_SHIFT_RATIO"][0]
        assert abs(metric_rep.independent_value - 1.950) <= 0.05
        assert metric_rep.verdict in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]

    def test_inflation_cohort_claim_reproduction(self):
        res = IndependentScientificReproductionEngine.reproduce_inflation_cohort_claim()
        assert res.overall_status in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]
        assert res.source_event_count == 102
        metric_rep = [m for m in res.metrics if m.metric_name == "MEAN_VOLATILITY_SHIFT_RATIO"][0]
        assert abs(metric_rep.independent_value - 1.817) <= 0.05
        assert metric_rep.verdict in ["REPRODUCED", "REPRODUCED_WITH_TOLERANCE"]

    def test_walk_forward_psi_claim_reproduction(self):
        res = IndependentScientificReproductionEngine.reproduce_walk_forward_psi_claim()
        assert res.overall_status == "REPRODUCED"
        metric_rep = [m for m in res.metrics if m.metric_name == "POPULATION_STABILITY_INDEX_TRAIN_TO_TEST"][0]
        assert metric_rep.independent_value < 0.02
        assert abs(metric_rep.independent_value - 0.0125) <= 0.005
        assert metric_rep.verdict == "REPRODUCED"


class TestSprint12DistributionLab:
    """Test suite for Historical Distribution Laboratory."""

    def test_distribution_moments_and_quantiles(self):
        data = [0.1, -0.2, 0.5, -0.4, 0.3, 0.0, 0.15, -0.05, 0.8, -0.6]
        metrics = HistoricalDistributionLabEngine._compute_distribution_metrics(data)
        assert metrics.sample_count == 10
        assert metrics.min_value == -0.6
        assert metrics.max_value == 0.8
        assert metrics.p05 < metrics.p50 < metrics.p95
        assert metrics.iqr > 0.0

    def test_distribution_comparison_year_vs_year(self):
        res = HistoricalDistributionLabEngine.compare_distributions(
            mode="YEAR_VS_YEAR", metric="RETURNS_PCT", param_a="2022", param_b="2024", interval="1h"
        )
        assert res["status"] == "success"
        r = res["result"]
        assert r["group_a_label"] == "2022 Yılı"
        assert r["group_b_label"] == "2024 Yılı"
        assert len(r["histogram_bins"]) == 31
        assert len(r["ecdf_a"]) == 50
        assert r["ks_statistic"] > 0.0
        assert r["wasserstein_distance"] > 0.0

    def test_distribution_comparison_pre_vs_post_event(self):
        res = HistoricalDistributionLabEngine.compare_distributions(
            mode="PRE_VS_POST_EVENT", metric="RETURNS_PCT", param_a="US_CPI", param_b="12", interval="1h"
        )
        assert res["status"] == "success"
        assert "US_CPI Öncesi" in res["result"]["group_a_label"]
        assert "US_CPI Sonrası" in res["result"]["group_b_label"]


class TestSprint12RobustnessExplorer:
    """Test suite for Historical Robustness & Sensitivity Explorer."""

    def test_robustness_matrix_computation(self):
        res = HistoricalRobustnessExplorer.compute_robustness_matrix(
            cohort="US_CPI",
            window_options=[6, 12],
            interval_options=["1h"],
            estimator_options=["CLOSE_TO_CLOSE", "PARKINSON_HIGH_LOW"]
        )
        assert len(res.cells) == 4
        assert res.robustness_status in ["ROBUST", "MODERATELY_SENSITIVE"]
        assert res.min_ratio > 1.0
        assert res.max_ratio >= res.min_ratio
        for cell in res.cells:
            assert cell.is_expansion_statistically_significant is True
            assert cell.ci_lower_95 > 1.0


class TestSprint12VisualResearchBuilder:
    """Test suite for Visual Research Builder V2."""

    def test_builder_templates_and_options(self):
        templates = VisualResearchBuilderEngine.get_builder_templates()
        assert len(templates) == 5
        assert templates[0]["template_id"].startswith("VRB-TMPL-01")

        options = VisualResearchBuilderEngine.get_builder_options()
        assert "BTCUSDT" in [d["asset"] for d in options["datasets"]]
        # Verify ETH and SOL are labeled SOURCE_NOT_AVAILABLE
        eth = [d for d in options["datasets"] if d["asset"] == "ETHUSDT"][0]
        assert eth["status"] == "SOURCE_NOT_AVAILABLE"

    def test_builder_preview_and_execution_bounds(self):
        cfg = {
            "hypothesis_id": "TEST-HYP",
            "title_tr": "Test Hipotezi",
            "event_cohort": "US_CPI",
            "target_asset": "BTCUSDT",
            "interval": "1h",
            "pre_event_window_hours": 12,
            "post_event_window_hours": 12,
            "volatility_estimator": "CLOSE_TO_CLOSE"
        }
        prev = VisualResearchBuilderEngine.generate_research_preview(cfg)
        assert prev["status"] == "PREVIEW_READY"
        assert prev["governance_verification"]["synthetic_price_fabrication"] == "PROHIBITED_VERIFIED"

        res = VisualResearchBuilderEngine.execute_builder_research(cfg)
        assert res["status"] == "COMPLETED"
        stats = res["statistical_results"]
        assert stats["point_estimate_ratio"] > 1.5
        assert stats["is_statistically_significant"] is True
        assert res["evidence_classification"] == "OUT_OF_SAMPLE_EFFECT_REPLICATED"


class TestSprint12EvidenceIntelligence:
    """Test suite for Evidence Intelligence Engine."""

    def test_evidence_report_aggregation(self):
        rep = EvidenceIntelligenceEngine.generate_intelligence_report()
        assert rep.evidence_health_score == 100
        assert rep.overall_reproducibility_rate_pct == 100.0
        assert rep.reproduced_findings_count >= 3
        assert len(rep.limitations) == 4
        assert rep.canonical_model_version == "CBE-0.7.0 (FROZEN)"


class TestSprint12ExperimentPackages:
    """Test suite for Portable Experiment Packages (.cbe-hyp.json)."""

    def test_package_creation_validation_and_tampering(self, tmp_path):
        pkg = ExperimentPackageManager.create_package(
            hypothesis_id="HYP-UNIT-TEST",
            title_tr="Test Hipotez Paketi",
            description_tr="Açıklama",
            event_cohort="US_CPI",
            target_asset="BTCUSDT",
            window_hours=12
        )
        pkg_file = tmp_path / "test.cbe-hyp.json"
        ExperimentPackageManager.export_to_file(pkg, pkg_file)

        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        val_ok = ExperimentPackageManager.validate_package_dict(data)
        assert val_ok["is_valid"] is True
        assert val_ok["status"] == "VALID"

        # Tampering check
        data["results"]["volatility_expansion_ratio"] = 9.99
        val_tampered = ExperimentPackageManager.validate_package_dict(data)
        assert val_tampered["is_valid"] is False
        assert val_tampered["status"] == "TAMPERED"

        # Code execution prevention
        data["specification"]["description_tr"] = "<script>alert('hack')</script>"
        val_unsafe = ExperimentPackageManager.validate_package_dict(data)
        assert val_unsafe["is_valid"] is False
        assert val_unsafe["status"] == "UNSAFE_CONTENT"


class TestSprint12NotebookExport:
    """Test suite for Reproducible Research Notebook Export (.ipynb)."""

    def test_offline_notebook_generation(self, tmp_path):
        nb_file = tmp_path / "research.ipynb"
        ResearchNotebookExporter.export_notebook_to_file(nb_file, hypothesis_id="HYP-NB-01", cohort="US_CPI")
        data = json.loads(nb_file.read_text(encoding="utf-8"))

        assert data["nbformat"] == 4
        assert len(data["cells"]) == 6
        code_cells = [c for c in data["cells"] if c["cell_type"] == "code"]
        assert len(code_cells) == 5
        # Verify offline imports and data paths
        all_code = "".join(["".join(c["source"]) for c in code_cells])
        assert "import matplotlib.pyplot as plt" in all_code
        assert "historical_macro_events_11_23.parquet" in all_code
        assert "realized_vol" in all_code


class TestSprint12ScientificReportingV4:
    """Test suite for Scientific Reporting V4 (Reports 13-16)."""

    def test_four_new_pdf_reports(self):
        # 13: Independent Reproduction Report
        r13 = ResearchReportGenerator.generate_independent_reproduction_report()
        pdf13 = ResearchReportGenerator.export_report_as_pdf(r13)
        assert pdf13.startswith(b"%PDF")
        assert len(pdf13) > 10000

        # 14: Historical Distribution Report
        r14 = ResearchReportGenerator.generate_historical_distribution_report(mode="YEAR_VS_YEAR", param_a="2022", param_b="2024")
        pdf14 = ResearchReportGenerator.export_report_as_pdf(r14)
        assert pdf14.startswith(b"%PDF")
        assert len(pdf14) > 10000

        # 15: Robustness Sensitivity Report
        r15 = ResearchReportGenerator.generate_robustness_sensitivity_report(cohort="US_CPI")
        pdf15 = ResearchReportGenerator.export_report_as_pdf(r15)
        assert pdf15.startswith(b"%PDF")
        assert len(pdf15) > 10000

        # 16: Portable Experiment Report
        r16 = ResearchReportGenerator.generate_portable_experiment_report(hypothesis_id="HYP-CPI-01")
        pdf16 = ResearchReportGenerator.export_report_as_pdf(r16)
        assert pdf16.startswith(b"%PDF")
        assert len(pdf16) > 10000
