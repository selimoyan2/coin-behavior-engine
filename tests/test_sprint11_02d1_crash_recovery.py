"""CBE — Sprint 11.02D.1: Recovery Transaction Hardening & Crash-Safe Evidence Integrity.

Comprehensive 28-Test Mandatory Failure-Injection Matrix:
1. Journal append failure before any bytes are written.
2. Partial journal append.
3. Journal fsync failure.
4. Crash after journal fsync but before read-back.
5. Read-back mismatch.
6. Crash after successful read-back but before metadata commit.
7. Partial metadata append.
8. Metadata fsync failure.
9. Crash after metadata fsync but before in-memory update.
10. Restart with committed metadata and valid journal.
11. Restart with journal entries but no metadata.
12. Restart with malformed metadata.
13. Restart with corrupted journal JSON.
14. Restart with broken recovery hash chain.
15. Restart with mismatched metadata entry indexes.
16. Restart with mismatched recovery batch ID.
17. Duplicate recovery request with identical candles.
18. Duplicate recovery request with conflicting OHLCV.
19. Recovery request with missing timestamps.
20. Recovery request with extra timestamps.
21. REST timeout.
22. REST rate limiting.
23. Incomplete REST response.
24. Exact 141-candle recovery.
25. Restart after successful 141-candle recovery.
26. Research eligibility remains false for uncommitted recovery.
27. Original raw evidence remains byte-for-byte unchanged.
28. Frozen 29/29 canonical hashes remain identical.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.gap_recovery_store import (
    ConflictingRecoveryCandleError,
    DurableGapRecoveryStore,
    RecoveredEvidenceEntry,
    RecoveryJournalCorruptionError,
    RecoveryMetadataCorruptionError,
    RecoveryStorePersistenceError,
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
    MockMarketDataTransport,
    RateLimitExceededError,
    TransportConnectionError,
)

BASE_TS = 1792149000000


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
        "5.2",
        "332800.00",
        "0",
    ]


def _make_sample_ws_candle(
    open_ts: int,
    open_price: str = "64000.00",
    close_price: str = "64050.00",
    vol: str = "10.5",
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
            "c": close_price,
            "h": h_str,
            "l": l_str,
            "v": vol,
            "q": "672525.00",
            "V": "5.2",
            "n": 150,
            "x": is_closed,
        },
    }


def _make_validated_candle(
    open_ts: int,
    open_p: str = "64000.00",
    close_p: str = "64050.00",
    vol: str = "10.5",
    provenance: str = ProvenanceSource.REST_GAP_RECOVERY.value,
) -> ValidatedCandle:
    validator = BinanceSpotCandleValidator()
    raw = _make_raw_kline(open_ts, open_p, close_p, vol)
    candle, violations = validator.validate_raw(
        raw_record=raw,
        provenance=provenance,
        market_type=MarketType.SPOT,
    )
    assert not violations, f"Violations: {violations}"
    assert candle is not None
    return candle


@pytest.fixture
def temp_capture_dirs():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        raw_market = tmp_path / "raw_market"
        quarantine = tmp_path / "quarantine"
        raw_market.mkdir(parents=True, exist_ok=True)
        quarantine.mkdir(parents=True, exist_ok=True)
        yield raw_market, quarantine


# 1. Journal append failure before any bytes are written
def test_01_journal_append_failure_before_bytes_written(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    with pytest.raises(RecoveryStorePersistenceError):
        store.persist_recovery_batch(
            gap_id="GAP-1",
            recovery_batch_id="REC-1",
            missing_start_ts=BASE_TS,
            missing_end_ts=BASE_TS,
            missing_timestamps=[BASE_TS],
            recovered_candles=[c],
            force_disk_error=True,
        )

    assert not store.journal_file.exists() or store.journal_file.stat().st_size == 0
    assert not store.metadata_file.exists()
    assert store.get_committed_gap("GAP-1") is None
    assert store.entry_count == 0


# 2. Partial journal append
def test_02_partial_journal_append(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)

    with open(store.journal_file, "w", encoding="utf-8") as f:
        f.write('{"entry_index": 0, "prev_recovery_hash": "0000000000000000000000000000000000000000000000000000000000000000", "gap_id": "GAP-1"\n')

    with pytest.raises(RecoveryJournalCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 3. Journal fsync failure
def test_03_journal_fsync_failure(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    orig_fsync = os.fsync
    def mock_fsync(fd):
        raise OSError("Simulated disk I/O fsync failure")

    with patch("os.fsync", side_effect=mock_fsync):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    assert not store.metadata_file.exists()
    assert store.get_committed_gap("GAP-1") is None


# 4. Crash after journal fsync but before read-back
def test_04_crash_after_journal_fsync_before_readback(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    with patch.object(store, "_readback_verify_journal", side_effect=RecoveryStorePersistenceError("Crash before readback")):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    assert store.journal_file.exists()
    assert not store.metadata_file.exists()

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.committed_gaps_count == 0
    assert restarted.uncommitted_gaps_count == 1
    assert restarted.get_committed_gap("GAP-1") is None
    assert len(restarted.get_uncommitted_entries_for_gap("GAP-1")) == 1


# 5. Read-back mismatch
def test_05_readback_mismatch(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    orig_readback = store._readback_verify_journal
    def tamper_and_verify(first_idx, last_idx, expected_entries, expected_candles):
        tampered_c = copy.deepcopy(expected_candles[0])
        tampered_c.close = "999999.00"
        return orig_readback(first_idx, last_idx, expected_entries, [tampered_c])

    with patch.object(store, "_readback_verify_journal", side_effect=tamper_and_verify):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    assert not store.metadata_file.exists()
    assert store.get_committed_gap("GAP-1") is None


# 6. Crash after successful read-back but before metadata commit
def test_06_crash_after_successful_readback_before_metadata_commit(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    real_open = open
    def mock_open(file, mode="r", *args, **kwargs):
        if str(file) == str(store.metadata_file) and "a" in mode:
            raise OSError("Crash before metadata write")
        return real_open(file, mode, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.get_committed_gap("GAP-1") is None
    assert restarted.uncommitted_gaps_count == 1

    # Retry recovery with identical candles: safe reconciliation succeeds without duplicate journal append!
    ok, msg = restarted.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )
    assert ok is True
    assert msg == "DURABLY_COMMITTED"
    assert restarted.committed_gaps_count == 1
    assert restarted.uncommitted_gaps_count == 0
    assert restarted.get_committed_gap("GAP-1") is not None
    assert restarted.entry_count == 1


# 7. Partial metadata append
def test_07_partial_metadata_append(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)
    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )

    with open(store.metadata_file, "a", encoding="utf-8") as f:
        f.write('{"gap_id": "GAP-2", "recovery_batch_id": "REC-2", "first_entry_index":\n')

    with pytest.raises(RecoveryMetadataCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 8. Metadata fsync failure
def test_08_metadata_fsync_failure(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    orig_fsync = os.fsync
    call_count = 0
    def mock_fsync(fd):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise OSError("Metadata fsync power failure")
        return orig_fsync(fd)

    with patch("os.fsync", side_effect=mock_fsync):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.get_committed_gap("GAP-1") is None


# 9. Crash after metadata fsync but before in-memory update
def test_09_crash_after_metadata_fsync_before_in_memory_update(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    orig_readback_meta = store._readback_verify_metadata
    def fail_after_meta_verify(gap_meta):
        orig_readback_meta(gap_meta)
        raise RuntimeError("Process killed immediately after metadata readback")

    with patch.object(store, "_readback_verify_metadata", side_effect=fail_after_meta_verify):
        with pytest.raises(RecoveryStorePersistenceError):
            store.persist_recovery_batch(
                gap_id="GAP-1",
                recovery_batch_id="REC-1",
                missing_start_ts=BASE_TS,
                missing_end_ts=BASE_TS,
                missing_timestamps=[BASE_TS],
                recovered_candles=[c],
            )

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.committed_gaps_count == 1
    assert restarted.get_committed_gap("GAP-1") is not None
    assert restarted.entry_count == 1
    assert restarted.get_recovered_candle(BASE_TS) is not None


# 10. Restart with committed metadata and valid journal
def test_10_restart_with_committed_metadata_and_valid_journal(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c1 = _make_validated_candle(BASE_TS)
    c2 = _make_validated_candle(BASE_TS + CANDLE_INTERVAL_MS)

    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS + CANDLE_INTERVAL_MS,
        missing_timestamps=[BASE_TS, BASE_TS + CANDLE_INTERVAL_MS],
        recovered_candles=[c1, c2],
    )

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.committed_gaps_count == 1
    assert restarted.entry_count == 2
    assert restarted.get_committed_gap("GAP-1").recovered_candles_count == 2
    assert restarted.get_recovered_candle(BASE_TS) is not None
    assert restarted.get_recovered_candle(BASE_TS + CANDLE_INTERVAL_MS) is not None


# 11. Restart with journal entries but no metadata
def test_11_restart_with_journal_entries_but_no_metadata(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    entry_h = store.compute_entry_integrity_hash("REC-1", "GAP-1", 0, "0" * 64, c.compute_sha256())
    entry = RecoveredEvidenceEntry(
        recovery_batch_id="REC-1",
        gap_id="GAP-1",
        entry_index=0,
        prev_recovery_hash="0" * 64,
        candle_hash=c.compute_sha256(),
        integrity_hash=entry_h,
        persisted_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_metadata={},
        candle=c.canonical_dict(),
    )
    with open(store.journal_file, "w", encoding="utf-8") as f:
        f.write(entry.to_json() + "\n")

    restarted = DurableGapRecoveryStore(raw_market, quarantine)
    assert restarted.committed_gaps_count == 0
    assert restarted.uncommitted_gaps_count == 1
    assert restarted.get_committed_gap("GAP-1") is None
    assert restarted.get_recovered_candle(BASE_TS) is None


# 12. Restart with malformed metadata
def test_12_restart_with_malformed_metadata(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)
    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )

    with open(store.metadata_file, "w", encoding="utf-8") as f:
        f.write("NOT_A_JSON_LINE\n")

    with pytest.raises(RecoveryMetadataCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 13. Restart with corrupted journal JSON
def test_13_restart_with_corrupted_journal_json(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)
    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )

    with open(store.journal_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json}\n")

    with pytest.raises(RecoveryJournalCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 14. Restart with broken recovery hash chain
def test_14_restart_with_broken_recovery_hash_chain(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c1 = _make_validated_candle(BASE_TS)
    c2 = _make_validated_candle(BASE_TS + CANDLE_INTERVAL_MS)

    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS + CANDLE_INTERVAL_MS,
        missing_timestamps=[BASE_TS, BASE_TS + CANDLE_INTERVAL_MS],
        recovered_candles=[c1, c2],
    )

    lines = open(store.journal_file, "r", encoding="utf-8").readlines()
    e2 = json.loads(lines[1])
    e2["prev_recovery_hash"] = "f" * 64
    lines[1] = json.dumps(e2) + "\n"
    with open(store.journal_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    with pytest.raises(RecoveryJournalCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 15. Restart with mismatched metadata entry indexes
def test_15_restart_with_mismatched_metadata_entry_indexes(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)
    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )

    lines = open(store.metadata_file, "r", encoding="utf-8").readlines()
    meta = json.loads(lines[0])
    meta["first_entry_index"] = 99
    meta["last_entry_index"] = 99
    with open(store.metadata_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")

    with pytest.raises(RecoveryMetadataCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 16. Restart with mismatched recovery batch ID
def test_16_restart_with_mismatched_recovery_batch_id(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)
    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )

    lines = open(store.metadata_file, "r", encoding="utf-8").readlines()
    meta = json.loads(lines[0])
    meta["recovery_batch_id"] = "REC-DIFFERENT"
    with open(store.metadata_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")

    with pytest.raises(RecoveryMetadataCorruptionError):
        DurableGapRecoveryStore(raw_market, quarantine)


# 17. Duplicate recovery request with identical candles
def test_17_duplicate_recovery_request_with_identical_candles(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c = _make_validated_candle(BASE_TS)

    ok1, msg1 = store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c],
    )
    assert ok1 is True
    assert msg1 == "DURABLY_COMMITTED"
    assert store.entry_count == 1

    c_clone = _make_validated_candle(BASE_TS)
    ok2, msg2 = store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-2",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c_clone],
    )
    assert ok2 is True
    assert msg2 == "ALREADY_COMMITTED"
    assert store.entry_count == 1


# 18. Duplicate recovery request with conflicting OHLCV
def test_18_duplicate_recovery_request_with_conflicting_ohlcv(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c1 = _make_validated_candle(BASE_TS, open_p="64000.00", close_p="64050.00")

    store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c1],
    )

    c_conflicting = _make_validated_candle(BASE_TS, open_p="64000.00", close_p="65000.00")
    with pytest.raises(ConflictingRecoveryCandleError):
        store.persist_recovery_batch(
            gap_id="GAP-1",
            recovery_batch_id="REC-2",
            missing_start_ts=BASE_TS,
            missing_end_ts=BASE_TS,
            missing_timestamps=[BASE_TS],
            recovered_candles=[c_conflicting],
        )

    assert store.quarantine_file.exists()
    q_content = open(store.quarantine_file, "r", encoding="utf-8").read()
    assert "CONFLICTING_RECOVERED_CANDLE" in q_content
    assert "GAP-1" in q_content


# 19. Recovery request with missing timestamps
def test_19_recovery_request_with_missing_timestamps(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c1 = _make_validated_candle(BASE_TS)

    ok, msg = store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS + CANDLE_INTERVAL_MS,
        missing_timestamps=[BASE_TS, BASE_TS + CANDLE_INTERVAL_MS],
        recovered_candles=[c1],
    )
    assert ok is False
    assert "TIMESTAMP_MISMATCH" in msg
    assert store.entry_count == 0


# 20. Recovery request with extra timestamps
def test_20_recovery_request_with_extra_timestamps(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    store = DurableGapRecoveryStore(raw_market, quarantine)
    c1 = _make_validated_candle(BASE_TS)
    c2 = _make_validated_candle(BASE_TS + CANDLE_INTERVAL_MS)

    ok, msg = store.persist_recovery_batch(
        gap_id="GAP-1",
        recovery_batch_id="REC-1",
        missing_start_ts=BASE_TS,
        missing_end_ts=BASE_TS,
        missing_timestamps=[BASE_TS],
        recovered_candles=[c1, c2],
    )
    assert ok is False
    assert "TIMESTAMP_MISMATCH" in msg
    assert store.entry_count == 0


# 21. REST timeout
def test_21_rest_timeout(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=5)
    cfg.ensure_directories()
    transport = MockMarketDataTransport()
    engine = MarketCaptureEngineV080(config=cfg, transport=transport)

    try:
        c1_msg = _make_sample_ws_candle(BASE_TS)
        c3_msg = _make_sample_ws_candle(BASE_TS + 2 * CANDLE_INTERVAL_MS)
        engine.process_raw_message(c1_msg)
        engine.process_raw_message(c3_msg)

        assert len(engine.gap_detector.gaps) == 1
        gap_id = engine.gap_detector.gaps[0].gap_id

        mock_rest = MockRestAdapter()
        mock_rest.simulate_timeout = True

        ok, msg = engine.recover_gap_via_rest(gap_id, mock_rest)
        assert ok is False
        assert "Mock timeout" in msg
        assert not engine.gap_detector.gaps[0].recovered
        assert engine.recovery_store.entry_count == 0
    finally:
        engine.evidence_store.close()


# 22. REST rate limiting
def test_22_rest_rate_limiting(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=5)
    cfg.ensure_directories()
    transport = MockMarketDataTransport()
    engine = MarketCaptureEngineV080(config=cfg, transport=transport)

    try:
        c1_msg = _make_sample_ws_candle(BASE_TS)
        c3_msg = _make_sample_ws_candle(BASE_TS + 2 * CANDLE_INTERVAL_MS)
        engine.process_raw_message(c1_msg)
        engine.process_raw_message(c3_msg)

        gap_id = engine.gap_detector.gaps[0].gap_id
        mock_rest = MockRestAdapter()
        mock_rest.simulate_rate_limit = True

        ok, msg = engine.recover_gap_via_rest(gap_id, mock_rest)
        assert ok is False
        assert "RateLimitExceededError" in msg or "HTTP 429" in msg
        assert not engine.gap_detector.gaps[0].recovered
    finally:
        engine.evidence_store.close()


# 23. Incomplete REST response
def test_23_incomplete_rest_response(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=5)
    cfg.ensure_directories()
    transport = MockMarketDataTransport()
    engine = MarketCaptureEngineV080(config=cfg, transport=transport)

    try:
        t1 = BASE_TS
        t4 = BASE_TS + 3 * CANDLE_INTERVAL_MS
        engine.process_raw_message(_make_sample_ws_candle(t1))
        engine.process_raw_message(_make_sample_ws_candle(t4))

        assert len(engine.gap_detector.gaps) == 1
        gap = engine.gap_detector.gaps[0]
        assert gap.missing_bars_count == 2

        mock_rest = MockRestAdapter(klines_data=[_make_raw_kline(BASE_TS + CANDLE_INTERVAL_MS)])
        ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
        assert ok is False
        assert "RECOVERY_MISMATCH" in msg
        assert not gap.recovered
        assert engine.recovery_store.entry_count == 0
    finally:
        engine.evidence_store.close()


# 24. Exact 141-candle recovery
def test_24_exact_141_candle_recovery(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=288)
    cfg.ensure_directories()
    transport = MockMarketDataTransport()
    engine = MarketCaptureEngineV080(config=cfg, transport=transport)

    try:
        start_ts = 1792149300000 - (200 * CANDLE_INTERVAL_MS)
        for i in range(200):
            engine.process_raw_message(_make_sample_ws_candle(start_ts + i * CANDLE_INTERVAL_MS))

        jump_ts = 1792191600000
        engine.process_raw_message(_make_sample_ws_candle(jump_ts))

        assert len(engine.gap_detector.gaps) == 1
        gap = engine.gap_detector.gaps[0]
        assert gap.missing_bars_count == 141
        assert gap.missing_start_ts == 1792149300000
        assert gap.missing_end_ts == 1792191600000 - CANDLE_INTERVAL_MS

        klines_141 = [
            _make_raw_kline(gap.missing_start_ts + i * CANDLE_INTERVAL_MS)
            for i in range(141)
        ]
        mock_rest = MockRestAdapter(klines_data=klines_141)

        ok, msg = engine.recover_gap_via_rest(gap.gap_id, mock_rest)
        assert ok is True, f"Recovery failed: {msg}"
        assert gap.recovered is True
        assert gap.recovered_candles_count == 141
        assert engine.recovery_store.entry_count == 141
        assert engine.recovery_store.committed_gaps_count == 1
    finally:
        engine.evidence_store.close()


# 25. Restart after successful 141-candle recovery
def test_25_restart_after_successful_141_candle_recovery(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=288)
    cfg.ensure_directories()
    transport = MockMarketDataTransport()
    engine = MarketCaptureEngineV080(config=cfg, transport=transport)

    engine_restarted = None
    try:
        start_ts = 1792149300000 - (150 * CANDLE_INTERVAL_MS)
        for i in range(150):
            engine.process_raw_message(_make_sample_ws_candle(start_ts + i * CANDLE_INTERVAL_MS))

        jump_ts = 1792191600000
        engine.process_raw_message(_make_sample_ws_candle(jump_ts))

        for i in range(1, 51):
            engine.process_raw_message(_make_sample_ws_candle(jump_ts + i * CANDLE_INTERVAL_MS))

        gap = engine.gap_detector.gaps[0]
        klines_141 = [
            _make_raw_kline(gap.missing_start_ts + i * CANDLE_INTERVAL_MS)
            for i in range(141)
        ]
        ok, msg = engine.recover_gap_via_rest(gap.gap_id, MockRestAdapter(klines_141))
        assert ok is True

        # 150 + 141 + 51 = 342 >= 288 (eligible!)
        assert engine.is_research_eligible is True
        assert engine.gap_detector.contiguous_closed_bars == 342

        # Restart engine from disk
        engine.evidence_store.close()

        engine_restarted = MarketCaptureEngineV080(config=cfg, transport=MockMarketDataTransport())
        assert len(engine_restarted.gap_detector.gaps) == 1
        assert engine_restarted.gap_detector.gaps[0].recovered is True
        assert engine_restarted.is_research_eligible is True
        assert engine_restarted.gap_detector.contiguous_closed_bars == 342
    finally:
        if engine_restarted is not None:
            engine_restarted.evidence_store.close()
        else:
            engine.evidence_store.close()


# 26. Research eligibility remains false for uncommitted recovery
def test_26_research_eligibility_remains_false_for_uncommitted_recovery(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=10)
    cfg.ensure_directories()
    engine = MarketCaptureEngineV080(config=cfg, transport=MockMarketDataTransport())

    engine_restarted = None
    try:
        start_ts = BASE_TS
        for i in range(5):
            engine.process_raw_message(_make_sample_ws_candle(start_ts + i * CANDLE_INTERVAL_MS))

        jump_ts = start_ts + 7 * CANDLE_INTERVAL_MS
        engine.process_raw_message(_make_sample_ws_candle(jump_ts))
        for i in range(1, 6):
            engine.process_raw_message(_make_sample_ws_candle(jump_ts + i * CANDLE_INTERVAL_MS))

        assert not engine.is_research_eligible

        store = engine.recovery_store
        gap = engine.gap_detector.gaps[0]
        cand1 = _make_validated_candle(gap.missing_start_ts)
        cand2 = _make_validated_candle(gap.missing_start_ts + CANDLE_INTERVAL_MS)

        e1_h = store.compute_entry_integrity_hash("REC-1", gap.gap_id, 0, "0" * 64, cand1.compute_sha256())
        e1 = RecoveredEvidenceEntry("REC-1", gap.gap_id, 0, "0" * 64, cand1.compute_sha256(), e1_h, "2026-10-17T00:00:00Z", {}, cand1.canonical_dict())
        e2_h = store.compute_entry_integrity_hash("REC-1", gap.gap_id, 1, e1_h, cand2.compute_sha256())
        e2 = RecoveredEvidenceEntry("REC-1", gap.gap_id, 1, e1_h, cand2.compute_sha256(), e2_h, "2026-10-17T00:00:00Z", {}, cand2.canonical_dict())

        with open(store.journal_file, "w", encoding="utf-8") as f:
            f.write(e1.to_json() + "\n" + e2.to_json() + "\n")

        engine.evidence_store.close()

        engine_restarted = MarketCaptureEngineV080(config=cfg, transport=MockMarketDataTransport())
        assert not engine_restarted.gap_detector.gaps[0].recovered
        assert engine_restarted.is_research_eligible is False
    finally:
        if engine_restarted is not None:
            engine_restarted.evidence_store.close()
        else:
            engine.evidence_store.close()


# 27. Original raw evidence remains byte-for-byte unchanged
def test_27_original_raw_evidence_remains_byte_for_byte_unchanged(temp_capture_dirs):
    raw_market, quarantine = temp_capture_dirs
    tmp_path = raw_market.parent
    cfg = ShadowCollectorConfig(shadow_data_dir=tmp_path / "live_capture", full_warmup_bars=5)
    cfg.ensure_directories()
    engine = MarketCaptureEngineV080(config=cfg, transport=MockMarketDataTransport())

    try:
        engine.process_raw_message(_make_sample_ws_candle(BASE_TS))
        engine.process_raw_message(_make_sample_ws_candle(BASE_TS + 2 * CANDLE_INTERVAL_MS))

        raw_file = engine.evidence_store.evidence_file
        raw_bytes_before = raw_file.read_bytes()
        raw_sha_before = hashlib.sha256(raw_bytes_before).hexdigest()

        gap_id = engine.gap_detector.gaps[0].gap_id
        mock_rest = MockRestAdapter(klines_data=[_make_raw_kline(BASE_TS + CANDLE_INTERVAL_MS)])
        ok, _ = engine.recover_gap_via_rest(gap_id, mock_rest)
        assert ok is True

        raw_bytes_after = raw_file.read_bytes()
        raw_sha_after = hashlib.sha256(raw_bytes_after).hexdigest()

        assert raw_sha_before == raw_sha_after, "Original raw_candles_BTCUSDT_5m.jsonl was modified!"
    finally:
        engine.evidence_store.close()


# 28. Frozen 29/29 canonical hashes remain identical
def test_28_frozen_29_of_29_canonical_hashes_remain_identical():
    res = verify_sprint07_freeze()
    assert res["verified"] is True
    assert res["status"] == "FREEZE_VERIFIED"
    assert res["canonical_hashes_verified"] == 29
    assert len(res["canonical_mismatches"]) == 0
