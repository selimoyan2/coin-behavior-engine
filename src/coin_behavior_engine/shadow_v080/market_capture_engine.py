"""CBE-0.8.0 Market Capture Engine & Observation Pipeline.

Coordinates:
- Transport ingestion (Mock or Approval 3 gated live transport).
- Strict closed-candle validation and decimal-safe boundary checks.
- Market data gap detection and 288-bar contiguous warm-up tracking.
- Immutable raw evidence persistence with SHA-256 hash chaining.
- Conflicting duplicate and malformed record quarantine.
- Full-window downstream research eligibility gating.
- Strict Approval 4 isolation (prospective inference permanently disengaged).
"""

from __future__ import annotations

import collections
import logging
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.gap_detector import MarketDataGapDetector
from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    ConflictingCandleError,
    EvidencePersistenceError,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BaseMarketDataTransport,
    MockMarketDataTransport,
    SafetyInterlockError,
)

logger = logging.getLogger("cbe_market_capture_engine")


class MarketCaptureEngineV080:
    """Orchestrates market data capture, validation, evidence preservation, and contiguity."""

    def __init__(
        self,
        config: ShadowCollectorConfig,
        transport: Optional[BaseMarketDataTransport] = None,
        default_provenance: str = ProvenanceSource.OFFLINE_FIXTURE.value,
    ):
        self.config = config
        self.config.ensure_directories()
        self.default_provenance = default_provenance

        # In-memory rolling buffer bounded to max_buffer_candles (default 350)
        self.rolling_buffer: collections.deque[ValidatedCandle] = collections.deque(
            maxlen=config.max_buffer_candles
        )

        self.transport = transport or MockMarketDataTransport(config)
        self.validator = BinanceSpotCandleValidator()
        self.gap_detector = MarketDataGapDetector(full_warmup_bars=config.full_warmup_bars)
        self.evidence_store = RawMarketEvidenceStore(
            raw_market_dir=config.raw_market_dir,
            quarantine_dir=config.quarantine_dir,
            symbol=config.symbol,
            interval=config.interval,
        )

        self.total_received = 0
        self.total_validated = 0
        self.total_persisted = 0
        self.total_quarantined = 0
        self.is_running = False

    def start(self) -> None:
        """Start the capture engine."""
        self.transport.connect()
        self.is_running = True
        logger.info("MarketCaptureEngineV080 started.")

    def stop(self) -> None:
        """Gracefully stop capture engine."""
        self.transport.disconnect()
        self.is_running = False
        logger.info("MarketCaptureEngineV080 stopped.")

    @property
    def is_research_eligible(self) -> bool:
        """Downstream research eligibility requires >= 288 contiguous closed candles without gaps."""
        return (
            len(self.rolling_buffer) >= self.config.full_warmup_bars
            and self.gap_detector.is_full_window_eligible
            and not self.gap_detector.has_unrecovered_gaps
        )

    @property
    def warmup_status(self) -> str:
        return self.gap_detector.warmup_status

    def verify_approval_4_isolation(self) -> bool:
        """Verify that Approval 4 (prospective scoring) remains strictly isolated and disabled."""
        if getattr(self.config, "approval_4_authorized", False):
            return False
        if os.environ.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "true":
            return False
        return True

    def process_raw_message(
        self,
        raw_message: Any,
        provenance: Optional[str] = None,
        force_disk_error: bool = False,
    ) -> Dict[str, Any]:
        """Validate, check gaps, and persist a single incoming raw candle message."""
        self.total_received += 1
        prov = provenance or self.default_provenance

        # 1. Validation Stage
        candle, violations = self.validator.validate_raw(
            raw_record=raw_message,
            provenance=prov,
            market_type=MarketType.SPOT,
        )

        if violations or candle is None:
            self.total_quarantined += 1
            self.evidence_store.quarantine_record(
                reason="VALIDATION_FAILED: " + "; ".join(violations),
                payload=raw_message,
            )
            return {
                "status": "VALIDATION_FAILED",
                "violations": violations,
                "lifecycle_state": CandleLifecycleState.CANDLE_RECEIVED.value,
            }

        self.total_validated += 1

        # 2. Gap Detection Stage
        is_contiguous, gap_event = self.gap_detector.process_next_candle(candle)

        # 3. Evidence Persistence Stage
        persist_status, entry = self.evidence_store.append_candle(
            candle=candle,
            force_disk_error=force_disk_error,
        )

        if persist_status == "PERSISTED":
            self.total_persisted += 1
            self.rolling_buffer.append(candle)
            if self.is_research_eligible:
                candle.lifecycle_state = CandleLifecycleState.CANDLE_RESEARCH_ELIGIBLE.value

            return {
                "status": "PERSISTED",
                "timestamp_open": candle.timestamp_open,
                "is_contiguous": is_contiguous,
                "gap_detected": gap_event is not None,
                "gap_event": gap_event.to_dict() if gap_event else None,
                "entry_hash": entry.entry_hash if entry else None,
                "warmup_status": self.warmup_status,
                "is_research_eligible": self.is_research_eligible,
                "lifecycle_state": candle.lifecycle_state,
            }

        elif persist_status == "DUPLICATE_IGNORED":
            return {
                "status": "DUPLICATE_IGNORED",
                "timestamp_open": candle.timestamp_open,
                "lifecycle_state": CandleLifecycleState.CANDLE_VALIDATED.value,
            }

        elif persist_status in ("CONFLICT_QUARANTINED", "OUT_OF_ORDER_QUARANTINED"):
            self.total_quarantined += 1
            return {
                "status": persist_status,
                "timestamp_open": candle.timestamp_open,
                "lifecycle_state": CandleLifecycleState.CANDLE_VALIDATED.value,
            }

        return {"status": persist_status}

    def process_next_tick(self, force_disk_error: bool = False) -> Dict[str, Any]:
        """Poll from transport and process next message."""
        raw_msg = self.transport.poll_message()
        if raw_msg is None:
            return {"status": "NO_MESSAGE"}

        return self.process_raw_message(raw_msg, force_disk_error=force_disk_error)

    def get_summary_report(self) -> Dict[str, Any]:
        """Return diagnostic metrics and safety status."""
        return {
            "total_received": self.total_received,
            "total_validated": self.total_validated,
            "total_persisted": self.total_persisted,
            "total_quarantined": self.total_quarantined,
            "rolling_buffer_size": len(self.rolling_buffer),
            "max_buffer_capacity": self.rolling_buffer.maxlen,
            "contiguous_bars_count": self.gap_detector.contiguous_closed_bars,
            "has_unrecovered_gaps": self.gap_detector.has_unrecovered_gaps,
            "unrecovered_gaps_count": self.gap_detector.unrecovered_gaps_count,
            "is_research_eligible": self.is_research_eligible,
            "warmup_status": self.warmup_status,
            "approval_3_authorized": getattr(self.config, "approval_3_authorized", False),
            "approval_4_isolated": self.verify_approval_4_isolation(),
            "latest_entry_hash": self.evidence_store.latest_entry_hash,
            "evidence_entries_count": self.evidence_store.count,
        }
