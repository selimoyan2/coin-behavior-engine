"""Unit tests for Sprint 09.4 Market State Classifier & Probabilistic Interval Calibration.

Verifies:
1. Root cause single-row collapse reproduction and mitigation.
2. MarketStateClassifierV080 deterministic inference, schema adherence, and fail-closed safety.
3. Strict tier boundary enforcement: DELEVERAGING_STRESS barred from SPOT_ONLY_U0.
4. Holdout non-collapse: balanced distribution with no state > 80%.
5. Transition matrix diagonal dominance and persistence.
6. Incremental information: discrete states add statistically significant explanatory power.
7. IntervalCalibratorV080 strict ordering invariant: 0 <= L95 <= L80 <= point_forecast <= U80 <= U95.
8. Holdout out-of-sample empirical coverage within tolerance ([72%, 88%] for 80%, [90%, 98%] for 95%).
9. Winkler score superiority over uncalibrated CBE-0.7.0 baseline.
10. Scientific gate registry: 12/12 gates PASS, READY_FOR_CANDIDATE_INTEGRATION verdict.
11. Component lockbox integrity: SHA-256 matches for all candidate model components.
12. Sprint 07 production freeze integrity: 29/29 canonical artifacts verified.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

from coin_behavior_engine.candidate_v080.calibrator import (
    CalibrationError,
    IntervalCalibrationV080,
    IntervalCalibratorV080,
)
from coin_behavior_engine.candidate_v080.classifier import (
    ClassificationResult,
    ClassifierError,
    MarketStateClassifierV080,
    StateThresholdsV080,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze

REPORTS_DIR = Path("data/reports/sprint09_4")
MODELS_DIR = Path("data/models")


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def test_01_root_cause_collapse_reproduction():
    """Verify single-row percentile collapse root cause reproduction report."""
    repro_path = REPORTS_DIR / "classifier_root_cause_reproduction.md"
    assert repro_path.exists()
    content = repro_path.read_text(encoding="utf-8")
    assert "SINGLE_ROW_PERCENTILE_COLLAPSE" in content or "single-row percentile evaluation flaw" in content
    assert "DELEVERAGING_STRESS" in content
    assert "SPOT_ONLY_U0" in content

    # Mathematical test of single row collapse
    single_val = np.array([0.0])
    p05 = float(np.nanpercentile(single_val, 5))
    assert p05 == single_val[0]
    assert bool(single_val[0] <= p05) is True


def test_02_state_taxonomy_spec():
    """Verify state taxonomy specification adheres to two-layer decoupled design."""
    tax_path = REPORTS_DIR / "state_taxonomy_v080.json"
    assert tax_path.exists()

    with open(tax_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "CBE-TAXONOMY-0.8.0"
    assert data["tier"] == "SPOT_ONLY_U0"
    assert "LOW_VOLATILITY" in [s["state"] for s in data["layer_1_primary_state"]["values"]]
    assert "NORMAL_VOLATILITY" in [s["state"] for s in data["layer_1_primary_state"]["values"]]
    assert "HIGH_VOLATILITY" in [s["state"] for s in data["layer_1_primary_state"]["values"]]
    assert "UNKNOWN_INSUFFICIENT_DATA" in [s["state"] for s in data["layer_1_primary_state"]["values"]]

    assert "VOLATILITY_COMPRESSION" in [f["flag"] for f in data["layer_2_secondary_flags"]["flags"]]
    assert "VOLATILITY_EXPANSION" in [f["flag"] for f in data["layer_2_secondary_flags"]["flags"]]

    # Verify forbidden states
    forbidden = data["derivatives_tier_barrier"]["forbidden_states_in_u0"]
    assert "DELEVERAGING_STRESS" in forbidden


def test_03_classifier_deterministic_inference():
    """Verify MarketStateClassifierV080 inference on individual bars and batches."""
    thresh_path = MODELS_DIR / "cbe_state_thresholds_v080.json"
    assert thresh_path.exists()
    classifier = MarketStateClassifierV080(thresh_path)

    # Low vol bar
    res_low = classifier.classify_bar({"volatility_realized_24h": 0.0005, "volatility_compression_ratio": 1.0})
    assert res_low.primary_state == "LOW_VOLATILITY"
    assert res_low.secondary_flags == []

    # Normal vol bar with compression
    res_norm_comp = classifier.classify_bar({"volatility_realized_24h": 0.0015, "volatility_compression_ratio": 0.75})
    assert res_norm_comp.primary_state == "NORMAL_VOLATILITY"
    assert "VOLATILITY_COMPRESSION" in res_norm_comp.secondary_flags

    # High vol bar with expansion
    res_high_exp = classifier.classify_bar({"volatility_realized_24h": 0.0035, "volatility_compression_ratio": 1.25})
    assert res_high_exp.primary_state == "HIGH_VOLATILITY"
    assert "VOLATILITY_EXPANSION" in res_high_exp.secondary_flags

    # Fail closed on missing/invalid
    res_missing = classifier.classify_bar({"volatility_realized_24h": None, "volatility_compression_ratio": 1.0})
    assert res_missing.primary_state == "UNKNOWN_INSUFFICIENT_DATA"

    res_nan = classifier.classify_bar({"volatility_realized_24h": float("nan"), "volatility_compression_ratio": 1.0})
    assert res_nan.primary_state == "UNKNOWN_INSUFFICIENT_DATA"

    res_invalid_type = classifier.classify_bar("not_a_dict")
    assert res_invalid_type.primary_state == "UNKNOWN_INSUFFICIENT_DATA"


def test_04_classifier_holdout_non_collapse():
    """Verify Holdout distribution eliminates mechanical collapse."""
    val_path = REPORTS_DIR / "classifier_validation.json"
    assert val_path.exists()

    with open(val_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["holdout_non_collapse_pass"] is True
    hold_dist = data["partitions"]["HOLDOUT_2026"]
    assert hold_dist["is_non_collapsed"] is True
    assert hold_dist["max_prevalence_pct"] < 80.0
    assert hold_dist["distinct_states_observed"] >= 3

    # Confirm CBE-0.7.0 vs CBE-0.8.0 contrast
    comp = data["cbe_070_vs_cbe_080_comparison"]
    assert comp["cbe_070_holdout_deleveraging_stress_pct"] == 100.0
    assert comp["cbe_080_holdout_deleveraging_stress_pct"] == 0.0


def test_05_state_transition_persistence():
    """Verify transition matrix diagonal dominance and persistence."""
    trans_path = REPORTS_DIR / "state_transition_analysis.json"
    assert trans_path.exists()

    with open(trans_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["diagonal_dominance_confirmed"] is True
    assert data["minimum_diagonal_probability"] > 0.70

    for s, p in data["diagonal_persistence_probabilities"].items():
        assert p > 0.85, f"State {s} diagonal persistence too low: {p}"


def test_06_incremental_information_significance():
    """Verify that discrete market state indicators yield statistically significant F-test."""
    incr_path = REPORTS_DIR / "state_incremental_information.json"
    assert incr_path.exists()

    with open(incr_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    h_eval = data["evaluations"]["HOLDOUT_2026"]["1h"]
    assert h_eval["statistically_significant"] is True
    assert h_eval["f_test_p_value"] < 0.001
    assert h_eval["incremental_r2_lift"] > 0.0


def test_07_interval_calibrator_ordering_and_monotonicity():
    """Verify strict mathematical ordering invariant across test grid."""
    cal_path = MODELS_DIR / "cbe_interval_calibration_v080.json"
    assert cal_path.exists()
    calibrator = IntervalCalibratorV080(cal_path)

    # Test individual point forecasts
    test_points = [0.0001, 0.001, 0.015, 0.03, 0.05, 0.10, 0.25]
    for horizon in ["1h", "4h", "24h"]:
        for pt in test_points:
            res = calibrator.compute_intervals(pt, horizon)
            pi80 = res["prediction_intervals"]["80_pct"]
            pi95 = res["prediction_intervals"]["95_pct"]

            l80, u80 = pi80["lower"], pi80["upper"]
            l95, u95 = pi95["lower"], pi95["upper"]

            # Strict Invariant: 0 <= L95 <= L80 <= pt <= U80 <= U95
            assert 0.0 <= l95 <= l80 <= pt <= u80 <= u95, (
                f"Invariant failed for {horizon} at {pt}: 0 <= {l95} <= {l80} <= {pt} <= {u80} <= {u95}"
            )
            assert pi80["width"] == u80 - l80
            assert pi95["width"] == u95 - l95
            assert pi95["width"] >= pi80["width"]

    # Test error handling
    with pytest.raises(CalibrationError):
        calibrator.compute_intervals(-0.01, "1h")

    with pytest.raises(CalibrationError):
        calibrator.compute_intervals(float("nan"), "1h")

    with pytest.raises(CalibrationError):
        calibrator.compute_intervals(0.01, "non_existent_horizon")


def test_08_holdout_empirical_coverage():
    """Verify Holdout empirical coverage falls within tolerance bounds."""
    cov_path = REPORTS_DIR / "interval_coverage_validation.json"
    assert cov_path.exists()

    with open(cov_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hold = data["HOLDOUT_2026"]

    # 1h Horizon
    cov_1h_80 = hold["1h"]["coverage_80_pct"]
    cov_1h_95 = hold["1h"]["coverage_95_pct"]
    assert 72.0 <= cov_1h_80 <= 88.0, f"1h 80% coverage out of bounds: {cov_1h_80}%"
    assert 90.0 <= cov_1h_95 <= 98.0, f"1h 95% coverage out of bounds: {cov_1h_95}%"
    assert hold["1h"]["monotonicity_verified"] is True

    # 4h Horizon
    cov_4h_80 = hold["4h"]["coverage_80_pct"]
    cov_4h_95 = hold["4h"]["coverage_95_pct"]
    assert 72.0 <= cov_4h_80 <= 88.0, f"4h 80% coverage out of bounds: {cov_4h_80}%"
    assert 90.0 <= cov_4h_95 <= 98.0, f"4h 95% coverage out of bounds: {cov_4h_95}%"
    assert hold["4h"]["monotonicity_verified"] is True


def test_09_winkler_score_superiority():
    """Verify calibrated intervals achieve lower Winkler scores than uncalibrated baseline."""
    sharp_path = REPORTS_DIR / "interval_sharpness_comparison.json"
    assert sharp_path.exists()

    with open(sharp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for h in ["1h", "4h"]:
        h_data = data[h]
        assert h_data["winkler_score_superior"] is True
        assert h_data["winkler_ratio_80"] < 1.0, f"Winkler 80 ratio not < 1.0: {h_data['winkler_ratio_80']}"
        assert h_data["winkler_ratio_95"] < 1.0, f"Winkler 95 ratio not < 1.0: {h_data['winkler_ratio_95']}"


def test_10_scientific_gate_registry():
    """Verify all 12 scientific decision gates pass."""
    gate_path = REPORTS_DIR / "scientific_gate_registry.json"
    assert gate_path.exists()

    with open(gate_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["candidate_model_version"] == "CBE-0.8.0"
    assert data["overall_verdict"] == "READY_FOR_CANDIDATE_INTEGRATION"
    assert data["gates_passed_count"] == 12
    assert data["gates_evaluated_count"] == 12

    for g in data["gates"]:
        assert g["status"] == "PASS", f"Gate {g['gate_id']} failed: {g['evidence']}"


def test_11_component_lockbox_integrity():
    """Verify component lockbox hashes match current disk artifacts."""
    lockbox_path = MODELS_DIR / "component_lockbox.json"
    assert lockbox_path.exists()

    with open(lockbox_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for fname, art_info in data["artifacts"].items():
        fpath = MODELS_DIR / fname
        assert fpath.exists(), f"Artifact {fname} missing from disk"
        computed_hash = compute_sha256(fpath)
        assert computed_hash == art_info["sha256"], f"SHA-256 mismatch for {fname}"


def test_12_sprint07_freeze_verification_untouched():
    """Verify that Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts)."""
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["status"] == "FREEZE_VERIFIED"
    assert freeze_res["verified_artifacts_count"] == 29
    assert freeze_res["total_artifacts_checked"] == 29
    assert len(freeze_res["missing_files"]) == 0
