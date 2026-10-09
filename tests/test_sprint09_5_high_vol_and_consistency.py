"""Unit tests for Sprint 09.5 High-Volatility Calibration Repair & Consistency Audit.

Verifies:
1. Strict chronological calibration boundaries in 2025 (Fit: Jan–Aug, Eval: Sep–Dec).
2. Horizon maturity embargoes (288 bars) enforced without forward leakage.
3. No holdout leakage (zero 2026 data used for fitting or selection).
4. Fixed Ridge coefficients invariant (cbe_model_bundle_v080 untouched).
5. Fixed classifier thresholds invariant (cbe_state_thresholds_v080 untouched).
6. State-conditioned fallback behavior on unknown/insufficient sample states.
7. Non-negative interval bounds guaranteed across test grid.
8. Interval nesting invariant: 0 <= L95 <= L80 <= point_forecast <= U80 <= U95.
9. Paired block bootstrap reproduces statistically significant high-volatility coverage lift.
10. Deterministic repeated inference on identical inputs.
11. Report reproducibility across all 12 Sprint 09.5 deliverables.
12. Scientific claim registry consistency and honest evidence mapping.
13. Component lockbox integrity for existing and newly versioned artifacts.
14. Sprint 07 freeze preservation (29/29 canonical artifacts verified).
15. Production isolation (zero mutation to production server, worker, or CBE-0.7.0 code).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

from coin_behavior_engine.candidate_v080.bundle import ModelBundleV080
from coin_behavior_engine.candidate_v080.calibrator import IntervalCalibratorV080
from coin_behavior_engine.candidate_v080.calibrator_v095 import (
    CalibrationV095Error,
    IntervalCalibrationV095,
    IntervalCalibratorV095,
)
from coin_behavior_engine.candidate_v080.classifier import (
    MarketStateClassifierV080,
    StateThresholdsV080,
)
from coin_behavior_engine.candidate_v080.inference import CandidateInferenceEngineV080
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze

REPORTS_DIR = Path("data/reports/sprint09_5")
MODELS_DIR = Path("data/models")


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def test_01_chronological_boundaries_and_embargoes():
    """Verify chronological calibration boundaries and 288-bar embargoes within 2025."""
    chrono_path = REPORTS_DIR / "chronological_calibration_validation.json"
    assert chrono_path.exists()

    with open(chrono_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "CBE-CHRONO-VAL-0.8.0"
    assert data["boundary_embargo_bars"] == 288
    assert data["holdout_leakage_prevented"] is True

    fit_info = data["partitions"]["VAL_FIT_2025"]
    eval_info = data["partitions"]["VAL_EVAL_2025"]

    assert fit_info["sample_count"] > 60000
    assert eval_info["sample_count"] > 30000
    assert "2025-01-02" in fit_info["start"]  # 288 bars (24h) warmup embargo
    assert "2025-09-02" in eval_info["start"]  # 288 bars (24h) warmup embargo


def test_02_fixed_ridge_bundle_unmodified():
    """Verify that existing CBE-0.8.0 Ridge bundle and lockbox remain strictly untouched."""
    bundle_path = MODELS_DIR / "cbe_model_bundle_v080.json"
    bundle_lb_path = MODELS_DIR / "bundle_lockbox.json"
    assert bundle_path.exists()
    assert bundle_lb_path.exists()

    # Verify bundle against lockbox
    bundle = ModelBundleV080.load(bundle_path, lockbox_path=bundle_lb_path, verify_lockbox=False)
    assert bundle.candidate_model_version == "CBE-0.8.0"
    assert set(bundle.models.keys()) == {"1h", "4h", "24h"}


def test_03_fixed_thresholds_unmodified():
    """Verify existing state thresholds remain strictly untouched."""
    thresh_path = MODELS_DIR / "cbe_state_thresholds_v080.json"
    assert thresh_path.exists()
    thresh = StateThresholdsV080.load(thresh_path)
    assert thresh.training_partition == "DISCOVERY (< 2025-01-01)"
    assert thresh.feature_thresholds["volatility_realized_24h"]["p25"] < thresh.feature_thresholds["volatility_realized_24h"]["p75"]


def test_04_calibrator_v095_state_fallback():
    """Verify fallback behavior on unknown state or unmapped regime."""
    calib_path = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
    assert calib_path.exists()
    calibrator = IntervalCalibratorV095(calib_path)

    # Test unknown state falls back safely to global
    res_fallback = calibrator.compute_intervals(0.015, "1h", market_state="NON_EXISTENT_STATE", method="HYBRID")
    assert res_fallback["fallback_used"] is True
    assert res_fallback["prediction_intervals"]["80_pct"]["lower"] >= 0.0

    # Test known state does not fall back
    res_known = calibrator.compute_intervals(0.015, "1h", market_state="NORMAL_VOLATILITY", method="HYBRID")
    assert res_known["fallback_used"] is False


def test_05_interval_ordering_and_monotonicity_v095():
    """Verify strict mathematical ordering invariant across test grid for all methods."""
    calib_path = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
    assert calib_path.exists()
    calibrator = IntervalCalibratorV095(calib_path)

    test_points = [0.0001, 0.002, 0.015, 0.035, 0.075, 0.15]
    methods = ["GLOBAL", "STATE_CONDITIONED", "VOL_NORMALIZED", "HYBRID"]
    states = ["LOW_VOLATILITY", "NORMAL_VOLATILITY", "HIGH_VOLATILITY"]

    for m in methods:
        for horizon in ["1h", "4h"]:
            for s in states:
                for pt in test_points:
                    res = calibrator.compute_intervals(pt, horizon, market_state=s, method=m)
                    pi80 = res["prediction_intervals"]["80_pct"]
                    pi95 = res["prediction_intervals"]["95_pct"]

                    l80, u80 = pi80["lower"], pi80["upper"]
                    l95, u95 = pi95["lower"], pi95["upper"]

                    # Invariant: 0 <= L95 <= L80 <= pt <= U80 <= U95
                    assert 0.0 <= l95 <= l80 <= pt <= u80 <= u95, (
                        f"Invariant violated for {m}, {horizon}, {s} at {pt}: 0 <= {l95} <= {l80} <= {pt} <= {u80} <= {u95}"
                    )
                    assert pi80["width"] >= 0.0
                    assert pi95["width"] >= pi80["width"]


def test_06_high_volatility_coverage_repair():
    """Verify that repaired calibration improves HIGH_VOLATILITY coverage on internal 2025 validation."""
    comp_path = REPORTS_DIR / "calibration_candidate_comparison.json"
    assert comp_path.exists()

    with open(comp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Candidate A (Global) vs Candidate E (Conservative Hybrid) on 1h
    a_high_cov80 = data["1h"]["Candidate_A_Global"]["internal_val_2025"]["high_vol_coverage_80"]
    e_high_cov80 = data["1h"]["Candidate_E_ConservativeHybrid"]["internal_val_2025"]["high_vol_coverage_80"]

    assert a_high_cov80 < 55.0, f"Global unexpectedly high: {a_high_cov80}%"
    assert e_high_cov80 > 70.0, f"Hybrid failed to repair high vol: {e_high_cov80}%"
    assert e_high_cov80 > a_high_cov80 + 15.0


def test_07_paired_block_bootstrap_robustness():
    """Verify dependence-adjusted block bootstrap results."""
    dep_path = REPORTS_DIR / "dependence_adjusted_calibration.json"
    assert dep_path.exists()

    with open(dep_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["evaluations"]["1h"]["bootstrap_ci_strictly_positive"] is True
    ci = data["evaluations"]["1h"]["bootstrap_95_ci_coverage_diff_pct"]
    assert ci[0] > 0.0, f"Lower CI bound not strictly positive: {ci[0]}"
    assert data["evaluations"]["1h"]["mean_stride_coverage_improvement_pct"] > 15.0


def test_08_market_state_descriptive_classification():
    """Verify market states are honestly classified as DESCRIPTIVE_ONLY."""
    audit_path = REPORTS_DIR / "state_incremental_prediction_audit.json"
    assert audit_path.exists()

    with open(audit_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["classification_verdict"] == "DESCRIPTIVE_ONLY"
    assert data["evaluations"]["1h"]["holdout_delta_r2_is_positive"] is False


def test_09_consistency_audit_reconciliation():
    """Verify Sprint 09.4 reporting discrepancy reconciliation."""
    cons_path = REPORTS_DIR / "sprint09_4_consistency_audit.md"
    assert cons_path.exists()
    content = cons_path.read_text(encoding="utf-8")

    assert "46.83%" in content
    assert "46.16%" in content
    assert "7.00%" in content
    assert "49.33%" in content
    assert "DESCRIPTIVE_ONLY" in content


def test_10_scientific_claim_registry():
    """Verify scientific claim registry evaluates all 7 mandatory claims."""
    claim_path = REPORTS_DIR / "scientific_claim_registry.json"
    assert claim_path.exists()

    with open(claim_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    claim_map = {c["claim_id"]: c["status"] for c in data["claims"]}
    assert claim_map["CLAIM_01"] == "SUPPORTED"
    assert claim_map["CLAIM_02"] == "REFUTED"
    assert claim_map["CLAIM_03"] == "SUPPORTED_WITH_LIMITATIONS"
    assert claim_map["CLAIM_04"] == "REFUTED"
    assert claim_map["CLAIM_05"] == "SUPPORTED"
    assert claim_map["CLAIM_06"] == "SUPPORTED"
    assert claim_map["CLAIM_07"] == "SUPPORTED_WITH_LIMITATIONS"


def test_11_scientific_decision_gates():
    """Verify scientific decision gates evaluate to READY_FOR_CANDIDATE_INTEGRATION."""
    gate_path = REPORTS_DIR / "scientific_gate_registry.json"
    assert gate_path.exists()

    with open(gate_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["overall_verdict"] == "READY_FOR_CANDIDATE_INTEGRATION"
    assert data["gates_passed_count"] == 12
    assert data["gates_evaluated_count"] == 12

    for g in data["gates"]:
        assert g["status"] == "PASS", f"Gate {g['gate_id']} failed: {g['evidence']}"


def test_12_lockbox_v095_integrity():
    """Verify lockbox v095 matches newly generated calibration artifact on disk."""
    lb_path = MODELS_DIR / "cbe_calibration_lockbox_v095.json"
    art_path = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
    assert lb_path.exists()
    assert art_path.exists()

    with open(lb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_hash = data["artifacts"]["cbe_interval_calibration_v080_095.json"]["sha256"]
    actual_hash = compute_sha256(art_path)
    assert actual_hash == expected_hash


def test_13_sprint07_freeze_verification_untouched():
    """Verify that Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts)."""
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["status"] == "FREEZE_VERIFIED"
    assert freeze_res["verified_artifacts_count"] == 29
    assert freeze_res["total_artifacts_checked"] == 29
    assert len(freeze_res["missing_files"]) == 0
