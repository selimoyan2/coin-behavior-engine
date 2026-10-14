"""Realistic offline execution modeling for historical crypto market research.

Models:
1. Taker (market order) execution:
   - Guaranteed fill at decision price + half spread + slippage.
   - Standard taker fees on entry and exit.
2. Passive limit (maker) execution:
   - Limit order placed at breakout level or decision bar close.
   - Queue position uncertainty and non-fill risk.
   - Penetration depth requirement (touch vs penetration).
   - Adverse selection ("winner's curse" - fills occur disproportionately on failed breakouts).
   - Order cancellation / expiration after configurable bars.
   - Scenarios: OPTIMISTIC, BASELINE, PESSIMISTIC.
3. Fill-rate sensitivity parameterization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Mapping, Optional, Sequence

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentOpportunity,
    SimulatedTradeResult,
    TradeCostModel,
    TradeDirection,
)


class ExecutionMode(str, Enum):
    """Execution mode scenario for order simulation."""

    TAKER = "TAKER"
    MAKER_OPTIMISTIC = "MAKER_OPTIMISTIC"
    MAKER_BASELINE = "MAKER_BASELINE"
    MAKER_PESSIMISTIC = "MAKER_PESSIMISTIC"


class OrderFillStatus(str, Enum):
    """Outcome of order placement."""

    FILLED = "FILLED"
    PARTIAL_FILL = "PARTIAL_FILL"
    EXPIRED_UNFILLED = "EXPIRED_UNFILLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ExecutionParameters:
    """Configurable parameters for realistic execution simulation."""

    mode: ExecutionMode = ExecutionMode.TAKER
    expiry_bars: int = 2  # Limit order expires if unfilled after N bars
    penetration_spread_multiple: float = 0.5  # Required price depth through limit price
    queue_fill_probability: float = 0.80  # Probability of filling when condition met
    adverse_selection_bps: float = 2.0  # Slippage penalty on fills due to adverse selection
    maker_fee_bps: float = 2.0  # Maker fee (e.g. 0.02% or 0% VIP)
    taker_fee_bps: float = 5.0  # Taker fee (0.05%)
    half_spread_bps: float = 1.0  # 0.01%
    slippage_bps: float = 2.0  # Market order slippage
    allow_partial_fills: bool = False
    partial_fill_ratio: float = 1.0

    @classmethod
    def taker_default(cls) -> ExecutionParameters:
        return cls(
            mode=ExecutionMode.TAKER,
            queue_fill_probability=1.0,
            penetration_spread_multiple=0.0,
            adverse_selection_bps=0.0,
        )

    @classmethod
    def maker_optimistic(cls) -> ExecutionParameters:
        return cls(
            mode=ExecutionMode.MAKER_OPTIMISTIC,
            expiry_bars=2,
            penetration_spread_multiple=0.0,  # Fills on mere touch
            queue_fill_probability=1.00,  # 100% queue fill
            adverse_selection_bps=0.0,  # No adverse selection
            maker_fee_bps=2.0,
            half_spread_bps=0.0,  # Maker captures the spread
            slippage_bps=0.0,
        )

    @classmethod
    def maker_baseline(cls) -> ExecutionParameters:
        return cls(
            mode=ExecutionMode.MAKER_BASELINE,
            expiry_bars=2,
            penetration_spread_multiple=0.5,  # Requires piercing half the spread
            queue_fill_probability=0.80,  # 80% queue fill rate
            adverse_selection_bps=2.0,  # 2 bps adverse selection
            maker_fee_bps=2.0,
            half_spread_bps=0.0,
            slippage_bps=0.0,
        )

    @classmethod
    def maker_pessimistic(cls) -> ExecutionParameters:
        return cls(
            mode=ExecutionMode.MAKER_PESSIMISTIC,
            expiry_bars=2,
            penetration_spread_multiple=1.0,  # Requires piercing full spread
            queue_fill_probability=0.50,  # 50% queue fill rate (severe competition)
            adverse_selection_bps=5.0,  # 5 bps adverse selection
            maker_fee_bps=2.0,
            half_spread_bps=0.0,
            slippage_bps=0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


@dataclass(frozen=True)
class ExecutionResult:
    """Detailed result of order execution simulation."""

    opportunity_id: str
    status: OrderFillStatus
    execution_mode: ExecutionMode
    intended_entry_price: float
    effective_entry_price: float
    entry_bar_index: int
    fill_bar_index: Optional[int]
    fill_ratio: float
    entry_cost_pct: float
    missed_reason: Optional[str] = None
    adverse_selection_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["execution_mode"] = self.execution_mode.value
        return d


class RealisticExecutionSimulator:
    """Simulates realistic taker and maker execution mechanics."""

    def __init__(self, params: ExecutionParameters | None = None) -> None:
        self.params = params or ExecutionParameters.taker_default()

    def simulate_entry(
        self,
        opportunity: InvestmentOpportunity,
        candles: Sequence[Mapping[str, Any]],
    ) -> tuple[ExecutionResult, Optional[InvestmentOpportunity]]:
        """Simulate entry execution against subsequent candles.

        Returns (ExecutionResult, updated_opportunity_or_none).
        """
        entry_idx = opportunity.entry_bar_index
        n_bars = len(candles)
        if entry_idx >= n_bars:
            res = ExecutionResult(
                opportunity_id=opportunity.opportunity_id,
                status=OrderFillStatus.REJECTED,
                execution_mode=self.params.mode,
                intended_entry_price=opportunity.entry_price,
                effective_entry_price=0.0,
                entry_bar_index=entry_idx,
                fill_bar_index=None,
                fill_ratio=0.0,
                entry_cost_pct=0.0,
                missed_reason="OUT_OF_BOUNDS",
            )
            return res, None

        direction = opportunity.direction
        limit_px = opportunity.entry_price
        half_spread_pct = self.params.half_spread_bps / 10_000.0

        # Case 1: TAKER execution
        if self.params.mode == ExecutionMode.TAKER:
            slippage_pct = self.params.slippage_bps / 10_000.0
            if direction == TradeDirection.LONG:
                effective_px = limit_px * (1.0 + half_spread_pct + slippage_pct)
            else:
                effective_px = limit_px * (1.0 - half_spread_pct - slippage_pct)

            entry_cost = (self.params.taker_fee_bps + self.params.half_spread_bps + self.params.slippage_bps) / 10_000.0

            res = ExecutionResult(
                opportunity_id=opportunity.opportunity_id,
                status=OrderFillStatus.FILLED,
                execution_mode=self.params.mode,
                intended_entry_price=limit_px,
                effective_entry_price=effective_px,
                entry_bar_index=entry_idx,
                fill_bar_index=entry_idx,
                fill_ratio=1.0,
                entry_cost_pct=entry_cost,
                missed_reason=None,
            )

            # Updated opportunity with effective entry price
            updated_opp = InvestmentOpportunity(
                opportunity_id=opportunity.opportunity_id,
                symbol=opportunity.symbol,
                entry_bar_index=entry_idx,
                entry_timestamp_ms=opportunity.entry_timestamp_ms,
                direction=opportunity.direction,
                entry_price=effective_px,
                take_profit_price=opportunity.take_profit_price,
                stop_loss_price=opportunity.stop_loss_price,
                max_holding_bars=opportunity.max_holding_bars,
                metadata=opportunity.metadata,
            )
            return res, updated_opp

        # Case 2: MAKER (Passive Limit Order) execution
        max_search = min(n_bars - 1, entry_idx + self.params.expiry_bars)
        spread_req_pct = (self.params.penetration_spread_multiple * self.params.half_spread_bps) / 10_000.0

        for b_idx in range(entry_idx, max_search + 1):
            bar = candles[b_idx]
            b_hi = float(bar["high"])
            b_lo = float(bar["low"])

            # Check if limit price was reached/penetrated
            is_touched = False
            is_penetrated = False

            if direction == TradeDirection.LONG:
                # To fill a long limit order, sellers must trade down to limit_px
                req_px = limit_px * (1.0 - spread_req_pct)
                if b_lo <= limit_px:
                    is_touched = True
                if b_lo <= req_px:
                    is_penetrated = True
            else:  # SHORT
                # To fill a short limit order, buyers must trade up to limit_px
                req_px = limit_px * (1.0 + spread_req_pct)
                if b_hi >= limit_px:
                    is_touched = True
                if b_hi >= req_px:
                    is_penetrated = True

            # If touched but required penetration depth not reached
            if is_touched and not is_penetrated and self.params.penetration_spread_multiple > 0:
                continue

            if is_penetrated or (is_touched and self.params.penetration_spread_multiple == 0):
                # Queue fill probability determination (deterministic pseudo-random based on bar timestamp)
                bar_ts = int(bar.get("open_time", bar.get("timestamp_ms", 0)))
                # Simple deterministic hash for fill test
                hash_val = ((bar_ts % 100_000) ^ (entry_idx * 31)) % 100
                fill_prob = self.params.queue_fill_probability * 100.0

                if hash_val < fill_prob:
                    # Filled! Apply adverse selection if configured
                    adv_sel_pct = self.params.adverse_selection_bps / 10_000.0
                    if direction == TradeDirection.LONG:
                        effective_px = limit_px * (1.0 + adv_sel_pct)
                    else:
                        effective_px = limit_px * (1.0 - adv_sel_pct)

                    entry_cost = self.params.maker_fee_bps / 10_000.0

                    res = ExecutionResult(
                        opportunity_id=opportunity.opportunity_id,
                        status=OrderFillStatus.FILLED,
                        execution_mode=self.params.mode,
                        intended_entry_price=limit_px,
                        effective_entry_price=effective_px,
                        entry_bar_index=entry_idx,
                        fill_bar_index=b_idx,
                        fill_ratio=1.0,
                        entry_cost_pct=entry_cost,
                        adverse_selection_pct=adv_sel_pct,
                    )

                    updated_opp = InvestmentOpportunity(
                        opportunity_id=opportunity.opportunity_id,
                        symbol=opportunity.symbol,
                        entry_bar_index=b_idx,
                        entry_timestamp_ms=int(bar.get("open_time", bar.get("timestamp_ms", 0))),
                        direction=opportunity.direction,
                        entry_price=effective_px,
                        take_profit_price=opportunity.take_profit_price,
                        stop_loss_price=opportunity.stop_loss_price,
                        max_holding_bars=max(1, opportunity.max_holding_bars - (b_idx - entry_idx)),
                        metadata=opportunity.metadata,
                    )
                    return res, updated_opp

        # Unfilled within expiry bars -> Canceled / Expired
        res = ExecutionResult(
            opportunity_id=opportunity.opportunity_id,
            status=OrderFillStatus.EXPIRED_UNFILLED,
            execution_mode=self.params.mode,
            intended_entry_price=limit_px,
            effective_entry_price=0.0,
            entry_bar_index=entry_idx,
            fill_bar_index=None,
            fill_ratio=0.0,
            entry_cost_pct=0.0,
            missed_reason="UNFILLED_WITHIN_EXPIRY",
        )
        return res, None
