"""Sprint 10.01 — Comprehensive Unit & Conformal Calibration Test Suite.

Verifies:
1. Baseline commit verification (c0042d1707a76b638d19baebfd1a1d46535b9dac) and prior sprint artifacts preservation.
2. Exact mathematical reproduction of baseline interval undercoverage (80% -> 64.24%, 95% -> 78.94%).
3. Strict chronological calibration split design with horizon embargo.
4. Independent horizon-level breakdown across all 8 horizons (15m, 30m, 1h, 2h, 4h, 8h, 12h, 24h).
5. Moving block bootstrap (k=12) uncertainty quantification and effective sample sizing.
6. Conformal candidate evaluation (Horizon-Specific Split Conformal meets +/- 2.5% tolerance for 15m to 4h).
7. Volatility regime diagnostics (Calm, Normal, High Volatility / Event Shock).
8. Forensic audit of the DELEVERAGING_STRESS state lock (single-row percentile collapse bug).
9. Probability provenance taxonomy (separating model-derived from static fallbacks 0.05/0.01).
10. Conformal calibration contract schema and JSON artifact serialization.
11. Adversarial tests: empty calibration set, insufficient sample gating, and fallback misclassification.
12. Pure analytical compute latency budget (< 50 ms).
"""

import json
import time
from pathlib import Path

import numpy as np
import pytest

from coin_behavior_engine.calibration import (
    CalibrationMethodType,
    CausalConformalCalibrator,
    ConformalCalibrationContract,
    HorizonCoverageResult,
    HorizonDecisionGate,
    ProbabilityProvenanceType,
    RegimeCoverageDiagnostic,
    RegimeClassifierAuditRecord,
    Sprint1001MasterReport,
)


@pytest.fixture(scope="module")
def calibrator() -> CausalConformalCalibrator:
    return CausalConformalCalibrator()


@pytest.fixture(scope="module")
def master_report(calibrator: CausalConformalCalibrator) -> Sprint1001MasterReport:
    report_path = Path("data/reports/sprint10_01_conformal_calibration_report.json")
    contract_path = Path("data/reports/sprint10_01_calibration_contract.json")
    return calibrator.run_full_sprint_audit(
        output_report_path=report_path,
        contract_output_path=contract_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint1001MasterReport):
    """Test 1: Verify baseline commit and prior sprint artifacts preservation."""
    assert master_report.baseline_commit_sha == "c0042d1707a76b638d19baebfd1a1d46535b9dac"
    assert "10.01" in master_report.sprint_id

    # Prior sprint artifacts must exist and remain untouched
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/reports/sprint09_39_cross_instrument_funding_report.json").exists()
    assert Path("data/reports/sprint09_40_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_41_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_42_master_report.json").exists()
    assert Path("data/reports/sprint09_43_product_readiness_audit.json").exists()
    assert Path("data/reports/sprint09_43_mvp_roadmap.json").exists()


def test_02_baseline_calibration_reproduction(master_report: Sprint1001MasterReport):
    """Test 2: Verify exact mathematical reproduction of uncalibrated baseline undercoverage."""
    base = master_report.baseline_reproduction
    assert base["nominal_80_overall_empirical_coverage"] == 0.6424
    assert base["nominal_95_overall_empirical_coverage"] == 0.7894
    assert base["reproduction_status"] == "EXACT_REPRODUCTION_VERIFIED"
    assert base["z_stat_80"] < -25.0
    assert base["z_stat_95"] < -30.0


def test_03_horizon_level_coverage_breakdown(master_report: Sprint1001MasterReport):
    """Test 3: Verify all 8 prediction horizons are evaluated with distinct metrics."""
    horizons = master_report.horizon_results
    expected_horizons = ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h"]
    assert list(horizons.keys()) == expected_horizons

    for h in expected_horizons:
        res = horizons[h]
        assert res.sample_size_total >= 6000
        assert res.effective_sample_size <= res.sample_size_total

        # Width inflation factors must be reasonable (1.20x to 1.55x)
        assert 1.20 <= res.width_inflation_factor_80 <= 1.45
        assert 1.25 <= res.width_inflation_factor_95 <= 1.55

        # Block bootstrap CI must encompass the point estimate
        assert res.block_bootstrap_ci_80[0] <= res.empirical_coverage_80 <= res.block_bootstrap_ci_80[1]
        assert res.block_bootstrap_ci_95[0] <= res.empirical_coverage_95 <= res.block_bootstrap_ci_95[1]


def test_04_intraday_horizons_conformal_validation(master_report: Sprint1001MasterReport):
    """Test 4: Verify that intraday horizons (15m to 4h) meet the +/- 2.5% tolerance gate."""
    horizons = master_report.horizon_results

    for h in ["15m", "30m", "1h", "2h", "4h"]:
        res = horizons[h]
        assert res.target_tolerance_met_80 is True
        assert res.target_tolerance_met_95 is True
        assert res.decision_gate == HorizonDecisionGate.CALIBRATION_VALIDATED.value

        # Coverage must be strictly within [77.5%, 82.5%] and [92.5%, 97.5%]
        assert 0.775 <= res.empirical_coverage_80 <= 0.825
        assert 0.925 <= res.empirical_coverage_95 <= 0.975


def test_05_insufficient_sample_gating_for_long_horizons(master_report: Sprint1001MasterReport):
    """Test 5: Verify that long horizons (8h, 12h, 24h) with small effective samples are gated."""
    horizons = master_report.horizon_results

    for h in ["8h", "12h", "24h"]:
        res = horizons[h]
        assert res.effective_sample_size < 200
        # If N_eff < 100 (e.g. 24h N_eff = 62), it MUST be gated as INSUFFICIENT_EVIDENCE
        if res.effective_sample_size < 100:
            assert res.decision_gate == HorizonDecisionGate.INSUFFICIENT_EVIDENCE.value


def test_06_conformal_candidate_comparison(master_report: Sprint1001MasterReport):
    """Test 6: Verify comparison across the 4 candidate calibration methods."""
    cands = master_report.candidate_comparison_summary
    assert "UNCALIBRATED_BASELINE" in cands
    assert "GLOBAL_SPLIT_CONFORMAL" in cands
    assert "HORIZON_SPECIFIC_SPLIT_CONFORMAL" in cands
    assert "ROLLING_WINDOW_CAUSAL_CONFORMAL" in cands

    uncal = cands["UNCALIBRATED_BASELINE"]
    assert "FAILED" in uncal["assessment"]

    rec = cands["HORIZON_SPECIFIC_SPLIT_CONFORMAL"]
    assert "RECOMMENDED" in rec["assessment"]
    assert abs(rec["coverage_gap_80"]) < 0.010
    assert abs(rec["coverage_gap_95"]) < 0.010


def test_07_volatility_regime_diagnostics(master_report: Sprint1001MasterReport):
    """Test 7: Verify coverage diagnostics across Calm, Normal, and High Volatility regimes."""
    diags = master_report.regime_diagnostics
    assert len(diags) == 3

    calm = next(d for d in diags if "CALM" in d.regime_name)
    normal = next(d for d in diags if "NORMAL" in d.regime_name)
    high_vol = next(d for d in diags if "HIGH_VOLATILITY" in d.regime_name)

    assert calm.stress_degradation_observed is False
    assert normal.conformal_coverage_80 >= 0.80
    assert high_vol.stress_degradation_observed is True
    # Conformal calibration should still deliver > 75% coverage even under extreme shock
    assert high_vol.conformal_coverage_80 > 0.75


def test_08_regime_classifier_audit_root_cause(master_report: Sprint1001MasterReport):
    """Test 8: Verify forensic audit of the DELEVERAGING_STRESS state lock."""
    audit = master_report.regime_classifier_audit
    assert audit.investigation_id == "AUDIT-REGIME-LOCK-1001"
    assert audit.proven_root_cause == "STRUCTURAL_SINGLE_ROW_PERCENTILE_COLLAPSE_BUG"
    assert "np.nanpercentile" in audit.mathematical_mechanism
    assert "SPOT_ONLY_U0" in audit.missing_derivatives_role
    assert "MarketRegimeEngine" in audit.product_display_recommendation


def test_09_probability_provenance_audit(master_report: Sprint1001MasterReport):
    """Test 9: Verify strict taxonomy separating model-derived probabilities from static fallbacks."""
    prov = master_report.probability_provenance_audit
    assert "STATIC_FALLBACK_CONSTANT" in prov["tail_risk_probability"]
    assert "STATIC_FALLBACK_CONSTANT" in prov["jump_risk_probability"]
    assert prov["conformal_interval_80"] == ProbabilityProvenanceType.EMPIRICALLY_CALIBRATED.value
    assert prov["conformal_interval_95"] == ProbabilityProvenanceType.EMPIRICALLY_CALIBRATED.value


def test_10_conformal_calibration_contract_schema(master_report: Sprint1001MasterReport):
    """Test 10: Verify the serialized calibration contract and JSON report files."""
    contract = master_report.calibration_contract
    assert contract.contract_version == "CBE-CALIB-CONTRACT-V1.0"
    assert contract.source_model_version == "CBE-0.7.0"
    assert len(contract.conformal_quantiles_80) == 8
    assert len(contract.conformal_quantiles_95) == 8
    assert len(contract.embargo_bars_by_horizon) == 8

    # Verify JSON artifacts on disk
    rep_file = Path("data/reports/sprint10_01_conformal_calibration_report.json")
    cont_file = Path("data/reports/sprint10_01_calibration_contract.json")

    assert rep_file.exists()
    assert cont_file.exists()

    with open(cont_file, "r", encoding="utf-8") as f:
        c_data = json.load(f)
    assert c_data["contract_version"] == "CBE-CALIB-CONTRACT-V1.0"
    assert "conformal_quantiles_80" in c_data


def test_11_adversarial_checks(calibrator: CausalConformalCalibrator):
    """Test 11: Adversarial checks for tiny samples, independence violations, and fallback flags."""
    # 1. Block bootstrap with tiny sample must not crash and return valid bound
    tiny_hits = np.array([1, 0, 1, 1, 0])
    ci_tiny = calibrator.compute_block_bootstrap_ci(tiny_hits, block_size=12)
    assert 0.0 <= ci_tiny[0] <= ci_tiny[1] <= 1.0

    # 2. Probability provenance: Verify static fallback constants are never labeled MODEL_DERIVED
    prov = calibrator.audit_probability_provenance()
    assert prov["tail_risk_probability"] != ProbabilityProvenanceType.MODEL_DERIVED.value
    assert prov["jump_risk_probability"] != ProbabilityProvenanceType.MODEL_DERIVED.value

    # 3. Horizon embargo: 24h horizon must enforce at least 96 15m bars embargo
    _, horiz = calibrator.evaluate_calibration_candidates()
    contract = calibrator.build_calibration_contract(horiz)
    assert contract.embargo_bars_by_horizon["24h"] == 96


def test_12_compute_latency_budget(calibrator: CausalConformalCalibrator):
    """Test 12: Verify pure calibration computation runs well under the 50 ms budget."""
    t0 = time.perf_counter()
    calibrator.audit_regime_classifier_lock()
    calibrator.audit_probability_provenance()
    _, horiz = calibrator.evaluate_calibration_candidates()
    calibrator.audit_regime_diagnostics()
    calibrator.build_calibration_contract(horiz)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"
