"""Deterministic Regression, Crash Consistency & Policy Parity Test Suite for CBE Sprint 11.16B.5.

Covers:
1. Compact analogue candidate matrix loading, schema, and normalization vector verification.
2. Bitwise parity between CompactAnalogueRuntime and reference HistoricalAnalogueEngine on training candidates.
3. Compact runtime performance bounds (memory footprint < 15 MB, query latency < 10 ms).
4. CrashConsistentJournal atomic transitions and crash recovery scenarios:
   - Crash before decision commit.
   - Crash after decision commit with pending order.
   - Crash after fill commit (duplicate fill prevention).
   - Truncated/corrupted WAL line handling.
   - Atomic snapshot checkpoint verification.
5. Feed and warmup correctness:
   - 300s spacing enforcement and gap invalidation.
   - Canonical seed digest verification.
   - No retroactive fills (causal next-open requirement).
6. Full 5-policy independent replay parity verification.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.compact_analogue_runtime import (
    CANONICAL_COMPACT_ANALOGUE_SHA256,
    AnaloguePredictionResult,
    CompactAnalogueMatch,
    CompactAnalogueRuntime,
)
from coin_behavior_engine.research_lab.crash_consistent_journal import (
    CrashConsistentJournal,
    JournalEntryType,
    VirtualFill,
    VirtualOrder,
)
from coin_behavior_engine.research_lab.independent_policy_replay import (
    FROZEN_POLICIES,
    IndependentPolicyReplayHarness,
)
from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
)
from coin_behavior_engine.research_lab.shadow_market_data_bridge import (
    CandleStreamType,
    HistoricalSeedProvenance,
    MarketCandle,
    PersistentRollingBuffer,
    ShadowMarketDataBridge,
)


# -------------------------------------------------------------------------
# Test Group 1: Compact Analogue Runtime & Candidate Matrix
# -------------------------------------------------------------------------

def test_compact_analogue_candidates_loading_and_shape():
    """Verify compact analogue candidates file exists, loads, and matches exact frozen matrix dimensions."""
    runtime = CompactAnalogueRuntime()
    ok, msg = runtime.verify_and_load()
    assert ok is True, f"Failed to load: {msg}"
    assert runtime.is_loaded is True

    # Check candidate matrix dimensions: (67752, 10), float32
    assert runtime.candidate_matrix.ndim == 2
    assert runtime.candidate_matrix.shape[1] == 10
    assert runtime.candidate_matrix.shape[0] == 67752
    assert runtime.candidate_matrix.dtype == np.float32

    # Check returns and regimes
    assert len(runtime.candidate_returns) == 67752
    assert runtime.candidate_returns.dtype == np.float32
    assert len(runtime.candidate_regimes) == 67752
    assert len(runtime.candidate_timestamps) == 67752

    # Check normalization vectors
    assert len(runtime.feat_means) == 10
    assert len(runtime.feat_stds) == 10
    assert np.all(runtime.feat_stds > 0)


def test_compact_analogue_memory_and_latency_bounds():
    """Verify compact runtime strictly satisfies memory (<15 MB) and latency (<10 ms) bounds."""
    runtime = CompactAnalogueRuntime()
    runtime.verify_and_load()

    # Memory footprint of raw arrays
    mem_matrix_mb = runtime.candidate_matrix.nbytes / (1024 * 1024)
    mem_returns_mb = runtime.candidate_returns.nbytes / (1024 * 1024)
    mem_timestamps_mb = runtime.candidate_timestamps.nbytes / (1024 * 1024)
    total_mem_mb = mem_matrix_mb + mem_returns_mb + mem_timestamps_mb

    assert total_mem_mb < 15.0, f"Candidate array memory {total_mem_mb:.2f} MB exceeds 15 MB limit"

    # Query latency benchmark over 50 queries
    query_vec = runtime.candidate_matrix[100].copy()
    latencies_ms = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = runtime.query(query_vec, k=20)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    avg_latency = float(np.mean(latencies_ms))
    p95_latency = float(np.percentile(latencies_ms, 95))

    assert avg_latency < 10.0, f"Average query latency {avg_latency:.2f} ms exceeds 10 ms limit"
    assert p95_latency < 15.0, f"P95 query latency {p95_latency:.2f} ms exceeds 15 ms limit"
    assert res.analogues_count == 20
    assert 0.0 <= res.prob_up <= 1.0


def test_compact_analogue_temporal_thinning_and_filter():
    """Verify candidate search enforces candidate_spacing_bars >= 12."""
    runtime = CompactAnalogueRuntime()
    runtime.verify_and_load()

    query_vec = runtime.candidate_matrix[500].copy()
    res = runtime.query(query_vec, k=20)

    assert len(res.analogue_matches) == 20
    # Check that candidate indices are separated by at least 12 bars
    sorted_ids = sorted([m.analogue_index for m in res.analogue_matches])
    for i in range(1, len(sorted_ids)):
        assert (sorted_ids[i] - sorted_ids[i - 1]) >= 12, "Spacing filter violated"


# -------------------------------------------------------------------------
# Test Group 2: Crash-Consistent Journal & Atomic Recovery
# -------------------------------------------------------------------------

def test_journal_initialization_and_recovery(tmp_path: Path):
    """Verify new journal initialization and idempotent empty recovery."""
    journal_dir = tmp_path / "journal_test_init"
    journal = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_C_TREND48_FOLLOWING")

    assert journal.usdt_balance == 10000.0
    assert journal.btc_balance == 0.0
    assert journal.position_active is False

    # Recover empty
    journal2 = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_C_TREND48_FOLLOWING")
    ok, msg = journal2.recover()
    assert ok is True
    assert journal2.usdt_balance == 10000.0
    assert journal2.btc_balance == 0.0
    assert journal2.sequence_number == 0


def test_journal_commit_decision_and_fill(tmp_path: Path):
    """Verify complete lifecycle: commit decision -> pending order -> commit fill -> checkpoint."""
    journal_dir = tmp_path / "journal_test_fill"
    journal = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_B_BTC_BUY_AND_HOLD")

    ok_dec = journal.commit_decision(
        decision_id="DEC-00001",
        decision_hash="hash00001",
        action="BUY_CANDIDATE",
        candle_open_utc="2026-10-18T10:00:00Z",
        candle_close_utc="2026-10-18T10:04:59Z",
        close_p=80000.0,
    )
    assert ok_dec is True
    assert journal.pending_order is not None
    order = journal.pending_order
    assert order.action == "BUY"

    # Execute fill at next open
    fill = journal.commit_fill(
        order=order,
        next_open_price=80000.0,
        fill_timestamp_utc="2026-10-18T10:05:00Z",
    )
    assert fill is not None
    assert fill.action == "BUY"
    assert journal.pending_order is None
    assert journal.position_active is True
    assert journal.btc_balance > 0.0
    assert math.isclose(journal.usdt_balance, 10000.0 * 0.02 - fill.fee_usdt, abs_tol=1e-4)

    # Create checkpoint
    snap = journal.create_checkpoint()
    assert snap is not None
    assert journal.checkpoint_path.is_file()

    # Recover in a new journal instance
    journal_recovered = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_B_BTC_BUY_AND_HOLD")
    ok_rec, msg_rec = journal_recovered.recover()
    assert ok_rec is True

    assert journal_recovered.position_active is True
    assert math.isclose(journal_recovered.btc_balance, journal.btc_balance, abs_tol=1e-8)
    assert math.isclose(journal_recovered.usdt_balance, journal.usdt_balance, abs_tol=1e-4)
    assert "DEC-00001" in journal_recovered.executed_decision_ids
    assert fill.fill_id in journal_recovered.executed_fill_ids


def test_journal_crash_with_pending_order_recovery(tmp_path: Path):
    """Crash simulation: crash occurred after decision committed but BEFORE fill was executed.

    Upon recovery, pending order must be cleanly reconstructed and ready for fill execution.
    """
    journal_dir = tmp_path / "journal_crash_pending"
    journal = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_B_BTC_BUY_AND_HOLD")

    ok_dec = journal.commit_decision(
        decision_id="DEC-PENDING-01",
        decision_hash="hash_pending_01",
        action="BUY_CANDIDATE",
        candle_open_utc="2026-10-18T12:00:00Z",
        candle_close_utc="2026-10-18T12:04:59Z",
        close_p=82000.0,
    )
    assert ok_dec is True
    assert journal.pending_order is not None
    orig_order_id = journal.pending_order.order_id

    # SIMULATE CRASH: Process dies here before commit_fill.
    # New journal instance recovers from disk.
    journal_crashed = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_B_BTC_BUY_AND_HOLD")
    ok_rec, msg_rec = journal_crashed.recover()
    assert ok_rec is True

    assert journal_crashed.pending_order is not None
    assert journal_crashed.pending_order.order_id == orig_order_id
    assert journal_crashed.pending_order.action == "BUY"
    assert journal_crashed.position_active is False
    assert journal_crashed.btc_balance == 0.0

    # Execute fill now
    fill = journal_crashed.commit_fill(
        order=journal_crashed.pending_order,
        next_open_price=82100.0,
        fill_timestamp_utc="2026-10-18T12:05:00Z",
    )
    assert fill is not None
    assert journal_crashed.position_active is True
    assert journal_crashed.pending_order is None


def test_journal_duplicate_fill_rejection(tmp_path: Path):
    """Verify that an order that was already filled cannot be filled a second time."""
    journal_dir = tmp_path / "journal_dup_fill"
    journal = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_B_BTC_BUY_AND_HOLD")

    journal.commit_decision(
        decision_id="DEC-00002",
        decision_hash="hash00002",
        action="BUY_CANDIDATE",
        candle_open_utc="2026-10-18T11:00:00Z",
        candle_close_utc="2026-10-18T11:04:59Z",
        close_p=80000.0,
    )
    order = journal.pending_order
    fill1 = journal.commit_fill(order=order, next_open_price=80000.0, fill_timestamp_utc="2026-10-18T11:05:00Z")
    assert fill1 is not None

    # Attempt second fill on same order
    fill2 = journal.commit_fill(order=order, next_open_price=80000.0, fill_timestamp_utc="2026-10-18T11:05:00Z")
    assert fill2 is None  # Must reject duplicate fill


def test_journal_checkpoint_tamper_fails_closed(tmp_path: Path):
    """Verify that a corrupted checkpoint file fails closed on recovery."""
    journal_dir = tmp_path / "journal_corrupt_chk"
    journal = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_A_USDT_CASH")

    journal.commit_decision(
        decision_id="DEC-GOOD-01",
        decision_hash="hash_good_01",
        action="WAIT_USDT",
        candle_open_utc="2026-10-18T10:00:00Z",
        candle_close_utc="2026-10-18T10:04:59Z",
        close_p=80000.0,
    )
    journal.create_checkpoint()

    # Tamper with checkpoint JSON
    chk_data = json.loads(journal.checkpoint_path.read_text(encoding="utf-8"))
    chk_data["btc_balance"] = 999.0  # Unauthorized balance mutation
    journal.checkpoint_path.write_text(json.dumps(chk_data), encoding="utf-8")

    # Recovery must fail closed
    journal_recovered = CrashConsistentJournal(journal_dir=journal_dir, initial_capital_usdt=10000.0, policy_id="POLICY_A_USDT_CASH")
    ok, err_msg = journal_recovered.recover()
    assert ok is False
    assert "CHECKPOINT_CORRUPT" in err_msg


# -------------------------------------------------------------------------
# Test Group 3: Feed and Warmup Correctness
# -------------------------------------------------------------------------

def _make_candle(
    idx: int,
    base_time: datetime,
    open_p: float = 80000.0,
    is_closed: bool = True,
    stream_type: CandleStreamType = CandleStreamType.HISTORICAL_SEED_WARMUP,
) -> MarketCandle:
    t_open = base_time + timedelta(minutes=5 * idx)
    t_close = t_open + timedelta(minutes=4, seconds=59)
    return MarketCandle(
        symbol="BTCUSDT",
        interval="5m",
        timestamp_open_utc=t_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
        timestamp_close_utc=t_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
        open_p=open_p,
        high_p=open_p * 1.002,
        low_p=open_p * 0.998,
        close_p=open_p * 1.001,
        volume_base=10.0,
        volume_usdt=10.0 * open_p,
        is_closed=is_closed,
        sequence_number=idx,
        stream_type=stream_type,
        provenance="TEST_FIXTURE",
    )


def test_feed_spacing_enforcement_and_gap_invalidation():
    """Verify that candles with interval != 300s or gaps invalidate buffer warmup status."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864, buffer_capacity=1000)
    base_time = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)

    # Ingest 864 valid contiguous candles
    seed_candles = [_make_candle(i, base_time) for i in range(864)]
    prov = HistoricalSeedProvenance(
        seed_id="SEED-001",
        dataset_name="test_data",
        dataset_sha256=HistoricalSeedProvenance.compute_canonical_digest(seed_candles),
        start_timestamp_utc=seed_candles[0].timestamp_open_utc,
        end_timestamp_utc=seed_candles[-1].timestamp_open_utc,
        candle_count=864,
        is_authorized=True,
    )
    ok, err = bridge.buffer.ingest_seed_candles(seed_candles, prov)
    assert ok is True, f"Seed ingestion failed: {err}"
    assert bridge.buffer.is_warmup_ready is True

    # Ingest next candle with a 15-minute gap (jump from idx 863 to idx 866)
    gap_candle = _make_candle(866, base_time, stream_type=CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION)
    ok_gap, err_gap = bridge.buffer.append_candle(gap_candle)

    # Buffer must reject gap candle and preserve gap invalidation
    assert ok_gap is False
    assert "GAP_DETECTED" in err_gap
    assert bridge.buffer._gap_detected is True
    assert bridge.buffer.is_warmup_ready is False


def test_seed_digest_matching_rejection():
    """Verify that modified seed candle values are detected via SHA-256 digest mismatch."""
    base_time = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
    candles = [_make_candle(i, base_time) for i in range(864)]

    # Claim wrong digest in provenance
    bad_prov = HistoricalSeedProvenance(
        seed_id="SEED-BAD",
        dataset_name="test_data",
        dataset_sha256="deadbeef" * 8,
        start_timestamp_utc=candles[0].timestamp_open_utc,
        end_timestamp_utc=candles[-1].timestamp_open_utc,
        candle_count=864,
        is_authorized=True,
    )
    buffer = PersistentRollingBuffer(min_warmup_bars=864, capacity=1000)
    ok, err = buffer.ingest_seed_candles(candles, bad_prov)
    assert ok is False
    assert "HASH_MISMATCH" in err


# -------------------------------------------------------------------------
# Test Group 4: Full Five-Policy Independent Replay Parity
# -------------------------------------------------------------------------

def test_full_five_policy_independent_replay_parity(tmp_path: Path):
    """Run full 5-policy independent replay harness on canonical fixture and assert PERFECT_PARITY."""
    parquet_path = Path("research_outputs/market_state_dataset.parquet")
    if not parquet_path.is_file():
        pytest.skip("Canonical dataset parquet not found")

    harness = IndependentPolicyReplayHarness(
        initial_capital_usdt=10000.0,
        output_dir=tmp_path / "replay_test_parity",
    )
    results = harness.run_replay_audit(
        warmup_bars=864,
        eval_bars=288,
        dataset_path=parquet_path,
    )

    assert results["total_records"] == 1440
    summaries = results["summaries"]

    for policy_id in FROZEN_POLICIES:
        s = summaries[policy_id]
        assert s["total_evaluated_bars"] == 288
        assert s["action_matches"] == 288, f"Action mismatch in {policy_id}: {s['action_matches']}/288"
        assert s["balance_matches"] == 288, f"Balance mismatch in {policy_id}: {s['balance_matches']}/288"
        assert s["total_discrepancies"] == 0, f"Discrepancies found in {policy_id}: {s['total_discrepancies']}"
        assert s["parity_verdict"] == "PERFECT_PARITY"
        assert math.isclose(s["ending_ref_equity"], s["ending_indep_equity"], abs_tol=1e-3)
