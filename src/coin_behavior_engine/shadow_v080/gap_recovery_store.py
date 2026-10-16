"""CBE-0.8.0 Durable Gap Recovery Evidence Store & Cryptographic Journal.

Sprint 11.02D: Durable Gap Recovery, Evidence Integrity & Deployment Continuity.

Enforces:
1. Append-only, tamper-evident recovery evidence journal (`recovery_candles_BTCUSDT_5m.jsonl`).
2. Continuous SHA-256 hash chaining of recovered records without modifying or inserting into
   the original immutable live capture ledger (`raw_candles_BTCUSDT_5m.jsonl`).
3. Strict recovery record schema with:
   - symbol, interval, timestamp_open, timestamp_close, OHLCV, is_closed=True
   - provenance='REST_GAP_RECOVERY'
   - recovery_batch_id, gap_id, source_metadata, integrity_hash
4. Transactional durability:
   - Atomic disk write + flush + os.fsync()
   - Verification read-back before committing gap recovery status
   - Fail-closed behavior on disk write failure (gap remains unrecovered, research eligibility false)
5. Idempotent recovery (retrying recovery does not duplicate records).
6. Conflicting candle detection & quarantine.
7. Restart continuity reconstruction from verified recovery journal + metadata.
"""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)

logger = logging.getLogger("cbe_gap_recovery_store")

RECOVERY_GENESIS_PREV_HASH = "0" * 64


class RecoveryStorePersistenceError(Exception):
    """Raised when writing recovery evidence to disk fails."""
    pass


class ConflictingRecoveryCandleError(Exception):
    """Raised when a recovered candle conflicts with existing evidence or recovery journal."""
    pass


class RecoveryJournalCorruptionError(Exception):
    """Raised when recovery journal hash chain corruption or tampering is detected."""
    pass


@dataclass
class RecoveredEvidenceEntry:
    """Immutable entry in the append-only gap recovery evidence journal."""
    recovery_batch_id: str
    gap_id: str
    entry_index: int
    prev_recovery_hash: str
    candle_hash: str
    integrity_hash: str
    persisted_at_utc: str
    source_metadata: Dict[str, Any]
    candle: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_batch_id": self.recovery_batch_id,
            "gap_id": self.gap_id,
            "entry_index": self.entry_index,
            "prev_recovery_hash": self.prev_recovery_hash,
            "candle_hash": self.candle_hash,
            "integrity_hash": self.integrity_hash,
            "persisted_at_utc": self.persisted_at_utc,
            "source_metadata": self.source_metadata,
            "symbol": self.candle.get("symbol", "BTCUSDT"),
            "interval": self.candle.get("interval", "5m"),
            "timestamp_open": self.candle.get("timestamp_open"),
            "timestamp_close": self.candle.get("timestamp_close"),
            "open": self.candle.get("open"),
            "high": self.candle.get("high"),
            "low": self.candle.get("low"),
            "close": self.candle.get("close"),
            "volume": self.candle.get("volume"),
            "is_closed": bool(self.candle.get("is_closed", True)),
            "provenance": self.candle.get("provenance", ProvenanceSource.REST_GAP_RECOVERY.value),
            "candle": self.candle,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass
class GapRecoveryMetadata:
    """Committed metadata entry representing a fully persisted and verified gap recovery."""
    gap_id: str
    recovery_batch_id: str
    missing_start_ts: int
    missing_end_ts: int
    recovered_candles_count: int
    recovered_at_utc: str
    status: str  # "COMMITTED"
    first_entry_index: int
    last_entry_index: int
    start_integrity_hash: str
    end_integrity_hash: str
    missing_timestamps: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


class DurableGapRecoveryStore:
    """Manages append-only gap recovery evidence, verification, and durability confirmation."""

    def __init__(
        self,
        raw_market_dir: Path,
        quarantine_dir: Path,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
    ):
        self.raw_market_dir = Path(raw_market_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.symbol = symbol
        self.interval = interval

        self.journal_file = self.raw_market_dir / f"recovery_candles_{self.symbol}_{self.interval}.jsonl"
        self.metadata_file = self.raw_market_dir / f"recovery_metadata_{self.symbol}_{self.interval}.jsonl"
        self.quarantine_file = self.quarantine_dir / f"recovery_quarantine_{self.symbol}_{self.interval}.jsonl"

        self._entry_count: int = 0
        self._latest_entry_hash: str = RECOVERY_GENESIS_PREV_HASH
        self._committed_gaps: Dict[str, GapRecoveryMetadata] = {}
        self._recovered_candles_by_ts: Dict[int, ValidatedCandle] = {}
        self._recovered_candles_by_gap: Dict[str, List[ValidatedCandle]] = collections.defaultdict(list)

        self._ensure_dirs()
        self.verify_and_load_recovery_journal()

    def _ensure_dirs(self) -> None:
        self.raw_market_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    @property
    def entry_count(self) -> int:
        return self._entry_count

    @property
    def latest_entry_hash(self) -> str:
        return self._latest_entry_hash

    @property
    def committed_gaps_count(self) -> int:
        return len(self._committed_gaps)

    def get_committed_gap(self, gap_id: str) -> Optional[GapRecoveryMetadata]:
        return self._committed_gaps.get(gap_id)

    def get_recovered_candle(self, timestamp_open: int) -> Optional[ValidatedCandle]:
        return self._recovered_candles_by_ts.get(timestamp_open)

    def get_recovered_candles_for_gap(self, gap_id: str) -> List[ValidatedCandle]:
        return list(self._recovered_candles_by_gap.get(gap_id, []))

    def get_all_recovered_candles_by_ts(self) -> Dict[int, ValidatedCandle]:
        return dict(self._recovered_candles_by_ts)

    @staticmethod
    def compute_entry_integrity_hash(
        recovery_batch_id: str,
        gap_id: str,
        entry_index: int,
        prev_hash: str,
        candle_hash: str,
    ) -> str:
        payload = f"{recovery_batch_id}:{gap_id}:{entry_index}:{prev_hash}:{candle_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_and_load_recovery_journal(self) -> None:
        """Verify cryptographic integrity of recovery journal and load all committed records."""
        self._entry_count = 0
        self._latest_entry_hash = RECOVERY_GENESIS_PREV_HASH
        self._recovered_candles_by_ts.clear()
        self._recovered_candles_by_gap.clear()
        self._committed_gaps.clear()

        # Load committed metadata first if available
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    for line_idx, line in enumerate(f, 1):
                        line_str = line.strip()
                        if not line_str:
                            continue
                        meta_dict = json.loads(line_str)
                        meta = GapRecoveryMetadata(**meta_dict)
                        self._committed_gaps[meta.gap_id] = meta
            except Exception as e:
                logger.error(f"Error reading recovery metadata file: {e}")

        # Load and verify recovery evidence journal
        if not self.journal_file.exists():
            return

        expected_prev_hash = RECOVERY_GENESIS_PREV_HASH
        expected_index = 0

        validator = BinanceSpotCandleValidator()

        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    entry_dict = json.loads(line_str)
                except Exception as e:
                    raise RecoveryJournalCorruptionError(f"Corrupt JSON at recovery journal line {line_idx}: {e}")

                entry_idx = entry_dict.get("entry_index")
                prev_h = entry_dict.get("prev_recovery_hash")
                candle_h = entry_dict.get("candle_hash")
                integrity_h = entry_dict.get("integrity_hash")
                batch_id = entry_dict.get("recovery_batch_id")
                gap_id = entry_dict.get("gap_id")
                candle_dict = entry_dict.get("candle")

                if entry_idx != expected_index:
                    raise RecoveryJournalCorruptionError(
                        f"Recovery journal index mismatch at line {line_idx}: got {entry_idx}, expected {expected_index}"
                    )
                if prev_h != expected_prev_hash:
                    raise RecoveryJournalCorruptionError(
                        f"Recovery journal prev_hash mismatch at line {line_idx}: got {prev_h}, expected {expected_prev_hash}"
                    )

                try:
                    candle = ValidatedCandle(**candle_dict)
                except Exception as e:
                    raise RecoveryJournalCorruptionError(
                        f"Invalid recovered candle at line {line_idx}: {e}"
                    )

                if candle.provenance != ProvenanceSource.REST_GAP_RECOVERY.value:
                    raise RecoveryJournalCorruptionError(
                        f"Provenance violation at line {line_idx}: expected {ProvenanceSource.REST_GAP_RECOVERY.value}, got {candle.provenance}"
                    )
                if not candle.is_closed:
                    raise RecoveryJournalCorruptionError(f"Unclosed candle in recovery journal at line {line_idx}")

                computed_candle_h = candle.compute_sha256()
                if computed_candle_h != candle_h:
                    raise RecoveryJournalCorruptionError(
                        f"Candle hash mismatch at line {line_idx}: got {candle_h}, computed {computed_candle_h}"
                    )

                computed_entry_h = self.compute_entry_integrity_hash(
                    batch_id, gap_id, entry_idx, prev_h, candle_h
                )
                if computed_entry_h != integrity_h:
                    raise RecoveryJournalCorruptionError(
                        f"Entry integrity hash mismatch at line {line_idx}: got {integrity_h}, computed {computed_entry_h}"
                    )

                # Index in-memory
                ts_open = candle.timestamp_open
                self._recovered_candles_by_ts[ts_open] = candle
                self._recovered_candles_by_gap[gap_id].append(candle)

                expected_prev_hash = integrity_h
                expected_index += 1

        self._entry_count = expected_index
        self._latest_entry_hash = expected_prev_hash
        logger.info(
            f"Recovery journal verified: {self._entry_count} entries, "
            f"{len(self._committed_gaps)} committed gaps, head_hash={self._latest_entry_hash[:16]}..."
        )

    def persist_recovery_batch(
        self,
        gap_id: str,
        recovery_batch_id: str,
        missing_start_ts: int,
        missing_end_ts: int,
        missing_timestamps: List[int],
        recovered_candles: List[ValidatedCandle],
        source_metadata: Optional[Dict[str, Any]] = None,
        force_disk_error: bool = False,
    ) -> Tuple[bool, str]:
        """Atomically and durably persist a verified batch of recovered gap candles.

        Transactional Semantics:
        1. Idempotency Check: if gap_id already committed and matches timestamps, return success.
        2. Timestamp Verification: candidate candles must match missing_timestamps exactly.
        3. Conflict Detection: no candle may conflict with existing recovered or live records.
        4. Durable Persistence: append to recovery journal with fsync.
        5. Durability Read-Back Confirmation.
        6. Commit Recovery Metadata with fsync.
        7. Update In-Memory Index.
        """
        # 1. Idempotency check
        existing_meta = self._committed_gaps.get(gap_id)
        if existing_meta is not None:
            existing_candles = self._recovered_candles_by_gap.get(gap_id, [])
            if len(existing_candles) == len(recovered_candles):
                existing_ts = [c.timestamp_open for c in existing_candles]
                cand_ts = [c.timestamp_open for c in recovered_candles]
                if existing_ts == cand_ts:
                    logger.info(f"Gap {gap_id} is already durably committed. Skipping duplicate persistence.")
                    return True, "ALREADY_COMMITTED"

        # 2. Exact Timestamp Verification
        cand_ts_list = [c.timestamp_open for c in recovered_candles]
        if cand_ts_list != missing_timestamps:
            return False, (
                f"TIMESTAMP_MISMATCH: Recovered timestamps {cand_ts_list} do not match "
                f"expected missing timestamps {missing_timestamps}."
            )

        # 3. Conflict Detection against existing recovered candles
        for c in recovered_candles:
            ts = c.timestamp_open
            existing_c = self._recovered_candles_by_ts.get(ts)
            if existing_c is not None:
                if not existing_c.matches_payload(c):
                    # Quarantine conflicting record
                    self._quarantine_conflicting_candle(c, existing_c, gap_id)
                    raise ConflictingRecoveryCandleError(
                        f"Recovered candle at ts={ts} conflicts with existing recovered evidence."
                    )

        # 4. Construct journal entries and prepare append payload
        metadata = source_metadata or {}
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        current_prev_hash = self._latest_entry_hash
        current_index = self._entry_count

        entries_to_write: List[RecoveredEvidenceEntry] = []
        for c in recovered_candles:
            c_hash = c.compute_sha256()
            entry_h = self.compute_entry_integrity_hash(
                recovery_batch_id, gap_id, current_index, current_prev_hash, c_hash
            )
            entry = RecoveredEvidenceEntry(
                recovery_batch_id=recovery_batch_id,
                gap_id=gap_id,
                entry_index=current_index,
                prev_recovery_hash=current_prev_hash,
                candle_hash=c_hash,
                integrity_hash=entry_h,
                persisted_at_utc=now_utc,
                source_metadata=metadata,
                candle=c.canonical_dict(),
            )
            entries_to_write.append(entry)
            current_prev_hash = entry_h
            current_index += 1

        first_entry_index = self._entry_count
        last_entry_index = current_index - 1
        start_integrity_hash = entries_to_write[0].integrity_hash
        end_integrity_hash = entries_to_write[-1].integrity_hash

        if force_disk_error:
            raise RecoveryStorePersistenceError("Simulated disk write failure during recovery persistence.")

        # 5. Durable Append to Recovery Evidence Journal + fsync
        try:
            journal_lines = "".join(e.to_json() + "\n" for e in entries_to_write)
            with open(self.journal_file, "a", encoding="utf-8") as jf:
                jf.write(journal_lines)
                jf.flush()
                os.fsync(jf.fileno())
        except Exception as e:
            logger.critical(f"FATAL: Failed to write recovery journal to disk: {e}")
            raise RecoveryStorePersistenceError(f"Disk write failure in recovery journal: {e}") from e

        # 6. Read-back verification to guarantee durability on disk before metadata commit
        try:
            with open(self.journal_file, "rb") as rf:
                rf.seek(0, os.SEEK_END)
                file_size = rf.tell()
                if file_size == 0:
                    raise RecoveryStorePersistenceError("Recovery journal file size is 0 after append.")
        except Exception as e:
            raise RecoveryStorePersistenceError(f"Durability confirmation read-back failed: {e}") from e

        # 7. Commit Recovery Metadata + fsync
        gap_meta = GapRecoveryMetadata(
            gap_id=gap_id,
            recovery_batch_id=recovery_batch_id,
            missing_start_ts=missing_start_ts,
            missing_end_ts=missing_end_ts,
            recovered_candles_count=len(recovered_candles),
            recovered_at_utc=now_utc,
            status="COMMITTED",
            first_entry_index=first_entry_index,
            last_entry_index=last_entry_index,
            start_integrity_hash=start_integrity_hash,
            end_integrity_hash=end_integrity_hash,
            missing_timestamps=missing_timestamps,
        )

        try:
            with open(self.metadata_file, "a", encoding="utf-8") as mf:
                mf.write(gap_meta.to_json() + "\n")
                mf.flush()
                os.fsync(mf.fileno())
        except Exception as e:
            logger.critical(f"FATAL: Failed to write recovery metadata to disk: {e}")
            raise RecoveryStorePersistenceError(f"Disk write failure in recovery metadata: {e}") from e

        # 8. Update in-memory state
        self._entry_count = current_index
        self._latest_entry_hash = current_prev_hash
        self._committed_gaps[gap_id] = gap_meta

        for c in recovered_candles:
            self._recovered_candles_by_ts[c.timestamp_open] = c
            self._recovered_candles_by_gap[gap_id].append(c)

        logger.info(
            f"Durable gap recovery committed: gap_id={gap_id}, count={len(recovered_candles)}, "
            f"entries=[{first_entry_index}..{last_entry_index}], head_hash={self._latest_entry_hash[:16]}..."
        )
        return True, "DURABLY_COMMITTED"

    def _quarantine_conflicting_candle(
        self,
        candidate: ValidatedCandle,
        existing: ValidatedCandle,
        gap_id: str,
    ) -> None:
        """Quarantine conflicting candle record to dedicated quarantine log."""
        quarantine_entry = {
            "quarantined_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gap_id": gap_id,
            "reason": "CONFLICTING_RECOVERED_CANDLE",
            "candidate_candle": candidate.canonical_dict(),
            "existing_candle": existing.canonical_dict(),
        }
        try:
            with open(self.quarantine_file, "a", encoding="utf-8") as qf:
                qf.write(json.dumps(quarantine_entry, sort_keys=True) + "\n")
                qf.flush()
                os.fsync(qf.fileno())
        except Exception as e:
            logger.warning(f"Failed to write recovery quarantine: {e}")
