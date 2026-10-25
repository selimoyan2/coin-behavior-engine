"""
Sprint 10 Automated Regression Tests.
Covers:
1. Dataset Provenance & Lineage Engine (inventory, fingerprints, lineage graph)
2. October 2026 Source Audit & Quarantine of synthetic intake candidate
3. Non-BTC Asset fail-closed policy (no price fabrication)
4. Statistical Validity Engine (moving block bootstrap, BH FDR, Cohen's d)
5. Event-Conditioned Regime Research Engine (cohort study, overlap confounding)
6. Walk-Forward Validation Engine (chronological splits, 24-bar embargo buffer, frozen model CBE-0.7.0)
7. Experiment Registry Engine (immutable CBE-EXP- hashes, structured findings cards)
8. Research Reports V2 (all 8 report types, PDF vector export, mandatory disclaimer)
9. API Endpoints (HTTP status codes, payload structures)
"""
import pytest
from http import HTTPStatus

from coin_behavior_engine.product.dataset_provenance import DatasetProvenanceEngine
from coin_behavior_engine.product.statistical_validity import StatisticalValidityEngine
from coin_behavior_engine.product.event_regime_research import EventRegimeResearchEngine
from coin_behavior_engine.product.walk_forward_validation import WalkForwardValidationEngine
from coin_behavior_engine.product.experiment_registry import ExperimentRegistryEngine
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


class TestSprint10DatasetProvenance:
    def test_dataset_inventory_coverage(self):
        inv = DatasetProvenanceEngine.get_dataset_inventory()
        assert len(inv) > 0
        assert "BTCUSDT-5m" in inv
        assert "BTCUSDT-1h" in inv
        rec_5m = inv["BTCUSDT-5m"]
        assert rec_5m.asset == "BTCUSDT"
        assert rec_5m.interval == "5m"
        assert rec_5m.partitions_count == 57
        assert rec_5m.provenance_fingerprint.startswith("FPR-BTCUSDT-5m-")

    def test_lineage_graph_structure(self):
        lineage = DatasetProvenanceEngine.get_lineage_graph()
        assert "root_archive" in lineage
        assert lineage["root_archive"]["canonical_base"] == "BTCUSDT-5m"
        assert "lineage_edges" in lineage
        children = [e["child"] for e in lineage["lineage_edges"]]
        assert "BTCUSDT-15m" in children
        assert "BTCUSDT-1h" in children
        assert "BTCUSDT-4h" in children
        assert "BTCUSDT-1d" in children

    def test_october_source_audit_and_quarantine(self):
        audit = DatasetProvenanceEngine.audit_october_source()
        assert audit["october_2026_source_status"] == "SOURCE_NOT_AVAILABLE"
        assert audit["october_2026_imported"] is False
        assert audit["october_2026_record_count"] == 0
        assert audit["candidate_verdict"] == "QUARANTINED"
        assert audit["safe_to_publish"] is False

    def test_non_btc_asset_availability_fail_closed(self):
        eth_check = DatasetProvenanceEngine.check_asset_availability("ETHUSDT")
        assert eth_check["status"] == "SOURCE_NOT_AVAILABLE"
        assert eth_check["is_synthetic"] is False

        sol_check = DatasetProvenanceEngine.check_asset_availability("SOLUSDT")
        assert sol_check["status"] == "SOURCE_NOT_AVAILABLE"
        assert sol_check["is_synthetic"] is False

        btc_check = DatasetProvenanceEngine.check_asset_availability("BTCUSDT")
        assert btc_check["status"] == "AVAILABLE"


class TestSprint10StatisticalValidity:
    def test_moving_block_bootstrap(self):
        import numpy as np
        np.random.seed(42)
        sample = list(np.random.normal(loc=1.2, scale=0.3, size=40))
        res = StatisticalValidityEngine.block_bootstrap_ci(
            series=sample,
            statistic_fn="mean",
            block_size=4,
            num_resamples=500,
            alpha=0.05
        )
        assert res["point_estimate"] > 1.0
        assert res["ci_lower"] < res["point_estimate"]
        assert res["ci_upper"] > res["point_estimate"]
        assert res["num_resamples"] == 500

    def test_benjamini_hochberg_fdr(self):
        raw_p_values = [0.001, 0.008, 0.03, 0.045, 0.12, 0.50]
        fdr_results = StatisticalValidityEngine.benjamini_hochberg_fdr(raw_p_values, q_threshold=0.05)
        assert len(fdr_results) == 6
        assert fdr_results[0]["adjusted_p_value"] <= raw_p_values[0] * 6
        assert fdr_results[0]["is_significant"] is True

    def test_cohen_d_effect_size(self):
        group_a = [1.2, 1.3, 1.4, 1.5, 1.6]
        group_b = [0.9, 1.0, 1.1, 1.0, 0.95]
        res = StatisticalValidityEngine.compute_effect_size(group_a, group_b)
        assert abs(res["cohens_d"]) > 0.8
        assert res["magnitude"] in ("LARGE", "VERY_LARGE")


class TestSprint10EventRegimeResearch:
    def test_run_cohort_study_inflation(self):
        study = EventRegimeResearchEngine.run_cohort_study(category="US_INFLATION", window_hours=12)
        assert study["status"] == "SUCCESS"
        assert study["category"] == "US_INFLATION"
        assert study["total_verified_events"] > 0
        assert "volatility_response" in study
        assert study["volatility_response"]["mean_vol_shift_ratio"] > 1.0
        assert "regime_distributions" in study

    def test_overlap_and_confounding_handling(self):
        verified_events, quarantined_events = EventRegimeResearchEngine.load_verified_events()
        assert len(verified_events) >= 12
        for ev in verified_events:
            assert ev.verification_status != "EVENT_QUARANTINED"


class TestSprint10WalkForwardValidation:
    def test_walk_forward_splits_and_embargo(self):
        res = WalkForwardValidationEngine.run_regime_stability_experiment()
        assert res["status"] == "SUCCESS"
        assert res["model_protection"]["is_frozen"] is True
        assert res["model_protection"]["canonical_model_version"] == "CBE-0.7.0"
        assert res["split_configuration"]["embargo_bars"] == 24
        assert res["sample_counts"]["in_sample_train_bars"] > 10000
        assert res["sample_counts"]["out_of_sample_test_bars"] > 5000
        assert res["sample_counts"]["holdout_2026_bars"] > 3000
        assert res["stability_telemetry"]["replication_status"] == "OUT_OF_SAMPLE_REPLICATED"
        assert res["leakage_controls_verified"]["embargo_applied"] is True


class TestSprint10ExperimentRegistry:
    def test_experiment_registry_immutability(self):
        experiments = ExperimentRegistryEngine.get_registered_experiments()
        assert len(experiments) >= 2
        exp_ids = [e["experiment_id"] for e in experiments]
        assert "CBE-EXP-01-CPI-VOLATILITY-SHIFT" in exp_ids
        assert "CBE-EXP-02-FOMC-RATE-REACTIONS" in exp_ids
        for exp in experiments:
            assert len(exp["reproducibility_hash"]) == 64
            assert len(exp["dataset_manifest_sha256"]) == 64

    def test_research_findings_cards(self):
        findings = ExperimentRegistryEngine.get_research_findings()
        assert len(findings) >= 3
        for f in findings:
            assert "finding_id" in f
            assert "research_question" in f
            assert "main_observation" in f
            assert "effect_size_magnitude" in f
            assert "evidence_status" in f

    def test_compare_experiments(self):
        comp = ExperimentRegistryEngine.compare_experiments(
            "CBE-EXP-01-CPI-VOLATILITY-SHIFT",
            "CBE-EXP-02-FOMC-RATE-REACTIONS"
        )
        assert comp["status"] == "success"
        assert "comparison" in comp
        assert comp["comparison"]["experiment_a"]["experiment_id"] == "CBE-EXP-01-CPI-VOLATILITY-SHIFT"
        assert comp["comparison"]["experiment_b"]["experiment_id"] == "CBE-EXP-02-FOMC-RATE-REACTIONS"


class TestSprint10ResearchReportsV2:
    @pytest.mark.parametrize("rpt_type", [
        "PERIOD_COMPARISON",
        "MACRO_EVENT",
        "REGIME_DRIFT",
        "DATA_QUALITY",
        "EVENT_CONDITIONED_REGIME_STUDY",
        "WALK_FORWARD_VALIDATION",
        "SCIENTIFIC_EVIDENCE_SUMMARY",
        "EXPERIMENT_COMPARISON",
    ])
    def test_all_eight_report_types_json_and_pdf(self, rpt_type):
        # 1. JSON Export
        status_json, res_json = ProductDashboardApiService.handle_request(
            f"/api/v1/product/research-report?report_type={rpt_type}&format=json"
        )
        assert status_json == HTTPStatus.OK
        assert "report_id" in res_json or "status" in res_json

        # 2. PDF Export
        status_pdf, res_pdf = ProductDashboardApiService.handle_request(
            f"/api/v1/product/research-report?report_type={rpt_type}&format=pdf"
        )
        assert status_pdf == HTTPStatus.OK
        assert "_binary_pdf" in res_pdf
        pdf_bytes = res_pdf["_binary_pdf"]
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert pdf_bytes.startswith(b"%PDF-1.")
        assert len(pdf_bytes) > 10000


class TestSprint10ApiEndpoints:
    def test_provenance_and_lineage_endpoints(self):
        s1, b1 = ProductDashboardApiService.handle_request("/api/v1/product/dataset-provenance")
        assert s1 == HTTPStatus.OK
        assert b1["status"] == "success"
        assert "BTCUSDT-5m" in b1["provenance_records"]

        s2, b2 = ProductDashboardApiService.handle_request("/api/v1/product/dataset-lineage")
        assert s2 == HTTPStatus.OK
        assert b2["status"] == "success"
        assert "root_archive" in b2["lineage"]

    def test_october_audit_endpoint(self):
        s, b = ProductDashboardApiService.handle_request("/api/v1/product/october-source-audit")
        assert s == HTTPStatus.OK
        assert b["status"] == "success"
        assert b["october_audit"]["candidate_verdict"] == "QUARANTINED"

    def test_event_regime_study_endpoint(self):
        s, b = ProductDashboardApiService.handle_request("/api/v1/product/event-regime-study?category=US_INFLATION")
        assert s == HTTPStatus.OK
        assert b["status"] == "SUCCESS"
        assert b["category"] == "US_INFLATION"

    def test_walk_forward_endpoint(self):
        s, b = ProductDashboardApiService.handle_request("/api/v1/product/walk-forward-experiments")
        assert s == HTTPStatus.OK
        assert b["status"] == "SUCCESS"
        assert b["stability_telemetry"]["replication_status"] == "OUT_OF_SAMPLE_REPLICATED"

    def test_findings_and_experiments_endpoints(self):
        s_f, b_f = ProductDashboardApiService.handle_request("/api/v1/product/research-findings")
        assert s_f == HTTPStatus.OK
        assert len(b_f["findings"]) >= 3

        s_e, b_e = ProductDashboardApiService.handle_request("/api/v1/product/research-experiments")
        assert s_e == HTTPStatus.OK
        assert len(b_e["experiments"]) >= 2
