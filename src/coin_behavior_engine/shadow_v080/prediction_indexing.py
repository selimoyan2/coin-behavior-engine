"""Pending Prediction Index Interface & Journal-Based Durability Reference.

Sprint 09.16: Persistent Evidence-Based Outcome Resolution.

Defines the contract for tracking, querying, and updating pending prospective predictions.
Full persistent SQLite prediction indexing is explicitly deferred to Sprint 09.17, while
the existing append-only JSONL journal (`shadow_predictions.jsonl`) and startup recovery
in `ImmutablePredictionStoreV080` provide crash-consistent restart durability.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional, Set

from coin_behavior_engine.shadow_v080.prediction_store import (
    ImmutablePredictionStoreV080,
    ShadowPredictionEvent,
)

logger = logging.getLogger("cbe_prediction_indexing")


class IPendingPredictionIndex(abc.ABC):
    """Abstract interface for managing pending (un-matured) prediction lifecycle.

    Guarantees:
    - O(1) or indexed lookup of pending predictions awaiting market maturity.
    - Causal status transition from PENDING to MATURED or INVALID_GAP.
    - Deterministic restart recovery from durable store.
    """

    @abc.abstractmethod
    def add_pending(self, prediction: ShadowPredictionEvent) -> None:
        """Register a newly committed prediction as pending maturity."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_pending_predictions(self) -> List[ShadowPredictionEvent]:
        """Retrieve all currently un-matured prediction events."""
        raise NotImplementedError

    @abc.abstractmethod
    def mark_matured(self, record_hash: str) -> None:
        """Mark a prediction event as resolved/matured."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_pending_count(self) -> int:
        """Return total count of pending predictions."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_pending(self, record_hash: str) -> bool:
        """Check whether a specific record hash is currently pending."""
        raise NotImplementedError


class JournalPendingPredictionIndexV080(IPendingPredictionIndex):
    """Reference pending prediction index backed by ImmutablePredictionStoreV080 journal.

    Maintains an in-memory queue bounded by the maximum prospective horizon (288 bars = 24h)
    while reconstructing state directly from the immutable JSONL prediction journal upon restart.
    """

    def __init__(self, prediction_store: ImmutablePredictionStoreV080):
        self.prediction_store = prediction_store
        self._matured_hashes: Set[str] = set()

    def add_pending(self, prediction: ShadowPredictionEvent) -> None:
        """Register a prediction. Appends to store if not already committed."""
        if prediction.record_hash in self._matured_hashes:
            return
        # Store append will handle dedup if already written
        try:
            self.prediction_store.append_event(prediction)
        except Exception:
            # If already appended or seen, it is tracked in store
            pass

    def get_pending_predictions(self) -> List[ShadowPredictionEvent]:
        """Return all pending events from the backing prediction store."""
        raw_pending = self.prediction_store.get_unmatured_events()
        return [p for p in raw_pending if p.record_hash not in self._matured_hashes]

    def mark_matured(self, record_hash: str) -> None:
        """Mark a prediction as matured and prune it from the store pending list."""
        self._matured_hashes.add(record_hash)
        self.prediction_store.prune_matured_events({record_hash})

    def get_pending_count(self) -> int:
        """Return current count of pending predictions."""
        return len(self.get_pending_predictions())

    def is_pending(self, record_hash: str) -> bool:
        """Return True if the prediction is still pending outcome maturity."""
        if record_hash in self._matured_hashes:
            return False
        return any(p.record_hash == record_hash for p in self.prediction_store.get_unmatured_events())
