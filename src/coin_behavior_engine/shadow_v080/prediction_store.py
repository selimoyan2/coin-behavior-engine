"""Immutable Forecast Event Store & Hash Chain for CBE-0.8.0 Shadow Collector.

Enforces:
- Append-only JSONL event storage.
- Cryptographic SHA-256 hash chaining from GENESIS_HASH.
- Duplicate event rejection (unique key: origin + branch + horizon).
- Explicit record labeling (HISTORICAL_REPLAY vs future PROSPECTIVE_SHADOW).
- Atomic disk flushing and durability guarantees.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cbe_prediction_store")

SHADOW_GENESIS_HASH = "GENESIS_CBE_0_8_0_SHADOW_CHAIN_2026"


class DuplicateForecastError(Exception):
    """Raised when an attempt is made to append an already stored forecast event."""
    pass


class EventTamperError(Exception):
    """Raised when hash chain or event serialization integrity fails."""
    pass


@dataclass
class ShadowPredictionEvent:
    event_id: str
    experiment_id: str
    protocol_version: str
    candidate_branch: str  # "candidate_c" or "candidate_e"
    forecast_origin_utc: str
    durable_commit_time_utc: str
    target_horizon: str  # "1h", "4h", "24h"
    target_maturity_utc: str
    feature_fingerprint: str
    component_hashes: Dict[str, str]
    data_quality: Dict[str, Any]
    point_prediction: float
    interval_80: Dict[str, float]
    interval_95: Dict[str, float]
    market_state: str
    record_label: str = "HISTORICAL_REPLAY"  # Default: strictly historical replay
    previous_event_hash: str = SHADOW_GENESIS_HASH
    record_hash: str = ""

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 digest of payload excluding record_hash."""
        d = asdict(self)
        d.pop("record_hash", None)
        canonical_bytes = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImmutablePredictionStoreV080:
    """Thread-safe append-only prediction store with cryptographic hash chaining."""

    def __init__(
        self,
        store_dir: Path,
        quarantine_dir: Optional[Path] = None,
        enable_sqlite_index: bool = True,
    ):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.store_dir / "shadow_predictions.jsonl"
        self.quarantine_dir = Path(quarantine_dir) if quarantine_dir else (self.store_dir / "quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.store_dir / "index_predictions.sqlite3"
        self._lock = threading.RLock()
        self._seen_keys: Set[str] = set()
        self._latest_hash: str = SHADOW_GENESIS_HASH
        self._event_count: int = 0
        self._is_chain_intact: bool = True
        self._unmatured_events: List[ShadowPredictionEvent] = []

        self.enable_sqlite_index = enable_sqlite_index
        self.durable_index: Optional[Any] = None
        if self.enable_sqlite_index:
            from coin_behavior_engine.shadow_v080.prediction_indexing import DurablePredictionIndexV080
            self.durable_index = DurablePredictionIndexV080(
                store_dir=self.store_dir,
                events_file=self.events_file,
                quarantine_dir=self.quarantine_dir,
            )

        self._load_or_verify_chain()

    @property
    def latest_hash(self) -> str:
        return self._latest_hash

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def is_chain_intact(self) -> bool:
        return self._is_chain_intact

    def _load_or_verify_chain(self) -> None:
        """Read existing JSONL, verify unbroken hash chain, and build dedup index."""
        if not self.events_file.exists():
            return

        if self.durable_index:
            valid_count, latest_h = self.durable_index.rebuild_or_sync_from_journal(self.events_file)
            self._event_count = valid_count
            self._latest_hash = latest_h
            self._is_chain_intact = True
            self._unmatured_events = self.durable_index.get_pending_predictions()[-2000:]
            self._seen_keys.update(self.durable_index.get_all_keys())
            self._file_offset = self.events_file.stat().st_size if self.events_file.exists() else 0
            return

        with open(self.events_file, "r", encoding="utf-8") as f:
            prev_hash = SHADOW_GENESIS_HASH
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    ev = ShadowPredictionEvent(**data)
                except Exception as e:
                    self._is_chain_intact = False
                    raise EventTamperError(f"Failed to parse event at line {line_no}: {e}") from e

                # Verify chain continuity
                if ev.previous_event_hash != prev_hash:
                    self._is_chain_intact = False
                    raise EventTamperError(
                        f"Hash chain broken at line {line_no}: expected prev {prev_hash}, got {ev.previous_event_hash}"
                    )

                # Verify record hash integrity
                calc_hash = ev.compute_hash()
                if ev.record_hash != calc_hash:
                    self._is_chain_intact = False
                    raise EventTamperError(
                        f"Tampered record at line {line_no}: declared {ev.record_hash}, calculated {calc_hash}"
                    )

                key = f"{ev.forecast_origin_utc}_{ev.candidate_branch}_{ev.target_horizon}"
                self._seen_keys.add(key)
                prev_hash = ev.record_hash
                self._event_count += 1
                self._unmatured_events.append(ev)

            # Bounded window: at most the last 288 bars * 6 events = 1728 events can ever be pending
            if len(self._unmatured_events) > 2000:
                self._unmatured_events = self._unmatured_events[-2000:]

            self._latest_hash = prev_hash

    def append_events_batch(self, events: List[ShadowPredictionEvent]) -> List[str]:
        """Append a batch of validated forecast events with single disk flush and batch SQLite index."""
        if not events:
            return []
        with self._lock:
            for event in events:
                key = f"{event.forecast_origin_utc}_{event.candidate_branch}_{event.target_horizon}"
                if key in self._seen_keys:
                    raise DuplicateForecastError(f"Forecast key '{key}' already exists in store.")

            hashes = []
            events_with_meta = []
            combined_bytes = bytearray()
            current_offset = getattr(self, "_file_offset", 0)

            for event in events:
                key = f"{event.forecast_origin_utc}_{event.candidate_branch}_{event.target_horizon}"
                event.previous_event_hash = self._latest_hash
                event.record_hash = event.compute_hash()

                line_str = json.dumps(event.to_dict(), sort_keys=True) + "\n"
                line_bytes = line_str.encode("utf-8")
                event_offset = current_offset + len(combined_bytes)
                combined_bytes.extend(line_bytes)

                self._seen_keys.add(key)
                self._latest_hash = event.record_hash
                self._event_count += 1
                self._unmatured_events.append(event)
                events_with_meta.append((event, event_offset, self._event_count, "PENDING"))
                hashes.append(event.record_hash)

            with open(self.events_file, "ab") as f:
                f.write(combined_bytes)
                f.flush()
                os.fsync(f.fileno())
            self._file_offset = current_offset + len(combined_bytes)

            if len(self._unmatured_events) > 2000:
                self._unmatured_events = self._unmatured_events[-2000:]

            if self.durable_index:
                self.durable_index.index_events_batch(events_with_meta)

            return hashes

    def append_event(self, event: ShadowPredictionEvent) -> str:
        """Append a validated forecast event to the hash chain and update durable index."""
        return self.append_events_batch([event])[0]

    def get_pending_count(self) -> int:
        """Return total count of pending predictions."""
        with self._lock:
            if len(self._unmatured_events) < 2000:
                return len(self._unmatured_events)
            if self.durable_index:
                return self.durable_index.get_pending_count()
            return len(self._unmatured_events)

    def get_unmatured_events(self) -> List[ShadowPredictionEvent]:
        """Return all currently un-matured prediction events without silent eviction."""
        with self._lock:
            if len(self._unmatured_events) >= 2000 and self.durable_index:
                pending_count = self.durable_index.get_pending_count()
                if pending_count > len(self._unmatured_events):
                    return self.durable_index.get_pending_predictions()
            return list(self._unmatured_events)

    def get_unmatured_events_paged(self, page_size: int = 500) -> Iterator[List[ShadowPredictionEvent]]:
        """Yield pages of un-matured prediction events."""
        if self.durable_index:
            yield from self.durable_index.get_pending_predictions_paged(page_size=page_size)
            return
        with self._lock:
            events_copy = list(self._unmatured_events)
        for i in range(0, len(events_copy), page_size):
            yield list(events_copy[i : i + page_size])

    def prune_matured_events(self, matured_hashes: Set[str]) -> None:
        """Prune resolved events from in-memory pending queue and update SQLite index."""
        if not matured_hashes:
            return
        with self._lock:
            self._unmatured_events = [e for e in self._unmatured_events if e.record_hash not in matured_hashes]
            if self.durable_index:
                self.durable_index.mark_matured_batch(matured_hashes, status="MATURED")

    def close(self) -> None:
        """Close underlying SQLite durable index."""
        with self._lock:
            if self.durable_index:
                try:
                    self.durable_index.close()
                except Exception:
                    pass

    def __del__(self) -> None:
        self.close()

    def list_events(self) -> List[ShadowPredictionEvent]:
        """Read and return all stored prediction events from disk (retained for backward compatibility)."""
        if not self.events_file.exists():
            return []
        events = []
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(ShadowPredictionEvent(**json.loads(line)))
        return events
