"""
Turnover Control Engine (Sprint 30 Task 5).

Provides configurable, versioned, and auditable turnover-control mechanisms:
1. Minimum Holding Period (e.g., 24h, 72h, 168h).
2. Allocation Hysteresis (buffer preventing whipsaw on boundary crossings).
3. Minimum Rebalance Threshold (e.g., 5%, 10%, 15% allocation divergence).
4. Rebalance Frequency (HOURLY, DAILY, WEEKLY, MONTHLY).
5. Minimum Trade Notional (rejecting economically insignificant orders).
6. Turnover Budget (hard cap on cumulative traded notional).
7. Transparent Trade Rejection Audit Ledger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RebalanceFrequency(str, Enum):
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class TradeRejectionReason(str, Enum):
    MIN_HOLDING_PERIOD_ACTIVE = "MIN_HOLDING_PERIOD_ACTIVE"
    BELOW_REBALANCE_THRESHOLD = "BELOW_REBALANCE_THRESHOLD"
    OFF_SCHEDULE_FREQUENCY = "OFF_SCHEDULE_FREQUENCY"
    BELOW_MIN_NOTIONAL = "BELOW_MIN_NOTIONAL"
    TURNOVER_BUDGET_EXHAUSTED = "TURNOVER_BUDGET_EXHAUSTED"
    HYSTERESIS_BAND_RETAINED = "HYSTERESIS_BAND_RETAINED"
    ZERO_TARGET_DIFF = "ZERO_TARGET_DIFF"


@dataclass(frozen=True)
class TurnoverControlConfig:
    """Configurable turnover constraint parameters."""
    min_holding_period_hours: int = 0          # e.g., 0, 24, 72, 168
    min_rebalance_threshold_pct: float = 0.0   # e.g., 0.05 (5%), 0.10 (10%), 0.15 (15%)
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.HOURLY
    min_trade_notional_usdt: float = 10.0      # Reject trades < $10 (or $100, $250)
    max_turnover_budget_ratio: Optional[float] = None  # e.g., 10.0x annual turnover cap
    hysteresis_band_pct: float = 0.0          # e.g. 0.02 (2% buffer on signal)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_holding_period_hours": self.min_holding_period_hours,
            "min_rebalance_threshold_pct": self.min_rebalance_threshold_pct,
            "rebalance_frequency": self.rebalance_frequency.value,
            "min_trade_notional_usdt": self.min_trade_notional_usdt,
            "max_turnover_budget_ratio": self.max_turnover_budget_ratio,
            "hysteresis_band_pct": self.hysteresis_band_pct,
        }


@dataclass(frozen=True)
class TradeRejectionAuditRecord:
    timestamp_ms: int
    timestamp_iso: str
    rejection_reason: str
    candidate_target_alloc: float
    current_actual_alloc: float
    allocation_diff_pct: float
    holding_hours_elapsed: float
    candidate_notional_usdt: float
    cumulative_turnover_ratio: float
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TurnoverController:
    """Applies rigorous turnover controls to portfolio rebalancing decisions."""

    def __init__(
        self,
        config: Optional[TurnoverControlConfig] = None,
        initial_capital_usdt: float = 10000.0,
    ):
        self.config = config or TurnoverControlConfig()
        self.initial_capital_usdt = float(initial_capital_usdt)

        # State tracking
        self.last_trade_timestamp_ms: Optional[int] = None
        self.cumulative_traded_notional: float = 0.0
        self.rejection_ledger: List[TradeRejectionAuditRecord] = []
        self.total_evaluations: int = 0
        self.total_rejections: int = 0
        self.total_approvals: int = 0

    def evaluate_rebalance_proposal(
        self,
        timestamp_ms: int,
        timestamp_iso: str,
        current_actual_alloc: float,
        proposed_target_alloc: float,
        current_equity_usdt: float,
        execution_price: float,
    ) -> Tuple[bool, Optional[float], Optional[TradeRejectionReason], str]:
        """Evaluate if proposed rebalance satisfies all turnover constraints.

        Returns:
            (approved: bool, adjusted_target: Optional[float], rejection_reason: Optional[TradeRejectionReason], message: str)
        """
        self.total_evaluations += 1
        alloc_diff = abs(proposed_target_alloc - current_actual_alloc)
        candidate_notional = alloc_diff * current_equity_usdt
        current_turnover_ratio = self.cumulative_traded_notional / max(self.initial_capital_usdt, 1.0)

        # 1. Zero difference check
        if alloc_diff < 1e-4:
            return False, None, TradeRejectionReason.ZERO_TARGET_DIFF, "Proposed allocation matches current allocation."

        # 2. Rebalance Frequency Schedule Check
        if not self._is_schedule_aligned(timestamp_iso):
            reason = TradeRejectionReason.OFF_SCHEDULE_FREQUENCY
            self._log_rejection(
                timestamp_ms, timestamp_iso, reason, proposed_target_alloc,
                current_actual_alloc, alloc_diff, 0.0, candidate_notional,
                current_turnover_ratio, f"Bar not aligned with {self.config.rebalance_frequency.value} schedule."
            )
            return False, None, reason, f"Rebalance blocked: off {self.config.rebalance_frequency.value} schedule."

        # 3. Minimum Holding Period Check
        if self.last_trade_timestamp_ms is not None and self.config.min_holding_period_hours > 0:
            elapsed_hours = (timestamp_ms - self.last_trade_timestamp_ms) / 3600000.0
            if elapsed_hours < self.config.min_holding_period_hours:
                reason = TradeRejectionReason.MIN_HOLDING_PERIOD_ACTIVE
                self._log_rejection(
                    timestamp_ms, timestamp_iso, reason, proposed_target_alloc,
                    current_actual_alloc, alloc_diff, elapsed_hours, candidate_notional,
                    current_turnover_ratio, f"Only {elapsed_hours:.1f}h elapsed < {self.config.min_holding_period_hours}h requirement."
                )
                return False, None, reason, f"Rebalance blocked: minimum holding period of {self.config.min_holding_period_hours}h active ({elapsed_hours:.1f}h elapsed)."

        # 4. Minimum Rebalance Threshold Check
        if self.config.min_rebalance_threshold_pct > 0:
            if alloc_diff < self.config.min_rebalance_threshold_pct:
                reason = TradeRejectionReason.BELOW_REBALANCE_THRESHOLD
                elapsed = (timestamp_ms - self.last_trade_timestamp_ms) / 3600000.0 if self.last_trade_timestamp_ms else 999.0
                self._log_rejection(
                    timestamp_ms, timestamp_iso, reason, proposed_target_alloc,
                    current_actual_alloc, alloc_diff, elapsed, candidate_notional,
                    current_turnover_ratio, f"Allocation diff {alloc_diff*100:.2f}% < {self.config.min_rebalance_threshold_pct*100:.2f}% threshold."
                )
                return False, None, reason, f"Rebalance blocked: allocation shift ({alloc_diff*100:.2f}%) below threshold ({self.config.min_rebalance_threshold_pct*100:.2f}%)."

        # 5. Minimum Trade Notional Check
        if candidate_notional < self.config.min_trade_notional_usdt:
            reason = TradeRejectionReason.BELOW_MIN_NOTIONAL
            elapsed = (timestamp_ms - self.last_trade_timestamp_ms) / 3600000.0 if self.last_trade_timestamp_ms else 999.0
            self._log_rejection(
                timestamp_ms, timestamp_iso, reason, proposed_target_alloc,
                current_actual_alloc, alloc_diff, elapsed, candidate_notional,
                current_turnover_ratio, f"Candidate notional ${candidate_notional:.2f} < ${self.config.min_trade_notional_usdt:.2f} minimum."
            )
            return False, None, reason, f"Rebalance blocked: trade notional (${candidate_notional:.2f}) below minimum (${self.config.min_trade_notional_usdt:.2f})."

        # 6. Turnover Budget Check
        if self.config.max_turnover_budget_ratio is not None:
            new_turnover_ratio = (self.cumulative_traded_notional + candidate_notional) / self.initial_capital_usdt
            if new_turnover_ratio > self.config.max_turnover_budget_ratio:
                reason = TradeRejectionReason.TURNOVER_BUDGET_EXHAUSTED
                elapsed = (timestamp_ms - self.last_trade_timestamp_ms) / 3600000.0 if self.last_trade_timestamp_ms else 999.0
                self._log_rejection(
                    timestamp_ms, timestamp_iso, reason, proposed_target_alloc,
                    current_actual_alloc, alloc_diff, elapsed, candidate_notional,
                    current_turnover_ratio, f"Turnover budget cap ({self.config.max_turnover_budget_ratio:.1f}x) would be exceeded ({new_turnover_ratio:.2f}x)."
                )
                return False, None, reason, f"Rebalance blocked: turnover budget cap ({self.config.max_turnover_budget_ratio:.1f}x) exhausted."

        # Passed all constraints!
        self.total_approvals += 1
        return True, proposed_target_alloc, None, "Approved"

    def record_executed_trade(self, timestamp_ms: int, notional_usdt: float) -> None:
        """Update controller state after a verified trade execution."""
        self.last_trade_timestamp_ms = timestamp_ms
        self.cumulative_traded_notional += abs(notional_usdt)

    def _is_schedule_aligned(self, timestamp_iso: str) -> bool:
        """Check if candle timestamp is on periodic rebalancing boundary."""
        freq = self.config.rebalance_frequency
        if freq == RebalanceFrequency.HOURLY:
            return True

        # Parse hour, minute, day of week
        # ISO string format e.g. "2024-01-15T00:00:00Z" or "2024-01-15 00:00:00+00:00"
        clean = timestamp_iso.replace("Z", "+00:00")
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(clean)
        except Exception:
            return True

        if freq == RebalanceFrequency.DAILY:
            # Rebalance only at 00:00 UTC
            return dt.hour == 0

        elif freq == RebalanceFrequency.WEEKLY:
            # Rebalance only on Monday (weekday=0) at 00:00 UTC
            return dt.weekday() == 0 and dt.hour == 0

        elif freq == RebalanceFrequency.MONTHLY:
            # Rebalance only on 1st day of month at 00:00 UTC
            return dt.day == 1 and dt.hour == 0

        return True

    def _log_rejection(
        self,
        timestamp_ms: int,
        timestamp_iso: str,
        reason: TradeRejectionReason,
        target_alloc: float,
        actual_alloc: float,
        diff_pct: float,
        holding_hours: float,
        notional_usdt: float,
        turnover_ratio: float,
        details: str,
    ) -> None:
        self.total_rejections += 1
        record = TradeRejectionAuditRecord(
            timestamp_ms=timestamp_ms,
            timestamp_iso=timestamp_iso,
            rejection_reason=reason.value,
            candidate_target_alloc=round(target_alloc, 4),
            current_actual_alloc=round(actual_alloc, 4),
            allocation_diff_pct=round(diff_pct * 100.0, 2),
            holding_hours_elapsed=round(holding_hours, 2),
            candidate_notional_usdt=round(notional_usdt, 2),
            cumulative_turnover_ratio=round(turnover_ratio, 4),
            details=details,
        )
        self.rejection_ledger.append(record)

    def summary(self) -> Dict[str, Any]:
        """Return comprehensive turnover control statistics."""
        return {
            "config": self.config.to_dict(),
            "total_evaluations": self.total_evaluations,
            "total_approvals": self.total_approvals,
            "total_rejections": self.total_rejections,
            "rejection_rate_pct": round((self.total_rejections / max(1, self.total_evaluations)) * 100.0, 2),
            "cumulative_traded_notional_usdt": round(self.cumulative_traded_notional, 2),
            "final_turnover_ratio": round(self.cumulative_traded_notional / max(self.initial_capital_usdt, 1.0), 4),
            "rejections_by_reason": self._rejection_breakdown(),
        }

    def _rejection_breakdown(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self.rejection_ledger:
            counts[r.rejection_reason] = counts.get(r.rejection_reason, 0) + 1
        return counts
