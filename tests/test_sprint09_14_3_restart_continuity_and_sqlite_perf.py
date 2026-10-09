"""CBE-0.8.0 Sprint 09.14.3 Test Suite: Restart Continuity, SQLite Index Optimization & Crash Consistency.

Verifies:
1. Deterministic state reconstruction after restart (100 candles, 288 candles, post-gap, partial write).
2. Agreement between reconstructed state and clean uninterrupted replay.
3. Strict fail-closed startup when evidence ledger is corrupted mid-chain.
4. Bounded-batch SQLite index rebuilding with WAL auto-healing after corruption/loss.
5. Exact binary byte-offset seeks without text-mode decoding shifts.
6. Crash consistency at critical failure boundaries.
7. Benchmarking startup verification & index reconstruction over 10,000 and 50,000 candles.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.gap_detector import CANDLE_INTERVAL_MS, MarketDataGapDetector
from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    EvidenceCorruptionError,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.transport_adapter import MockMarketDataTransport


def _make_candle(ts_open: int, provenance: str = ProvenanceSource.OFFLINE_FIXTURE.value, close_val: str = "50000.00") -> ValidatedCandle:
    return ValidatedCandle(
        symbol="BTCUSDT",
        interval="5m",
        market_type=MarketType.SPOT.value,
        timestamp_open=ts_open,
        timestamp_close=ts_open + 299_999,
        datetime_open_utc="2026-03-29T00:00:00Z",
        datetime_close_utc="2026-03-29T00:04:59.999Z",
        open="50000.00",
        high="50100.00",
        low="49900.00",
        close=close_val,
        volume="10.50000000",
        quote_volume="525000.00000000",
        trades_count=100,
        taker_buy_base_volume="5.25000000",
        is_closed=True,
        provenance=provenance,
        receipt_timestamp_utc="2026-03-29T00:05:00.050Z",
        lifecycle_state=CandleLifecycleState.CANDLE_VALIDATED.value,
    )


def _make_raw_msg(ts_open: int, close_val: str = "50000.00") -> Dict[str, Any]:
    return {
        "e": "kline",
        "E": ts_open + 300_000,
        "s": "BTCUSDT",
        "k": {
            "t": ts_open,
            "T": ts_open + 299_999,
            "s": "BTCUSDT",
            "i": "5m",
            "o": "50000.00",
            "h": "50100.00",
            "l": "49900.00",
            "c": close_val,
            "v": "10.0",
            "q": "500000.0",
            "n": 100,
            "V": "5.0",
            "x": True,
        },
    }


@pytest.fixture
def temp_engine_env():
    tmp_path = Path(tempfile.mkdtemp(prefix="cbe_test_09_14_3_"))
    config = ShadowCollectorConfig(
        symbol="BTCUSDT",
        interval="5m",
        approval_3_authorized=False,
        approval_4_authorized=False,
        live_shadow_enabled=False,
        network_enabled=False,
        trading_enabled=False,
        shadow_data_dir=tmp_path / "shadow",
    )
    config.raw_market_dir = tmp_path / "shadow" / "raw_market"
    config.quarantine_dir = tmp_path / "shadow" / "quarantine"
    config.ensure_directories()
    yield config, tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


class TestRestartContinuityReconstruction:
    """Verifies Task 1: Engine state restoration from previously committed evidence."""

    def test_restart_after_100_candles(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        for i in range(100):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS, close_val=f"{50000 + i}.00"))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(100):
            res = engine1.process_next_tick()
            assert res["status"] == "PERSISTED"
        engine1.stop()

        assert engine1.total_persisted == 100
        assert engine1.gap_detector.contiguous_closed_bars == 100
        assert len(engine1.rolling_buffer) == 100
        assert engine1.is_research_eligible is False  # Needs 288
        assert engine1.warmup_status == "WARMUP_PARTIAL (100/288)"

        # Restart engine with fresh instance pointing to same storage
        transport2 = MockMarketDataTransport(config)
        engine2 = MarketCaptureEngineV080(config=config, transport=transport2)

        assert engine2.total_persisted == 100
        assert engine2.gap_detector.contiguous_closed_bars == 100
        assert engine2.gap_detector.last_candle_open_ts == base_ts + 99 * CANDLE_INTERVAL_MS
        assert len(engine2.rolling_buffer) == 100
        assert engine2.is_research_eligible is False
        assert engine2.warmup_status == "WARMUP_PARTIAL (100/288)"
        assert len(engine2.gap_detector.gaps) == 0

        # Verify rolling buffer candles match in exact order
        assert engine2.rolling_buffer[0].timestamp_open == base_ts
        assert engine2.rolling_buffer[-1].timestamp_open == base_ts + 99 * CANDLE_INTERVAL_MS

    def test_restart_after_288_candles_restores_research_eligibility(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        for i in range(288):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(288):
            res = engine1.process_next_tick()
            assert res["status"] == "PERSISTED"
        engine1.stop()

        assert engine1.total_persisted == 288
        assert engine1.gap_detector.contiguous_closed_bars == 288
        assert engine1.is_research_eligible is True
        assert engine1.warmup_status == "FULL_WINDOW_READY"

        # Restart
        transport2 = MockMarketDataTransport(config)
        engine2 = MarketCaptureEngineV080(config=config, transport=transport2)

        # Full window eligibility must be restored
        assert engine2.total_persisted == 288
        assert engine2.gap_detector.contiguous_closed_bars == 288
        assert engine2.gap_detector.last_candle_open_ts == base_ts + 287 * CANDLE_INTERVAL_MS
        assert len(engine2.rolling_buffer) == 288
        assert engine2.is_research_eligible is True
        assert engine2.warmup_status == "FULL_WINDOW_READY"
        assert engine2.rolling_buffer[-1].lifecycle_state == CandleLifecycleState.CANDLE_RESEARCH_ELIGIBLE.value

    def test_restart_following_gap_in_history(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        # 50 contiguous candles
        for i in range(50):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))
        # Skip 2 candles (gap between 50 and 53), then 10 candles
        for i in range(53, 63):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(60):
            res = engine1.process_next_tick()
            assert res["status"] == "PERSISTED"
        engine1.stop()

        assert engine1.gap_detector.has_unrecovered_gaps is True
        assert len(engine1.gap_detector.gaps) == 1
        assert engine1.gap_detector.gaps[0].missing_bars_count == 3
        assert engine1.gap_detector.contiguous_closed_bars == 10
        assert engine1.is_research_eligible is False

        # Restart
        transport2 = MockMarketDataTransport(config)
        engine2 = MarketCaptureEngineV080(config=config, transport=transport2)

        # Gap state and contiguity must be restored identically
        assert engine2.total_persisted == 60
        assert engine2.gap_detector.has_unrecovered_gaps is True
        assert len(engine2.gap_detector.gaps) == 1
        gap_event = engine2.gap_detector.gaps[0]
        assert gap_event.missing_bars_count == 3
        assert gap_event.missing_start_ts == base_ts + 50 * CANDLE_INTERVAL_MS
        assert gap_event.missing_end_ts == base_ts + 52 * CANDLE_INTERVAL_MS
        assert engine2.gap_detector.contiguous_closed_bars == 10
        assert engine2.is_research_eligible is False
        assert len(engine2.rolling_buffer) == 60

    def test_rolling_buffer_caps_at_350_after_restart(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        for i in range(400):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(400):
            engine1.process_next_tick()
        engine1.stop()

        assert engine1.total_persisted == 400
        assert len(engine1.rolling_buffer) == 350
        assert engine1.gap_detector.contiguous_closed_bars == 400

        # Restart
        transport2 = MockMarketDataTransport(config)
        engine2 = MarketCaptureEngineV080(config=config, transport=transport2)

        assert engine2.total_persisted == 400
        assert len(engine2.rolling_buffer) == 350
        assert engine2.gap_detector.contiguous_closed_bars == 400
        assert engine2.is_research_eligible is True
        # Oldest in buffer is candle 50 (index 50)
        assert engine2.rolling_buffer[0].timestamp_open == base_ts + 50 * CANDLE_INTERVAL_MS
        assert engine2.rolling_buffer[-1].timestamp_open == base_ts + 399 * CANDLE_INTERVAL_MS

    def test_restart_after_partial_trailing_write(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        for i in range(20):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(20):
            engine1.process_next_tick()
        engine1.stop()

        evidence_file = engine1.evidence_store.evidence_file
        valid_size = evidence_file.stat().st_size

        # Append corrupted partial write at EOF
        with open(evidence_file, "ab") as f:
            f.write(b'{"entry_index":20,"prev_hash":"incomplete_data_break_')
            f.flush()
            os.fsync(f.fileno())

        # Restart engine
        transport2 = MockMarketDataTransport(config)
        engine2 = MarketCaptureEngineV080(config=config, transport=transport2)

        # Corrupt trailing bytes truncated, clean 20 entries restored
        assert evidence_file.stat().st_size == valid_size
        assert engine2.total_persisted == 20
        assert engine2.gap_detector.contiguous_closed_bars == 20
        assert len(engine2.rolling_buffer) == 20

    def test_mid_chain_corruption_stops_startup_immediately(self, temp_engine_env):
        config, _ = temp_engine_env
        transport = MockMarketDataTransport(config)
        transport.connect()

        base_ts = 1774742400000
        for i in range(10):
            transport.inject_message(_make_raw_msg(base_ts + i * CANDLE_INTERVAL_MS))

        engine1 = MarketCaptureEngineV080(config=config, transport=transport)
        engine1.start()
        for _ in range(10):
            engine1.process_next_tick()
        engine1.stop()

        evidence_file = engine1.evidence_store.evidence_file
        lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        data = json.loads(lines[5])
        data["candle"]["close"] = "999999.00"
        lines[5] = json.dumps(data)
        evidence_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Must fail closed immediately on engine instantiation
        with pytest.raises(EvidenceCorruptionError):
            MarketCaptureEngineV080(config=config, transport=MockMarketDataTransport(config))


class TestSQLiteBatchReconstructionAndPerformance:
    """Verifies Task 2: Efficient bounded-batch index reconstruction and SQLite auto-healing."""

    def test_sqlite_index_auto_heals_after_file_corruption(self, temp_engine_env):
        config, _ = temp_engine_env
        store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        base_ts = 1774742400000
        for i in range(25):
            store.append_candle(_make_candle(base_ts + i * CANDLE_INTERVAL_MS, close_val=f"{50000 + i}.00"))
        store.close()

        # Corrupt the SQLite database file with garbage bytes
        with open(store.index_file, "wb") as f:
            f.write(b"GARBAGE_NOT_A_SQLITE_DATABASE_HEADER" * 10)

        # Reopening store must detect corruption, quarantine corrupt file, and rebuild index cleanly
        recovered_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        assert recovered_store.count == 25
        # Verify all candles can be looked up from rebuilt index
        for i in range(25):
            c = recovered_store.get_candle_by_timestamp(base_ts + i * CANDLE_INTERVAL_MS)
            assert c is not None
            assert c.close == f"{50000 + i}.00"

        # Verify corrupted database was quarantined
        corrupted_quarantine = list(config.quarantine_dir.glob("corrupted_index_*"))
        assert len(corrupted_quarantine) >= 1
        recovered_store.close()

    def test_binary_offset_integrity(self, temp_engine_env):
        config, _ = temp_engine_env
        store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        base_ts = 1774742400000
        for i in range(15):
            store.append_candle(_make_candle(base_ts + i * CANDLE_INTERVAL_MS, close_val=f"{50000 + i}.12345678"))

        store.close()

        # Clear in-memory cache to force binary disk seek via offset
        test_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        test_store._recent_candles.clear()
        test_store._recent_candles_by_ts.clear()

        for i in range(15):
            ts = base_ts + i * CANDLE_INTERVAL_MS
            c = test_store.get_candle_by_timestamp(ts)
            assert c is not None
            assert c.timestamp_open == ts
            assert c.close == f"{50000 + i}.12345678"

        test_store.close()

    def test_benchmark_10000_and_50000_fixture_reconstruction(self, temp_engine_env):
        config, _ = temp_engine_env
        raw_dir = config.raw_market_dir
        quarantine_dir = config.quarantine_dir
        symbol = config.symbol
        interval = config.interval

        evidence_file = raw_dir / f"raw_candles_{symbol}_{interval}.jsonl"

        # Generate 10,000 deterministic fixture candles directly into JSONL
        base_ts = 1774742400000
        prev_h = "0" * 64
        lines_10k: List[str] = []

        for i in range(10_000):
            ts_open = base_ts + i * CANDLE_INTERVAL_MS
            c = _make_candle(ts_open)
            c_dict = c.canonical_dict()
            c_hash = c.compute_sha256()
            e_hash = hashlib.sha256(f"{i}:{prev_h}:{c_hash}".encode("utf-8")).hexdigest()
            entry_dict = {
                "entry_index": i,
                "prev_hash": prev_h,
                "candle_hash": c_hash,
                "entry_hash": e_hash,
                "persisted_at_utc": "2026-03-29T00:05:00Z",
                "candle": c_dict,
            }
            lines_10k.append(json.dumps(entry_dict, sort_keys=True, separators=(",", ":")))
            prev_h = e_hash

        with open(evidence_file, "wb") as f:
            f.write(("\n".join(lines_10k) + "\n").encode("utf-8"))

        tracemalloc.start()
        gc.collect()
        t0 = time.time()
        store_10k = RawMarketEvidenceStore(raw_dir, quarantine_dir, symbol, interval)
        t_10k = time.time() - t0
        _, peak_mem_10k = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert store_10k.count == 10_000
        store_10k.close()
        print(f"\n[BENCHMARK] 10,000 candles startup verification & index rebuild: {t_10k:.3f}s (Peak Mem: {peak_mem_10k / 1024 / 1024:.2f} MB)")
        assert t_10k < 5.0  # Must be fast (< 5s for 10k items)

        # Extend ledger to 50,000 candles
        lines_40k: List[str] = []
        for i in range(10_000, 50_000):
            ts_open = base_ts + i * CANDLE_INTERVAL_MS
            c = _make_candle(ts_open)
            c_dict = c.canonical_dict()
            c_hash = c.compute_sha256()
            e_hash = hashlib.sha256(f"{i}:{prev_h}:{c_hash}".encode("utf-8")).hexdigest()
            entry_dict = {
                "entry_index": i,
                "prev_hash": prev_h,
                "candle_hash": c_hash,
                "entry_hash": e_hash,
                "persisted_at_utc": "2026-03-29T00:05:00Z",
                "candle": c_dict,
            }
            lines_40k.append(json.dumps(entry_dict, sort_keys=True, separators=(",", ":")))
            prev_h = e_hash

        with open(evidence_file, "ab") as f:
            f.write(("\n".join(lines_40k) + "\n").encode("utf-8"))

        tracemalloc.start()
        gc.collect()
        t0 = time.time()
        store_50k = RawMarketEvidenceStore(raw_dir, quarantine_dir, symbol, interval)
        t_50k = time.time() - t0
        _, peak_mem_50k = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert store_50k.count == 50_000
        store_50k.close()
        print(f"[BENCHMARK] 50,000 candles startup verification & index rebuild: {t_50k:.3f}s (Peak Mem: {peak_mem_50k / 1024 / 1024:.2f} MB)")
        assert t_50k < 30.0  # Must be well within budget (< 30s for 50k items)
        assert (peak_mem_50k / 1024 / 1024) < 100.0  # Under 100 MB memory


class TestCrashConsistency:
    """Verifies Task 3: Crash interruption safety across critical operational boundaries."""

    def test_crash_after_jsonl_append_before_index_update(self, temp_engine_env):
        config, _ = temp_engine_env
        store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        base_ts = 1774742400000
        for i in range(5):
            store.append_candle(_make_candle(base_ts + i * CANDLE_INTERVAL_MS))
        store.close()

        # Simulate crash: directly append entry 5 to JSONL ledger without updating SQLite index
        c5 = _make_candle(base_ts + 5 * CANDLE_INTERVAL_MS, close_val="50555.00")
        c_dict = c5.canonical_dict()
        c_hash = c5.compute_sha256()
        prev_h = store.latest_entry_hash
        e_hash = hashlib.sha256(f"5:{prev_h}:{c_hash}".encode("utf-8")).hexdigest()
        entry_dict = {
            "entry_index": 5,
            "prev_hash": prev_h,
            "candle_hash": c_hash,
            "entry_hash": e_hash,
            "persisted_at_utc": "2026-03-29T00:05:00Z",
            "candle": c_dict,
        }
        with open(store.evidence_file, "ab") as f:
            f.write((json.dumps(entry_dict, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())

        # On restart, verify_and_recover_chain synchronizes index with entry 5
        recovered_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        assert recovered_store.count == 6
        assert recovered_store.get_candle_by_timestamp(base_ts + 5 * CANDLE_INTERVAL_MS).close == "50555.00"
        recovered_store.close()

    def test_crash_during_batch_reconstruction(self, temp_engine_env):
        config, _ = temp_engine_env
        store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        base_ts = 1774742400000
        for i in range(20):
            store.append_candle(_make_candle(base_ts + i * CANDLE_INTERVAL_MS))
        store.close()

        # Break SQLite index transaction midway by deleting some rows
        conn = sqlite3.connect(str(store.index_file))
        conn.execute("DELETE FROM timestamp_index WHERE entry_index >= 10;")
        conn.commit()
        conn.close()

        # Restarting store reconciles missing rows from JSONL
        recovered_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        assert recovered_store.count == 20
        for i in range(20):
            assert recovered_store.get_candle_by_timestamp(base_ts + i * CANDLE_INTERVAL_MS) is not None
        recovered_store.close()

    def test_crash_after_truncation_before_index_synchronization(self, temp_engine_env):
        config, _ = temp_engine_env
        store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        base_ts = 1774742400000
        for i in range(10):
            store.append_candle(_make_candle(base_ts + i * CANDLE_INTERVAL_MS))
        store.close()

        # Manually truncate evidence file by 2 entries (now 8 entries), while SQLite index still has 10
        with open(store.evidence_file, "r+b") as f:
            lines = [f.readline() for _ in range(8)]
            valid_len = sum(len(line) for line in lines)
            f.truncate(valid_len)
            f.flush()
            os.fsync(f.fileno())

        # On restart, verify_and_recover_chain purges orphaned entries from index
        recovered_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )
        assert recovered_store.count == 8
        assert recovered_store.get_candle_by_timestamp(base_ts + 8 * CANDLE_INTERVAL_MS) is None
        assert recovered_store.get_candle_by_timestamp(base_ts + 9 * CANDLE_INTERVAL_MS) is None
        recovered_store.close()
