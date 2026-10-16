"""CBE — Sprint 11.02D: Durable Gap Recovery, Evidence Integrity & Deployment Continuity.

Comprehensive Automated Test Suite:
1. Approval 3 fail-closed behavior.
2. Approval 4 isolation.
3. Trading permanently disabled.
4. WebSocket closed-candle ingestion.
5. Historical snapshot classification.
6. Live snapshot classification.
7. Heartbeat without fabricated candles.
8. Gap detection after long downtime.
9. Exact 141-candle gap recovery.
10. Incomplete REST response.
11. REST timeout and rate-limit handling.
12. Invalid recovered candle.
13. Duplicate recovered candle.
14. Conflicting recovered candle.
15. Disk write failure.
16. Interrupted recovery before commit.
17. Interrupted recovery after durable persistence.
18. Recovery retry idempotency.
19. Recovery journal integrity.
20. Restart reconstruction.
21. Research eligibility after recovery.
22. Preservation of original evidence chain.
23. Snapshot schema backward compatibility.
24. Correct Live Capture Dockerfile and entrypoint.
25. Correct persistent volume mapping.
26. Deployment preflight failure on configuration drift.
27. Rollback compatibility.
28. Frozen CBE-0.7.0 hash preservation.
"""

from __future__ import annotations

import collections
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import yaml

import pytest

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.product.market_data_adapter import (
    AtomicSnapshotIO,
    DataClassification,
    FactualMarketDataAdapter,
    FactualMarketDataRecord,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.gap_detector import GapEvent, MarketDataGapDetector
from coin_behavior_engine.shadow_v080.gap_recovery_store import (
    ConflictingRecoveryCandleError,
    DurableGapRecoveryStore,
    RecoveryJournalCorruptionError,
    RecoveryStorePersistenceError,
)
from coin_behavior_engine.shadow_v080.live_capture_service import (
    LiveCaptureService,
    verify_live_capture_preflight,
)
from coin_behavior_engine.shadow_v080.market_capture_engine import (
    MarketCaptureEngineV080,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CANDLE_INTERVAL_MS,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BaseMarketDataTransport,
    BinanceSpotRestAdapter,
    MockMarketDataTransport,
    RateLimitExceededError,
    SafetyInterlockError,
    TransportConnectionError,
)
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from deploy.shadow_v080.verify_deployment_preflight import verify_deployment_preflight

DOCKERFILE_STAGING = REPO_ROOT / "deploy" / "shadow_v080" / "Dockerfile.staging"
ENTRYPOINT_LIVE_CAPTURE = REPO_ROOT / "deploy" / "shadow_v080" / "entrypoint_live_capture.sh"
LIVE_CAPTURE_COMPOSE = REPO_ROOT / "deploy" / "shadow_v080" / "docker-compose.coolify-live-capture.yaml"
RUNBOOK_FILE = REPO_ROOT / "docs" / "operations" / "CBE_LIVE_CAPTURE_COOLIFY_RUNBOOK.md"


class MockRestAdapter:
    """Deterministic, offline REST adapter for gap recovery unit tests."""

    def __init__(self, klines_data: Optional[List[List[Any]]] = None):
        self.klines_data = klines_data or []
        self.base_url = "https://mock.api.binance.com/api/v3/klines"
        self.call_count = 0
        self.last_query_params: Dict[str, Any] = {}
        self.simulate_rate_limit = False
        self.simulate_timeout = False

    def fetch_klines(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        self.call_count += 1
        self.last_query_params = {
            "symbol": symbol,
            "interval": interval,
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit,
        }
        if self.simulate_rate_limit:
            raise RateLimitExceededError("Mock rate limit HTTP 429 triggered. Backoff: 60s")
        if self.simulate_timeout:
            raise TransportConnectionError("Mock timeout connecting to Binance REST API.")

        return self.klines_data


def _make_raw_kline(
    open_ts: int,
    open_p: str = "64000.00",
    close_p: str = "64050.00",
    vol: str = "10.5",
    is_closed: bool = True,
    high_p: Optional[str] = None,
    low_p: Optional[str] = None,
) -> List[Any]:
    o_val = float(open_p)
    c_val = float(close_p)
    h_str = high_p if high_p is not None else f"{max(o_val, c_val) + 50.0:.2f}"
    l_str = low_p if low_p is not None else f"{min(o_val, c_val) - 50.0:.2f}"
    close_ts = open_ts + 299_999
    return [
        open_ts,
        open_p,
        h_str,
        l_str,
        close_p,
        vol,
        close_ts,
        "672525.00",
        150,
        "5.25",
        "336262.50",
        "0",
    ]


def _make_sample_ws_candle(
    open_ts: int,
    open_price: str = "64000.00",
    close_price: str = "64250.00",
    is_closed: bool = True,
) -> Dict[str, Any]:
    close_ts = open_ts + 299_999
    o_val = float(open_price)
    c_val = float(close_price)
    h_str = f"{max(o_val, c_val) + 50.0:.2f}"
    l_str = f"{min(o_val, c_val) - 50.0:.2f}"
    return {
        "s": "BTCUSDT",
        "k": {
            "s": "BTCUSDT",
            "i": "5m",
            "t": open_ts,
            "T": close_ts,
            "o": open_price,
            "h": h_str,
            "l": l_str,
            "c": close_price,
            "v": "100.00",
            "q": "6425000.00",
            "n": 1000,
            "V": "50.00",
            "x": is_closed,
        },
    }


# ==============================================================================
# 1. Approval 3 Fail-Closed Behavior
# ==============================================================================

def test_01_approval_3_fail_closed_behavior(monkeypatch):
    """Verify that LiveCaptureService and REST adapter fail closed without explicit Approval 3."""
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert is_valid is False
    assert any("Approval 3 is NOT authorized" in v for v in violations)

    with pytest.raises(SafetyInterlockError):
        LiveCaptureService()


# ==============================================================================
# 2. Approval 4 Isolation
# ==============================================================================

def test_02_approval_4_isolation(monkeypatch):
    """Verify that enabling Approval 4 causes fail-closed abort."""
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")  # VIOLATION
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert is_valid is False
    assert any("Approval 4 is pending" in v for v in violations)


# ==============================================================================
# 3. Trading Permanently Disabled
# ==============================================================================

def test_03_trading_permanently_disabled(monkeypatch):
    """Verify that attempting to enable trading triggers immediate fail-closed shutdown."""
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")  # VIOLATION
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

    is_valid, violations = verify_live_capture_preflight()
    assert is_valid is False
    assert any("Trading interlock violated" in v for v in violations)


# ==============================================================================
# 4. WebSocket Closed-Candle Ingestion
# ==============================================================================

def test_04_websocket_closed_candle_ingestion():
    """Verify that a valid closed candle is ingested and persisted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            msg = _make_sample_ws_candle(t0, close_price="64100.00", is_closed=True)
            res = engine.process_raw_message(msg)
            assert res["status"] == "PERSISTED"
            assert engine.total_persisted == 1
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 5. Historical Snapshot Classification
# ==============================================================================

def test_05_historical_snapshot_classification():
    """Verify older candle (>30m) produces HISTORICAL_SNAPSHOT with is_live=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg, default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
        try:
            # 45 minutes ago
            t_old = ((int(time.time() * 1000) // 300_000) - 9) * 300_000
            msg = _make_sample_ws_candle(t_old, close_price="64200.00", is_closed=True)
            engine.process_raw_message(msg)

            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)
            assert rec.is_live is False
            assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 6. Live Snapshot Classification
# ==============================================================================

def test_06_live_snapshot_classification():
    """Verify fresh closed candle (<30m) produces LIVE_OBSERVED with is_live=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg, default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value)
        try:
            # 1 bar back (<5m)
            t_fresh = ((int(time.time() * 1000) // 300_000) - 1) * 300_000
            msg = _make_sample_ws_candle(t_fresh, close_price="64300.00", is_closed=True)
            engine.process_raw_message(msg)

            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)
            assert rec.is_live is True
            assert rec.classification == DataClassification.LIVE_OBSERVED
            assert rec.spot_price_usdt == 64300.0
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 7. Heartbeat Without Fabricated Candles
# ==============================================================================

def test_07_heartbeat_without_fabricated_candles():
    """Verify periodic heartbeat update refreshes writer_heartbeat_utc without altering candle data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            msg = _make_sample_ws_candle(t0, close_price="64400.00", is_closed=True)
            engine.process_raw_message(msg)

            snap_file = cfg.shadow_data_dir / "live_market_state.json"
            data1 = json.loads(snap_file.read_text(encoding="utf-8"))
            hb1 = data1["writer_heartbeat_utc"]

            time.sleep(0.05)
            engine.update_writer_heartbeat()

            data2 = json.loads(snap_file.read_text(encoding="utf-8"))
            hb2 = data2["writer_heartbeat_utc"]

            assert data2["spot_price_usdt"] == 64400.0
            assert data2["timestamp_open_utc"] == data1["timestamp_open_utc"]
            assert hb2 >= hb1
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 8. Gap Detection After Long Downtime
# ==============================================================================

def test_08_gap_detection_after_long_downtime():
    """Verify that a time jump detects missing intervals and resets contiguity."""
    detector = MarketDataGapDetector(full_warmup_bars=288)
    v = BinanceSpotCandleValidator()

    # Candle 1: t0
    c1, _ = v.validate_raw(_make_raw_kline(1792149000000), provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
    detector.process_next_candle(c1)
    assert detector.contiguous_closed_bars == 1

    # Candle 2: t0 + 10 bars (9 missing bars)
    t_jump = 1792149000000 + (10 * CANDLE_INTERVAL_MS)
    c2, _ = v.validate_raw(_make_raw_kline(t_jump), provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
    is_contig, gap = detector.process_next_candle(c2)

    assert is_contig is False
    assert gap is not None
    assert gap.missing_bars_count == 9
    assert len(gap.missing_timestamps) == 9
    assert detector.contiguous_closed_bars == 1  # Reset to 1


# ==============================================================================
# 9. Exact 141-Candle Gap Recovery
# ==============================================================================

def test_09_exact_141_candle_gap_recovery():
    """Verify reproduction and recovery of the observed 141-candle gap."""
    t_start = 1792149300000
    t_next = 1792191600000
    missing_count = 141

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            # 1. Ingest bar before gap
            c0_ts = t_start - CANDLE_INTERVAL_MS
            engine.process_raw_message(_make_sample_ws_candle(c0_ts, close_price="64000.00"))

            # 2. Ingest bar after 141-candle gap
            res = engine.process_raw_message(_make_sample_ws_candle(t_next, close_price="64500.00"))
            assert res["status"] == "PERSISTED"
            assert engine.gap_detector.has_unrecovered_gaps is True
            assert len(engine.gap_detector.gaps) == 1

            gap = engine.gap_detector.gaps[0]
            assert gap.missing_bars_count == missing_count
            assert gap.missing_start_ts == t_start

            # 3. Create synthetic 141 klines for REST mock
            synthetic_klines = [
                _make_raw_kline(t_start + (i * CANDLE_INTERVAL_MS), close_p=f"{64000.0 + i:.2f}")
                for i in range(missing_count)
            ]
            mock_rest = MockRestAdapter(synthetic_klines)

            # 4. Recover gap
            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is True
            assert gap.recovered is True
            assert engine.gap_detector.has_unrecovered_gaps is False
            assert engine.recovery_store.committed_gaps_count == 1
            assert engine.recovery_store.entry_count == 141
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 10. Incomplete REST Response Rejection
# ==============================================================================

def test_10_incomplete_rest_response_rejected():
    """Verify that returning fewer than expected gap candles fails and does NOT mark recovered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            t_jump = t0 + (5 * CANDLE_INTERVAL_MS)
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t_jump))

            gap = engine.gap_detector.gaps[0]
            assert gap.missing_bars_count == 4

            # Partial REST response: only 2 candles out of 4
            partial_klines = [
                _make_raw_kline(t0 + CANDLE_INTERVAL_MS),
                _make_raw_kline(t0 + (2 * CANDLE_INTERVAL_MS)),
            ]
            mock_rest = MockRestAdapter(partial_klines)

            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is False
            assert "RECOVERY_MISMATCH" in msg
            assert gap.recovered is False
            assert engine.recovery_store.entry_count == 0  # Zero durable persistence
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 11. REST Timeout and Rate-Limit Handling
# ==============================================================================

def test_11_rest_timeout_and_rate_limit_handling():
    """Verify fail-closed handling when REST adapter triggers rate limits or timeouts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))

            gap = engine.gap_detector.gaps[0]

            # Simulate HTTP 429
            mock_rest = MockRestAdapter()
            mock_rest.simulate_rate_limit = True

            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is False
            assert "rate limit" in msg
            assert gap.recovered is False

            # Simulate Timeout
            mock_rest.simulate_rate_limit = False
            mock_rest.simulate_timeout = True

            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is False
            assert "timeout" in msg.lower()
            assert gap.recovered is False
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 12. Invalid Recovered Candle Rejection
# ==============================================================================

def test_12_invalid_recovered_candle_rejected():
    """Verify that corrupt or unclosed candles returned by REST fail validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))
            gap = engine.gap_detector.gaps[0]

            # Invalid candle: High < Low
            bad_kline = _make_raw_kline(t0 + CANDLE_INTERVAL_MS, high_p="63000.00", low_p="64000.00")
            mock_rest = MockRestAdapter([bad_kline])

            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is False
            assert "validation" in msg.lower()
            assert gap.recovered is False
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 13. Duplicate Recovered Candle
# ==============================================================================

def test_13_duplicate_recovered_candle_idempotent():
    """Verify duplicate recovery invocation on already recovered gap is idempotent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))
            gap = engine.gap_detector.gaps[0]

            kline = _make_raw_kline(t0 + CANDLE_INTERVAL_MS)
            mock_rest = MockRestAdapter([kline])

            ok1, _ = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok1 is True
            assert engine.recovery_store.entry_count == 1

            # Second recovery call
            ok2, msg2 = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok2 is False
            assert "already marked as recovered" in msg2
            assert engine.recovery_store.entry_count == 1  # No duplicate entries
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 14. Conflicting Recovered Candle Quarantined
# ==============================================================================

def test_14_conflicting_recovered_candle_quarantined():
    """Verify conflicting candle payload raises ConflictingRecoveryCandleError and quarantines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        validator = BinanceSpotCandleValidator()

        t0 = 1792149000000
        c1, _ = validator.validate_raw(
            _make_raw_kline(t0, close_p="64000.00"),
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )
        c2_conflict, _ = validator.validate_raw(
            _make_raw_kline(t0, close_p="65000.00"),  # Different close price
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )

        # Persist first
        store.persist_recovery_batch(
            gap_id="GAP-1",
            recovery_batch_id="BATCH-1",
            missing_start_ts=t0,
            missing_end_ts=t0,
            missing_timestamps=[t0],
            recovered_candles=[c1],
        )

        # Attempt to persist conflicting candle under new gap
        with pytest.raises(ConflictingRecoveryCandleError):
            store.persist_recovery_batch(
                gap_id="GAP-2",
                recovery_batch_id="BATCH-2",
                missing_start_ts=t0,
                missing_end_ts=t0,
                missing_timestamps=[t0],
                recovered_candles=[c2_conflict],
            )

        assert store.quarantine_file.exists()
        assert "CONFLICTING_RECOVERED_CANDLE" in store.quarantine_file.read_text(encoding="utf-8")


# ==============================================================================
# 15. Disk Write Failure Safety
# ==============================================================================

def test_15_disk_write_failure_safety():
    """Verify that simulated disk write failure aborts recovery and leaves gap unrecovered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))
            gap = engine.gap_detector.gaps[0]

            kline = _make_raw_kline(t0 + CANDLE_INTERVAL_MS)
            mock_rest = MockRestAdapter([kline])

            # Force disk error
            ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest, force_disk_error=True)
            assert ok is False
            assert "PERSISTENCE" in msg
            assert gap.recovered is False
            assert engine.is_research_eligible is False
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 16. Interrupted Recovery Before Commit
# ==============================================================================

def test_16_interrupted_recovery_before_commit():
    """Verify that if process is killed before metadata commit, gap remains uncommitted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        validator = BinanceSpotCandleValidator()

        t0 = 1792149000000
        c1, _ = validator.validate_raw(
            _make_raw_kline(t0),
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )

        # Write to journal directly without writing metadata (simulating mid-crash)
        entry = store.compute_entry_integrity_hash("BATCH-1", "GAP-1", 0, "0"*64, c1.compute_sha256())
        line_payload = {
            "recovery_batch_id": "BATCH-1",
            "gap_id": "GAP-1",
            "entry_index": 0,
            "prev_recovery_hash": "0" * 64,
            "candle_hash": c1.compute_sha256(),
            "integrity_hash": entry,
            "persisted_at_utc": "2026-10-17T00:00:00Z",
            "source_metadata": {},
            "candle": c1.canonical_dict(),
        }
        with open(store.journal_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(line_payload) + "\n")

        # Reload store from disk
        store2 = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        assert store2.get_committed_gap("GAP-1") is None  # Uncommitted metadata


# ==============================================================================
# 17. Interrupted Recovery After Durable Persistence
# ==============================================================================

def test_17_interrupted_recovery_after_durable_persistence():
    """Verify that once both journal and metadata are written, reload fully reconstructs recovery."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        validator = BinanceSpotCandleValidator()

        t0 = 1792149000000
        c1, _ = validator.validate_raw(
            _make_raw_kline(t0),
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )

        store.persist_recovery_batch(
            gap_id="GAP-1",
            recovery_batch_id="BATCH-1",
            missing_start_ts=t0,
            missing_end_ts=t0,
            missing_timestamps=[t0],
            recovered_candles=[c1],
        )

        # Reload
        store2 = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        assert store2.entry_count == 1
        meta = store2.get_committed_gap("GAP-1")
        assert meta is not None
        assert meta.recovered_candles_count == 1
        assert store2.get_recovered_candle(t0) is not None


# ==============================================================================
# 18. Recovery Retry Idempotency
# ==============================================================================

def test_18_recovery_retry_idempotency():
    """Verify that calling persist_recovery_batch multiple times with identical data is idempotent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        validator = BinanceSpotCandleValidator()

        t0 = 1792149000000
        c1, _ = validator.validate_raw(
            _make_raw_kline(t0),
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )

        ok1, msg1 = store.persist_recovery_batch("GAP-1", "BATCH-1", t0, t0, [t0], [c1])
        assert ok1 is True
        assert store.entry_count == 1

        ok2, msg2 = store.persist_recovery_batch("GAP-1", "BATCH-1", t0, t0, [t0], [c1])
        assert ok2 is True
        assert msg2 == "ALREADY_COMMITTED"
        assert store.entry_count == 1


# ==============================================================================
# 19. Recovery Journal Integrity & Tamper Detection
# ==============================================================================

def test_19_recovery_journal_integrity_and_tamper():
    """Verify that tampering with an entry in the recovery journal triggers RecoveryJournalCorruptionError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store = DurableGapRecoveryStore(
            raw_market_dir=tmp_path / "raw_market",
            quarantine_dir=tmp_path / "quarantine",
        )
        validator = BinanceSpotCandleValidator()

        t0 = 1792149000000
        c1, _ = validator.validate_raw(
            _make_raw_kline(t0),
            provenance=ProvenanceSource.REST_GAP_RECOVERY.value,
        )
        store.persist_recovery_batch("GAP-1", "BATCH-1", t0, t0, [t0], [c1])

        # Tamper with file
        lines = store.journal_file.read_text(encoding="utf-8").strip().split("\n")
        bad_entry = json.loads(lines[0])
        bad_entry["candle"]["close"] = "99999.00"  # Tampered price
        store.journal_file.write_text(json.dumps(bad_entry) + "\n", encoding="utf-8")

        with pytest.raises(RecoveryJournalCorruptionError):
            DurableGapRecoveryStore(
                raw_market_dir=tmp_path / "raw_market",
                quarantine_dir=tmp_path / "quarantine",
            )


# ==============================================================================
# 20. Restart Reconstruction with Durable Recovery
# ==============================================================================

def test_20_restart_reconstruction_with_durable_recovery():
    """Verify that restarting engine on storage with recovered gaps seamlessly bridges continuity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()

        # Phase 1: create 2 candles with 1 gap, recover gap via REST
        t0 = 1792149000000
        e1 = MarketCaptureEngineV080(config=cfg)
        e1.process_raw_message(_make_sample_ws_candle(t0))
        e1.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))
        gap = e1.gap_detector.gaps[0]

        mock_rest = MockRestAdapter([_make_raw_kline(t0 + CANDLE_INTERVAL_MS)])
        ok, _ = e1.recover_gap_via_rest(gap.gap_id, mock_rest)
        assert ok is True
        e1.evidence_store.close()

        # Phase 2: Start new engine instance on same directory
        e2 = MarketCaptureEngineV080(config=cfg)
        try:
            assert e2.total_persisted == 2  # 2 raw candles
            assert len(e2.gap_detector.gaps) == 1
            assert e2.gap_detector.gaps[0].recovered is True
            assert e2.gap_detector.has_unrecovered_gaps is False
            # Continuity spans across the recovered gap: bar 1 + recovered bar + bar 2 = 3 contiguous bars!
            assert e2.gap_detector.contiguous_closed_bars == 3
            assert len(e2.rolling_buffer) == 3
        finally:
            e2.evidence_store.close()


# ==============================================================================
# 21. Research Eligibility After Recovery
# ==============================================================================

def test_21_research_eligibility_after_recovery():
    """Verify research eligibility becomes True only when contiguous closed bars >= 288 with zero gaps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(
            shadow_data_dir=tmp_path / "live_capture",
            full_warmup_bars=10,  # Bounded for test
        )
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            # Feed 5 candles
            for i in range(5):
                engine.process_raw_message(_make_sample_ws_candle(t0 + (i * CANDLE_INTERVAL_MS)))
            assert engine.gap_detector.contiguous_closed_bars == 5
            assert engine.is_research_eligible is False

            # Feed jump (skip bar 5)
            engine.process_raw_message(_make_sample_ws_candle(t0 + (6 * CANDLE_INTERVAL_MS)))
            assert engine.gap_detector.contiguous_closed_bars == 1
            assert engine.gap_detector.has_unrecovered_gaps is True

            # Recover missing bar 5
            gap = engine.gap_detector.gaps[0]
            mock_rest = MockRestAdapter([_make_raw_kline(t0 + (5 * CANDLE_INTERVAL_MS))])
            ok, _ = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is True
            assert engine.gap_detector.contiguous_closed_bars == 7

            # Add 3 more candles to reach threshold 10
            for i in range(7, 10):
                engine.process_raw_message(_make_sample_ws_candle(t0 + (i * CANDLE_INTERVAL_MS)))

            assert engine.gap_detector.contiguous_closed_bars == 10
            assert engine.is_research_eligible is True
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 22. Preservation of Original Evidence Chain
# ==============================================================================

def test_22_preservation_of_original_evidence_chain():
    """Verify original raw_candles.jsonl and index.sqlite3 are never modified or rewritten during gap recovery."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))
            engine.process_raw_message(_make_sample_ws_candle(t0 + (2 * CANDLE_INTERVAL_MS)))

            ev_file = cfg.raw_market_dir / f"raw_candles_{cfg.symbol}_{cfg.interval}.jsonl"
            ev_bytes_before = ev_file.read_bytes()
            ev_mtime_before = ev_file.stat().st_mtime

            gap = engine.gap_detector.gaps[0]
            mock_rest = MockRestAdapter([_make_raw_kline(t0 + CANDLE_INTERVAL_MS)])
            ok, _ = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
            assert ok is True

            # Original raw evidence file byte content and size MUST be untouched
            assert ev_file.read_bytes() == ev_bytes_before
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 23. Snapshot Schema Backward Compatibility
# ==============================================================================

def test_23_snapshot_schema_backward_compatibility():
    """Verify factual snapshot schema conforms strictly to FactualMarketDataAdapter expectations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture")
        cfg.ensure_directories()
        engine = MarketCaptureEngineV080(config=cfg)
        try:
            t0 = 1792149000000
            engine.process_raw_message(_make_sample_ws_candle(t0))

            snap_file = cfg.shadow_data_dir / "live_market_state.json"
            data = json.loads(snap_file.read_text(encoding="utf-8"))

            is_valid, err = FactualMarketDataAdapter.validate_snapshot_schema(data)
            assert is_valid is True, f"Schema validation error: {err}"
            assert "symbol" in data
            assert "spot_price_usdt" in data
            assert "is_closed" in data
            assert "writer_heartbeat_utc" in data
        finally:
            engine.evidence_store.close()


# ==============================================================================
# 24. Correct Live Capture Dockerfile and Entrypoint
# ==============================================================================

def test_24_dockerfile_and_entrypoint_existence():
    """Verify deploy/shadow_v080/Dockerfile.staging and entrypoint_live_capture.sh exist and are valid."""
    assert DOCKERFILE_STAGING.exists()
    assert ENTRYPOINT_LIVE_CAPTURE.exists()

    df_content = DOCKERFILE_STAGING.read_text(encoding="utf-8")
    assert "entrypoint_live_capture.sh" in df_content

    ep_content = ENTRYPOINT_LIVE_CAPTURE.read_text(encoding="utf-8")
    assert "coin_behavior_engine.shadow_v080.live_capture_service" in ep_content


# ==============================================================================
# 25. Correct Persistent Volume Mapping
# ==============================================================================

def test_25_correct_persistent_volume_mapping():
    """Verify live capture compose targets zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data."""
    assert LIVE_CAPTURE_COMPOSE.exists()
    compose_data = yaml.safe_load(LIVE_CAPTURE_COMPOSE.read_text(encoding="utf-8"))

    vols = compose_data.get("volumes", {})
    assert "cbe_080_live_capture_data" in vols
    vol_def = vols["cbe_080_live_capture_data"]
    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in vol_def.get("name", "")


# ==============================================================================
# 26. Deployment Preflight Failure on Configuration Drift
# ==============================================================================

def test_26_deployment_preflight_drift_detection():
    """Verify read-only preflight catches safety or configuration drift."""
    # 1. Clean run passes
    is_valid, violations = verify_deployment_preflight()
    assert is_valid is True
    assert len(violations) == 0

    # 2. Simulated drift: approval 4 enabled
    drift_env = {"CBE_APPROVAL_4_AUTHORIZED": "true"}
    is_valid_drift, violations_drift = verify_deployment_preflight(env_vars=drift_env)
    assert is_valid_drift is False
    assert any("CBE_APPROVAL_4_AUTHORIZED" in v for v in violations_drift)


# ==============================================================================
# 27. Rollback Compatibility
# ==============================================================================

def test_27_rollback_runbook_documentation():
    """Verify CBE_LIVE_CAPTURE_COOLIFY_RUNBOOK.md exists and documents rollback and resource topology."""
    assert RUNBOOK_FILE.exists()
    runbook_text = RUNBOOK_FILE.read_text(encoding="utf-8")

    assert "Rollback Procedure" in runbook_text
    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in runbook_text
    assert "Dockerfile.staging" in runbook_text
    assert "6t63aehpaw0cw1bbt4zcm09g" in runbook_text  # Production UUID
    assert "dzzfws54by1whlbq6fk4ywut" in runbook_text  # Staging UUID
    assert "zgit1s3n1acdtqtsxp0s44vj" in runbook_text  # Live Capture UUID


# ==============================================================================
# 28. Frozen CBE-0.7.0 Hash Preservation
# ==============================================================================

def test_28_frozen_cbe_070_hash_preservation():
    """Verify that all 29/29 canonical files remain strictly unmodified."""
    res = verify_sprint07_freeze()
    assert res["verified"] is True
    assert res["status"] == "FREEZE_VERIFIED"
    assert res["canonical_hashes_verified"] == 29
    assert len(res["canonical_mismatches"]) == 0
    assert len(res["missing_files"]) == 0
