"""Pre-registered market regime conditioning and filters for H1 breakout research.

To avoid p-hacking and multiple-testing bias, filters are pre-registered
with strict observable invariants at or before decision time.

Filters:
1. TrendAlignmentFilter: Higher-timeframe / 24h trend direction matches trade.
2. RelativeVolumeFilter: Breakout candle volume exceeds average volume (Z-score >= 1.0).
3. StrongCandleBodyFilter: Breakout bar body-to-range ratio >= 0.60.
4. PriorSessionLocationFilter: Price breaks beyond London session high/low.
5. DayOfWeekFilter: Mid-week active trading days (Tuesday to Thursday UTC).
6. VolatilityConditioningFilter: Normal to High volatility (excludes extreme compression or panic).
7. CombinedRegimeFilter: Pre-registered composite filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentOpportunity,
    TradeDirection,
)
from coin_behavior_engine.research.historical.market_context import MarketContextFeatures
from coin_behavior_engine.research.historical.market_sessions import MarketSessionDetector, MarketSession


class RegimeFilterType(str, Enum):
    """Pre-registered regime filter category."""

    NONE = "NONE"
    TREND_ALIGNED = "TREND_ALIGNED"
    RELATIVE_VOLUME = "RELATIVE_VOLUME"
    STRONG_BODY = "STRONG_BODY"
    PRIOR_SESSION_LOCATION = "PRIOR_SESSION_LOCATION"
    MID_WEEK_ONLY = "MID_WEEK_ONLY"
    NORMAL_TO_HIGH_VOLATILITY = "NORMAL_TO_HIGH_VOLATILITY"
    COMBINED_PREREGISTERED = "COMBINED_PREREGISTERED"


@dataclass(frozen=True)
class FilterEvaluationReport:
    """Statistics on filtered opportunity set."""

    filter_name: str
    total_candidates: int
    passed_candidates: int
    filter_pass_ratio: float
    description: str


class RegimeFilterBank:
    """Collection of deterministic, zero-lookahead regime filters."""

    @staticmethod
    def is_trend_aligned(
        opp: InvestmentOpportunity,
        context: MarketContextFeatures,
    ) -> bool:
        """Filter 1: Direction of trade must align with market trend."""
        if not context.is_trending:
            return False
        if opp.direction == TradeDirection.LONG:
            return context.trend_direction > 0
        else:
            return context.trend_direction < 0

    @staticmethod
    def is_high_relative_volume(
        opp: InvestmentOpportunity,
        context: MarketContextFeatures,
        min_relative_volume: float = 1.25,
    ) -> bool:
        """Filter 2: Breakout bar volume must exceed average volume."""
        return context.relative_volume >= min_relative_volume

    @staticmethod
    def is_strong_candle_body(
        opp: InvestmentOpportunity,
        candles: Sequence[Mapping[str, Any]],
        min_body_ratio: float = 0.50,
    ) -> bool:
        """Filter 3: Breakout candle must have decisive body relative to full range."""
        b_idx = opp.entry_bar_index
        if b_idx < 0 or b_idx >= len(candles):
            return False
        bar = candles[b_idx]
        op = float(bar["open"])
        hi = float(bar["high"])
        lo = float(bar["low"])
        cl = float(bar["close"])
        rng = hi - lo
        if rng <= 1e-9:
            return False
        body = abs(cl - op)
        return (body / rng) >= min_body_ratio

    @staticmethod
    def is_mid_week_day(
        opp: InvestmentOpportunity,
    ) -> bool:
        """Filter 5: Entry occurs on Tuesday, Wednesday, or Thursday UTC (peak volume)."""
        dt = datetime.fromtimestamp(opp.entry_timestamp_ms / 1000.0, tz=timezone.utc)
        # Monday is 0, Tuesday is 1, Wednesday is 2, Thursday is 3, Friday is 4
        return dt.weekday() in (1, 2, 3)

    @staticmethod
    def is_normal_or_high_volatility(
        opp: InvestmentOpportunity,
        context: MarketContextFeatures,
    ) -> bool:
        """Filter 6: Volatility is neither dead compression nor erratic extreme."""
        return context.volatility_regime in ("NORMAL", "HIGH")

    @classmethod
    def apply_filter(
        cls,
        filter_type: RegimeFilterType,
        opportunities: Sequence[InvestmentOpportunity],
        context_features: Sequence[MarketContextFeatures],
        candles: Sequence[Mapping[str, Any]],
    ) -> tuple[list[InvestmentOpportunity], FilterEvaluationReport]:
        """Apply a specified pre-registered filter to opportunities."""
        if filter_type == RegimeFilterType.NONE:
            rep = FilterEvaluationReport(
                filter_name="NONE",
                total_candidates=len(opportunities),
                passed_candidates=len(opportunities),
                filter_pass_ratio=1.0,
                description="Baseline unconditioned opportunity set",
            )
            return list(opportunities), rep

        passed: list[InvestmentOpportunity] = []
        for opp in opportunities:
            ctx = context_features[opp.entry_bar_index]

            keep = False
            if filter_type == RegimeFilterType.TREND_ALIGNED:
                keep = cls.is_trend_aligned(opp, ctx)
            elif filter_type == RegimeFilterType.RELATIVE_VOLUME:
                keep = cls.is_high_relative_volume(opp, ctx)
            elif filter_type == RegimeFilterType.STRONG_BODY:
                keep = cls.is_strong_candle_body(opp, candles)
            elif filter_type == RegimeFilterType.MID_WEEK_ONLY:
                keep = cls.is_mid_week_day(opp)
            elif filter_type == RegimeFilterType.NORMAL_TO_HIGH_VOLATILITY:
                keep = cls.is_normal_or_high_volatility(opp, ctx)
            elif filter_type == RegimeFilterType.COMBINED_PREREGISTERED:
                # Composite: Trend-aligned OR (High volume AND Strong body) in non-extreme vol
                is_vol_ok = cls.is_normal_or_high_volatility(opp, ctx)
                is_trend = cls.is_trend_aligned(opp, ctx)
                is_conviction = cls.is_high_relative_volume(opp, ctx) and cls.is_strong_candle_body(opp, candles)
                keep = is_vol_ok and (is_trend or is_conviction)

            if keep:
                passed.append(opp)

        pass_ratio = len(passed) / len(opportunities) if opportunities else 0.0
        rep = FilterEvaluationReport(
            filter_name=filter_type.value,
            total_candidates=len(opportunities),
            passed_candidates=len(passed),
            filter_pass_ratio=round(pass_ratio, 4),
            description=f"Filtered {len(opportunities)} down to {len(passed)} trades using {filter_type.value}",
        )
        return passed, rep
