"""Sprint 09.15: Prospective Inference Authorization Hardening Tests.

Verifies:
1. Approval 4 absent, false, disabled, and malformed value rejection ('1', 'True', 'yes', 'TRUE', 'enabled').
2. Direct inference invocation bypass attempts (DualBranchInferenceRunnerV080 and CandidateInferenceEngineV080).
3. Runtime revocation during execution loop.
4. Causal data eligibility: 287 bars rejected (InsufficientWarmupBarsError) vs 288 bars accepted.
5. Timestamp gaps and discontinuous candles rejected (DiscontinuousCandlesError).
6. Duplicate candle timestamps rejected (DuplicateTimestampError).
7. Open / incomplete candles rejected (IncompleteCandleError).
8. Incorrect market identity rejected (InvalidMarketIdentityError: symbol, interval, market_type).
9. Synthetic, mock, or historical replay provenance rejected for prospective observation (SyntheticProvenanceError).
10. Unverified evidence references rejected when evidence store provided (UnverifiedEvidenceError).
11. Trading disabled invariant enforced across prospective and offline modes.
12. Offline historical research and regression test compatibility preserved.
13. Approval 3 active alone does NOT authorize prospective scoring.
14. ShadowCollectorV080 fails closed on unapproved prospective execution.
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

from coin_behavior_engine.candidate_v080.feed_adapter import CandleData
from coin_behavior_engine.candidate_v080.inference import CandidateInferenceEngineV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.collector import ShadowCollectorV080
from coin_behavior_engine.shadow_v080.inference_runner import DualBranchInferenceRunnerV080
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    CausalDataEligibilityGuard,
    DiscontinuousCandlesError,
    DuplicateTimestampError,
    IncompleteCandleError,
    InsufficientWarmupBarsError,
    InvalidMarketIdentityError,
    ProspectiveAuthorizationError,
    ProspectiveAuthorizationGuard,
    SyntheticProvenanceError,
    TemporalAlignmentError,
    UnverifiedEvidenceError,
)


def make_candle(
    index: int,
    start_ts: int = 1770000000000,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    market_type: str = "SPOT",
    is_closed: bool = True,
    provenance: str = "LIVE_BINANCE_SPOT",
    is_synthetic: bool = False,
    is_mock: bool = False,
) -> ValidatedCandle:
    """Generate a valid test candle with precise timestamp alignment."""
    ts_open = start_ts + (index * CANDLE_INTERVAL_MS)
    ts_close = ts_open + CANDLE_INTERVAL_MS - 1
    return ValidatedCandle(
        symbol=symbol,
        interval=interval,
        market_type=market_type,
        timestamp_open=ts_open,
        timestamp_close=ts_close,
        datetime_open_utc=f"2026-02-01T{index:04d}Z",
        datetime_close_utc=f"2026-02-01T{index:04d}Z",
        open="50000.00",
        high="50100.00",
        low="49900.00",
        close="50050.00",
        volume="10.5",
        quote_volume="525525.00",
        trades_count=100,
        taker_buy_base_volume="5.2",
        is_closed=is_closed,
        provenance=provenance,
        receipt_timestamp_utc="2026-02-01T00:05:00Z",
    )


def sample_features() -> Dict[str, float]:
    return {
        "volatility_realized_24h": 0.045,
        "volatility_compression_ratio": 0.95,
        "volume_zscore_24h": 0.12,
    }


# ==============================================================================
# 1. Authorization Guard & Malformed Value Rejection
# ==============================================================================

def test_01_approval_4_absent_fails(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError, match="CBE_APPROVAL_4_AUTHORIZED must be strictly 'true'"):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=True)


@pytest.mark.parametrize("bad_val", ["1", "True", "yes", "TRUE", "enabled", "false", ""])
def test_02_approval_4_malformed_values_rejected(bad_val, monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", bad_val)
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError, match="CBE_APPROVAL_4_AUTHORIZED must be strictly 'true'"):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=True)


@pytest.mark.parametrize("bad_val", ["1", "True", "yes", "TRUE", "false", ""])
def test_03_prospective_observation_enabled_malformed_rejected(bad_val, monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", bad_val)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError, match="CBE_PROSPECTIVE_OBSERVATION_ENABLED must be strictly 'true'"):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=True)


def test_04_approval_3_alone_does_not_confer_approval_4(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError, match="Approval 3 .* does NOT confer Approval 4"):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=True)


def test_05_trading_enabled_strictly_prohibited(monkeypatch):
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")

    with pytest.raises(ProspectiveAuthorizationError, match="CBE_TRADING_DISABLED must be strictly 'true'"):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=True)


def test_06_offline_research_cannot_emit_prospective_label(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError):
        ProspectiveAuthorizationGuard.verify_authorization(record_label="PROSPECTIVE_LIVE", is_prospective=False)


def test_07_offline_research_passes_cleanly(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    # Offline research with historical replay must pass without raising
    ProspectiveAuthorizationGuard.verify_authorization(record_label="HISTORICAL_REPLAY", is_prospective=False)
    ProspectiveAuthorizationGuard.verify_authorization(record_label="WARMUP_REPLAY", is_prospective=False)


# ==============================================================================
# 2. Execution Boundary Bypass & Revocation
# ==============================================================================

def test_08_direct_inference_runner_predict_bypass_fails(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    cfg = ShadowCollectorConfig()
    runner = DualBranchInferenceRunnerV080(cfg)

    # Direct invocation attempting prospective scoring without approval
    with pytest.raises(ProspectiveAuthorizationError):
        runner.predict(
            features=sample_features(),
            forecast_origin_utc="2026-02-01T00:00:00Z",
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
        )


def test_09_direct_candidate_engine_predict_bypass_fails(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    cfg = ShadowCollectorConfig()
    bundle_path = cfg.models_dir / "cbe_model_bundle_v080.json"
    engine = CandidateInferenceEngineV080(bundle_path)

    with pytest.raises(ProspectiveAuthorizationError):
        engine.predict(
            features=sample_features(),
            horizon="1h",
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
        )


def test_10_runtime_revocation_stops_execution_immediately(monkeypatch):
    # Start authorized
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    cfg = ShadowCollectorConfig()
    runner = DualBranchInferenceRunnerV080(cfg)
    candles_288 = [make_candle(i) for i in range(288)]

    # 1. First execution with authorization passes causal + authorization check
    res = runner.predict(
        features=sample_features(),
        forecast_origin_utc="2026-02-01T00:00:00Z",
        record_label="PROSPECTIVE_LIVE",
        is_prospective=True,
        context_candles=candles_288,
        current_time_ms=candles_288[-1].timestamp_close,
    )
    assert res is not None

    # 2. Operator revokes APPROVAL_4 at runtime
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")

    # 3. Next execution immediately fails closed
    with pytest.raises(ProspectiveAuthorizationError):
        runner.predict(
            features=sample_features(),
            forecast_origin_utc="2026-02-01T00:05:00Z",
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
            context_candles=candles_288,
            current_time_ms=candles_288[-1].timestamp_close,
        )


# ==============================================================================
# 3. Causal Data Eligibility & Warmup Verification
# ==============================================================================

def test_11_insufficient_warmup_287_bars_rejected():
    candles_287 = [make_candle(i) for i in range(287)]
    with pytest.raises(InsufficientWarmupBarsError, match="expected at least 288 contiguous closed candles, got 287"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles_287)


def test_12_exactly_288_bars_accepted():
    candles_288 = [make_candle(i) for i in range(288)]
    # Should complete without error
    CausalDataEligibilityGuard.verify_causal_data_eligibility(
        candles_288,
        current_time_ms=candles_288[-1].timestamp_close,
    )


def test_13_discontinuous_candles_gap_rejected():
    candles = [make_candle(i) for i in range(288)]
    # Introduce a 5-minute missing bar gap at index 100 (10 minutes instead of 5 minutes jump)
    for i in range(100, 288):
        candles[i] = make_candle(i + 1)  # skipped one candle interval

    with pytest.raises(DiscontinuousCandlesError, match="Discontinuous candles at index 100"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles)


def test_14_duplicate_timestamp_rejected():
    candles = [make_candle(i) for i in range(288)]
    # Introduce a duplicate timestamp
    candles[150] = candles[149]

    with pytest.raises(DuplicateTimestampError, match="Duplicate candle timestamp"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles)


def test_15_open_incomplete_candle_rejected():
    candles = [make_candle(i) for i in range(288)]
    # Mark candle at index 200 as unclosed
    candles[200] = make_candle(200, is_closed=False)

    with pytest.raises(IncompleteCandleError, match="Candle is incomplete / not closed"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles)


# ==============================================================================
# 4. Market Identity & Provenance Verification
# ==============================================================================

def test_16_invalid_symbol_rejected():
    c = make_candle(0, symbol="ETHUSDT")
    with pytest.raises(InvalidMarketIdentityError, match="Invalid symbol 'ETHUSDT'"):
        CausalDataEligibilityGuard.verify_candle_identity(c)


def test_17_invalid_interval_rejected():
    c = make_candle(0, interval="1h")
    with pytest.raises(InvalidMarketIdentityError, match="Invalid interval '1h'"):
        CausalDataEligibilityGuard.verify_candle_identity(c)


def test_18_invalid_market_type_rejected():
    c = make_candle(0, market_type="FUTURES_USDM")
    with pytest.raises(InvalidMarketIdentityError, match="Invalid market type 'FUTURES_USDM'"):
        CausalDataEligibilityGuard.verify_candle_identity(c)


def test_19_synthetic_provenance_rejected_for_prospective():
    candles = [make_candle(i) for i in range(288)]
    # Mark the latest candle as OFFLINE_FIXTURE
    candles[-1] = make_candle(287, provenance="OFFLINE_FIXTURE")

    with pytest.raises(SyntheticProvenanceError, match="Invalid provenance 'OFFLINE_FIXTURE' for prospective scoring"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles, is_prospective=True)


def test_20_future_dated_candle_rejected():
    candles = [make_candle(i) for i in range(288)]
    # Current clock is 1 hour BEFORE the candle close
    clock_time = candles[-1].timestamp_close - 3600_000

    with pytest.raises(TemporalAlignmentError, match="Future-dated candle rejected"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles, current_time_ms=clock_time)


def test_21_stale_backdated_candle_rejected():
    candles = [make_candle(i) for i in range(288)]
    # Current clock is 2 hours AFTER candle close (staleness threshold is 15 minutes)
    clock_time = candles[-1].timestamp_close + 7200_000

    with pytest.raises(TemporalAlignmentError, match="Excessively stale candle rejected"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(candles, current_time_ms=clock_time)


# ==============================================================================
# 5. Authoritative Raw Evidence Store Verification
# ==============================================================================

def test_22_unverified_evidence_reference_rejected():
    candles = [make_candle(i) for i in range(288)]
    mock_store = MagicMock()
    # Simulate candle timestamp not found in raw evidence ledger
    mock_store.get_candle_by_timestamp.return_value = None

    with pytest.raises(UnverifiedEvidenceError, match="has not been committed to the durable raw evidence ledger"):
        CausalDataEligibilityGuard.verify_causal_data_eligibility(
            candles,
            evidence_store=mock_store,
            current_time_ms=candles[-1].timestamp_close,
        )


def test_23_verified_evidence_reference_accepted():
    candles = [make_candle(i) for i in range(288)]
    mock_store = MagicMock()
    # Simulate candle timestamp found in raw evidence ledger
    mock_store.get_candle_by_timestamp.return_value = candles[-1]

    # Should succeed without error
    CausalDataEligibilityGuard.verify_causal_data_eligibility(
        candles,
        evidence_store=mock_store,
        current_time_ms=candles[-1].timestamp_close,
    )
    mock_store.get_candle_by_timestamp.assert_called_once_with(candles[-1].timestamp_open)


# ==============================================================================
# 6. ShadowCollectorV080 Integration & Initialization Guard
# ==============================================================================

def test_24_collector_unapproved_prospective_init_fails(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    cfg = ShadowCollectorConfig()
    mock_source = MagicMock()

    # Attempting to initialize collector with PROSPECTIVE_LIVE without Gate 4 approval
    with pytest.raises(ProspectiveAuthorizationError):
        ShadowCollectorV080(
            config=cfg,
            source=mock_source,
            record_label="PROSPECTIVE_LIVE",
        )


def test_25_collector_historical_replay_init_succeeds(monkeypatch):
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    cfg = ShadowCollectorConfig()
    mock_source = MagicMock()

    # Offline historical replay initializes cleanly without requiring Approval 4
    collector = ShadowCollectorV080(
        config=cfg,
        source=mock_source,
        record_label="HISTORICAL_REPLAY",
    )
    assert collector.record_label == "HISTORICAL_REPLAY"
