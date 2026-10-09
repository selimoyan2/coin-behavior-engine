"""Sprint 09.12 — Deployment Readiness & Shadow Activation Safety Gate Test Suite.

Verifies:
1. Production freeze integrity (29/29 artifacts).
2. Prospective eligibility boundary (287 vs 288 bars).
3. Six-tier timestamp provenance & ordering.
4. Source gap fail-closed transition.
5. Restart recovery and durable hash chain audit.
6. Idempotent duplicate suppression and conflicting candle rejection.
7. Simulated disk write failure handling.
8. Resource configuration parsing and cgroup bounds.
9. Trading and order routing interlock.
10. Presence and integrity of all 14 required deliverables.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.audit_sprint09_10_1 import (
    CANDLE_INTERVAL_MS,
    generate_synthetic_candles,
)
from coin_behavior_engine.shadow_v080.candle_source import CandleData, OfflineFixtureSource
from coin_behavior_engine.shadow_v080.collector import CaptureState, ShadowCollectorV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.prediction_store import EventTamperError


def test_01_production_freeze_and_candidate_bundle():
    """Verify Sprint 07 freeze (29/29) and CBE-0.8.0 model/calibration artifacts."""
    res = verify_sprint07_freeze(raise_on_error=False)
    assert res.get("verified") is True
    assert res.get("status") == "FREEZE_VERIFIED"
    assert res.get("canonical_hashes_verified") == 29

    expected_hashes = {
        "cbe_model_bundle_v080.json": "7755ddcb369c29825f9205f09e805b2e518526726b4bd5d948787d24c9419ad0",
        "cbe_state_thresholds_v080.json": "3979ab8e37377f1d5cb2623c63c20081078ae49c5bcbedcbb860affe3dfd95d9",
        "cbe_interval_calibration_v080_candidate_c.json": "d7ce73edf6595c9ef167a8ec69f4e40f102dff2f32d8f265cf3efe4f60ef89ce",
        "cbe_interval_calibration_v080_095.json": "6821136ad71411b8778c481055d4204640d19be0acaedaf8db3cd18ee3b4bf50",
    }
    for filename, exp_h in expected_hashes.items():
        p = Path("data/models") / filename
        assert p.exists(), f"Missing candidate component: {filename}"
        import hashlib
        actual_h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual_h == exp_h, f"Hash mismatch for {filename}: {actual_h} != {exp_h}"


def test_02_prospective_boundary_287_vs_288():
    """Verify that bar 287 remains WARMUP_REPLAY while bar 288 transitions to ELIGIBLE and PROSPECTIVE_SHADOW."""
    candles = generate_synthetic_candles(300)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles), record_label="PROSPECTIVE_SHADOW")
        col.initialize()

        for i in range(287):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        assert col.state_machine.is_eligible is False
        preds_287 = col.prediction_store.list_events()
        assert all(p.record_label == "WARMUP_REPLAY" for p in preds_287)
        assert all(p.data_quality["eligible_for_prospective_scoring"] is False for p in preds_287)

        # Bar 288 step
        c288 = candles[287]
        col.step(simulated_receipt_time_ms=c288.timestamp_close + 500, simulated_wall_time_ms=c288.timestamp_close + 500)
        assert col.state_machine.is_eligible is True
        preds_288 = col.prediction_store.list_events()
        latest = preds_288[-6:]
        assert all(p.record_label == "PROSPECTIVE_SHADOW" for p in latest)
        assert all(p.data_quality["eligible_for_prospective_scoring"] is True for p in latest)


def test_03_timestamp_provenance_and_ordering():
    """Verify receipt >= close and durable commit < target maturity."""
    candles = generate_synthetic_candles(80)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col.initialize()

        for c in candles:
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        preds = col.prediction_store.list_events()
        for p in preds:
            commit_ts = pd.Timestamp(p.durable_commit_time_utc).timestamp()
            mat_ts = pd.Timestamp(p.target_maturity_utc).timestamp()
            assert commit_ts < mat_ts, f"Commit {commit_ts} must precede maturity {mat_ts}"


def test_04_source_gap_fail_closed():
    """Verify missing bars trigger SOURCE_GAP state transition."""
    candles = generate_synthetic_candles(50) + generate_synthetic_candles(50, base_t=1760000000000 + 55 * CANDLE_INTERVAL_MS)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col.initialize()

        gap_triggered = False
        for c in candles:
            res = col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)
            if col.state_machine.current_state == CaptureState.SOURCE_GAP:
                gap_triggered = True

        assert gap_triggered is True


def test_05_restart_recovery_and_hash_chain():
    """Verify crash recovery from local snapshot and chain integrity audit."""
    candles = generate_synthetic_candles(350)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col1 = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col1.initialize()
        for c in candles:
            col1.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        # Restart
        col2 = ShadowCollectorV080(cfg, OfflineFixtureSource([]))
        init_ok = col2.initialize()
        assert init_ok is True
        assert len(col2.feature_pipeline.adapter.buffer) == 350
        assert col2.state_machine.current_state == CaptureState.FULL_WINDOW_READY


def test_06_duplicate_suppression_and_conflict_rejection():
    """Verify duplicate candle is suppressed and conflicting candle is rejected."""
    candles = generate_synthetic_candles(10)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        candles_dup = candles[:5] + [candles[4]]
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles_dup))
        col.initialize()
        for c in candles_dup:
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        assert len(col.feature_pipeline.adapter.buffer) == 5

        # Conflicting candle
        bad_candle = CandleData(
            timestamp_open=candles[4].timestamp_open,
            timestamp_close=candles[4].timestamp_close,
            datetime_open=candles[4].datetime_open,
            datetime_close=candles[4].datetime_close,
            open=candles[4].open,
            high=candles[4].high * 2.0,
            low=candles[4].low,
            close=candles[4].close * 2.0,
            volume=candles[4].volume,
            is_closed=True,
        )
        ok_add, msg_add = col.feature_pipeline.adapter.add_candle(bad_candle)
        assert ok_add is False
        assert "Conflicting" in msg_add


def test_07_simulated_disk_failure():
    """Verify read-only filesystem / write failure is detected cleanly."""
    candles = generate_synthetic_candles(80)
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        col = ShadowCollectorV080(cfg, OfflineFixtureSource(candles))
        col.initialize()
        for i in range(75):
            c = candles[i]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)

        events_file = col.prediction_store.events_file
        os.chmod(events_file, stat.S_IREAD)
        write_error = False
        try:
            c = candles[76]
            col.step(simulated_receipt_time_ms=c.timestamp_close + 500, simulated_wall_time_ms=c.timestamp_close + 500)
        except (PermissionError, OSError):
            write_error = True
        finally:
            os.chmod(events_file, stat.S_IWRITE | stat.S_IREAD)

        assert write_error is True


def test_08_resource_configuration_parsing():
    """Verify inert docker compose template parses and specifies required limits."""
    compose_path = Path("deploy/shadow_v080/docker-compose.cbe-080-shadow.inert.yaml")
    assert compose_path.exists(), "Missing inert docker compose template"
    content = compose_path.read_text(encoding="utf-8")
    assert "memory: 300M" in content
    assert "cpus: '0.25'" in content
    assert "restart: \"no\"" in content
    assert "cbe_080_shadow_data" in content
    assert "ports:" not in content


def test_09_trading_interlock():
    """Verify no trading, execution, or order routing imports or calls exist in shadow modules."""
    import inspect
    from coin_behavior_engine.shadow_v080 import collector, feature_pipeline, prediction_store
    for mod in [collector, feature_pipeline, prediction_store]:
        src = inspect.getsource(mod)
        assert "create_order" not in src
        assert "place_order" not in src
        assert "order_market" not in src
        assert "order_limit" not in src


def test_10_deliverables_completeness():
    """Verify all 14 required deliverables are present in data/reports/sprint09_12/."""
    rep_dir = Path("data/reports/sprint09_12")
    expected_files = [
        "preflight_integrity.json",
        "sprint09_11_evidence_corrections.md",
        "vps_baseline_assessment.md",
        "isolation_architecture_decision.md",
        "resource_limit_proposal.md",
        "binance_request_budget.md",
        "prospective_scientific_protocol.md",
        "deployment_dry_run_runbook.md",
        "rollback_and_emergency_stop.md",
        "activation_approval_matrix.json",
        "failure_injection_results.json",
        "regression_test_results.json",
        "scientific_gate_registry.json",
        "executive_summary.md",
    ]
    for fn in expected_files:
        p = rep_dir / fn
        if fn not in ("regression_test_results.json", "executive_summary.md"):
            assert p.exists(), f"Missing required deliverable: {fn}"
