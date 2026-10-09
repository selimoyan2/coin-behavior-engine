"""Tests for Sprint 09.7: Prospective Shadow Protocol & Calibration Decision Freeze.

Validates:
1. Candidate branch loading (Branch C and Branch E).
2. Prospective experiment manifest validation and integrity.
3. Event log record hashing and cryptographic hash-chain continuity.
4. Idempotent duplicate event rejection.
5. Recovery from log interruption and tamper detection.
6. Chronological eligibility invariants (creation <= maturity, cutoff <= origin).
7. Non-overwriting outcome maturity pairing.
8. Paired branch comparison (identical point forecast, different interval bounds).
9. Feature availability validation and feed parity audit status.
10. Existence and schema validity of all 15 research deliverables.
11. Sprint 07 frozen model preservation (29/29 artifacts).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.calibration_branches import (
    BranchIntervals,
    CalibrationBranchC,
    CalibrationBranchE,
    CalibrationBranchError,
    DualBranchCalibrationManager,
)
from coin_behavior_engine.candidate_v080.protocol_simulator import (
    AppendOnlyEvent,
    DuplicateEventError,
    EventChainIntegrityError,
    OfflineProtocolSimulator,
    compute_payload_hash,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze

MODELS_DIR = Path("data/models")
BRANCH_C_PATH = MODELS_DIR / "cbe_interval_calibration_v080_candidate_c.json"
BRANCH_E_PATH = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
BUNDLE_PATH = MODELS_DIR / "cbe_model_bundle_v080.json"
THRESHOLDS_PATH = MODELS_DIR / "cbe_state_thresholds_v080.json"
REPORTS_DIR = Path("data/reports/sprint09_7")


# ---------------------------------------------------------------------------
# Section 1: Candidate Branch Loading Tests
# ---------------------------------------------------------------------------

def test_01_branch_c_loading_and_intervals():
    branch_c = CalibrationBranchC(BRANCH_C_PATH)
    assert branch_c.BRANCH_ID == "BRANCH_C_VOLATILITY_NORMALIZED"
    assert branch_c.STATUS == "FROZEN_RESEARCH_BRANCH"

    itv = branch_c.compute_intervals(point_forecast=0.030, horizon="1h")
    assert isinstance(itv, BranchIntervals)
    assert itv.branch_id == branch_c.BRANCH_ID
    assert itv.point_forecast == 0.030
    assert 0.0 <= itv.lower_95 <= itv.lower_80 <= 0.030 <= itv.upper_80 <= itv.upper_95


def test_02_branch_e_loading_and_intervals():
    branch_e = CalibrationBranchE(BRANCH_E_PATH)
    assert branch_e.BRANCH_ID == "BRANCH_E_CONSERVATIVE_HYBRID"
    assert branch_e.STATUS == "FROZEN_RESEARCH_BRANCH"

    itv = branch_e.compute_intervals(point_forecast=0.030, horizon="1h", market_state="HIGH_VOLATILITY")
    assert isinstance(itv, BranchIntervals)
    assert itv.branch_id == branch_e.BRANCH_ID
    assert itv.point_forecast == 0.030
    assert 0.0 <= itv.lower_95 <= itv.lower_80 <= 0.030 <= itv.upper_80 <= itv.upper_95


def test_03_dual_branch_manager_identical_point_forecast():
    manager = DualBranchCalibrationManager(BRANCH_C_PATH, BRANCH_E_PATH)
    res = manager.compute_dual_intervals(point_forecast=0.035, horizon="1h", market_state="NORMAL_VOLATILITY")
    assert "branch_c" in res
    assert "branch_e" in res
    # Point forecast must be identical
    assert res["branch_c"].point_forecast == res["branch_e"].point_forecast == 0.035
    # Intervals are distinct due to different calibration methods
    assert res["branch_c"].lower_80 != res["branch_e"].lower_80 or res["branch_c"].upper_95 != res["branch_e"].upper_95


def test_04_negative_or_nan_point_forecast_fails():
    branch_c = CalibrationBranchC(BRANCH_C_PATH)
    with pytest.raises(CalibrationBranchError):
        branch_c.compute_intervals(-0.01, horizon="1h")
    with pytest.raises(CalibrationBranchError):
        branch_c.compute_intervals(float("nan"), horizon="1h")


def test_05_unknown_horizon_fails():
    branch_e = CalibrationBranchE(BRANCH_E_PATH)
    with pytest.raises(CalibrationBranchError):
        branch_e.compute_intervals(0.02, horizon="72h")


# ---------------------------------------------------------------------------
# Section 2: Simulator & Event Log Hashing Tests
# ---------------------------------------------------------------------------

def test_06_compute_payload_hash_deterministic():
    payload1 = {"b": 2, "a": 1, "nested": {"y": [1, 2], "x": "test"}}
    payload2 = {"a": 1, "nested": {"x": "test", "y": [1, 2]}, "b": 2}
    h1 = compute_payload_hash(payload1)
    h2 = compute_payload_hash(payload2)
    assert h1 == h2
    assert len(h1) == 64


def test_07_simulator_event_chaining():
    sim = OfflineProtocolSimulator(
        bundle_path=str(BUNDLE_PATH),
        thresholds_path=str(THRESHOLDS_PATH),
        branch_c_path=str(BRANCH_C_PATH),
        branch_e_path=str(BRANCH_E_PATH),
    )

    ev1 = sim.append_event("CHECKPOINT_CREATED", "2026-03-01T00:00:00Z", {"msg": "genesis"})
    assert ev1.sequence_number == 1
    assert ev1.previous_record_hash.startswith("GENESIS_")

    ev2 = sim.append_event("CHECKPOINT_CREATED", "2026-03-01T01:00:00Z", {"msg": "second"})
    assert ev2.sequence_number == 2
    assert ev2.previous_record_hash == ev1.record_hash

    audit = sim.verify_event_chain()
    assert audit["verified"] is True
    assert audit["event_count"] == 2


def test_08_duplicate_event_rejection():
    sim = OfflineProtocolSimulator(
        bundle_path=str(BUNDLE_PATH),
        thresholds_path=str(THRESHOLDS_PATH),
        branch_c_path=str(BRANCH_C_PATH),
        branch_e_path=str(BRANCH_E_PATH),
    )

    payload = {
        "forecast_origin_timestamp_utc": "2026-03-01T12:00:00Z",
        "candidate_branch_id": "BRANCH_C_VOLATILITY_NORMALIZED",
        "forecast_horizon": "1h",
        "point_prediction": 0.025,
    }

    sim.append_event("FORECAST_EMITTED", "2026-03-01T12:00:00Z", payload)

    # Attempting to append duplicate must raise DuplicateEventError
    with pytest.raises(DuplicateEventError):
        sim.append_event("FORECAST_EMITTED", "2026-03-01T12:00:00Z", payload)


def test_09_event_chain_tamper_detection():
    sim = OfflineProtocolSimulator(
        bundle_path=str(BUNDLE_PATH),
        thresholds_path=str(THRESHOLDS_PATH),
        branch_c_path=str(BRANCH_C_PATH),
        branch_e_path=str(BRANCH_E_PATH),
    )

    sim.append_event("CHECKPOINT_CREATED", "2026-03-01T00:00:00Z", {"step": 1})
    sim.append_event("CHECKPOINT_CREATED", "2026-03-01T01:00:00Z", {"step": 2})
    sim.append_event("CHECKPOINT_CREATED", "2026-03-01T02:00:00Z", {"step": 3})

    tampered_events = [e for e in sim.events]
    # Tamper with step 2 payload
    tampered_events[1].payload["step"] = 999

    with pytest.raises(EventChainIntegrityError):
        sim.verify_event_chain(tampered_events)


def test_10_chronological_eligibility_invariants():
    sim = OfflineProtocolSimulator(
        bundle_path=str(BUNDLE_PATH),
        thresholds_path=str(THRESHOLDS_PATH),
        branch_c_path=str(BRANCH_C_PATH),
        branch_e_path=str(BRANCH_E_PATH),
    )

    features = {
        "volatility_realized_24h": 0.0018,
        "volatility_compression_ratio": 1.05,
        "volume_zscore_24h": 0.25,
    }
    origin = pd.Timestamp("2026-03-01T12:00:00Z")
    creation = pd.Timestamp("2026-03-01T12:00:05Z")
    targets = {"fwd_vol_1h": 0.0019, "fwd_vol_4h": 0.0020, "fwd_vol_24h": 0.0021}

    sim_res = sim.simulate_bar(features, origin, creation, realized_targets=targets)
    assert sim_res["forecasts_count"] == 6  # 3 horizons * 2 branches

    # Check forecast events
    fc_events = [e for e in sim.events if e.event_type == "FORECAST_EMITTED"]
    for e in fc_events:
        p = e.payload
        t_create = pd.Timestamp(p["record_creation_timestamp_utc"])
        t_mat = pd.Timestamp(p["forecast_target_maturity_timestamp_utc"])
        t_cutoff = pd.Timestamp(p["source_data_cutoff_timestamp_utc"])
        t_orig = pd.Timestamp(p["forecast_origin_timestamp_utc"])

        assert t_create <= t_mat, "Creation time must be <= maturity time"
        assert t_cutoff <= t_orig, "Data cutoff must be <= forecast origin"
        assert p["record_type"] == "HISTORICAL_REPLAY"


def test_11_outcome_maturity_pairing_and_immutability():
    sim = OfflineProtocolSimulator(
        bundle_path=str(BUNDLE_PATH),
        thresholds_path=str(THRESHOLDS_PATH),
        branch_c_path=str(BRANCH_C_PATH),
        branch_e_path=str(BRANCH_E_PATH),
    )

    features = {"volatility_realized_24h": 0.0018, "volatility_compression_ratio": 1.05, "volume_zscore_24h": 0.25}
    origin = pd.Timestamp("2026-03-01T12:00:00Z")
    targets = {"fwd_vol_1h": 0.0020, "fwd_vol_4h": 0.0021, "fwd_vol_24h": 0.0022}

    sim.simulate_bar(features, origin, origin, realized_targets=targets)

    # Verify outcomes reference prediction_record_hash
    fc_events = [e for e in sim.events if e.event_type == "FORECAST_EMITTED"]
    out_events = [e for e in sim.events if e.event_type == "OUTCOME_MATURED"]

    assert len(out_events) == len(fc_events)
    fc_hashes = {e.record_hash for e in fc_events}

    for oe in out_events:
        assert oe.payload["prediction_record_hash"] in fc_hashes
        assert oe.payload["status"] == "MATURED"
        assert oe.payload["realized_volatility"] > 0.0


# ---------------------------------------------------------------------------
# Section 3: Deliverables, Artifacts & Freeze Tests
# ---------------------------------------------------------------------------

def test_12_all_15_deliverables_exist():
    expected_files = [
        "sprint09_6_gate_correction.md",
        "calibration_branch_freeze.json",
        "prospective_experiment_manifest.json",
        "prospective_forecast_schema.json",
        "prospective_outcome_schema.json",
        "append_only_event_schema.json",
        "integrity_and_recovery_protocol.md",
        "baseline_and_pairing_policy.md",
        "statistical_analysis_plan.md",
        "experiment_duration_and_stopping_rules.md",
        "offline_protocol_simulation.json",
        "prospective_feed_readiness_audit.json",
        "resource_budget_and_isolation.md",
        "scientific_gate_registry.json",
        "executive_summary.md",
    ]
    for fname in expected_files:
        fpath = REPORTS_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"Empty deliverable: {fname}"


def test_13_calibration_branch_freeze_schema():
    with open(REPORTS_DIR / "calibration_branch_freeze.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == "CBE-CALIBRATION-FREEZE-0.8.0"
    assert data["calibration_winner"] == "UNDETERMINED"
    assert data["calibration_branches"]["BRANCH_C"]["status"] == "FROZEN_RESEARCH_BRANCH"
    assert data["calibration_branches"]["BRANCH_E"]["status"] == "FROZEN_RESEARCH_BRANCH"


def test_14_prospective_experiment_manifest_schema():
    with open(REPORTS_DIR / "prospective_experiment_manifest.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["experiment_id"] == "EXP-CBE-0.8.0-SHADOW-2026"
    assert "ridge_bundle" in data["frozen_artifacts"]
    assert "calibration_branch_c" in data["frozen_artifacts"]
    assert "calibration_branch_e" in data["frozen_artifacts"]


def test_15_prospective_feed_parity_status():
    with open(REPORTS_DIR / "prospective_feed_readiness_audit.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["feed_parity_status"] == "NOT_VERIFIED"
    assert data["volume_feature_available_in_live_records"] is False


def test_16_scientific_gate_registry_audit():
    with open(REPORTS_DIR / "scientific_gate_registry.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["gates_evaluated_count"] == 12
    assert data["gates_passed_count"] == 11
    assert data["gates_not_verified_count"] == 1
    assert data["overall_verdict"] == "PROSPECTIVE_PROTOCOL_FROZEN_PENDING_FEED_PARITY"

    gate_k = [g for g in data["gates"] if g["gate_id"] == "GATE_K_PROSPECTIVE_FEED_PARITY"][0]
    assert gate_k["status"] == "NOT_VERIFIED"


def test_17_sprint07_freeze_verification_untouched():
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["canonical_hashes_verified"] == 29
    assert freeze_res["status"] == "FREEZE_VERIFIED"
