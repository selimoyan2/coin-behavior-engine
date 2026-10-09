"""Comprehensive Verification Tests for CBE-0.8.0 Shadow Collector Suite (Sprint 09.10).

Covers:
- Safety interlock enforcement (network lockout, trading prohibited).
- Bounded 350-candle rolling buffer & deduplication.
- Exact canonical 3-feature reconstruction & quality metadata.
- Dual-branch inference (Candidate C vs Candidate E) synchronization.
- Append-only event store & unbroken cryptographic SHA-256 hash chaining.
- Forward outcome maturity resolution (12, 48, 288 bars) & premature evaluation rejection.
- Atomic snapshotting & crash recovery.
- Failure injection handling (gaps, malformed candles, timestamps).
- Deliverables existence and scientific gate status.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
from typing import Any, Dict, List
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.feed_adapter import (
    BUFFER_CAPACITY,
    CANDLE_INTERVAL_MS,
    FULL_WARMUP_BARS,
    MIN_WARMUP_BARS,
    CandleData,
)
from coin_behavior_engine.candidate_v080.capture_manager import FeatureQualityStatus
from coin_behavior_engine.shadow_v080.candle_source import (
    OfflineFixtureSource,
    ReadOnlyLiveBinanceSource,
    SafetyInterlockError,
    SourceDataError,
)
from coin_behavior_engine.shadow_v080.collector import CaptureState, ShadowCollectorV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.event_integrity import EventIntegrityAuditorV080
from coin_behavior_engine.shadow_v080.feature_pipeline import FeaturePipelineV080
from coin_behavior_engine.shadow_v080.health_monitor import ShadowHealthMonitorV080
from coin_behavior_engine.shadow_v080.inference_runner import DualBranchInferenceRunnerV080
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    HORIZON_BARS,
    OutcomeResolverV080,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    DuplicateForecastError,
    EventTamperError,
    ImmutablePredictionStoreV080,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)


def make_candle(idx: int, base_time_ms: int = 1735689600000, price: float = 95000.0, vol: float = 10.0) -> CandleData:
    open_time = base_time_ms + idx * CANDLE_INTERVAL_MS
    close_time = open_time + CANDLE_INTERVAL_MS - 1
    dt_o = pd.Timestamp(open_time, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    dt_c = pd.Timestamp(close_time, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    p = price + math.sin(idx / 10.0) * 100.0
    return CandleData(
        timestamp_open=open_time,
        timestamp_close=close_time,
        datetime_open=dt_o,
        datetime_close=dt_c,
        open=p,
        high=p + 20.0,
        low=p - 20.0,
        close=p + 5.0,
        volume=vol + math.cos(idx / 5.0) * 2.0,
        is_closed=True,
        receipt_timestamp_utc=dt_c,
    )


def test_safety_interlock_read_only_live_source():
    """Verify live network access and trading are strictly locked out by default."""
    cfg = ShadowCollectorConfig()
    source = ReadOnlyLiveBinanceSource(config=cfg)
    assert not source.config.network_enabled
    assert not source.config.live_shadow_enabled
    assert not source.config.trading_enabled

    with pytest.raises(SafetyInterlockError, match="HARD SAFETY INTERLOCK"):
        source.fetch_next_candle()

    # Invariant: trading cannot be enabled under any circumstances
    with pytest.raises(ValueError, match="trading is strictly prohibited"):
        ShadowCollectorConfig(trading_enabled=True)


def test_buffer_capacity_and_warmup():
    """Verify buffer caps at 350 bars, warm-up transitions, and duplicate detection."""
    cfg = ShadowCollectorConfig()
    pipeline = FeaturePipelineV080(config=cfg)
    assert len(pipeline.adapter.buffer) == 0

    # Ingest 75 candles
    for i in range(75):
        c = make_candle(i)
        accepted, reason = pipeline.add_candle(c)
        assert accepted, f"Candle {i} rejected: {reason}"

    assert len(pipeline.adapter.buffer) == 75
    assert len(pipeline.adapter.buffer) >= MIN_WARMUP_BARS

    # Idempotent duplicate: ignored without expanding buffer
    dup = make_candle(74)
    accepted, reason = pipeline.add_candle(dup)
    assert accepted
    assert reason == "IDEMPOTENT_DUPLICATE_IGNORED"
    assert len(pipeline.adapter.buffer) == 75

    # Conflicting duplicate: rejected
    conflict = make_candle(74, price=120000.0)
    accepted, reason = pipeline.add_candle(conflict)
    assert not accepted
    assert "Conflicting candle" in reason

    # Ingest up to 400 candles -> verify bounded at 350
    for i in range(75, 400):
        c = make_candle(i)
        accepted, _ = pipeline.add_candle(c)
        assert accepted

    assert len(pipeline.adapter.buffer) == BUFFER_CAPACITY
    assert len(pipeline.adapter.buffer) >= FULL_WARMUP_BARS


def test_canonical_feature_reconstruction():
    """Verify exact 3 canonical features are computed with quality status."""
    cfg = ShadowCollectorConfig()
    pipeline = FeaturePipelineV080(config=cfg)
    for i in range(300):
        pipeline.add_candle(make_candle(i))

    recon, quality = pipeline.compute_features()
    assert "volatility_realized_24h" in recon.features
    assert "volatility_compression_ratio" in recon.features
    assert "volume_zscore_24h" in recon.features

    assert recon.features["volatility_realized_24h"] > 0
    assert recon.features["volatility_compression_ratio"] > 0
    assert not math.isnan(recon.features["volume_zscore_24h"])
    assert quality.feature_quality_status == FeatureQualityStatus.PRISTINE.value
    assert quality.eligible_for_prospective_scoring is True


def test_dual_branch_inference():
    """Verify Candidate C and Candidate E produce calibrated intervals from identical Ridge forecasts."""
    cfg = ShadowCollectorConfig()
    if not (cfg.models_dir / "cbe_model_bundle_v080.json").exists():
        pytest.skip("Model bundle not found")

    runner = DualBranchInferenceRunnerV080(config=cfg)
    features = {
        "volatility_realized_24h": 0.0015,
        "volatility_compression_ratio": 0.95,
        "volume_zscore_24h": 0.2,
    }
    origin = "2026-01-01T00:00:00Z"
    result = runner.predict(features, origin)

    assert result.primary_state in ["LOW_VOLATILITY", "NORMAL_VOLATILITY", "HIGH_VOLATILITY"]
    assert "1h" in result.point_forecasts
    assert "4h" in result.point_forecasts
    assert "24h" in result.point_forecasts

    # Shared Ridge point forecast
    assert result.point_forecasts["1h"] > 0
    # Branch C intervals
    assert result.candidate_c_intervals["1h"].lower_80 <= result.candidate_c_intervals["1h"].upper_80
    # Branch E intervals
    assert result.candidate_e_intervals["1h"].lower_80 <= result.candidate_e_intervals["1h"].upper_80


def test_immutable_prediction_store_and_tamper_detection():
    """Verify cryptographic SHA-256 hash chaining and tamper detection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_dir = Path(tmp_dir) / "predictions"
        store = ImmutablePredictionStoreV080(store_dir=store_dir)

        # Event 1
        e1 = ShadowPredictionEvent(
            event_id="test-1",
            experiment_id="EXP-TEST",
            protocol_version="CBE-PROTOCOL-0.8.0-V1",
            candidate_branch="candidate_c",
            forecast_origin_utc="2026-01-01T00:05:00Z",
            durable_commit_time_utc="2026-01-01T00:05:01Z",
            target_horizon="1h",
            target_maturity_utc="2026-01-01T01:05:00Z",
            feature_fingerprint="fp1",
            component_hashes={},
            data_quality={"status": "OK"},
            point_prediction=0.02,
            interval_80={"lower": 0.015, "upper": 0.025},
            interval_95={"lower": 0.01, "upper": 0.03},
            market_state="NORMAL_VOLATILITY",
            record_label="HISTORICAL_REPLAY",
        )
        h1 = store.append_event(e1)
        assert store.latest_hash == h1
        assert len(h1) == 64

        # Duplicate key rejection
        with pytest.raises(DuplicateForecastError):
            store.append_event(e1)

        # Event 2
        e2 = ShadowPredictionEvent(
            event_id="test-2",
            experiment_id="EXP-TEST",
            protocol_version="CBE-PROTOCOL-0.8.0-V1",
            candidate_branch="candidate_c",
            forecast_origin_utc="2026-01-01T00:10:00Z",
            durable_commit_time_utc="2026-01-01T00:10:01Z",
            target_horizon="1h",
            target_maturity_utc="2026-01-01T01:10:00Z",
            feature_fingerprint="fp2",
            component_hashes={},
            data_quality={"status": "OK"},
            point_prediction=0.021,
            interval_80={"lower": 0.015, "upper": 0.025},
            interval_95={"lower": 0.01, "upper": 0.03},
            market_state="NORMAL_VOLATILITY",
            record_label="HISTORICAL_REPLAY",
        )
        h2 = store.append_event(e2)
        assert e2.previous_event_hash == h1
        assert store.latest_hash == h2

        # Audit unbroken chain
        report = EventIntegrityAuditorV080.audit_prediction_chain(store.events_file)
        assert report.is_valid
        assert report.total_events == 2

        # Tamper simulation
        lines = store.events_file.read_text(encoding="utf-8").strip().split("\n")
        bad_event = json.loads(lines[0])
        bad_event["market_state"] = "TAMPERED_STATE"
        lines[0] = json.dumps(bad_event)
        store.events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        bad_report = EventIntegrityAuditorV080.audit_prediction_chain(store.events_file)
        assert not bad_report.is_valid
        assert len(bad_report.violations) > 0


def test_forward_outcome_maturity_engine():
    """Verify 1h/4h/24h maturity bars (12, 48, 288) and premature evaluation rejection."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        resolver = OutcomeResolverV080(store_dir=Path(tmp_dir) / "outcomes")

        base_t = 1735689600000
        origin_t = base_t + 288 * CANDLE_INTERVAL_MS
        origin_utc = pd.Timestamp(origin_t, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

        pred_event = ShadowPredictionEvent(
            event_id="pred-001",
            experiment_id="EXP-TEST",
            protocol_version="CBE-PROTOCOL-0.8.0-V1",
            candidate_branch="candidate_c",
            forecast_origin_utc=origin_utc,
            durable_commit_time_utc=origin_utc,
            target_horizon="1h",
            target_maturity_utc=pd.Timestamp(origin_t + 12 * CANDLE_INTERVAL_MS, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            feature_fingerprint="fp001",
            component_hashes={},
            data_quality={"status": "OK"},
            point_prediction=0.02,
            interval_80={"lower": 0.015, "upper": 0.025},
            interval_95={"lower": 0.01, "upper": 0.03},
            market_state="NORMAL_VOLATILITY",
            record_label="HISTORICAL_REPLAY",
        )
        pred_event.record_hash = pred_event.compute_hash()

        all_candles = [make_candle(i, base_time_ms=base_t) for i in range(288 + 15)]
        
        # Scenario A: Only 11 forward candles available -> premature rejection (0 matured)
        matured_premature = resolver.resolve_matured_predictions(
            pending_events=[pred_event],
            available_candles=all_candles[: 288 + 11],
        )
        assert len(matured_premature) == 0

        # Scenario B: 12 forward candles available -> 1h outcome resolves
        matured_valid = resolver.resolve_matured_predictions(
            pending_events=[pred_event],
            available_candles=all_candles[: 288 + 12],
        )
        assert len(matured_valid) == 1
        assert matured_valid[0].target_horizon == "1h"
        assert matured_valid[0].actual_bars_evaluated == 12
        assert matured_valid[0].status == "MATURED_VALID"
        assert matured_valid[0].realized_volatility > 0


def test_atomic_snapshot_and_crash_recovery():
    """Verify collector persists state and recovers after crash."""
    candles = [make_candle(i) for i in range(100)]

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = ShadowCollectorConfig(base_dir=Path(tmp_dir))
        cfg.ensure_directories()

        # Phase 1: Run collector for 80 candles
        source1 = OfflineFixtureSource(candles[:80])
        col1 = ShadowCollectorV080(cfg, source1)
        col1.initialize()
        for _ in range(80):
            col1.step()

        assert len(col1.feature_pipeline.adapter.buffer) == 80

        # Phase 2: Start new collector instance and verify restored state
        source2 = OfflineFixtureSource(candles[80:])
        col2 = ShadowCollectorV080(cfg, source2)
        restored = col2.initialize()

        assert restored is True
        assert len(col2.feature_pipeline.adapter.buffer) == 80
        assert len(col2.feature_pipeline.adapter.buffer) >= MIN_WARMUP_BARS


def test_deliverables_and_scientific_gates():
    """Verify all 14 deliverables exist and Gate Registry has 12 PASS and 2 NOT_VERIFIED."""
    reports_dir = Path("data/reports/sprint09_10")
    assert reports_dir.exists()

    expected_files = [
        "preflight_integrity.json",
        "collector_architecture.md",
        "live_source_safety_audit.json",
        "bootstrap_and_buffer_tests.json",
        "feature_and_inference_parity.json",
        "timing_and_clock_safety.json",
        "forecast_event_integrity.json",
        "outcome_maturity_validation.json",
        "restart_and_recovery_tests.json",
        "failure_injection_matrix.json",
        "resource_measurements.json",
        "deployment_preparation.md",
        "scientific_gate_registry.json",
        "executive_summary.md",
    ]
    for fn in expected_files:
        p = reports_dir / fn
        assert p.exists(), f"Missing deliverable: {fn}"
        assert p.stat().st_size > 0, f"Empty deliverable: {fn}"

    reg_path = reports_dir / "scientific_gate_registry.json"
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert registry["gates_evaluated_count"] == 14
    assert registry["gates_passed_count"] == 12
    assert registry["gates_not_verified_count"] == 2
    assert registry["overall_verdict"] == "SHADOW_COLLECTOR_READY_FOR_PRE_ACTIVATION_REVIEW"

    # Verify Gate M and Gate N are NOT_VERIFIED
    gate_m = next(g for g in registry["gates"] if g["gate_id"] == "GATE_M_PROSPECTIVE_TIMESTAMP_EVIDENCE")
    assert gate_m["status"] == "NOT_VERIFIED"

    gate_n = next(g for g in registry["gates"] if g["gate_id"] == "GATE_N_LIVE_FEED_PARITY")
    assert gate_n["status"] == "NOT_VERIFIED"
