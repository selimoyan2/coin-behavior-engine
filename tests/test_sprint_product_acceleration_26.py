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

import hashlib
from http import HTTPStatus
import json
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

        # Caller-supplied DataFrame without trusted_fixture_context is blocked fail-closed
        df_nan = pd.DataFrame(
            {
                "open_time": [1704067200000 + i * 3600000 for i in range(40)],
                "high": [42000.0] * 39 + [np.nan],
                "low": [41000.0] * 40,
                "close": [41500.0] * 40,
            }
        )
        blocked_untrusted_df = engine.run_regime_research(custom_df=df_nan)
        assert blocked_untrusted_df.status == "RESEARCH_BLOCKED"
        assert blocked_untrusted_df.rejection_code == "CALLER_SUPPLIED_UNVERIFIED"

        # Missing OHLC observations rejected when trusted_fixture_context=True
        blocked_nan = engine.run_regime_research(custom_df=df_nan, trusted_fixture_context=True)
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

        # Rejected when caller only sets boolean flag independent_replication_evidence_verified=True without signed attestation
        candidate_boolean_only = dict(candidate_disjoint_dataset)
        candidate_boolean_only["procedure_id"] = "INDEPENDENT-REPLICATION-PROC-02"
        candidate_boolean_only["independent_replication_evidence_verified"] = True
        audit_bool_rejected = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate_boolean_only,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert audit_bool_rejected.independence_established is False
        assert audit_bool_rejected.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"

        # Succeeds when independent procedure lineage AND signed replication attestation + physical artifact are verified
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        res_artifact_rel = "research_outputs/sprint26_advanced_scientific_validation/08_independent_validation_criteria.json"
        res_artifact_sha = hashlib.sha256((Path.cwd() / res_artifact_rel).read_bytes()).hexdigest()
        prim_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet").read_bytes()
        ).hexdigest()
        cand_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet").read_bytes()
        ).hexdigest()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-rep-key-2026-v1",
            secret="isolated-test-replication-secret-2026-v1-a9b8",
        ) as auth_ctx:
            signed_rep_att = IndependentValidationFramework.create_signed_replication_attestation(
                replication_attempt_id="REP-ATTEMPT-S26-JAN2025-01",
                primary_record_id="STUDY-Q1-2024",
                candidate_record_id="STUDY-JAN-2025",
                primary_dataset_id="DS-BTC-1H-Q1-2024",
                candidate_dataset_id="DS-BTC-1H-JAN-2025",
                primary_source_sha256=prim_sha,
                candidate_source_sha256=cand_sha,
                result_artifact_path=res_artifact_rel,
                result_artifact_sha256=res_artifact_sha,
                hypothesis_id="HYP-PAT-SIM-S26",
                methodology_id="CBE-0.7.0-CANONICAL",
                primary_procedure_id="SAME-PROC-01",
                candidate_procedure_id="INDEPENDENT-REPLICATION-PROC-02",
                procedure_version="SPRINT26-V1.0",
                independent_execution_lineage="EXEC-LINEAGE-INDEPENDENT-2025",
                replication_outcome="OUT_OF_SAMPLE_REPLICATED",
                key_id="cbe-test-rep-key-2026-v1",
                authority_context=auth_ctx,
            )
            candidate_true_rep = dict(candidate_disjoint_dataset)
            candidate_true_rep["procedure_id"] = "INDEPENDENT-REPLICATION-PROC-02"
            candidate_true_rep["replication_attestation"] = signed_rep_att
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


# ===========================================================================
# 7. SPRINT 26 FINAL SCIENTIFIC TRUST CLOSURE — 20 NEGATIVE + POSITIVE TESTS
# ===========================================================================


class TestSprint26FinalScientificTrustClosure:
    """Comprehensive negative and positive test suite for Sprint 26 Final Scientific Trust Closure."""

    @pytest.fixture(autouse=True)
    def setup_isolated_trust_closure_keys(self):
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import (
            CANONICAL_HISTORICAL_AUTHORITY_KEY_ID,
        )

        with signing_key_registry.isolated_test_signing_context(
            key_id=CANONICAL_HISTORICAL_AUTHORITY_KEY_ID,
            secret="isolated-test-intake-manifest-secret-2026-v2",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            self.intake_auth_ctx = auth_ctx
            yield

    @staticmethod
    def _build_test_only_forged_intake_manifest(
        *,
        dataset_id: str,
        artifact_hashes: Dict[str, str],
        source_lineage: str,
        key_id: str,
        forged_signature: str,
        issuer: str = "CBE_DATA_GOVERNANCE_COUNCIL",
        record_id: str = "",
        expires_at_utc: str = "",
        is_superseded: bool = False,
    ) -> Dict[str, Any]:
        """Isolated test-only helper for constructing deliberately invalid/forged intake manifests
        without invoking production signing APIs or exposing forged_signature in production code.
        """
        from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json

        artifacts = [{"path": str(k), "sha256": str(v)} for k, v in artifact_hashes.items()]
        src_sha = artifacts[0]["sha256"] if artifacts else ""
        claims = {
            "artifacts": sorted(artifacts, key=lambda x: str(x.get("path", ""))),
            "dataset_id": str(dataset_id),
            "expires_at_utc": str(expires_at_utc or ""),
            "is_superseded": bool(is_superseded),
            "issuer": str(issuer),
            "key_id": str(key_id),
            "record_id": str(record_id),
            "schema_version": "CBE-INTAKE-MANIFEST-1.0.0",
            "source_artifact_sha256": str(src_sha),
            "source_lineage": str(source_lineage),
        }
        canonical_bytes = rfc8785_canonical_json(claims)
        return {
            **claims,
            "claims_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
            "signature": forged_signature,
        }

    def test_01_existing_parquet_without_trusted_provenance_rejected(self, tmp_path):
        # Copy a real Parquet file to a new path not bound in any signed manifest
        src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        unverified_parquet = tmp_path / "unverified_copy.parquet"
        unverified_parquet.write_bytes(src.read_bytes())

        wf_lab = WalkForwardResearchLab(workspace_root=tmp_path)
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-UNREGISTERED-PARQUET",
            source_path="unverified_copy.parquet",
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["verification_status"] == "UNVERIFIED_HISTORICAL_INPUT"

        reg_engine = HistoricalMarketRegimeResearchEngine(workspace_root=tmp_path)
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-UNREGISTERED-PARQUET",
            source_path="unverified_copy.parquet",
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["verification_status"] == "UNVERIFIED_HISTORICAL_INPUT"

    def test_02_valid_looking_unsigned_provenance_sidecar_rejected(self, tmp_path):
        src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        raw = src.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        p_file = tmp_path / "historical_binance_btcusdt_1h_q1_2024.parquet"
        p_file.write_bytes(raw)
        sidecar = tmp_path / "historical_binance_btcusdt_1h_q1_2024_provenance.json"
        sidecar.write_text(
            json.dumps(
                {
                    "dataset_id": "DS-BTC-1H-Q1-2024",
                    "sha256": sha,
                    "status": "VERIFIED",
                    "issuer": "SELF_DECLARED_UNSIGNED",
                }
            ),
            encoding="utf-8",
        )

        wf_lab = WalkForwardResearchLab(workspace_root=tmp_path)
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            source_path="historical_binance_btcusdt_1h_q1_2024.parquet",
            provenance_sidecar_path=str(sidecar),
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "UNSIGNED_PROVENANCE_SIDECAR"

        reg_engine = HistoricalMarketRegimeResearchEngine(workspace_root=tmp_path)
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            source_path="historical_binance_btcusdt_1h_q1_2024.parquet",
            provenance_sidecar_path=str(sidecar),
            require_explicit_evidence=True,
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["provenance_rejection_code"] == "UNSIGNED_PROVENANCE_SIDECAR"

    def test_03_forged_signed_intake_manifest_rejected(self):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes={
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5"
            },
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            authority_context=self.intake_auth_ctx,
        )
        forged_manifest = dict(manifest)
        forged_manifest["signature"] = "0" * 64

        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=forged_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=forged_manifest,
            require_explicit_evidence=True,
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["provenance_rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_04_source_sha256_mismatch_rejected(self):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        bad_hash_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes={
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "f" * 64
            },
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            authority_context=self.intake_auth_ctx,
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=bad_hash_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=bad_hash_manifest,
            require_explicit_evidence=True,
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["provenance_rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

    def test_05_dataset_identity_mismatch_rejected(self):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        wrong_id_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-OTHER-DATASET-ID",
            artifact_hashes={
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5"
            },
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            authority_context=self.intake_auth_ctx,
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=wrong_id_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "DATASET_ID_MISMATCH"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=wrong_id_manifest,
            require_explicit_evidence=True,
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["provenance_rejection_code"] == "DATASET_ID_MISMATCH"

    def test_06_revoked_attestation_signing_key_rejected(self):
        revoked_manifest = self._build_test_only_forged_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes={
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5"
            },
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            key_id="cbe-attestation-2025-revoked",
            forged_signature="hmac-sha256:cbe-attestation-2025-revoked:" + ("a" * 64),
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=revoked_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_07_expired_attestation_rejected(self):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        expired_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes={
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5"
            },
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            issued_at_utc="2020-01-01T00:00:00Z",
            expires_at_utc="2021-01-01T00:00:00Z",
            authority_context=self.intake_auth_ctx,
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=expired_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "ATTESTATION_EXPIRED"

    def test_08_quarantined_historical_dataset_rejected(self):
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(dataset_id="DS-BTC-1H-OCT2026-QUARANTINE")
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "DATASET_QUARANTINED"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(dataset_id="DS-BTC-1H-OCT2026-QUARANTINE")
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "QUARANTINED_DATASET_REJECTED"

        fw = IndependentValidationFramework()
        audit = fw.evaluate_validation_independence(
            primary_study={"record_id": "R1", "dataset_id": "DS-BTC-1H-Q1-2024", "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"},
            candidate_study={"record_id": "R2", "dataset_id": "DS-BTC-1H-OCT2026-QUARANTINE", "quarantined": True},
        )
        assert audit.assigned_category == "VALIDATION_BLOCKED"
        assert audit.independence_established is False

    def test_09_caller_supplied_dataframe_without_provenance_rejected(self):
        df_caller = pd.DataFrame(
            {
                "open_time": [1704067200000 + i * 3600000 for i in range(200)],
                "open": [42000.0] * 200,
                "high": [42200.0] * 200,
                "low": [41800.0] * 200,
                "close": [42100.0] * 200,
            }
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(custom_df=df_caller)
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "CALLER_SUPPLIED_UNVERIFIED"
        assert wf_res.dataset_provenance["verification_status"] == "CALLER_SUPPLIED_UNVERIFIED"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(custom_df=df_caller)
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "CALLER_SUPPLIED_UNVERIFIED"
        assert reg_res.verified_source_artifact["verification_status"] == "CALLER_SUPPLIED_UNVERIFIED"

        rob_lab = RobustnessSensitivityLab()
        rob_res = rob_lab.run_sensitivity_experiment(custom_df=df_caller)
        assert rob_res.status == "EXPERIMENT_BLOCKED"
        assert rob_res.rejection_code == "CALLER_SUPPLIED_UNVERIFIED"

    def test_10_caller_supplied_fake_source_sha256_rejected(self):
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            caller_supplied_sha256="deadbeef" * 8,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "CALLER_SUPPLIED_SHA256_MISMATCH"

        reg_engine = HistoricalMarketRegimeResearchEngine()
        reg_res = reg_engine.run_regime_research(
            dataset_id="DS-BTC-1H-Q1-2024",
            caller_supplied_sha256="deadbeef" * 8,
        )
        assert reg_res.status == "RESEARCH_BLOCKED"
        assert reg_res.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert reg_res.verified_source_artifact["provenance_rejection_code"] == "CALLER_SUPPLIED_SHA256_MISMATCH"

    def test_11_caller_provided_independent_replication_boolean_flag_rejected(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "STUDY-Q1-2024",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1",
            "procedure_id": "PROC-PRIMARY-01",
        }
        candidate = {
            "record_id": "STUDY-JAN-2025",
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-JAN25",
            "procedure_id": "PROC-CANDIDATE-02",
            "independent_replication_evidence_verified": True,
        }
        audit = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["researcher_or_procedure_independence"]["passed"] is False
        assert (
            audit.eight_point_checks["researcher_or_procedure_independence"]["status_code"]
            == "CALLER_BOOLEAN_REPLICATION_FLAG_REJECTED"
        )

    def test_12_different_procedure_ids_without_independent_execution_evidence_rejected(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "STUDY-Q1-2024",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1",
            "procedure_id": "PROC-PRIMARY-A",
        }
        candidate = {
            "record_id": "STUDY-JAN-2025",
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-JAN25",
            "procedure_id": "PROC-CANDIDATE-B",
        }
        audit = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert (
            audit.eight_point_checks["researcher_or_procedure_independence"]["status_code"]
            == "MISSING_REPLICATION_ATTESTATION"
        )

    def test_13_different_filenames_pointing_to_identical_data_rejected(self, tmp_path):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        raw = src.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        f_a = tmp_path / "dataset_alpha.parquet"
        f_b = tmp_path / "dataset_beta.parquet"
        f_a.write_bytes(raw)
        f_b.write_bytes(raw)

        man_a = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-ALPHA",
            artifact_hashes={"dataset_alpha.parquet": sha},
            source_lineage="LINEAGE-ALPHA",
            authority_context=self.intake_auth_ctx,
        )
        man_b = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-BETA",
            artifact_hashes={"dataset_beta.parquet": sha},
            source_lineage="LINEAGE-BETA",
            authority_context=self.intake_auth_ctx,
        )
        fw = IndependentValidationFramework(workspace_root=tmp_path)
        audit = fw.evaluate_validation_independence(
            primary_study={
                "record_id": "R-ALPHA",
                "dataset_id": "DS-ALPHA",
                "source_path": "dataset_alpha.parquet",
                "intake_manifest": man_a,
            },
            candidate_study={
                "record_id": "R-BETA",
                "dataset_id": "DS-BETA",
                "source_path": "dataset_beta.parquet",
                "intake_manifest": man_b,
            },
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["dataset_lineage"]["passed"] is False
        assert audit.eight_point_checks["source_overlap"]["passed"] is False

    def test_14_different_dataset_ids_with_overlapping_observations_rejected(self):
        fw = IndependentValidationFramework()
        audit = fw.evaluate_validation_independence(
            primary_study={
                "record_id": "R-Q1-1H",
                "dataset_id": "DS-BTC-1H-Q1-2024",
                "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            },
            candidate_study={
                "record_id": "R-Q1-15M",
                "dataset_id": "DS-BTC-15M-Q1-2024",
                "source_path": "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
            },
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["observation_overlap"]["passed"] is False
        assert audit.eight_point_checks["time_window_overlap"]["passed"] is False

    def test_15_shared_preprocessing_lineage_rejected(self):
        fw = IndependentValidationFramework()
        audit = fw.evaluate_validation_independence(
            primary_study={
                "record_id": "R-Q1-1H",
                "dataset_id": "DS-BTC-1H-Q1-2024",
                "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
                "preprocessing_lineage_id": "SHARED-FIT-SCALER-2024",
            },
            candidate_study={
                "record_id": "R-JAN25-1H",
                "dataset_id": "DS-BTC-1H-JAN-2025",
                "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
                "preprocessing_lineage_id": "SHARED-FIT-SCALER-2024",
            },
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert audit.eight_point_checks["shared_preprocessing_artifacts"]["passed"] is False

    def test_16_invalid_replication_result_artifact_rejected(self, tmp_path):
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        prim_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet").read_bytes()
        ).hexdigest()
        cand_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet").read_bytes()
        ).hexdigest()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-rep-key-16",
            secret="isolated-test-rep-secret-16-9911",
        ) as auth_ctx:
            bad_att = IndependentValidationFramework.create_signed_replication_attestation(
                replication_attempt_id="REP-BAD-ARTIFACT",
                primary_record_id="STUDY-Q1-2024",
                candidate_record_id="STUDY-JAN-2025",
                primary_dataset_id="DS-BTC-1H-Q1-2024",
                candidate_dataset_id="DS-BTC-1H-JAN-2025",
                primary_source_sha256=prim_sha,
                candidate_source_sha256=cand_sha,
                result_artifact_path="research_outputs/sprint26_advanced_scientific_validation/08_independent_validation_criteria.json",
                result_artifact_sha256="0" * 64,  # Wrong SHA-256 for the result artifact
                hypothesis_id="HYP-PAT-SIM-S26",
                methodology_id="CBE-0.7.0-CANONICAL",
                primary_procedure_id="PROC-01",
                candidate_procedure_id="PROC-02",
                procedure_version="V1.0",
                independent_execution_lineage="EXEC-IND-02",
                key_id="cbe-test-rep-key-16",
                authority_context=auth_ctx,
            )
            audit = fw.evaluate_validation_independence(
                primary_study={
                    "record_id": "STUDY-Q1-2024",
                    "dataset_id": "DS-BTC-1H-Q1-2024",
                    "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
                    "procedure_id": "PROC-01",
                },
                candidate_study={
                    "record_id": "STUDY-JAN-2025",
                    "dataset_id": "DS-BTC-1H-JAN-2025",
                    "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
                    "procedure_id": "PROC-02",
                    "replication_attestation": bad_att,
                },
                claimed_category="INDEPENDENT_REPLICATION",
            )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert (
            audit.eight_point_checks["researcher_or_procedure_independence"]["status_code"]
            == "INVALID_REPLICATION_RESULT_ARTIFACT_HASH"
        )

    def test_17_replication_evidence_belonging_to_another_research_record_rejected(self):
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        res_rel = "research_outputs/sprint26_advanced_scientific_validation/08_independent_validation_criteria.json"
        res_sha = hashlib.sha256((Path.cwd() / res_rel).read_bytes()).hexdigest()
        prim_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet").read_bytes()
        ).hexdigest()
        cand_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet").read_bytes()
        ).hexdigest()

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-rep-key-17",
            secret="isolated-test-rep-secret-17-9922",
        ) as auth_ctx:
            other_record_att = IndependentValidationFramework.create_signed_replication_attestation(
                replication_attempt_id="REP-OTHER-RECORD",
                primary_record_id="RES-OTHER-RECORD-999",
                candidate_record_id="STUDY-JAN-2025",
                primary_dataset_id="DS-BTC-1H-Q1-2024",
                candidate_dataset_id="DS-BTC-1H-JAN-2025",
                primary_source_sha256=prim_sha,
                candidate_source_sha256=cand_sha,
                result_artifact_path=res_rel,
                result_artifact_sha256=res_sha,
                hypothesis_id="HYP-OTHER",
                methodology_id="CBE-0.7.0-CANONICAL",
                primary_procedure_id="PROC-01",
                candidate_procedure_id="PROC-02",
                procedure_version="V1.0",
                independent_execution_lineage="EXEC-IND-02",
                key_id="cbe-test-rep-key-17",
                authority_context=auth_ctx,
            )
            audit = fw.evaluate_validation_independence(
                primary_study={
                    "record_id": "STUDY-Q1-2024",
                    "dataset_id": "DS-BTC-1H-Q1-2024",
                    "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
                    "procedure_id": "PROC-01",
                },
                candidate_study={
                    "record_id": "STUDY-JAN-2025",
                    "dataset_id": "DS-BTC-1H-JAN-2025",
                    "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
                    "procedure_id": "PROC-02",
                    "replication_attestation": other_record_att,
                },
                claimed_category="INDEPENDENT_REPLICATION",
            )
        assert audit.independence_established is False
        assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
        assert (
            audit.eight_point_checks["researcher_or_procedure_independence"]["status_code"]
            == "REPLICATION_RECORD_BINDING_MISMATCH"
        )

    def test_18_and_19_source_mutation_after_verification_invalidates_cache_and_fails_closed(self, tmp_path):
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        raw = src.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        rel_p = "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        target_p = tmp_path / rel_p
        target_p.parent.mkdir(parents=True, exist_ok=True)
        target_p.write_bytes(raw)

        manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes={rel_p: sha},
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            authority_context=self.intake_auth_ctx,
        )

        # First verification succeeds and populates cache
        wf_lab = WalkForwardResearchLab(workspace_root=tmp_path)
        res_ok = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            source_path=rel_p,
            intake_manifest=manifest,
            require_explicit_evidence=True,
        )
        assert res_ok.status == "EVALUATION_COMPLETED"
        assert res_ok.dataset_provenance["is_verified"] is True

        # Mutate physical Parquet file on disk after successful verification
        other_src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet"
        target_p.write_bytes(other_src.read_bytes())

        # Subsequent call must NOT reuse stale cache and must fail closed with SOURCE_ARTIFACT_HASH_MISMATCH
        res_mutated = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            source_path=rel_p,
            intake_manifest=manifest,
            require_explicit_evidence=True,
        )
        assert res_mutated.status == "EVALUATION_BLOCKED"
        assert res_mutated.rejection_code == "UNVERIFIED_HISTORICAL_INPUT"
        assert res_mutated.dataset_provenance["provenance_rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

    def test_20_explicit_independent_replication_claim_without_authenticated_evidence_rejected_while_dataset_validation_preserved(self):
        fw = IndependentValidationFramework()
        primary = {
            "record_id": "RES-29-PAT-SIM",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1-ISOLATED",
            "procedure_id": "PROC-DISCOVERY-01",
        }
        candidate = {
            "record_id": "VAL-BTC-1H-JAN-2025",
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-JAN25-ISOLATED",
            "procedure_id": "PROC-HOLDOUT-02",
        }

        # Explicit INDEPENDENT_REPLICATION claim without signed replication attestation -> INDEPENDENCE_NOT_ESTABLISHED
        rep_claim = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate,
            claimed_category="INDEPENDENT_REPLICATION",
        )
        assert rep_claim.independence_established is False
        assert rep_claim.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"

        # Permitted INDEPENDENT_DATASET_VALIDATION assessment -> INDEPENDENT_DATASET_VALIDATION
        ds_claim = fw.evaluate_validation_independence(
            primary_study=primary,
            candidate_study=candidate,
            claimed_category="INDEPENDENT_DATASET_VALIDATION",
        )
        assert ds_claim.independence_established is True
        assert ds_claim.assigned_category == "INDEPENDENT_DATASET_VALIDATION"


# ===========================================================================
# 8. SPRINT 26 FINAL SIGNING AUTHORITY HARDENING — 20 NEGATIVE + POSITIVE TESTS
# ===========================================================================


class TestSprint26FinalSigningAuthorityHardening:
    """
    Comprehensive negative and positive test suite for Sprint 26 Final Signing Authority Hardening:
    - P0 Cryptographic Signing Key Isolation (zero hardcoded fallback secrets, zero _keys leakage)
    - P0 6-condition Signing Authority Enforcement & 5 Rejection Codes
    - P0 Verification-Only Runtime & Public API Separation
    - Key Rotation, Revocation, Cache Invalidation & Scientific Independence Preservation
    """

    @staticmethod
    def _base_replication_kwargs() -> dict:
        res_rel = "research_outputs/sprint26_advanced_scientific_validation/08_independent_validation_criteria.json"
        res_sha = hashlib.sha256((Path.cwd() / res_rel).read_bytes()).hexdigest()
        prim_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet").read_bytes()
        ).hexdigest()
        cand_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet").read_bytes()
        ).hexdigest()
        return {
            "replication_attempt_id": "REP-HARDENING-2026-01",
            "primary_record_id": "STUDY-Q1-2024",
            "candidate_record_id": "STUDY-JAN-2025",
            "primary_dataset_id": "DS-BTC-1H-Q1-2024",
            "candidate_dataset_id": "DS-BTC-1H-JAN-2025",
            "primary_source_sha256": prim_sha,
            "candidate_source_sha256": cand_sha,
            "result_artifact_path": res_rel,
            "result_artifact_sha256": res_sha,
            "hypothesis_id": "HYP-PAT-SIM-S26",
            "methodology_id": "CBE-0.7.0-CANONICAL",
            "primary_procedure_id": "PROC-PRIMARY-01",
            "candidate_procedure_id": "PROC-INDEPENDENT-02",
            "procedure_version": "SPRINT26-V1.0",
            "independent_execution_lineage": "EXEC-LINEAGE-INDEPENDENT-2026",
        }

    def test_00_source_code_contains_no_hardcoded_signing_secrets_or_private_keys_access(self):
        """Verify hardcoded signing secrets and direct _keys accesses are completely removed."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        ivf_src = (
            Path.cwd() / "src/coin_behavior_engine/product/independent_validation_framework.py"
        ).read_text(encoding="utf-8")
        sr_src = (
            Path.cwd() / "src/coin_behavior_engine/product/scientific_readiness.py"
        ).read_text(encoding="utf-8")

        forbidden_literals = (
            "cbe-replication-attestation-authority-secret-2026-v1-9c31b7e2",
            "cbe-canonical-historical-dataset-authority-secret-2026-v1-a8f49d21",
            "cbe-revoked-historical-key-secret-2025-v1-00000000",
            "signing_key_registry._keys",
        )
        for lit in forbidden_literals:
            assert lit not in ivf_src, f"Forbidden literal '{lit}' found in independent_validation_framework.py"
            assert lit not in sr_src, f"Forbidden literal '{lit}' found in scientific_readiness.py"

        # Previously exposed key IDs must be revoked by default
        assert signing_key_registry.is_key_revoked("cbe-attestation-2026-v1") is True
        assert signing_key_registry.is_key_revoked("cbe-data-authority-2026-v1") is True
        assert signing_key_registry.is_key_revoked("cbe-attestation-2025-revoked") is True

    def test_neg_01_missing_signing_key_rejected(self):
        """1. Missing signing key -> Rejected (SIGNING_KEY_NOT_FOUND)."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityContext,
            SigningAuthorityError,
        )

        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing()
        kwargs = self._base_replication_kwargs()
        with pytest.raises(SigningAuthorityError) as exc_info:
            IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="",
                authority_context=auth_ctx,
            )
        assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_FOUND"

    def test_neg_02_unknown_key_id_rejected(self):
        """2. Unknown key ID -> Rejected (SIGNING_KEY_NOT_FOUND)."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityContext,
            SigningAuthorityError,
        )

        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing()
        kwargs = self._base_replication_kwargs()
        with pytest.raises(SigningAuthorityError) as exc_info:
            IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-nonexistent-unknown-key-9999",
                authority_context=auth_ctx,
            )
        assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_FOUND"

    def test_neg_03_revoked_signing_key_rejected_during_signing(self):
        """3. Revoked signing key -> Rejected (SIGNING_KEY_REVOKED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_REPLICATION_ATTESTATION,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )

        rev_key = "cbe-test-revoked-signing-key-03"
        signing_key_registry.register_key(
            rev_key,
            "isolated-test-revoked-secret-03-abcd",
            is_active=True,
            allowed_purposes=(KEY_PURPOSE_REPLICATION_ATTESTATION,),
            is_test_key=True,
        )
        signing_key_registry.revoke_key(rev_key)
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(allowed_key_ids=(rev_key,))
        kwargs = self._base_replication_kwargs()
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=rev_key,
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_REVOKED"
        finally:
            signing_key_registry.remove_key(rev_key)

    def test_neg_04_key_without_replication_signing_permission_rejected(self):
        """4. Key without replication-signing permission -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )

        intake_only_key = "cbe-test-intake-only-key-04"
        signing_key_registry.register_key(
            intake_only_key,
            "isolated-test-intake-only-secret-04-efgh",
            is_active=True,
            allowed_purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
            is_test_key=True,
        )
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=(intake_only_key,)
        )
        kwargs = self._base_replication_kwargs()
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=intake_only_key,
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"
        finally:
            signing_key_registry.remove_key(intake_only_key)

    def test_neg_05_unauthorized_signing_caller_rejected(self):
        """5. Unauthorized signing caller -> Rejected (SIGNING_AUTHORITY_NOT_GRANTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_REPLICATION_ATTESTATION,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )

        test_key = "cbe-test-active-key-05"
        signing_key_registry.register_key(
            test_key,
            "isolated-test-active-secret-05-1234",
            is_active=True,
            allowed_purposes=(KEY_PURPOSE_REPLICATION_ATTESTATION,),
            is_test_key=True,
        )
        kwargs = self._base_replication_kwargs()
        try:
            # Missing authority_context -> SIGNING_AUTHORITY_NOT_GRANTED
            with pytest.raises(SigningAuthorityError) as exc_missing:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=test_key,
                    authority_context=None,
                    runtime_mode="ISOLATED_TEST_SIGNING",
                )
            assert exc_missing.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

            # Forged/unsealed authority_context -> SIGNING_AUTHORITY_NOT_GRANTED
            forged_ctx = SigningAuthorityContext(
                context_id="forged-session",
                authority_principal="FORGED_CALLER",
                allowed_purposes={KEY_PURPOSE_REPLICATION_ATTESTATION},
                allowed_key_ids={test_key},
                environment_scope="test_isolated",
                is_test_authority=True,
                capability_seal="0" * 64,
            )
            with pytest.raises(SigningAuthorityError) as exc_forged:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=test_key,
                    authority_context=forged_ctx,
                    runtime_mode="ISOLATED_TEST_SIGNING",
                )
            assert exc_forged.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"
        finally:
            signing_key_registry.remove_key(test_key)

    def test_neg_06_ordinary_research_api_attempting_attestation_creation_rejected(self):
        """6. Ordinary research API attempting attestation creation -> Rejected (SIGNING_OPERATION_NOT_PERMITTED)."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityError,
            public_api_request_guard,
            signing_key_registry,
        )

        # A. HTTP POST to /api/v1/product/workspace/independent-validation attempting signing
        st_sign, res_sign = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/independent-validation",
            body={"action": "sign", "create_attestation": True},
        )
        assert st_sign == HTTPStatus.FORBIDDEN
        assert res_sign["rejection_code"] == "SIGNING_OPERATION_NOT_PERMITTED"

        st_ep, res_ep = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/replication-attestation/sign",
            body=self._base_replication_kwargs(),
        )
        assert st_ep == HTTPStatus.FORBIDDEN
        assert res_ep["rejection_code"] == "SIGNING_OPERATION_NOT_PERMITTED"

        # B. Even if internal code inside a public_api_request_guard() tries to sign, it is blocked
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-api-guard-key-06",
            secret="isolated-test-api-guard-secret-06",
        ) as auth_ctx:
            with public_api_request_guard():
                with pytest.raises(SigningAuthorityError) as exc_info:
                    IndependentValidationFramework.create_signed_replication_attestation(
                        **kwargs,
                        key_id="cbe-test-api-guard-key-06",
                        authority_context=auth_ctx,
                    )
                assert exc_info.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

    def test_neg_07_caller_supplied_authorization_boolean_rejected(self):
        """7. Caller-supplied authorization boolean (is_admin=True, authorized=True) -> Rejected."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityError,
            signing_key_registry,
        )

        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-bool-key-07",
            secret="isolated-test-bool-secret-07",
        ) as auth_ctx:
            with pytest.raises(SigningAuthorityError) as exc_admin:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id="cbe-test-bool-key-07",
                    authority_context=auth_ctx,
                    is_admin=True,
                )
            assert exc_admin.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

            with pytest.raises(SigningAuthorityError) as exc_auth:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id="cbe-test-bool-key-07",
                    authority_context=auth_ctx,
                    authorized=True,
                )
            assert exc_auth.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

        # Also rejected at the HTTP API layer
        st_api, res_api = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/independent-validation",
            body={"is_admin": True, "authorized": True},
        )
        assert st_api == HTTPStatus.FORBIDDEN
        assert res_api["rejection_code"] == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_08_caller_supplied_signing_key_rejected(self):
        """8. Caller-supplied signing key -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityError,
            signing_key_registry,
        )

        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-08",
            secret="isolated-test-secret-08",
        ) as auth_ctx:
            with pytest.raises(SigningAuthorityError) as exc_key:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id="cbe-test-key-08",
                    authority_context=auth_ctx,
                    signing_key="caller-injected-signing-key-material",
                )
            assert exc_key.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

        st_api, res_api = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/independent-validation",
            body={"signing_key": "caller-injected-signing-key-material"},
        )
        assert st_api == HTTPStatus.FORBIDDEN
        assert res_api["rejection_code"] == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_neg_09_caller_supplied_signing_secret_rejected(self):
        """9. Caller-supplied signing secret -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityError,
            signing_key_registry,
        )

        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-09",
            secret="isolated-test-secret-09",
        ) as auth_ctx:
            with pytest.raises(SigningAuthorityError) as exc_sec:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id="cbe-test-key-09",
                    authority_context=auth_ctx,
                    secret="caller-supplied-raw-hmac-secret",
                )
            assert exc_sec.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

        st_api, res_api = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/independent-validation",
            body={"signing_secret": "caller-supplied-raw-hmac-secret"},
        )
        assert st_api == HTTPStatus.FORBIDDEN
        assert res_api["rejection_code"] == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_neg_10_forged_replication_attestation_rejected(self):
        """10. Forged replication attestation -> Rejected (SIGNATURE_VERIFICATION_FAILED)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-10",
            secret="isolated-test-secret-10",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-10",
                authority_context=auth_ctx,
            )
            forged = dict(att)
            forged["signature"] = "hmac-sha256:cbe-test-key-10:" + ("f" * 64)
            ver = fw.verify_replication_attestation(
                attestation=forged,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_neg_11_modified_signed_claims_rejected(self):
        """11. Modified signed claims -> Rejected (SIGNATURE_VERIFICATION_FAILED)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-11",
            secret="isolated-test-secret-11",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-11",
                authority_context=auth_ctx,
            )
            tampered = dict(att)
            tampered["hypothesis_id"] = "HYP-TAMPERED-AFTER-SIGNING"
            ver = fw.verify_replication_attestation(
                attestation=tampered,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_neg_12_expired_replication_attestation_rejected(self):
        """12. Expired attestation -> Rejected (ATTESTATION_EXPIRED)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-12",
            secret="isolated-test-secret-12",
        ) as auth_ctx:
            att_exp = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-12",
                authority_context=auth_ctx,
                issued_at_utc="2021-01-01T00:00:00Z",
                expires_at_utc="2022-01-01T00:00:00Z",
            )
            ver = fw.verify_replication_attestation(
                attestation=att_exp,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "ATTESTATION_EXPIRED"

    def test_neg_13_revoked_attestation_key_rejected_on_verification(self):
        """13. Revoked attestation key -> Rejected (REVOKED_SIGNING_KEY)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-13",
            secret="isolated-test-secret-13",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-13",
                authority_context=auth_ctx,
            )
            # Revoke the key after the attestation was issued
            signing_key_registry.revoke_key("cbe-test-key-13")
            ver = fw.verify_replication_attestation(
                attestation=att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_neg_14_invalid_result_artifact_hash_rejected(self):
        """14. Invalid result artifact hash -> Rejected (INVALID_REPLICATION_RESULT_ARTIFACT_HASH)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        kwargs["result_artifact_sha256"] = "e" * 64
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-14",
            secret="isolated-test-secret-14",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-14",
                authority_context=auth_ctx,
            )
            ver = fw.verify_replication_attestation(
                attestation=att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "INVALID_REPLICATION_RESULT_ARTIFACT_HASH"

    def test_neg_15_missing_replication_result_artifact_rejected(self):
        """15. Missing replication result artifact -> Rejected (MISSING_REPLICATION_RESULT_ARTIFACT)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        kwargs["result_artifact_path"] = "research_outputs/non_existent_replication_output_999.json"
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-key-15",
            secret="isolated-test-secret-15",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-key-15",
                authority_context=auth_ctx,
            )
            ver = fw.verify_replication_attestation(
                attestation=att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is False
            assert ver["rejection_code"] == "MISSING_REPLICATION_RESULT_ARTIFACT"

    def test_neg_16_signing_key_rotation_enforces_lifecycle_policy(self):
        """16. Signing-key rotation: old valid signatures remain verifiable (HISTORICAL_VERIFY_ONLY),
        new signing with old key fails closed (SIGNING_KEY_NOT_AUTHORIZED), new key signs and verifies.
        """
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_REPLICATION_ATTESTATION,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        old_key = "cbe-test-rot-key-v1"
        new_key = "cbe-test-rot-key-v2"

        signing_key_registry.register_key(
            old_key,
            "isolated-rotation-secret-v1-1111",
            is_active=True,
            allowed_purposes=(KEY_PURPOSE_REPLICATION_ATTESTATION,),
            is_test_key=True,
        )
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=(old_key, new_key)
        )
        try:
            # 1. Sign with old_key while it is active
            att_v1 = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id=old_key,
                authority_context=auth_ctx,
            )

            # 2. Rotate old_key -> new_key (keep_old_for_verification=True)
            signing_key_registry.rotate_key(
                old_key_id=old_key,
                new_key_id=new_key,
                new_secret="isolated-rotation-secret-v2-2222",
                allowed_purposes=(KEY_PURPOSE_REPLICATION_ATTESTATION,),
                keep_old_for_verification=True,
                is_test_key=True,
            )

            # 3. Historical signature created before rotation remains verifiable
            ver_v1 = fw.verify_replication_attestation(
                attestation=att_v1,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver_v1["is_valid"] is True
            assert ver_v1["verified_key_id"] == old_key

            # 4. New signing attempt with rotated-out old_key fails closed!
            with pytest.raises(SigningAuthorityError) as exc_old:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=old_key,
                    authority_context=auth_ctx,
                )
            assert exc_old.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

            # 5. New active key signs and verifies cleanly
            att_v2 = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id=new_key,
                authority_context=auth_ctx,
            )
            ver_v2 = fw.verify_replication_attestation(
                attestation=att_v2,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver_v2["is_valid"] is True
            assert ver_v2["verified_key_id"] == new_key
        finally:
            signing_key_registry.remove_key(old_key)
            signing_key_registry.remove_key(new_key)

    def test_neg_17_verification_only_runtime_attempting_signing_rejected(self):
        """17. Verification-only runtime attempting signing -> Rejected (SIGNING_OPERATION_NOT_PERMITTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_REPLICATION_ATTESTATION,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )

        # Default application runtime mode must be VERIFICATION_ONLY
        assert signing_key_registry.get_runtime_signing_mode() == "VERIFICATION_ONLY"

        op_key = "cbe-test-op-key-17"
        signing_key_registry.register_key(
            op_key,
            "isolated-operator-secret-17-abcd",
            is_active=True,
            allowed_purposes=(KEY_PURPOSE_REPLICATION_ATTESTATION,),
            is_test_key=False,
        )
        # 1. Attempting to authorize operator signing in default VERIFICATION_ONLY runtime -> rejected
        with pytest.raises(SigningAuthorityError) as exc_op:
            SigningAuthorityContext.authorize_operator_signing(
                operator_token="test-operator-token-123456",
                allowed_key_ids=(op_key,),
            )
        assert exc_op.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

        # 2. Attempting to sign in VERIFICATION_ONLY runtime mode -> rejected
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(allowed_key_ids=(op_key,))
        kwargs = self._base_replication_kwargs()
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id=op_key,
                    authority_context=auth_ctx,
                    runtime_mode="VERIFICATION_ONLY",
                )
            assert exc_info.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"
        finally:
            auth_ctx.close()
            signing_key_registry.remove_key(op_key)

    def test_neg_18_test_signing_authority_leaking_into_application_runtime_rejected(self):
        """18. Test signing authority leaking into application runtime -> Rejected."""
        from coin_behavior_engine.product.credential_manager import (
            SigningAuthorityError,
            signing_key_registry,
        )

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-leak-key-18",
            secret="isolated-test-leak-secret-18",
        ) as auth_ctx:
            # A. Attempting to use test authority_context in AUTHORIZED_OPERATOR_SIGNING mode -> rejected
            with pytest.raises(SigningAuthorityError) as exc_mode:
                IndependentValidationFramework.create_signed_replication_attestation(
                    **kwargs,
                    key_id="cbe-test-leak-key-18",
                    authority_context=auth_ctx,
                    runtime_mode="AUTHORIZED_OPERATOR_SIGNING",
                )
            assert exc_mode.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-leak-key-18",
                authority_context=auth_ctx,
            )

        # B. Outside the isolated_test_signing_context block:
        # 1) Reuse of exited test authority_context fails closed with SIGNING_OPERATION_NOT_PERMITTED
        with pytest.raises(SigningAuthorityError) as exc_leaked:
            IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-leak-key-18",
                authority_context=auth_ctx,
            )
        assert exc_leaked.value.rejection_code in (
            "SIGNING_OPERATION_NOT_PERMITTED",
            "SIGNING_KEY_NOT_FOUND",
            "SIGNING_AUTHORITY_NOT_GRANTED",
        )

        # 2) Test key is automatically purged from registry after context exit, so verification in app runtime rejects it
        assert signing_key_registry.has_key("cbe-test-leak-key-18") is False
        ver_after = fw.verify_replication_attestation(
            attestation=att,
            primary_record_id=kwargs["primary_record_id"],
            candidate_record_id=kwargs["candidate_record_id"],
            primary_dataset_id=kwargs["primary_dataset_id"],
            candidate_dataset_id=kwargs["candidate_dataset_id"],
            primary_source_sha256=kwargs["primary_source_sha256"],
            candidate_source_sha256=kwargs["candidate_source_sha256"],
            primary_procedure_id=kwargs["primary_procedure_id"],
            candidate_procedure_id=kwargs["candidate_procedure_id"],
        )
        assert ver_after["is_valid"] is False
        assert ver_after["rejection_code"] == "SIGNING_KEY_NOT_FOUND"

    def test_neg_19_signature_cache_reuse_after_revocation_rejected(self):
        """19. Signature cache reuse after revocation -> Rejected (REVOKED_SIGNING_KEY)."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-cache-rev-key-19",
            secret="isolated-test-cache-rev-secret-19",
        ) as auth_ctx:
            att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-cache-rev-key-19",
                authority_context=auth_ctx,
            )
            # First verification succeeds and populates attestation_cache
            ver_1 = fw.verify_replication_attestation(
                attestation=att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver_1["is_valid"] is True

            # Revoke key after cache population
            signing_key_registry.revoke_key("cbe-test-cache-rev-key-19")

            # Subsequent verification must NOT serve stale cached valid result; must reject with REVOKED_SIGNING_KEY
            ver_2 = fw.verify_replication_attestation(
                attestation=att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver_2["is_valid"] is False
            assert ver_2["rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_neg_20_valid_signature_with_insufficient_scientific_independence_rejected(self):
        """20. Replication claim with valid signature but insufficient scientific independence -> Rejected."""
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        res_rel = "research_outputs/sprint26_advanced_scientific_validation/08_independent_validation_criteria.json"
        res_sha = hashlib.sha256((Path.cwd() / res_rel).read_bytes()).hexdigest()
        q1_1h_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet").read_bytes()
        ).hexdigest()
        q1_15m_sha = hashlib.sha256(
            (Path.cwd() / "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet").read_bytes()
        ).hexdigest()

        # Both datasets cover Q1 2024 (overlapping temporal window & observations), even though signature is valid!
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-overlap-key-20",
            secret="isolated-test-overlap-secret-20",
        ) as auth_ctx:
            valid_sig_overlapping_att = IndependentValidationFramework.create_signed_replication_attestation(
                replication_attempt_id="REP-OVERLAPPING-Q1-2024",
                primary_record_id="STUDY-Q1-1H",
                candidate_record_id="STUDY-Q1-15M",
                primary_dataset_id="DS-BTC-1H-Q1-2024",
                candidate_dataset_id="DS-BTC-15M-Q1-2024",
                primary_source_sha256=q1_1h_sha,
                candidate_source_sha256=q1_15m_sha,
                result_artifact_path=res_rel,
                result_artifact_sha256=res_sha,
                hypothesis_id="HYP-PAT-SIM-S26",
                methodology_id="CBE-0.7.0-CANONICAL",
                primary_procedure_id="PROC-PRIMARY-01",
                candidate_procedure_id="PROC-INDEPENDENT-02",
                procedure_version="SPRINT26-V1.0",
                independent_execution_lineage="EXEC-LINEAGE-INDEPENDENT-2026",
                key_id="cbe-test-overlap-key-20",
                authority_context=auth_ctx,
            )
            audit = fw.evaluate_validation_independence(
                primary_study={
                    "record_id": "STUDY-Q1-1H",
                    "dataset_id": "DS-BTC-1H-Q1-2024",
                    "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
                    "procedure_id": "PROC-PRIMARY-01",
                },
                candidate_study={
                    "record_id": "STUDY-Q1-15M",
                    "dataset_id": "DS-BTC-15M-Q1-2024",
                    "source_path": "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
                    "procedure_id": "PROC-INDEPENDENT-02",
                    "replication_attestation": valid_sig_overlapping_att,
                },
                claimed_category="INDEPENDENT_REPLICATION",
            )
            assert audit.independence_established is False
            assert audit.assigned_category == "INDEPENDENCE_NOT_ESTABLISHED"
            assert audit.eight_point_checks["time_window_overlap"]["passed"] is False

    def test_pos_21_authorized_signing_with_isolated_test_key_and_scientific_independence(self):
        """Positive test: isolated test signing key + explicit SigningAuthorityContext +
        verified non-overlapping datasets + verified replication artifact -> INDEPENDENT_REPLICATION.
        """
        from coin_behavior_engine.product.credential_manager import signing_key_registry

        fw = IndependentValidationFramework()
        kwargs = self._base_replication_kwargs()

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-pos-rep-key-21",
            secret="isolated-test-pos-rep-secret-21-9876",
        ) as auth_ctx:
            signed_att = IndependentValidationFramework.create_signed_replication_attestation(
                **kwargs,
                key_id="cbe-test-pos-rep-key-21",
                authority_context=auth_ctx,
            )
            ver = fw.verify_replication_attestation(
                attestation=signed_att,
                primary_record_id=kwargs["primary_record_id"],
                candidate_record_id=kwargs["candidate_record_id"],
                primary_dataset_id=kwargs["primary_dataset_id"],
                candidate_dataset_id=kwargs["candidate_dataset_id"],
                primary_source_sha256=kwargs["primary_source_sha256"],
                candidate_source_sha256=kwargs["candidate_source_sha256"],
                primary_procedure_id=kwargs["primary_procedure_id"],
                candidate_procedure_id=kwargs["candidate_procedure_id"],
            )
            assert ver["is_valid"] is True
            assert ver["rejection_code"] is None
            assert ver["verified_key_id"] == "cbe-test-pos-rep-key-21"

            audit = fw.evaluate_validation_independence(
                primary_study={
                    "record_id": kwargs["primary_record_id"],
                    "dataset_id": kwargs["primary_dataset_id"],
                    "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
                    "period_start_utc": "2024-01-01T00:00:00Z",
                    "period_end_utc": "2024-03-31T23:00:00Z",
                    "preprocessing_lineage_id": "PREP-Q1-ISOLATED",
                    "procedure_id": kwargs["primary_procedure_id"],
                },
                candidate_study={
                    "record_id": kwargs["candidate_record_id"],
                    "dataset_id": kwargs["candidate_dataset_id"],
                    "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
                    "period_start_utc": "2025-01-01T00:00:00Z",
                    "period_end_utc": "2025-01-31T23:00:00Z",
                    "preprocessing_lineage_id": "PREP-JAN25-ISOLATED",
                    "procedure_id": kwargs["candidate_procedure_id"],
                    "replication_attestation": signed_att,
                },
                claimed_category="INDEPENDENT_REPLICATION",
            )
            assert audit.independence_established is True
            assert audit.assigned_category == "INDEPENDENT_REPLICATION"
            assert audit.trust_progression_state == "INDEPENDENT_REPLICATION"
            assert audit.eight_point_checks["researcher_or_procedure_independence"]["passed"] is True


# ===========================================================================
# 9. SPRINT 26 FINAL INTAKE SIGNING TRUST CLOSURE — 20 NEGATIVE + POSITIVE TESTS
# ===========================================================================


class TestSprint26FinalIntakeSigningTrustClosure:
    """
    Comprehensive negative and positive test suite for Sprint 26 Final Intake Signing Trust Closure
    (CBE_SPRINT26_FINAL_INTAKE_SIGNING_TRUST_CLOSURE).
    Verifies P0 Dataset Intake Manifest Signing Isolation & Unified Signing Authority.
    """

    @staticmethod
    def _base_intake_kwargs() -> Dict[str, Any]:
        src = Path.cwd() / "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet"
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        return {
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "artifact_hashes": {
                "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": sha
            },
            "source_lineage": "BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
        }

    def test_neg_01_caller_supplied_intake_signing_secret_rejected(self):
        """1. Caller-supplied intake signing secret -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-01",
            secret="isolated-test-intake-secret-01",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            for bad_field in ("secret", "signing_secret", "key_secret", "raw_secret"):
                with pytest.raises(SigningAuthorityError) as exc_info:
                    ScientificReadinessEvaluator.create_signed_intake_manifest(
                        **kwargs,
                        key_id="cbe-test-intake-key-01",
                        authority_context=auth_ctx,
                        **{bad_field: "caller-supplied-intake-secret-bypass"},
                    )
                assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_neg_02_caller_supplied_forged_signature_rejected(self):
        """2. Caller-supplied forged_signature -> Rejected (SIGNING_AUTHORITY_NOT_GRANTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-02",
            secret="isolated-test-intake-secret-02",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-key-02",
                    authority_context=auth_ctx,
                    forged_signature="hmac-sha256:cbe-test-intake-key-02:" + ("f" * 64),
                )
            assert exc_info.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_03_missing_signing_authority_context_rejected(self):
        """3. Missing signing authority context -> Rejected (SIGNING_AUTHORITY_NOT_GRANTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-03",
            secret="isolated-test-intake-secret-03",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ):
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-key-03",
                    authority_context=None,
                )
            assert exc_info.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_04_boolean_authorization_flag_rejected(self):
        """4. Boolean authorization flag -> Rejected (SIGNING_AUTHORITY_NOT_GRANTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-04",
            secret="isolated-test-intake-secret-04",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            for flag_kw in (
                {"is_admin": True},
                {"authorized": True},
                {"is_authorized": True},
                {"bypass_authority": True},
            ):
                with pytest.raises(SigningAuthorityError) as exc_info:
                    ScientificReadinessEvaluator.create_signed_intake_manifest(
                        **kwargs,
                        key_id="cbe-test-intake-key-04",
                        authority_context=auth_ctx,
                        **flag_kw,
                    )
                assert exc_info.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

            # Passing boolean True directly as authority_context -> rejected
            with pytest.raises(SigningAuthorityError) as exc_bool:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-key-04",
                    authority_context=True,  # type: ignore[arg-type]
                )
            assert exc_bool.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_05_forged_authority_context_rejected(self):
        """5. Forged authority context -> Rejected (SIGNING_AUTHORITY_NOT_GRANTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-05",
            secret="isolated-test-intake-secret-05",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ):
            forged_ctx = SigningAuthorityContext(
                context_id="forged-ctx-999",
                authority_principal="FORGED_CALLER",
                allowed_purposes={KEY_PURPOSE_INTAKE_MANIFEST},
                allowed_key_ids={"cbe-test-intake-key-05"},
                environment_scope="test_isolated",
                is_test_authority=True,
                capability_seal="f" * 64,
            )
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-key-05",
                    authority_context=forged_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_06_revoked_signing_key_rejected(self):
        """6. Revoked signing key -> Rejected (SIGNING_KEY_REVOKED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-revoked-06",
            secret="isolated-test-intake-secret-06",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            signing_key_registry.revoke_key("cbe-test-intake-revoked-06")
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-revoked-06",
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_REVOKED"

    def test_neg_07_unknown_signing_key_rejected(self):
        """7. Unknown signing key -> Rejected (SIGNING_KEY_NOT_FOUND)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=["cbe-nonexistent-intake-key-07"],
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-nonexistent-intake-key-07",
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_FOUND"
        finally:
            auth_ctx.close()

    def test_neg_08_wrong_signing_key_purpose_rejected(self):
        """8. Wrong signing-key purpose -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_EVIDENCE_BUNDLE,
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        signing_key_registry.register_key(
            key_id="cbe-test-wrong-purpose-key-08",
            secret="isolated-test-wrong-purpose-secret-08",
            is_active=True,
            allowed_purposes=[KEY_PURPOSE_EVIDENCE_BUNDLE],  # Does NOT include KEY_PURPOSE_INTAKE_MANIFEST
            is_test_key=True,
        )
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=["cbe-test-wrong-purpose-key-08"],
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-wrong-purpose-key-08",
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"
        finally:
            auth_ctx.close()
            signing_key_registry.remove_key("cbe-test-wrong-purpose-key-08")

    def test_neg_09_verification_only_runtime_attempting_intake_signing_rejected(self):
        """9. Verification-only runtime attempting intake signing -> Rejected (SIGNING_OPERATION_NOT_PERMITTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-09",
            secret="isolated-test-intake-secret-09",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            for locked_mode in ("VERIFICATION_ONLY", "VERIFICATION_ONLY_LOCKED", "DISABLED"):
                with pytest.raises(SigningAuthorityError) as exc_info:
                    ScientificReadinessEvaluator.create_signed_intake_manifest(
                        **kwargs,
                        key_id="cbe-test-intake-key-09",
                        authority_context=auth_ctx,
                        runtime_mode=locked_mode,
                    )
                assert exc_info.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

    def test_neg_10_public_api_attempting_intake_signing_rejected(self):
        """10. Public API attempting intake signing -> Rejected (403 FORBIDDEN / SIGNING_OPERATION_NOT_PERMITTED)."""
        from http import HTTPStatus
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            public_api_request_guard,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        # A. Direct HTTP POST to /api/v1/product/workspace/intake-manifest/sign
        status_1, resp_1 = ProductDashboardApiService.handle_post_request(
            path="/api/v1/product/workspace/intake-manifest/sign",
            query_params={},
            body={"dataset_id": "DS-BTC-1H-Q1-2024", "create_intake_manifest": True},
        )
        assert status_1 == HTTPStatus.FORBIDDEN
        assert resp_1["rejection_code"] == "SIGNING_OPERATION_NOT_PERMITTED"

        # B. HTTP POST to /api/v1/product/workspace/walk-forward with create_intake_manifest=True
        status_2, resp_2 = ProductDashboardApiService.handle_post_request(
            path="/api/v1/product/workspace/walk-forward",
            query_params={},
            body={"dataset_id": "DS-BTC-1H-Q1-2024", "create_intake_manifest": True},
        )
        assert status_2 == HTTPStatus.FORBIDDEN
        assert resp_2["rejection_code"] == "SIGNING_OPERATION_NOT_PERMITTED"

        # C. Direct Python call inside public_api_request_guard()
        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-10",
            secret="isolated-test-intake-secret-10",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            with public_api_request_guard():
                with pytest.raises(SigningAuthorityError) as exc_info:
                    ScientificReadinessEvaluator.create_signed_intake_manifest(
                        **kwargs,
                        key_id="cbe-test-intake-key-10",
                        authority_context=auth_ctx,
                    )
                assert exc_info.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

    def test_neg_11_direct_sign_for_purpose_bypass_attempt_rejected(self):
        """11. Direct sign_for_purpose() bypass attempt without SigningAuthorityContext -> Rejected."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-11",
            secret="isolated-test-intake-secret-11",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ):
            # Calling sign_for_purpose() without authority_context must fail closed
            with pytest.raises(SigningAuthorityError) as exc_info:
                signing_key_registry.sign_for_purpose(
                    canonical_bytes=b'{"dataset_id":"DS-BTC-1H-Q1-2024"}',
                    key_id="cbe-test-intake-key-11",
                    required_purpose=KEY_PURPOSE_INTAKE_MANIFEST,
                )
            assert exc_info.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

    def test_neg_12_test_authority_leaking_into_staging_runtime_rejected(self):
        """12. Test authority leaking into staging runtime -> Rejected (SIGNING_OPERATION_NOT_PERMITTED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-leak-12",
            secret="isolated-test-intake-leak-secret-12",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            # A. Using test authority_context in AUTHORIZED_OPERATOR_SIGNING mode -> rejected
            with pytest.raises(SigningAuthorityError) as exc_mode:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-test-intake-leak-12",
                    authority_context=auth_ctx,
                    runtime_mode="AUTHORIZED_OPERATOR_SIGNING",
                )
            assert exc_mode.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"

        # B. Reusing exited test authority_context outside the with-block -> rejected
        with pytest.raises(SigningAuthorityError) as exc_leaked:
            ScientificReadinessEvaluator.create_signed_intake_manifest(
                **kwargs,
                key_id="cbe-test-intake-leak-12",
                authority_context=auth_ctx,
            )
        assert exc_leaked.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"
        assert signing_key_registry.has_key("cbe-test-intake-leak-12") is False

    def test_neg_13_invalid_signature_verification_rejected(self):
        """13. Invalid signature verification -> Rejected (SIGNATURE_VERIFICATION_FAILED)."""
        forged_manifest = TestSprint26FinalScientificTrustClosure._build_test_only_forged_intake_manifest(
            dataset_id="DS-BTC-1H-Q1-2024",
            artifact_hashes=self._base_intake_kwargs()["artifact_hashes"],
            source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
            key_id="k2026-v1",
            forged_signature="hmac-sha256:k2026-v1:" + ("b" * 64),
        )
        wf_lab = WalkForwardResearchLab()
        wf_res = wf_lab.run_walk_forward_evaluation(
            dataset_id="DS-BTC-1H-Q1-2024",
            intake_manifest=forged_manifest,
            require_explicit_evidence=True,
        )
        assert wf_res.status == "EVALUATION_BLOCKED"
        assert wf_res.dataset_provenance["provenance_rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_neg_14_source_artifact_hash_mismatch_rejected(self):
        """14. Source artifact hash mismatch -> Rejected (SOURCE_ARTIFACT_HASH_MISMATCH)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-14",
            secret="isolated-test-intake-secret-14",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            bad_hash_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                dataset_id="DS-BTC-1H-Q1-2024",
                artifact_hashes={
                    "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet": "e" * 64
                },
                source_lineage="BINANCE_SPOT_KLINES_BTCUSDT_1H_2024Q1",
                key_id="cbe-test-intake-key-14",
                authority_context=auth_ctx,
            )
            wf_lab = WalkForwardResearchLab()
            wf_res = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=bad_hash_manifest,
                require_explicit_evidence=True,
            )
            assert wf_res.status == "EVALUATION_BLOCKED"
            assert wf_res.dataset_provenance["provenance_rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

    def test_neg_15_manifest_dataset_id_mismatch_rejected(self):
        """15. Manifest dataset ID mismatch -> Rejected (DATASET_ID_MISMATCH)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-15",
            secret="isolated-test-intake-secret-15",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            wrong_id_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                dataset_id="DS-WRONG-DATASET-2024",
                artifact_hashes=kwargs["artifact_hashes"],
                source_lineage=kwargs["source_lineage"],
                key_id="cbe-test-intake-key-15",
                authority_context=auth_ctx,
            )
            wf_lab = WalkForwardResearchLab()
            wf_res = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=wrong_id_manifest,
                require_explicit_evidence=True,
            )
            assert wf_res.status == "EVALUATION_BLOCKED"
            assert wf_res.dataset_provenance["provenance_rejection_code"] == "DATASET_ID_MISMATCH"

    def test_neg_16_previously_valid_manifest_verification_after_signing_api_changes(self):
        """16. Previously valid manifest verification remains functional in VERIFICATION_ONLY runtime."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-key-16",
            secret="isolated-test-intake-secret-16",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
            remove_key_on_exit=False,
        ) as auth_ctx:
            valid_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                **kwargs,
                key_id="cbe-test-intake-key-16",
                authority_context=auth_ctx,
            )

        try:
            # Outside signing context (key is now HISTORICAL_VERIFY_ONLY and runtime is VERIFICATION_ONLY):
            # Verification of previously signed manifest succeeds across Walk-Forward & Regime Research
            wf_lab = WalkForwardResearchLab()
            wf_res = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=valid_manifest,
                require_explicit_evidence=True,
            )
            assert wf_res.status == "EVALUATION_COMPLETED"
            assert wf_res.dataset_provenance["is_verified"] is True

            reg_engine = HistoricalMarketRegimeResearchEngine()
            reg_res = reg_engine.run_regime_research(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=valid_manifest,
                require_explicit_evidence=True,
            )
            assert reg_res.status == "RESEARCH_COMPLETED"
            assert reg_res.verified_source_artifact["is_verified"] is True
        finally:
            signing_key_registry.remove_key("cbe-test-intake-key-16")

    def test_neg_17_signing_key_rotation_compatibility(self):
        """17. Signing-key rotation compatibility: old key verifies existing manifests but cannot sign new ones."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        signing_key_registry.register_key(
            key_id="cbe-intake-rot-old-17",
            secret="intake-rot-old-secret-17",
            is_active=True,
            allowed_purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
            is_test_key=True,
        )
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=["cbe-intake-rot-old-17", "cbe-intake-rot-new-17"],
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
        )
        try:
            old_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                **kwargs,
                key_id="cbe-intake-rot-old-17",
                authority_context=auth_ctx,
            )
            # Rotate old -> new
            signing_key_registry.rotate_key(
                old_key_id="cbe-intake-rot-old-17",
                new_key_id="cbe-intake-rot-new-17",
                new_secret="intake-rot-new-secret-17",
                allowed_purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
                is_test_key=True,
                keep_old_for_verification=True,
            )
            # Old key cannot sign new manifests after rotation
            with pytest.raises(SigningAuthorityError) as exc_old:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="cbe-intake-rot-old-17",
                    authority_context=auth_ctx,
                )
            assert exc_old.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

            # Old manifest still verifies
            wf_lab = WalkForwardResearchLab()
            wf_old = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=old_manifest,
                require_explicit_evidence=True,
            )
            assert wf_old.status == "EVALUATION_COMPLETED"
            assert wf_old.dataset_provenance["is_verified"] is True

            # New key signs and verifies
            new_manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                **kwargs,
                key_id="cbe-intake-rot-new-17",
                authority_context=auth_ctx,
            )
            wf_new = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=new_manifest,
                require_explicit_evidence=True,
            )
            assert wf_new.status == "EVALUATION_COMPLETED"
            assert wf_new.dataset_provenance["is_verified"] is True
        finally:
            auth_ctx.close()
            signing_key_registry.remove_key("cbe-intake-rot-old-17")
            signing_key_registry.remove_key("cbe-intake-rot-new-17")

    def test_neg_18_signature_cache_invalidation_after_revocation(self):
        """18. Signature cache invalidation after revocation -> Rejected (REVOKED_SIGNING_KEY)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-cache-18",
            secret="isolated-test-intake-cache-secret-18",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            manifest = ScientificReadinessEvaluator.create_signed_intake_manifest(
                **kwargs,
                key_id="cbe-test-intake-cache-18",
                authority_context=auth_ctx,
            )
            wf_lab = WalkForwardResearchLab()
            res_1 = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=manifest,
                require_explicit_evidence=True,
            )
            assert res_1.status == "EVALUATION_COMPLETED"
            assert res_1.dataset_provenance["is_verified"] is True

            # Revoke key after cache population
            signing_key_registry.revoke_key("cbe-test-intake-cache-18")

            # Subsequent verification must NOT use stale cached valid result
            res_2 = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=manifest,
                require_explicit_evidence=True,
            )
            assert res_2.status == "EVALUATION_BLOCKED"
            assert res_2.dataset_provenance["provenance_rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_neg_19_trusted_signing_attempt_using_unregistered_secret_rejected(self):
        """19. Trusted signing attempt using an unregistered secret -> Rejected (SIGNING_KEY_NOT_AUTHORIZED)."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            SigningAuthorityContext,
            SigningAuthorityError,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        kwargs = self._base_intake_kwargs()
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=["unregistered-key-19"],
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc_info:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    **kwargs,
                    key_id="unregistered-key-19",
                    secret="unregistered-raw-secret-material-19",
                    authority_context=auth_ctx,
                )
            assert exc_info.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"
        finally:
            auth_ctx.close()

    def test_neg_20_unauthorized_signing_attempt_through_indirect_helper_rejected(self):
        """20. Unauthorized signing attempt through get_canonical_signed_intake_manifest -> Rejected."""
        from coin_behavior_engine.product.credential_manager import SigningAuthorityError
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        # A. Calling get_canonical_signed_intake_manifest without authority_context -> rejected
        with pytest.raises(SigningAuthorityError) as exc_no_auth:
            ScientificReadinessEvaluator.get_canonical_signed_intake_manifest(
                dataset_id="DS-BTC-1H-Q1-2024",
            )
        assert exc_no_auth.value.rejection_code == "SIGNING_AUTHORITY_NOT_GRANTED"

        # B. Calling get_canonical_signed_intake_manifest with caller-supplied secret -> rejected
        with pytest.raises(SigningAuthorityError) as exc_sec:
            ScientificReadinessEvaluator.get_canonical_signed_intake_manifest(
                dataset_id="DS-BTC-1H-Q1-2024",
                secret="caller-secret-bypass-attempt",
            )
        assert exc_sec.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_pos_21_authorized_intake_manifest_signing_and_cross_module_compatibility(self):
        """Positive test: isolated test signing context + KEY_PURPOSE_INTAKE_MANIFEST signs and verifies across modules."""
        from coin_behavior_engine.product.credential_manager import (
            KEY_PURPOSE_INTAKE_MANIFEST,
            signing_key_registry,
        )
        from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

        with signing_key_registry.isolated_test_signing_context(
            key_id="cbe-test-intake-pos-21",
            secret="isolated-test-intake-pos-secret-21",
            purposes=(KEY_PURPOSE_INTAKE_MANIFEST,),
        ) as auth_ctx:
            manifest = ScientificReadinessEvaluator.get_canonical_signed_intake_manifest(
                dataset_id="DS-BTC-1H-Q1-2024",
                key_id="cbe-test-intake-pos-21",
                authority_context=auth_ctx,
            )
            assert manifest is not None
            assert manifest["key_id"] == "cbe-test-intake-pos-21"
            assert manifest["signature"].startswith("hmac-sha256:cbe-test-intake-pos-21:")

            wf_lab = WalkForwardResearchLab()
            wf_res = wf_lab.run_walk_forward_evaluation(
                dataset_id="DS-BTC-1H-Q1-2024",
                intake_manifest=manifest,
                require_explicit_evidence=True,
            )
            assert wf_res.status == "EVALUATION_COMPLETED"
            assert wf_res.dataset_provenance["is_verified"] is True

    def test_pos_22_source_code_audit_no_direct_hmac_or_forged_signature_in_intake_signing(self):
        """Source-code audit: scientific_readiness.py contains zero direct hmac.new or forged_signature branches."""
        sr_src = (
            Path.cwd() / "src/coin_behavior_engine/product/scientific_readiness.py"
        ).read_text(encoding="utf-8")
        assert "hmac.new(" not in sr_src
        assert "elif secret is not None:" not in sr_src
        assert "if forged_signature is not None:" not in sr_src
        assert "signing_key_registry.sign_with_authority(" in sr_src




