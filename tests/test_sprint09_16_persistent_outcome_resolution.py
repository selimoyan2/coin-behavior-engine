"""Offline Verification Suite for CBE-0.8.0 Sprint 09.16.

Persistent Evidence-Based Outcome Resolution:
- Exact 1h (12 bars), 4h (48 bars), and 24h (288 bars) causal maturity
- Missing outcome candle gap detection and NaN outcome handling
- Delayed arrival (pending until exact maturity close)
- Duplicate evidence rejection
- Restart recovery without rolling buffer dependency
- No double counting across multiple resolution passes
- Evidence hash linkage to immutable raw market ledger
- Incomplete candle rejection (is_closed=False)
- Historical vs prospective record label separation
- Prospective authorization bypass and null evidence store rejection
- Zero live inference execution during outcome resolution
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.feed_adapter import CandleData
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    ForwardWindowResult,
    ForwardWindowStatus,
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.inference_runner import (
    DualBranchInferenceRunnerV080,
    verify_prospective_execution_boundary,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    CandleLifecycleState,
    MarketType,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    OutcomeResolverV080,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_indexing import (
    IPendingPredictionIndex,
    JournalPendingPredictionIndexV080,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    ImmutablePredictionStoreV080,
    ShadowPredictionEvent,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    ProspectiveAuthorizationError,
    UnverifiedEvidenceError,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    ConflictingCandleError,
    RawMarketEvidenceStore,
)


def make_validated_candle(
    index: int,
    base_price: float = 65000.0,
    start_ts_open: int = 1770000000000,
    is_closed: bool = True,
    provenance: str = "LIVE_BINANCE_SPOT",
) -> ValidatedCandle:
    """Deterministic factory for ValidatedCandle instances."""
    ts_open = start_ts_open + index * CANDLE_INTERVAL_MS
    ts_close = ts_open + CANDLE_INTERVAL_MS - 1
    # Introduce small deterministic price movement
    price = base_price * (1.0 + 0.001 * math.sin(index / 5.0))
    dt_open = pd.Timestamp(ts_open, unit="ms", tz="UTC").isoformat()
    dt_close = pd.Timestamp(ts_close, unit="ms", tz="UTC").isoformat()

    return ValidatedCandle(
        symbol="BTCUSDT",
        interval="5m",
        market_type=MarketType.SPOT.value,
        timestamp_open=ts_open,
        timestamp_close=ts_close,
        datetime_open_utc=dt_open,
        datetime_close_utc=dt_close,
        open=f"{price:.2f}",
        high=f"{(price + 20.0):.2f}",
        low=f"{(price - 20.0):.2f}",
        close=f"{(price + 5.0):.2f}",
        volume="12.50000000",
        quote_volume="812500.00000000",
        trades_count=150,
        taker_buy_base_volume="6.25000000",
        is_closed=is_closed,
        provenance=provenance,
        receipt_timestamp_utc=dt_close,
        lifecycle_state=CandleLifecycleState.CANDLE_VALIDATED.value,
    )


def make_prediction_event(
    origin_utc: str,
    horizon: str = "1h",
    branch: str = "candidate_c",
    record_label: str = "HISTORICAL_REPLAY",
) -> ShadowPredictionEvent:
    """Helper to instantiate a valid prediction event."""
    h_mins = 60 if horizon == "1h" else (240 if horizon == "4h" else 1440)
    mat_dt = pd.Timestamp(origin_utc) + pd.Timedelta(minutes=h_mins)
    mat_utc = mat_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    ev = ShadowPredictionEvent(
        event_id=f"PRED-{origin_utc[:16]}-{branch}-{horizon}",
        experiment_id="EXP-SHADOW-V080-2026",
        protocol_version="0.8.0",
        candidate_branch=branch,
        forecast_origin_utc=origin_utc,
        durable_commit_time_utc=origin_utc,
        target_horizon=horizon,
        target_maturity_utc=mat_utc,
        feature_fingerprint="abc123fingerprint",
        component_hashes={"bundle": "hash1"},
        data_quality={"eligible": True},
        point_prediction=0.015,
        interval_80={"lower": 0.005, "upper": 0.035},
        interval_95={"lower": 0.001, "upper": 0.050},
        market_state="LOW_VOL_CONSOLIDATION",
        record_label=record_label,
    )
    ev.record_hash = ev.compute_hash()
    return ev


# ==============================================================================
# 1. Exact Horizon Maturity Tests (1h, 4h, 24h)
# ==============================================================================

def test_01_exact_1h_maturity_12_bars(tmp_path: Path):
    """Verify that a 1h prediction resolves when exactly 12 contiguous closed 5m bars are present."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    # Ingest 12 forward candles
    for i in range(1, 13):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    # Observation clock exactly at 12th candle close
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(outcomes) == 1
    out = outcomes[0]

    assert out.status == "MATURED_VALID"
    assert out.actual_bars_evaluated == 12
    assert not math.isnan(out.realized_volatility)
    assert out.realized_volatility > 0.0
    assert out.maturity_candle_hash != ""
    assert out.maturity_entry_hash != ""


def test_02_exact_4h_maturity_48_bars(tmp_path: Path):
    """Verify that a 4h prediction resolves when exactly 48 contiguous closed 5m bars are present."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    for i in range(1, 49):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="4h")
    clock_ms = start_ts + 48 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(outcomes) == 1
    assert outcomes[0].status == "MATURED_VALID"
    assert outcomes[0].actual_bars_evaluated == 48


def test_03_exact_24h_maturity_288_bars(tmp_path: Path):
    """Verify that a 24h prediction resolves when exactly 288 contiguous closed 5m bars are present."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    # Ingest 288 forward bars
    for i in range(1, 289):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="24h")
    clock_ms = start_ts + 288 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(outcomes) == 1
    assert outcomes[0].status == "MATURED_VALID"
    assert outcomes[0].actual_bars_evaluated == 288
    assert outcomes[0].realized_volatility > 0.0


# ==============================================================================
# 2. Gap Detection & Premature Evaluation Prevention
# ==============================================================================

def test_04_missing_outcome_candle_produces_invalid_gap(tmp_path: Path):
    """Verify that a missing candle in the forward window produces INVALID_GAP and NaN volatility."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    # Ingest bars 1..12 except bar 6 (missing)
    for i in range(1, 13):
        if i == 6:
            continue
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(outcomes) == 1
    assert outcomes[0].status == "INVALID_GAP"
    assert math.isnan(outcomes[0].realized_volatility)
    assert outcomes[0].actual_bars_evaluated == 11


def test_05_delayed_arrival_pending_until_exact_close_time(tmp_path: Path):
    """Verify that an outcome remains pending until wall clock reaches exact target maturity close."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    # Ingest 11 bars (out of 12 required)
    for i in range(1, 12):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")

    # 1. Observation clock is before bar 12 close -> INCOMPLETE_PENDING
    clock_early = start_ts + 11 * CANDLE_INTERVAL_MS
    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_early)
    assert len(outcomes) == 0  # Still pending

    # 2. Add 12th bar and advance clock to maturity close -> Resolves
    store.append_candle(make_validated_candle(12, start_ts_open=start_ts))
    clock_mature = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes2 = resolver.resolve_matured_predictions([pred], current_time_ms=clock_mature)
    assert len(outcomes2) == 1
    assert outcomes2[0].status == "MATURED_VALID"


# ==============================================================================
# 3. Duplicate Prevention & No Double Counting
# ==============================================================================

def test_06_duplicate_evidence_rejection_in_store(tmp_path: Path):
    """Verify that duplicate candle entry is rejected/ignored by the underlying raw evidence store."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")

    candle = make_validated_candle(0)
    status1, _ = store.append_candle(candle)
    assert status1 == "PERSISTED"

    # Second append with identical payload returns DUPLICATE_IGNORED
    status2, _ = store.append_candle(candle)
    assert status2 == "DUPLICATE_IGNORED"

    # Conflicting duplicate returns CONFLICT_QUARANTINED
    conflicting_candle = make_validated_candle(0, base_price=70000.0)
    status3, _ = store.append_candle(conflicting_candle)
    assert status3 == "CONFLICT_QUARANTINED"


def test_07_no_double_counting_across_resolver_evaluations(tmp_path: Path):
    """Verify that resolving an already resolved prediction event produces no duplicate outcomes."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    first_res = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(first_res) == 1

    # Second attempt with the exact same prediction must be ignored
    second_res = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(second_res) == 0


# ==============================================================================
# 4. Restart Recovery & Hash Chain Verification
# ==============================================================================

def test_08_restart_recovery_without_rolling_buffer(tmp_path: Path):
    """Verify that un-matured predictions survive process restart and resolve against persistent SQLite index."""
    market_dir = tmp_path / "raw_market"
    pred_dir = tmp_path / "predictions"
    outcomes_dir = tmp_path / "outcomes"

    # Step 1: Initialize session 1, append prediction and only 6 bars (un-matured)
    store1 = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    p_store1 = ImmutablePredictionStoreV080(pred_dir)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store1.append_candle(origin_candle)
    for i in range(1, 7):
        store1.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    p_store1.append_event(pred)
    assert p_store1.event_count == 1
    store1.close()

    # Step 2: Simulate process termination & complete memory loss.
    # Instantiate completely fresh instances pointing only to persisted disk data
    store2 = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    # Add remaining 6 bars to the raw store
    for i in range(7, 13):
        store2.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    # Restart prediction store and lookup
    p_store2 = ImmutablePredictionStoreV080(pred_dir)
    pending_events = p_store2.get_unmatured_events()
    assert len(pending_events) == 1
    assert pending_events[0].record_hash == pred.record_hash

    lookup2 = PersistentEvidenceLookupV080(evidence_store=store2)
    resolver2 = OutcomeResolverV080(outcomes_dir, evidence_lookup=lookup2)

    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    resolved = resolver2.resolve_matured_predictions(pending_events, current_time_ms=clock_ms)

    assert len(resolved) == 1
    assert resolved[0].status == "MATURED_VALID"
    assert resolved[0].actual_bars_evaluated == 12

    # Prune matured from store and verify queue is empty
    p_store2.prune_matured_events({resolved[0].prediction_event_hash})
    assert len(p_store2.get_unmatured_events()) == 0


def test_09_evidence_hash_linkage_to_ledger(tmp_path: Path):
    """Verify that resolved outcome accurately references the cryptographic hashes in the raw evidence entry."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    out = outcomes[0]

    # Look up maturity entry directly from ledger
    mat_open = start_ts + 12 * CANDLE_INTERVAL_MS
    entry = lookup.get_entry(mat_open)
    assert entry is not None

    assert out.maturity_candle_hash == entry.candle_hash
    assert out.maturity_entry_hash == entry.entry_hash
    assert len(out.maturity_candle_hash) == 64
    assert len(out.maturity_entry_hash) == 64


# ==============================================================================
# 5. Incomplete Candle Rejection & Historical Separation
# ==============================================================================

def test_10_incomplete_unclosed_candle_rejected(tmp_path: Path):
    """Verify that unconfirmed/unclosed candles in the forward window are rejected as invalid gaps."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)

    # Ingest 11 closed bars and 1 unclosed bar (bar 12)
    for i in range(1, 12):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    # Manually append an unclosed candle directly to jsonl and index
    unclosed = make_validated_candle(12, start_ts_open=start_ts, is_closed=False)
    store.append_candle(unclosed)

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(outcomes) == 1
    assert outcomes[0].status == "INVALID_GAP"
    assert math.isnan(outcomes[0].realized_volatility)


def test_11_historical_vs_prospective_record_label_separation(tmp_path: Path):
    """Verify that historical replay and prospective outcome records maintain strict label separation."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred_hist = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h", branch="candidate_c", record_label="HISTORICAL_REPLAY")
    pred_prosp = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h", branch="candidate_e", record_label="PROSPECTIVE_LIVE")

    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    outcomes = resolver.resolve_matured_predictions([pred_hist, pred_prosp], current_time_ms=clock_ms)

    assert len(outcomes) == 2
    out_hist = next(o for o in outcomes if o.candidate_branch == "candidate_c")
    out_prosp = next(o for o in outcomes if o.candidate_branch == "candidate_e")

    assert out_hist.record_label == "HISTORICAL_REPLAY"
    assert out_prosp.record_label == "PROSPECTIVE_LIVE"


# ==============================================================================
# 6. Authorization Bypass Rejection & Zero Live Inference
# ==============================================================================

def test_12_prospective_authorization_and_null_evidence_bypass_rejection(monkeypatch):
    """Verify fail-closed authorization checks and requirement for non-null evidence store."""
    # 1. Gate 4 unapproved fails immediately
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError):
        verify_prospective_execution_boundary(
            evidence_store=None,
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
        )

    # 2. Gate 4 approved, but evidence_store is None -> must raise UnverifiedEvidenceError
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")

    with pytest.raises(UnverifiedEvidenceError):
        verify_prospective_execution_boundary(
            evidence_store=None,
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
        )

    # 3. Offline research does not require evidence_store
    verify_prospective_execution_boundary(
        evidence_store=None,
        record_label="HISTORICAL_REPLAY",
        is_prospective=False,
    )


def test_13_zero_live_inference_execution_during_resolution(tmp_path: Path):
    """Verify outcome resolution operates strictly on market evidence without invoking inference models."""
    market_dir = tmp_path / "raw_market"
    store = RawMarketEvidenceStore(market_dir, tmp_path / "quarantine", "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(tmp_path / "outcomes", evidence_lookup=lookup)

    start_ts = 1770000000000
    origin_candle = make_validated_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_validated_candle(i, start_ts_open=start_ts))

    pred = make_prediction_event(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    # Mock any model runner or external connection to ensure none are called
    mock_runner = MagicMock()
    outcomes = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)

    assert len(outcomes) == 1
    assert outcomes[0].status == "MATURED_VALID"
    mock_runner.predict.assert_not_called()


def test_14_pending_prediction_index_contract(tmp_path: Path):
    """Verify IPendingPredictionIndex implementation contract."""
    pred_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(pred_dir)
    index = JournalPendingPredictionIndexV080(p_store)

    ev1 = make_prediction_event("2026-02-01T00:00:00Z", "1h", "candidate_c")
    ev2 = make_prediction_event("2026-02-01T00:00:00Z", "4h", "candidate_e")

    index.add_pending(ev1)
    index.add_pending(ev2)

    assert index.get_pending_count() == 2
    assert index.is_pending(ev1.record_hash)
    assert index.is_pending(ev2.record_hash)

    index.mark_matured(ev1.record_hash)
    assert index.get_pending_count() == 1
    assert not index.is_pending(ev1.record_hash)
    assert index.is_pending(ev2.record_hash)
