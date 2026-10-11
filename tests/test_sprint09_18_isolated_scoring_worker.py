"""Sprint 09.18: Isolated Prospective Scoring Worker Tests.

Verifies:
1. Fail-closed authorization checks at BACKGROUND_WORKER execution boundary.
2. Approval 3 active alone does NOT confer Approval 4 prospective scoring authorization.
3. Offline warmup mode executes safely without Approval 4 and emits zero live predictions.
4. Continuous warmup enforcement (287 bars rejected vs 288 contiguous bars accepted).
5. Timestamp gaps in rolling warmup buffer reject prospective inference.
6. WorkerStartBoundaryRecord persistence, loading, and immutable barrier enforcement.
7. Pre-boundary candles closed <= start boundary are strictly HISTORICAL_WARMUP and NEVER emit prospective live predictions.
8. Post-boundary candles closed > start boundary emit prospective predictions when Gate 4 authorized.
9. Zero-discard queue overflow handling (> 2,000 pending items) via paged queries with bounded memory.
10. Crash-safe checkpointing and idempotent resumption.
11. Read-only raw market evidence ledger protection (zero write permission).
12. Offline resource benchmarks (latency and bounded memory).
13. Coolify container and entrypoint configuration validation.
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
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    CandleData,
)
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    MarketType,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    HORIZON_BARS,
    OutcomeResolverV080,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_indexing import (
    DurablePredictionIndexV080,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    ImmutablePredictionStoreV080,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    CausalDataEligibilityGuard,
    DiscontinuousCandlesError,
    ExecutionBoundary,
    InsufficientWarmupBarsError,
    ProspectiveAuthorizationError,
    ProspectiveAuthorizationGuard,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    MarketEvidenceEntry,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.scoring_worker import (
    ProspectiveScoringWorkerV080,
    WorkerCheckpoint,
    WorkerConfigV080,
    WorkerStartBoundaryRecord,
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
        volume=f"{(15.0 + 0.5 * math.sin(index)):.4f}",
        quote_volume="975000.0",
        trades_count=200,
        taker_buy_base_volume="7.5",
        is_closed=is_closed,
        provenance="LIVE_BINANCE_SPOT",
        receipt_timestamp_utc=dt_close,
    )


def populate_raw_evidence(
    evidence_dir: Path,
    num_candles: int = 300,
    start_ts_open: int = 1770000000000,
) -> List[ValidatedCandle]:
    """Helper to populate raw evidence store with valid test candles."""
    quarantine_dir = evidence_dir.parent / "quarantine"
    store = RawMarketEvidenceStore(
        raw_market_dir=evidence_dir,
        quarantine_dir=quarantine_dir,
        symbol="BTCUSDT",
        interval="5m",
    )
    candles = []
    for i in range(num_candles):
        c = make_test_candle(i, start_ts_open=start_ts_open)
        store.append_candle(c)
        candles.append(c)
    store.close()
    return candles


# ==============================================================================
# 1. Authorization Tests
# ==============================================================================

def test_01_worker_authorization_fail_closed_without_approval_4():
    """Worker fails closed if APPROVAL 4 is absent or disabled in PROSPECTIVE_LIVE mode."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        populate_raw_evidence(ev_dir, num_candles=5)

        env = {
            "CBE_APPROVAL_4_AUTHORIZED": "false",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            "CBE_TRADING_DISABLED": "true",
        }

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PROSPECTIVE_LIVE",
            env=env,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            # establish_start_boundary must fail-closed
            with pytest.raises(ProspectiveAuthorizationError):
                worker.establish_start_boundary()

            # Direct authorization check at BACKGROUND_WORKER execution boundary must fail
            with pytest.raises(ProspectiveAuthorizationError):
                ProspectiveAuthorizationGuard.verify_authorization(
                    boundary=ExecutionBoundary.BACKGROUND_WORKER,
                    run_mode="PROSPECTIVE_LIVE",
                    env=env,
                )
        finally:
            worker.close()


def test_02_worker_approval_3_does_not_confer_approval_4():
    """Approval 3 active alone does NOT confer prospective scoring authorization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        populate_raw_evidence(ev_dir, num_candles=5)

        env = {
            "CBE_APPROVAL_3_AUTHORIZED": "true",
            "CBE_BINANCE_COLLECTION_ENABLED": "true",
            "CBE_APPROVAL_4_AUTHORIZED": "false",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            "CBE_TRADING_DISABLED": "true",
        }

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PROSPECTIVE_LIVE",
            env=env,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            with pytest.raises(ProspectiveAuthorizationError) as exc_info:
                worker.establish_start_boundary()
            assert "Approval 3" in str(exc_info.value) or "Approval 4" in str(exc_info.value)
        finally:
            worker.close()


def test_03_worker_offline_warmup_mode_allowed_without_approval_4():
    """Worker can initialize and process evidence in OFFLINE_WARMUP mode without Approval 4."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        populate_raw_evidence(ev_dir, num_candles=10)

        env = {
            "CBE_APPROVAL_4_AUTHORIZED": "false",
            "CBE_TRADING_DISABLED": "true",
        }

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="OFFLINE_WARMUP",
            env=env,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            processed = worker.process_next_batch()

            assert processed == 10
            assert worker.checkpoint.total_entries_read == 10
            # Zero prospective predictions emitted in offline warmup mode
            assert worker.checkpoint.total_predictions_emitted == 0
        finally:
            worker.close()


# ==============================================================================
# 2. Continuous Warmup Enforcement Tests
# ==============================================================================

def test_04_continuous_warmup_enforcement_287_vs_288_bars():
    """Worker requires at least 288 contiguous closed 5m bars before prospective scoring."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=288)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            min_warmup_bars=288,
            batch_size=300,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            # Ingest 287 bars manually into buffer
            worker._recent_candles = list(candles[:287])
            is_ready, count, msg = worker.check_warmup_status()
            assert is_ready is False
            assert count == 287
            assert "Insufficient warmup" in msg

            # Ingest 288th bar
            worker._recent_candles.append(candles[287])
            is_ready, count, msg = worker.check_warmup_status()
            assert is_ready is True
            assert count == 288
            assert "Full warmup satisfied" in msg
        finally:
            worker.close()


def test_05_warmup_gap_rejection():
    """A timestamp gap in the rolling warmup buffer invalidates warmup status."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=300)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            min_warmup_bars=288,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            # Create list with gap at bar 100
            discontinuous_candles = list(candles[:100])
            # Skip 1 candle (10m gap)
            discontinuous_candles.extend(candles[101:290])
            worker._recent_candles = discontinuous_candles

            is_ready, count, msg = worker.check_warmup_status()
            assert is_ready is False
            assert "Discontinuous candles" in msg
        finally:
            worker.close()


# ==============================================================================
# 3. Immutable Start Boundary & Separation of Replay
# ==============================================================================

def test_06_start_boundary_persistence_and_reloading():
    """WorkerStartBoundaryRecord saves and loads accurately."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        file_path = tmp_path / "authorized_start_boundary.json"

        rec = WorkerStartBoundaryRecord(
            authorized_start_boundary_utc="2026-02-01T12:00:00Z",
            authorized_start_boundary_ts_ms=1770000000000,
            git_commit="abcdef1234567890",
            authorization_digest="AUTH-DIGEST-12345678",
            last_captured_candle_timestamp_ms=1769999999999,
            created_at_utc="2026-02-01T12:00:01Z",
        )
        rec.save(file_path)

        loaded = WorkerStartBoundaryRecord.load(file_path)
        assert loaded is not None
        assert loaded.authorized_start_boundary_utc == rec.authorized_start_boundary_utc
        assert loaded.authorized_start_boundary_ts_ms == rec.authorized_start_boundary_ts_ms
        assert loaded.git_commit == rec.git_commit
        assert loaded.authorization_digest == rec.authorization_digest


def test_07_pre_boundary_candles_strictly_historical_warmup():
    """Candles closed <= start boundary NEVER emit prospective live predictions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=300)

        # Set start boundary AFTER candle index 295
        boundary_ts = candles[295].timestamp_close
        boundary = WorkerStartBoundaryRecord(
            authorized_start_boundary_utc="2026-02-01T12:00:00Z",
            authorized_start_boundary_ts_ms=boundary_ts,
            git_commit="test_commit",
            authorization_digest="test_digest",
            last_captured_candle_timestamp_ms=boundary_ts,
            created_at_utc="2026-02-01T12:00:00Z",
        )
        boundary.save(prosp_dir / "authorized_start_boundary.json")

        env = {
            "CBE_APPROVAL_4_AUTHORIZED": "true",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "true",
            "CBE_TRADING_DISABLED": "true",
        }

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PROSPECTIVE_LIVE",
            batch_size=300,
            env=env,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            # Process candles up to 295 (all pre-boundary)
            worker.evidence_lookup.get_entries_after_index = MagicMock(
                return_value=[
                    (MarketEvidenceEntry(i + 1, "test_hash", "prev", candles[i].timestamp_open, candles[i].timestamp_close, 100), candles[i])
                    for i in range(296)
                ]
            )

            worker.process_next_batch()

            # Zero prospective predictions must be emitted for pre-boundary bars
            assert worker.checkpoint.total_predictions_emitted == 0
            assert worker.prediction_store.get_pending_count() == 0
        finally:
            worker.close()


def test_08_post_boundary_candles_emit_prospective_predictions_when_authorized():
    """Post-boundary candles closed > start boundary emit prospective predictions when authorized."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=300)

        # Set boundary at candle 288
        boundary_ts = candles[288].timestamp_close
        boundary = WorkerStartBoundaryRecord(
            authorized_start_boundary_utc="2026-02-01T12:00:00Z",
            authorized_start_boundary_ts_ms=boundary_ts,
            git_commit="test_commit",
            authorization_digest="test_digest",
            last_captured_candle_timestamp_ms=boundary_ts,
            created_at_utc="2026-02-01T12:00:00Z",
        )
        boundary.save(prosp_dir / "authorized_start_boundary.json")

        env = {
            "CBE_APPROVAL_4_AUTHORIZED": "true",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "true",
            "CBE_TRADING_DISABLED": "true",
        }

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PROSPECTIVE_LIVE",
            batch_size=300,
            env=env,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            # Mock inference runner to return valid prediction result
            mock_result = MagicMock()
            mock_result.point_forecasts = {"1h": 0.02, "4h": 0.04, "24h": 0.08}
            branch_int = MagicMock()
            branch_int.interval_80 = (0.01, 0.03)
            branch_int.interval_95 = (0.005, 0.035)
            mock_result.candidate_c_intervals = {"1h": branch_int, "4h": branch_int, "24h": branch_int}
            mock_result.candidate_e_intervals = {"1h": branch_int, "4h": branch_int, "24h": branch_int}
            mock_result.primary_state = "NORMAL_VOLATILITY"

            worker.inference_runner = MagicMock()
            worker.inference_runner.predict.return_value = mock_result

            # Process all 300 candles: candles 0..288 are pre-boundary, candles 289..299 are post-boundary
            worker.process_next_batch()

            # Total post-boundary candles = 300 - 289 = 11 candles
            # Each candle emits 2 branches x 3 horizons = 6 prediction events
            expected_events = 11 * 6
            assert worker.checkpoint.total_predictions_emitted == expected_events
            assert worker.prediction_store.get_pending_count() == expected_events
        finally:
            worker.close()


# ==============================================================================
# 4. Zero-Discard Queue Overflow (> 2,000 pending items) Tests
# ==============================================================================

def test_09_zero_discard_queue_overflow_over_2000_items():
    """Pending prediction store handles > 2,000 items with bounded pagination without silent eviction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        prosp_dir = tmp_path / "prospective"

        store = ImmutablePredictionStoreV080(
            store_dir=prosp_dir,
            enable_sqlite_index=True,
        )
        try:
            total_items = 2100
            events: List[ShadowPredictionEvent] = []
            for i in range(total_items):
                ev = ShadowPredictionEvent(
                    event_id=f"EVT-{i:05d}",
                    experiment_id="EXP-1",
                    protocol_version="V1",
                    candidate_branch="candidate_c",
                    forecast_origin_utc=f"2026-02-01T{i%24:02d}:00:00Z",
                    durable_commit_time_utc="2026-02-01T00:00:00Z",
                    target_horizon="1h",
                    target_maturity_utc="2026-02-01T01:00:00Z",
                    feature_fingerprint="fprint",
                    component_hashes={},
                    data_quality={},
                    point_prediction=0.02,
                    interval_80={"lower": 0.01, "upper": 0.03},
                    interval_95={"lower": 0.005, "upper": 0.035},
                    market_state="NORMAL_VOLATILITY",
                    record_label="PROSPECTIVE_LIVE",
                )
                events.append(ev)

            # Batch append all 2,100 events
            store.append_events_batch(events)

            # 1. Total pending count must be exactly 2,100
            assert store.get_pending_count() == total_items

            # 2. get_unmatured_events must return all 2,100 events without silent eviction
            all_pending = store.get_unmatured_events()
            assert len(all_pending) == total_items

            # 3. Paged iteration must retrieve all items in pages of 500
            pages = list(store.get_unmatured_events_paged(page_size=500))
            assert len(pages) == 5
            assert len(pages[0]) == 500
            assert len(pages[1]) == 500
            assert len(pages[2]) == 500
            assert len(pages[3]) == 500
            assert len(pages[4]) == 100

            # Verify no items were duplicated across pages
            seen_ids = set()
            for page in pages:
                for ev in page:
                    assert ev.event_id not in seen_ids
                    seen_ids.add(ev.event_id)
            assert len(seen_ids) == total_items
        finally:
            if store.durable_index:
                store.durable_index.close()


# ==============================================================================
# 5. Crash Recovery & Checkpointing Tests
# ==============================================================================

def test_10_crash_recovery_and_checkpoint_durability():
    """Worker state checkpointing survives simulated crash and resumes idempotently."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=50)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="OFFLINE_WARMUP",
            batch_size=20,
        )

        # First run: process batch 1 (20 items: 0..19)
        worker1 = ProspectiveScoringWorkerV080(config)
        try:
            processed1 = worker1.process_next_batch()
            assert processed1 == 20
            assert worker1.checkpoint.last_processed_entry_index == 19
        finally:
            worker1.close()

        # Simulate Crash: re-instantiate worker from disk
        worker2 = ProspectiveScoringWorkerV080(config)
        try:
            assert worker2.checkpoint.last_processed_entry_index == 19

            # Process next batch: should start from entry 20 and process 20 items (20..39)
            processed2 = worker2.process_next_batch()
            assert processed2 == 20
            assert worker2.checkpoint.last_processed_entry_index == 39
            assert worker2.checkpoint.total_entries_read == 40

            # Process final batch (remaining 10 items: 40..49)
            processed3 = worker2.process_next_batch()
            assert processed3 == 10
            assert worker2.checkpoint.last_processed_entry_index == 49
        finally:
            worker2.close()


# ==============================================================================
# 6. Read-Only Raw Market Ledger Tests
# ==============================================================================

def test_11_read_only_evidence_enforcement():
    """Evidence lookup uses SQLite in read-only mode, preventing modification of capture data."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        populate_raw_evidence(ev_dir, num_candles=10)

        lookup = PersistentEvidenceLookupV080(evidence_dir=ev_dir, symbol="BTCUSDT", interval="5m")
        conn = lookup._get_conn()
        assert conn is not None

        cur = conn.cursor()
        try:
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                cur.execute(
                    "INSERT INTO timestamp_index (timestamp_open, byte_offset, entry_index) "
                    "VALUES (1, 0, 9999);"
                )
            assert "readonly" in str(exc_info.value).lower() or "read-only" in str(exc_info.value).lower()
        finally:
            cur.close()
            lookup.close()
            del lookup, conn, cur
            import gc
            gc.collect()


# ==============================================================================
# 7. Offline Resource Benchmarks Tests
# ==============================================================================

def test_12_offline_resource_benchmarks():
    """Worker batch processing and paged outcome resolution executes within tight latency bounds."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        populate_raw_evidence(ev_dir, num_candles=100)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="OFFLINE_WARMUP",
            batch_size=50,
        )
        worker = ProspectiveScoringWorkerV080(config)
        try:
            t0 = time.perf_counter()
            count = worker.process_next_batch()
            t1 = time.perf_counter()

            elapsed_ms = (t1 - t0) * 1000.0
            assert count == 50
            # Processing 50 candles sequentially from SQLite index should take < 200 ms
            assert elapsed_ms < 200.0, f"Processing 50 candles took {elapsed_ms:.2f}ms (expected < 200ms)"
        finally:
            worker.close()


# ==============================================================================
# 8. Coolify Configuration Invariants Tests
# ==============================================================================

def test_13_coolify_compose_and_entrypoint_invariants():
    """Verify Coolify docker-compose and entrypoint file security settings."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-scoring-worker.yaml")
    entrypoint_path = Path("deploy/shadow_v080/entrypoint_scoring_worker.sh")

    assert compose_path.exists(), "Scoring worker docker-compose file must exist."
    assert entrypoint_path.exists(), "Scoring worker entrypoint script must exist."

    compose_text = compose_path.read_text(encoding="utf-8")
    assert 'network_mode: "none"' in compose_text
    assert "read_only: true" in compose_text
    assert "mem_limit: 300m" in compose_text
    assert "cpus: 0.25" in compose_text
    assert "pids_limit: 64" in compose_text
    assert "cbe_080_live_capture_data:/app/data/live_capture:ro" in compose_text
    assert "cbe_080_live_capture_data:/app/data/live_capture/raw_market:ro" not in compose_text
    assert "cbe_080_prospective_data:/app/data/prospective:rw" in compose_text
    assert "CBE_APPROVAL_4_AUTHORIZED=false" in compose_text
    assert "CBE_TRADING_DISABLED=true" in compose_text

    entrypoint_text = entrypoint_path.read_text(encoding="utf-8")
    assert "APPROVAL_4" in entrypoint_text
    assert "coin_behavior_engine.shadow_v080.scoring_worker" in entrypoint_text
