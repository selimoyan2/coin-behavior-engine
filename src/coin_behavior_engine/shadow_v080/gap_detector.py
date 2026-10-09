"""CBE-0.8.0 Market Data Gap Detector & Contiguity Tracker.

Enforces:
- Deterministic detection of missing 5-minute interval candles.
- Distinguishing missing intervals from out-of-order/delayed arrivals.
- Gap event tracking and immutable gap recovery audit logging.
- Strict provenance enforcement: recovered gap data must be labeled 'REST_GAP_RECOVERY'
  and can never be counted as genuine prospective evidence.
- Contiguous closed candle tracking for the 288-bar minimum full-window eligibility invariant.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    ProvenanceSource,
    ValidatedCandle,
)

logger = logging.getLogger("cbe_gap_detector")

FULL_WARMUP_BARS = 288  # 24 hours of contiguous 5-minute candles


@dataclass
class GapEvent:
    gap_id: str
    missing_start_ts: int
    missing_end_ts: int
    missing_bars_count: int
    detected_at_utc: str
    missing_timestamps: List[int]
    recovered: bool = False
    recovered_at_utc: Optional[str] = None
    recovery_provenance: Optional[str] = None
    recovered_candles_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MarketDataGapDetector:
    """Monitors 5m candle sequence contiguity, detects missing bars, and tracks recovery."""

    def __init__(self, full_warmup_bars: int = FULL_WARMUP_BARS):
        self.full_warmup_bars = full_warmup_bars
        self.last_candle_open_ts: Optional[int] = None
        self.contiguous_closed_bars: int = 0
        self.total_processed_bars: int = 0
        self.gaps: List[GapEvent] = []
        self._missing_ts_set: Set[int] = set()

    @property
    def has_unrecovered_gaps(self) -> bool:
        return any(not g.recovered for g in self.gaps)

    @property
    def unrecovered_gaps_count(self) -> int:
        return sum(1 for g in self.gaps if not g.recovered)

    @property
    def is_full_window_eligible(self) -> bool:
        """Eligibility requires at least 288 contiguous closed candles with zero unrecovered gaps in window."""
        return self.contiguous_closed_bars >= self.full_warmup_bars

    @property
    def warmup_status(self) -> str:
        if self.contiguous_closed_bars >= self.full_warmup_bars:
            return "FULL_WINDOW_READY"
        return f"WARMUP_PARTIAL ({self.contiguous_closed_bars}/{self.full_warmup_bars})"

    def process_next_candle(self, candle: ValidatedCandle) -> Tuple[bool, Optional[GapEvent]]:
        """Process incoming validated candle and detect any temporal gap.

        Returns (is_contiguous, gap_event_or_none).
        """
        curr_open = candle.timestamp_open
        self.total_processed_bars += 1

        if self.last_candle_open_ts is None:
            # First candle processed
            self.last_candle_open_ts = curr_open
            self.contiguous_closed_bars = 1
            return True, None

        expected_open = self.last_candle_open_ts + CANDLE_INTERVAL_MS

        if curr_open == expected_open:
            # Perfectly contiguous
            self.last_candle_open_ts = curr_open
            self.contiguous_closed_bars += 1
            return True, None

        elif curr_open > expected_open:
            # Missing interval(s) detected!
            missing_count = (curr_open - expected_open) // CANDLE_INTERVAL_MS
            missing_ts_list = [
                expected_open + (i * CANDLE_INTERVAL_MS)
                for i in range(missing_count)
            ]
            gap_id = f"GAP-{expected_open}-{curr_open - CANDLE_INTERVAL_MS}"
            detected_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            gap = GapEvent(
                gap_id=gap_id,
                missing_start_ts=expected_open,
                missing_end_ts=curr_open - CANDLE_INTERVAL_MS,
                missing_bars_count=missing_count,
                detected_at_utc=detected_utc,
                missing_timestamps=missing_ts_list,
                recovered=False,
            )
            self.gaps.append(gap)
            self._missing_ts_set.update(missing_ts_list)

            logger.error(
                f"SEQUENCE GAP DETECTED: Expected {expected_open}, got {curr_open}. "
                f"Missing {missing_count} bar(s). Contiguity reset."
            )

            # Break in contiguity: reset contiguous counter to 1 (current candle)
            self.contiguous_closed_bars = 1
            self.last_candle_open_ts = curr_open
            return False, gap

        else:
            # curr_open < expected_open: duplicate or out-of-order
            # Does not advance latest timestamp; handled by caller/store
            return False, None

    def register_recovered_gap(
        self,
        gap_id: str,
        recovered_candles: List[ValidatedCandle],
    ) -> Tuple[bool, str]:
        """Apply gap recovery candles, enforcing strict REST_GAP_RECOVERY provenance."""
        target_gap = None
        for g in self.gaps:
            if g.gap_id == gap_id:
                target_gap = g
                break

        if target_gap is None:
            return False, f"Gap ID {gap_id} not found."

        if target_gap.recovered:
            return False, f"Gap {gap_id} is already marked as recovered."

        # Verify all candles carry REST_GAP_RECOVERY provenance
        for c in recovered_candles:
            if c.provenance != ProvenanceSource.REST_GAP_RECOVERY.value:
                return False, (
                    f"PROVENANCE_VIOLATION: Recovered gap candles must have provenance "
                    f"'{ProvenanceSource.REST_GAP_RECOVERY.value}'; got '{c.provenance}'."
                )

        # Verify timestamps match missing timestamps
        rec_ts = [c.timestamp_open for c in recovered_candles]
        if rec_ts != target_gap.missing_timestamps:
            return False, (
                f"RECOVERY_MISMATCH: Recovered timestamps {rec_ts} do not match "
                f"missing gap timestamps {target_gap.missing_timestamps}."
            )

        target_gap.recovered = True
        target_gap.recovered_at_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target_gap.recovery_provenance = ProvenanceSource.REST_GAP_RECOVERY.value
        target_gap.recovered_candles_count = len(recovered_candles)

        for ts in target_gap.missing_timestamps:
            self._missing_ts_set.discard(ts)

        logger.info(f"Gap {gap_id} successfully marked as recovered via {target_gap.recovery_provenance}.")
        return True, "GAP_RECOVERED_SUCCESSFULLY"
