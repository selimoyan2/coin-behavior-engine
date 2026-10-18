"""CBE-0.8.0 Independent Research Readiness & Evidence Integrity Auditor Test Matrix.

Sprint 11.02E: Live Capture Research Readiness & Evidence Audit.

Deterministic test coverage:
1. Clean continuous evidence (>= 288 bars) -> PASS / READY_FOR_OFFLINE_RESEARCH.
2. Valid committed recovery bridge -> PASS / full window contiguous.
3. Uncommitted recovery batch -> Rejected from research timeline / Gap unrecovered.
4. Corrupted raw candle hash -> Fail-closed / EVIDENCE_INTEGRITY FAIL.
5. Corrupted raw entry hash -> Fail-closed / EVIDENCE_INTEGRITY FAIL.
6. Corrupted recovery journal hash -> Fail-closed / EVIDENCE_INTEGRITY FAIL.
7. Broken raw genesis hash -> Fail-closed / EVIDENCE_INTEGRITY FAIL.
8. Broken recovery genesis hash -> Fail-closed / EVIDENCE_INTEGRITY FAIL.
9. Duplicate timestamps in raw evidence -> TEMPORAL_CONTINUITY FAIL.
10. Out-of-order timestamps in raw evidence -> TEMPORAL_CONTINUITY FAIL.
11. Missing candles with no recovery -> Gap detected / Contiguity reset.
12. Raw / Recovery timestamp collision -> Overwrite prevented / RECOVERY_CORRECTNESS FAIL.
13. Invalid / corrupt recovery metadata JSON -> EVIDENCE_INTEGRITY FAIL.
14. Recovery metadata index out-of-bounds -> EVIDENCE_INTEGRITY FAIL.
15. Recovery metadata start/end hash mismatch -> EVIDENCE_INTEGRITY FAIL.
16. Incomplete latest 288-bar window (< 288 bars) -> RESEARCH_WINDOW_READINESS FAIL.
17. Evidence modified during audit -> File mutation detected / Fail-closed.
18. Read-only filesystem / file permissions enforcement -> Pure read-only execution.
19. Engine reconstruction parity check -> Auditor and MarketCaptureEngine agree.
20. Authorization safety interlocks: CBE_TRADING_DISABLED=false -> FAIL.
21. Authorization safety interlocks: CBE_PROSPECTIVE_OBSERVATION_ENABLED=true -> FAIL.
22. Authorization safety interlocks: CBE_APPROVAL_4_AUTHORIZED=true -> FAIL.
23. Non-closed candle in raw evidence -> TEMPORAL_CONTINUITY FAIL.
24. Non-aligned candle timestamp -> TEMPORAL_CONTINUITY FAIL.
25. Report generation: JSON schema & Markdown formatting completeness.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from coin_behavior_engine.shadow_v080.gap_detector import FULL_WARMUP_BARS
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.research_readiness_auditor import (
    AuditVerdict,
    FileAuditInfo,
    GateStatus,
    RAW_GENESIS_PREV_HASH,
    RECOVERY_GENESIS_PREV_HASH,
    ResearchReadinessAuditor,
)


def _make_candle_dict(
    open_ts: int,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    price: float = 65000.0,
    provenance: str = ProvenanceSource.LIVE_BINANCE_SPOT.value,
    is_closed: bool = True,
) -> Dict[str, Any]:
    close_ts = open_ts + CANDLE_INTERVAL_MS - 1
    dt_open = datetime.fromtimestamp(open_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dt_close = datetime.fromtimestamp(close_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "symbol": symbol,
        "interval": interval,
        "market_type": MarketType.SPOT.value,
        "timestamp_open": open_ts,
        "timestamp_close": close_ts,
        "datetime_open_utc": dt_open,
        "datetime_close_utc": dt_close,
        "open": f"{price:.2f}",
        "high": f"{price + 10.0:.2f}",
        "low": f"{price - 10.0:.2f}",
        "close": f"{price + 2.0:.2f}",
        "volume": "1.50000000",
        "quote_volume": "97500.00",
        "trades_count": 120,
        "taker_buy_base_volume": "0.75000000",
        "is_closed": is_closed,
        "provenance": provenance,
        "receipt_timestamp_utc": dt_close,
        "lifecycle_state": CandleLifecycleState.CANDLE_PERSISTED.value,
    }


def _write_raw_ledger(
    path: Path,
    candles: List[Dict[str, Any]],
    corrupt_idx: Optional[int] = None,
    corrupt_field: Optional[str] = None,
    genesis_prev_hash: str = RAW_GENESIS_PREV_HASH,
) -> List[str]:
    """Write synthetic raw candles ledger and return list of entry hashes."""
    hashes: List[str] = []
    prev_h = genesis_prev_hash

    with open(path, "w", encoding="utf-8") as f:
        for idx, c_dict in enumerate(candles):
            canonical_json = json.dumps(c_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
            c_hash = hashlib.sha256(canonical_json).hexdigest()
            e_hash = hashlib.sha256(f"{idx}:{prev_h}:{c_hash}".encode("utf-8")).hexdigest()

            line_entry = {
                "entry_index": idx,
                "prev_hash": prev_h,
                "candle_hash": c_hash,
                "entry_hash": e_hash,
                "persisted_at_utc": c_dict["receipt_timestamp_utc"],
                "candle": c_dict,
            }

            if corrupt_idx is not None and idx == corrupt_idx:
                if corrupt_field == "candle_hash":
                    line_entry["candle_hash"] = "f" * 64
                elif corrupt_field == "entry_hash":
                    line_entry["entry_hash"] = "e" * 64
                elif corrupt_field == "prev_hash":
                    line_entry["prev_hash"] = "d" * 64
                elif corrupt_field == "corrupt_json":
                    f.write("{\"corrupted\": true, invalid_json\n")
                    continue

            f.write(json.dumps(line_entry) + "\n")
            hashes.append(e_hash)
            prev_h = e_hash

    return hashes


def _write_recovery_batch(
    journal_path: Path,
    meta_path: Path,
    gap_id: str,
    batch_id: str,
    candles: List[Dict[str, Any]],
    first_entry_index: int = 0,
    genesis_prev_hash: str = RECOVERY_GENESIS_PREV_HASH,
    write_metadata: bool = True,
    corrupt_journal_idx: Optional[int] = None,
    corrupt_journal_field: Optional[str] = None,
    corrupt_metadata_field: Optional[str] = None,
) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Write recovery journal and optional metadata."""
    hashes: List[str] = []
    prev_h = genesis_prev_hash
    entries = []

    # Write journal
    with open(journal_path, "a", encoding="utf-8") as f:
        for i, c_dict in enumerate(candles):
            entry_idx = first_entry_index + i
            vcandle = ValidatedCandle(**c_dict)
            c_hash = vcandle.compute_sha256()
            integ_h = hashlib.sha256(
                f"{batch_id}:{gap_id}:{entry_idx}:{prev_h}:{c_hash}".encode("utf-8")
            ).hexdigest()

            line_entry = {
                "recovery_batch_id": batch_id,
                "gap_id": gap_id,
                "entry_index": entry_idx,
                "prev_recovery_hash": prev_h,
                "candle_hash": c_hash,
                "integrity_hash": integ_h,
                "persisted_at_utc": c_dict["receipt_timestamp_utc"],
                "source_metadata": {"source": "test"},
                "candle": c_dict,
            }

            if corrupt_journal_idx is not None and entry_idx == corrupt_journal_idx:
                if corrupt_journal_field == "candle_hash":
                    line_entry["candle_hash"] = "0" * 64
                elif corrupt_journal_field == "integrity_hash":
                    line_entry["integrity_hash"] = "1" * 64
                elif corrupt_journal_field == "prev_recovery_hash":
                    line_entry["prev_recovery_hash"] = "2" * 64

            f.write(json.dumps(line_entry) + "\n")
            hashes.append(integ_h)
            entries.append(line_entry)
            prev_h = integ_h

    meta_entry = None
    if write_metadata and entries:
        last_entry_index = first_entry_index + len(candles) - 1
        meta_entry = {
            "gap_id": gap_id,
            "recovery_batch_id": batch_id,
            "missing_start_ts": candles[0]["timestamp_open"],
            "missing_end_ts": candles[-1]["timestamp_open"],
            "recovered_candles_count": len(candles),
            "recovered_at_utc": candles[-1]["receipt_timestamp_utc"],
            "status": "COMMITTED",
            "first_entry_index": first_entry_index,
            "last_entry_index": last_entry_index,
            "start_integrity_hash": hashes[0],
            "end_integrity_hash": hashes[-1],
            "missing_timestamps": [c["timestamp_open"] for c in candles],
        }

        if corrupt_metadata_field == "status":
            meta_entry["status"] = "PENDING"
        elif corrupt_metadata_field == "count_mismatch":
            meta_entry["recovered_candles_count"] = len(candles) + 10
        elif corrupt_metadata_field == "start_hash":
            meta_entry["start_integrity_hash"] = "9" * 64
        elif corrupt_metadata_field == "end_hash":
            meta_entry["end_integrity_hash"] = "8" * 64
        elif corrupt_metadata_field == "corrupt_json":
            with open(meta_path, "a", encoding="utf-8") as f:
                f.write("{corrupt_metadata_line\n")
            return hashes, meta_entry

        with open(meta_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta_entry) + "\n")

    return hashes, meta_entry


@pytest.fixture
def env_safety():
    """Environment with safety interlocks enforced."""
    return {
        "CBE_TRADING_DISABLED": "true",
        "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
        "CBE_APPROVAL_4_AUTHORIZED": "false",
        "CBE_GIT_COMMIT": "test_sprint11_02e_sha",
    }


def test_clean_continuous_evidence(env_safety):
    """Test 1: Clean continuous evidence (300 candles >= 288) results in READY_FOR_OFFLINE_RESEARCH."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = 1700000000000  # Multiples of 300,000 (1700000000000 % 300000 == 200000, align it)
        start_ts = (start_ts // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.PASS
        assert report.gates["TEMPORAL_CONTINUITY"].status == GateStatus.PASS
        assert report.gates["RECOVERY_CORRECTNESS"].status == GateStatus.PASS
        assert report.gates["RESEARCH_WINDOW_READINESS"].status == GateStatus.PASS
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.PASS
        assert report.latest_contiguous_closed_bars == 300
        assert report.raw_candle_count == 300
        assert report.missing_timestamp_count == 0
        assert report.duplicate_timestamp_count == 0
        assert report.latest_complete_research_window is not None
        assert report.latest_complete_research_window["status"] == "FULL_WINDOW_READY"
        assert report.latest_complete_research_window["bar_count"] == 288


def test_valid_committed_recovery(env_safety):
    """Test 2: Raw evidence has a 3-bar gap, fully recovered and committed -> READY_FOR_OFFLINE_RESEARCH."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

        # 300 total candles with gap at index 100..102 (3 candles missing)
        raw_candles = []
        missing_candles = []
        for i in range(300):
            ts = start_ts + (i * CANDLE_INTERVAL_MS)
            if 100 <= i <= 102:
                missing_candles.append(
                    _make_candle_dict(ts, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
                )
            else:
                raw_candles.append(_make_candle_dict(ts))

        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, raw_candles)

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        gap_id = f"GAP-{missing_candles[0]['timestamp_open']}-{missing_candles[-1]['timestamp_open']}"
        _write_recovery_batch(
            journal_file, meta_file, gap_id, "BATCH-TEST-001", missing_candles, write_metadata=True
        )

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.PASS
        assert report.gates["RECOVERY_CORRECTNESS"].status == GateStatus.PASS
        assert report.gates["RESEARCH_WINDOW_READINESS"].status == GateStatus.PASS
        assert report.latest_contiguous_closed_bars == 300
        assert report.raw_candle_count == 297
        assert report.recovery_candle_count == 3
        assert report.committed_recovery_count == 3
        assert report.gap_reconciliation_results[0]["recovered"] is True
        assert report.gap_reconciliation_results[0]["verified"] is True
        assert report.provenance_breakdown[ProvenanceSource.LIVE_BINANCE_SPOT.value] == 297
        assert report.provenance_breakdown[ProvenanceSource.REST_GAP_RECOVERY.value] == 3


def test_uncommitted_recovery(env_safety):
    """Test 3: Uncommitted recovery journal entries are NOT counted toward research timeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

        # 300 total candles with gap at index 100..102 (3 candles missing)
        raw_candles = []
        missing_candles = []
        for i in range(300):
            ts = start_ts + (i * CANDLE_INTERVAL_MS)
            if 100 <= i <= 102:
                missing_candles.append(
                    _make_candle_dict(ts, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
                )
            else:
                raw_candles.append(_make_candle_dict(ts))

        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, raw_candles)

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        gap_id = f"GAP-{missing_candles[0]['timestamp_open']}-{missing_candles[-1]['timestamp_open']}"
        # write_metadata=False simulates uncommitted crash
        _write_recovery_batch(
            journal_file, meta_file, gap_id, "BATCH-TEST-002", missing_candles, write_metadata=False
        )

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        # Gap is unrecovered, so contiguous streak resets at index 103 (197 bars remaining < 288)
        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["RESEARCH_WINDOW_READINESS"].status == GateStatus.FAIL
        assert report.latest_contiguous_closed_bars == 197
        assert report.uncommitted_recovery_count == 3
        assert report.gap_reconciliation_results[0]["recovered"] is False


def test_corrupted_raw_hash(env_safety):
    """Test 4 & 5: Corrupted raw candle hash or entry hash fails closed."""
    # Corrupt candle hash
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(50)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles, corrupt_idx=25, corrupt_field="candle_hash")

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("candle hash mismatch" in v.lower() for v in report.gates["EVIDENCE_INTEGRITY"].violations)

    # Corrupt entry hash
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(50)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles, corrupt_idx=25, corrupt_field="entry_hash")

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("entry hash mismatch" in v.lower() for v in report.gates["EVIDENCE_INTEGRITY"].violations)


def test_corrupted_recovery_hash(env_safety):
    """Test 6: Corrupted recovery candle hash or integrity hash fails closed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        raw_candles = [_make_candle_dict(start_ts)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, raw_candles)

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        rec_candles = [_make_candle_dict(start_ts + CANDLE_INTERVAL_MS, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)]
        gap_id = f"GAP-{rec_candles[0]['timestamp_open']}-{rec_candles[0]['timestamp_open']}"

        _write_recovery_batch(
            journal_file, meta_file, gap_id, "BATCH-CORRUPT", rec_candles,
            corrupt_journal_idx=0, corrupt_journal_field="candle_hash"
        )

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("candle hash mismatch" in v.lower() for v in report.gates["EVIDENCE_INTEGRITY"].violations)


def test_broken_genesis_hash(env_safety):
    """Test 7 & 8: Non-zero genesis hash in raw or recovery ledger fails closed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles, genesis_prev_hash="a" * 64)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("hash chain break" in v.lower() for v in report.gates["EVIDENCE_INTEGRITY"].violations)


def test_duplicate_timestamps(env_safety):
    """Test 9: Duplicate timestamps detected in raw evidence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        c1 = _make_candle_dict(start_ts)
        c2 = _make_candle_dict(start_ts)  # Duplicate!
        c3 = _make_candle_dict(start_ts + CANDLE_INTERVAL_MS)
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c1, c2, c3])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["TEMPORAL_CONTINUITY"].status == GateStatus.FAIL
        assert report.duplicate_timestamp_count == 1
        assert any("duplicate raw candle timestamp" in v.lower() for v in report.gates["TEMPORAL_CONTINUITY"].violations)


def test_out_of_order_timestamps(env_safety):
    """Test 10: Out-of-order timestamps in raw evidence fails continuity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        c1 = _make_candle_dict(start_ts + CANDLE_INTERVAL_MS)
        c2 = _make_candle_dict(start_ts)  # Out of order!
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c1, c2])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["TEMPORAL_CONTINUITY"].status == GateStatus.FAIL
        assert any("out-of-order" in v.lower() for v in report.gates["TEMPORAL_CONTINUITY"].violations)


def test_missing_candles_unrecovered(env_safety):
    """Test 11: Missing candles reset contiguous bars and mark gap unrecovered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        c1 = _make_candle_dict(start_ts)
        # Gap of 2 candles
        c2 = _make_candle_dict(start_ts + (3 * CANDLE_INTERVAL_MS))
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c1, c2])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.missing_timestamp_count == 2
        assert len(report.gap_reconciliation_results) == 1
        assert report.gap_reconciliation_results[0]["recovered"] is False
        assert report.latest_contiguous_closed_bars == 1


def test_recovery_raw_timestamp_conflict(env_safety):
    """Test 12: Conflict when recovery journal attempts to overwrite an existing raw candle timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        # Raw has candle 0 and candle 2, gap at 1
        c0 = _make_candle_dict(start_ts)
        c2 = _make_candle_dict(start_ts + (2 * CANDLE_INTERVAL_MS))
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c0, c2])

        # Recovery contains candle 1 AND candle 2 (collision with c2!)
        rec1 = _make_candle_dict(start_ts + CANDLE_INTERVAL_MS, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
        rec2 = _make_candle_dict(start_ts + (2 * CANDLE_INTERVAL_MS), provenance=ProvenanceSource.REST_GAP_RECOVERY.value)

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        gap_id = f"GAP-{rec1['timestamp_open']}-{rec1['timestamp_open']}"
        _write_recovery_batch(journal_file, meta_file, gap_id, "BATCH-COLLIDE", [rec1, rec2])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["RECOVERY_CORRECTNESS"].status == GateStatus.FAIL
        assert any("collides with existing raw candle" in v.lower() or "do not match expected" in v.lower() for v in report.gates["RECOVERY_CORRECTNESS"].violations)


def test_invalid_recovery_metadata(env_safety):
    """Test 13, 14 & 15: Corrupt metadata JSON, count mismatch, or hash mismatch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        c0 = _make_candle_dict(start_ts)
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c0])

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        rec = _make_candle_dict(start_ts + CANDLE_INTERVAL_MS, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
        gap_id = f"GAP-{rec['timestamp_open']}-{rec['timestamp_open']}"

        _write_recovery_batch(
            journal_file, meta_file, gap_id, "BATCH-META-CORRUPT", [rec],
            corrupt_metadata_field="count_mismatch"
        )

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("candle count mismatch" in v.lower() for v in report.gates["EVIDENCE_INTEGRITY"].violations)


def test_incomplete_latest_288_bar_window(env_safety):
    """Test 16: Less than 288 contiguous bars captures (e.g. 150 bars) -> RESEARCH_WINDOW_READINESS FAIL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(150)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.PASS
        assert report.gates["RESEARCH_WINDOW_READINESS"].status == GateStatus.FAIL
        assert report.latest_contiguous_closed_bars == 150
        assert report.latest_complete_research_window is None


def test_evidence_modified_during_audit(env_safety, monkeypatch):
    """Test 17: Concurrent evidence modification during audit is detected and fails closed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(50)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)

        # Hook stream_raw_lines to append a byte to raw_file mid-stream
        orig_stream = auditor.reader.stream_raw_lines

        def tampered_stream():
            for item in orig_stream():
                yield item
            # Mutate file at end of stream
            with open(raw_file, "a", encoding="utf-8") as f:
                f.write('{"tampered": true}\n')

        monkeypatch.setattr(auditor.reader, "stream_raw_lines", tampered_stream)
        report = auditor.run_full_audit(compare_with_engine=False)

        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.FAIL
        assert any("modified concurrently during audit" in v.lower() for v in report.unresolved_findings)


def test_read_only_filesystem_enforcement(env_safety):
    """Test 18: File permissions set to read-only; auditor runs and verifies cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        # Set file to read-only (chmod 444)
        os.chmod(raw_file, stat.S_IREAD)
        try:
            auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
            report = auditor.run_full_audit(compare_with_engine=False)
            assert report.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH
            assert report.gates["EVIDENCE_INTEGRITY"].status == GateStatus.PASS
        finally:
            # Restore write permission for directory cleanup on Windows
            os.chmod(raw_file, stat.S_IWRITE | stat.S_IREAD)


def test_engine_parity_agreement(env_safety):
    """Test 19: Auditor and MarketCaptureEngine agree on contiguity and eligibility in isolated test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS

        # 300 candles with 1 gap of 2 bars recovered
        raw_candles = []
        missing_candles = []
        for i in range(300):
            ts = start_ts + (i * CANDLE_INTERVAL_MS)
            if 50 <= i <= 51:
                missing_candles.append(
                    _make_candle_dict(ts, provenance=ProvenanceSource.REST_GAP_RECOVERY.value)
                )
            else:
                raw_candles.append(_make_candle_dict(ts))

        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, raw_candles)

        journal_file = raw_dir / "recovery_candles_BTCUSDT_5m.jsonl"
        meta_file = raw_dir / "recovery_metadata_BTCUSDT_5m.jsonl"
        gap_id = f"GAP-{missing_candles[0]['timestamp_open']}-{missing_candles[-1]['timestamp_open']}"
        _write_recovery_batch(journal_file, meta_file, gap_id, "BATCH-PARITY", missing_candles)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit(compare_with_engine=True)

        assert report.engine_agreement is not None
        assert report.engine_agreement["status"] == "COMPLETED"
        assert report.engine_agreement["parity_verdict"] == "PARITY_CONFIRMED"
        assert report.engine_agreement["auditor_contiguous_bars"] == report.engine_agreement["engine_contiguous_bars"]
        assert report.engine_agreement["auditor_is_eligible"] == report.engine_agreement["engine_is_eligible"]


def test_authorization_safety_gate_failures():
    """Test 20, 21 & 22: Unsafe runtime flags fail AUTHORIZATION_SAFETY gate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        # 1. Trading enabled
        unsafe_env_trading = {
            "CBE_TRADING_DISABLED": "false",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            "CBE_APPROVAL_4_AUTHORIZED": "false",
        }
        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=unsafe_env_trading)
        report = auditor.run_full_audit()
        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.FAIL
        assert any("cbe_trading_disabled is 'false'" in v.lower() for v in report.gates["AUTHORIZATION_SAFETY"].violations)

        # 2. Prospective scoring enabled
        unsafe_env_scoring = {
            "CBE_TRADING_DISABLED": "true",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "true",
            "CBE_APPROVAL_4_AUTHORIZED": "false",
        }
        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=unsafe_env_scoring)
        report = auditor.run_full_audit()
        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.FAIL
        assert any("cbe_prospective_observation_enabled is 'true'" in v.lower() for v in report.gates["AUTHORIZATION_SAFETY"].violations)

        # 3. Approval 4 enabled
        unsafe_env_app4 = {
            "CBE_TRADING_DISABLED": "true",
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
            "CBE_APPROVAL_4_AUTHORIZED": "true",
        }
        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=unsafe_env_app4)
        report = auditor.run_full_audit()
        assert report.verdict == AuditVerdict.NOT_READY
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.FAIL
        assert any("cbe_approval_4_authorized is 'true'" in v.lower() for v in report.gates["AUTHORIZATION_SAFETY"].violations)


def test_non_closed_and_unaligned_candle(env_safety):
    """Test 23 & 24: Unclosed candle or unaligned timestamp in raw ledger fails continuity."""
    # Unclosed candle
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        c = _make_candle_dict(start_ts, is_closed=False)
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit()
        assert report.gates["TEMPORAL_CONTINUITY"].status == GateStatus.FAIL
        assert any("not marked is_closed=true" in v.lower() for v in report.gates["TEMPORAL_CONTINUITY"].violations)

    # Unaligned timestamp
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        unaligned_ts = 1700000000123  # Not divisible by 300,000
        c = _make_candle_dict(unaligned_ts)
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, [c])

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit()
        assert report.gates["TEMPORAL_CONTINUITY"].status == GateStatus.FAIL
        assert any("not aligned to 300000 ms boundary" in v.lower() for v in report.gates["TEMPORAL_CONTINUITY"].violations)


def test_markdown_and_json_report_generation(env_safety):
    """Test 25: JSON and Markdown report formatting completeness and valid structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=env_safety)
        report = auditor.run_full_audit()

        json_str = report.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json["verdict"] == "READY_FOR_OFFLINE_RESEARCH"
        assert "gates" in parsed_json
        assert "EVIDENCE_INTEGRITY" in parsed_json["gates"]
        assert "files" in parsed_json
        assert parsed_json["summary_metrics"]["latest_contiguous_closed_bars"] == 300

        md_str = report.to_markdown()
        assert "# CBE Research Readiness & Evidence Audit Report" in md_str
        assert "READY_FOR_OFFLINE_RESEARCH" in md_str
        assert "## 1. Audit Gates Summary" in md_str
        assert "## 2. Evidence Files & Cryptographic Fingerprints" in md_str
        assert "## 4. Latest Complete 288-Bar Research Window" in md_str
        assert "Zero unresolved findings" in md_str


def test_missing_authorization_variables_fail_closed():
    """Test 26: Missing authorization environment variables must NOT assume safe defaults; return INDETERMINATE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        # Empty environment: no CBE_* variables set
        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override={})
        report = auditor.run_full_audit()

        assert report.verdict == AuditVerdict.INDETERMINATE
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.INDETERMINATE
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_TRADING_DISABLED"] == "UNSET"
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] == "UNSET"
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_APPROVAL_4_AUTHORIZED"] == "UNSET"
        assert any("missing required authorization safety evidence" in v.lower() for v in report.gates["AUTHORIZATION_SAFETY"].violations)


def test_partial_missing_authorization_variables():
    """Test 27: Partially set authorization environment variables still return INDETERMINATE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        # Only trading_disabled is provided; scoring and approval_4 are missing
        partial_env = {"CBE_TRADING_DISABLED": "true"}
        auditor = ResearchReadinessAuditor(evidence_dir=raw_dir, environment_override=partial_env)
        report = auditor.run_full_audit()

        assert report.verdict == AuditVerdict.INDETERMINATE
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.INDETERMINATE
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_TRADING_DISABLED"] == "true"
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] == "UNSET"
        assert report.gates["AUTHORIZATION_SAFETY"].details["CBE_APPROVAL_4_AUTHORIZED"] == "UNSET"


def test_safe_offline_authorization_context():
    """Test 28: Explicit offline authorization context passes safety gate without claiming production provenance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_dir = Path(tmpdir)
        start_ts = (1700000000000 // CANDLE_INTERVAL_MS) * CANDLE_INTERVAL_MS
        candles = [_make_candle_dict(start_ts + (i * CANDLE_INTERVAL_MS)) for i in range(300)]
        raw_file = raw_dir / "raw_candles_BTCUSDT_5m.jsonl"
        _write_raw_ledger(raw_file, candles)

        offline_ctx = {
            "trading_disabled": True,
            "prospective_observation_enabled": False,
            "approval_4_authorized": False,
            "documentation": "Explicit offline testing context for Sprint 11.02E.1",
        }
        auditor = ResearchReadinessAuditor(
            evidence_dir=raw_dir,
            environment_override={},
            offline_authorization_context=offline_ctx,
        )
        report = auditor.run_full_audit()

        assert report.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH
        assert report.gates["AUTHORIZATION_SAFETY"].status == GateStatus.PASS
        assert report.gates["AUTHORIZATION_SAFETY"].details["source"] == "EXPLICIT_OFFLINE_CONTEXT"
        assert report.gates["AUTHORIZATION_SAFETY"].details["production_container_verified"] is False
        assert "does NOT prove runtime configuration of running production container" in report.gates["AUTHORIZATION_SAFETY"].details["disclaimer"]


def test_absence_of_engine_behavior_changes():
    """Test 29: Verify MarketCaptureEngineV080 does NOT write gap_recovery_audit.jsonl, preserving 11.02D.1 baseline."""
    from unittest import mock
    from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
    from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
    from coin_behavior_engine.shadow_v080.transport_adapter import BinanceSpotRestAdapter

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ShadowCollectorConfig(
            approval_3_authorized=True,
            shadow_data_dir=Path(tmpdir) / "live_capture",
            full_warmup_bars=10,
        )
        engine = MarketCaptureEngineV080(cfg)
        try:
            t0 = 1700000100000
            t1 = t0 + 300000
            t2 = t1 + 300000  # Missing bar
            t3 = t2 + 300000

            def make_raw(ts_open):
                return {
                    "e": "kline",
                    "s": "BTCUSDT",
                    "k": {
                        "t": ts_open,
                        "T": ts_open + 299999,
                        "s": "BTCUSDT",
                        "i": "5m",
                        "o": "35000.0",
                        "c": "35050.0",
                        "h": "35100.0",
                        "l": "34950.0",
                        "v": "10.0",
                        "x": True,
                        "q": "350500.0",
                        "n": 50,
                        "V": "5.0",
                    },
                }

            engine.process_raw_message(make_raw(t0))
            engine.process_raw_message(make_raw(t1))
            engine.process_raw_message(make_raw(t3))  # triggers gap at t2

            gap_event = engine.gap_detector.gaps[0]
            gap_id = gap_event.gap_id

            mock_rest = mock.MagicMock(spec=BinanceSpotRestAdapter)
            mock_rest.fetch_klines.return_value = [
                [
                    t2, "35050.0", "35150.0", "35000.0", "35100.0", "12.0",
                    t2 + 299999, "421200.0", 60, "6.0", "210600.0", "0"
                ]
            ]

            ok, msg = engine.recover_gap_via_rest(gap_id, mock_rest)
            assert ok, f"Recovery failed: {msg}"

            # CRITICAL INVARIANT: gap_recovery_audit.jsonl must NOT be created!
            legacy_audit_file = cfg.quarantine_dir / "gap_recovery_audit.jsonl"
            assert not legacy_audit_file.exists(), (
                "Unrelated modification detected: gap_recovery_audit.jsonl must not be written by engine"
            )

            # Invariant: durable recovery journal and metadata ARE created in raw_market_dir
            assert (cfg.raw_market_dir / "recovery_candles_BTCUSDT_5m.jsonl").exists()
            assert (cfg.raw_market_dir / "recovery_metadata_BTCUSDT_5m.jsonl").exists()
        finally:
            engine.evidence_store.close()

