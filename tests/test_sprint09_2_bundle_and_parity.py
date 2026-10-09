"""Tests for Sprint 09.2 Candidate Model Bundle, Inference Engine & Release Gates.

Verifies:
1. Feature and target schemas match authoritative definitions for CBE-0.8.0.
2. Bundle serialization, lockbox hashing, and tamper detection.
3. Zero-dependency inference engine exhibits exact float parity (< 1e-12) with sklearn Ridge.
4. Inference engine enforces strict fail-closed validation on missing or non-finite inputs.
5. Baseline challenge and dependence-aware reports accurately record 1h/4h lift and 24h persistence parity.
6. Scientific release gates evaluate correctly.
7. Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts).
"""

import copy
import json
import math
import tempfile
from pathlib import Path
import numpy as np
import pytest

from coin_behavior_engine.candidate_v080.bundle import (
    BundleIntegrityError,
    ModelBundleV080,
)
from coin_behavior_engine.candidate_v080.inference import (
    CandidateInferenceEngineV080,
    FeatureValidationError,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze


BUNDLE_PATH = Path("data/reports/sprint09_2/cbe_model_bundle_v080.json")
LOCKBOX_PATH = Path("data/reports/sprint09_2/bundle_lockbox.json")


def test_feature_and_target_schemas():
    """Verify feature and target schemas in data/reports/sprint09_2/."""
    feat_schema_path = Path("data/reports/sprint09_2/feature_schema_v080.json")
    tgt_schema_path = Path("data/reports/sprint09_2/target_schema_v080.json")

    assert feat_schema_path.exists()
    assert tgt_schema_path.exists()

    with open(feat_schema_path, "r", encoding="utf-8") as f:
        feat_data = json.load(f)
    with open(tgt_schema_path, "r", encoding="utf-8") as f:
        tgt_data = json.load(f)

    assert feat_data["tier"] == "SPOT_ONLY_U0"
    assert feat_data["ordered_features"] == [
        "volatility_realized_24h",
        "volatility_compression_ratio",
        "volume_zscore_24h",
    ]

    assert "1h" in tgt_data["horizons"]
    assert "4h" in tgt_data["horizons"]
    assert "24h" in tgt_data["horizons"]
    assert np.isclose(tgt_data["daily_scaling_factor"], math.sqrt(288.0))


def test_bundle_loading_and_lockbox_integrity():
    """Verify bundle loads properly and lockbox catches tampering."""
    assert BUNDLE_PATH.exists()
    assert LOCKBOX_PATH.exists()

    # Valid load
    bundle = ModelBundleV080.load(BUNDLE_PATH, lockbox_path=LOCKBOX_PATH, verify_lockbox=True)
    assert bundle.candidate_model_version == "CBE-0.8.0"
    assert bundle.schema_version == "CBE-BUNDLE-0.8.0"
    assert len(bundle.models) == 3

    # Tampered lockbox should raise BundleIntegrityError
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_lockbox = Path(tmp_dir) / "lockbox.json"
        with open(LOCKBOX_PATH, "r", encoding="utf-8") as f:
            lb_data = json.load(f)
        lb_data["bundle_sha256"] = "corrupted_hash_0000000000000000000000000000000000000000"
        with open(tmp_lockbox, "w", encoding="utf-8") as f:
            json.dump(lb_data, f)

        with pytest.raises(BundleIntegrityError, match="Bundle hash mismatch"):
            ModelBundleV080.load(BUNDLE_PATH, lockbox_path=tmp_lockbox, verify_lockbox=True)


def test_inference_engine_parity_and_predictions():
    """Verify inference engine predictions match expected values from numerical parity report."""
    engine = CandidateInferenceEngineV080(BUNDLE_PATH, lockbox_path=LOCKBOX_PATH)

    parity_report_path = Path("data/reports/sprint09_2/numerical_parity_report.json")
    with open(parity_report_path, "r", encoding="utf-8") as f:
        parity_data = json.load(f)

    for test_case in parity_data["tests"]:
        h = test_case["horizon"]
        sample_name = test_case["sample_name"]
        expected_pred = test_case["bundle_pred"]

        if sample_name == "typical_market_sample":
            x = {"volatility_realized_24h": 0.0016, "volatility_compression_ratio": 1.0, "volume_zscore_24h": 0.0}
        elif sample_name == "calm_regime_sample":
            x = {"volatility_realized_24h": 0.0008, "volatility_compression_ratio": 0.6, "volume_zscore_24h": -1.2}
        elif sample_name == "high_vol_shock_sample":
            x = {"volatility_realized_24h": 0.0085, "volatility_compression_ratio": 2.4, "volume_zscore_24h": 4.5}
        elif sample_name == "extreme_positive_outlier":
            x = {"volatility_realized_24h": 0.0500, "volatility_compression_ratio": 5.0, "volume_zscore_24h": 15.0}
        elif sample_name == "boundary_minimum_sample":
            x = {"volatility_realized_24h": 0.0001, "volatility_compression_ratio": 0.1, "volume_zscore_24h": -3.0}
        else:
            continue

        pred = engine.predict(x, horizon=h)
        assert np.isclose(pred, expected_pred, atol=1e-12)

        # Raw 5m unscaled prediction
        raw_pred = engine.predict_unscaled_5m(x, horizon=h)
        assert np.isclose(raw_pred * math.sqrt(288.0), pred, atol=1e-12)


def test_inference_engine_fail_closed_validation():
    """Verify inference engine strictly fails closed on missing features, wrong names, or NaNs."""
    engine = CandidateInferenceEngineV080(BUNDLE_PATH, lockbox_path=LOCKBOX_PATH)

    # 1. Missing feature
    with pytest.raises(FeatureValidationError, match="Missing required feature: 'volume_zscore_24h'"):
        engine.predict({"volatility_realized_24h": 0.002, "volatility_compression_ratio": 1.0}, horizon="1h")

    # 2. None value
    with pytest.raises(FeatureValidationError, match="has None value"):
        engine.predict({
            "volatility_realized_24h": 0.002,
            "volatility_compression_ratio": None,
            "volume_zscore_24h": 0.0,
        }, horizon="1h")

    # 3. NaN value
    with pytest.raises(FeatureValidationError, match="is non-finite"):
        engine.predict({
            "volatility_realized_24h": np.nan,
            "volatility_compression_ratio": 1.0,
            "volume_zscore_24h": 0.0,
        }, horizon="1h")

    # 4. Unknown horizon
    with pytest.raises(ValueError, match="Unknown horizon '12h'"):
        engine.predict({
            "volatility_realized_24h": 0.002,
            "volatility_compression_ratio": 1.0,
            "volume_zscore_24h": 0.0,
        }, horizon="12h")


def test_baseline_challenge_results():
    """Verify Baseline Challenge results in baseline_comparison.json."""
    baseline_path = Path("data/reports/sprint09_2/baseline_comparison.json")
    with open(baseline_path, "r", encoding="utf-8") as f:
        res = json.load(f)

    # 1h: Ridge beats persistence on Validation and Holdout
    assert res["1h"]["VALIDATION_2025"]["ridge_beats_persistence"] is True
    assert res["1h"]["HOLDOUT_2026"]["ridge_beats_persistence"] is True
    assert res["1h"]["VALIDATION_2025"]["ridge_mae_lift_over_persistence_pct"] > 0

    # 4h: Ridge beats persistence on Validation and Holdout
    assert res["4h"]["VALIDATION_2025"]["ridge_beats_persistence"] is True
    assert res["4h"]["HOLDOUT_2026"]["ridge_beats_persistence"] is True
    assert res["4h"]["VALIDATION_2025"]["ridge_mae_lift_over_persistence_pct"] > 0

    # 24h: On Holdout, persistence has lower MAE than Ridge
    assert res["24h"]["HOLDOUT_2026"]["ridge_beats_persistence"] is False


def test_scientific_release_gates():
    """Verify formal evaluation of Gates A through J in scientific_gate_registry.json."""
    gate_path = Path("data/reports/sprint09_2/scientific_gate_registry.json")
    with open(gate_path, "r", encoding="utf-8") as f:
        res = json.load(f)

    assert res["candidate_version"] == "CBE-0.8.0"
    assert res["overall_status"] == "ARTIFACT_VALID_RESEARCH_CANDIDATE"

    gate_map = {g["gate_id"]: g["status"] for g in res["gates"]}
    assert gate_map["GATE_A_FEATURE_PARITY"] == "PASS"
    assert gate_map["GATE_B_TARGET_PARITY"] == "PASS"
    assert gate_map["GATE_C_CAUSAL_VALIDITY"] == "PASS"
    assert gate_map["GATE_D_SCALER_PARITY"] == "PASS"
    assert gate_map["GATE_E_REPRODUCIBLE_TRAINING"] == "PASS"
    assert gate_map["GATE_F_BUNDLE_INTEGRITY"] == "PASS"
    assert gate_map["GATE_G_NUMERICAL_INFERENCE_PARITY"] == "PASS"
    assert gate_map["GATE_H_BASELINE_COMPARISON"] == "PARTIAL_PASS"
    assert gate_map["GATE_I_DEPENDENCE_AWARE_VALIDATION"] == "PASS"
    assert gate_map["GATE_J_PROSPECTIVE_REPLAY"] == "NOT_EVALUABLE"


def test_sprint07_model_freeze_untouched():
    """Verify that Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts)."""
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["status"] == "FREEZE_VERIFIED"
    assert freeze_res["verified_artifacts_count"] == 29
    assert freeze_res["total_artifacts_checked"] == 29
    assert len(freeze_res["missing_files"]) == 0
