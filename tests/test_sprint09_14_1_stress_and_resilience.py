"""Sprint 09.14.1 — Long-Run Stress, Data Integrity & Failure Resilience Test Suite.

Covers:
1. Long-run 10,000-event stress test (P95 latency < 5 ms, bounded memory, restart recovery < 1.0 s).
2. Persistence-before-continuity transactional guarantee (zero state advance on persistence failure).
3. Queue overflow drop tracking and FULL_WINDOW_READY reset.
4. Forensic EOF corruption backup, recovery audit, and in-place truncation without rewriting history.
5. Mid-chain tampering detection (fail-closed with EvidenceCorruptionError).
6. Exact Decimal string preservation, zero lossy float rounding, and analytical float boundaries.
7. RFC 6455 WebSocket framing, ping/pong echo, and oversized frame rejection.
8. Live transport fail-closed Approval 3 safety gates.
9. Read-only filesystem and disk-write failure resilience.
"""

from __future__ import annotations

import collections
import ctypes
import decimal
import errno
import hashlib
import io
import json
import os
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
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
    SafetyInterlockError,
    TransportConnectionError,
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


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_current_rss_mb() -> float:
    """Measure resident process memory in MB cross-platform."""
    if sys.platform == "win32":
        try:
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.windll.psapi
            kernel32 = ctypes.windll.kernel32
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            h = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                return round(pmc.WorkingSetSize / (1024.0 * 1024.0), 2)
        except Exception:
            return 0.0
    elif sys.platform.startswith("linux"):
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return round(float(line.split()[1]) / 1024.0, 2)
        except Exception:
            return 0.0
    return 0.0


def test_01_long_run_10000_sequential_events_stress(tmp_path):
    """Stress test processing >= 10,000 synthetic events:

    Verifies:
    - P95 latency < 5.0 ms.
    - Memory growth bounded (delta < 25 MB).
    - Rolling buffer strictly bounded (<= max_buffer_candles).
    - Restart recovery for 10,000 events completes in < 1.0 s.
    - Unbroken SHA-256 hash chain verified.
    """
    cfg = ShadowCollectorConfig(
        shadow_data_dir=tmp_path / "shadow",
        max_buffer_candles=350,
        full_warmup_bars=288,
    )
    engine = MarketCaptureEngineV080(cfg)

    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    n_events = 10000
    latencies = []
    initial_rss = get_current_rss_mb()

    for i in range(n_events):
        step_start = time.perf_counter()
        ts_open = t0 + i * CANDLE_INTERVAL_MS
        ts_close = ts_open + CANDLE_INTERVAL_MS - 1
        msg = {
            "e": "kline",
            "E": ts_close + 10,
            "s": "BTCUSDT",
            "k": {
                "t": ts_open,
                "T": ts_close,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "65000.00",
                "c": "65100.00",
                "h": "65200.00",
                "l": "64950.00",
                "v": "100.5",
                "n": 500,
                "x": True,
                "q": "6542550.00",
                "V": "50.25",
            },
        }
        res = engine.process_raw_message(msg)
        step_lat_ms = (time.perf_counter() - step_start) * 1000.0
        latencies.append(step_lat_ms)
        assert res["status"] == "PERSISTED"

    # Latency verification
    latencies.sort()
    p95_lat = latencies[int(n_events * 0.95)]
    mean_lat = sum(latencies) / len(latencies)
    assert p95_lat < 5.0, f"P95 latency {p95_lat:.3f} ms exceeded 5.0 ms threshold"

    # Memory boundedness verification
    peak_rss = get_current_rss_mb()
    rss_delta = peak_rss - initial_rss
    assert rss_delta < 25.0, f"RSS memory growth {rss_delta:.2f} MB exceeded 25 MB bound"

    # Buffer capacity boundedness
    assert len(engine.rolling_buffer) == 350
    assert engine.evidence_store.count == n_events

    # Restart recovery timing verification
    rec_start = time.perf_counter()
    recovered_store = RawMarketEvidenceStore(
        raw_market_dir=cfg.raw_market_dir,
        quarantine_dir=cfg.quarantine_dir,
    )
    rec_duration = time.perf_counter() - rec_start
    assert rec_duration < 1.0, f"Restart recovery {rec_duration:.3f} s exceeded 1.0 s threshold"
    assert recovered_store.count == n_events
    assert recovered_store.latest_entry_hash == engine.evidence_store.latest_entry_hash


def test_02_persistence_before_continuity_transactional_guarantee(tmp_path):
    """Verify that gap detector and rolling buffer state do NOT advance if persistence fails."""
    cfg = ShadowCollectorConfig(
        shadow_data_dir=tmp_path / "shadow",
        full_warmup_bars=288,
    )
    engine = MarketCaptureEngineV080(cfg)
    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

    def make_candle(ts_open):
        return {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": ts_open,
                "T": ts_open + CANDLE_INTERVAL_MS - 1,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "65000.00",
                "c": "65100.00",
                "h": "65200.00",
                "l": "64950.00",
                "v": "10.0",
                "x": True,
            },
        }

    # 1. First candle succeeds
    res1 = engine.process_raw_message(make_candle(t0))
    assert res1["status"] == "PERSISTED"
    assert engine.gap_detector.contiguous_closed_bars == 1
    assert engine.gap_detector.last_candle_open_ts == t0
    assert len(engine.rolling_buffer) == 1

    # 2. Second candle fails disk persistence
    t1 = t0 + CANDLE_INTERVAL_MS
    with pytest.raises(EvidencePersistenceError):
        engine.process_raw_message(make_candle(t1), force_disk_error=True)

    # 3. Verify continuity state remained UNMUTATED
    assert engine.gap_detector.contiguous_closed_bars == 1  # Still 1, NOT 2!
    assert engine.gap_detector.last_candle_open_ts == t0  # Still t0, NOT t1!
    assert len(engine.rolling_buffer) == 1  # Still 1, NOT 2!

    # 4. Retry second candle without error -> cleanly commits
    res2 = engine.process_raw_message(make_candle(t1), force_disk_error=False)
    assert res2["status"] == "PERSISTED"
    assert engine.gap_detector.contiguous_closed_bars == 2
    assert engine.gap_detector.last_candle_open_ts == t1
    assert len(engine.rolling_buffer) == 2


def test_03_queue_overflow_tracks_drops_and_resets_contiguity(tmp_path):
    """Verify that inbound queue overflow records drops, engages degraded state, and resets contiguity."""
    cfg = ShadowCollectorConfig(
        shadow_data_dir=tmp_path / "shadow",
        full_warmup_bars=10,  # Small warmup for test speed
    )
    engine = MarketCaptureEngineV080(cfg)
    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

    # Feed 10 contiguous candles to achieve ready state
    for i in range(10):
        ts = t0 + i * CANDLE_INTERVAL_MS
        msg = {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": ts,
                "T": ts + CANDLE_INTERVAL_MS - 1,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "65000.00",
                "c": "65100.00",
                "h": "65200.00",
                "l": "64950.00",
                "v": "10.0",
                "x": True,
            },
        }
        engine.process_raw_message(msg)

    assert engine.gap_detector.contiguous_closed_bars == 10
    assert engine.is_research_eligible is True
    assert engine.warmup_status == "FULL_WINDOW_READY"

    # Simulate inbound transport queue overflow drop
    engine.record_queue_overflow(dropped_count=1)

    assert engine.overflow_events_count == 1
    assert engine.is_degraded is True
    assert engine.is_research_eligible is False
    assert engine.gap_detector.contiguous_closed_bars == 0
    assert engine.warmup_status == "DEGRADED_OVERFLOW_RECOVERY"


def test_04_forensic_eof_corruption_backup_and_in_place_truncation(tmp_path):
    """Verify that trailing incomplete EOF writes are backed up forensically and truncated in-place without rewriting valid history."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    for i in range(10):
        c, _ = BinanceSpotCandleValidator.validate_raw(
            {
                "e": "kline",
                "s": "BTCUSDT",
                "k": {
                    "t": t0 + i * CANDLE_INTERVAL_MS,
                    "T": t0 + (i + 1) * CANDLE_INTERVAL_MS - 1,
                    "s": "BTCUSDT",
                    "i": "5m",
                    "o": "65000.00",
                    "c": "65100.00",
                    "h": "65200.00",
                    "l": "64950.00",
                    "v": "10.0",
                    "x": True,
                },
            },
            provenance="OFFLINE_FIXTURE",
        )
        store.append_candle(c)

    original_bytes = store.evidence_file.read_bytes()
    original_size = len(original_bytes)
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()

    # Simulate sudden crash / mid-line EOF truncation
    damaged_trailing_bytes = b'{"entry_index": 10, "prev_hash": "abcdef", "cand'
    with open(store.evidence_file, "ab") as f:
        f.write(damaged_trailing_bytes)

    # Reopen store to trigger forensic verification and recovery
    recovered_store = RawMarketEvidenceStore(raw_dir, q_dir)

    # 1. Recovered count is exactly 10
    assert recovered_store.count == 10

    # 2. File size matches original size exactly (in-place truncate)
    current_bytes = recovered_store.evidence_file.read_bytes()
    assert len(current_bytes) == original_size
    assert hashlib.sha256(current_bytes).hexdigest() == original_sha256

    # 3. Forensic backup exists and contains exact damaged bytes
    forensic_files = list(q_dir.glob("forensic_trailing_corruption_*.bin"))
    assert len(forensic_files) >= 1
    assert forensic_files[0].read_bytes() == damaged_trailing_bytes

    # 4. Recovery audit log contains structured audit record
    audit_file = q_dir / "recovery_audit.jsonl"
    assert audit_file.exists()
    audit_line = audit_file.read_text(encoding="utf-8").strip()
    audit_data = json.loads(audit_line)
    assert audit_data["action"] == "TRAILING_CORRUPTION_FORENSIC_TRUNCATE"
    assert audit_data["truncated_bytes_count"] == len(damaged_trailing_bytes)
    assert audit_data["valid_entries_count"] == 10


def test_05_mid_chain_tampering_fails_closed(tmp_path):
    """Verify that mid-chain corruption strictly fails closed with EvidenceCorruptionError."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    for i in range(5):
        c, _ = BinanceSpotCandleValidator.validate_raw(
            {
                "e": "kline",
                "s": "BTCUSDT",
                "k": {
                    "t": t0 + i * CANDLE_INTERVAL_MS,
                    "T": t0 + (i + 1) * CANDLE_INTERVAL_MS - 1,
                    "s": "BTCUSDT",
                    "i": "5m",
                    "o": "65000.00",
                    "c": "65100.00",
                    "h": "65200.00",
                    "l": "64950.00",
                    "v": "10.0",
                    "x": True,
                },
            },
            provenance="OFFLINE_FIXTURE",
        )
        store.append_candle(c)

    # Tamper with entry at index 2 (mid-file)
    lines = store.evidence_file.read_text(encoding="utf-8").splitlines()
    item2 = json.loads(lines[2])
    item2["candle"]["close"] = "99999.00"
    lines[2] = json.dumps(item2)
    store.evidence_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reopening store must raise EvidenceCorruptionError
    with pytest.raises(EvidenceCorruptionError) as exc:
        RawMarketEvidenceStore(raw_dir, q_dir)
    assert "Candle hash mismatch" in str(exc.value)


def test_06_exact_decimal_string_preservation_and_float_boundaries(tmp_path):
    """Verify that high-precision exchange strings are preserved without IEEE 754 float drift."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    exact_open = "65123.123456789012345"
    exact_close = "65456.987654321098765"
    exact_high = "65500.000000000000000"
    exact_low = "65000.000000000000000"
    exact_vol = "0.000000012345678901"

    msg = {
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": t0,
            "T": t0 + CANDLE_INTERVAL_MS - 1,
            "s": "BTCUSDT",
            "i": "5m",
            "o": exact_open,
            "c": exact_close,
            "h": exact_high,
            "l": exact_low,
            "v": exact_vol,
            "x": True,
        },
    }
    c, violations = BinanceSpotCandleValidator.validate_raw(msg, provenance="OFFLINE_FIXTURE")
    assert violations == []
    assert c.open == exact_open
    assert c.close == exact_close

    # Persist and inspect on-disk canonical json
    status, entry = store.append_candle(c)
    assert status == "PERSISTED"

    disk_line = store.evidence_file.read_text(encoding="utf-8").strip()
    assert f'"{exact_open}"' in disk_line
    assert f'"{exact_close}"' in disk_line

    # Float boundaries for downstream models
    float_dict = c.to_float_dict()
    assert isinstance(float_dict["open"], float)
    assert float_dict["open"] == pytest.approx(65123.123456789)
    assert c.open_float == pytest.approx(65123.123456789)

    # matches_payload uses Decimal exactness
    c_copy, _ = BinanceSpotCandleValidator.validate_raw(msg, provenance="OFFLINE_FIXTURE")
    assert c.matches_payload(c_copy)


def test_07_live_transport_rfc6455_framing_and_ping_pong():
    """Verify RFC 6455 framing, ping echo, and frame size checking in BinanceSpotWebSocketAdapter."""
    cfg = ShadowCollectorConfig(
        approval_3_authorized=True,
    )
    with patch.dict(os.environ, {
        "CBE_APPROVAL_3_AUTHORIZED": "true",
        "CBE_BINANCE_COLLECTION_ENABLED": "true",
        "CBE_TRADING_DISABLED": "true",
    }):
        adapter = BinanceSpotWebSocketAdapter(cfg, max_message_bytes=1024)
        mock_sock = MagicMock()
        adapter._sock = mock_sock
        adapter._connected = True

        # 1. Send frame generates masked payload
        adapter._send_frame(opcode=0x1, payload=b"ping-test")
        sent_data = mock_sock.sendall.call_args[0][0]
        assert len(sent_data) > 0
        # Byte 0 has FIN=1 (0x80) and text opcode (0x1) -> 0x81
        assert sent_data[0] == 0x81
        # Byte 1 has MASK bit set (0x80)
        assert sent_data[1] & 0x80 != 0

        # 2. Simulate incoming Ping frame (opcode 0x9) -> triggers Pong (opcode 0xA)
        # Server sends unmasked frame: 0x89 (FIN+Ping), length 4, "PING"
        mock_sock.recv.side_effect = [
            bytes([0x89, 0x04]),  # Header: FIN+Ping, len=4
            b"PING",               # Payload
        ]
        mock_sock.sendall.reset_mock()
        result = adapter.poll_message()
        assert result is None  # Ping handled internally
        assert mock_sock.sendall.called
        pong_data = mock_sock.sendall.call_args[0][0]
        assert pong_data[0] == 0x8A  # FIN + Pong opcode 0xA

        # 3. Oversized frame raises OversizedMessageError
        mock_sock.recv.side_effect = [
            bytes([0x81, 126]),   # Text frame, 16-bit length follows
            (2048).to_bytes(2, "big"),
        ]
        with pytest.raises(OversizedMessageError):
            adapter._read_frame()


def test_08_live_transports_strict_approval_3_fail_closed(monkeypatch):
    """Verify that WebSocket and REST adapters strictly fail closed without explicit Approval 3."""
    cfg = ShadowCollectorConfig(
        approval_3_authorized=False,
    )

    # Missing config authorization
    with pytest.raises(SafetyInterlockError) as exc1:
        BinanceSpotWebSocketAdapter(cfg)
    assert "HARD SAFETY INTERLOCK" in str(exc1.value)

    with pytest.raises(SafetyInterlockError) as exc2:
        BinanceSpotRestAdapter(cfg)
    assert "HARD SAFETY INTERLOCK" in str(exc2.value)

    # Config enabled but env missing
    cfg.approval_3_authorized = True
    with pytest.raises(SafetyInterlockError) as exc3:
        BinanceSpotWebSocketAdapter(cfg)
    assert "CBE_APPROVAL_3_AUTHORIZED" in str(exc3.value)

    # Env collection disabled
    monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
    with pytest.raises(SafetyInterlockError) as exc4:
        BinanceSpotWebSocketAdapter(cfg)
    assert "CBE_BINANCE_COLLECTION_ENABLED" in str(exc4.value)

    # Trading enabled -> permanent interlock
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    cfg.trading_enabled = True
    with pytest.raises(SafetyInterlockError) as exc5:
        BinanceSpotWebSocketAdapter(cfg)
    assert "Trading is permanently prohibited" in str(exc5.value)


def test_09_read_only_filesystem_safety(tmp_path):
    """Verify that read-only filesystem errors are detected and handled without state corruption."""
    raw_dir = tmp_path / "raw"
    q_dir = tmp_path / "quarantine"
    store = RawMarketEvidenceStore(raw_dir, q_dir)

    t0 = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
    c, _ = BinanceSpotCandleValidator.validate_raw(
        {
            "e": "kline",
            "s": "BTCUSDT",
            "k": {
                "t": t0,
                "T": t0 + CANDLE_INTERVAL_MS - 1,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "65000.00",
                "c": "65100.00",
                "h": "65200.00",
                "l": "64950.00",
                "v": "10.0",
                "x": True,
            },
        },
        provenance="OFFLINE_FIXTURE",
    )

    with patch("builtins.open", side_effect=OSError(errno.EROFS, "Read-only file system")):
        with pytest.raises(EvidencePersistenceError) as exc:
            store.append_candle(c)
        assert "Read-only filesystem" in str(exc.value)

    assert store.count == 0
    assert store.latest_open_ts == -1
