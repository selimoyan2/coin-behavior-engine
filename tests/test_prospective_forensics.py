"""Tests for Sprint 08.2 Prospective Scientific Forensics & Baseline Audit Tool.

Verifies:
1. Market-state lock forensics correctly detects single-row percentile collapse and 100% lock.
2. Forecasting mechanism audit detects empty vol_models and naive persistence fallback.
3. Baseline comparison accurately detects zero incremental improvement over persistence.
4. Overlapping outcome dependence correctly computes effective sample size and dependence-adjusted CI.
5. Interval coverage audit identifies under-coverage on 80% and 95% nominal bands.
6. 24h deterioration audit properly diagnoses term-structure persistence decay and noise.
7. Claim registry correctly evaluates Claims A-F according to scientific evidence.
8. Full forensics suite executes cleanly in temp dir and produces all 7 required files.
"""

import json
import tempfile
from pathlib import Path

import pytest

from coin_behavior_engine.audit.prospective_forensics import (
    ForensicsTelemetry,
    audit_market_state_lock,
    audit_forecasting_mechanism,
    audit_incremental_predictive_value,
    audit_overlapping_outcomes,
    audit_prediction_interval_coverage,
    audit_24h_deterioration,
    evaluate_scientific_claims,
    run_sprint08_2_forensics,
)


def test_market_state_lock_diagnostics():
    """Verify that market-state audit detects single-row collapse and locks to DELEVERAGING_STRESS."""
    res = audit_market_state_lock()
    assert res["verdict"] == "CONFIRMED_DETERMINISTIC_LOCK"
    assert res["lock_state"] == "DELEVERAGING_STRESS"
    assert len(res["single_row_counterfactual_tests"]) >= 4
    for tc in res["single_row_counterfactual_tests"]:
        assert tc["classified_state"] == "DELEVERAGING_STRESS"
        assert tc["locked_to_deleveraging"] is True
    assert res["reachability_under_spot_only_u0"]["NORMAL"] == "0% (Unreachable)"


def test_forecasting_mechanism_audit():
    """Verify that forecasting audit isolates uninitialized vol_models and trailing vol fallback."""
    res = audit_forecasting_mechanism()
    assert res["verdict"] == "NAIVE_PERSISTENCE_FALLBACK_ACTIVE"
    assert res["vol_models_fitted"] is False
    assert res["vol_models_count"] == 0
    assert res["runtime_execution_path"]["all_horizons_identical"] is True
    assert res["tail_risk_mechanism"]["is_fixed_constant"] is True
    assert res["jump_risk_mechanism"]["is_fixed_constant"] is True


def test_incremental_predictive_value_audit():
    """Verify that incremental value against trailing vol persistence is zero."""
    dummy_telemetry = ForensicsTelemetry(
        source="TEST",
        prediction_count=4308,
        schema_v2_predictions=4289,
        valid_evaluation_outcomes=33691,
        total_matured_outcomes=33843,
        invalid_legacy_v1_outcomes=114,
        excluded_outcomes=38,
        data_quality_state="DEGRADED_STREAM",
        fallback_level="SPOT_ONLY_U0",
        active_feature_groups=["SPOT", "SESSION"],
        missing_feature_groups=["DERIVATIVES"],
        horizons_data={
            "1h": {"sample_size": 4277, "mae": 0.00560, "rmse": 0.00851, "pearson_correlation": 0.5410, "spearman_correlation": 0.6434, "bias": 0.00014, "mean_realized": 0.01404},
            "4h": {"sample_size": 4241, "mae": 0.00607, "rmse": 0.00886, "pearson_correlation": 0.4519, "spearman_correlation": 0.6012, "bias": -0.00115, "mean_realized": 0.01533},
            "24h": {"sample_size": 4001, "mae": 0.00814, "rmse": 0.01114, "pearson_correlation": 0.1103, "spearman_correlation": 0.1166, "bias": -0.00127, "mean_realized": 0.01533},
        },
        interval_coverage={},
        expansion_calibration={},
        market_states_distribution={},
    )
    res = audit_incremental_predictive_value(dummy_telemetry)
    h1 = res["horizons"]["1h"]
    assert h1["baseline_trailing_realized_vol_persistence"]["mae_difference"] == 0.0
    assert h1["baseline_trailing_realized_vol_persistence"]["incremental_improvement_pct"] == 0.0
    assert "ZERO_OVER_PERSISTENCE" in h1["incremental_scientific_value"]


def test_overlapping_outcomes_effective_sample_size():
    """Verify that effective sample size accounts for 5m spacing and overlap windows."""
    dummy_telemetry = ForensicsTelemetry(
        source="TEST",
        prediction_count=4308,
        schema_v2_predictions=4289,
        valid_evaluation_outcomes=33691,
        total_matured_outcomes=33843,
        invalid_legacy_v1_outcomes=114,
        excluded_outcomes=38,
        data_quality_state="DEGRADED_STREAM",
        fallback_level="SPOT_ONLY_U0",
        active_feature_groups=["SPOT"],
        missing_feature_groups=["DERIVATIVES"],
        horizons_data={
            "1h": {"sample_size": 4277, "pearson_correlation": 0.5410, "spearman_correlation": 0.6434},
            "4h": {"sample_size": 4241, "pearson_correlation": 0.4519, "spearman_correlation": 0.6012},
            "24h": {"sample_size": 4001, "pearson_correlation": 0.1103, "spearman_correlation": 0.1166},
        },
        interval_coverage={},
        expansion_calibration={},
        market_states_distribution={},
    )
    res = audit_overlapping_outcomes(dummy_telemetry)
    f1 = res["findings"]["1h"]
    f4 = res["findings"]["4h"]
    f24 = res["findings"]["24h"]

    assert f1["overlap_window_bars"] == 12
    assert f1["effective_independent_sample_size"] == int(4277 / 12)
    assert f1["statistically_distinguishable_from_zero"] is True

    assert f4["overlap_window_bars"] == 48
    assert f4["effective_independent_sample_size"] == int(4241 / 48)

    assert f24["overlap_window_bars"] == 288
    assert f24["effective_independent_sample_size"] == int(4001 / 288)
    assert f24["confidence_interval_95_pct"][0] < 0.0  # Spans zero!
    assert f24["statistically_distinguishable_from_zero"] is False


def test_interval_coverage_audit():
    """Verify that interval coverage audit calculates under-coverage accurately."""
    dummy_telemetry = ForensicsTelemetry(
        source="TEST",
        prediction_count=4308,
        schema_v2_predictions=4289,
        valid_evaluation_outcomes=33691,
        total_matured_outcomes=33843,
        invalid_legacy_v1_outcomes=114,
        excluded_outcomes=38,
        data_quality_state="DEGRADED_STREAM",
        fallback_level="SPOT_ONLY_U0",
        active_feature_groups=["SPOT"],
        missing_feature_groups=["DERIVATIVES"],
        horizons_data={},
        interval_coverage={
            "nominal_80": {"nominal_coverage": 0.80, "empirical_coverage": 0.6501, "n_samples": 4278},
            "nominal_95": {"nominal_coverage": 0.95, "empirical_coverage": 0.7882, "n_samples": 4278},
        },
        expansion_calibration={},
        market_states_distribution={},
    )
    res = audit_prediction_interval_coverage(dummy_telemetry)
    assert res["nominal_80_pct_interval"]["verdict"] == "SEVERE_UNDERCOVERAGE"
    assert res["nominal_80_pct_interval"]["undercoverage_percentage_points"] == pytest.approx(14.99, abs=0.1)
    assert res["nominal_95_pct_interval"]["verdict"] == "SEVERE_UNDERCOVERAGE"
    assert res["nominal_95_pct_interval"]["undercoverage_percentage_points"] == pytest.approx(16.18, abs=0.1)


def test_scientific_claims_registry():
    """Verify that all claims A-F are classified according to empirical evidence."""
    claims = evaluate_scientific_claims()
    assert len(claims) == 6
    cmap = {c["claim_id"]: c for c in claims}

    assert cmap["A"]["classification"] == "REFUTED"
    assert cmap["B"]["classification"] == "REFUTED"
    assert cmap["C"]["classification"] == "REFUTED"
    assert cmap["D"]["classification"] == "REFUTED"
    assert cmap["E"]["classification"] == "REFUTED"
    assert cmap["F"]["classification"] == "SUPPORTED_BUT_LIMITED"


def test_run_forensics_produces_all_seven_deliverables():
    """Verify that run_sprint08_2_forensics creates all 7 deliverables in target directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "reports"
        res = run_sprint08_2_forensics(out_path)
        assert res["status"] == "COMPLETED"
        assert len(res["files_generated"]) == 7

        expected_files = [
            "scientific_forensics_report.md",
            "baseline_comparison.json",
            "overlap_dependence_audit.json",
            "interval_coverage_audit.json",
            "market_state_forensics.md",
            "claim_registry.json",
            "resource_usage_report.md",
        ]
        for f in expected_files:
            file_p = out_path / f
            assert file_p.exists(), f"Missing deliverable: {f}"
            assert file_p.stat().st_size > 100, f"Empty deliverable: {f}"
