"""Sprint 10.02 — Independent Calibration Verification, Regime Integrity & Product Data Contracts Test Suite.

Verifies:
1. Baseline commit verification (d844f6cf5af9b5511a3fd89ff95ae97debb2ed16) & prior artifacts preservation.
2. Exact denominator reconciliation: 6,328 prediction events -> 50,007 matured multi-horizon outcomes.
3. Chronological causality audit: prediction precedes target, mature residuals, no lookahead, embargo Eh >= h.
4. Conformal method selection audit: exploratory classification & 3-way chronological split protocol.
5. Independent coverage & sharpness audit across all 8 horizons (15m to 24h).
6. Effective sample size sensitivity analysis (k in [6, 12, 24, 48, 96]), confirming 24h INSUFFICIENT_EVIDENCE.
7. Volatility regime diagnostics & stress degradation under fat-tail shocks.
8. Offline reproduction of the single-row percentile collapse bug (x <= x) in CBE-0.7.0.
9. Corrected causal regime classifier candidate (UNKNOWN on history < 96 bars and in SPOT_ONLY_U0).
10. Product-facing data contracts schema compliance (all 10 domains with ContractField metadata).
11. Fail-closed display rules validation (regime, fallback probabilities, stale data, 24h suppression).
12. MVP feature readiness classification across 5 mandated tiers.
13. Adversarial tests (future outcome leakage, stale data, static probability mislabeling, short history).
14. Pure analytical compute latency budget (< 50 ms).
"""

from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.calibration import (
    CalibrationMethodType,
    CausalConformalCalibrator,
    ChronologicalCausalityAudit,
    CorrectedCausalRegimeClassifierCandidate,
    CorrectedRegimeResult,
    EffectiveSampleSizeSensitivity,
    IndependentCalibrationVerifier,
    MethodSelectionAudit,
    ProbabilityProvenanceType,
    SourceRecordReconciliation,
    Sprint1002MasterReport,
)
from coin_behavior_engine.product.data_contracts import (
    ContractField,
    FailClosedDisplayRuleEngine,
    FieldAvailabilityStatus,
    FieldFallbackStatus,
    ProductValidationStatus,
)


@pytest.fixture(scope="module")
def verifier() -> IndependentCalibrationVerifier:
    return IndependentCalibrationVerifier()


@pytest.fixture(scope="module")
def master_report(verifier: IndependentCalibrationVerifier) -> Sprint1002MasterReport:
    report_path = Path("data/reports/sprint10_02_independent_verification_report.json")
    contracts_path = Path("data/reports/sprint10_02_product_data_contracts.json")
    return verifier.run_full_sprint_verification(
        output_report_path=report_path,
        contracts_output_path=contracts_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint1002MasterReport):
    """Test 1: Verify baseline commit and preservation of all prior sprint reports."""
    assert master_report.baseline_commit_sha == "d844f6cf5af9b5511a3fd89ff95ae97debb2ed16"
    assert "10.02" in master_report.sprint_id

    # Verify prior sprint artifacts exist and remain intact
    prior_reports = [
        "data/reports/sprint09_36_delta_neutral_forensics_report.json",
        "data/reports/sprint09_37_carry_accounting_closure_report.json",
        "data/reports/sprint09_38_funding_predictability_report.json",
        "data/reports/sprint09_39_cross_instrument_funding_report.json",
        "data/reports/sprint09_40_multi_asset_carry_report.json",
        "data/reports/sprint09_41_multi_asset_carry_report.json",
        "data/reports/sprint09_42_master_report.json",
        "data/reports/sprint09_43_product_readiness_audit.json",
        "data/reports/sprint10_01_conformal_calibration_report.json",
        "data/reports/sprint10_01_calibration_contract.json",
    ]
    for rep in prior_reports:
        p = Path(rep)
        assert p.exists(), f"Prior report missing: {rep}"
        assert p.stat().st_size > 0, f"Prior report empty: {rep}"


def test_02_source_record_reconciliation(master_report: Sprint1002MasterReport):
    """Test 2: Independently reconcile 6,328 prediction events to 50,007 matured multi-horizon outcomes."""
    rec = master_report.reconciliation
    assert rec.prediction_event_count == 6328
    assert rec.matured_outcome_count == 50007
    assert rec.valid_evaluation_outcomes == 49855
    assert rec.invalid_legacy_v1_outcomes == 114
    assert rec.excluded_outcomes == 38
    assert rec.reconciliation_status == "EXACT_RECONCILIATION_CONFIRMED"

    # Verify individual horizon denominators
    expected_denoms = {
        "15m": 6325,
        "30m": 6322,
        "1h": 6316,
        "2h": 6304,
        "4h": 6281,
        "8h": 6233,
        "12h": 6185,
        "24h": 6041,
    }
    assert rec.horizon_denominators == expected_denoms
    assert sum(expected_denoms.values()) == rec.denominator_sum == 50007


def test_03_chronological_causality_audit(master_report: Sprint1002MasterReport):
    """Test 3: Verify machine-checkable point-in-time causality and lack of lookahead."""
    caus = master_report.causality_audit
    assert caus.prediction_precedes_target_pct == 100.0
    assert caus.residuals_mature_before_use is True
    assert caus.evaluation_leakage_into_calibration is False
    assert caus.random_shuffling_detected is False
    assert caus.future_features_detected is False
    assert caus.causality_verdict == "MACHINE_PROVEN_CAUSAL_NO_LOOKAHEAD"

    # Embargo must be at least the horizon bars
    assert caus.embargo_enforced_by_horizon["15m"] >= 1
    assert caus.embargo_enforced_by_horizon["1h"] >= 4
    assert caus.embargo_enforced_by_horizon["4h"] >= 16
    assert caus.embargo_enforced_by_horizon["24h"] >= 96


def test_04_conformal_method_selection_audit(master_report: Sprint1002MasterReport):
    """Test 4: Verify method selection audit classifies Sprint 10.01 as exploratory and formalizes 3-way split."""
    ms = master_report.method_selection_audit
    assert ms.selected_method == CalibrationMethodType.HORIZON_SPECIFIC_SPLIT_CONFORMAL.value
    assert ms.evaluation_data_exposed_in_selection is True
    assert ms.data_exposure_status == "EXPLORATORY_NOT_VIRGIN_HOLDOUT"

    # Formal 3-way split must be defined
    split = ms.formal_three_way_split_protocol
    assert "fold_1_training_reference" in split
    assert "fold_2_calibration_split" in split
    assert "fold_3_post_embargo_holdout" in split


def test_05_independent_coverage_and_sharpness(master_report: Sprint1002MasterReport):
    """Test 5: Verify empirical coverage across all 8 horizons."""
    horizs = master_report.horizon_coverage_results
    assert len(horizs) == 8

    # 15m to 4h must meet +/- 2.5% tolerance
    for h in ["15m", "30m", "1h", "2h", "4h"]:
        res = horizs[h]
        assert abs(res.empirical_coverage_80 - 0.80) <= 0.025
        assert abs(res.empirical_coverage_95 - 0.95) <= 0.025
        assert 1.20 <= res.width_inflation_factor_80 <= 1.40
        assert 1.25 <= res.width_inflation_factor_95 <= 1.50

    # 24h must be INSUFFICIENT_EVIDENCE
    assert horizs["24h"].decision_gate == "INSUFFICIENT_EVIDENCE"


def test_06_effective_sample_size_sensitivity(master_report: Sprint1002MasterReport):
    """Test 6: Verify sensitivity of effective sample size across block lengths k in [6..96]."""
    eff = master_report.effective_sample_sensitivity
    assert "24h" in eff
    assert eff["24h"].heuristic_n_eff == 62
    assert eff["24h"].decision_gate == ProductValidationStatus.INSUFFICIENT_EVIDENCE.value

    # Verify 8h and 12h are VALIDATED_WITH_LIMITATIONS
    assert eff["8h"].decision_gate == ProductValidationStatus.VALIDATED_WITH_LIMITATIONS.value
    assert eff["12h"].decision_gate == ProductValidationStatus.VALIDATED_WITH_LIMITATIONS.value

    # Verify 15m through 4h are VALIDATED_FOR_PRODUCT
    for h in ["15m", "30m", "1h", "2h", "4h"]:
        assert eff[h].decision_gate == ProductValidationStatus.VALIDATED_FOR_PRODUCT.value
        assert eff[h].heuristic_n_eff >= 390

    # Sensitivity checks across blocks
    sens_24h = eff["24h"].block_sensitivity
    assert "block_k_6" in sens_24h
    assert "block_k_96" in sens_24h


def test_07_stress_regime_diagnostics(master_report: Sprint1002MasterReport):
    """Test 7: Verify coverage diagnostics across volatility terciles and stress degradation."""
    diags = master_report.stress_regime_diagnostics
    assert len(diags) == 3

    # Calm and Normal regimes do not degrade
    assert diags[0].stress_degradation_observed is False
    assert diags[1].stress_degradation_observed is False

    # Event shock regime shows observed stress degradation
    assert diags[2].stress_degradation_observed is True
    assert diags[2].uncalibrated_coverage_80 < 0.60
    assert diags[2].conformal_coverage_80 > 0.75


def test_08_offline_regime_bug_reproduction(master_report: Sprint1002MasterReport):
    """Test 8: Verify offline reproduction of the single-row percentile collapse bug."""
    rep = master_report.regime_bug_reproduction
    assert rep["reproduction_verdict"] == "CONFIRMED_DETERMINISTIC_BUG_REPRODUCED"
    assert rep["frozen_code_intact"] is True

    # Check test cases: all must have locked to DELEVERAGING_STRESS due to x <= x
    for tc in rep["test_cases_evaluated"]:
        assert tc["cond_delev_evaluated"] is True
        assert tc["resulting_state"] == "DELEVERAGING_STRESS"


def test_09_corrected_causal_regime_classifier_candidate():
    """Test 9: Verify CorrectedCausalRegimeClassifierCandidate enforces causal history and UNKNOWN states."""
    # 1. Insufficient history (< 96 bars) -> must return UNKNOWN
    short_hist = pd.DataFrame({
        "volatility_realized_24h": [0.01] * 50,
        "volatility_compression_ratio": [1.0] * 50,
    })
    res_short = CorrectedCausalRegimeClassifierCandidate.classify_bar(
        current_bar={"volatility_realized_24h": 0.01, "volatility_compression_ratio": 1.0},
        history_df=short_hist,
    )
    assert res_short.state_id == "UNKNOWN"
    assert res_short.fallback_used is True
    assert "Yetersiz Tarihsel Veri" in res_short.display_label

    # 2. Sufficient history (120 bars) in SPOT_ONLY_U0 mode -> must evaluate spot regimes, NOT deleveraging
    rng = np.random.default_rng(123)
    valid_hist = pd.DataFrame({
        "volatility_realized_24h": rng.normal(0.015, 0.003, size=120),
        "volatility_compression_ratio": rng.normal(1.0, 0.15, size=120),
    })
    res_spot = CorrectedCausalRegimeClassifierCandidate.classify_bar(
        current_bar={"volatility_realized_24h": 0.015, "volatility_compression_ratio": 1.0},
        history_df=valid_hist,
        data_mode="SPOT_ONLY_U0",
    )
    assert res_spot.state_id in ("NORMAL", "QUIET", "COMPRESSION", "HIGH_VOLATILITY")
    assert res_spot.state_id != "DELEVERAGING_STRESS"
    assert res_spot.is_spot_only is True

    # 3. Missing spot features (NaN) -> must return UNKNOWN
    res_nan = CorrectedCausalRegimeClassifierCandidate.classify_bar(
        current_bar={"volatility_realized_24h": np.nan, "volatility_compression_ratio": np.nan},
        history_df=valid_hist,
    )
    assert res_nan.state_id == "UNKNOWN"
    assert "Eksik Spot Özellikler" in res_nan.display_label


def test_10_product_data_contracts_schema(master_report: Sprint1002MasterReport):
    """Test 10: Verify all 10 product data contracts conform to schema requirements."""
    contracts = master_report.product_contracts_summary
    expected_contracts = [
        "market_overview",
        "market_regime",
        "volatility_diagnostics",
        "prediction_diagnostics",
        "calibration_status",
        "data_freshness",
        "probability_provenance",
        "model_version",
        "feature_availability",
        "experimental_warnings",
    ]
    assert list(contracts.keys()) == expected_contracts

    # Check field integrity in market_overview
    mo = contracts["market_overview"]
    assert mo["symbol"]["value"] == "BTCUSDT"
    assert mo["symbol"]["validation_status"] == ProductValidationStatus.VALIDATED_FOR_PRODUCT.value

    # Check that tail risk and jump risk in probability_provenance have fallback status
    prob = contracts["probability_provenance"]
    assert prob["tail_risk_probability"]["fallback_status"] == FieldFallbackStatus.STATIC_FALLBACK_CONSTANT.value
    assert prob["jump_risk_probability"]["fallback_status"] == FieldFallbackStatus.STATIC_FALLBACK_CONSTANT.value

    # Check that 24h prediction interval is suppressed / flagged INSUFFICIENT_EVIDENCE
    pred = contracts["prediction_diagnostics"]
    assert pred["conformal_band_80_24h_bps"]["validation_status"] == ProductValidationStatus.INSUFFICIENT_EVIDENCE.value


def test_11_fail_closed_display_rules():
    """Test 11: Verify fail-closed display rule engine enforcement."""
    # Rule 1: Regime fail-closed to UNKNOWN
    sanitized_regime = FailClosedDisplayRuleEngine.sanitize_regime_display(
        raw_state="DELEVERAGING_STRESS",
        history_length=1,
        data_mode="SPOT_ONLY_U0",
        is_computed_causally=False,
    )
    assert sanitized_regime["display_state"] == "UNKNOWN"
    assert sanitized_regime["suppressed"] is True

    # Rule 2: Static fallback probability cannot be labeled live prediction
    sanitized_prob = FailClosedDisplayRuleEngine.sanitize_probability_display(
        prob_name="tail_risk_probability",
        prob_value=0.05,
        provenance_type=ProbabilityProvenanceType.STATIC_FALLBACK_CONSTANT.value,
    )
    assert sanitized_prob["is_live_prediction"] is False
    assert "Statik Güvenlik Sabiti" in sanitized_prob["display_label"]

    # Rule 3: 24h horizon confidence claims suppressed
    sanitized_24h = FailClosedDisplayRuleEngine.sanitize_horizon_conformal_display(
        horizon_name="24h",
        nominal_cov=0.80,
        empirical_cov=0.788,
        effective_sample_size=62,
    )
    assert sanitized_24h["display_allowed"] is False
    assert sanitized_24h["validation_status"] == ProductValidationStatus.INSUFFICIENT_EVIDENCE.value

    # Rule 4: Data staleness
    stale_check = FailClosedDisplayRuleEngine.check_data_freshness(
        latest_bar_ts="2026-09-24T00:00:00Z",
        current_ts="2026-09-24T01:00:00Z",  # 60 min late
    )
    assert stale_check["is_stale"] is True
    assert "DİKKAT: Veri akışı" in stale_check["warning_message"]


def test_12_mvp_feature_readiness_classification(master_report: Sprint1002MasterReport):
    """Test 12: Verify accurate categorization of MVP features into 5 readiness tiers."""
    readiness = master_report.mvp_feature_readiness
    assert readiness["realized_volatility_term_structure_15m_4h"] == ProductValidationStatus.VALIDATED_FOR_PRODUCT.value
    assert readiness["conformal_uncertainty_intervals_15m_4h"] == ProductValidationStatus.VALIDATED_FOR_PRODUCT.value
    assert readiness["conformal_uncertainty_intervals_8h_12h"] == ProductValidationStatus.VALIDATED_WITH_LIMITATIONS.value
    assert readiness["corrected_causal_market_regime_classifier"] == ProductValidationStatus.EXPERIMENTAL_ONLY.value
    assert readiness["prediction_and_conformal_coverage_24h"] == ProductValidationStatus.INSUFFICIENT_EVIDENCE.value
    assert readiness["live_spot_only_deleveraging_stress_score"] == ProductValidationStatus.BLOCKED_BY_DATA_QUALITY.value


def test_13_adversarial_checks(verifier: IndependentCalibrationVerifier):
    """Test 13: Adversarial tests for leakage, duplicate mappings, and missing data fallbacks."""
    # 1. Leakage check: test causality audit
    caus = verifier.audit_chronological_causality()
    assert caus.evaluation_leakage_into_calibration is False

    # 2. Freshness check: normal latency (10 min) should not be marked stale
    fresh_check = FailClosedDisplayRuleEngine.check_data_freshness(
        latest_bar_ts="2026-09-24T00:00:00Z",
        current_ts="2026-09-24T00:10:00Z",
    )
    assert fresh_check["is_stale"] is False

    # 3. ModelDerived probability can be labeled live prediction
    live_prob = FailClosedDisplayRuleEngine.sanitize_probability_display(
        prob_name="directional_probability_up",
        prob_value=0.55,
        provenance_type=ProbabilityProvenanceType.MODEL_DERIVED.value,
    )
    assert live_prob["is_live_prediction"] is True


def test_14_pure_analytical_compute_latency_budget(verifier: IndependentCalibrationVerifier):
    """Test 14: Verify pure analytical compute runs well under 50 ms budget."""
    t0 = time.perf_counter()
    verifier.reconcile_source_records()
    verifier.audit_chronological_causality()
    verifier.audit_conformal_method_selection()
    verifier.audit_effective_sample_size_sensitivity()
    verifier.reproduce_regime_classifier_bug()
    verifier.audit_mvp_feature_readiness()
    verifier.build_product_data_contracts()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"
