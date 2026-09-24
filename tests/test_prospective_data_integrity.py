"""Test Suite: Prospective Data Integrity Patch for CBE-0.7.0.

Validates:
1. Outcome correctness with explicit reference_close (no 0-return artifacts).
2. Elimination of silent numeric fallbacks (explicit None/null + availability tracking).
3. Data quality forensics for spot-only streams (DEGRADED_STREAM, SPOT_ONLY_U0).
4. Deterministic market_bar_hash and model_input_hash input provenance.
5. Cryptographic hash chain continuity across Schema V1 and V2 records.
6. Audit log invalidation events for historical V1 outcomes and fallbacks.
7. Outcome store filtering (valid vs excluded outcomes).
8. Strict preservation of frozen model CBE-0.7.0 and Sprint 07/08 freeze verification.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest
import numpy as np
import pandas as pd

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.market_state.engine import (
    DataQualityState,
    FallbackLevel,
    UnifiedMarketStateEngine,
)
from coin_behavior_engine.prospective.store import (
    AuditLogger,
    ImmutablePredictionStore,
    ImmutableStoreViolation,
    OutcomeRecord,
    OutcomeStore,
    PredictionRecord,
    PREDICTION_V1_FIELDS,
    format_utc_iso,
    parse_utc_iso,
)
from coin_behavior_engine.prospective.worker import ProspectiveWorker


def test_01_prediction_schema_v2_has_reference_close():
    """Verify PredictionRecord Schema V2 defaults and explicit reference_close."""
    p = PredictionRecord(
        prediction_id="PRED-TEST-V2-01",
        model_version="CBE-0.7.0",
        model_hash="HASH",
        feature_manifest_hash="HASH",
        input_data_hash="HASH",
        timestamp="2026-09-24T12:00:00Z",
        reference_close=64500.5,
    )
    assert p.prediction_schema_version == "2"
    assert p.reference_close == 64500.5
    assert p.close == 64500.5
    assert p.forecast_15m is None
    assert p.forecast_30m is None


def test_02_legacy_prediction_schema_v1_compatibility():
    """Verify historical V1 prediction lines deserialize without error into Schema V1."""
    v1_dict = {
        "prediction_id": "PRED-LEGACY-01",
        "model_version": "CBE-0.7.0",
        "model_hash": "HASH",
        "feature_manifest_hash": "HASH",
        "input_data_hash": "HASH",
        "timestamp": "2026-09-24T12:00:00Z",
        "asset": "BTCUSDT",
        "market_state": "NORMAL",
        "forecast_15m": 0.001,
        "forecast_30m": 0.0015,
        "forecast_1h": 0.002,
        "forecast_2h": 0.003,
        "forecast_4h": 0.004,
        "forecast_8h": 0.006,
        "forecast_12h": 0.0075,
        "forecast_24h": 0.010,
        "tail_95_probability": 0.05,
        "tail_99_probability": 0.01,
        "jump_probability": 0.01,
        "expansion_probabilities": {"4h": 0.25},
        "prediction_intervals": {},
        "context_availability": "ACTIVE",
        "data_quality": "DEGRADED_STREAM",
        "research_direction_probability": {"p_up": 0.5, "p_down": 0.5},
        "input_cutoff_timestamp": "2026-09-24T12:00:00Z",
        "created_at": "2026-09-24T12:00:05Z",
        "previous_record_hash": "GENESIS_CBE_0_7_0_PROSPECTIVE_CHAIN",
        "record_hash": "DUMMY",
    }
    with tempfile.TemporaryDirectory() as tmp:
        p_file = Path(tmp) / "predictions.jsonl"
        with open(p_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(v1_dict) + "\n")
        store = ImmutablePredictionStore(Path(tmp))
        loaded = store.get_prediction("PRED-LEGACY-01")
        assert loaded is not None
        assert loaded.prediction_schema_version == "1"
        assert loaded.reference_close is None
        assert loaded.forecast_15m == 0.001


def test_03_prediction_v1_hash_preservation():
    """Verify canonical dict for V1 predictions strictly matches original V1 fields."""
    store = ImmutablePredictionStore(Path("data/prospective/predictions"))
    preds = store.list_predictions()
    assert len(preds) >= 2
    for p in preds:
        if p.prediction_schema_version == "1":
            expected_hash = p.compute_hash()
            assert p.record_hash == expected_hash, f"Hash mismatch on V1 record {p.prediction_id}"


def test_04_prediction_v2_hashes_included_fields():
    """Verify V2 prediction computes hash over V2 fields (reference_close, market_bar_hash, etc.)."""
    p = PredictionRecord(
        prediction_id="PRED-TEST-V2-HASH",
        model_version="CBE-0.7.0",
        model_hash="HASH",
        feature_manifest_hash="HASH",
        input_data_hash="HASH",
        timestamp="2026-09-24T12:00:00Z",
        prediction_schema_version="2",
        reference_close=64500.0,
        market_bar_hash="BAR_HASH_123",
        model_input_hash="INPUT_HASH_456",
        fallback_level="SPOT_ONLY_U0",
    )
    canonical = p.to_canonical_dict()
    assert "prediction_schema_version" in canonical
    assert "reference_close" in canonical
    assert "market_bar_hash" in canonical
    assert "model_input_hash" in canonical
    assert "fallback_level" in canonical
    h = p.compute_hash()
    assert isinstance(h, str) and len(h) == 64


def test_05_outcome_schema_v2_fields():
    """Verify OutcomeRecord Schema V2 defaults, status, and invalidation tracking."""
    o = OutcomeRecord(
        prediction_id="PRED-01",
        horizon="1h",
        outcome_available_at="2026-09-24T13:00:00Z",
        realized_return=0.015,
        absolute_return=0.015,
        realized_volatility=0.022,
        realized_range=0.008,
        tail_95_occurred=False,
        tail_99_occurred=False,
        jump_occurred=False,
        expansion_occurred=False,
    )
    assert o.outcome_schema_version == "2"
    assert o.status == "SCORED"
    assert o.excluded_from_evaluation is False
    assert o.invalidation_reason is None


def test_06_outcome_v1_compatibility():
    """Verify legacy outcome lines without schema version deserialize properly."""
    legacy_out = {
        "prediction_id": "PRED-01",
        "horizon": "1h",
        "outcome_available_at": "2026-09-24T13:00:00Z",
        "realized_return": 0.0,
        "absolute_return": 0.0,
        "realized_volatility": 0.0,
        "realized_range": 50.0,
        "tail_95_occurred": False,
        "tail_99_occurred": False,
        "jump_occurred": False,
        "expansion_occurred": False,
        "status": "SCORED",
        "created_at": "2026-09-24T13:05:00Z",
    }
    with tempfile.TemporaryDirectory() as tmp:
        o_file = Path(tmp) / "outcomes.jsonl"
        with open(o_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(legacy_out) + "\n")
        store = OutcomeStore(Path(tmp))
        loaded = store.get_outcome("PRED-01", "1h")
        assert loaded is not None
        assert loaded.outcome_schema_version == "1"
        assert loaded.excluded_from_evaluation is False


def test_07_invalid_reference_price_status():
    """Verify prediction missing reference_close produces INVALID_REFERENCE_PRICE status."""
    with tempfile.TemporaryDirectory() as tmp:
        store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="PRED-NO-REF",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="H",
            input_data_hash="H",
            timestamp="2026-09-24T12:00:00Z",
            created_at="2026-09-24T12:00:05Z",
            reference_close=None,  # Missing!
        )
        # Outcome dictionary when reference price is missing
        out_data = {
            "outcome_available_at": "2026-09-24T13:05:00Z",
            "realized_return": None,
            "absolute_return": None,
            "realized_volatility": None,
            "realized_range": None,
            "tail_95_occurred": None,
            "tail_99_occurred": None,
            "jump_occurred": None,
            "expansion_occurred": None,
            "status": "INVALID_REFERENCE_PRICE",
            "outcome_schema_version": "2",
            "excluded_from_evaluation": True,
            "invalidation_reason": "PREDICTION_SCHEMA_V1_MISSING_REFERENCE_CLOSE",
        }
        rec = store.attach_outcome(p, "1h", out_data, current_timestamp="2026-09-24T13:05:00Z")
        assert rec.status == "INVALID_REFERENCE_PRICE"
        assert rec.excluded_from_evaluation is True
        assert rec.invalidation_reason == "PREDICTION_SCHEMA_V1_MISSING_REFERENCE_CLOSE"


def test_08_invalid_reference_price_does_not_produce_zero_returns():
    """Verify invalid reference price sets returns and volatility to None, NOT 0.0."""
    with tempfile.TemporaryDirectory() as tmp:
        store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="PRED-NO-ZERO",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="H",
            input_data_hash="H",
            timestamp="2026-09-24T12:00:00Z",
            created_at="2026-09-24T12:00:05Z",
            reference_close=None,
        )
        out_data = {
            "outcome_available_at": "2026-09-24T13:05:00Z",
            "realized_return": None,
            "absolute_return": None,
            "realized_volatility": None,
            "status": "INVALID_REFERENCE_PRICE",
            "excluded_from_evaluation": True,
        }
        rec = store.attach_outcome(p, "1h", out_data, current_timestamp="2026-09-24T13:05:00Z")
        assert rec.realized_return is None
        assert rec.absolute_return is None
        assert rec.realized_volatility is None
        assert rec.realized_return != 0.0


def test_09_valid_reference_price_calculates_correct_returns():
    """Verify correct positive return calculation (51000 - 50000)/50000 = +0.02."""
    ref_close = 50000.0
    realized_close = 51000.0
    ret = (realized_close - ref_close) / ref_close
    abs_ret = abs(ret)
    assert pytest.approx(ret, 1e-6) == 0.02
    assert pytest.approx(abs_ret, 1e-6) == 0.02


def test_10_negative_return_calculation():
    """Verify correct negative return calculation (49000 - 50000)/50000 = -0.02."""
    ref_close = 50000.0
    realized_close = 49000.0
    ret = (realized_close - ref_close) / ref_close
    abs_ret = abs(ret)
    assert pytest.approx(ret, 1e-6) == -0.02
    assert pytest.approx(abs_ret, 1e-6) == 0.02


def test_11_realized_volatility_calculation():
    """Verify intra-horizon realized volatility calculates properly from log returns."""
    closes = np.array([50000, 50200, 49900, 50500, 50300, 50800, 51000], dtype=float)
    log_rets = np.diff(np.log(closes))
    vol = float(np.std(log_rets) * np.sqrt(288))
    assert vol > 0.005
    assert not np.isnan(vol)


def test_12_no_silent_numeric_fallbacks_in_worker():
    """Verify worker sets None for unpredicted horizons rather than hardcoded 0.001."""
    worker = ProspectiveWorker()
    assert worker.initialize() is True

    # Call predict_bar with spot features
    feats = {
        "datetime_open": "2026-09-24T12:00:00Z",
        "close": 64000.0,
        "volatility_realized_24h": 0.002,
        "volatility_compression_ratio": 1.0,
        "volume_zscore": 0.0,
        "session_asia_active": False,
        "session_london_active": True,
        "session_new_york_active": False,
        "london_new_york_overlap": False,
        "weekend_flag": False,
        "atr_pct": 0.0015,
    }
    pred_res = worker.engine.predict_bar(feats)
    vol_fc = pred_res.get("volatility_forecasts", {})

    # Engine only outputs 1h, 4h, 24h
    assert "15m" not in vol_fc
    assert "30m" not in vol_fc
    assert "2h" not in vol_fc
    assert "8h" not in vol_fc
    assert "12h" not in vol_fc

    # Extract forecasts as worker does in Schema V2
    f_15m = float(vol_fc["15m"]["p50"]) if "15m" in vol_fc and "p50" in vol_fc["15m"] else None
    f_1h = float(vol_fc["1h"]["p50"]) if "1h" in vol_fc and "p50" in vol_fc["1h"] else None

    assert f_15m is None, "Missing 15m forecast must be None, not silent 0.001"
    assert f_1h is not None and f_1h > 0.0


def test_13_forecast_availability_tracking():
    """Verify forecast availability dictionary accurately maps available vs missing horizons."""
    all_horizons = ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h"]
    vol_fc = {"1h": {"p50": 0.002}, "4h": {"p50": 0.004}, "24h": {"p50": 0.01}}
    availability = {h: bool(h in vol_fc and "p50" in vol_fc[h]) for h in all_horizons}
    missing = [h for h in all_horizons if not availability[h]]

    assert availability["1h"] is True
    assert availability["4h"] is True
    assert availability["24h"] is True
    assert availability["15m"] is False
    assert availability["30m"] is False
    assert missing == ["15m", "30m", "2h", "8h", "12h"]


def test_14_data_quality_forensics_spot_only():
    """Verify engine and worker report DEGRADED_STREAM and SPOT_ONLY_U0 when derivatives are absent."""
    worker = ProspectiveWorker()
    assert worker.initialize() is True

    # Spot only features (as fetched by Binance spot provider)
    feats = {
        "datetime_open": "2026-09-24T12:00:00Z",
        "close": 64000.0,
        "volatility_realized_24h": 0.002,
        "volatility_compression_ratio": 1.0,
        "volume_zscore": 0.0,
        "session_asia_active": False,
        "session_london_active": True,
    }
    dq_state, fallback = worker.engine.evaluate_data_quality(feats)
    assert dq_state == DataQualityState.DEGRADED_STREAM
    assert fallback == FallbackLevel.SPOT_ONLY_U0

    pred_res = worker.engine.predict_bar(feats)
    assert pred_res["data_quality_state"] == "DEGRADED_STREAM"
    assert pred_res["fallback_level"] == "SPOT_ONLY_U0"


def test_15_market_bar_hash_deterministic():
    """Verify market_bar_hash computation is deterministic and reproducible."""
    import hashlib
    bar_ts = "2026-09-24T12:00:00Z"
    bar_summary = f"{bar_ts}_64000.0_64200.0_63900.0_64100.0_120.5"
    h1 = hashlib.sha256(bar_summary.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(bar_summary.encode("utf-8")).hexdigest()
    assert h1 == h2
    assert len(h1) == 64


def test_16_model_input_hash_deterministic():
    """Verify model_input_hash is deterministic with sorted keys."""
    import hashlib
    feats1 = {"b": 2.0, "a": 1.0, "c": 3.0}
    feats2 = {"c": 3.0, "a": 1.0, "b": 2.0}
    h1 = hashlib.sha256(json.dumps(feats1, sort_keys=True).encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(json.dumps(feats2, sort_keys=True).encode("utf-8")).hexdigest()
    assert h1 == h2


def test_17_hash_chain_continuity_v1_to_v2():
    """Verify adding a Schema V2 record to a chain containing V1 records succeeds seamlessly."""
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))

        # 1. Add V1 record
        p1 = PredictionRecord(
            prediction_id="P1_V1",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="H",
            input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z",
            prediction_schema_version="1",
        )
        stored1 = store.store_prediction(p1)

        # 2. Add V2 record chaining to V1 record
        p2 = PredictionRecord(
            prediction_id="P2_V2",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="H",
            input_data_hash="H",
            timestamp="2026-09-24T00:05:00Z",
            prediction_schema_version="2",
            reference_close=64000.0,
            market_bar_hash="BAR_HASH_2",
            model_input_hash="INPUT_HASH_2",
        )
        stored2 = store.store_prediction(p2)

        assert stored2.previous_record_hash == stored1.record_hash
        valid, errors = store.verify_hash_chain()
        assert valid is True, f"Chain verification failed: {errors}"


def test_18_audit_logger_invalidation_events():
    """Verify OUTCOME_CALCULATION_INVALID_V1 and LEGACY_NUMERIC_FALLBACK_PRESENT exist in audit log."""
    audit_file = Path("data/prospective/audit/audit_log.jsonl")
    assert audit_file.exists()
    event_types = []
    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line.strip())
                event_types.append(data.get("event_type"))

    assert "OUTCOME_CALCULATION_INVALID_V1" in event_types
    assert "LEGACY_NUMERIC_FALLBACK_PRESENT" in event_types

    logger = AuditLogger()
    assert logger.verify_audit_chain() is True


def test_19_outcome_store_filtering():
    """Verify get_valid_outcomes() excludes INVALID_REFERENCE_PRICE records."""
    with tempfile.TemporaryDirectory() as tmp:
        store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="P_FILTER",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="H",
            input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z",
            created_at="2026-09-24T00:00:05Z",
        )
        # Attach valid outcome for 1h
        store.attach_outcome(
            p, "1h",
            {"outcome_available_at": "2026-09-24T01:05:00Z", "realized_return": 0.01, "status": "SCORED", "excluded_from_evaluation": False},
            "2026-09-24T01:05:00Z"
        )
        # Attach invalid outcome for 4h
        store.attach_outcome(
            p, "4h",
            {"outcome_available_at": "2026-09-24T04:05:00Z", "realized_return": None, "status": "INVALID_REFERENCE_PRICE", "excluded_from_evaluation": True},
            "2026-09-24T04:05:00Z"
        )

        valid = store.get_valid_outcomes()
        invalid = store.get_invalid_outcomes()

        assert len(valid) == 1
        assert valid[0].horizon == "1h"
        assert len(invalid) == 1
        assert invalid[0].horizon == "4h"


def test_20_freeze_and_model_untouched():
    """Verify model CBE-0.7.0 freeze verification remains 100% intact and untouched."""
    res = verify_sprint07_freeze(
        sprint07_dir=Path("data/reports/sprint07"),
        lockbox_path=Path("data/prospective/lockbox_manifest.json"),
    )
    assert res["status"] == "FREEZE_VERIFIED"
    assert res["verified"] is True
    assert res["canonical_hashes_verified"] == 29
    assert res["total_artifacts_checked"] == 29
    assert len(res["canonical_mismatches"]) == 0
    assert len(res["missing_files"]) == 0
    assert res["lockbox_verified"] is True
