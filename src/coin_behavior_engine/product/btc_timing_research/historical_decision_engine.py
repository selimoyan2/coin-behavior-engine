"""Historical Decision Engine (Module 29.6).

Enforces strict point-in-time information availability, preventing lookahead bias.
At each decision point T:
1. Only completed historical candles (up to T_close) are fed to indicators.
2. Information is marked available at T_close + publication delay.
3. Decision is evaluated at decision_timestamp.
4. Execution is scheduled strictly at next candle open (simulated_execution_timestamp).
5. Explicitly records 4 timestamps for every decision.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BaseTimingPolicy,
    PolicyDecision,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulatedDecisionRecord:
    """Complete audit record of a simulated historical decision."""
    decision_id: str
    policy_id: str
    observation_timestamp_ms: int
    observation_timestamp_iso: str
    information_available_at_ms: int
    information_available_at_iso: str
    decision_timestamp_ms: int
    decision_timestamp_iso: str
    simulated_execution_timestamp_ms: int
    simulated_execution_timestamp_iso: str
    target_btc_allocation: float
    current_allocation: float
    rebalance_required: bool
    nominal_execution_price: float
    decision_reason: str
    indicators_used: Dict[str, Any]
    status: str  # DECISION_CREATED, SIMULATED_EXECUTION_FILLED, SIMULATED_EXECUTION_REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HistoricalDecisionEngine:
    """Coordinates point-in-time policy evaluations without lookahead bias."""

    def __init__(self, policy: BaseTimingPolicy, interval_ms: int = 3600000, publication_lag_ms: int = 1000):
        self.policy = policy
        self.interval_ms = interval_ms
        self.publication_lag_ms = publication_lag_ms

    def evaluate_step(
        self,
        current_candle_row: Dict[str, Any],
        next_candle_open_price: float,
        current_btc_allocation: float,
    ) -> SimulatedDecisionRecord:
        """Evaluate decision at completed candle close, for execution at next open."""
        open_time = int(current_candle_row["open_time"])
        close_time = open_time + self.interval_ms
        info_available_time = close_time + self.publication_lag_ms
        decision_time = info_available_time
        execution_time = decision_time

        # Evaluate policy
        policy_decision = self.policy.evaluate(current_candle_row)
        target_allocation = policy_decision.target_btc_allocation

        # Check if rebalance is needed (allocation difference > 0.01)
        rebalance_needed = abs(target_allocation - current_btc_allocation) > 0.01

        rec = SimulatedDecisionRecord(
            decision_id=f"DEC-{uuid.uuid4().hex[:12].upper()}",
            policy_id=self.policy.policy_id,
            observation_timestamp_ms=close_time,
            observation_timestamp_iso=_ms_to_iso(close_time),
            information_available_at_ms=info_available_time,
            information_available_at_iso=_ms_to_iso(info_available_time),
            decision_timestamp_ms=decision_time,
            decision_timestamp_iso=_ms_to_iso(decision_time),
            simulated_execution_timestamp_ms=execution_time,
            simulated_execution_timestamp_iso=_ms_to_iso(execution_time),
            target_btc_allocation=target_allocation,
            current_allocation=round(current_btc_allocation, 4),
            rebalance_required=rebalance_needed,
            nominal_execution_price=float(next_candle_open_price),
            decision_reason=policy_decision.decision_reason,
            indicators_used=policy_decision.indicators_used,
            status="DECISION_CREATED",
        )
        return rec
