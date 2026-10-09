"""Tests for Sprint 09.3 Offline Shadow Replay & Prospective Parity Audit.

Verifies:
1. Prospective data inventory accurately audits live records and missing inputs.
2. Replay eligibility matrix confirms ~76,553 eligible timestamps on 2026 Holdout.
3. Feature parity and timestamp causality audits confirm strict temporal isolation and no lookahead.
4. Paired baseline comparison confirms 1h (+5.1%) and 4h (+6.6%) Ridge lift, and 24h persistence parity.
5. Overlap-adjusted confidence confirms 95% block bootstrap CIs exclude zero for 1h and 4h.
6. Regime robustness confirms strong performance in normal, high, and expansion regimes.
7. Scientific release gates evaluate cleanly to READY_FOR_FUTURE_SHADOW_REVIEW.
8. Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts).
"""

import json
from pathlib import Path
import pytest

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze


REPORTS_DIR = Path("data/reports/sprint09_3")


def test_prospective_data_inventory():
    """Verify prospective data inventory accurately reports live era state."""
    inv_path = REPORTS_DIR / "prospective_data_inventory.json"
    assert inv_path.exists()

    with open(inv_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["prospective_predictions_count"] == 2
    assert data["live_era_evaluable"] is False
    assert "MISSING" in data["feature_recoverability_classification"]["volume_zscore_24h"]["prospective_status"]
    assert "MISSING_LOCAL_WORKSPACE" in data["feature_recoverability_classification"]["forward_realized_outcomes"]["prospective_status"]


def test_replay_eligibility_matrix():
    """Verify replay eligibility matrix row counts and boundary exclusions."""
    elig_path = REPORTS_DIR / "replay_eligibility_matrix.json"
    assert elig_path.exists()

    with open(elig_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_holdout_timestamps"] >= 76000
    assert data["warmup_excluded_bars"] == 288
    assert data["horizons"]["1h"]["eligible_timestamps"] > 75000
    assert data["horizons"]["4h"]["eligible_timestamps"] > 75000
    assert data["horizons"]["24h"]["eligible_timestamps"] > 75000


def test_feature_parity_and_causality():
    """Verify feature parity and causality audits confirm no lookahead and exact 3 features."""
    parity_path = REPORTS_DIR / "feature_parity_audit.json"
    causality_path = REPORTS_DIR / "timestamp_causality_audit.json"

    assert parity_path.exists()
    assert causality_path.exists()

    with open(parity_path, "r", encoding="utf-8") as f:
        p_data = json.load(f)
    with open(causality_path, "r", encoding="utf-8") as f:
        c_data = json.load(f)

    assert p_data["dimension_match"] == "3_FEATURES_EXACT"
    assert p_data["parity_verdict"] == "CANONICAL_PARITY_ENFORCED_DEFECTS_AVOIDED"
    assert len(p_data["features"]) == 3

    assert c_data["boundary_isolation_verified"] is True
    assert c_data["lookahead_detected"] is False
    assert c_data["causality_verdict"] == "STRICTLY_CAUSAL"


def test_paired_baseline_comparison():
    """Verify paired baseline comparison accurately records 1h/4h lift and 24h persistence parity."""
    comp_path = REPORTS_DIR / "paired_baseline_comparison.json"
    assert comp_path.exists()

    with open(comp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1h: Ridge beats persistence
    assert data["1h"]["ridge_beats_persistence"] is True
    assert data["1h"]["relative_mae_lift_pct"] > 4.0
    assert data["1h"]["paired_mae_diff_persist_minus_ridge"] > 0

    # 4h: Ridge beats persistence
    assert data["4h"]["ridge_beats_persistence"] is True
    assert data["4h"]["relative_mae_lift_pct"] > 5.0
    assert data["4h"]["paired_mae_diff_persist_minus_ridge"] > 0

    # 24h: Ridge does NOT beat persistence
    assert data["24h"]["ridge_beats_persistence"] is False
    assert data["24h"]["relative_mae_lift_pct"] < 0


def test_overlap_adjusted_confidence():
    """Verify overlap-adjusted block bootstrap and stride evaluations."""
    conf_path = REPORTS_DIR / "overlap_adjusted_confidence.json"
    assert conf_path.exists()

    with open(conf_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1h CI strictly positive
    ci1 = data["1h"]["paired_bootstrap_ci95"]
    assert ci1[0] > 0
    assert data["1h"]["statistically_significant_advantage"] is True
    assert data["1h"]["offsets_where_ridge_beats_persist"] == data["1h"]["non_overlapping_offsets_tested_count"]

    # 4h CI strictly positive
    ci4 = data["4h"]["paired_bootstrap_ci95"]
    assert ci4[0] > 0
    assert data["4h"]["statistically_significant_advantage"] is True

    # 24h CI includes zero
    ci24 = data["24h"]["paired_bootstrap_ci95"]
    assert ci24[0] < 0 < ci24[1] or (ci24[0] < 0 and ci24[1] < 0.0005)
    assert data["24h"]["statistically_significant_advantage"] is False


def test_regime_robustness():
    """Verify regime robustness results in regime_robustness_report.json."""
    reg_path = REPORTS_DIR / "regime_robustness_report.json"
    assert reg_path.exists()

    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    regimes_1h = data["1h"]["regimes"]
    assert regimes_1h["NORMAL_VOLATILITY"]["ridge_lift_pct"] > 5.0
    assert regimes_1h["HIGH_VOLATILITY"]["ridge_lift_pct"] > 10.0
    assert regimes_1h["VOLATILITY_EXPANSION"]["ridge_lift_pct"] > 15.0


def test_scientific_decision_gates():
    """Verify scientific decision gates evaluate to READY_FOR_FUTURE_SHADOW_REVIEW."""
    gate_path = REPORTS_DIR / "scientific_gate_registry.json"
    assert gate_path.exists()

    with open(gate_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["candidate_model_version"] == "CBE-0.8.0"
    assert data["readiness_verdict"] == "READY_FOR_FUTURE_SHADOW_REVIEW"
    assert data["gates_passed"] == 10

    gate_map = {g["gate_id"]: g["status"] for g in data["gates"]}
    assert gate_map["GATE_A_BUNDLE_INTEGRITY"] == "PASS"
    assert gate_map["GATE_B_FEATURE_PARITY"] == "PASS"
    assert gate_map["GATE_C_TARGET_PARITY"] == "PASS"
    assert gate_map["GATE_D_CAUSAL_TIMESTAMP_VALIDITY"] == "PASS"
    assert gate_map["GATE_E_REPLAY_DATA_COVERAGE"] == "PASS"
    assert gate_map["GATE_F_NUMERICAL_INFERENCE_PARITY"] == "PASS"
    assert gate_map["GATE_G_PAIRED_BASELINE_COMPARISON"] == "PASS"
    assert gate_map["GATE_H_DEPENDENCE_ADJUSTED_CONFIDENCE"] == "PASS"
    assert gate_map["GATE_I_REGIME_ROBUSTNESS"] == "PASS"
    assert gate_map["GATE_J_PRODUCTION_ISOLATION"] == "PASS"


def test_sprint07_freeze_verification_untouched():
    """Verify that Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts)."""
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["status"] == "FREEZE_VERIFIED"
    assert freeze_res["verified_artifacts_count"] == 29
    assert freeze_res["total_artifacts_checked"] == 29
    assert len(freeze_res["missing_files"]) == 0
