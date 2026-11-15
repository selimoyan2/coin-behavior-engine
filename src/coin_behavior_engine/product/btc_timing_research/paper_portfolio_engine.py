"""Historical Paper Portfolio Simulator (Module 29.7).

Deterministic, spot-only paper portfolio accounting engine for BTC/USDT timing research:
1. Strict balance conservation: cash (USDT) + BTC holdings.
2. No leverage, no margin, no short selling, no synthetic credit.
3. Non-negative balance invariants strictly enforced at all times.
4. Seamless integration with TransactionCostEngine (fees, spread, slippage).
5. Comprehensive trade ledger and point-in-time equity curve tracking.
6. Realized and unrealized P&L computation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from coin_behavior_engine.product.btc_timing_research.historical_decision_engine import (
    HistoricalDecisionEngine,
    SimulatedDecisionRecord,
)
from coin_behavior_engine.product.btc_timing_research.historical_feature_adapter import (
    HistoricalFeatureAdapter,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BaseTimingPolicy,
)
from coin_behavior_engine.product.btc_timing_research.transaction_cost_model import (
    TradeCostBreakdown,
    TransactionCostEngine,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulatedTradeRecord:
    """Audit record for a single executed rebalancing trade."""
    trade_id: str
    decision_id: str
    timestamp_ms: int
    timestamp_iso: str
    side: str  # BUY or SELL
    nominal_price: float
    effective_price: float
    btc_quantity: float
    gross_usdt_value: float
    fee_usdt: float
    spread_cost_usdt: float
    slippage_cost_usdt: float
    total_cost_usdt: float
    net_usdt_impact: float
    usdt_balance_after: float
    btc_balance_after: float
    equity_usdt_after: float
    realized_pnl_usdt: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EquityPoint:
    """Point-in-time portfolio valuation snapshot."""
    timestamp_ms: int
    timestamp_iso: str
    btc_price: float
    usdt_balance: float
    btc_balance: float
    btc_equity_usdt: float
    total_equity_usdt: float
    actual_btc_allocation: float
    target_btc_allocation: float
    peak_equity_usdt: float
    drawdown_pct: float
    rebalance_executed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PaperPortfolioEngine:
    """Simulates spot-only historical execution and tracks portfolio equity."""

    def __init__(
        self,
        initial_capital_usdt: float = 10000.0,
        cost_profile_id: Any = "BASE_COST",
        turnover_controller: Optional[Any] = None,
    ):
        if initial_capital_usdt <= 0:
            raise ValueError(f"Initial capital must be positive, got {initial_capital_usdt}")
        self.initial_capital_usdt = float(initial_capital_usdt)
        if isinstance(cost_profile_id, TransactionCostEngine):
            self.cost_engine = cost_profile_id
        else:
            self.cost_engine = TransactionCostEngine(str(cost_profile_id))
        self.turnover_controller = turnover_controller

        # Internal state
        self.usdt_balance: float = self.initial_capital_usdt
        self.btc_balance: float = 0.0
        self.avg_cost_basis: float = 0.0  # For realized P&L calculation
        self.total_realized_pnl: float = 0.0

        # Ledgers
        self.trades: List[SimulatedTradeRecord] = []
        self.equity_curve: List[EquityPoint] = []
        self.peak_equity: float = self.initial_capital_usdt

    def current_equity(self, current_btc_price: float) -> float:
        """Calculate current total portfolio equity in USDT."""
        return self.usdt_balance + (self.btc_balance * current_btc_price)

    def current_allocation(self, current_btc_price: float) -> float:
        """Calculate current actual BTC allocation fraction in [0, 1]."""
        eq = self.current_equity(current_btc_price)
        if eq <= 1e-6:
            return 0.0
        return (self.btc_balance * current_btc_price) / eq

    def execute_rebalance(
        self,
        decision: SimulatedDecisionRecord,
        execution_price: float,
    ) -> Optional[SimulatedTradeRecord]:
        """Execute portfolio rebalancing to match target allocation at execution_price."""
        if execution_price <= 0:
            raise ValueError(f"Execution price must be positive, got {execution_price}")

        eq = self.current_equity(execution_price)
        target_alloc = decision.target_btc_allocation
        target_btc_equity = eq * target_alloc
        current_btc_equity = self.btc_balance * execution_price
        diff_usdt = target_btc_equity - current_btc_equity

        # Rebalance threshold: only trade if required shift > 0.5% of equity or > $10
        if abs(diff_usdt) < max(10.0, eq * 0.005):
            return None

        # Turnover controller evaluation if active
        if self.turnover_controller is not None:
            current_actual_alloc = self.current_allocation(execution_price)
            approved, adj_target, rejection_reason, msg = self.turnover_controller.evaluate_rebalance_proposal(
                timestamp_ms=decision.simulated_execution_timestamp_ms,
                timestamp_iso=decision.simulated_execution_timestamp_iso,
                current_actual_alloc=current_actual_alloc,
                proposed_target_alloc=target_alloc,
                current_equity_usdt=eq,
                execution_price=execution_price,
            )
            if not approved:
                return None

        trade_id = f"TRD-{uuid.uuid4().hex[:12].upper()}"
        ts_ms = decision.simulated_execution_timestamp_ms
        ts_iso = decision.simulated_execution_timestamp_iso
        realized_pnl = 0.0

        if diff_usdt > 0:
            # BUY BTC with USDT cash
            # Determine max spendable USDT including fees
            # effective_price = execution_price * (1 + spread/2 + slippage)
            costs = self.cost_engine.compute_costs(diff_usdt, execution_price, is_buy=True)
            # Ensure we do not spend more USDT than available
            spendable_usdt = min(diff_usdt, self.usdt_balance)
            if spendable_usdt <= 1.0:
                return None

            # Re-estimate quantity with effective price
            eff_price = costs.effective_execution_price
            fee_rate = self.cost_engine.profile.taker_fee_pct

            # Total spend: qty * eff_price + fee = qty * eff_price * (1 + fee_rate) <= spendable_usdt
            btc_qty_to_buy = spendable_usdt / (eff_price * (1.0 + fee_rate))
            nominal_val = btc_qty_to_buy * execution_price
            costs = self.cost_engine.compute_costs(nominal_val, execution_price, is_buy=True)
            total_cash_needed = nominal_val + costs.fee_usdt

            # Adjust if slightly exceeds due to rounding
            if total_cash_needed > self.usdt_balance:
                btc_qty_to_buy = self.usdt_balance / (eff_price * (1.0 + fee_rate))
                nominal_val = btc_qty_to_buy * execution_price
                costs = self.cost_engine.compute_costs(nominal_val, execution_price, is_buy=True)
                total_cash_needed = nominal_val + costs.fee_usdt

            # Update cost basis
            old_btc_val = self.btc_balance * self.avg_cost_basis
            new_btc_val = btc_qty_to_buy * costs.effective_execution_price
            self.btc_balance += btc_qty_to_buy
            self.avg_cost_basis = (old_btc_val + new_btc_val) / max(self.btc_balance, 1e-9)

            # Deduct cash
            self.usdt_balance -= total_cash_needed
            self.usdt_balance = max(0.0, self.usdt_balance)  # Prevent micro floating-point negative

            side = "BUY"
            net_impact = -total_cash_needed

        else:
            # SELL BTC to USDT cash
            usdt_to_raise = abs(diff_usdt)
            btc_qty_to_sell = usdt_to_raise / execution_price
            # Cannot sell more BTC than held
            btc_qty_to_sell = min(btc_qty_to_sell, self.btc_balance)
            if btc_qty_to_sell <= 1e-8:
                return None

            nominal_val = btc_qty_to_sell * execution_price
            costs = self.cost_engine.compute_costs(nominal_val, execution_price, is_buy=False)
            net_cash_received = (btc_qty_to_sell * costs.effective_execution_price) - costs.fee_usdt

            # Calculate realized P&L on sold portion
            realized_pnl = (costs.effective_execution_price - self.avg_cost_basis) * btc_qty_to_sell - costs.fee_usdt
            self.total_realized_pnl += realized_pnl

            self.btc_balance -= btc_qty_to_sell
            self.btc_balance = max(0.0, self.btc_balance)
            if self.btc_balance <= 1e-8:
                self.btc_balance = 0.0
                self.avg_cost_basis = 0.0

            self.usdt_balance += max(0.0, net_cash_received)

            side = "SELL"
            net_impact = net_cash_received

        eq_after = self.current_equity(execution_price)

        trade = SimulatedTradeRecord(
            trade_id=trade_id,
            decision_id=decision.decision_id,
            timestamp_ms=ts_ms,
            timestamp_iso=ts_iso,
            side=side,
            nominal_price=round(execution_price, 4),
            effective_price=costs.effective_execution_price,
            btc_quantity=round(btc_qty_to_buy if side == "BUY" else btc_qty_to_sell, 8),
            gross_usdt_value=costs.trade_value_usdt,
            fee_usdt=costs.fee_usdt,
            spread_cost_usdt=costs.spread_cost_usdt,
            slippage_cost_usdt=costs.slippage_cost_usdt,
            total_cost_usdt=costs.total_transaction_cost_usdt,
            net_usdt_impact=round(net_impact, 4),
            usdt_balance_after=round(self.usdt_balance, 4),
            btc_balance_after=round(self.btc_balance, 8),
            equity_usdt_after=round(eq_after, 4),
            realized_pnl_usdt=round(realized_pnl, 4),
        )
        self.trades.append(trade)
        if self.turnover_controller is not None:
            self.turnover_controller.record_executed_trade(ts_ms, trade.gross_usdt_value)
        return trade

    def record_snapshot(
        self,
        timestamp_ms: int,
        timestamp_iso: str,
        btc_price: float,
        target_allocation: float,
        rebalance_executed: bool = False,
    ) -> EquityPoint:
        """Record valuation snapshot and compute running drawdown."""
        btc_eq = self.btc_balance * btc_price
        total_eq = self.usdt_balance + btc_eq
        alloc = btc_eq / max(total_eq, 1e-6)

        if total_eq > self.peak_equity:
            self.peak_equity = total_eq

        dd = (self.peak_equity - total_eq) / max(self.peak_equity, 1e-6)

        pt = EquityPoint(
            timestamp_ms=timestamp_ms,
            timestamp_iso=timestamp_iso,
            btc_price=round(btc_price, 4),
            usdt_balance=round(self.usdt_balance, 4),
            btc_balance=round(self.btc_balance, 8),
            btc_equity_usdt=round(btc_eq, 4),
            total_equity_usdt=round(total_eq, 4),
            actual_btc_allocation=round(alloc, 4),
            target_btc_allocation=round(target_allocation, 4),
            peak_equity_usdt=round(self.peak_equity, 4),
            drawdown_pct=round(dd * 100.0, 4),
            rebalance_executed=rebalance_executed,
        )
        self.equity_curve.append(pt)
        return pt


def run_historical_simulation(
    df_features: pd.DataFrame,
    policy: BaseTimingPolicy,
    initial_capital_usdt: float = 10000.0,
    cost_profile_id: str = "BASE_COST",
    start_index: int = 50,  # Warm-up window
    turnover_controller: Optional[Any] = None,
) -> Tuple[PaperPortfolioEngine, List[SimulatedDecisionRecord]]:
    """Run full point-in-time simulation over pre-calculated feature DataFrame.

    Strictly no-lookahead:
    - At index i, features are from completed candle i.
    - Decision is evaluated using candle i.
    - Rebalance order executes at candle i+1 open price.
    """
    engine = PaperPortfolioEngine(
        initial_capital_usdt=initial_capital_usdt,
        cost_profile_id=cost_profile_id,
        turnover_controller=turnover_controller,
    )
    decision_engine = HistoricalDecisionEngine(policy=policy)
    decisions: List[SimulatedDecisionRecord] = []

    n = len(df_features)
    if n <= start_index + 1:
        raise ValueError(f"Insufficient candles ({n}) for simulation starting at index {start_index}")

    records = df_features.to_dict("records")

    # Initial valuation snapshot before first trade
    first_candle = records[start_index]
    engine.record_snapshot(
        timestamp_ms=int(first_candle["open_time"]),
        timestamp_iso=str(first_candle.get("datetime_utc", "")),
        btc_price=float(first_candle["open"]),
        target_allocation=0.0,
        rebalance_executed=False,
    )

    for i in range(start_index, n - 1):
        candle_i = records[i]
        next_candle = records[i + 1]
        next_open_price = float(next_candle["open"])
        next_open_time_ms = int(next_candle["open_time"])
        next_open_time_iso = str(next_candle.get("datetime_utc", ""))

        current_alloc = engine.current_allocation(float(candle_i["close"]))

        # 1. Point-in-time decision
        dec = decision_engine.evaluate_step(
            current_candle_row=candle_i,
            next_candle_open_price=next_open_price,
            current_btc_allocation=current_alloc,
        )
        decisions.append(dec)

        # 2. Execution at next open
        trade = None
        if dec.rebalance_required:
            trade = engine.execute_rebalance(dec, execution_price=next_open_price)

        # 3. Snapshot recording after execution at next candle open
        engine.record_snapshot(
            timestamp_ms=next_open_time_ms,
            timestamp_iso=next_open_time_iso,
            btc_price=next_open_price,
            target_allocation=dec.target_btc_allocation,
            rebalance_executed=(trade is not None),
        )

    return engine, decisions
