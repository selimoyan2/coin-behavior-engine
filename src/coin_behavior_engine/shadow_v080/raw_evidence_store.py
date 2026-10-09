"""CBE-0.8.0 Immutable Raw Market Evidence Store & Cryptographic Hash Chain.

Provides:
- Append-only, tamper-evident raw candle ledger (`raw_candles_BTCUSDT_5m.jsonl`).
- Continuous SHA-256 hash chaining (entry_hash = sha256(index:prev_hash:candle_hash)).
- Idempotent duplicate rejection and conflicting payload quarantine.
- Out-of-order record quarantine.
- Streaming line-by-line hash chain verification with strictly bounded memory.
- In-place forensic truncation of trailing EOF corruption without rewriting valid history.
- Dedicated binary quarantine backup and recovery audit logging.
- Mid-chain corruption fail-closed protection.
- Read-only filesystem and disk-write failure safety.
"""

from __future__ import annotations

import collections
import errno
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from coin_behavior_engine.shadow_v080.market_data_contract import (
    CandleLifecycleState,
    ValidatedCandle,
)

logger = logging.getLogger("cbe_raw_evidence_store")

GENESIS_PREV_HASH = "0" * 64
MAX_RECENT_CANDLES_CACHE = 1000


class EvidencePersistenceError(Exception):
    """Raised when writing evidence to disk fails."""
    pass


class ConflictingCandleError(Exception):
    """Raised when an incoming candle conflicts with previously accepted immutable evidence."""
    pass


class EvidenceCorruptionError(Exception):
    """Raised when mid-chain hash corruption or unrecoverable evidence tampering is detected."""
    pass


@dataclass
class MarketEvidenceEntry:
    entry_index: int
    prev_hash: str
    candle_hash: str
    entry_hash: str
    persisted_at_utc: str
    candle: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


class RawMarketEvidenceStore:
    """Manages append-only raw candle storage with cryptographic verification, quarantine, and bounded memory."""

    def __init__(self, raw_market_dir: Path, quarantine_dir: Path, symbol: str = "BTCUSDT", interval: str = "5m"):
        self.raw_market_dir = Path(raw_market_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.symbol = symbol
        self.interval = interval

        self.evidence_file = self.raw_market_dir / f"raw_candles_{self.symbol}_{self.interval}.jsonl"
        self.quarantine_file = self.quarantine_dir / f"quarantined_candles_{self.symbol}_{self.interval}.jsonl"

        self._entry_count: int = 0
        self._recent_candles: collections.deque[ValidatedCandle] = collections.deque(maxlen=MAX_RECENT_CANDLES_CACHE)
        self._recent_candles_by_ts: Dict[int, ValidatedCandle] = {}
        self._seen_timestamps: Set[int] = set()
        self._latest_open_ts: int = -1
        self._latest_entry_hash: str = GENESIS_PREV_HASH

        self._ensure_dirs()
        self.verify_and_recover_chain()

    def _ensure_dirs(self) -> None:
        self.raw_market_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _cache_candle(self, c: ValidatedCandle) -> None:
        """Cache candle in bounded recent cache, evicting oldest from map when deque fills."""
        if len(self._recent_candles) == self._recent_candles.maxlen:
            oldest = self._recent_candles[0]
            self._recent_candles_by_ts.pop(oldest.timestamp_open, None)
        self._recent_candles.append(c)
        self._recent_candles_by_ts[c.timestamp_open] = c

    @property
    def count(self) -> int:
        return self._entry_count

    @property
    def latest_entry_hash(self) -> str:
        return self._latest_entry_hash

    @property
    def latest_open_ts(self) -> int:
        return self._latest_open_ts

    def get_candle_by_timestamp(self, ts_open: int) -> Optional[ValidatedCandle]:
        """Lookup candle by timestamp. Uses in-memory cache first, falls back to disk scan if evicted."""
        if ts_open not in self._seen_timestamps:
            return None
        cached = self._recent_candles_by_ts.get(ts_open)
        if cached is not None:
            return cached
        return self._scan_disk_for_timestamp(ts_open)

    def _scan_disk_for_timestamp(self, ts_open: int) -> Optional[ValidatedCandle]:
        if not self.evidence_file.exists():
            return None
        with open(self.evidence_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    c_dict = data["candle"]
                    if c_dict["timestamp_open"] == ts_open:
                        return ValidatedCandle(
                            symbol=c_dict["symbol"],
                            interval=c_dict["interval"],
                            market_type=c_dict["market_type"],
                            timestamp_open=c_dict["timestamp_open"],
                            timestamp_close=c_dict["timestamp_close"],
                            datetime_open_utc=c_dict["datetime_open_utc"],
                            datetime_close_utc=c_dict["datetime_close_utc"],
                            open=str(c_dict["open"]),
                            high=str(c_dict["high"]),
                            low=str(c_dict["low"]),
                            close=str(c_dict["close"]),
                            volume=str(c_dict["volume"]),
                            quote_volume=str(c_dict.get("quote_volume", "0")),
                            trades_count=int(c_dict.get("trades_count", 0)),
                            taker_buy_base_volume=str(c_dict.get("taker_buy_base_volume", "0")),
                            is_closed=c_dict["is_closed"],
                            provenance=c_dict["provenance"],
                            receipt_timestamp_utc=c_dict["receipt_timestamp_utc"],
                            lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                        )
                except Exception:
                    continue
        return None

    def get_all_candles(self) -> List[ValidatedCandle]:
        """Read and return all validated candles from the evidence store."""
        if not self.evidence_file.exists():
            return []
        candles: List[ValidatedCandle] = []
        with open(self.evidence_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    c_dict = data["candle"]
                    c_obj = ValidatedCandle(
                        symbol=c_dict["symbol"],
                        interval=c_dict["interval"],
                        market_type=c_dict["market_type"],
                        timestamp_open=c_dict["timestamp_open"],
                        timestamp_close=c_dict["timestamp_close"],
                        datetime_open_utc=c_dict["datetime_open_utc"],
                        datetime_close_utc=c_dict["datetime_close_utc"],
                        open=str(c_dict["open"]),
                        high=str(c_dict["high"]),
                        low=str(c_dict["low"]),
                        close=str(c_dict["close"]),
                        volume=str(c_dict["volume"]),
                        quote_volume=str(c_dict.get("quote_volume", "0")),
                        trades_count=int(c_dict.get("trades_count", 0)),
                        taker_buy_base_volume=str(c_dict.get("taker_buy_base_volume", "0")),
                        is_closed=c_dict["is_closed"],
                        provenance=c_dict["provenance"],
                        receipt_timestamp_utc=c_dict["receipt_timestamp_utc"],
                        lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                    )
                    candles.append(c_obj)
                except Exception:
                    continue
        return candles

    def verify_and_recover_chain(self) -> bool:
        """Inspect and verify on-disk hash chain using line-by-line streaming without full-file in-memory loading.

        Recovers trailing partial writes at EOF via in-place forensic truncation without rewriting valid history.
        Fails closed on mid-chain corruption.
        """
        self._recent_candles.clear()
        self._recent_candles_by_ts.clear()
        self._seen_timestamps.clear()
        self._entry_count = 0
        self._latest_open_ts = -1
        self._latest_entry_hash = GENESIS_PREV_HASH

        if not self.evidence_file.exists():
            return True

        expected_prev = GENESIS_PREV_HASH
        valid_count = 0
        last_valid_offset = 0

        # Open in r+b mode for reading and in-place truncation
        with open(self.evidence_file, "r+b") as f:
            while True:
                line_offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break

                curr_offset = f.tell()
                # Check whether another line exists after this one
                next_peek = f.readline()
                is_trailing = (len(next_peek) == 0)
                f.seek(curr_offset)

                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    last_valid_offset = curr_offset
                    continue

                try:
                    data = json.loads(line_str)
                    e_idx = data["entry_index"]
                    prev_h = data["prev_hash"]
                    c_hash = data["candle_hash"]
                    e_hash = data["entry_hash"]
                    persisted_utc = data["persisted_at_utc"]
                    c_dict = data["candle"]

                    # Verify chain continuity
                    if e_idx != valid_count:
                        raise EvidenceCorruptionError(
                            f"Sequence index mismatch at offset {line_offset}: expected {valid_count}, got {e_idx}"
                        )
                    if prev_h != expected_prev:
                        raise EvidenceCorruptionError(
                            f"Hash chain break at offset {line_offset}: expected prev_hash {expected_prev}, got {prev_h}"
                        )

                    # Recompute candle hash
                    recomputed_c_hash = hashlib.sha256(
                        json.dumps(c_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    if c_hash != recomputed_c_hash:
                        raise EvidenceCorruptionError(
                            f"Candle hash mismatch at offset {line_offset}: stored {c_hash}, recomputed {recomputed_c_hash}"
                        )

                    # Recompute entry hash
                    expected_e_hash = hashlib.sha256(
                        f"{e_idx}:{prev_h}:{c_hash}".encode("utf-8")
                    ).hexdigest()
                    if e_hash != expected_e_hash:
                        raise EvidenceCorruptionError(
                            f"Entry hash mismatch at offset {line_offset}: stored {e_hash}, recomputed {expected_e_hash}"
                        )

                    # Reconstruct candle for bounded memory cache
                    c_obj = ValidatedCandle(
                        symbol=c_dict["symbol"],
                        interval=c_dict["interval"],
                        market_type=c_dict["market_type"],
                        timestamp_open=c_dict["timestamp_open"],
                        timestamp_close=c_dict["timestamp_close"],
                        datetime_open_utc=c_dict["datetime_open_utc"],
                        datetime_close_utc=c_dict["datetime_close_utc"],
                        open=str(c_dict["open"]),
                        high=str(c_dict["high"]),
                        low=str(c_dict["low"]),
                        close=str(c_dict["close"]),
                        volume=str(c_dict["volume"]),
                        quote_volume=str(c_dict.get("quote_volume", "0")),
                        trades_count=int(c_dict.get("trades_count", 0)),
                        taker_buy_base_volume=str(c_dict.get("taker_buy_base_volume", "0")),
                        is_closed=c_dict["is_closed"],
                        provenance=c_dict["provenance"],
                        receipt_timestamp_utc=c_dict["receipt_timestamp_utc"],
                        lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                    )

                    self._seen_timestamps.add(c_obj.timestamp_open)
                    self._cache_candle(c_obj)
                    self._latest_open_ts = max(self._latest_open_ts, c_obj.timestamp_open)
                    expected_prev = e_hash
                    valid_count += 1
                    last_valid_offset = curr_offset

                except (json.JSONDecodeError, KeyError, EvidenceCorruptionError) as e:
                    if is_trailing:
                        logger.warning(
                            f"Trailing corrupt/partial write detected at EOF offset {line_offset} ({e}). "
                            f"Initiating forensic quarantine backup and in-place truncation."
                        )
                        f.seek(line_offset)
                        corrupted_bytes = f.read()

                        # 1. Forensic binary copy in quarantine directory
                        ts_ms = int(time.time() * 1000)
                        forensic_file = self.quarantine_dir / f"forensic_trailing_corruption_{ts_ms}.bin"
                        forensic_file.write_bytes(corrupted_bytes)

                        # 2. Verify backup integrity
                        b_sha256 = hashlib.sha256(corrupted_bytes).hexdigest()
                        if not forensic_file.exists() or forensic_file.stat().st_size != len(corrupted_bytes):
                            raise EvidencePersistenceError("Forensic backup verification failed!")

                        # 3. Record recovery audit log entry
                        audit_file = self.quarantine_dir / "recovery_audit.jsonl"
                        audit_entry = {
                            "timestamp_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "action": "TRAILING_CORRUPTION_FORENSIC_TRUNCATE",
                            "backup_file": str(forensic_file.name),
                            "backup_sha256": b_sha256,
                            "truncated_bytes_count": len(corrupted_bytes),
                            "last_valid_offset": last_valid_offset,
                            "valid_entries_count": valid_count,
                            "error": str(e),
                        }
                        with open(audit_file, "a", encoding="utf-8") as af:
                            af.write(json.dumps(audit_entry, sort_keys=True) + "\n")
                            af.flush()
                            os.fsync(af.fileno())

                        # 4. In-place truncate without rewriting valid history
                        f.flush()
                        os.truncate(f.fileno(), last_valid_offset)
                        f.seek(last_valid_offset)
                        f.flush()
                        os.fsync(f.fileno())
                        break
                    else:
                        if isinstance(e, EvidenceCorruptionError):
                            raise
                        raise EvidenceCorruptionError(
                            f"Mid-file corrupt JSON at offset {line_offset}: {e}"
                        ) from e

        self._entry_count = valid_count
        self._latest_entry_hash = expected_prev
        logger.info(f"Verified {self._entry_count} market evidence entries streaming line-by-line. Chain intact.")
        return True

    def quarantine_record(self, reason: str, payload: Any) -> None:
        """Write quarantined payload to dedicated quarantine log."""
        record = {
            "quarantined_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": reason,
            "payload": payload,
        }
        try:
            with open(self.quarantine_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"Failed to write to quarantine file: {e}")

    def append_candle(
        self,
        candle: ValidatedCandle,
        force_disk_error: bool = False,
    ) -> Tuple[str, Optional[MarketEvidenceEntry]]:
        """Append a validated closed candle to the immutable ledger.

        Returns (status, entry):
        - ("PERSISTED", entry) on success.
        - ("DUPLICATE_IGNORED", existing_entry) if duplicate with identical payload.
        - ("CONFLICT_QUARANTINED", None) if conflicting duplicate detected.
        - ("OUT_OF_ORDER_QUARANTINED", None) if out-of-order record detected.
        """
        if candle is None:
            raise ValueError("candle cannot be None")

        # 1. Duplicate & Conflict Check
        if candle.timestamp_open in self._seen_timestamps:
            existing = self.get_candle_by_timestamp(candle.timestamp_open)
            if existing is not None:
                if existing.matches_payload(candle):
                    logger.info(f"Idempotent duplicate candle at open_ts={candle.timestamp_open} ignored.")
                    return "DUPLICATE_IGNORED", None
                else:
                    logger.error(
                        f"CONFLICTING DUPLICATE at open_ts={candle.timestamp_open}! "
                        f"Existing O={existing.open}, H={existing.high}, L={existing.low}, C={existing.close} "
                        f"vs Incoming O={candle.open}, H={candle.high}, L={candle.low}, C={candle.close}."
                    )
                    self.quarantine_record(
                        reason="CONFLICTING_PAYLOAD_FOR_EXISTING_TIMESTAMP",
                        payload={"existing": existing.canonical_dict(), "incoming": candle.canonical_dict()},
                    )
                    return "CONFLICT_QUARANTINED", None

        # 2. Out-of-Order Check
        if self._latest_open_ts > 0 and candle.timestamp_open < self._latest_open_ts:
            logger.warning(
                f"OUT-OF-ORDER candle: incoming open_ts={candle.timestamp_open} < latest={self._latest_open_ts}."
            )
            self.quarantine_record(
                reason="OUT_OF_ORDER_TIMESTAMP",
                payload=candle.canonical_dict(),
            )
            return "OUT_OF_ORDER_QUARANTINED", None

        # 3. Build Cryptographic Entry
        new_index = self._entry_count
        prev_hash = self._latest_entry_hash
        candle_dict = candle.canonical_dict()
        candle_hash = candle.compute_sha256()

        entry_hash = hashlib.sha256(
            f"{new_index}:{prev_hash}:{candle_hash}".encode("utf-8")
        ).hexdigest()

        persisted_at_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        entry = MarketEvidenceEntry(
            entry_index=new_index,
            prev_hash=prev_hash,
            candle_hash=candle_hash,
            entry_hash=entry_hash,
            persisted_at_utc=persisted_at_utc,
            candle=candle_dict,
        )

        # 4. Atomic Disk Persistence
        if force_disk_error:
            raise EvidencePersistenceError("Simulated disk-write failure (force_disk_error=True)")

        try:
            with open(self.evidence_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            if e.errno == errno.EROFS:
                raise EvidencePersistenceError(f"Read-only filesystem: cannot persist candle to {self.evidence_file}: {e}")
            raise EvidencePersistenceError(f"Disk persistence failed for {self.evidence_file}: {e}") from e

        # 5. Commit In-Memory State Only After Successful Disk Write
        candle.lifecycle_state = CandleLifecycleState.CANDLE_PERSISTED.value
        self._entry_count += 1
        self._seen_timestamps.add(candle.timestamp_open)
        self._cache_candle(candle)
        self._latest_entry_hash = entry_hash
        self._latest_open_ts = max(self._latest_open_ts, candle.timestamp_open)

        return "PERSISTED", entry
