"""Investment-oriented net-return evaluator for historical strategy discovery.

Transforms predictive signals into risk-adjusted simulated trades with:
- Realistic fee, spread, and slippage cost modeling.
- Exact TP/SL and time-horizon exit simulations.
- Max Favorable Excursion (MFE) and Max Adverse Excursion (MAE).
- Portfolio metrics: Sharpe, Sortino, Calmar, Max Drawdown, Profit Factor,
  Expectancy, Exposure, and count of non-overlapping independent opportunities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Mapping, Sequence


class TradeDirection(str, Enum):
    """Direction of investment trade."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class TradeCostModel:
    """Realistic cost model for cryptocurrency spot/derivatives execution."""

    taker_fee_bps: float = 5.0  # 0.05%
    maker_fee_bps: float = 2.0  # 0.02%
    half_spread_bps: float = 1.0  # 0.01%
    slippage_bps: float = 2.0  # 0.02%
    use_maker_entry: bool = False
    use_maker_exit: bool = False

    @property
    def entry_cost_pct(self) -> float:
        fee = self.maker_fee_bps if self.use_maker_entry else self.taker_fee_bps
        return (fee + self.half_spread_bps + self.slippage_bps) / 10_000.0

    @property
    def exit_cost_pct(self) -> float:
        fee = self.maker_fee_bps if self.use_maker_exit else self.taker_fee_bps
        return (fee + self.half_spread_bps + self.slippage_bps) / 10_000.0

    @property
    def total_roundtrip_cost_pct(self) -> float:
        return self.entry_cost_pct + self.exit_cost_pct

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InvestmentOpportunity:
    """Hypothetical trade opportunity proposed by a research signal."""

    opportunity_id: str
    symbol: str
    entry_bar_index: int
    entry_timestamp_ms: int
    direction: TradeDirection
    entry_price: float
    take_profit_price: float
    stop_loss_price: float
    max_holding_bars: int = 24  # e.g. 2 hours on 5m
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["direction"] = self.direction.value
        return d


@dataclass(frozen=True)
class SimulatedTradeResult:
    """Detailed outcome of a simulated trade."""

    opportunity_id: str
    direction: TradeDirection
    entry_price: float
    exit_price: float
    entry_timestamp_ms: int
    exit_timestamp_ms: int
    entry_bar_index: int
    exit_bar_index: int
    exit_reason: str  # "TAKE_PROFIT", "STOP_LOSS", "HORIZON_EXPIRY"
    holding_bars: int
    gross_return_pct: float
    net_return_pct: float
    total_cost_pct: float
    mfe_pct: float  # Max favorable excursion
    mae_pct: float  # Max adverse excursion
    is_win: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["direction"] = self.direction.value
        return d


@dataclass(frozen=True)
class PortfolioEvaluationReport:
    """Comprehensive performance and risk report."""

    total_opportunities: int
    executed_trades: int
    independent_opportunities_count: int
    win_count: int
    loss_count: int
    win_rate: float
    gross_profit_pct: float
    gross_loss_pct: float
    profit_factor: float
    net_expectancy_pct: float
    total_net_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_holding_bars: float
    exposure_pct: float
    total_costs_paid_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InvestmentEvaluator:
    """Simulates trade execution with realistic costs and institutional risk metrics."""

    def __init__(self, default_cost_model: TradeCostModel | None = None) -> None:
        self.cost_model = default_cost_model or TradeCostModel()

    def simulate_trade(
        self,
        opp: InvestmentOpportunity,
        candles: Sequence[Mapping[str, Any]],
        cost_model: TradeCostModel | None = None,
    ) -> SimulatedTradeResult | None:
        """Simulate single trade forward through candles from opp.entry_bar_index."""
        costs = cost_model or self.cost_model
        entry_idx = opp.entry_bar_index
        n_candles = len(candles)

        if entry_idx >= n_candles - 1:
            return None

        # Effective entry price incorporating entry slippage/costs
        entry_px = opp.entry_price
        direction = opp.direction

        max_bar = min(n_candles - 1, entry_idx + opp.max_holding_bars)
        exit_bar = max_bar
        exit_px = float(candles[max_bar]["close"])
        exit_reason = "HORIZON_EXPIRY"
        exit_ts = int(candles[max_bar].get("open_time", candles[max_bar].get("timestamp_ms", max_bar)))

        mfe = 0.0
        mae = 0.0

        for b_idx in range(entry_idx + 1, max_bar + 1):
            bar = candles[b_idx]
            b_hi = float(bar["high"])
            b_lo = float(bar["low"])
            b_cl = float(bar["close"])
            b_ts = int(bar.get("open_time", bar.get("timestamp_ms", b_idx)))

            if direction == TradeDirection.LONG:
                # Excursions
                favorable = (b_hi - entry_px) / entry_px
                adverse = (entry_px - b_lo) / entry_px
                mfe = max(mfe, favorable)
                mae = max(mae, adverse)

                # Check SL hit
                if b_lo <= opp.stop_loss_price:
                    exit_bar = b_idx
                    exit_px = opp.stop_loss_price
                    exit_reason = "STOP_LOSS"
                    exit_ts = b_ts
                    break

                # Check TP hit
                if b_hi >= opp.take_profit_price:
                    exit_bar = b_idx
                    exit_px = opp.take_profit_price
                    exit_reason = "TAKE_PROFIT"
                    exit_ts = b_ts
                    break

            else:  # SHORT
                favorable = (entry_px - b_lo) / entry_px
                adverse = (b_hi - entry_px) / entry_px
                mfe = max(mfe, favorable)
                mae = max(mae, adverse)

                # Check SL hit
                if b_hi >= opp.stop_loss_price:
                    exit_bar = b_idx
                    exit_px = opp.stop_loss_price
                    exit_reason = "STOP_LOSS"
                    exit_ts = b_ts
                    break

                # Check TP hit
                if b_lo <= opp.take_profit_price:
                    exit_bar = b_idx
                    exit_px = opp.take_profit_price
                    exit_reason = "TAKE_PROFIT"
                    exit_ts = b_ts
                    break

        # Calculate gross and net returns
        if direction == TradeDirection.LONG:
            gross_ret = (exit_px - entry_px) / entry_px
        else:
            gross_ret = (entry_px - exit_px) / entry_px

        total_costs = costs.total_roundtrip_cost_pct
        net_ret = gross_ret - total_costs
        holding_bars = exit_bar - entry_idx

        return SimulatedTradeResult(
            opportunity_id=opp.opportunity_id,
            direction=direction,
            entry_price=entry_px,
            exit_price=exit_px,
            entry_timestamp_ms=opp.entry_timestamp_ms,
            exit_timestamp_ms=exit_ts,
            entry_bar_index=entry_idx,
            exit_bar_index=exit_bar,
            exit_reason=exit_reason,
            holding_bars=holding_bars,
            gross_return_pct=gross_ret,
            net_return_pct=net_ret,
            total_cost_pct=total_costs,
            mfe_pct=mfe,
            mae_pct=mae,
            is_win=net_ret > 0.0,
        )

    def evaluate_opportunities(
        self,
        opportunities: Sequence[InvestmentOpportunity],
        candles: Sequence[Mapping[str, Any]],
        cost_model: TradeCostModel | None = None,
    ) -> tuple[list[SimulatedTradeResult], PortfolioEvaluationReport]:
        """Simulate all opportunities and calculate aggregate portfolio risk/return metrics."""
        costs = cost_model or self.cost_model
        results: list[SimulatedTradeResult] = []

        for opp in opportunities:
            res = self.simulate_trade(opp, candles, costs)
            if res is not None:
                results.append(res)

        if not results:
            empty_report = PortfolioEvaluationReport(
                total_opportunities=len(opportunities),
                executed_trades=0,
                independent_opportunities_count=0,
                win_count=0,
                loss_count=0,
                win_rate=0.0,
                gross_profit_pct=0.0,
                gross_loss_pct=0.0,
                profit_factor=0.0,
                net_expectancy_pct=0.0,
                total_net_return_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                avg_holding_bars=0.0,
                exposure_pct=0.0,
                total_costs_paid_pct=0.0,
            )
            return results, empty_report

        # 1. Independent non-overlapping opportunities count (Greedy interval scheduling)
        sorted_by_exit = sorted(results, key=lambda r: r.exit_bar_index)
        independent_count = 0
        last_exit_bar = -1
        for r in sorted_by_exit:
            if r.entry_bar_index >= last_exit_bar:
                independent_count += 1
                last_exit_bar = r.exit_bar_index

        # 2. Win / Loss stats
        wins = [r for r in results if r.is_win]
        losses = [r for r in results if not r.is_win]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / len(results) if results else 0.0

        gross_profit = sum(r.gross_return_pct for r in results if r.gross_return_pct > 0)
        gross_loss = sum(abs(r.gross_return_pct) for r in results if r.gross_return_pct < 0)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 1e-9 else (99.0 if gross_profit > 0 else 0.0)

        net_returns = [r.net_return_pct for r in results]
        total_net_ret = sum(net_returns)
        net_expectancy = sum(net_returns) / len(net_returns)
        total_costs_paid = sum(r.total_cost_pct for r in results)

        # 3. Drawdown calculation (cumulative equity curve)
        cum_equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for ret in net_returns:
            cum_equity *= (1.0 + ret)
            if cum_equity > peak:
                peak = cum_equity
            dd = (peak - cum_equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        # 4. Risk-adjusted metrics (Sharpe, Sortino, Calmar)
        if len(net_returns) > 1:
            mean_ret = sum(net_returns) / len(net_returns)
            variance = sum((x - mean_ret) ** 2 for x in net_returns) / (len(net_returns) - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 1e-9
            # Annualized factor assuming ~1000 trades/year or standard sqrt(N)
            annual_factor = math.sqrt(len(net_returns))
            sharpe = (mean_ret / std_dev) * annual_factor if std_dev > 1e-9 else 0.0

            downside_returns = [x for x in net_returns if x < 0]
            if downside_returns:
                downside_var = sum(x ** 2 for x in downside_returns) / len(downside_returns)
                downside_dev = math.sqrt(downside_var) if downside_var > 0 else 1e-9
                sortino = (mean_ret / downside_dev) * annual_factor if downside_dev > 1e-9 else 0.0
            else:
                sortino = 99.0 if mean_ret > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        calmar = (total_net_ret / max_dd) if max_dd > 1e-9 else (99.0 if total_net_ret > 0 else 0.0)

        # 5. Holding and exposure
        avg_holding = sum(r.holding_bars for r in results) / len(results)
        total_bars_span = len(candles)
        total_held_bars = sum(r.holding_bars for r in results)
        exposure = min(1.0, total_held_bars / total_bars_span) if total_bars_span > 0 else 0.0

        report = PortfolioEvaluationReport(
            total_opportunities=len(opportunities),
            executed_trades=len(results),
            independent_opportunities_count=independent_count,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            gross_profit_pct=gross_profit,
            gross_loss_pct=gross_loss,
            profit_factor=profit_factor,
            net_expectancy_pct=net_expectancy,
            total_net_return_pct=total_net_ret,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            avg_holding_bars=avg_holding,
            exposure_pct=exposure,
            total_costs_paid_pct=total_costs_paid,
        )

        return results, report
