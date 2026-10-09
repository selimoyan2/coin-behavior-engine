"""Tests for Sprint 09.6: Candidate Integration, Scientific Release Audit & Offline Shadow Readiness.

Validates:
1. Canonical Scientific Metrics Engine correctness, determinism, and invariants.
2. CandidateInferencePipelineV080 integrated behavior, schema validation, fail-closed mechanics.
3. Interval monotonicity: 0 <= lower95 <= lower80 <= point_forecast <= upper80 <= upper95.
4. MARKET_STATE_POINT_FORECAST_ROLE = DESCRIPTIVE_ONLY invariant.
5. Numerical parity between integrated pipeline and standalone Ridge engine.
6. Existence and schema validity of all 14 research deliverables.
7. Sprint 07 frozen model preservation (29/29 artifacts).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.bundle import ModelBundleV080
from coin_behavior_engine.candidate_v080.classifier import (
    ClassificationResult,
    MarketStateClassifierV080,
    StateThresholdsV080,
)
from coin_behavior_engine.candidate_v080.inference import (
    CandidateInferenceEngineV080,
    FeatureValidationError,
)
from coin_behavior_engine.candidate_v080.calibrator_v095 import (
    IntervalCalibrationV095,
    IntervalCalibratorV095,
)
from coin_behavior_engine.candidate_v080.inference_pipeline import (
    CandidateInferencePipelineV080,
    CandidatePredictionResult,
    HorizonForecastResult,
    MARKET_STATE_POINT_FORECAST_ROLE,
    TARGET_UNITS,
)
from coin_behavior_engine.candidate_v080.metrics import (
    CanonicalMetricsEngine,
    IntervalMetrics,
    PointMetrics,
    StateDistributionMetrics,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze


MODELS_DIR = Path("data/models")
BUNDLE_PATH = MODELS_DIR / "cbe_model_bundle_v080.json"
BUNDLE_LOCKBOX_PATH = MODELS_DIR / "bundle_lockbox.json"
THRESHOLDS_PATH = MODELS_DIR / "cbe_state_thresholds_v080.json"
CALIBRATION_V095_PATH = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
REPORTS_DIR = Path("data/reports/sprint09_6")


@pytest.fixture
def sample_valid_features() -> dict:
    return {
        "volatility_realized_24h": 0.001850,
        "volatility_compression_ratio": 1.050,
        "volume_zscore_24h": 0.350,
    }


@pytest.fixture
def pipeline() -> CandidateInferencePipelineV080:
    return CandidateInferencePipelineV080(
        bundle=BUNDLE_PATH,
        classifier=THRESHOLDS_PATH,
        calibrator=CALIBRATION_V095_PATH,
        calibration_method="HYBRID",
        lockbox_path=BUNDLE_LOCKBOX_PATH,
    )


# ---------------------------------------------------------------------------
# Section 1: Canonical Metrics Engine Tests
# ---------------------------------------------------------------------------

def test_01_metrics_sample_accounting():
    counts = CanonicalMetricsEngine.compute_sample_counts(
        total_rows=1000,
        valid_features=980,
        valid_targets=950,
        eligible_samples=950,
        excluded_reasons={"missing_target": 50},
    )
    assert counts["total_rows"] == 1000
    assert counts["eligible_samples"] == 950
    assert counts["excluded_samples"] == 50
    assert counts["excluded_reasons"] == {"missing_target": 50}


def test_02_metrics_state_distribution_percentages():
    states = ["LOW_VOLATILITY"] * 40 + ["NORMAL_VOLATILITY"] * 50 + ["HIGH_VOLATILITY"] * 10
    dist = CanonicalMetricsEngine.compute_state_distribution(states)
    assert dist.total_samples == 100
    assert dist.counts["LOW_VOLATILITY"] == 40
    assert dist.counts["NORMAL_VOLATILITY"] == 50
    assert dist.counts["HIGH_VOLATILITY"] == 10
    pct_sum = sum(dist.percentages.values())
    assert abs(pct_sum - 100.0) < 1e-4


def test_03_metrics_point_forecast_calculation():
    y_true = np.array([0.02, 0.03, 0.04, 0.05])
    y_pred = np.array([0.022, 0.028, 0.041, 0.049])
    pt = CanonicalMetricsEngine.compute_point_metrics(y_true, y_pred)
    assert pt.sample_count == 4
    expected_mae = float(np.mean(np.abs(y_pred - y_true)))
    assert abs(pt.mae - expected_mae) < 1e-9
    assert pt.rmse > 0.0
    assert pt.pearson_r > 0.95
    assert pt.mae_se > 0.0


def test_04_metrics_interval_calculation_and_winkler():
    y_true = np.array([0.02, 0.03, 0.04, 0.05])
    y_pred = np.array([0.02, 0.03, 0.04, 0.05])
    l80 = y_pred - 0.005
    u80 = y_pred + 0.005
    l95 = y_pred - 0.010
    u95 = y_pred + 0.010
    itv = CanonicalMetricsEngine.compute_interval_metrics(y_true, y_pred, l80, u80, l95, u95)
    assert itv.sample_count == 4
    assert itv.coverage_80 == 100.0
    assert itv.coverage_95 == 100.0
    assert abs(itv.mean_width_80 - 0.010) < 1e-9
    assert abs(itv.mean_width_95 - 0.020) < 1e-9
    assert itv.winkler_80 > 0.0


def test_05_metrics_by_state_conditioning():
    y_true = np.array([0.02, 0.03, 0.04, 0.05])
    y_pred = np.array([0.02, 0.03, 0.04, 0.05])
    l80, u80 = y_pred - 0.005, y_pred + 0.005
    l95, u95 = y_pred - 0.010, y_pred + 0.010
    states = np.array(["LOW", "LOW", "HIGH", "HIGH"])
    by_st = CanonicalMetricsEngine.compute_metrics_by_state(y_true, y_pred, l80, u80, l95, u95, states)
    assert "LOW" in by_st
    assert "HIGH" in by_st
    assert by_st["LOW"].sample_count == 2
    assert by_st["HIGH"].sample_count == 2


def test_06_metrics_non_overlapping_strides():
    y_true = np.arange(100, dtype=float)
    y_pred = np.arange(100, dtype=float) + 0.1
    res_1h = CanonicalMetricsEngine.compute_non_overlapping_metrics(y_true, y_pred, horizon="1h")
    assert res_1h["step"] == 12
    assert res_1h["sample_count"] == 9  # indices 0, 12, 24, 36, 48, 60, 72, 84, 96

    res_4h = CanonicalMetricsEngine.compute_non_overlapping_metrics(y_true, y_pred, horizon="4h")
    assert res_4h["step"] == 48
    assert res_4h["sample_count"] == 3  # indices 0, 48, 96


def test_07_metrics_paired_block_bootstrap_determinism():
    errors_cand = np.sin(np.linspace(0, 100, 600)) * 0.01
    errors_base = np.sin(np.linspace(0, 100, 600)) * 0.015
    res1 = CanonicalMetricsEngine.compute_paired_block_bootstrap(errors_cand, errors_base, block_size=288, n_boot=200, random_seed=42)
    res2 = CanonicalMetricsEngine.compute_paired_block_bootstrap(errors_cand, errors_base, block_size=288, n_boot=200, random_seed=42)
    assert res1["ci_95_lower"] == res2["ci_95_lower"]
    assert res1["ci_95_upper"] == res2["ci_95_upper"]
    assert res1["p_value"] == res2["p_value"]


def test_08_metrics_claim_registry_summation_invariant():
    claims = [
        {"claim_id": "C1", "status": "SUPPORTED"},
        {"claim_id": "C2", "status": "SUPPORTED_WITH_LIMITATIONS"},
        {"claim_id": "C3", "status": "REFUTED"},
        {"claim_id": "C4", "status": "NOT_VERIFIED"},
    ]
    agg = CanonicalMetricsEngine.aggregate_claims(claims)
    assert agg["total_claims"] == 4
    sum_counts = sum(agg["status_counts"].values())
    assert sum_counts == 4
    assert agg["integrity_verified"] is True


def test_09_metrics_gate_aggregation():
    gates = [
        {"gate_id": "G1", "status": "PASS"},
        {"gate_id": "G2", "status": "PASS"},
    ]
    agg = CanonicalMetricsEngine.aggregate_gates(gates)
    assert agg["total_gates"] == 2
    assert agg["gates_passed"] == 2
    assert agg["verdict"] == "READY_FOR_CANDIDATE_INTEGRATION"


# ---------------------------------------------------------------------------
# Section 2: Integrated Pipeline Tests
# ---------------------------------------------------------------------------

def test_10_pipeline_initialization_defaults():
    pip = CandidateInferencePipelineV080()
    assert pip.ridge_engine is not None
    assert pip.classifier is not None
    assert pip.calibrator is not None
    assert pip.calibration_method == "HYBRID"


def test_11_pipeline_predict_bar_valid(pipeline, sample_valid_features):
    result = pipeline.predict_bar(sample_valid_features, timestamp="2026-03-01T12:00:00Z")
    assert isinstance(result, CandidatePredictionResult)
    assert result.primary_state in ["LOW_VOLATILITY", "NORMAL_VOLATILITY", "HIGH_VOLATILITY"]
    assert result.timestamp == "2026-03-01T12:00:00Z"
    assert "1h" in result.forecasts
    assert "4h" in result.forecasts
    assert "24h" in result.forecasts


def test_12_point_forecast_role_is_descriptive_only(pipeline, sample_valid_features):
    result = pipeline.predict_bar(sample_valid_features)
    for h, fc in result.forecasts.items():
        assert fc.point_forecast_role == MARKET_STATE_POINT_FORECAST_ROLE
        assert fc.point_forecast_role == "DESCRIPTIVE_ONLY"


def test_13_target_units_uniformity(pipeline, sample_valid_features):
    result = pipeline.predict_bar(sample_valid_features)
    for h, fc in result.forecasts.items():
        assert fc.units == TARGET_UNITS
        assert fc.units == "Daily-scaled standard deviation (sigma_5m * sqrt(288))"


def test_14_interval_monotonicity_invariant(pipeline, sample_valid_features):
    result = pipeline.predict_bar(sample_valid_features)
    for h, fc in result.forecasts.items():
        p = fc.point_forecast
        l80 = fc.intervals["80_pct"]["lower"]
        u80 = fc.intervals["80_pct"]["upper"]
        l95 = fc.intervals["95_pct"]["lower"]
        u95 = fc.intervals["95_pct"]["upper"]
        assert 0.0 <= l95 <= l80 <= p <= u80 <= u95, f"Monotonicity violated: {l95} <= {l80} <= {p} <= {u80} <= {u95}"


def test_15_feature_validation_missing_feature_fails_closed(pipeline, sample_valid_features):
    bad_features = sample_valid_features.copy()
    del bad_features["volume_zscore_24h"]
    with pytest.raises(FeatureValidationError) as exc_info:
        pipeline.predict_bar(bad_features)
    assert "Missing required feature" in str(exc_info.value)


def test_16_feature_validation_nan_feature_fails_closed(pipeline, sample_valid_features):
    bad_features = sample_valid_features.copy()
    bad_features["volatility_realized_24h"] = float("nan")
    with pytest.raises(FeatureValidationError) as exc_info:
        pipeline.predict_bar(bad_features)
    assert "non-finite" in str(exc_info.value)


def test_17_feature_validation_inf_feature_fails_closed(pipeline, sample_valid_features):
    bad_features = sample_valid_features.copy()
    bad_features["volatility_compression_ratio"] = float("inf")
    with pytest.raises(FeatureValidationError) as exc_info:
        pipeline.predict_bar(bad_features)
    assert "non-finite" in str(exc_info.value)


def test_18_feature_validation_non_dict_fails_closed(pipeline):
    with pytest.raises(FeatureValidationError) as exc_info:
        pipeline.predict_bar("not a dict")  # type: ignore
    assert "Expected dict of features" in str(exc_info.value)


def test_19_unknown_horizon_raises_value_error(pipeline, sample_valid_features):
    with pytest.raises(ValueError) as exc_info:
        pipeline.predict_bar(sample_valid_features, horizons=["72h"])
    assert "Unsupported horizon" in str(exc_info.value)


def test_20_ridge_numerical_parity(pipeline, sample_valid_features):
    engine = CandidateInferenceEngineV080(BUNDLE_PATH, lockbox_path=BUNDLE_LOCKBOX_PATH)
    result = pipeline.predict_bar(sample_valid_features)
    for h in ["1h", "4h", "24h"]:
        pt_engine = engine.predict(sample_valid_features, horizon=h)
        pt_pipe = result.forecasts[h].point_forecast
        assert abs(pt_engine - pt_pipe) <= 1e-12


def test_21_batch_prediction_row_count(pipeline, sample_valid_features):
    df = pd.DataFrame([sample_valid_features for _ in range(5)])
    batch_res = pipeline.predict_batch(df)
    assert len(batch_res) == 5
    assert all(isinstance(r, CandidatePredictionResult) for r in batch_res)


def test_22_batch_dataframe_prediction(pipeline, sample_valid_features):
    df = pd.DataFrame([sample_valid_features for _ in range(3)])
    df["timestamp"] = ["2026-01-01", "2026-01-02", "2026-01-03"]
    out_df = pipeline.predict_batch_df(df)
    assert len(out_df) == 3
    assert "pred_1h" in out_df.columns
    assert "lower80_1h" in out_df.columns
    assert "upper80_1h" in out_df.columns
    assert "primary_state" in out_df.columns


# ---------------------------------------------------------------------------
# Section 3: Deliverables & Freeze Preservation Tests
# ---------------------------------------------------------------------------

def test_23_all_14_deliverables_exist():
    expected_files = [
        "source_of_truth_audit.md",
        "canonical_metrics_schema.json",
        "canonical_metrics_validation.json",
        "calibration_selection_framework.md",
        "calibration_selection_result.json",
        "integrated_inference_contract.json",
        "ridge_inference_parity.json",
        "feature_target_unit_audit.json",
        "offline_shadow_replay.json",
        "prospective_readiness_matrix.json",
        "scientific_claim_registry.json",
        "scientific_gate_registry.json",
        "resource_usage_report.md",
        "executive_summary.md",
    ]
    for fname in expected_files:
        fpath = REPORTS_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"Deliverable is empty: {fname}"


def test_24_canonical_metrics_schema_valid():
    with open(REPORTS_DIR / "canonical_metrics_validation.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == "CBE-METRICS-SCHEMA-0.8.0"
    assert data["target_units"] == TARGET_UNITS
    assert "1h" in data["horizons"]
    assert "4h" in data["horizons"]
    assert "24h" in data["horizons"]


def test_25_scientific_claims_registry_integrity():
    with open(REPORTS_DIR / "scientific_claim_registry.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    summary = data["summary"]
    total = summary["total_claims"]
    status_sum = sum(summary["status_counts"].values())
    assert total == status_sum == len(data["claims"])
    assert summary["integrity_verified"] is True


def test_26_scientific_gate_registry_all_pass():
    with open(REPORTS_DIR / "scientific_gate_registry.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["gates_evaluated_count"] == 12
    assert data["gates_passed_count"] == 12
    assert data["overall_verdict"] == "READY_FOR_CANDIDATE_INTEGRATION"
    for g in data["gates"]:
        assert g["status"] == "PASS"


def test_27_sprint07_freeze_preserved():
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["canonical_hashes_verified"] == 29
    assert freeze_res["status"] == "FREEZE_VERIFIED"
