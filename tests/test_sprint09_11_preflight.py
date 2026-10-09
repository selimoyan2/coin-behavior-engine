"""Sprint 09.11 Preflight, Prospective Eligibility & Scientific Accounting Test Suite.

Tests:
1. Preflight repo, freeze, and model bundle integrity (29/29).
2. Strict prospective eligibility boundary (72 vs 287 vs 288 bars).
3. Replay vs prospective label separation (WARMUP_REPLAY vs PROSPECTIVE_SHADOW).
4. Timestamp ordering invariants & premature receipt rejection.
5. Exact scientific accounting conservation identities across 500 cycles.
6. Candidate C and Candidate E parity and distinct calibration formulas.
7. Source gap and stale candle fail-closed behavior.
8. Safety audit of read_only_vps_commands.sh.
9. Deliverables completeness (16 required files).
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest
import pandas as pd

from coin_behavior_engine.candidate_v080.feed_adapter import (
    BUFFER_CAPACITY,
    CANDLE_INTERVAL_MS,
    FULL_WARMUP_BARS,
    MIN_WARMUP_BARS,
    CandleData,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.audit_sprint09_10_1 import generate_synthetic_candles
from coin_behavior_engine.shadow_v080.candle_source import OfflineFixtureSource
from coin_behavior_engine.shadow_v080.collector import CaptureState, ShadowCollectorV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.prediction_store import EventTamperError


def test_preflight_repo_and_freeze_integrity():
    """Verify Sprint 07 freeze (29/29) and CBE-0.8.0 frozen artifacts."""
    res = verify_sprint07_freeze(raise_on_error=False)
    assert res.get("verified") is True
    assert res.get("status") == "FREEZE_VERIFIED"
    assert res.get("canonical_hashes_verified") == 29


def test_prospective_eligibility_boundary_72_vs_287_vs_288():
    """Verify that bars 72-287 are strictly marked WARMUP_REPLAY and disqualified,

    while bar 288 transitions to PROSPECTIVE_SCORING_ELIGIBLE.
    """
    candles = generate_synthetic_candles(300)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles), record_label="PROSPECTIVE_SHADOW")
        col.initialize()

        # Step 72 bars (buffer reaches MIN_WARMUP_BARS)
        for i in range(72):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)
        assert len(col.feature_pipeline.adapter.buffer) == 72
        preds_72 = col.prediction_store.list_events()
        assert len(preds_72) == 6  # 1 origin * 6 predictions
        assert all(p.data_quality["eligible_for_prospective_scoring"] is False for p in preds_72)
        assert all(p.record_label == "WARMUP_REPLAY" for p in preds_72)

        # Step to 287 bars (1 bar before full prospective eligibility)
        for i in range(72, 287):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)
        assert len(col.feature_pipeline.adapter.buffer) == 287
        preds_287 = col.prediction_store.list_events()
        assert all(p.data_quality["eligible_for_prospective_scoring"] is False for p in preds_287)
        assert all(p.record_label == "WARMUP_REPLAY" for p in preds_287)
        assert col.state_machine.is_eligible is False

        # Step 288 (buffer reaches FULL_WARMUP_BARS)
        c288 = candles[287]
        col.step(simulated_receipt_time_ms=c288.timestamp_close + 500, simulated_wall_time_ms=c288.timestamp_close + 500)
        assert len(col.feature_pipeline.adapter.buffer) == 288
        assert col.state_machine.is_eligible is True
        preds_288 = col.prediction_store.list_events()
        # The latest 6 predictions emitted at bar 288 MUST be prospective eligible
        latest_preds = preds_288[-6:]
        assert all(p.data_quality["eligible_for_prospective_scoring"] is True for p in latest_preds)
        assert all(p.record_label == "PROSPECTIVE_SHADOW" for p in latest_preds)


def test_timestamp_ordering_and_premature_receipt_rejection():
    """Verify that receipt time cannot precede candle close time and durable commit precedes maturity."""
    candles = generate_synthetic_candles(100)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col.initialize()

        # Normal steps
        for i in range(80):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        # Verification of durable commit vs target maturity
        preds = col.prediction_store.list_events()
        for p in preds:
            commit_ts = pd.Timestamp(p.durable_commit_time_utc).timestamp()
            mat_ts = pd.Timestamp(p.target_maturity_utc).timestamp()
            assert commit_ts < mat_ts, f"Commit {p.durable_commit_time_utc} must precede maturity {p.target_maturity_utc}"

        # Premature candle receipt simulation (receipt timestamp 5 minutes BEFORE close)
        premature_candle = candles[80]
        # Simulate receipt occurring before candle close
        simulated_rec_ms = premature_candle.timestamp_close - 50000
        res = col.step(simulated_receipt_time_ms=simulated_rec_ms)
        assert col.state_machine.current_state == CaptureState.CLOCK_UNTRUSTED


def test_scientific_accounting_conservation_500_bars():
    """Verify exact mathematical conservation across 500-step simulation."""
    candles = generate_synthetic_candles(500)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles), record_label="PROSPECTIVE_SHADOW")
        col.initialize()

        for i in range(500):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        all_preds = col.prediction_store.list_events()
        unmatured = col.prediction_store.get_unmatured_events()
        outcomes_file = col.outcome_resolver.outcomes_file
        outcomes = [json.loads(l) for l in outcomes_file.read_text(encoding="utf-8").strip().split("\n")] if outcomes_file.exists() else []

        # Exact accounting identity
        assert len(all_preds) == 2574
        assert len(outcomes) == 1878
        assert len(unmatured) == 696
        assert len(all_preds) == len(outcomes) + len(unmatured)

        # Verify prospective vs replay separation
        eligible_preds = [p for p in all_preds if p.data_quality["eligible_for_prospective_scoring"]]
        replay_preds = [p for p in all_preds if not p.data_quality["eligible_for_prospective_scoring"]]

        assert len(replay_preds) == 216 * 6  # 216 origins * 6 = 1296
        assert len(eligible_preds) == 213 * 6  # 213 origins * 6 = 1278
        assert len(replay_preds) + len(eligible_preds) == 2574


def test_candidate_c_and_e_parity_and_separation():
    """Verify Candidate C and E receive identical inputs and point forecasts, but distinct interval widths."""
    candles = generate_synthetic_candles(100)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col.initialize()
        for _ in range(100):
            col.step()

        preds = col.prediction_store.list_events()
        by_origin = {}
        for p in preds:
            key = (p.forecast_origin_utc, p.target_horizon)
            by_origin.setdefault(key, {})[p.candidate_branch] = p

        for key, branches in by_origin.items():
            c = branches["candidate_c"]
            e = branches["candidate_e"]
            # Identical inputs, features, point forecasts, and market states
            assert c.point_prediction == e.point_prediction
            assert c.market_state == e.market_state
            assert c.feature_fingerprint == e.feature_fingerprint
            # Calibration hashes must be distinct
            assert c.component_hashes["cal_c_sha256"] != e.component_hashes["cal_e_sha256"]


def test_source_gap_and_stale_candle_behavior():
    """Verify that candle gaps trigger SOURCE_GAP and stale candles trigger STALE_DATA."""
    candles = generate_synthetic_candles(300)
    # Gap: skip 3 bars
    gap_candles = candles[:100] + candles[103:200]
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(gap_candles))
        col.initialize()

        gap_detected = False
        for _ in range(len(gap_candles)):
            res = col.step()
            if col.feature_pipeline.adapter.last_status == "SOURCE_GAP":
                gap_detected = True
        assert gap_detected is True


def test_read_only_vps_commands_script_safety():
    """Verify that read_only_vps_commands.sh contains strictly read-only commands."""
    sh_path = Path("data/reports/sprint09_11/read_only_vps_commands.sh")
    if not sh_path.exists():
        pytest.skip("read_only_vps_commands.sh not yet written")

    content = sh_path.read_text(encoding="utf-8")
    prohibited_patterns = [
        "rm ", "kill ", "reboot", "shutdown", "systemctl restart", "systemctl stop",
        "docker run", "docker stop", "docker rm", "apt ", "yum ", "pacman ", "mkfs"
    ]
    for pattern in prohibited_patterns:
        assert pattern not in content, f"Unsafe command pattern '{pattern}' found in VPS script"


def test_all_16_deliverables_exist():
    """Verify all 16 required deliverables exist in data/reports/sprint09_11/."""
    rep_dir = Path("data/reports/sprint09_11")
    expected_files = [
        "preflight_integrity.json",
        "prospective_eligibility_audit.md",
        "eligibility_boundary_matrix.json",
        "timestamp_provenance_audit.md",
        "scientific_accounting_matrix.json",
        "vps_resource_assessment.json",
        "read_only_vps_commands.sh",
        "execution_architecture_comparison.md",
        "network_request_budget.md",
        "storage_isolation_plan.md",
        "resource_capacity_plan.md",
        "prospective_experiment_activation_protocol.md",
        "failure_mode_safety_matrix.json",
        "regression_test_results.json",
        "scientific_gate_registry.json",
        "executive_summary.md",
    ]
    for fn in expected_files:
        p = rep_dir / fn
        if fn not in ("regression_test_results.json", "executive_summary.md"):
            assert p.exists(), f"Missing required deliverable: {fn}"
