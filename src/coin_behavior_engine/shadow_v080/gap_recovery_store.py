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


class RecoveryMetadataCorruptionError(RecoveryJournalCorruptionError):
    """Raised when recovery metadata file contains malformed, truncated, or corrupted records."""
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
    """Manages append-only gap recovery evidence, verification, and durability confirmation.
    
    Transaction State Machine:
    NEW -> VALIDATED -> JOURNAL_DURABLE -> JOURNAL_VERIFIED -> METADATA_COMMITTED -> COMMIT_VERIFIED -> RECOVERY_APPLIED
    """

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
        self._uncommitted_entries_by_gap: Dict[str, List[RecoveredEvidenceEntry]] = collections.defaultdict(list)

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

    @property
    def uncommitted_gaps_count(self) -> int:
        return len(self._uncommitted_entries_by_gap)

    def get_committed_gap(self, gap_id: str) -> Optional[GapRecoveryMetadata]:
        return self._committed_gaps.get(gap_id)

    def get_recovered_candle(self, timestamp_open: int) -> Optional[ValidatedCandle]:
        return self._recovered_candles_by_ts.get(timestamp_open)

    def get_recovered_candles_for_gap(self, gap_id: str) -> List[ValidatedCandle]:
        return list(self._recovered_candles_by_gap.get(gap_id, []))

    def get_uncommitted_entries_for_gap(self, gap_id: str) -> List[RecoveredEvidenceEntry]:
        return list(self._uncommitted_entries_by_gap.get(gap_id, []))

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
        """Verify cryptographic integrity of recovery journal and metadata, reconciling uncommitted batches."""
        self._entry_count = 0
        self._latest_entry_hash = RECOVERY_GENESIS_PREV_HASH
        self._recovered_candles_by_ts.clear()
        self._recovered_candles_by_gap.clear()
        self._uncommitted_entries_by_gap.clear()
        self._committed_gaps.clear()

        # Step 1: Strict loading of recovery metadata if exists (FAIL-CLOSED on error)
        metadata_by_gap: Dict[str, GapRecoveryMetadata] = {}
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    for line_idx, line in enumerate(f, 1):
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            meta_dict = json.loads(line_str)
                        except Exception as e:
                            raise RecoveryMetadataCorruptionError(
                                f"Corrupt JSON at recovery metadata line {line_idx}: {e}"
                            )
                        required_fields = [
                            "gap_id", "recovery_batch_id", "first_entry_index",
                            "last_entry_index", "recovered_candles_count",
                            "start_integrity_hash", "end_integrity_hash", "status"
                        ]
                        for rf in required_fields:
                            if rf not in meta_dict:
                                raise RecoveryMetadataCorruptionError(
                                    f"Missing required field '{rf}' in metadata line {line_idx}"
                                )
                        meta = GapRecoveryMetadata(**meta_dict)
                        if meta.gap_id in metadata_by_gap:
                            raise RecoveryMetadataCorruptionError(
                                f"Duplicate committed gap_id '{meta.gap_id}' in metadata line {line_idx}"
                            )
                        metadata_by_gap[meta.gap_id] = meta
            except RecoveryMetadataCorruptionError:
                raise
            except Exception as e:
                raise RecoveryMetadataCorruptionError(f"Failed to read recovery metadata file: {e}")

        # Step 2: Strict loading and cryptographic verification of recovery journal
        if not self.journal_file.exists():
            if metadata_by_gap:
                raise RecoveryMetadataCorruptionError(
                    "Recovery metadata exists but recovery journal file is missing."
                )
            return

        all_entries: List[RecoveredEvidenceEntry] = []
        expected_prev_hash = RECOVERY_GENESIS_PREV_HASH
        expected_index = 0

        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    entry_dict = json.loads(line_str)
                except Exception as e:
                    raise RecoveryJournalCorruptionError(
                        f"Corrupt JSON at recovery journal line {line_idx}: {e}"
                    )

                required_entry_fields = [
                    "entry_index", "prev_recovery_hash", "candle_hash",
                    "integrity_hash", "recovery_batch_id", "gap_id", "candle"
                ]
                for ref in required_entry_fields:
                    if ref not in entry_dict:
                        raise RecoveryJournalCorruptionError(
                            f"Missing required field '{ref}' at journal line {line_idx}"
                        )

                entry_idx = entry_dict["entry_index"]
                prev_h = entry_dict["prev_recovery_hash"]
                candle_h = entry_dict["candle_hash"]
                integrity_h = entry_dict["integrity_hash"]
                batch_id = entry_dict["recovery_batch_id"]
                gap_id = entry_dict["gap_id"]
                candle_dict = entry_dict["candle"]

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

                entry = RecoveredEvidenceEntry(
                    recovery_batch_id=batch_id,
                    gap_id=gap_id,
                    entry_index=entry_idx,
                    prev_recovery_hash=prev_h,
                    candle_hash=candle_h,
                    integrity_hash=integrity_h,
                    persisted_at_utc=entry_dict.get("persisted_at_utc", ""),
                    source_metadata=entry_dict.get("source_metadata", {}),
                    candle=candle.canonical_dict(),
                )
                all_entries.append(entry)
                expected_prev_hash = integrity_h
                expected_index += 1

        self._entry_count = expected_index
        self._latest_entry_hash = expected_prev_hash

        # Step 3: Cross-validate committed metadata against journal records
        committed_indices: Set[int] = set()

        for gap_id, meta in metadata_by_gap.items():
            first_idx = meta.first_entry_index
            last_idx = meta.last_entry_index
            count = meta.recovered_candles_count

            if count != (last_idx - first_idx + 1):
                raise RecoveryMetadataCorruptionError(
                    f"Metadata candle count mismatch for gap {gap_id}: count={count}, range=[{first_idx}..{last_idx}]"
                )
            if first_idx < 0 or last_idx >= len(all_entries) or first_idx > last_idx:
                raise RecoveryMetadataCorruptionError(
                    f"Metadata indexes out of journal bounds for gap {gap_id}: [{first_idx}..{last_idx}] (journal has {len(all_entries)} entries)"
                )

            if all_entries[first_idx].integrity_hash != meta.start_integrity_hash:
                raise RecoveryMetadataCorruptionError(
                    f"Metadata start_integrity_hash mismatch for gap {gap_id}"
                )
            if all_entries[last_idx].integrity_hash != meta.end_integrity_hash:
                raise RecoveryMetadataCorruptionError(
                    f"Metadata end_integrity_hash mismatch for gap {gap_id}"
                )

            gap_candles: List[ValidatedCandle] = []
            for i in range(first_idx, last_idx + 1):
                if i in committed_indices:
                    raise RecoveryMetadataCorruptionError(
                        f"Overlapping committed journal entry index {i} in gap {gap_id}"
                    )
                committed_indices.add(i)
                entry = all_entries[i]
                if entry.gap_id != gap_id:
                    raise RecoveryMetadataCorruptionError(
                        f"Journal gap_id '{entry.gap_id}' does not match metadata gap_id '{gap_id}' at index {i}"
                    )
                if entry.recovery_batch_id != meta.recovery_batch_id:
                    raise RecoveryMetadataCorruptionError(
                        f"Journal batch_id '{entry.recovery_batch_id}' does not match metadata batch_id '{meta.recovery_batch_id}' at index {i}"
                    )
                c = ValidatedCandle(**entry.candle)
                gap_candles.append(c)

            if meta.missing_timestamps:
                candle_ts = [c.timestamp_open for c in gap_candles]
                if candle_ts != meta.missing_timestamps:
                    raise RecoveryMetadataCorruptionError(
                        f"Metadata missing_timestamps mismatch for gap {gap_id}"
                    )

            self._committed_gaps[gap_id] = meta
            self._recovered_candles_by_gap[gap_id] = gap_candles
            for c in gap_candles:
                self._recovered_candles_by_ts[c.timestamp_open] = c

        # Step 4: Identify uncommitted journal entries
        for i, entry in enumerate(all_entries):
            if i not in committed_indices:
                self._uncommitted_entries_by_gap[entry.gap_id].append(entry)

        if self._uncommitted_entries_by_gap:
            total_uncommitted = sum(len(entries) for entries in self._uncommitted_entries_by_gap.values())
            logger.warning(
                f"Identified {total_uncommitted} uncommitted durable journal entries across gaps: "
                f"{list(self._uncommitted_entries_by_gap.keys())}. These will NOT count toward research eligibility until reconciled and committed."
            )

        logger.info(
            f"Recovery journal verified: {self._entry_count} entries, "
            f"{len(self._committed_gaps)} committed gaps, head_hash={self._latest_entry_hash[:16]}..."
        )

    def _readback_verify_journal(
        self,
        first_index: int,
        last_index: int,
        expected_entries: List[RecoveredEvidenceEntry],
        expected_candles: List[ValidatedCandle],
    ) -> None:
        """Read back newly persisted batch from disk and verify byte-for-byte / record-level integrity."""
        if not self.journal_file.exists():
            raise RecoveryStorePersistenceError("Recovery journal does not exist for read-back verification.")

        records_read: List[Dict[str, Any]] = []
        try:
            with open(self.journal_file, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    if line_idx >= first_index:
                        if line_idx <= last_index:
                            records_read.append(json.loads(line_str))
                        if line_idx > last_index:
                            break
        except Exception as e:
            raise RecoveryStorePersistenceError(f"Failed to read back recovery journal from disk: {e}") from e

        expected_count = last_index - first_index + 1
        if len(records_read) != expected_count:
            raise RecoveryStorePersistenceError(
                f"Read-back count mismatch: expected {expected_count} records [{first_index}..{last_index}], got {len(records_read)}"
            )

        for i, (rec, expected_entry, expected_cand) in enumerate(zip(records_read, expected_entries, expected_candles)):
            expected_idx = first_index + i
            if rec.get("entry_index") != expected_idx:
                raise RecoveryStorePersistenceError(
                    f"Read-back index mismatch at position {i}: got {rec.get('entry_index')}, expected {expected_idx}"
                )
            if rec.get("gap_id") != expected_entry.gap_id:
                raise RecoveryStorePersistenceError(
                    f"Read-back gap_id mismatch: got {rec.get('gap_id')}, expected {expected_entry.gap_id}"
                )
            if rec.get("recovery_batch_id") != expected_entry.recovery_batch_id:
                raise RecoveryStorePersistenceError(
                    f"Read-back recovery_batch_id mismatch: got {rec.get('recovery_batch_id')}, expected {expected_entry.recovery_batch_id}"
                )
            if rec.get("prev_recovery_hash") != expected_entry.prev_recovery_hash:
                raise RecoveryStorePersistenceError(
                    f"Read-back prev_recovery_hash mismatch: got {rec.get('prev_recovery_hash')}, expected {expected_entry.prev_recovery_hash}"
                )
            if rec.get("candle_hash") != expected_entry.candle_hash:
                raise RecoveryStorePersistenceError(
                    f"Read-back candle_hash mismatch: got {rec.get('candle_hash')}, expected {expected_entry.candle_hash}"
                )
            if rec.get("integrity_hash") != expected_entry.integrity_hash:
                raise RecoveryStorePersistenceError(
                    f"Read-back integrity_hash mismatch: got {rec.get('integrity_hash')}, expected {expected_entry.integrity_hash}"
                )

            c_dict = rec.get("candle", {})
            try:
                c = ValidatedCandle(**c_dict)
            except Exception as e:
                raise RecoveryStorePersistenceError(f"Read-back candle failed validation: {e}") from e

            if not c.matches_payload(expected_cand) or c.compute_sha256() != expected_cand.compute_sha256():
                raise RecoveryStorePersistenceError(
                    f"Read-back candle payload mismatch at ts={expected_cand.timestamp_open}"
                )

    def _readback_verify_metadata(self, expected_meta: GapRecoveryMetadata) -> None:
        """Read back committed metadata from disk and verify exact match with expected commit."""
        if not self.metadata_file.exists():
            raise RecoveryStorePersistenceError("Metadata file does not exist during read-back verification.")

        found = False
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    m_dict = json.loads(line_str)
                    if m_dict.get("gap_id") == expected_meta.gap_id and m_dict.get("recovery_batch_id") == expected_meta.recovery_batch_id:
                        found = True
                        if m_dict.get("first_entry_index") != expected_meta.first_entry_index:
                            raise RecoveryStorePersistenceError("Metadata read-back first_entry_index mismatch.")
                        if m_dict.get("last_entry_index") != expected_meta.last_entry_index:
                            raise RecoveryStorePersistenceError("Metadata read-back last_entry_index mismatch.")
                        if m_dict.get("start_integrity_hash") != expected_meta.start_integrity_hash:
                            raise RecoveryStorePersistenceError("Metadata read-back start_integrity_hash mismatch.")
                        if m_dict.get("end_integrity_hash") != expected_meta.end_integrity_hash:
                            raise RecoveryStorePersistenceError("Metadata read-back end_integrity_hash mismatch.")
                        if m_dict.get("recovered_candles_count") != expected_meta.recovered_candles_count:
                            raise RecoveryStorePersistenceError("Metadata read-back recovered_candles_count mismatch.")
                        if m_dict.get("missing_timestamps") != expected_meta.missing_timestamps:
                            raise RecoveryStorePersistenceError("Metadata read-back missing_timestamps mismatch.")
        except RecoveryStorePersistenceError:
            raise
        except Exception as e:
            raise RecoveryStorePersistenceError(f"Failed to read back metadata from disk: {e}") from e

        if not found:
            raise RecoveryStorePersistenceError(
                f"Metadata entry for gap {expected_meta.gap_id} not found on disk during read-back."
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

        Transaction State Machine:
        1. STAGE: NEW -> VALIDATED
           - Check idempotency against committed gaps using full canonical payload and SHA-256 hash.
           - Exact timestamp match verification.
           - Conflict detection against all existing recovered candles.
        2. STAGE: CRASH_RECONCILIATION
           - Check if uncommitted journal entries already exist for this gap.
           - If matching, reconcile safely and commit metadata.
        3. STAGE: JOURNAL_DURABLE
           - Append batch to recovery journal with flush + fsync.
        4. STAGE: JOURNAL_VERIFIED
           - Comprehensive read-back verification of appended journal records.
        5. STAGE: METADATA_COMMITTED
           - Append commit record to recovery metadata with flush + fsync.
        6. STAGE: COMMIT_VERIFIED
           - Read-back verification of metadata entry.
        7. STAGE: RECOVERY_APPLIED
           - Update in-memory indexes and state.
        """
        # 1. Idempotency check against COMMITTED gaps
        existing_meta = self._committed_gaps.get(gap_id)
        if existing_meta is not None:
            existing_candles = self._recovered_candles_by_gap.get(gap_id, [])
            if len(existing_candles) != len(recovered_candles):
                if recovered_candles:
                    first_exist = existing_candles[0] if existing_candles else None
                    if first_exist:
                        self._quarantine_conflicting_candle(recovered_candles[0], first_exist, gap_id)
                raise ConflictingRecoveryCandleError(
                    f"Recovery request for gap {gap_id} has candle count {len(recovered_candles)}, existing has {len(existing_candles)}"
                )
            for c_cand, c_exist in zip(recovered_candles, existing_candles):
                if (
                    c_cand.timestamp_open != c_exist.timestamp_open
                    or not c_exist.matches_payload(c_cand)
                ):
                    self._quarantine_conflicting_candle(c_cand, c_exist, gap_id)
                    raise ConflictingRecoveryCandleError(
                        f"Conflicting recovery candle for gap {gap_id} at ts={c_cand.timestamp_open}"
                    )
            logger.info(f"Gap {gap_id} is already durably committed with identical canonical payload. Skipping duplicate persistence.")
            return True, "ALREADY_COMMITTED"

        # 2. Exact Timestamp Verification
        cand_ts_list = [c.timestamp_open for c in recovered_candles]
        if cand_ts_list != missing_timestamps:
            return False, (
                f"TIMESTAMP_MISMATCH: Recovered timestamps {cand_ts_list} do not match "
                f"expected missing timestamps {missing_timestamps}."
            )

        # 3. Conflict Detection against existing recovered candles across all gaps
        for c in recovered_candles:
            ts = c.timestamp_open
            existing_c = self._recovered_candles_by_ts.get(ts)
            if existing_c is not None:
                if not existing_c.matches_payload(c):
                    self._quarantine_conflicting_candle(c, existing_c, gap_id)
                    raise ConflictingRecoveryCandleError(
                        f"Recovered candle at ts={ts} conflicts with existing recovered evidence."
                    )

        # 4. Crash Reconciliation: Check if there are UNCOMMITTED entries for this gap
        uncommitted_entries = self._uncommitted_entries_by_gap.get(gap_id, [])
        if uncommitted_entries:
            if len(uncommitted_entries) != len(recovered_candles):
                first_c = recovered_candles[0]
                exist_c = ValidatedCandle(**uncommitted_entries[0].candle)
                self._quarantine_conflicting_candle(first_c, exist_c, gap_id)
                raise ConflictingRecoveryCandleError(
                    f"Uncommitted entries for gap {gap_id} have {len(uncommitted_entries)} candles, request has {len(recovered_candles)}"
                )
            for entry, c_cand in zip(uncommitted_entries, recovered_candles):
                exist_c = ValidatedCandle(**entry.candle)
                if not exist_c.matches_payload(c_cand):
                    self._quarantine_conflicting_candle(c_cand, exist_c, gap_id)
                    raise ConflictingRecoveryCandleError(
                        f"Uncommitted entry for gap {gap_id} at ts={c_cand.timestamp_open} conflicts with candidate candle."
                    )

            first_entry_index = uncommitted_entries[0].entry_index
            last_entry_index = uncommitted_entries[-1].entry_index
            start_integrity_hash = uncommitted_entries[0].integrity_hash
            end_integrity_hash = uncommitted_entries[-1].integrity_hash
            actual_batch_id = uncommitted_entries[0].recovery_batch_id

            # Verify journal on disk
            self._readback_verify_journal(first_entry_index, last_entry_index, uncommitted_entries, recovered_candles)

            if force_disk_error:
                raise RecoveryStorePersistenceError("Simulated disk write failure during recovery persistence.")

            # Commit metadata
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            gap_meta = GapRecoveryMetadata(
                gap_id=gap_id,
                recovery_batch_id=actual_batch_id,
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

            meta_pos = self.metadata_file.stat().st_size if self.metadata_file.exists() else 0
            try:
                with open(self.metadata_file, "a", encoding="utf-8") as mf:
                    mf.write(gap_meta.to_json() + "\n")
                    mf.flush()
                    os.fsync(mf.fileno())
            except Exception as e:
                if self.metadata_file.exists():
                    try:
                        with open(self.metadata_file, "r+b") as mf_fix:
                            mf_fix.truncate(meta_pos)
                            mf_fix.flush()
                            os.fsync(mf_fix.fileno())
                    except Exception:
                        pass
                logger.critical(f"FATAL: Failed to write recovery metadata to disk: {e}")
                raise RecoveryStorePersistenceError(f"Disk write failure in recovery metadata: {e}") from e

            self._readback_verify_metadata(gap_meta)

            self._committed_gaps[gap_id] = gap_meta
            self._recovered_candles_by_gap[gap_id] = list(recovered_candles)
            for c in recovered_candles:
                self._recovered_candles_by_ts[c.timestamp_open] = c
            del self._uncommitted_entries_by_gap[gap_id]

            logger.info(f"Uncommitted gap {gap_id} successfully reconciled and committed: [{first_entry_index}..{last_entry_index}]")
            return True, "DURABLY_COMMITTED"

        # 5. Normal Append Path: construct journal entries
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

        # 6. Durable Append to Recovery Evidence Journal + fsync (STAGE: JOURNAL_DURABLE)
        try:
            journal_lines = "".join(e.to_json() + "\n" for e in entries_to_write)
            with open(self.journal_file, "a", encoding="utf-8") as jf:
                jf.write(journal_lines)
                jf.flush()
                os.fsync(jf.fileno())
        except Exception as e:
            logger.critical(f"FATAL: Failed to write recovery journal to disk: {e}")
            raise RecoveryStorePersistenceError(f"Disk write failure in recovery journal: {e}") from e

        # 7. Read-back verification (STAGE: JOURNAL_VERIFIED)
        try:
            self._readback_verify_journal(first_entry_index, last_entry_index, entries_to_write, recovered_candles)
        except Exception as e:
            # Track as uncommitted in-memory if journal was written
            self._uncommitted_entries_by_gap[gap_id] = entries_to_write
            self._entry_count = current_index
            self._latest_entry_hash = current_prev_hash
            raise RecoveryStorePersistenceError(f"Durability confirmation read-back failed: {e}") from e

        # 8. Commit Recovery Metadata + fsync (STAGE: METADATA_COMMITTED)
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

        meta_pos = self.metadata_file.stat().st_size if self.metadata_file.exists() else 0
        try:
            with open(self.metadata_file, "a", encoding="utf-8") as mf:
                mf.write(gap_meta.to_json() + "\n")
                mf.flush()
                os.fsync(mf.fileno())
        except Exception as e:
            if self.metadata_file.exists():
                try:
                    with open(self.metadata_file, "r+b") as mf_fix:
                        mf_fix.truncate(meta_pos)
                        mf_fix.flush()
                        os.fsync(mf_fix.fileno())
                except Exception:
                    pass
            # Journal is written, metadata failed: track as uncommitted
            self._uncommitted_entries_by_gap[gap_id] = entries_to_write
            self._entry_count = current_index
            self._latest_entry_hash = current_prev_hash
            logger.critical(f"FATAL: Failed to write recovery metadata to disk: {e}")
            raise RecoveryStorePersistenceError(f"Disk write failure in recovery metadata: {e}") from e

        # 9. Read-back verification of metadata (STAGE: COMMIT_VERIFIED)
        try:
            self._readback_verify_metadata(gap_meta)
        except Exception as e:
            self._uncommitted_entries_by_gap[gap_id] = entries_to_write
            self._entry_count = current_index
            self._latest_entry_hash = current_prev_hash
            raise RecoveryStorePersistenceError(f"Metadata read-back verification failed: {e}") from e

        # 10. Update in-memory state (STAGE: RECOVERY_APPLIED)
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

