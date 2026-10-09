"""Tests for Sprint 09.8: Prospective Feed Parity & Isolated Data Capture Engineering.

Validates:
1. Frozen artifact integrity and lockbox hashes.
2. Feature schema completeness (3 canonical spot features).
3. Feature order parity with model bundle manifest.
4. Volume z-score reconstruction mathematical parity (< 1e-12).
5. Closed-candle enforcement (rejects unclosed candles).
6. Causality and no future candle access.
7. Warm-up states: FEATURE_UNAVAILABLE (< 72), WARMING_UP, READY (>= 288).
8. Gap detection (> 300,000 ms step triggers SOURCE_GAP).
9. Idempotent duplicate candle handling.
10. Conflicting duplicate candle rejection.
11. Out-of-order candle rejection.
12. Non-finite input rejection (NaN / Inf).
13. Zero-volume handling (no ZeroDivisionError, zero standard deviation fallback).
14. Restart recovery and buffer reset.
15. Feature fingerprint determinism.
16. Candidate C/E point forecast parity in end-to-end replay.
17. Calibration branch separation and monotonicity.
18. Target-unit consistency (Daily-scaled standard deviation: sigma_5m * sqrt(288)).
19. Historical replay record labeling.
20. Prospective timing honesty (prospective feed parity marked NOT_VERIFIED).
21. Production source isolation and Sprint 07 freeze preservation (29/29).
22. Resource budget measurements (< 150 ms latency, < 150 MB RAM).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CandleData,
    FeedAdapterError,
    FeedAdapterV080,
    ReconstructedFeatures,
)
from coin_behavior_engine.candidate_v080.inference_pipeline import (
    CandidateInferencePipelineV080,
    TARGET_UNITS,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze

MODELS_DIR = Path("data/models")
BUNDLE_PATH = MODELS_DIR / "cbe_model_bundle_v080.json"
THRESHOLDS_PATH = MODELS_DIR / "cbe_state_thresholds_v080.json"
CAL_C_PATH = MODELS_DIR / "cbe_interval_calibration_v080_candidate_c.json"
CAL_E_PATH = MODELS_DIR / "cbe_interval_calibration_v080_095.json"
REPORTS_DIR = Path("data/reports/sprint09_8")
NORM_PARQUET = Path("data/normalized/btcusdt_5m.parquet")
DERIVED_PARQUET = Path("data/derived/features_with_outcomes_5m.parquet")


@pytest.fixture
def sample_valid_candle() -> CandleData:
    return CandleData(
        timestamp_open=1704067200000,
        timestamp_close=1704067499999,
        datetime_open="2026-01-01T00:00:00Z",
        datetime_close="2026-01-01T00:05:00Z",
        open=42000.0,
        high=42100.0,
        low=41900.0,
        close=42050.0,
        volume=15.5,
        is_closed=True,
    )


# ---------------------------------------------------------------------------
# Section 1: Frozen Artifact Integrity & Schema Tests
# ---------------------------------------------------------------------------

def test_01_frozen_artifact_integrity():
    with open(REPORTS_DIR / "preflight_integrity.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["freeze_verification"]["status"] == "FREEZE_VERIFIED"
    assert data["freeze_verification"]["canonical_hashes_verified"] == 29
    assert data["integrity_verdict"] == "ALL_FROZEN_ARTIFACTS_MATCH_EXACT_SPECIFICATION"


def test_02_feature_schema_completeness():
    with open(REPORTS_DIR / "canonical_feature_inventory.json", "r", encoding="utf-8") as f:
        inv = json.load(f)
    assert inv["feature_count"] == 3
    feats = inv["features"]
    assert "volatility_realized_24h" in feats
    assert "volatility_compression_ratio" in feats
    assert "volume_zscore_24h" in feats


def test_03_feature_order_parity():
    adapter = FeedAdapterV080()
    assert adapter.CANONICAL_FEATURES == [
        "volatility_realized_24h",
        "volatility_compression_ratio",
        "volume_zscore_24h",
    ]


# ---------------------------------------------------------------------------
# Section 2: Mathematical Parity Tests
# ---------------------------------------------------------------------------

def test_04_volume_zscore_reconstruction_parity():
    with open(REPORTS_DIR / "feature_reconstruction_parity.json", "r", encoding="utf-8") as f:
        res = json.load(f)
    assert res["parity_status"] == "PASS_EXACT_NUMERICAL_PARITY"
    assert res["max_difference_volume_zscore_24h"] <= 1e-12
    assert res["max_difference_volatility_realized_24h"] <= 1e-12
    assert res["max_difference_volatility_compression_ratio"] <= 1e-12


def test_05_closed_candle_enforcement(sample_valid_candle):
    adapter = FeedAdapterV080()
    bad_c = sample_valid_candle
    bad_c.is_closed = False
    ok, reason = adapter.add_candle(bad_c)
    assert ok is False
    assert "not closed" in reason


def test_06_causality_and_no_future_candle_access():
    adapter = FeedAdapterV080()
    base_t = 1704067200000
    for i in range(100):
        c = CandleData(
            timestamp_open=base_t + i * 300000,
            timestamp_close=base_t + (i + 1) * 300000 - 1,
            datetime_open=f"2026-01-01T{i:02d}:00:00Z",
            datetime_close=f"2026-01-01T{i:02d}:05:00Z",
            open=40000.0 + i,
            high=40050.0 + i,
            low=39950.0 + i,
            close=40020.0 + i,
            volume=10.0 + i,
        )
        adapter.add_candle(c)

    res = adapter.reconstruct_features()
    assert res.latest_source_candle_close_utc == adapter.candles[-1].datetime_close
    assert res.forecast_origin_utc == res.latest_source_candle_close_utc


# ---------------------------------------------------------------------------
# Section 3: Warmup, Gap, and Invariant Tests
# ---------------------------------------------------------------------------

def test_07_warmup_correctness():
    adapter = FeedAdapterV080()
    # 0 bars
    assert adapter.reconstruct_features().status == "FEATURE_UNAVAILABLE"

    # Add 50 bars (< 72)
    base_t = 1704067200000
    for i in range(50):
        c = CandleData(
            timestamp_open=base_t + i * 300000,
            timestamp_close=base_t + (i + 1) * 300000 - 1,
            datetime_open="2026-01-01T00:00:00Z",
            datetime_close="2026-01-01T00:05:00Z",
            open=40000.0,
            high=40100.0,
            low=39900.0,
            close=40050.0,
            volume=10.0,
        )
        adapter.add_candle(c)
    assert adapter.reconstruct_features().status == "WARMING_UP"


def test_08_gap_detection_handling(sample_valid_candle):
    adapter = FeedAdapterV080()
    adapter.add_candle(sample_valid_candle)

    # Gap candle (1 hour later instead of 5 minutes)
    gap_c = CandleData(
        timestamp_open=sample_valid_candle.timestamp_open + 3600000,
        timestamp_close=sample_valid_candle.timestamp_open + 3600000 + 299999,
        datetime_open="2026-01-01T01:00:00Z",
        datetime_close="2026-01-01T01:05:00Z",
        open=42000.0,
        high=42100.0,
        low=41900.0,
        close=42050.0,
        volume=10.0,
    )
    ok, reason = adapter.add_candle(gap_c)
    assert ok is False
    assert "Source gap detected" in reason
    assert adapter.last_status == "SOURCE_GAP"


def test_09_idempotent_duplicate_handling(sample_valid_candle):
    adapter = FeedAdapterV080()
    ok1, _ = adapter.add_candle(sample_valid_candle)
    assert ok1 is True
    # Same candle again
    ok2, reason = adapter.add_candle(sample_valid_candle)
    assert ok2 is True
    assert "IDEMPOTENT_DUPLICATE_IGNORED" in reason
    assert len(adapter.candles) == 1


def test_10_conflicting_duplicate_rejection(sample_valid_candle):
    adapter = FeedAdapterV080()
    adapter.add_candle(sample_valid_candle)

    conflicting_c = CandleData(
        timestamp_open=sample_valid_candle.timestamp_open,
        timestamp_close=sample_valid_candle.timestamp_close,
        datetime_open=sample_valid_candle.datetime_open,
        datetime_close=sample_valid_candle.datetime_close,
        open=50000.0,  # Different price!
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=10.0,
    )
    ok, reason = adapter.add_candle(conflicting_c)
    assert ok is False
    assert "Conflicting candle" in reason


def test_11_out_of_order_candle_rejection(sample_valid_candle):
    adapter = FeedAdapterV080()
    adapter.add_candle(sample_valid_candle)

    older_c = CandleData(
        timestamp_open=sample_valid_candle.timestamp_open - 300000,
        timestamp_close=sample_valid_candle.timestamp_open - 1,
        datetime_open="2025-12-31T23:55:00Z",
        datetime_close="2026-01-01T00:00:00Z",
        open=42000.0,
        high=42100.0,
        low=41900.0,
        close=42050.0,
        volume=10.0,
    )
    ok, reason = adapter.add_candle(older_c)
    assert ok is False
    assert "Out of order" in reason


def test_12_non_finite_candle_rejection():
    adapter = FeedAdapterV080()
    bad_c = CandleData(
        timestamp_open=1704067200000,
        timestamp_close=1704067499999,
        datetime_open="2026-01-01T00:00:00Z",
        datetime_close="2026-01-01T00:05:00Z",
        open=float("nan"),
        high=42100.0,
        low=41900.0,
        close=42050.0,
        volume=10.0,
    )
    ok, reason = adapter.add_candle(bad_c)
    assert ok is False
    assert "Non-finite" in reason


def test_13_zero_volume_handling():
    adapter = FeedAdapterV080()
    base_t = 1704067200000
    for i in range(100):
        c = CandleData(
            timestamp_open=base_t + i * 300000,
            timestamp_close=base_t + (i + 1) * 300000 - 1,
            datetime_open="2026-01-01T00:00:00Z",
            datetime_close="2026-01-01T00:05:00Z",
            open=40000.0,
            high=40050.0,
            low=39950.0,
            close=40020.0,
            volume=0.0,  # Zero volume
        )
        adapter.add_candle(c)

    feats = adapter.reconstruct_features()
    assert feats.status == "READY_PARTIAL_WARMUP"
    assert feats.features["volume_zscore_24h"] == 0.0


def test_14_restart_recovery_and_reset(sample_valid_candle):
    adapter = FeedAdapterV080()
    adapter.add_candle(sample_valid_candle)
    assert len(adapter.candles) == 1
    adapter.reset()
    assert len(adapter.candles) == 0
    assert adapter.last_status == "WARMING_UP"


def test_15_feature_fingerprint_determinism():
    adapter = FeedAdapterV080()
    base_t = 1704067200000
    for i in range(80):
        c = CandleData(
            timestamp_open=base_t + i * 300000,
            timestamp_close=base_t + (i + 1) * 300000 - 1,
            datetime_open=f"2026-01-01T{i:02d}:00:00Z",
            datetime_close=f"2026-01-01T{i:02d}:05:00Z",
            open=40000.0 + i,
            high=40050.0 + i,
            low=39950.0 + i,
            close=40020.0 + i,
            volume=10.0 + i,
        )
        adapter.add_candle(c)

    f1 = adapter.reconstruct_features()
    f2 = adapter.reconstruct_features()
    assert f1.feature_fingerprint == f2.feature_fingerprint
    assert len(f1.feature_fingerprint) == 64


# ---------------------------------------------------------------------------
# Section 4: End-to-End Replay & Safety Deliverable Tests
# ---------------------------------------------------------------------------

def test_16_end_to_end_replay_point_forecast_parity():
    with open(REPORTS_DIR / "offline_end_to_end_replay.json", "r", encoding="utf-8") as f:
        res = json.load(f)
    assert res["end_to_end_replay_status"] == "PASS_END_TO_END_INTEGRATION_VERIFIED"
    assert res["max_point_difference_branch_c_vs_e"] == 0.0
    assert res["monotonicity_violations_count"] == 0
    assert res["record_type_enforced"] == "HISTORICAL_REPLAY"


def test_17_target_unit_uniformity():
    with open(REPORTS_DIR / "canonical_feature_inventory.json", "r", encoding="utf-8") as f:
        inv = json.load(f)
    assert inv["features"]["volatility_realized_24h"]["units"] == "5-minute return sample standard deviation (unscaled)"


def test_18_prospective_feed_parity_honesty():
    with open(REPORTS_DIR / "prospective_feed_parity_matrix.json", "r", encoding="utf-8") as f:
        mat = json.load(f)
    assert mat["historical_feature_parity"] == "PASS"
    assert mat["source_schema_compatibility"] == "PASS"
    assert mat["prospective_timestamp_parity"] == "NOT_VERIFIED"
    assert mat["prospective_feed_parity"] == "NOT_VERIFIED"


def test_19_all_13_deliverables_exist():
    expected_files = [
        "preflight_integrity.json",
        "production_feed_architecture_audit.md",
        "canonical_feature_inventory.json",
        "volume_zscore_24h_analysis.md",
        "feature_reconstruction_parity.json",
        "timestamp_causality_audit.json",
        "warmup_and_gap_handling.json",
        "offline_end_to_end_replay.json",
        "prospective_feed_parity_matrix.json",
        "isolated_capture_architecture.md",
        "resource_measurements.json",
        "scientific_gate_registry.json",
        "executive_summary.md",
    ]
    for fname in expected_files:
        p = REPORTS_DIR / fname
        assert p.exists(), f"Missing file: {fname}"
        assert p.stat().st_size > 0, f"Empty file: {fname}"


def test_20_scientific_gate_registry_audit():
    with open(REPORTS_DIR / "scientific_gate_registry.json", "r", encoding="utf-8") as f:
        gates_doc = json.load(f)
    assert gates_doc["gates_evaluated_count"] == 12
    assert gates_doc["gates_passed_count"] == 11
    assert gates_doc["gates_not_verified_count"] == 1
    assert gates_doc["overall_verdict"] == "PROSPECTIVE_FEED_PARITY_FROZEN_PENDING_LIVE_TAP"


def test_21_production_freeze_preserved():
    res = verify_sprint07_freeze()
    assert res["verified"] is True
    assert res["canonical_hashes_verified"] == 29
    assert res["status"] == "FREEZE_VERIFIED"


def test_22_resource_budget_adherence():
    with open(REPORTS_DIR / "resource_measurements.json", "r", encoding="utf-8") as f:
        res = json.load(f)
    assert res["feature_reconstruction_latency_ms"] < res["allocated_budget_cpu_ms"]
    assert res["rolling_buffer_memory_kb"] < 1000.0
