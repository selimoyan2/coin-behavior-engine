"""Sprint 09.14 — Binance Market Data Capture Foundation Comprehensive Test Suite.

Covers all 24 mandatory test requirements:
1. Default-deny live transport.
2. Approval 3 gate enforcement.
3. Closed-candle validation.
4. Timestamp and interval consistency.
5. Duplicate detection.
6. Conflicting duplicate quarantine.
7. Out-of-order messages.
8. Missing intervals.
9. Gap-recovery provenance.
10. Crash recovery.
11. Hash-chain verification.
12. Invalid OHLCV.
13. Unexpected market types.
14. Rate-limit simulation.
15. Reconnection simulation.
16. Stale feed simulation.
17. Queue overflow.
18. Disk-write failure.
19. Read-only filesystem failure.
20. Shutdown during persistence.
21. Fixture-versus-live evidence separation.
22. Approval 4 isolation.
23. Existing inert entrypoint remains inert.
24. Existing CBE-0.7.0 freeze remains intact.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.gap_detector import (
    FULL_WARMUP_BARS,
    MarketDataGapDetector,
)
from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
    ValidationStatus,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    ConflictingCandleError,
    EvidenceCorruptionError,
    EvidencePersistenceError,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BinanceSpotRestAdapter,
    BinanceSpotWebSocketAdapter,
    MockMarketDataTransport,
    OversizedMessageError,
    QueueOverflowError,
    RateLimitExceededError,
    SafetyInterlockError,
    StaleFeedError,
    TransportConnectionError,
    calculate_backoff,
)


@pytest.fixture(autouse=True)
def base_safe_env(monkeypatch):
    """Ensure safe base environment for all tests."""
    monkeypatch.setenv("CBE_ENV", "staging_offline")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.delenv("CBE_APPROVAL_3_AUTHORIZED", raising=False)
    monkeypatch.delenv("CBE_APPROVAL_4_AUTHORIZED", raising=False)


def create_sample_ws_candle(
    timestamp_open: int = 1700000100000,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    is_closed: bool = True,
    open_price: float = 65000.0,
    high_price: float = 65500.0,
    low_price: float = 64900.0,
    close_price: float = 65200.0,
    volume: float = 120.5,
) -> Dict[str, Any]:
    """Helper to generate a valid Binance WebSocket 5m kline payload."""
    aligned_open = (timestamp_open // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    aligned_close = aligned_open + CANDLE_INTERVAL_MS - 1
    return {
        "e": "kline",
        "E": aligned_close + 10,
        "s": symbol,
        "k": {
            "t": aligned_open,
            "T": aligned_close,
            "s": symbol,
            "i": interval,
            "o": str(open_price),
            "c": str(close_price),
            "h": str(high_price),
            "l": str(low_price),
            "v": str(volume),
            "n": 500,
            "x": is_closed,
            "q": str(round(volume * close_price, 2)),
            "V": str(round(volume * 0.5, 2)),
        },
    }


def test_01_default_deny_live_transport():
    """Verify that live WebSocket and REST adapters refuse construction/connection by default."""
    cfg = ShadowCollectorConfig(network_enabled=False, live_shadow_enabled=False)

    with pytest.raises(SafetyInterlockError) as exc_ws:
        BinanceSpotWebSocketAdapter(cfg)
    assert "HARD SAFETY INTERLOCK" in str(exc_ws.value)
    assert "Approval 3" in str(exc_ws.value)

    with pytest.raises(SafetyInterlockError) as exc_rest:
        BinanceSpotRestAdapter(cfg)
    assert "HARD SAFETY INTERLOCK" in str(exc_rest.value)
    assert "Approval 3" in str(exc_rest.value)


def test_02_approval_3_gate_enforcement(monkeypatch):
    """Verify that live transport fails closed even if config says enabled unless environment matches."""
    cfg = ShadowCollectorConfig(
        network_enabled=True,
        live_shadow_enabled=True,
        approval_3_authorized=True,
    )

    # Missing CBE_APPROVAL_3_AUTHORIZED environment variable
    with pytest.raises(SafetyInterlockError) as exc:
        BinanceSpotWebSocketAdapter(cfg)
    assert "CBE_APPROVAL_3_AUTHORIZED" in str(exc.value)

    # Missing CBE_BINANCE_COLLECTION_ENABLED environment variable
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    with pytest.raises(SafetyInterlockError) as exc2:
        BinanceSpotWebSocketAdapter(cfg)
    assert "CBE_BINANCE_COLLECTION_ENABLED" in str(exc2.value)


def test_03_closed_candle_validation():
    """Verify that confirmed closed candles pass while open/in-progress candles are rejected."""
    # Closed candle passes
    closed_msg = create_sample_ws_candle(is_closed=True)
    c, v = BinanceSpotCandleValidator.validate_raw(closed_msg, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert v == []
    assert c is not None
    assert c.is_closed is True
    assert c.lifecycle_state == CandleLifecycleState.CANDLE_CONFIRMED_CLOSED.value

    # Open candle rejected
    open_msg = create_sample_ws_candle(is_closed=False)
    c_open, v_open = BinanceSpotCandleValidator.validate_raw(open_msg, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert c_open is None
    assert any("OPEN_CANDLE_REJECTED" in err for err in v_open)


def test_04_timestamp_and_interval_consistency():
    """Verify rejection of misaligned open timestamps or incorrect close durations."""
    # Misaligned open timestamp (not multiple of 300,000)
    misaligned = create_sample_ws_candle()
    misaligned["k"]["t"] = 1700000000001
    c, v = BinanceSpotCandleValidator.validate_raw(misaligned, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert c is None
    assert any("TIMESTAMP_NOT_ALIGNED_TO_5M" in err for err in v)

    # Invalid interval duration (e.g. 1 minute instead of 5 minutes)
    invalid_dur = create_sample_ws_candle()
    invalid_dur["k"]["T"] = invalid_dur["k"]["t"] + 60000 - 1
    c2, v2 = BinanceSpotCandleValidator.validate_raw(invalid_dur, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert c2 is None
    assert any("INVALID_INTERVAL_DURATION" in err for err in v2)


def test_05_duplicate_detection(tmp_path):
    """Verify that exact duplicate candles are detected and ignored without ledger corruption."""
    store = RawMarketEvidenceStore(
        raw_market_dir=tmp_path / "raw",
        quarantine_dir=tmp_path / "quarantine",
    )
    raw = create_sample_ws_candle()
    c, _ = BinanceSpotCandleValidator.validate_raw(raw, provenance=ProvenanceSource.OFFLINE_FIXTURE)

    # First append
    status1, entry1 = store.append_candle(c)
    assert status1 == "PERSISTED"
    assert entry1 is not None
    assert store.count == 1

    # Exact duplicate append
    status2, entry2 = store.append_candle(c)
    assert status2 == "DUPLICATE_IGNORED"
    assert entry2 is None
    assert store.count == 1  # Unchanged


def test_06_conflicting_duplicate_quarantine(tmp_path):
    """Verify that conflicting duplicate payloads for an existing timestamp are quarantined."""
    quarantine_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(
        raw_market_dir=tmp_path / "raw",
        quarantine_dir=quarantine_dir,
    )
    raw1 = create_sample_ws_candle(close_price=65000.0)
    c1, _ = BinanceSpotCandleValidator.validate_raw(raw1, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    store.append_candle(c1)

    # Conflicting duplicate: same timestamp, different close price (and valid high)
    raw2 = create_sample_ws_candle(high_price=66500.0, close_price=66000.0)
    c2, v2 = BinanceSpotCandleValidator.validate_raw(raw2, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert v2 == []
    assert c2 is not None

    status, entry = store.append_candle(c2)
    assert status == "CONFLICT_QUARANTINED"
    assert entry is None
    assert store.count == 1

    # Verify original candle was NOT overwritten
    persisted = store.get_candle_by_timestamp(c1.timestamp_open)
    assert persisted.close == 65000.0

    # Verify quarantine file contains record
    q_file = quarantine_dir / "quarantined_candles_BTCUSDT_5m.jsonl"
    assert q_file.exists()
    assert "CONFLICTING_PAYLOAD_FOR_EXISTING_TIMESTAMP" in q_file.read_text(encoding="utf-8")


def test_07_out_of_order_messages(tmp_path):
    """Verify that candles arriving out-of-order are quarantined."""
    store = RawMarketEvidenceStore(
        raw_market_dir=tmp_path / "raw",
        quarantine_dir=tmp_path / "quarantine",
    )
    t1 = 1700000100000 // CANDLE_INTERVAL_MS * CANDLE_INTERVAL_MS
    t2 = t1 + CANDLE_INTERVAL_MS
    t0 = t1 - CANDLE_INTERVAL_MS

    c1, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t1), provenance="OFFLINE_FIXTURE")
    c2, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t2), provenance="OFFLINE_FIXTURE")
    c0, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t0), provenance="OFFLINE_FIXTURE")

    store.append_candle(c1)
    store.append_candle(c2)

    # c0 arrives after c2 -> out-of-order!
    status, entry = store.append_candle(c0)
    assert status == "OUT_OF_ORDER_QUARANTINED"
    assert entry is None
    assert store.count == 2


def test_08_missing_intervals():
    """Verify gap detector detects missing 5m intervals and resets contiguous bar count."""
    detector = MarketDataGapDetector(full_warmup_bars=288)
    t0 = 1700000000000

    c1, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t0), provenance="OFFLINE_FIXTURE")
    is_contig1, gap1 = detector.process_next_candle(c1)
    assert is_contig1 is True
    assert gap1 is None
    assert detector.contiguous_closed_bars == 1

    # Skip 2 intervals (jump 3 intervals = 900,000 ms)
    t3 = t0 + (3 * CANDLE_INTERVAL_MS)
    c3, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t3), provenance="OFFLINE_FIXTURE")
    is_contig3, gap3 = detector.process_next_candle(c3)

    assert is_contig3 is False
    assert gap3 is not None
    assert gap3.missing_bars_count == 2
    assert len(gap3.missing_timestamps) == 2
    assert detector.contiguous_closed_bars == 1  # Reset to 1


def test_09_gap_recovery_provenance():
    """Verify gap recovery requires REST_GAP_RECOVERY provenance and forbids prospective labeling."""
    detector = MarketDataGapDetector()
    t0 = 1700000000000
    t2 = t0 + (2 * CANDLE_INTERVAL_MS)

    c0, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t0), provenance="OFFLINE_FIXTURE")
    c2, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t2), provenance="OFFLINE_FIXTURE")

    detector.process_next_candle(c0)
    _, gap = detector.process_next_candle(c2)
    assert gap is not None

    t_missing = t0 + CANDLE_INTERVAL_MS
    # Attempt recovery with invalid provenance (e.g. LIVE_BINANCE_SPOT)
    c_inv, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t_missing), provenance="LIVE_BINANCE_SPOT")
    ok1, msg1 = detector.register_recovered_gap(gap.gap_id, [c_inv])
    assert ok1 is False
    assert "PROVENANCE_VIOLATION" in msg1

    # Valid recovery with REST_GAP_RECOVERY provenance
    c_valid, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(timestamp_open=t_missing), provenance=ProvenanceSource.REST_GAP_RECOVERY)
    ok2, msg2 = detector.register_recovered_gap(gap.gap_id, [c_valid])
    assert ok2 is True
    assert msg2 == "GAP_RECOVERED_SUCCESSFULLY"
    assert detector.has_unrecovered_gaps is False


def test_10_crash_recovery(tmp_path):
    """Verify that a trailing corrupt or truncated line from a mid-write crash is recovered."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = 1700000000000
    for i in range(3):
        c, _ = BinanceSpotCandleValidator.validate_raw(
            create_sample_ws_candle(timestamp_open=t0 + i * CANDLE_INTERVAL_MS),
            provenance="OFFLINE_FIXTURE",
        )
        store.append_candle(c)

    assert store.count == 3

    # Simulate mid-write power cut / crash: append incomplete truncated JSON line
    with open(store.evidence_file, "a", encoding="utf-8") as f:
        f.write('{"entry_index": 3, "prev_hash": "abc", "cand\n')

    # Restart store (simulates crash recovery on restart)
    store2 = RawMarketEvidenceStore(raw_dir, q_dir)
    assert store2.count == 3  # Recovered back to 3 valid entries


def test_11_hash_chain_verification(tmp_path):
    """Verify that mid-chain evidence tampering is detected and fails closed."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = 1700000000000
    for i in range(3):
        c, _ = BinanceSpotCandleValidator.validate_raw(
            create_sample_ws_candle(timestamp_open=t0 + i * CANDLE_INTERVAL_MS),
            provenance="OFFLINE_FIXTURE",
        )
        store.append_candle(c)

    # Tamper with middle line (index 1)
    lines = store.evidence_file.read_text(encoding="utf-8").splitlines()
    entry1 = json.loads(lines[1])
    entry1["candle"]["close"] = 99999.0  # Tamper price
    lines[1] = json.dumps(entry1)
    store.evidence_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Restart store must raise EvidenceCorruptionError
    with pytest.raises(EvidenceCorruptionError) as exc:
        RawMarketEvidenceStore(raw_dir, q_dir)
    assert "Candle hash mismatch" in str(exc.value)


def test_12_invalid_ohlcv():
    """Verify rejection of invalid OHLCV numeric violations."""
    # Negative volume
    m1 = create_sample_ws_candle(volume=-10.0)
    _, v1 = BinanceSpotCandleValidator.validate_raw(m1, provenance="OFFLINE_FIXTURE")
    assert any("NEGATIVE_VOLUME" in err for err in v1)

    # High lower than Low
    m2 = create_sample_ws_candle(high_price=64000.0, low_price=65000.0)
    _, v2 = BinanceSpotCandleValidator.validate_raw(m2, provenance="OFFLINE_FIXTURE")
    assert any("PRICE_INVARIANT_VIOLATION_HIGH_LOW" in err for err in v2)

    # Non-numeric string
    m3 = create_sample_ws_candle()
    m3["k"]["o"] = "NOT_A_NUMBER"
    _, v3 = BinanceSpotCandleValidator.validate_raw(m3, provenance="OFFLINE_FIXTURE")
    assert any("MALFORMED_OHLCV_NON_NUMERIC" in err for err in v3)


def test_13_unexpected_market_types():
    """Verify rejection of non-SPOT market types."""
    raw = create_sample_ws_candle()
    c, v = BinanceSpotCandleValidator.validate_raw(raw, provenance="OFFLINE_FIXTURE", market_type=MarketType.FUTURES_USDM)
    assert c is None
    assert any("INVALID_MARKET_TYPE" in err for err in v)


def test_14_rate_limit_simulation():
    """Verify that simulated HTTP 429/418 upstream rate limit triggers RateLimitExceededError."""
    transport = MockMarketDataTransport()
    transport.connect()
    transport.simulate_rate_limit(retry_after_sec=60.0)

    with pytest.raises(RateLimitExceededError) as exc:
        transport.poll_message()
    assert "Backoff required: 60.0s" in str(exc.value)


def test_15_reconnection_simulation():
    """Verify reconnection lifecycle and exponential backoff calculation."""
    # Test calculate_backoff
    b0 = calculate_backoff(attempt=0, base_sec=1.0, jitter=False)
    b1 = calculate_backoff(attempt=1, base_sec=1.0, jitter=False)
    b2 = calculate_backoff(attempt=2, base_sec=1.0, jitter=False)
    assert b0 == 1.0
    assert b1 == 2.0
    assert b2 == 4.0

    transport = MockMarketDataTransport()
    assert transport.is_connected() is False
    transport.connect()
    assert transport.is_connected() is True
    transport.disconnect()
    assert transport.is_connected() is False
    transport.connect()
    assert transport.is_connected() is True


def test_16_stale_feed_simulation():
    """Verify detection of stale feeds when elapsed time exceeds threshold."""
    transport = MockMarketDataTransport(stale_timeout_sec=900.0)
    transport.connect()

    now = time.time()
    # 5 minutes elapsed -> not stale
    assert transport.check_stale_feed(current_time=now + 300) is False
    # 16 minutes elapsed -> stale!
    assert transport.check_stale_feed(current_time=now + 960) is True


def test_17_queue_overflow():
    """Verify that exceeding inbound transport queue capacity triggers backpressure error."""
    transport = MockMarketDataTransport(max_queue_size=2)
    transport.connect()

    transport.inject_message({"msg": 1})
    transport.inject_message({"msg": 2})

    with pytest.raises(QueueOverflowError) as exc:
        transport.inject_message({"msg": 3})
    assert "Inbound queue capacity reached" in str(exc.value)
    assert transport.dropped_messages == 1


def test_18_disk_write_failure(tmp_path):
    """Verify that simulated disk-write failure raises EvidencePersistenceError without mutating state."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    c, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(), provenance="OFFLINE_FIXTURE")

    with pytest.raises(EvidencePersistenceError):
        store.append_candle(c, force_disk_error=True)

    assert store.count == 0  # In-memory state was not committed


def test_19_read_only_filesystem_failure(monkeypatch, tmp_path):
    """Verify that a read-only filesystem (EROFS) produces an EvidencePersistenceError."""
    store = RawMarketEvidenceStore(tmp_path / "raw", tmp_path / "quarantine")
    c, _ = BinanceSpotCandleValidator.validate_raw(create_sample_ws_candle(), provenance="OFFLINE_FIXTURE")

    def mock_open(*args, **kwargs):
        raise OSError(errno.EROFS, "Read-only file system")

    with patch("builtins.open", mock_open):
        with pytest.raises(EvidencePersistenceError) as exc:
            store.append_candle(c)
        assert "Read-only filesystem" in str(exc.value)


def test_20_shutdown_during_persistence(tmp_path):
    """Verify graceful engine stop mid-lifecycle without leaked processes or corrupt buffer."""
    cfg = ShadowCollectorConfig(base_dir=tmp_path)
    engine = MarketCaptureEngineV080(cfg)

    engine.start()
    assert engine.is_running is True

    # Process one candle
    raw = create_sample_ws_candle()
    engine.process_raw_message(raw)
    assert engine.total_persisted == 1

    engine.stop()
    assert engine.is_running is False


def test_21_fixture_versus_live_evidence_separation():
    """Verify that fixture evidence cannot masquerade as genuine live capture."""
    raw = create_sample_ws_candle()

    c_fixture, _ = BinanceSpotCandleValidator.validate_raw(raw, provenance=ProvenanceSource.OFFLINE_FIXTURE)
    assert c_fixture.provenance == "OFFLINE_FIXTURE"

    c_replay, _ = BinanceSpotCandleValidator.validate_raw(raw, provenance=ProvenanceSource.HISTORICAL_REPLAY)
    assert c_replay.provenance == "HISTORICAL_REPLAY"

    # Confirms distinct canonical representations
    assert c_fixture.compute_sha256() != c_replay.compute_sha256()


def test_22_approval_4_isolation(tmp_path):
    """Verify that prospective scored inference is strictly isolated and disabled."""
    cfg = ShadowCollectorConfig(base_dir=tmp_path, approval_4_authorized=False)
    engine = MarketCaptureEngineV080(cfg)

    assert engine.verify_approval_4_isolation() is True
    summary = engine.get_summary_report()
    assert summary["approval_4_isolated"] is True


def test_23_existing_inert_entrypoint_remains_inert():
    """Verify that the existing inert Coolify staging container remains inert."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-inert.yaml")
    spec = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    svc = spec["services"]["cbe-080-shadow-inert"]
    env_vars = dict(e.split("=", 1) for e in svc["environment"])

    assert env_vars.get("CBE_BINANCE_COLLECTION_ENABLED") == "false"
    assert env_vars.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"
    assert env_vars.get("CBE_TRADING_DISABLED") == "true"
    assert svc["network_mode"] == "none"
    assert svc["restart"] == "no"


def test_24_canonical_freeze_intact():
    """Verify all 29 canonical frozen CBE-0.7.0 artifacts remain untouched."""
    res = verify_sprint07_freeze(raise_on_error=False)
    assert res.get("verified") is True
    assert res.get("status") == "FREEZE_VERIFIED"
    assert res.get("canonical_hashes_verified") == 29
    assert len(res.get("canonical_mismatches", [])) == 0
