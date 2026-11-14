"""Performance & Risk Analytics Engine (Module 29.8).

Computes comprehensive point-in-time risk and return metrics for historical BTC paper portfolios:
1. Returns: Gross return, net return, annualized return.
2. Drawdowns: Peak-to-trough max drawdown, drawdown duration.
3. Volatilities: Annualized return volatility, downside semi-deviation.
4. Risk-adjusted ratios: Sharpe ratio, Sortino ratio, Calmar ratio.
5. Trading metrics: Trade count, win rate, turnover, fee/spread/slippage drag.
6. Exposure: Time invested in BTC percentage.
7. Benchmark comparisons: Excess return over Buy-and-Hold, excess return over Cash.
8. Explicit handling of undefined metrics (e.g. 0 trades, 0 downside deviation).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    EquityPoint,
    PaperPortfolioEngine,
    SimulatedTradeRecord,
)


@dataclass(frozen=True)
class PerformanceMetricsReport:
    """Comprehensive performance and risk analytics report."""
    initial_capital_usdt: float
    ending_equity_usdt: float
    gross_pnl_usdt: float
    net_pnl_usdt: float
    net_return_pct: float
    annualized_return_pct: Optional[float]
    max_drawdown_pct: float
    annualized_volatility_pct: Optional[float]
    downside_volatility_pct: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Optional[float]
    turnover_pct: float
    total_fees_usdt: float
    total_spread_cost_usdt: float
    total_slippage_cost_usdt: float
    total_transaction_costs_usdt: float
    cost_drag_pct: float
    time_invested_pct: float
    observation_hours: int
    benchmark_buy_and_hold_return_pct: Optional[float] = None
    benchmark_cash_return_pct: float = 0.0
    excess_return_over_bnh_pct: Optional[float] = None
    risk_adjusted_excess: Optional[float] = None
    metric_limitations: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class PerformanceAnalyticsEngine:
    """Computes transparent risk and return metrics with explicit limitations."""

    HOURLY_ANNUALIZATION_FACTOR = math.sqrt(8760)  # 24 * 365 = 8760 hours per year
    ANNUAL_HOURS = 8760.0

    @classmethod
    def calculate_metrics(
        cls,
        engine: PaperPortfolioEngine,
        bnh_net_return_pct: Optional[float] = None,
    ) -> PerformanceMetricsReport:
        """Calculate complete performance suite from simulation engine."""
        curve = engine.equity_curve
        trades = engine.trades
        init_cap = engine.initial_capital_usdt
        limitations: List[str] = []

        if not curve or len(curve) < 2:
            return PerformanceMetricsReport(
                initial_capital_usdt=init_cap,
                ending_equity_usdt=init_cap,
                gross_pnl_usdt=0.0,
                net_pnl_usdt=0.0,
                net_return_pct=0.0,
                annualized_return_pct=None,
                max_drawdown_pct=0.0,
                annualized_volatility_pct=None,
                downside_volatility_pct=None,
                sharpe_ratio=None,
                sortino_ratio=None,
                calmar_ratio=None,
                trade_count=0,
                winning_trades=0,
                losing_trades=0,
                win_rate_pct=None,
                turnover_pct=0.0,
                total_fees_usdt=0.0,
                total_spread_cost_usdt=0.0,
                total_slippage_cost_usdt=0.0,
                total_transaction_costs_usdt=0.0,
                cost_drag_pct=0.0,
                time_invested_pct=0.0,
                observation_hours=0,
                metric_limitations=["INSUFFICIENT_OBSERVATIONS: Fewer than 2 equity points."],
            )

        end_eq = curve[-1].total_equity_usdt
        net_pnl = end_eq - init_cap
        net_ret = (net_pnl / init_cap) * 100.0

        # Cost accounting
        total_fees = sum(t.fee_usdt for t in trades)
        total_spread = sum(t.spread_cost_usdt for t in trades)
        total_slippage = sum(t.slippage_cost_usdt for t in trades)
        total_costs = total_fees + total_spread + total_slippage
        gross_pnl = net_pnl + total_costs
        cost_drag_pct = (total_costs / init_cap) * 100.0

        # Max drawdown
        drawdowns = [pt.drawdown_pct for pt in curve]
        max_dd = max(drawdowns) if drawdowns else 0.0

        # Returns series
        equities = pd.Series([pt.total_equity_usdt for pt in curve])
        hourly_rets = equities.pct_change().dropna()
        n_hours = len(hourly_rets)

        # Annualized return (only if n_hours >= 168 ~ 1 week)
        ann_ret: Optional[float] = None
        if n_hours >= 168:
            years = n_hours / cls.ANNUAL_HOURS
            if end_eq > 0 and years > 0:
                ann_ret = round(((end_eq / init_cap) ** (1.0 / years) - 1.0) * 100.0, 2)
        else:
            limitations.append("SAMPLE_TOO_SHORT: Annualized metrics omitted for periods under 168 hours.")

        # Volatility
        vol_ann: Optional[float] = None
        downside_vol_ann: Optional[float] = None
        sharpe: Optional[float] = None
        sortino: Optional[float] = None
        calmar: Optional[float] = None

        if len(hourly_rets) > 10:
            std_hourly = float(hourly_rets.std())
            if std_hourly > 1e-8:
                vol_ann = round(std_hourly * cls.HOURLY_ANNUALIZATION_FACTOR * 100.0, 2)
                # Sharpe: mean_hourly / std_hourly * sqrt(8760) (zero risk-free rate assumed for USDT)
                mean_hourly = float(hourly_rets.mean())
                raw_sharpe = (mean_hourly / std_hourly) * cls.HOURLY_ANNUALIZATION_FACTOR
                sharpe = round(float(raw_sharpe), 2)
            else:
                sharpe = None
                limitations.append("ZERO_VARIANCE: Return standard deviation is zero.")

            # Downside semi-deviation (negative returns only)
            neg_rets = hourly_rets[hourly_rets < 0]
            if len(neg_rets) > 2:
                downside_std = math.sqrt(float((neg_rets ** 2).mean()))
                if downside_std > 1e-8:
                    downside_vol_ann = round(downside_std * cls.HOURLY_ANNUALIZATION_FACTOR * 100.0, 2)
                    mean_hourly = float(hourly_rets.mean())
                    raw_sortino = (mean_hourly / downside_std) * cls.HOURLY_ANNUALIZATION_FACTOR
                    sortino = round(float(raw_sortino), 2)
            else:
                sortino = None
                limitations.append("NO_DOWNSIDE_RETURNS: Downside deviation undefined (too few negative hourly periods).")

            # Calmar: Annualized Return / Max Drawdown
            if ann_ret is not None and max_dd > 0.01:
                calmar = round(ann_ret / max_dd, 2)
            elif max_dd <= 0.01:
                calmar = None
                limitations.append("ZERO_DRAWDOWN: Calmar ratio undefined when max drawdown is zero.")

        # Trade metrics
        trade_count = len(trades)
        winning_trades = 0
        losing_trades = 0
        win_rate: Optional[float] = None

        sell_trades = [t for t in trades if t.side == "SELL"]
        if sell_trades:
            for st in sell_trades:
                if st.realized_pnl_usdt > 0:
                    winning_trades += 1
                elif st.realized_pnl_usdt < 0:
                    losing_trades += 1
            evaluated_trades = winning_trades + losing_trades
            if evaluated_trades > 0:
                win_rate = round((winning_trades / evaluated_trades) * 100.0, 2)
        else:
            limitations.append("NO_CLOSED_TRADES: Win rate undefined when no positions have been closed.")

        total_turnover_usdt = sum(t.gross_usdt_value for t in trades)
        turnover_pct = round((total_turnover_usdt / init_cap) * 100.0, 2)

        # Time invested in BTC
        hours_invested = sum(1 for pt in curve if pt.actual_btc_allocation > 0.05)
        time_invested_pct = round((hours_invested / max(len(curve), 1)) * 100.0, 2)

        # Benchmark comparison
        excess_bnh: Optional[float] = None
        if bnh_net_return_pct is not None:
            excess_bnh = round(net_ret - bnh_net_return_pct, 2)

        return PerformanceMetricsReport(
            initial_capital_usdt=round(init_cap, 2),
            ending_equity_usdt=round(end_eq, 2),
            gross_pnl_usdt=round(gross_pnl, 2),
            net_pnl_usdt=round(net_pnl, 2),
            net_return_pct=round(net_ret, 2),
            annualized_return_pct=ann_ret,
            max_drawdown_pct=round(max_dd, 2),
            annualized_volatility_pct=vol_ann,
            downside_volatility_pct=downside_vol_ann,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            trade_count=trade_count,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=win_rate,
            turnover_pct=turnover_pct,
            total_fees_usdt=round(total_fees, 2),
            total_spread_cost_usdt=round(total_spread, 2),
            total_slippage_cost_usdt=round(total_slippage, 2),
            total_transaction_costs_usdt=round(total_costs, 2),
            cost_drag_pct=round(cost_drag_pct, 2),
            time_invested_pct=time_invested_pct,
            observation_hours=n_hours,
            benchmark_buy_and_hold_return_pct=round(bnh_net_return_pct, 2) if bnh_net_return_pct is not None else None,
            benchmark_cash_return_pct=0.0,
            excess_return_over_bnh_pct=excess_bnh,
            metric_limitations=limitations,
        )
