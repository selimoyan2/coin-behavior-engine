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

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.store_dir / "shadow_predictions.jsonl"
        self._lock = threading.Lock()
        self._seen_keys: Set[str] = set()
        self._latest_hash: str = SHADOW_GENESIS_HASH
        self._event_count: int = 0
        self._load_or_verify_chain()

    @property
    def latest_hash(self) -> str:
        return self._latest_hash

    @property
    def event_count(self) -> int:
        return self._event_count

    def _load_or_verify_chain(self) -> None:
        """Read existing JSONL, verify unbroken hash chain, and build dedup index."""
        if not self.events_file.exists():
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
                    raise EventTamperError(f"Failed to parse event at line {line_no}: {e}") from e

                # Verify chain continuity
                if ev.previous_event_hash != prev_hash:
                    raise EventTamperError(
                        f"Hash chain broken at line {line_no}: expected prev {prev_hash}, got {ev.previous_event_hash}"
                    )

                # Verify record hash integrity
                calc_hash = ev.compute_hash()
                if ev.record_hash != calc_hash:
                    raise EventTamperError(
                        f"Tampered record at line {line_no}: declared {ev.record_hash}, calculated {calc_hash}"
                    )

                key = f"{ev.forecast_origin_utc}_{ev.candidate_branch}_{ev.target_horizon}"
                self._seen_keys.add(key)
                prev_hash = ev.record_hash
                self._event_count += 1

            self._latest_hash = prev_hash

    def append_event(self, event: ShadowPredictionEvent) -> str:
        """Append a validated forecast event to the hash chain."""
        key = f"{event.forecast_origin_utc}_{event.candidate_branch}_{event.target_horizon}"
        with self._lock:
            if key in self._seen_keys:
                raise DuplicateForecastError(f"Forecast key '{key}' already exists in store.")

            event.previous_event_hash = self._latest_hash
            event.record_hash = event.compute_hash()

            line = json.dumps(event.to_dict(), sort_keys=True) + "\n"
            with open(self.events_file, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            self._seen_keys.add(key)
            self._latest_hash = event.record_hash
            self._event_count += 1
            return event.record_hash

    def list_events(self) -> List[ShadowPredictionEvent]:
        """Read and return all stored prediction events."""
        if not self.events_file.exists():
            return []
        events = []
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(ShadowPredictionEvent(**json.loads(line)))
        return events
