"""CBE-0.8.0 Immutable Raw Market Evidence Store & Cryptographic Hash Chain.

Provides:
- Append-only, tamper-evident raw candle ledger (`raw_candles_BTCUSDT_5m.jsonl`).
- Continuous SHA-256 hash chaining (entry_hash = sha256(index:prev_hash:candle_hash)).
- Idempotent duplicate rejection and conflicting payload quarantine.
- Out-of-order record quarantine.
- Crash recovery with atomic truncation of partial trailing writes.
- Mid-chain corruption fail-closed protection.
- Read-only filesystem and disk-write failure safety.
"""

from __future__ import annotations

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
    """Manages append-only raw candle storage with cryptographic verification and quarantine."""

    def __init__(self, raw_market_dir: Path, quarantine_dir: Path, symbol: str = "BTCUSDT", interval: str = "5m"):
        self.raw_market_dir = Path(raw_market_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.symbol = symbol
        self.interval = interval

        self.evidence_file = self.raw_market_dir / f"raw_candles_{self.symbol}_{self.interval}.jsonl"
        self.quarantine_file = self.quarantine_dir / f"quarantined_candles_{self.symbol}_{self.interval}.jsonl"

        self._entries: List[MarketEvidenceEntry] = []
        self._seen_candles: Dict[int, ValidatedCandle] = {}
        self._latest_open_ts: int = -1
        self._latest_entry_hash: str = GENESIS_PREV_HASH

        self._ensure_dirs()
        self.verify_and_recover_chain()

    def _ensure_dirs(self) -> None:
        self.raw_market_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def latest_entry_hash(self) -> str:
        return self._latest_entry_hash

    @property
    def latest_open_ts(self) -> int:
        return self._latest_open_ts

    def get_candle_by_timestamp(self, ts_open: int) -> Optional[ValidatedCandle]:
        return self._seen_candles.get(ts_open)

    def get_all_candles(self) -> List[ValidatedCandle]:
        return list(self._seen_candles.values())

    def verify_and_recover_chain(self) -> bool:
        """Inspect and verify entire on-disk hash chain.

        Recovers trailing partial writes if power failure occurred mid-line.
        Fails closed on mid-chain corruption.
        """
        self._entries.clear()
        self._seen_candles.clear()
        self._latest_open_ts = -1
        self._latest_entry_hash = GENESIS_PREV_HASH

        if not self.evidence_file.exists():
            return True

        lines = self.evidence_file.read_text(encoding="utf-8").splitlines()
        if not lines:
            return True

        valid_entries: List[MarketEvidenceEntry] = []
        expected_prev = GENESIS_PREV_HASH

        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            is_last_line = (idx == len(lines) - 1)
            try:
                data = json.loads(line_str)
                e_idx = data["entry_index"]
                prev_h = data["prev_hash"]
                c_hash = data["candle_hash"]
                e_hash = data["entry_hash"]
                persisted_utc = data["persisted_at_utc"]
                c_dict = data["candle"]

                # Verify chain continuity
                if e_idx != len(valid_entries):
                    raise EvidenceCorruptionError(
                        f"Sequence index mismatch at line {idx}: expected {len(valid_entries)}, got {e_idx}"
                    )
                if prev_h != expected_prev:
                    raise EvidenceCorruptionError(
                        f"Hash chain break at line {idx}: expected prev_hash {expected_prev}, got {prev_h}"
                    )

                # Recompute candle hash
                recomputed_c_hash = hashlib.sha256(
                    json.dumps(c_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if c_hash != recomputed_c_hash:
                    raise EvidenceCorruptionError(
                        f"Candle hash mismatch at line {idx}: stored {c_hash}, recomputed {recomputed_c_hash}"
                    )

                # Recompute entry hash
                expected_e_hash = hashlib.sha256(
                    f"{e_idx}:{prev_h}:{c_hash}".encode("utf-8")
                ).hexdigest()
                if e_hash != expected_e_hash:
                    raise EvidenceCorruptionError(
                        f"Entry hash mismatch at line {idx}: stored {e_hash}, recomputed {expected_e_hash}"
                    )

                entry = MarketEvidenceEntry(
                    entry_index=e_idx,
                    prev_hash=prev_h,
                    candle_hash=c_hash,
                    entry_hash=e_hash,
                    persisted_at_utc=persisted_utc,
                    candle=c_dict,
                )
                valid_entries.append(entry)
                expected_prev = e_hash

                # Reconstruct ValidatedCandle in memory
                c_obj = ValidatedCandle(
                    symbol=c_dict["symbol"],
                    interval=c_dict["interval"],
                    market_type=c_dict["market_type"],
                    timestamp_open=c_dict["timestamp_open"],
                    timestamp_close=c_dict["timestamp_close"],
                    datetime_open_utc=c_dict["datetime_open_utc"],
                    datetime_close_utc=c_dict["datetime_close_utc"],
                    open=c_dict["open"],
                    high=c_dict["high"],
                    low=c_dict["low"],
                    close=c_dict["close"],
                    volume=c_dict["volume"],
                    quote_volume=c_dict.get("quote_volume", 0.0),
                    trades_count=c_dict.get("trades_count", 0),
                    taker_buy_base_volume=c_dict.get("taker_buy_base_volume", 0.0),
                    is_closed=c_dict["is_closed"],
                    provenance=c_dict["provenance"],
                    receipt_timestamp_utc=c_dict["receipt_timestamp_utc"],
                    lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                )
                self._seen_candles[c_obj.timestamp_open] = c_obj
                self._latest_open_ts = max(self._latest_open_ts, c_obj.timestamp_open)

            except (json.JSONDecodeError, KeyError) as e:
                if is_last_line:
                    logger.warning(f"Trailing corrupt/partial line detected at EOF ({e}); truncating valid prefix.")
                    self._truncate_file_to_entries(valid_entries)
                    break
                else:
                    raise EvidenceCorruptionError(
                        f"Mid-file corrupt JSON at line {idx}: {e}"
                    ) from e

        self._entries = valid_entries
        self._latest_entry_hash = expected_prev
        logger.info(f"Verified {len(self._entries)} market evidence entries. Chain intact.")
        return True

    def _truncate_file_to_entries(self, entries: List[MarketEvidenceEntry]) -> None:
        """Atomically overwrite file with only valid entries."""
        tmp_file = self.raw_market_dir / f".{self.evidence_file.name}.recover.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(e.to_json() + "\n")
        tmp_file.replace(self.evidence_file)

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
        existing = self._seen_candles.get(candle.timestamp_open)
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
        new_index = len(self._entries)
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
            # Append entry to file and flush to disk
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
        self._entries.append(entry)
        self._seen_candles[candle.timestamp_open] = candle
        self._latest_entry_hash = entry_hash
        self._latest_open_ts = max(self._latest_open_ts, candle.timestamp_open)

        return "PERSISTED", entry
