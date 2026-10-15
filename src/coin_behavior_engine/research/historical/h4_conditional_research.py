"""H4 Volatility Compression & Expansion Conditional Research.

Pre-registered conditional variants of H4:
- H4_BASE: Unconditioned squeeze breakout
- H4_TREND_ALIGNED: Squeeze breakout aligned with 50-EMA trend
- H4_EXTENDED_SQUEEZE: Squeeze breakout after >= 4 consecutive squeeze bars
- H4_HIGH_VOLUME: Squeeze breakout confirmed by relative volume >= 1.2x
- H4_SESSION_PEAK: Squeeze breakout during London or New York sessions

Evaluates across horizons (4, 8, 12 bars) and cost regimes (0 bps, 7 bps maker, 16 bps taker).
Strictly pre-registered; does NOT optimize parameters on held-out partitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentEvaluator,
    InvestmentOpportunity,
    PortfolioEvaluationReport,
    TradeCostModel,
    TradeDirection,
)
from coin_behavior_engine.research.historical.market_regime_intelligence import (
    MarketRegimeEngine,
    MarketRegimeState,
    TrendRegime,
)


@dataclass(frozen=True)
class H4ConditionalVariantResult:
    """Performance evaluation of a specific H4 conditional variant."""

    variant_name: str
    partition: str
    horizon_bars: int
    cost_model_bps: float
    total_candidates: int
    executed_trades: int
    independent_trades: int
    win_rate: float
    gross_profit_factor: float
    gross_expectancy_bps: float
    net_expectancy_bps: float
    net_profit_factor: float
    total_net_return_pct: float
    max_drawdown_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class H4ConditionalExperimentRunner:
    """Executes pre-registered H4 conditional experiments."""

    def __init__(self, candles: Sequence[Mapping[str, Any]], symbol: str = "BTCUSDT") -> None:
        self.candles = candles
        self.symbol = symbol
        self.n_bars = len(candles)
        self.regime_engine = MarketRegimeEngine(candles)
        self.evaluator = InvestmentEvaluator()

    def generate_conditioned_opportunities(
        self,
        variant: str = "H4_BASE",
        horizon_bars: int = 8,
    ) -> list[InvestmentOpportunity]:
        """Generate pre-registered H4 opportunities matching conditional rules."""
        if self.n_bars < 50:
            return []

        closes = np.array([float(c["close"]) for c in self.candles])
        highs = np.array([float(c["high"]) for c in self.candles])
        lows = np.array([float(c["low"]) for c in self.candles])

        opportunities: list[InvestmentOpportunity] = []

        for i in range(30, self.n_bars - horizon_bars):
            # Prior bar was in squeeze
            regime_prev = self.regime_engine.classify_bar(i - 1)
            was_squeeze = (regime_prev.squeeze_consecutive_bars > 0)
            if not was_squeeze:
                continue

            regime_curr = self.regime_engine.classify_bar(i)
            atr = regime_curr.atr_14
            curr_cl = closes[i]

            # Rolling 20-bar BB
            window_cl = closes[i - 19 : i + 1]
            mean_cl = float(np.mean(window_cl))
            std_cl = float(np.std(window_cl, ddof=1)) if len(window_cl) > 1 else 1e-9
            bb_upper = mean_cl + 2.0 * std_cl
            bb_lower = mean_cl - 2.0 * std_cl

            is_bull_breakout = curr_cl > bb_upper
            is_bear_breakout = curr_cl < bb_lower

            if not (is_bull_breakout or is_bear_breakout):
                continue

            direction = TradeDirection.LONG if is_bull_breakout else TradeDirection.SHORT

            # Apply Pre-Registered Variant Conditions
            if variant == "H4_TREND_ALIGNED":
                if direction == TradeDirection.LONG and regime_curr.trend != TrendRegime.BULLISH_TREND:
                    continue
                if direction == TradeDirection.SHORT and regime_curr.trend != TrendRegime.BEARISH_TREND:
                    continue

            elif variant == "H4_EXTENDED_SQUEEZE":
                # Prior squeeze persisted for at least 4 bars
                if regime_prev.squeeze_consecutive_bars < 4:
                    continue

            elif variant == "H4_HIGH_VOLUME":
                # Current breakout bar volume >= 1.2x 24h rolling average
                if regime_curr.relative_volume_24h < 1.20:
                    continue

            elif variant == "H4_SESSION_PEAK":
                # Session is London or New York
                if regime_curr.primary_session not in ("LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"):
                    continue

            # Build opportunity
            entry_px = curr_cl
            tp = entry_px + (2.5 * atr if direction == TradeDirection.LONG else -2.5 * atr)
            sl = entry_px - (1.5 * atr if direction == TradeDirection.LONG else -1.5 * atr)
            bar_ts = int(self.candles[i].get("open_time", self.candles[i].get("timestamp_ms", 0)))

            opportunities.append(
                InvestmentOpportunity(
                    opportunity_id=f"{variant}_{direction.value}_{i}_{bar_ts}",
                    symbol=self.symbol,
                    entry_bar_index=i,
                    entry_timestamp_ms=bar_ts,
                    direction=direction,
                    entry_price=entry_px,
                    take_profit_price=tp,
                    stop_loss_price=sl,
                    max_holding_bars=horizon_bars,
                    metadata={"hypothesis": "H4", "variant": variant, "atr": atr},
                )
            )

        return opportunities

    def evaluate_variant(
        self,
        variant: str,
        partition_name: str,
        horizon_bars: int = 8,
        cost_bps: float = 7.0,
    ) -> H4ConditionalVariantResult:
        """Evaluate a variant under specified cost and horizon parameters."""
        opps = self.generate_conditioned_opportunities(variant=variant, horizon_bars=horizon_bars)
        cost_model = TradeCostModel.from_roundtrip_bps(cost_bps)
        gross_cost = TradeCostModel(0.0, 0.0, 0.0, 0.0)

        if not opps:
            return H4ConditionalVariantResult(
                variant_name=variant, partition=partition_name, horizon_bars=horizon_bars,
                cost_model_bps=cost_bps, total_candidates=0, executed_trades=0,
                independent_trades=0, win_rate=0.0, gross_profit_factor=0.0,
                gross_expectancy_bps=0.0, net_expectancy_bps=0.0, net_profit_factor=0.0,
                total_net_return_pct=0.0, max_drawdown_pct=0.0,
            )

        _, rep_net = self.evaluator.evaluate_opportunities(opps, self.candles, cost_model)
        _, rep_gross = self.evaluator.evaluate_opportunities(opps, self.candles, gross_cost)

        return H4ConditionalVariantResult(
            variant_name=variant,
            partition=partition_name,
            horizon_bars=horizon_bars,
            cost_model_bps=cost_bps,
            total_candidates=len(opps),
            executed_trades=rep_net.executed_trades,
            independent_trades=rep_net.independent_opportunities_count,
            win_rate=round(rep_net.win_rate, 4),
            gross_profit_factor=round(rep_gross.profit_factor, 2),
            gross_expectancy_bps=round(rep_gross.net_expectancy_pct * 10000.0, 2),
            net_expectancy_bps=round(rep_net.net_expectancy_pct * 10000.0, 2),
            net_profit_factor=round(rep_net.profit_factor, 2),
            total_net_return_pct=round(rep_net.total_net_return_pct * 100.0, 2),
            max_drawdown_pct=round(rep_net.max_drawdown_pct * 100.0, 2),
        )
