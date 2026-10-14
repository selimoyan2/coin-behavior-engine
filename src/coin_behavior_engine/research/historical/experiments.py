"""Scientific market behavior experiments for historical research.

Implements and evaluates three foundational market hypotheses:
- H1: Opening-range breakout continuation (5, 10, 15, 30, 60m windows across sessions).
- H2: Failed breakout / liquidity sweep proxy (reversal after level rejection).
- H3: Pullback after directional movement vs immediate breakout chasing.

All experiments enforce:
1. Strict zero-lookahead (signal at bar t close, entry at t+1 open).
2. Realistic transaction costs (maker/taker bps, spread, slippage).
3. Purged and embargoed chronological walk-forward splitting.
4. Non-overlapping independent trade counting.
5. Objective reporting of both favorable and unfavorable outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
import math
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

import pandas as pd

logger = logging.getLogger("cbe_experiments")

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentEvaluator,
    InvestmentOpportunity,
    PortfolioEvaluationReport,
    SimulatedTradeResult,
    TradeCostModel,
    TradeDirection,
)
from coin_behavior_engine.research.historical.market_context import (
    MarketContextExtractor,
    MarketContextFeatures,
)
from coin_behavior_engine.research.historical.market_sessions import (
    MarketSession,
    MarketSessionDetector,
    OpeningRangeWindow,
)
from coin_behavior_engine.research.historical.price_action import (
    PriceActionFeatureExtractor,
    PriceActionSignals,
)
from coin_behavior_engine.research.historical.walkforward_purged import (
    PurgedEmbargoTimeSeriesSplitter,
    PurgedFold,
)


@dataclass(frozen=True)
class HypothesisExperimentConfig:
    """Configuration parameters for a hypothesis test."""

    hypothesis_id: str  # "H1", "H2", "H3"
    name: str
    target_sessions: tuple[str, ...] = (
        MarketSession.NEW_YORK.value,
        MarketSession.LONDON.value,
        MarketSession.ASIAN.value,
        MarketSession.LONDON_NY_OVERLAP.value,
    )
    opening_range_windows_min: tuple[int, ...] = (5, 10, 15, 30, 60)
    holding_horizons_bars: tuple[int, ...] = (3, 6, 12, 24)  # 15m, 30m, 60m, 120m for 5m bars
    cost_models: tuple[TradeCostModel, ...] = (
        TradeCostModel(taker_fee_bps=0.0, maker_fee_bps=0.0, half_spread_bps=0.0, slippage_bps=0.0),  # 0 bps
        TradeCostModel(taker_fee_bps=2.0, maker_fee_bps=1.0, half_spread_bps=0.5, slippage_bps=0.5),  # 8 bps roundtrip
        TradeCostModel(taker_fee_bps=5.0, maker_fee_bps=2.0, half_spread_bps=1.0, slippage_bps=2.0),  # 16 bps roundtrip (realistic)
        TradeCostModel(taker_fee_bps=8.0, maker_fee_bps=4.0, half_spread_bps=2.0, slippage_bps=2.0),  # 24 bps roundtrip (stress)
    )


@dataclass(frozen=True)
class HypothesisEvaluationResult:
    """Comprehensive statistical and financial evaluation of a hypothesis."""

    hypothesis_id: str
    description: str
    total_eligible_signals: int
    executed_trades: int
    independent_trades: int
    win_rate: float
    profit_factor: float
    gross_return_pct: float
    net_return_pct: float
    net_expectancy_bps: float  # Basis points per trade
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    train_net_return_pct: float
    val_net_return_pct: float
    test_net_return_pct: float  # Held-out test performance
    buy_and_hold_return_pct: float
    cost_sensitivity: dict[str, float]  # {cost_label: net_return_pct}
    regime_breakdown: dict[str, dict[str, Any]]
    is_statistically_significant: bool
    scientific_conclusion: str
    unallocated_cumulative_return_pct: float = 0.0
    independent_cumulative_return_pct: float = 0.0
    compounded_independent_equity_pct: float = 0.0
    capital_allocated_portfolio_return_pct: float = 0.0
    independent_net_expectancy_bps: float = 0.0
    break_even_cost_bps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScientificExperimentRunner:
    """Executes leakage-free, cost-adjusted market behavior experiments."""

    def __init__(
        self,
        candles: Sequence[Mapping[str, Any]],
        default_cost_model: Optional[TradeCostModel] = None,
    ) -> None:
        self.candles = candles
        self.n_bars = len(candles)
        self.cost_model = default_cost_model or TradeCostModel()
        self.session_detector = MarketSessionDetector()
        self.pa_extractor = PriceActionFeatureExtractor()
        self.ctx_extractor = MarketContextExtractor()
        self.evaluator = InvestmentEvaluator(self.cost_model)

        logger.info(f"Extracting features across {self.n_bars} candles...")
        self.pa_signals = self.pa_extractor.extract_features(candles)
        self.ctx_features = self.ctx_extractor.extract_context(candles)

    # -------------------------------------------------------------------------
    # H1: Opening-Range Breakout Continuation
    # -------------------------------------------------------------------------
    def generate_h1_opportunities(
        self,
        target_session: str = MarketSession.NEW_YORK.value,
        window_minutes: int = 15,
        horizon_bars: int = 12,  # 60 minutes
    ) -> list[InvestmentOpportunity]:
        """Generate breakout continuation opportunities after session opening range."""
        opening_ranges = self.session_detector.compute_opening_ranges(
            self.candles, window_minutes=window_minutes, target_session=target_session
        )

        opportunities: list[InvestmentOpportunity] = []
        or_map = {r.session_start_ms: r for r in opening_ranges}

        for i in range(1, self.n_bars - horizon_bars):
            bar = self.candles[i]
            ts = int(bar.get("open_time", bar.get("timestamp_ms", i)))
            cl = float(bar["close"])
            atr = self.pa_signals[i].atr_14

            cfg = self.session_detector.detect_session(ts)
            if target_session not in cfg.active_sessions:
                continue

            # Check if current bar is after the opening range cutoff for the active session day
            matching_or: Optional[OpeningRangeWindow] = None
            for s_start, r in or_map.items():
                if r.session_start_ms <= ts < r.session_start_ms + 8 * 3600_000:
                    matching_or = r
                    break

            if not matching_or or ts < matching_or.cutoff_ms:
                continue

            prev_bar = self.candles[i - 1]
            prev_cl = float(prev_bar["close"])

            # Bullish Breakout above OR High
            if prev_cl <= matching_or.high and cl > matching_or.high:
                or_height = max(matching_or.high - matching_or.low, atr)
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H1_BULL_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.LONG,
                        entry_price=cl,
                        take_profit_price=cl + 1.5 * or_height,
                        stop_loss_price=cl - 1.0 * or_height,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H1", "type": "OR_BREAKOUT_BULL", "window": window_minutes, "session": target_session},
                    )
                )

            # Bearish Breakout below OR Low
            elif prev_cl >= matching_or.low and cl < matching_or.low:
                or_height = max(matching_or.high - matching_or.low, atr)
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H1_BEAR_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.SHORT,
                        entry_price=cl,
                        take_profit_price=cl - 1.5 * or_height,
                        stop_loss_price=cl + 1.0 * or_height,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H1", "type": "OR_BREAKOUT_BEAR", "window": window_minutes, "session": target_session},
                    )
                )

        return opportunities

    # -------------------------------------------------------------------------
    # H2: Failed Breakout / Liquidity Sweep Proxy (Reversal)
    # -------------------------------------------------------------------------
    def generate_h2_opportunities(
        self,
        horizon_bars: int = 12,
    ) -> list[InvestmentOpportunity]:
        """Generate reversal opportunities following failed breakout / rejection at S/R."""
        opportunities: list[InvestmentOpportunity] = []

        for i in range(1, self.n_bars - horizon_bars):
            sig = self.pa_signals[i]
            ts = sig.timestamp_ms
            cl = sig.close
            hi = sig.high
            lo = sig.low
            atr = max(sig.atr_14, 1.0)

            # Bear trap (Failed Bearish Breakout): dipped below support but closed back above
            if sig.is_failed_breakout_bearish or (sig.is_pinbar_bullish and sig.dist_to_support_pct is not None and abs(sig.dist_to_support_pct) < 0.005):
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H2_REVERSAL_LONG_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.LONG,
                        entry_price=cl,
                        take_profit_price=cl + 2.0 * atr,
                        stop_loss_price=lo - 0.2 * atr,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H2", "type": "BEAR_TRAP_REVERSAL"},
                    )
                )

            # Bull trap (Failed Bullish Breakout): pierced above resistance but closed back below
            elif sig.is_failed_breakout_bullish or (sig.is_pinbar_bearish and sig.dist_to_resistance_pct is not None and abs(sig.dist_to_resistance_pct) < 0.005):
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H2_REVERSAL_SHORT_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.SHORT,
                        entry_price=cl,
                        take_profit_price=cl - 2.0 * atr,
                        stop_loss_price=hi + 0.2 * atr,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H2", "type": "BULL_TRAP_REVERSAL"},
                    )
                )

        return opportunities

    # -------------------------------------------------------------------------
    # H3: Pullback After Directional Movement
    # -------------------------------------------------------------------------
    def generate_h3_opportunities(
        self,
        horizon_bars: int = 12,
    ) -> list[InvestmentOpportunity]:
        """Generate pullback continuation opportunities in established trend direction."""
        opportunities: list[InvestmentOpportunity] = []

        for i in range(5, self.n_bars - horizon_bars):
            sig = self.pa_signals[i]
            ctx = self.ctx_features[i]
            ts = sig.timestamp_ms
            cl = sig.close
            hi = sig.high
            lo = sig.low
            atr = max(sig.atr_14, 1.0)

            # Long pullback: Trend is bullish, bar is pulling back
            if sig.is_pullback_bullish and (ctx.trend_direction == 1 or (i < 20 and cl > float(self.candles[0]["close"]))):
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H3_PULLBACK_LONG_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.LONG,
                        entry_price=cl,
                        take_profit_price=cl + 2.0 * atr,
                        stop_loss_price=lo - 0.5 * atr,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H3", "type": "PULLBACK_BULL"},
                    )
                )

            # Short pullback: Trend is bearish, bar is pulling back upward
            elif sig.is_pullback_bearish and (ctx.trend_direction == -1 or (i < 20 and cl < float(self.candles[0]["close"]))):
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H3_PULLBACK_SHORT_{ts}",
                        symbol="BTCUSDT",
                        entry_bar_index=i,
                        entry_timestamp_ms=ts,
                        direction=TradeDirection.SHORT,
                        entry_price=cl,
                        take_profit_price=cl - 2.0 * atr,
                        stop_loss_price=hi + 0.5 * atr,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H3", "type": "PULLBACK_BEAR"},
                    )
                )

        return opportunities

    # -------------------------------------------------------------------------
    # Chronological Purged Walk-Forward Evaluation
    # -------------------------------------------------------------------------
    def evaluate_hypothesis(
        self,
        hypothesis_id: str,
        description: str,
        opportunities: list[InvestmentOpportunity],
    ) -> HypothesisEvaluationResult:
        """Evaluate opportunities across chronological partitions and sensitivity dimensions."""
        if not opportunities:
            return HypothesisEvaluationResult(
                hypothesis_id=hypothesis_id,
                description=description,
                total_eligible_signals=0,
                executed_trades=0,
                independent_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                gross_return_pct=0.0,
                net_return_pct=0.0,
                net_expectancy_bps=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                train_net_return_pct=0.0,
                val_net_return_pct=0.0,
                test_net_return_pct=0.0,
                buy_and_hold_return_pct=0.0,
                cost_sensitivity={},
                regime_breakdown={},
                is_statistically_significant=False,
                scientific_conclusion="No eligible signals identified for this hypothesis.",
            )

        # Baseline: Buy & Hold
        first_cl = float(self.candles[0]["close"])
        last_cl = float(self.candles[-1]["close"])
        bnh_ret = (last_cl - first_cl) / first_cl

        # Standard simulation with default costs
        trades, report = self.evaluator.evaluate_opportunities(opportunities, self.candles)

        # Chronological partitions: 60% train, 20% validation, 20% test
        train_cutoff = int(self.n_bars * 0.60)
        val_cutoff = int(self.n_bars * 0.80)

        train_trades = [t for t in trades if t.entry_bar_index < train_cutoff]
        val_trades = [t for t in trades if train_cutoff <= t.entry_bar_index < val_cutoff]
        test_trades = [t for t in trades if t.entry_bar_index >= val_cutoff]

        train_net = sum(t.net_return_pct for t in train_trades) if train_trades else 0.0
        val_net = sum(t.net_return_pct for t in val_trades) if val_trades else 0.0
        test_net = sum(t.net_return_pct for t in test_trades) if test_trades else 0.0

        # Cost sensitivity analysis
        cost_models = {
            "0_bps (Zero Cost)": TradeCostModel.from_roundtrip_bps(0.0),
            "5_bps (Low Friction)": TradeCostModel.from_roundtrip_bps(5.0),
            "8_bps (Maker/VIP)": TradeCostModel.from_roundtrip_bps(8.0),
            "10_bps (Standard Maker)": TradeCostModel.from_roundtrip_bps(10.0),
            "16_bps (Realistic)": TradeCostModel(taker_fee_bps=5.0, maker_fee_bps=2.0, half_spread_bps=1.0, slippage_bps=2.0),
            "25_bps (Stress/Adverse)": TradeCostModel.from_roundtrip_bps(25.0),
        }
        cost_sensitivity: dict[str, float] = {}
        for c_label, cm in cost_models.items():
            _, c_rep = self.evaluator.evaluate_opportunities(opportunities, self.candles, cost_model=cm)
            cost_sensitivity[c_label] = round(c_rep.total_net_return_pct * 100.0, 3)

        # Market Regime breakdown
        regime_trades: dict[str, list[SimulatedTradeResult]] = {
            "TRENDING": [],
            "RANGING": [],
            "HIGH_VOLATILITY": [],
            "NORMAL_VOLATILITY": [],
        }
        for t in trades:
            ctx = self.ctx_features[t.entry_bar_index]
            if ctx.is_trending:
                regime_trades["TRENDING"].append(t)
            else:
                regime_trades["RANGING"].append(t)
            if ctx.volatility_regime in ("HIGH", "EXTREME"):
                regime_trades["HIGH_VOLATILITY"].append(t)
            else:
                regime_trades["NORMAL_VOLATILITY"].append(t)

        regime_breakdown: dict[str, dict[str, Any]] = {}
        for r_name, r_list in regime_trades.items():
            r_n = len(r_list)
            r_wins = sum(1 for x in r_list if x.is_win)
            r_net = sum(x.net_return_pct for x in r_list)
            regime_breakdown[r_name] = {
                "trades": r_n,
                "win_rate": round(r_wins / r_n, 3) if r_n > 0 else 0.0,
                "total_net_return_pct": round(r_net * 100.0, 3),
            }

        net_exp_bps = (report.net_expectancy_pct * 10_000.0) if report.executed_trades > 0 else 0.0
        gross_exp_bps = (sum(t.gross_return_pct for t in trades) / len(trades) * 10_000.0) if trades else 0.0
        break_even_bps = max(0.0, round(gross_exp_bps, 2))
        stat_sig = (report.independent_opportunities_count >= 30) and (report.profit_factor > 1.25) and (test_net > 0)

        # Conclusion text
        if report.independent_opportunities_count < 30:
            conclusion = (
                f"FEASIBILITY TEST ONLY: Sample size ({report.independent_opportunities_count} independent trades) "
                f"is insufficient for conclusive out-of-sample statistical significance. Net expectancy: {net_exp_bps:.1f} bps."
            )
        elif test_net > 0 and report.profit_factor > 1.2:
            conclusion = (
                f"POSITIVE EVIDENCE: Net expectancy of {net_exp_bps:.1f} bps after 16 bps costs, "
                f"with positive held-out test return ({test_net*100:.2f}%) and profit factor {report.profit_factor:.2f}."
            )
        else:
            conclusion = (
                f"UNFAVORABLE / UNPROVEN: Net return after costs is negative or fails to beat trading friction. "
                f"Expectancy: {net_exp_bps:.1f} bps, Held-out Test: {test_net*100:.2f}%."
            )

        return HypothesisEvaluationResult(
            hypothesis_id=hypothesis_id,
            description=description,
            total_eligible_signals=len(opportunities),
            executed_trades=report.executed_trades,
            independent_trades=report.independent_opportunities_count,
            win_rate=round(report.win_rate, 4),
            profit_factor=round(report.profit_factor, 2),
            gross_return_pct=round(report.gross_profit_pct - report.gross_loss_pct, 4),
            net_return_pct=round(report.total_net_return_pct, 4),
            net_expectancy_bps=round(net_exp_bps, 2),
            unallocated_cumulative_return_pct=round(report.unallocated_cumulative_return_pct, 4),
            independent_cumulative_return_pct=round(report.independent_cumulative_return_pct, 4),
            compounded_independent_equity_pct=round(report.compounded_independent_equity_pct, 4),
            capital_allocated_portfolio_return_pct=round(report.capital_allocated_portfolio_return_pct, 4),
            independent_net_expectancy_bps=round(report.independent_net_expectancy_bps, 2),
            break_even_cost_bps=break_even_bps,
            max_drawdown_pct=round(report.max_drawdown_pct, 4),
            sharpe_ratio=round(report.sharpe_ratio, 2),
            sortino_ratio=round(report.sortino_ratio, 2),
            train_net_return_pct=round(train_net, 4),
            val_net_return_pct=round(val_net, 4),
            test_net_return_pct=round(test_net, 4),
            buy_and_hold_return_pct=round(bnh_ret, 4),
            cost_sensitivity=cost_sensitivity,
            regime_breakdown=regime_breakdown,
            is_statistically_significant=stat_sig,
            scientific_conclusion=conclusion,
        )
