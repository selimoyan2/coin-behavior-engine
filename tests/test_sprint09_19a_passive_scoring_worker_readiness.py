"""Sprint 09.19A: Passive Scoring Worker Deployment Readiness Audit Tests.

Verifies:
1. Docker Compose volume identity mapping: cbe_080_live_capture_data -> zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data.
2. Mount path alignment: /app/data/live_capture:ro with raw_market subpath.
3. Passive observation mode safety: zero model inference, zero predictions emitted, zero outcomes fabricated.
4. Read-only evidence health reporting (warmup status, continuous count, store stats).
5. Fail-closed startup on unauthorized configurations (trading enabled, live mode without auth, contradictory flags).
6. Immutable start boundary retroactive scoring protection: past passive candles cannot be retroactively scored.
7. Read-only SQLite evidence connection enforcement (PRAGMA query_only / mode=ro).
8. Resource ceilings (memory <= 300M, cpu <= 0.25, pids <= 64, network_mode: none).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml

from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
)
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    MarketType,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.prospective_guard import (
    ExecutionBoundary,
    ProspectiveAuthorizationError,
    ProspectiveAuthorizationGuard,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    MarketEvidenceEntry,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.scoring_worker import (
    ProspectiveScoringWorkerV080,
    VALID_RUN_MODES,
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
        volume=f"{(100.0 + 50.0 * math.sin(index / 7.0)):.4f}",
        quote_volume="6500000.00",
        trades_count=200,
        taker_buy_base_volume="7.5",
        is_closed=is_closed,
        provenance="LIVE_BINANCE_SPOT",
        receipt_timestamp_utc=dt_close,
    )


def populate_raw_evidence(
    raw_dir: Path,
    num_candles: int = 300,
    start_ts_open: int = 1770000000000,
) -> List[ValidatedCandle]:
    quarantine_dir = raw_dir.parent / "quarantine"
    store = RawMarketEvidenceStore(
        raw_market_dir=raw_dir,
        quarantine_dir=quarantine_dir,
        symbol="BTCUSDT",
        interval="5m",
    )
    candles = [make_test_candle(i, start_ts_open=start_ts_open) for i in range(num_candles)]
    for c in candles:
        store.append_candle(c)
    store.close()
    return candles


# ==============================================================================
# 1. Volume Identity & Mount Path Alignment Audit
# ==============================================================================

def test_01_compose_volume_identity_and_path_mapping():
    """Verify Docker Compose volume identity mapping and mount paths."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-scoring-worker.yaml")
    assert compose_path.exists(), "Scoring worker compose file must exist."

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    # 1. Check external volume declaration
    volumes = compose_cfg.get("volumes", {})
    assert "cbe_080_live_capture_data" in volumes
    live_vol_def = volumes["cbe_080_live_capture_data"]
    assert live_vol_def.get("external") is True
    assert "name" in live_vol_def
    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in live_vol_def["name"]

    # 2. Check service mount paths
    svc = compose_cfg["services"]["cbe-080-scoring-worker"]
    svc_volumes = svc.get("volumes", [])
    
    # Must mount live capture volume read-only at /app/data/live_capture/raw_market
    live_mount = [v for v in svc_volumes if "cbe_080_live_capture_data" in v]
    assert len(live_mount) == 1
    assert live_mount[0] == "cbe_080_live_capture_data:/app/data/live_capture/raw_market:ro"

    # Must mount scoring volume read-write at /app/data/prospective
    scoring_mount = [v for v in svc_volumes if "cbe_080_prospective_data" in v]
    assert len(scoring_mount) == 1
    assert scoring_mount[0] == "cbe_080_prospective_data:/app/data/prospective:rw"

    # 3. Check environment path alignment
    env_vars = {}
    for item in svc.get("environment", []):
        if "=" in item:
            k, v = item.split("=", 1)
            env_vars[k] = v

    assert env_vars.get("CBE_RAW_MARKET_DIR") == "/app/data/live_capture/raw_market"
    assert env_vars.get("CBE_PROSPECTIVE_DIR") == "/app/data/prospective"
    assert env_vars.get("CBE_RUN_MODE") == "PASSIVE_OBSERVATION"
    assert env_vars.get("CBE_APPROVAL_4_AUTHORIZED") == "false"
    assert env_vars.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"
    assert env_vars.get("CBE_TRADING_DISABLED") == "true"


# ==============================================================================
# 2. Passive Observation Mode Safety & Zero Inference
# ==============================================================================

def test_02_passive_mode_safety_and_zero_inference():
    """Passive mode ingests evidence and updates warmup buffer without emitting predictions or resolving outcomes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=300)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PASSIVE_OBSERVATION",
            batch_size=100,
            env={
                "CBE_TRADING_DISABLED": "true",
                "CBE_APPROVAL_4_AUTHORIZED": "false",
                "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            },
        )
        worker = ProspectiveScoringWorkerV080(config)

        try:
            # Process all 300 candles in batches of 100
            p1 = worker.process_next_batch()
            p2 = worker.process_next_batch()
            p3 = worker.process_next_batch()
            p4 = worker.process_next_batch()

            assert p1 == 100
            assert p2 == 100
            assert p3 == 100
            assert p4 == 0  # No more new entries

            # Invariants verification
            assert worker.checkpoint.total_entries_read == 300
            assert worker.checkpoint.last_processed_entry_index == 299
            assert worker.checkpoint.total_predictions_emitted == 0
            assert worker.checkpoint.total_outcomes_resolved == 0
            assert worker.checkpoint.pending_predictions_count == 0
            assert worker.checkpoint.total_warmup_bars_buffered >= 288

            # No start boundary file created
            assert not (prosp_dir / "authorized_start_boundary.json").exists()

            # Prediction store must be completely empty
            assert worker.prediction_store.get_pending_count() == 0

        finally:
            worker.close()


def test_03_evidence_health_report():
    """Worker provides read-only evidence health and continuous warmup telemetry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=295)

        config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PASSIVE_OBSERVATION",
            batch_size=300,
        )
        worker = ProspectiveScoringWorkerV080(config)

        try:
            worker.process_next_batch()
            report = worker.get_evidence_health_report()

            assert report["run_mode"] == "PASSIVE_OBSERVATION"
            assert report["warmup_ready"] is True
            assert report["buffered_bars"] == 295
            assert report["min_warmup_bars"] == 288
            assert "Full warmup satisfied" in report["status_message"]
            assert report["last_processed_entry_index"] == 294
            assert report["latest_evidence_candle_timestamp_ms"] == candles[-1].timestamp_open
            assert report["start_boundary_established"] is False
            assert report["authorized_start_boundary_ts_ms"] is None
            assert report["total_predictions_emitted"] == 0
            assert report["total_outcomes_resolved"] == 0
            assert report["pending_predictions_count"] == 0

        finally:
            worker.close()


# ==============================================================================
# 3. Fail-Closed Startup Invariants
# ==============================================================================

def test_04_fail_closed_on_unauthorized_startup():
    """Worker refuses initialization on unsafe or unauthorized configurations."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        populate_raw_evidence(ev_dir, num_candles=10)

        # 1. Trading enabled -> Fail closed
        with pytest.raises(ProspectiveAuthorizationError, match="Trading is prohibited"):
            ProspectiveScoringWorkerV080(
                WorkerConfigV080(
                    evidence_dir=ev_dir,
                    prospective_dir=prosp_dir,
                    env={"CBE_TRADING_DISABLED": "false"},
                )
            )

        # 2. PROSPECTIVE_LIVE boundary establishment without Approval 4 -> Fail closed
        w_live = ProspectiveScoringWorkerV080(
            WorkerConfigV080(
                evidence_dir=ev_dir,
                prospective_dir=prosp_dir,
                run_mode="PROSPECTIVE_LIVE",
                env={
                    "CBE_TRADING_DISABLED": "true",
                    "CBE_APPROVAL_4_AUTHORIZED": "false",
                    "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
                },
            )
        )
        try:
            with pytest.raises(ProspectiveAuthorizationError):
                w_live.establish_start_boundary()
        finally:
            w_live.close()

        # 3. Invalid run_mode -> Fail closed with ValueError
        with pytest.raises(ValueError, match="Invalid run_mode"):
            WorkerConfigV080(
                evidence_dir=ev_dir,
                prospective_dir=prosp_dir,
                run_mode="ARBITRARY_UNAUTHORIZED_MODE",
            )


# ==============================================================================
# 4. Retroactive Scoring Protection Audit
# ==============================================================================

def test_05_retroactive_scoring_protection_after_passive_period():
    """Past candles closed during passive operation CANNOT be retroactively scored upon future authorization."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        prosp_dir = tmp_path / "prospective"
        candles = populate_raw_evidence(ev_dir, num_candles=300)

        # Step 1: Worker runs passively through all 300 candles
        passive_config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PASSIVE_OBSERVATION",
            batch_size=350,
            env={
                "CBE_TRADING_DISABLED": "true",
                "CBE_APPROVAL_4_AUTHORIZED": "false",
                "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            },
        )
        worker = ProspectiveScoringWorkerV080(passive_config)
        try:
            worker.process_next_batch()
            assert worker.checkpoint.last_processed_entry_index == 299
            assert worker.checkpoint.total_predictions_emitted == 0
        finally:
            worker.close()

        # Step 2: Simulate future Gate 4 authorization at candle 299 close timestamp
        auth_env = {
            "CBE_TRADING_DISABLED": "true",
            "CBE_APPROVAL_4_AUTHORIZED": "true",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "true",
        }
        live_config = WorkerConfigV080(
            evidence_dir=ev_dir,
            prospective_dir=prosp_dir,
            run_mode="PROSPECTIVE_LIVE",
            batch_size=350,
            env=auth_env,
        )
        live_worker = ProspectiveScoringWorkerV080(live_config)
        try:
            # Establish start boundary at current latest candle close
            boundary_rec = live_worker.establish_start_boundary(
                git_commit="audit_test_commit_sha",
            )
            assert boundary_rec.authorized_start_boundary_ts_ms >= candles[-1].timestamp_close

            # Step 3: Malicious replay attempt - rewind checkpoint to entry 0
            live_worker.checkpoint.last_processed_entry_index = -1
            live_worker.checkpoint.last_processed_candle_timestamp_ms = 0
            live_worker._recent_candles = []

            # Re-process all 300 historical candles
            processed = live_worker.process_next_batch()
            assert processed == 300

            # CRITICAL INVARIANT: Zero predictions emitted because all 300 candles closed <= boundary_ts
            assert live_worker.checkpoint.total_predictions_emitted == 0
            assert live_worker.prediction_store.get_pending_count() == 0

        finally:
            live_worker.close()


# ==============================================================================
# 5. Read-Only Evidence SQLite Protection Audit
# ==============================================================================

def test_06_evidence_sqlite_read_only_protection():
    """PersistentEvidenceLookupV080 uses query_only / read-only SQLite connections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        ev_dir = tmp_path / "evidence"
        populate_raw_evidence(ev_dir, num_candles=50)

        lookup = PersistentEvidenceLookupV080(
            raw_market_dir=ev_dir,
            symbol="BTCUSDT",
            interval="5m",
        )
        try:
            conn = lookup._get_conn()
            assert conn is not None

            # Attempt a write operation -> Must raise OperationalError
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("CREATE TABLE malicious_test (id INT);")

        finally:
            lookup.close()


# ==============================================================================
# 6. Compose Resource Ceiling Audit
# ==============================================================================

def test_07_compose_resource_limits_and_security_profile():
    """Verify compose resource constraints conform to strict VPS safety quotas."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-scoring-worker.yaml")
    with open(compose_path, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    svc = compose_cfg["services"]["cbe-080-scoring-worker"]

    # Resource limits
    assert svc.get("mem_limit") == "300m"
    assert svc.get("memswap_limit") == "300m"
    assert svc.get("cpus") <= 0.25
    assert svc.get("pids_limit") <= 64

    # Network isolation
    assert svc.get("network_mode") == "none"
    assert "ports" not in svc

    # Security options
    assert svc.get("read_only") is True
    assert svc.get("user") == "1000:1000"
    assert "ALL" in svc.get("cap_drop", [])
    assert "no-new-privileges:true" in svc.get("security_opt", [])

    # Logging limits
    log_cfg = svc.get("logging", {})
    assert log_cfg.get("driver") == "json-file"
    assert log_cfg.get("options", {}).get("max-size") == "10m"
    assert int(log_cfg.get("options", {}).get("max-file")) <= 3
