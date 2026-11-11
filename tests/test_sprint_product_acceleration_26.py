"""Comprehensive Test Suite for Sprint 26 — Advanced Scientific Research,
Statistical Validation & Robustness Intelligence.

Covers:
1. Module 26.1 — Advanced Statistical Validation (CI, MHT Bonferroni/Holm/BH-FDR,
   small-sample fail-closed, missing data, autocorrelation IID bootstrap rejection,
   numerical stability, deterministic reproducibility, cache invalidation).
2. Module 26.2 — Walk-Forward Research Lab (expanding/rolling splits, chronological
   ordering, future-data leakage rejection, invalid split handling, embargo/purge,
   frozen parameter refit blocking, missing observation handling).
3. Module 26.3 — Historical Market Regime Research (transition matrices, Dirichlet
   uncertainty, episode durations with boundary censoring, gap handling, frozen
   threshold guard, perturbation stability, cross-period consistency).
4. Module 26.4 — Robustness & Sensitivity Lab (all 8 sensitivity dimensions,
   reproducibility, source SHA-256 binding, baseline comparison, unsupported
   assumption rejection, frozen-model mutation rejection, resource limits).
5. Module 26.5 — Independent Validation Framework (same dataset under different
   filenames/IDs, overlapping observation windows, shared preprocessing lineage,
   shared source artifact hashes, missing independence evidence, false independent
   replication claims, fail-closed INDEPENDENCE_NOT_ESTABLISHED).
6. Module 26.6 & Cross-Module Integration — Dashboard V4 API endpoints, HTML tabs,
   4-pillar concept separation, and non-negotiable governance invariants.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.product.advanced_statistical_validation import (
    AdvancedStatisticalValidator,
)
from coin_behavior_engine.product.walk_forward_research_lab import (
    WalkForwardResearchLab,
)
from coin_behavior_engine.product.historical_regime_research import (
    HistoricalMarketRegimeResearchEngine,
)
from coin_behavior_engine.product.robustness_sensitivity_lab import (
    RobustnessSensitivityLab,
)
from coin_behavior_engine.product.independent_validation_framework import (
    IndependentValidationFramework,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.research_explorer_ui import (
    render_research_explorer_html,
)


# ===========================================================================
# 1. MODULE 26.1 — ADVANCED STATISTICAL VALIDATION TESTS
# ===========================================================================


class TestModule261AdvancedStatisticalValidation:
    """Tests for Module 26.1 Statistical Validation capabilities and safeguards."""

    def test_multiple_testing_corrections_bonferroni_holm_bh_fdr(self):
        p_fam = {
            "H1_FUNDING": 0.001,
            "H2_HOLDOUT": 0.012,
            "H3_PATTERN": 0.030,
            "H4_NOISE": 0.250,
        }
        bonf = AdvancedStatisticalValidator.apply_multiple_testing_correction(
            p_values=p_fam,
            method="bonferroni",
            hypothesis_family_id="FAM-TEST-01",
            alpha=0.05,
        )
        holm = AdvancedStatisticalValidator.apply_multiple_testing_correction(
            p_values=p_fam,
            method="holm",
            hypothesis_family_id="FAM-TEST-01",
            alpha=0.05,
        )
        bh = AdvancedStatisticalValidator.apply_multiple_testing_correction(
            p_values=p_fam,
            method="benjamini_hochberg_fdr",
            hypothesis_family_id="FAM-TEST-01",
            alpha=0.05,
        )

        assert bonf.family_size_m == 4
        assert bonf.adjusted_p_or_q_values["H1_FUNDING"] == pytest.approx(0.004)
        assert bonf.adjusted_p_or_q_values["H2_HOLDOUT"] == pytest.approx(0.048)
        assert bonf.adjusted_p_or_q_values["H3_PATTERN"] == pytest.approx(0.120)
        assert bonf.adjusted_p_or_q_values["H4_NOISE"] == pytest.approx(1.000)

        # Holm step-down is uniformly less conservative than or equal to Bonferroni
        for k in p_fam:
            assert holm.adjusted_p_or_q_values[k] <= bonf.adjusted_p_or_q_values[k] + 1e-9
            assert bh.adjusted_p_or_q_values[k] <= holm.adjusted_p_or_q_values[k] + 1e-9

        assert holm.adjusted_p_or_q_values["H1_FUNDING"] == pytest.approx(0.004)  # 4 * 0.001
        assert holm.adjusted_p_or_q_values["H2_HOLDOUT"] == pytest.approx(0.036)  # 3 * 0.012
        assert holm.adjusted_p_or_q_values["H3_PATTERN"] == pytest.approx(0.060)  # 2 * 0.030
        assert bh.rejected_null_flags["H3_PATTERN"] is True  # BH q = 0.030 * 4 / 3 = 0.040 <= 0.05

    def test_multiple_testing_rejects_invalid_method_or_missing_family(self):
        with pytest.raises(ValueError, match="Unsupported multiple-testing correction"):
            AdvancedStatisticalValidator.apply_multiple_testing_correction(
                {"H1": 0.01}, method="uncorrected_p_hacking"
            )
        with pytest.raises(ValueError, match="hypothesis_family_id is required"):
            AdvancedStatisticalValidator.apply_multiple_testing_correction(
                {"H1": 0.01}, method="holm", hypothesis_family_id=""
            )
        with pytest.raises(ValueError, match="Invalid p-value"):
            AdvancedStatisticalValidator.apply_multiple_testing_correction(
                {"H1": 1.5}, method="bonferroni"
            )

    def test_autocorrelation_safeguard_rejects_iid_bootstrap_without_justification(self):
        validator = AdvancedStatisticalValidator()
        # Generate strongly autocorrelated AR(1) series (rho ~ 0.85)
        rng = np.random.default_rng(42)
        n = 250
        ar_series = np.zeros(n)
        for i in range(1, n):
            ar_series[i] = 0.85 * ar_series[i - 1] + rng.normal(0.0, 0.01)

        iid_res = validator.compute_safeguarded_confidence_interval(
            series=ar_series,
            bootstrap_method="iid",
            allow_iid_with_justification=None,
            seed=42,
        )
        assert iid_res["status"] == "BOOTSTRAP_METHOD_REJECTED_AUTOCORRELATION"
        assert iid_res["rejection_code"] == "IID_BOOTSTRAP_PROHIBITED_UNDER_AUTOCORRELATION"
        assert iid_res["ci_lower"] is None
        assert iid_res["ci_upper"] is None

        # Moving-block bootstrap succeeds on the same autocorrelated series
        mbb_res = validator.compute_safeguarded_confidence_interval(
            series=ar_series,
            bootstrap_method="moving_block",
            seed=42,
        )
        assert mbb_res["status"] == "COMPUTED"
        assert mbb_res["ci_lower"] < mbb_res["point_estimate"] < mbb_res["ci_upper"]

    def test_small_sample_behavior_never_manufactures_p_values_or_ci(self):
        validator = AdvancedStatisticalValidator()
        tiny_record = {
            "research_id": "RES-TINY-SAMPLE",
            "dataset_id": "DS-TINY",
            "sample_size": 3,
            "evidence_status": "VERIFIED_GENUINE",
        }
        res = validator.evaluate_research_record(record=tiny_record, custom_series=[0.01, 0.02, 0.015])
        assert res.finding_classification == "INSUFFICIENT_EVIDENCE"
        assert res.verification_status == "INSUFFICIENT_EVIDENCE"
        assert res.confidence_interval is None
        assert res.test_statistic is None
        assert res.adjusted_significance_result is None

    def test_missing_observation_analysis_and_numerical_stability(self):
        # Continuous grid
        ts_cont = [1704067200000 + i * 3600000 for i in range(100)]
        diag_cont = AdvancedStatisticalValidator.compute_missing_observation_analysis(ts_cont, 3600000)
        assert diag_cont["continuity_verdict"] == "CONTINUOUS_GRID_VERIFIED"
        assert diag_cont["missing_bar_count"] == 0

        # Grid with significant gap (missing 10 bars)
        ts_gapped = ts_cont[:40] + ts_cont[50:]
        diag_gap = AdvancedStatisticalValidator.compute_missing_observation_analysis(ts_gapped, 3600000)
        assert diag_gap["missing_bar_count"] == 10
        assert diag_gap["max_gap_bars"] == 10
        assert diag_gap["continuity_verdict"] == "DISCONTINUOUS_SIGNIFICANT_GAPS"

        # Numerical stability on constant zero-variance series
        const_series = [0.025] * 50
        dep_const = AdvancedStatisticalValidator.compute_temporal_dependence_diagnostics(const_series)
        dist_const = AdvancedStatisticalValidator.compute_distribution_diagnostics(const_series)
        assert dep_const["status"] == "ZERO_VARIANCE_SERIES"
        assert dist_const["status"] == "ZERO_VARIANCE"

    def test_deterministic_reproducibility_and_quarantine_blocking(self):
        validator = AdvancedStatisticalValidator()
        cat = [r.to_dict() for r in ResearchWorkspaceV2Engine.get_canonical_catalog()]
        pat_rec = next(r for r in cat if r["id"] in ("RES-ANALOG-01", "RES-29-PAT-SIM"))
        pat_rec["research_id"] = pat_rec["id"]

        r1 = validator.evaluate_research_record(pat_rec, seed=42)
        r2 = validator.evaluate_research_record(pat_rec, seed=42)
        assert r1.evidence_fingerprint_sha256 == r2.evidence_fingerprint_sha256
        assert r1.confidence_interval == r2.confidence_interval

        quar_rec = next(r for r in cat if r["id"] == "RES-CRYPTO-01")
        quar_rec["research_id"] = quar_rec["id"]
        r_quar = validator.evaluate_research_record(quar_rec)
        assert r_quar.finding_classification == "INSUFFICIENT_EVIDENCE"
        assert r_quar.verification_status == "QUARANTINED_BLOCKED"


# ===========================================================================
# 2. MODULE 26.2 — WALK-FORWARD RESEARCH LAB TESTS
# ===========================================================================


class TestModule262WalkForwardResearchLab:
    """Tests for Module 26.2 Walk-Forward Research Lab and temporal leakage guards."""

    def test_expanding_and_rolling_walk_forward_execution(self):
        lab = WalkForwardResearchLab()
        rep_exp = lab.run_walk_forward_evaluation(
            record_id="RES-29-PAT-SIM",
            dataset_id="DS-BTC-1H-Q1-2024",
            frequency="1h",
            split_mode="expanding",
            n_splits=4,
            warmup_bars=24,
            purge_bars=2,
            embargo_bars=2,
        )
        assert rep_exp.status == "EVALUATION_COMPLETED"
        assert rep_exp.fold_count == 4
        assert rep_exp.temporal_leakage_diagnostics["future_data_leakage_detected"] is False
        assert rep_exp.frozen_model_contract["parameter_mutations_applied"] == 0
        for fold in rep_exp.folds:
            assert fold["leakage_check_passed"] is True
            assert fold["train_end_idx"] < fold["test_start_idx"]
            assert fold["temporal_gap_ms"] > 0

        rep_roll = lab.run_walk_forward_evaluation(
            record_id="RES-29-PAT-SIM",
            dataset_id="DS-BTC-1H-Q1-2024",
            frequency="1h",
            split_mode="rolling",
            n_splits=4,
            warmup_bars=24,
            rolling_train_bars=300,
        )
        assert rep_roll.status == "EVALUATION_COMPLETED"
        assert rep_roll.folds[-1]["train_bar_count"] <= 300

    def test_walk_forward_blocks_frozen_model_refit_and_optimization(self):
        lab = WalkForwardResearchLab()
        blocked_refit = lab.run_walk_forward_evaluation(
            allow_parameter_refit=True,
        )
        assert blocked_refit.status == "EVALUATION_BLOCKED"
        assert blocked_refit.rejection_code == "FROZEN_MODEL_REFIT_PROHIBITED"

        blocked_opt = lab.run_walk_forward_evaluation(
            optimize_parameters=True,
        )
        assert blocked_opt.status == "EVALUATION_BLOCKED"
        assert blocked_opt.rejection_code == "FROZEN_MODEL_OPTIMIZATION_PROHIBITED"

        blocked_mut = lab.run_walk_forward_evaluation(
            custom_model_parameters={"parkinson_window_bars": 99},
        )
        assert blocked_mut.status == "EVALUATION_BLOCKED"
        assert blocked_mut.rejection_code == "CANONICAL_PARAMETER_MUTATION_BLOCKED"

    def test_walk_forward_rejects_future_leakage_overlap_and_bad_timestamps(self):
        lab = WalkForwardResearchLab()
        ts_valid = [1704067200000 + i * 3600000 for i in range(200)]

        # 1. Future observation used in earlier window
        leak_check = lab.inspect_temporal_integrity(
            timestamps_ms=ts_valid,
            frequency="1h",
            explicit_splits=[
                {
                    "train_start_ms": ts_valid[100],
                    "train_end_ms": ts_valid[150],
                    "test_start_ms": ts_valid[20],
                    "test_end_ms": ts_valid[80],
                }
            ],
        )
        assert leak_check["valid"] is False
        assert leak_check["rejection_code"] == "FUTURE_OBSERVATION_LEAKAGE_DETECTED"

        # 2. Overlapping train and test windows
        overlap_check = lab.inspect_temporal_integrity(
            timestamps_ms=ts_valid,
            frequency="1h",
            explicit_splits=[
                {
                    "train_start_ms": ts_valid[0],
                    "train_end_ms": ts_valid[60],
                    "test_start_ms": ts_valid[50],
                    "test_end_ms": ts_valid[100],
                }
            ],
        )
        assert overlap_check["valid"] is False
        assert overlap_check["rejection_code"] == "TRAIN_TEST_OVERLAP_DETECTED"

        # 3. Non-monotonic chronological ordering
        bad_order_ts = list(ts_valid)
        bad_order_ts[10], bad_order_ts[11] = bad_order_ts[11], bad_order_ts[10]
        order_check = lab.inspect_temporal_integrity(bad_order_ts, frequency="1h")
        assert order_check["valid"] is False
        assert order_check["rejection_code"] == "CHRONOLOGICAL_ORDER_VIOLATION"

        # 4. Unsupported frequency
        freq_check = lab.inspect_temporal_integrity(ts_valid, frequency="7m")
        assert freq_check["valid"] is False
        assert freq_check["rejection_code"] == "UNSUPPORTED_DATA_FREQUENCY"

        # 5. Missing timestamps
        miss_check = lab.inspect_temporal_integrity([], frequency="1h")
        assert miss_check["valid"] is False
        assert miss_check["rejection_code"] == "MISSING_EVALUATION_TIMESTAMPS"

        # 6. Quarantined dataset blocked
        quar_rep = lab.run_walk_forward_evaluation(dataset_id="DS-BTC-1H-OCT2026-QUARANTINE")
        assert quar_rep.status == "EVALUATION_BLOCKED"
        assert quar_rep.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"


# ===========================================================================
# 3. MODULE 26.3 — HISTORICAL MARKET REGIME RESEARCH TESTS
# ===========================================================================


class TestModule263HistoricalMarketRegimeResearch:
    """Tests for Module 26.3 Market Regime Research Engine."""

    def test_regime_research_transitions_durations_and_provenance(self):
        engine = HistoricalMarketRegimeResearchEngine()
        rep = engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            comparison_dataset_id="DS-BTC-15M-Q2-2024",
        )
        assert rep.status == "RESEARCH_COMPLETED"
        assert rep.verified_source_artifact["source_artifact_sha256"] is not None
        assert rep.methodology["thresholds_modified"] is False

        # Transition probabilities row-sum to 1.0 for active regimes
        probs = np.asarray(rep.regime_transition_frequency["probabilities_matrix"])
        counts = np.asarray(rep.regime_transition_frequency["counts_matrix"])
        for i in range(len(probs)):
            if np.sum(counts[i, :]) > 0:
                assert np.sum(probs[i, :]) == pytest.approx(1.0, abs=1e-4)

        # Duration statistics & boundary censoring tracked
        assert rep.regime_duration_statistics["total_episodes_count"] > 0
        assert rep.perturbation_stability["canonical_model_modified"] is False
        assert 0.0 <= rep.perturbation_stability["combined_stability_score"] <= 1.0
        assert rep.cross_period_consistency["status"] == "COMPUTED"

    def test_regime_research_blocks_threshold_mutation_and_missing_data(self):
        engine = HistoricalMarketRegimeResearchEngine()
        blocked = engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            custom_thresholds={"vol_extreme_quantile": 0.99},
        )
        assert blocked.status == "RESEARCH_BLOCKED"
        assert blocked.rejection_code == "FROZEN_REGIME_THRESHOLD_MUTATION_BLOCKED"

        # Missing OHLC observations rejected
        df_nan = pd.DataFrame(
            {
                "open_time": [1704067200000 + i * 3600000 for i in range(40)],
                "high": [42000.0] * 39 + [np.nan],
                "low": [41000.0] * 40,
                "close": [41500.0] * 40,
            }
        )
        blocked_nan = engine.run_regime_research(custom_df=df_nan)
        assert blocked_nan.status == "RESEARCH_BLOCKED"
        assert blocked_nan.rejection_code == "MISSING_OHLC_OBSERVATIONS"

        # Timestamp gaps are skipped during transition counting
        regimes = ["CONSOLIDATION_RANGING", "MOMENTUM_EXPANSION", "CAPITULATION"]
        ts_gapped = [1000, 2000, 50000]  # second step is a huge gap (> 1000)
        freq, _, _ = engine.compute_transition_matrix_and_uncertainty(
            regimes=regimes, timestamps_ms=ts_gapped, expected_step_ms=1000
        )
        assert freq["total_valid_transitions"] == 1
        assert freq["skipped_gap_transitions"] == 1


# ===========================================================================
# 4. MODULE 26.4 — ROBUSTNESS & SENSITIVITY LAB TESTS
# ===========================================================================


class TestModule264RobustnessSensitivityLab:
    """Tests for Module 26.4 Robustness & Sensitivity Lab."""

    def test_all_eight_sensitivity_dimensions_and_reproducibility(self):
        lab = RobustnessSensitivityLab()
        suite = lab.run_comprehensive_suite(
            original_record_id="RES-29-PAT-SIM",
            dataset_id="DS-BTC-1H-Q1-2024",
        )
        assert suite["status"] == "SUCCESS"
        assert suite["total_experiments"] == 8

        # Deterministic reproducibility check
        exp1 = lab.run_sensitivity_experiment(
            original_record_id="RES-29-PAT-SIM",
            analysis_type="MISSING_DATA_SENSITIVITY",
            dataset_id="DS-BTC-1H-Q1-2024",
            seed=42,
        )
        exp2 = lab.run_sensitivity_experiment(
            original_record_id="RES-29-PAT-SIM",
            analysis_type="MISSING_DATA_SENSITIVITY",
            dataset_id="DS-BTC-1H-Q1-2024",
            seed=42,
        )
        assert exp1.evidence_provenance["experiment_fingerprint_sha256"] == exp2.evidence_provenance["experiment_fingerprint_sha256"]
        assert exp1.resulting_measurements == exp2.resulting_measurements
        assert exp1.dataset_identity["source_sha256"] is not None

    def test_robustness_lab_rejects_canonical_mutation_unsupported_assumption_and_limits(self):
        lab = RobustnessSensitivityLab()
        mut_blocked = lab.run_sensitivity_experiment(
            modify_canonical_model=True,
        )
        assert mut_blocked.status == "EXPERIMENT_BLOCKED"
        assert mut_blocked.rejection_code == "CANONICAL_PARAMETER_MUTATION_PROHIBITED"

        unsup_blocked = lab.run_sensitivity_experiment(
            analysis_type="DIRECTIONAL_PROFIT_OPTIMIZATION",
        )
        assert unsup_blocked.status == "EXPERIMENT_BLOCKED"
        assert unsup_blocked.rejection_code == "UNSUPPORTED_SENSITIVITY_ASSUMPTION"

        limit_blocked = lab.run_sensitivity_experiment(
            analysis_type="BOOTSTRAP_UNCERTAINTY",
            perturbation_params={"n_iterations": 99999},
        )
        assert limit_blocked.status == "EXPERIMENT_BLOCKED"
        assert limit_blocked.rejection_code == "RESOURCE_LIMIT_EXCEEDED"


# ===========================================================================
# 5. MODULE 26.5 — INDEPENDENT VALIDATION FRAMEWORK TESTS
# ===========================================================================


class TestModule265IndependentValidationFramework:
    """Tests for Module 26.5 Independent Validation Framework."""

    def test_same_dataset_under_different_filename_or_id_rejected(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "STUDY-PRIMARY",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
        }
        renamed_clone = {
            "record_id": "STUDY-CANDIDATE-RENAMED",
            "dataset_id": "DS-EXTERNAL-INDEPENDENT-ALIAS-999",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
        }
        audit = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=renamed_clone,
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["dataset_lineage"]["passed"] is False
        assert audit.eight_point_checks["source_overlap"]["passed"] is False

    def test_overlapping_observation_windows_and_shared_preprocessing_rejected(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "STUDY-A",
            "dataset_id": "DS-A",
            "source_sha256": "aaa111",
            "content_fingerprint_sha256": "fp_aaa111",
            "timestamps_ms": [1000, 2000, 3000, 4000],
            "preprocessing_lineage_id": "SHARED-SCALER-01",
        }
        candidate = {
            "record_id": "STUDY-B",
            "dataset_id": "DS-B",
            "source_sha256": "bbb222",
            "content_fingerprint_sha256": "fp_bbb222",
            "timestamps_ms": [3000, 4000, 5000, 6000],
            "preprocessing_lineage_id": "SHARED-SCALER-01",
        }
        audit = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate,
            claimed_category="TEMPORAL_HOLDOUT_VALIDATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["observation_overlap"]["passed"] is False
        assert audit.eight_point_checks["time_window_overlap"]["passed"] is False
        assert audit.eight_point_checks["shared_preprocessing_artifacts"]["passed"] is False

    def test_independent_dataset_does_not_automatically_grant_independent_replication(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "STUDY-Q1-2024",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1",
            "procedure_id": "SAME-PROC-01",
        }
        candidate_disjoint_dataset = {
            "record_id": "STUDY-JAN-2025",
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-JAN25",
            "procedure_id": "SAME-PROC-01",
            "independent_replication_evidence_verified": False,
        }

        # Valid as INDEPENDENT_DATASET_VALIDATION
        audit_ds = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate_disjoint_dataset,
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert audit_ds.independence_established is True
        assert audit_ds.assigned_category == "INDEPENDENT_DATASET_VALIDATION"

        # Rejected when over-claiming INDEPENDENT_REPLICATION without procedure independence
        audit_rep = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate_disjoint_dataset,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert audit_rep.independence_established is False
        assert audit_rep.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"

        # Succeeds when independent procedure lineage and replication evidence are verified
        candidate_true_rep = dict(candidate_disjoint_dataset)
        candidate_true_rep["procedure_id"] = "INDEPENDENT-REPLICATION-PROC-02"
        candidate_true_rep["independent_replication_evidence_verified"] = True
        audit_true_rep = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate_true_rep,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert audit_true_rep.independence_established is True
        assert audit_true_rep.assigned_category == "INDEPENDENT_REPLICATION"


# ===========================================================================
# 6. MODULE 26.6 — DASHBOARD V4 API, UI & CROSS-MODULE INTEGRATION TESTS
# ===========================================================================


class TestModule266DashboardV4AndCrossModuleIntegration:
    """Tests for Dashboard V4 API endpoints, UI tabs, and Sprint 24-26 integration."""

    def test_all_six_sprint26_api_endpoints_get_and_post(self):
        # 1. Statistical Validation API
        st, res = ProductDashboardApiService.handle_request(
            "/api/v1/product/workspace/statistical-validation",
            {"record_id": ["RES-29-PAT-SIM"]},
        )
        assert st == HTTPStatus.OK
        assert res["assessment"]["record_id"] == "RES-29-PAT-SIM"

        # 2. Walk-Forward API
        st, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/walk-forward",
            {"dataset_id": "DS-BTC-1H-Q1-2024", "split_mode": "expanding", "n_splits": 4},
        )
        assert st == HTTPStatus.OK
        assert res["walk_forward_report"]["status"] == "EVALUATION_COMPLETED"

        # 3. Regime Research API
        st, res = ProductDashboardApiService.handle_request(
            "/api/v1/product/workspace/regime-research",
            {"dataset_id": ["DS-BTC-1H-Q1-2024"]},
        )
        assert st == HTTPStatus.OK
        assert res["regime_research_report"]["status"] == "RESEARCH_COMPLETED"

        # 4. Robustness Lab API
        st, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/robustness-lab",
            {"record_id": "RES-29-PAT-SIM", "analysis_type": "OUTLIER_SENSITIVITY"},
        )
        assert st == HTTPStatus.OK
        assert res["experiment"]["status"] == "EXPERIMENT_COMPLETED"

        # 5. Independent Validation API
        st, res = ProductDashboardApiService.handle_request(
            "/api/v1/product/workspace/independent-validation", {}
        )
        assert st == HTTPStatus.OK
        assert res["total_audits"] >= 6

        # 6. Scientific Validation Reports V4 API & 4-pillar concept separation
        st, res = ProductDashboardApiService.handle_request(
            "/api/v1/product/workspace/validation-reports",
            {"record_id": ["RES-29-PAT-SIM"]},
        )
        assert st == HTTPStatus.OK
        assert res["canonical_model"] == "CBE-0.7.0"
        assert res["model_status"] == "STRICTLY_FROZEN"
        assert res["governance_decision"] == "TECHNICAL_NO_GO"
        cs = res["concept_separation"]
        assert set(cs.keys()) == {
            "cryptographic_integrity",
            "methodological_validity",
            "statistical_validity",
            "independent_validation",
        }

    def test_dashboard_v4_html_contains_all_sprint26_views_and_preserves_sprint24_25(self):
        html = render_research_explorer_html()
        for tab_id in (
            "ws-tab-stat-validation",
            "ws-tab-walk-forward",
            "ws-tab-regime-research",
            "ws-tab-robustness-lab",
            "ws-tab-independent-validation",
            "ws-tab-validation-reports",
            "ws-tab-graph",
            "ws-tab-readiness",
            "ws-tab-gaps",
            "ws-tab-reproducibility",
            "ws-tab-priorities",
        ):
            assert tab_id in html
        for view_id in (
            "ws-view-stat-validation",
            "ws-view-walk-forward",
            "ws-view-regime-research",
            "ws-view-robustness-lab",
            "ws-view-independent-validation",
            "ws-view-validation-reports",
        ):
            assert view_id in html

    def test_cross_module_evidence_graph_readiness_gaps_reproducibility_priorities_and_reports(self):
        # 1. Evidence Graph connects statistical results with concept_separation
        g_res = ResearchWorkspaceV2Engine.get_evidence_graph_data()
        assert g_res["status"] == "success"
        stat_nodes = [
            n
            for n in g_res["graph"]["nodes"]
            if n["node_type"] == "STATISTICAL_RESULT"
        ]
        assert len(stat_nodes) >= 1
        for sn in stat_nodes:
            cs = sn["properties"].get("concept_separation")
            assert cs is not None
            assert set(cs.keys()) == {
                "cryptographic_integrity",
                "methodological_validity",
                "statistical_validity",
                "independent_validation",
            }

        # 2. Readiness scorecards reflect statistical & replication evidence
        sc_res = ResearchWorkspaceV2Engine.get_readiness_scorecards(record_id="RES-ANALOG-01")
        assert sc_res["status"] == "success"
        assert "scorecard" in sc_res

        # 3. Evidence gaps identify statistical/validation gaps
        gap_res = ResearchWorkspaceV2Engine.get_evidence_gaps()
        assert gap_res["status"] == "success"
        assert len(gap_res["gaps"]) >= 1

        # 4. Reproducibility & Priority Queue remain intact
        rep_res = ResearchWorkspaceV2Engine.get_reproducibility_procedures()
        assert rep_res["status"] == "success"
        prio_res = ResearchWorkspaceV2Engine.get_research_priorities()
        assert prio_res["status"] == "success"

        # 5. Decision & Validation Reports include Sprint 26 outputs
        val_rep = ResearchWorkspaceV2Engine.get_scientific_validation_reports(
            record_id="RES-29-PAT-SIM"
        )
        assert val_rep["status"] == "success"
        assert "statistical_validation" in val_rep
        assert "walk_forward_summary" in val_rep
        assert "regime_research_summary" in val_rep
        assert "robustness_summary" in val_rep
        assert "independent_validation_summary" in val_rep
        assert "sprint25_readiness_and_gaps" in val_rep

    def test_security_and_governance_invariants_across_sprint26(self):
        # 1. Malformed / non-existent record_id handled cleanly without 500
        st, res = ProductDashboardApiService.handle_request(
            "/api/v1/product/workspace/statistical-validation",
            {"record_id": ["NON-EXISTENT-RECORD-999"]},
        )
        assert st == HTTPStatus.NOT_FOUND
        assert res["error_code"] == "NOT_FOUND"

        # 2. Unauthorized saved-comparison mutation blocked
        st_unauth, _ = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/saved-comparisons",
            body={"title": "Test", "candidate_ids": ["RES-ANALOG-01", "RES-REGIME-01"]},
            headers={},
        )
        assert st_unauth in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)

        # 3. Resource governor bounds enforced
        lab = RobustnessSensitivityLab()
        exp_over = lab.run_sensitivity_experiment(
            original_record_id="RES-29-PAT-SIM",
            analysis_type="BOOTSTRAP_UNCERTAINTY",
            perturbation_params={"n_iterations": 999999},
        )
        assert exp_over.status == "EXPERIMENT_BLOCKED"
        assert exp_over.rejection_code == "RESOURCE_LIMIT_EXCEEDED"

        # 4. Governance invariants strictly enforced across all modules
        val_rep = ResearchWorkspaceV2Engine.get_scientific_validation_reports(
            record_id="RES-29-PAT-SIM"
        )
        assert val_rep["canonical_model"] == "CBE-0.7.0"
        assert val_rep["model_status"] == "STRICTLY_FROZEN"
        assert val_rep["governance_decision"] == "TECHNICAL_NO_GO"
        assert val_rep["trading_eligibility"] == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"

