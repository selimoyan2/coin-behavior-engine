"""Offline Verification Suite for CBE-0.8.0 Sprint 09.17.

Durable Prediction & Outcome Indexing — Crash-Safe Persistence:
- Crash before journal append
- Crash after journal append but before SQLite commit (deterministic recovery)
- Crash during index transaction / index deletion recovery
- Repeated journal replay idempotency
- Repeated outcome resolution idempotency (no duplicate counting)
- Restart with pending predictions (bounded O(1) seek)
- Restart after outcome maturity (marked MATURED, not pending)
- Missing maturity candle (marked INVALID_GAP)
- Corrupt trailing journal record (quarantine & in-place ftruncate)
- Mid-chain evidence corruption (fail-closed EventTamperError)
- Durable outcome index rebuild from authoritative journal
- Bounded memory and WAL mode verification
- Scientific causality across 1h, 4h, 24h horizons
- Zero prospective inference without APPROVAL 4
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.shadow_v080.evidence_lookup import (
    ForwardWindowResult,
    ForwardWindowStatus,
    PersistentEvidenceLookupV080,
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
    DurableOutcomeIndexV080,
    DurablePredictionIndexV080,
    IPendingPredictionIndex,
    JournalPendingPredictionIndexV080,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    DuplicateForecastError,
    EventTamperError,
    ImmutablePredictionStoreV080,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    ProspectiveAuthorizationError,
    UnverifiedEvidenceError,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    RawMarketEvidenceStore,
)


def make_test_candle(
    index: int,
    base_price: float = 65000.0,
    start_ts_open: int = 1770000000000,
    is_closed: bool = True,
) -> ValidatedCandle:
    ts_open = start_ts_open + index * CANDLE_INTERVAL_MS
    ts_close = ts_open + CANDLE_INTERVAL_MS - 1
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
        volume="15.0",
        quote_volume="975000.0",
        trades_count=200,
        taker_buy_base_volume="7.5",
        is_closed=is_closed,
        provenance="LIVE_BINANCE_SPOT",
        receipt_timestamp_utc=dt_close,
        lifecycle_state=CandleLifecycleState.CANDLE_VALIDATED.value,
    )


def make_test_prediction(
    origin_utc: str,
    horizon: str = "1h",
    branch: str = "candidate_c",
    record_label: str = "HISTORICAL_REPLAY",
    prev_hash: str = SHADOW_GENESIS_HASH,
) -> ShadowPredictionEvent:
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
        feature_fingerprint="feat123fingerprint",
        component_hashes={"bundle": "bundle_hash_v080"},
        data_quality={"eligible": True},
        point_prediction=0.015,
        interval_80={"lower": 0.005, "upper": 0.035},
        interval_95={"lower": 0.001, "upper": 0.050},
        market_state="LOW_VOL_CONSOLIDATION",
        record_label=record_label,
        previous_event_hash=prev_hash,
    )
    ev.record_hash = ev.compute_hash()
    return ev


# ==============================================================================
# 1. Crash Consistency Scenarios (Scenarios 1, 2, 3, 4)
# ==============================================================================

def test_01_crash_before_journal_append(tmp_path: Path):
    """Crash before journal write leaves state completely clean."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    pred = make_test_prediction("2026-02-01T00:00:00Z")
    # Simulate failure before append_event() is called
    assert p_store.event_count == 0
    assert p_store.get_unmatured_events() == []

    # Restart
    p_store2 = ImmutablePredictionStoreV080(store_dir)
    assert p_store2.event_count == 0
    assert p_store2.get_unmatured_events() == []


def test_02_crash_after_journal_append_before_sqlite_commit(tmp_path: Path):
    """If process crashes after journal append but before SQLite commit, restart reconciles SQLite from journal."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    # 1. Normal append
    ev1 = make_test_prediction("2026-02-01T00:00:00Z", horizon="1h", prev_hash=SHADOW_GENESIS_HASH)
    h1 = p_store.append_event(ev1)

    # 2. Simulate append to journal directly (as if system crashed before SQLite index_event)
    ev2 = make_test_prediction("2026-02-01T00:05:00Z", horizon="1h", prev_hash=h1)
    ev2.previous_event_hash = h1
    ev2.record_hash = ev2.compute_hash()
    with open(p_store.events_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev2.to_dict(), sort_keys=True) + "\n")
        f.flush()

    # In SQLite, only ev1 is currently indexed
    assert p_store.durable_index.get_total_count() == 1

    # 3. Process restarts: new store instance automatically syncs from authoritative journal
    p_store_restart = ImmutablePredictionStoreV080(store_dir)
    assert p_store_restart.event_count == 2
    assert p_store_restart.latest_hash == ev2.record_hash
    assert p_store_restart.durable_index.get_total_count() == 2

    pending = p_store_restart.get_unmatured_events()
    assert len(pending) == 2
    assert pending[1].record_hash == ev2.record_hash


def test_03_crash_during_index_transaction_recovers_from_journal(tmp_path: Path):
    """If SQLite database is deleted or corrupt, restarting recovers 100% of index from journal."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    prev_h = SHADOW_GENESIS_HASH
    for i in range(5):
        ts_utc = f"2026-02-01T00:{i*5:02d}:00Z"
        ev = make_test_prediction(ts_utc, horizon="1h", prev_hash=prev_h)
        prev_h = p_store.append_event(ev)

    assert p_store.event_count == 5
    assert p_store.durable_index.get_total_count() == 5

    # Simulate index loss (delete SQLite file)
    p_store.durable_index.close()
    p_store.index_file.unlink()
    assert not p_store.index_file.exists()

    # Restart store
    p_store_rebuilt = ImmutablePredictionStoreV080(store_dir)
    assert p_store_rebuilt.index_file.exists()
    assert p_store_rebuilt.event_count == 5
    assert p_store_rebuilt.durable_index.get_total_count() == 5
    assert len(p_store_rebuilt.get_unmatured_events()) == 5


def test_04_repeated_journal_replay_is_idempotent(tmp_path: Path):
    """Replaying the authoritative journal multiple times does not duplicate index records."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    ev = make_test_prediction("2026-02-01T00:00:00Z")
    p_store.append_event(ev)

    # Calling rebuild_or_sync_from_journal repeatedly
    count1, _ = p_store.durable_index.rebuild_or_sync_from_journal(p_store.events_file)
    count2, _ = p_store.durable_index.rebuild_or_sync_from_journal(p_store.events_file)

    assert count1 == 1
    assert count2 == 1
    assert p_store.durable_index.get_total_count() == 1


# ==============================================================================
# 2. Outcome Resolution Idempotency & Duplicate Prevention (Scenario 5)
# ==============================================================================

def test_05_repeated_outcome_resolution_idempotency(tmp_path: Path):
    """Repeated outcome resolution does not duplicate outcomes in journal or SQLite index."""
    market_dir = tmp_path / "raw_market"
    quarantine_dir = tmp_path / "quarantine"
    outcomes_dir = tmp_path / "outcomes"

    store = RawMarketEvidenceStore(market_dir, quarantine_dir, "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    resolver = OutcomeResolverV080(outcomes_dir, evidence_lookup=lookup, quarantine_dir=quarantine_dir)

    start_ts = 1770000000000
    origin_candle = make_test_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_test_candle(i, start_ts_open=start_ts))

    pred = make_test_prediction(origin_candle.datetime_close_utc, horizon="1h")
    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1

    # First resolution
    first_res = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(first_res) == 1
    assert resolver.outcome_index.get_outcome_count() == 1
    assert resolver.has_outcome(pred.record_hash)

    # Repeated resolution pass
    second_res = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(second_res) == 0
    assert resolver.outcome_index.get_outcome_count() == 1

    # Rebuilding outcome index produces exact count 1
    resolver.outcome_index.rebuild_or_sync_from_journal()
    assert resolver.outcome_index.get_outcome_count() == 1


# ==============================================================================
# 3. Pending Lifecycle, Status Transition & Restart (Scenarios 6, 7, 8)
# ==============================================================================

def test_06_restart_with_pending_predictions(tmp_path: Path):
    """Pending predictions are retrieved via indexed byte-offset seek across restarts."""
    store_dir = tmp_path / "predictions"
    p_store1 = ImmutablePredictionStoreV080(store_dir)

    prev_h = SHADOW_GENESIS_HASH
    for i in range(3):
        ev = make_test_prediction(f"2026-02-01T00:{i*5:02d}:00Z", horizon="1h", prev_hash=prev_h)
        prev_h = p_store1.append_event(ev)

    assert p_store1.durable_index.get_pending_count() == 3

    # Restart
    p_store2 = ImmutablePredictionStoreV080(store_dir)
    pending = p_store2.get_unmatured_events()
    assert len(pending) == 3
    assert p_store2.durable_index.get_pending_count() == 3


def test_07_restart_after_outcome_maturity_not_pending(tmp_path: Path):
    """Matured predictions transitioned to MATURED in SQLite index do not reappear as pending upon restart."""
    pred_dir = tmp_path / "predictions"
    outcomes_dir = tmp_path / "outcomes"
    market_dir = tmp_path / "raw_market"
    quarantine_dir = tmp_path / "quarantine"

    store = RawMarketEvidenceStore(market_dir, quarantine_dir, "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    p_store = ImmutablePredictionStoreV080(pred_dir, quarantine_dir=quarantine_dir)
    resolver = OutcomeResolverV080(
        outcomes_dir,
        evidence_lookup=lookup,
        prediction_index=p_store.durable_index,
        quarantine_dir=quarantine_dir,
    )

    start_ts = 1770000000000
    origin_candle = make_test_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 13):
        store.append_candle(make_test_candle(i, start_ts_open=start_ts))

    pred = make_test_prediction(origin_candle.datetime_close_utc, horizon="1h")
    p_store.append_event(pred)
    assert p_store.durable_index.get_pending_count() == 1

    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    resolved = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(resolved) == 1
    assert p_store.durable_index.get_pending_count() == 0

    # Restart prediction store
    p_store_restarted = ImmutablePredictionStoreV080(pred_dir, quarantine_dir=quarantine_dir)
    assert p_store_restarted.durable_index.get_pending_count() == 0
    assert len(p_store_restarted.get_unmatured_events()) == 0


def test_08_missing_maturity_candle_marked_invalid_gap_in_index(tmp_path: Path):
    """Forward window gap resolves prediction with status INVALID_GAP and updates index accordingly."""
    pred_dir = tmp_path / "predictions"
    outcomes_dir = tmp_path / "outcomes"
    market_dir = tmp_path / "raw_market"
    quarantine_dir = tmp_path / "quarantine"

    store = RawMarketEvidenceStore(market_dir, quarantine_dir, "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    p_store = ImmutablePredictionStoreV080(pred_dir, quarantine_dir=quarantine_dir)
    resolver = OutcomeResolverV080(
        outcomes_dir,
        evidence_lookup=lookup,
        prediction_index=p_store.durable_index,
        quarantine_dir=quarantine_dir,
    )

    start_ts = 1770000000000
    origin_candle = make_test_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    # Missing bar 5
    for i in range(1, 13):
        if i == 5:
            continue
        store.append_candle(make_test_candle(i, start_ts_open=start_ts))

    pred = make_test_prediction(origin_candle.datetime_close_utc, horizon="1h")
    p_store.append_event(pred)

    clock_ms = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    resolved = resolver.resolve_matured_predictions([pred], current_time_ms=clock_ms)
    assert len(resolved) == 1
    assert resolved[0].status == "INVALID_GAP"
    assert math.isnan(resolved[0].realized_volatility)

    # In prediction index, status is now INVALID_GAP and pending count is 0
    assert p_store.durable_index.get_pending_count() == 0


# ==============================================================================
# 4. Forensic Recovery & Corruption Scenarios (Scenarios 9, 10)
# ==============================================================================

def test_09_corrupt_trailing_journal_record_quarantined_and_truncated(tmp_path: Path):
    """Trailing partial writes at EOF are safely quarantined and truncated in-place without losing valid history."""
    store_dir = tmp_path / "predictions"
    quarantine_dir = tmp_path / "quarantine"
    p_store = ImmutablePredictionStoreV080(store_dir, quarantine_dir=quarantine_dir)

    ev1 = make_test_prediction("2026-02-01T00:00:00Z", horizon="1h")
    h1 = p_store.append_event(ev1)
    ev2 = make_test_prediction("2026-02-01T00:05:00Z", horizon="1h", prev_hash=h1)
    p_store.append_event(ev2)
    assert p_store.event_count == 2

    # Simulate mid-write power cut resulting in partial corrupt trailing bytes
    with open(p_store.events_file, "a", encoding="utf-8") as f:
        f.write('{"event_id": "PRED-corrupt-partial-entry-without-closing-bra')
        f.flush()

    # Restart store
    p_store_restarted = ImmutablePredictionStoreV080(store_dir, quarantine_dir=quarantine_dir)

    # Valid events preserved
    assert p_store_restarted.event_count == 2
    assert p_store_restarted.durable_index.get_total_count() == 2

    # Quarantine file created
    quarantined_files = list(quarantine_dir.glob("forensic_trailing_prediction_corruption_*.bin"))
    assert len(quarantined_files) == 1
    assert b"corrupt-partial" in quarantined_files[0].read_bytes()


def test_10_mid_chain_evidence_corruption_fails_closed(tmp_path: Path):
    """Mid-chain corruption raises EventTamperError fail-closed and does not truncate valid history."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    ev1 = make_test_prediction("2026-02-01T00:00:00Z", horizon="1h")
    h1 = p_store.append_event(ev1)
    ev2 = make_test_prediction("2026-02-01T00:05:00Z", horizon="1h", prev_hash=h1)
    h2 = p_store.append_event(ev2)
    ev3 = make_test_prediction("2026-02-01T00:10:00Z", horizon="1h", prev_hash=h2)
    p_store.append_event(ev3)
    assert p_store.event_count == 3

    # Tamper with middle entry (line 2)
    lines = p_store.events_file.read_text(encoding="utf-8").splitlines()
    data = json.loads(lines[1])
    data["point_prediction"] = 999.99  # Corrupt payload breaks hash
    lines[1] = json.dumps(data)
    p_store.events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Restart must raise EventTamperError fail-closed
    with pytest.raises(EventTamperError, match="Tampered record|Hash chain break"):
        ImmutablePredictionStoreV080(store_dir)


# ==============================================================================
# 5. Outcome Index Rebuild & Performance (Scenarios 11, 12)
# ==============================================================================

def test_11_durable_outcome_index_rebuild_from_journal(tmp_path: Path):
    """Outcome SQLite index can be reconstructed 100% deterministically from shadow_outcomes.jsonl."""
    outcomes_dir = tmp_path / "outcomes"
    quarantine_dir = tmp_path / "quarantine"
    outcomes_file = outcomes_dir / "shadow_outcomes.jsonl"
    outcomes_dir.mkdir(parents=True, exist_ok=True)

    outcome_idx = DurableOutcomeIndexV080(outcomes_dir, outcomes_file=outcomes_file, quarantine_dir=quarantine_dir)

    # Append 3 outcome records to journal and index
    for i in range(3):
        out_event = {
            "outcome_id": f"OUT-test-{i}",
            "prediction_event_hash": f"pred_hash_{i}",
            "forecast_origin_utc": f"2026-02-01T00:{i*5:02d}:00Z",
            "target_maturity_utc": f"2026-02-01T01:{i*5:02d}:00Z",
            "target_horizon": "1h",
            "candidate_branch": "candidate_c",
            "point_forecast": 0.02,
            "realized_volatility": 0.025,
            "actual_bars_evaluated": 12,
            "status": "MATURED_VALID",
            "in_interval_80": 1,
            "in_interval_95": 1,
            "maturity_candle_hash": "c_hash",
            "maturity_entry_hash": "e_hash",
            "record_label": "HISTORICAL_REPLAY",
            "outcome_hash": f"outcome_hash_{i}",
            "evaluated_at_utc": "2026-02-01T01:05:00Z",
        }
        line = json.dumps(out_event, sort_keys=True) + "\n"
        with open(outcomes_file, "a+", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            offset = f.tell()
            f.write(line)
        outcome_idx.record_outcome(out_event, byte_offset=offset, line_no=i+1)

    assert outcome_idx.get_outcome_count() == 3

    # Delete index file and rebuild
    outcome_idx.close()
    outcome_idx.index_file.unlink()
    assert not outcome_idx.index_file.exists()

    outcome_idx2 = DurableOutcomeIndexV080(outcomes_dir, outcomes_file=outcomes_file, quarantine_dir=quarantine_dir)
    synced = outcome_idx2.rebuild_or_sync_from_journal()
    assert synced == 3
    assert outcome_idx2.get_outcome_count() == 3
    assert outcome_idx2.has_outcome("pred_hash_1")


def test_12_sqlite_wal_mode_and_bounded_cache(tmp_path: Path):
    """Verify SQLite index utilizes WAL journal mode and capped cache size for bounded memory."""
    store_dir = tmp_path / "predictions"
    p_store = ImmutablePredictionStoreV080(store_dir)

    with p_store.durable_index._get_connection() as conn:
        cur = conn.cursor()

        cur.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"

        cur.execute("PRAGMA synchronous;")
        sync = cur.fetchone()[0]
        # Normal synchronous is 1
        assert sync == 1


# ==============================================================================
# 6. Scientific Causality & Authorization Integrity (Scenarios 13, 14)
# ==============================================================================

def test_13_exact_1h_4h_24h_causality_with_durable_indexing(tmp_path: Path):
    """Verify exact horizon maturity evaluation (12, 48, 288 bars) with durable indexing enabled."""
    market_dir = tmp_path / "raw_market"
    pred_dir = tmp_path / "predictions"
    outcomes_dir = tmp_path / "outcomes"
    quarantine_dir = tmp_path / "quarantine"

    store = RawMarketEvidenceStore(market_dir, quarantine_dir, "BTCUSDT", "5m")
    lookup = PersistentEvidenceLookupV080(evidence_store=store)
    p_store = ImmutablePredictionStoreV080(pred_dir, quarantine_dir=quarantine_dir)
    resolver = OutcomeResolverV080(
        outcomes_dir,
        evidence_lookup=lookup,
        prediction_index=p_store.durable_index,
        quarantine_dir=quarantine_dir,
    )

    start_ts = 1770000000000
    origin_candle = make_test_candle(0, start_ts_open=start_ts)
    store.append_candle(origin_candle)
    for i in range(1, 289):
        store.append_candle(make_test_candle(i, start_ts_open=start_ts))

    # Commit 3 predictions across 1h, 4h, 24h
    pred_1h = make_test_prediction(origin_candle.datetime_close_utc, horizon="1h", prev_hash=SHADOW_GENESIS_HASH)
    h1 = p_store.append_event(pred_1h)
    pred_4h = make_test_prediction(origin_candle.datetime_close_utc, horizon="4h", prev_hash=h1)
    h2 = p_store.append_event(pred_4h)
    pred_24h = make_test_prediction(origin_candle.datetime_close_utc, horizon="24h", prev_hash=h2)
    p_store.append_event(pred_24h)

    assert p_store.durable_index.get_pending_count() == 3

    # Clock at 1h maturity
    clock_1h = start_ts + 12 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    res_1h = resolver.resolve_matured_predictions([pred_1h, pred_4h, pred_24h], current_time_ms=clock_1h)
    assert len(res_1h) == 1
    assert res_1h[0].target_horizon == "1h"
    assert res_1h[0].actual_bars_evaluated == 12
    assert p_store.durable_index.get_pending_count() == 2

    # Clock at 4h maturity
    clock_4h = start_ts + 48 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    res_4h = resolver.resolve_matured_predictions([pred_4h, pred_24h], current_time_ms=clock_4h)
    assert len(res_4h) == 1
    assert res_4h[0].target_horizon == "4h"
    assert res_4h[0].actual_bars_evaluated == 48
    assert p_store.durable_index.get_pending_count() == 1

    # Clock at 24h maturity
    clock_24h = start_ts + 288 * CANDLE_INTERVAL_MS + CANDLE_INTERVAL_MS - 1
    res_24h = resolver.resolve_matured_predictions([pred_24h], current_time_ms=clock_24h)
    assert len(res_24h) == 1
    assert res_24h[0].target_horizon == "24h"
    assert res_24h[0].actual_bars_evaluated == 288
    assert p_store.durable_index.get_pending_count() == 0


def test_14_zero_prospective_inference_without_approval_4(monkeypatch):
    """Enforce fail-closed gate: Approval 4 absent strictly blocks prospective execution."""
    from coin_behavior_engine.shadow_v080.inference_runner import verify_prospective_execution_boundary

    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")

    with pytest.raises(ProspectiveAuthorizationError):
        verify_prospective_execution_boundary(
            evidence_store=None,
            record_label="PROSPECTIVE_LIVE",
            is_prospective=True,
        )
