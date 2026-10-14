"""Historical price action feature extraction with strict zero-lookahead guarantee.

Identifies:
- Support and resistance levels (rolling swing extrema).
- Breakout and failed breakout (traps/fakeouts).
- Retest and pullback behaviors.
- Momentum continuation patterns.
- Reversal patterns (pin-bars, engulfing, rejection wicks).
- Volatility expansion and contraction (squeeze).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SwingLevel:
    """Confirmed support or resistance swing level."""

    level_type: str  # "support" or "resistance"
    price: float
    confirmed_bar_index: int
    pivot_bar_index: int
    timestamp_ms: int
    touch_count: int = 1


@dataclass(frozen=True)
class PriceActionSignals:
    """Price action signals and features computed for a specific bar."""

    bar_index: int
    timestamp_ms: int
    close: float
    open: float
    high: float
    low: float

    # S/R levels known at or before this bar
    nearest_support: float | None = None
    nearest_resistance: float | None = None
    dist_to_support_pct: float | None = None
    dist_to_resistance_pct: float | None = None

    # Breakout signals
    is_breakout_bullish: bool = False
    is_breakout_bearish: bool = False
    is_failed_breakout_bullish: bool = False  # Bear trap / fakeout to upside then close below
    is_failed_breakout_bearish: bool = False  # Bull trap / fakeout to downside then close above

    # Retest and pullback
    is_retest_support: bool = False
    is_retest_resistance: bool = False
    is_pullback_bullish: bool = False
    is_pullback_bearish: bool = False

    # Momentum continuation
    is_momentum_continuation_bullish: bool = False
    is_momentum_continuation_bearish: bool = False

    # Reversal patterns
    is_pinbar_bullish: bool = False  # Hammer / Long lower wick rejection
    is_pinbar_bearish: bool = False  # Shooting star / Long upper wick rejection
    is_engulfing_bullish: bool = False
    is_engulfing_bearish: bool = False

    # Volatility states
    atr_14: float = 0.0
    volatility_expansion: bool = False
    volatility_contraction: bool = False  # Squeeze

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PriceActionFeatureExtractor:
    """Extracts price action features and patterns chronologically.

    Strict zero-lookahead guarantee:
    A swing pivot at bar `j` requiring `k` right-confirmation bars is only
    considered active at bar `i` when `i >= j + k`.
    """

    def __init__(
        self,
        swing_left_bars: int = 5,
        swing_right_bars: int = 5,
        level_tolerance_pct: float = 0.003,  # 0.3% price tolerance for touches/retests
        atr_period: int = 14,
    ) -> None:
        self.swing_left_bars = swing_left_bars
        self.swing_right_bars = swing_right_bars
        self.level_tolerance_pct = level_tolerance_pct
        self.atr_period = atr_period

    def extract_features(
        self,
        candles: Sequence[Mapping[str, Any]],
    ) -> list[PriceActionSignals]:
        """Extract chronological price action signals for each candle in sequence."""
        n = len(candles)
        if n == 0:
            return []

        results: list[PriceActionSignals] = []
        confirmed_supports: list[SwingLevel] = []
        confirmed_resistances: list[SwingLevel] = []

        # Running true range for ATR
        tr_list: list[float] = []

        for i in range(n):
            c = candles[i]
            ts = int(c.get("open_time", c.get("timestamp_ms", c.get("timestamp", i))))
            op = float(c["open"])
            hi = float(c["high"])
            lo = float(c["low"])
            cl = float(c["close"])

            # Compute True Range
            if i == 0:
                tr = hi - lo
            else:
                prev_cl = float(candles[i - 1]["close"])
                tr = max(hi - lo, abs(hi - prev_cl), abs(lo - prev_cl))
            tr_list.append(tr)

            # Rolling ATR
            if len(tr_list) >= self.atr_period:
                atr = sum(tr_list[-self.atr_period:]) / self.atr_period
            else:
                atr = sum(tr_list) / len(tr_list) if tr_list else (hi - lo)

            # Check if a new swing level was confirmed at this bar i
            # The candidate pivot bar would be at pivot_idx = i - self.swing_right_bars
            pivot_idx = i - self.swing_right_bars
            if pivot_idx >= self.swing_left_bars:
                pivot_c = candles[pivot_idx]
                pivot_hi = float(pivot_c["high"])
                pivot_lo = float(pivot_c["low"])
                pivot_ts = int(pivot_c.get("open_time", pivot_c.get("timestamp_ms", pivot_c.get("timestamp", pivot_idx))))

                # Check if pivot_hi is higher than all left and right bars
                is_swing_high = True
                for left_i in range(pivot_idx - self.swing_left_bars, pivot_idx):
                    if float(candles[left_i]["high"]) >= pivot_hi:
                        is_swing_high = False
                        break
                if is_swing_high:
                    for right_i in range(pivot_idx + 1, pivot_idx + self.swing_right_bars + 1):
                        if float(candles[right_i]["high"]) > pivot_hi:
                            is_swing_high = False
                            break

                if is_swing_high:
                    confirmed_resistances.append(
                        SwingLevel(
                            level_type="resistance",
                            price=pivot_hi,
                            confirmed_bar_index=i,
                            pivot_bar_index=pivot_idx,
                            timestamp_ms=pivot_ts,
                        )
                    )

                # Check if pivot_lo is lower than all left and right bars
                is_swing_low = True
                for left_i in range(pivot_idx - self.swing_left_bars, pivot_idx):
                    if float(candles[left_i]["low"]) <= pivot_lo:
                        is_swing_low = False
                        break
                if is_swing_low:
                    for right_i in range(pivot_idx + 1, pivot_idx + self.swing_right_bars + 1):
                        if float(candles[right_i]["low"]) < pivot_lo:
                            is_swing_low = False
                            break

                if is_swing_low:
                    confirmed_supports.append(
                        SwingLevel(
                            level_type="support",
                            price=pivot_lo,
                            confirmed_bar_index=i,
                            pivot_bar_index=pivot_idx,
                            timestamp_ms=pivot_ts,
                        )
                    )

            # Find nearest known support & resistance (only using levels confirmed at or before i)
            known_supports = [s.price for s in confirmed_supports if s.price < cl]
            known_resistances = [r.price for r in confirmed_resistances if r.price > cl]

            nearest_sup = max(known_supports) if known_supports else None
            nearest_res = min(known_resistances) if known_resistances else None

            dist_sup_pct = ((cl - nearest_sup) / cl) if nearest_sup is not None else None
            dist_res_pct = ((nearest_res - cl) / cl) if nearest_res is not None else None

            # Breakout and Failed Breakout
            is_breakout_bull = False
            is_breakout_bear = False
            is_failed_breakout_bull = False
            is_failed_breakout_bear = False

            if i > 0:
                prev_c = candles[i - 1]
                prev_cl = float(prev_c["close"])

                # Look at recent resistances
                if nearest_res is not None:
                    # Bullish breakout: previous close below resistance, current close convincingly above
                    if prev_cl <= nearest_res and cl > nearest_res:
                        is_breakout_bull = True
                    # Bull trap (failed breakout): high penetrated above resistance, but close fell back below
                    elif hi > nearest_res and cl < nearest_res and (hi - nearest_res) > 0.3 * atr:
                        is_failed_breakout_bull = True

                if nearest_sup is not None:
                    # Bearish breakout: previous close above support, current close convincingly below
                    if prev_cl >= nearest_sup and cl < nearest_sup:
                        is_breakout_bear = True
                    # Bear trap (failed breakout): low penetrated below support, but close recovered above
                    elif lo < nearest_sup and cl > nearest_sup and (nearest_sup - lo) > 0.3 * atr:
                        is_failed_breakout_bear = True

            # Retest detection
            is_retest_sup = False
            is_retest_res = False
            if nearest_sup is not None and abs(lo - nearest_sup) / nearest_sup <= self.level_tolerance_pct and cl > nearest_sup:
                is_retest_sup = True
            if nearest_res is not None and abs(hi - nearest_res) / nearest_res <= self.level_tolerance_pct and cl < nearest_res:
                is_retest_res = True

            # Candlestick anatomy for Reversals
            candle_range = hi - lo if (hi - lo) > 0 else 1e-6
            body = abs(cl - op)
            upper_wick = hi - max(op, cl)
            lower_wick = min(op, cl) - lo

            # Pinbars
            # Bullish pinbar (Hammer): long lower wick (>= 50% of range), small body (<= 35%), small upper wick
            is_pinbar_bull = (lower_wick >= 0.5 * candle_range) and (body <= 0.35 * candle_range)
            # Bearish pinbar (Shooting star): long upper wick (>= 50% of range), small body (<= 35%), small lower wick
            is_pinbar_bear = (upper_wick >= 0.5 * candle_range) and (body <= 0.35 * candle_range)

            # Engulfing patterns
            is_engulfing_bull = False
            is_engulfing_bear = False
            if i > 0:
                p_op = float(candles[i - 1]["open"])
                p_cl = float(candles[i - 1]["close"])
                # Bullish engulfing: previous was red, current is green and engulfs body
                if p_cl < p_op and cl > op and op <= p_cl and cl >= p_op:
                    is_engulfing_bull = True
                # Bearish engulfing: previous was green, current is red and engulfs body
                if p_cl > p_op and cl < op and op >= p_cl and cl <= p_op:
                    is_engulfing_bear = True

            # Momentum continuation
            is_mom_bull = False
            is_mom_bear = False
            if i >= 2:
                c1 = candles[i - 1]
                c2 = candles[i - 2]
                if cl > op and float(c1["close"]) > float(c1["open"]) and float(c2["close"]) > float(c2["open"]):
                    if body > 0.8 * atr:
                        is_mom_bull = True
                elif cl < op and float(c1["close"]) < float(c1["open"]) and float(c2["close"]) < float(c2["open"]):
                    if body > 0.8 * atr:
                        is_mom_bear = True

            # Pullback in short term trend
            is_pullback_bull = False
            is_pullback_bear = False
            if i >= 5:
                # 5-bar trend check
                c5_cl = float(candles[i - 5]["close"])
                if cl > c5_cl and cl < op and lo <= min(float(candles[i-1]["low"]), float(candles[i-2]["low"])):
                    is_pullback_bull = True
                elif cl < c5_cl and cl > op and hi >= max(float(candles[i-1]["high"]), float(candles[i-2]["high"])):
                    is_pullback_bear = True

            # Volatility expansion vs contraction
            # Relative ATR to rolling 50-bar ATR
            if len(tr_list) >= 50:
                long_atr = sum(tr_list[-50:]) / 50.0
                vol_expansion = atr > 1.35 * long_atr
                vol_contraction = atr < 0.70 * long_atr
            else:
                vol_expansion = False
                vol_contraction = False

            results.append(
                PriceActionSignals(
                    bar_index=i,
                    timestamp_ms=ts,
                    close=cl,
                    open=op,
                    high=hi,
                    low=lo,
                    nearest_support=nearest_sup,
                    nearest_resistance=nearest_res,
                    dist_to_support_pct=dist_sup_pct,
                    dist_to_resistance_pct=dist_res_pct,
                    is_breakout_bullish=is_breakout_bull,
                    is_breakout_bearish=is_breakout_bear,
                    is_failed_breakout_bullish=is_failed_breakout_bull,
                    is_failed_breakout_bearish=is_failed_breakout_bear,
                    is_retest_support=is_retest_sup,
                    is_retest_resistance=is_retest_res,
                    is_pullback_bullish=is_pullback_bull,
                    is_pullback_bearish=is_pullback_bear,
                    is_momentum_continuation_bullish=is_mom_bull,
                    is_momentum_continuation_bearish=is_mom_bear,
                    is_pinbar_bullish=is_pinbar_bull,
                    is_pinbar_bearish=is_pinbar_bear,
                    is_engulfing_bullish=is_engulfing_bull,
                    is_engulfing_bearish=is_engulfing_bear,
                    atr_14=atr,
                    volatility_expansion=vol_expansion,
                    volatility_contraction=vol_contraction,
                )
            )

        return results
