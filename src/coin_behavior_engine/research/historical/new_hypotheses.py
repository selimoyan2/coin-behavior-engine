"""New market behavior hypotheses framework for historical research.

Pre-registered behavioral candidates:
1. H4 — Volatility Compression & Expansion (Bollinger/Keltner Squeeze).
2. H5 — Trend Continuation After Consolidation (Trend Pause Flag).
3. H6 — Failed Breakout With Strong Rejection Confirmation (Enhanced H2 Liquidity Sweep).
4. H7 — Session Transition & Liquidity Regime Changes (London-NY Overlap Expansion).

All hypotheses enforce:
- Zero lookahead (features computed strictly at or before decision bar).
- Pre-registered entry and exit logic.
- Bounded risk (explicit SL and TP).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentOpportunity,
    TradeDirection,
)


class NewHypothesesGenerator:
    """Generates pre-registered opportunities for hypotheses H4 to H7."""

    def __init__(self, candles: Sequence[Mapping[str, Any]], symbol: str = "BTCUSDT") -> None:
        self.candles = candles
        self.n_bars = len(candles)
        self.symbol = symbol

    # -------------------------------------------------------------------------
    # H4: Volatility Compression & Expansion (Squeeze Breakout)
    # -------------------------------------------------------------------------
    def generate_h4_opportunities(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        kc_mult: float = 1.5,
        horizon_bars: int = 8,
    ) -> list[InvestmentOpportunity]:
        """Generate H4 Squeeze Breakout opportunities."""
        if self.n_bars < bb_period + 5:
            return []

        closes = np.array([float(c["close"]) for c in self.candles])
        highs = np.array([float(c["high"]) for c in self.candles])
        lows = np.array([float(c["low"]) for c in self.candles])

        opportunities: list[InvestmentOpportunity] = []

        # Compute rolling ATR, BB, KC
        for i in range(bb_period, self.n_bars - horizon_bars):
            window_cl = closes[i - bb_period + 1 : i + 1]
            window_hi = highs[i - bb_period + 1 : i + 1]
            window_lo = lows[i - bb_period + 1 : i + 1]

            mean_cl = float(np.mean(window_cl))
            std_cl = float(np.std(window_cl, ddof=1)) if len(window_cl) > 1 else 1e-9

            # True ranges
            tr = np.maximum(
                window_hi[1:] - window_lo[1:],
                np.maximum(
                    np.abs(window_hi[1:] - window_cl[:-1]),
                    np.abs(window_lo[1:] - window_cl[:-1]),
                ),
            )
            atr = float(np.mean(tr)) if len(tr) > 0 else (highs[i] - lows[i])

            # BB bounds
            bb_upper = mean_cl + bb_std * std_cl
            bb_lower = mean_cl - bb_std * std_cl

            # KC bounds
            kc_upper = mean_cl + kc_mult * atr
            kc_lower = mean_cl - kc_mult * atr

            # Prior bar was in squeeze (BB inside KC)
            prev_window_cl = closes[i - bb_period : i]
            prev_std = float(np.std(prev_window_cl, ddof=1)) if len(prev_window_cl) > 1 else 1e-9
            was_in_squeeze = (bb_std * prev_std) <= (kc_mult * atr)

            curr_cl = closes[i]
            # Breakout expansion
            if was_in_squeeze:
                if curr_cl > bb_upper:  # Bullish expansion
                    entry_px = curr_cl
                    tp = entry_px + 2.5 * atr
                    sl = entry_px - 1.5 * atr
                    bar_ts = int(self.candles[i].get("open_time", self.candles[i].get("timestamp_ms", 0)))
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H4_BULL_{i}_{bar_ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=bar_ts,
                            direction=TradeDirection.LONG,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H4_VOLATILITY_EXPANSION", "atr": atr},
                        )
                    )
                elif curr_cl < bb_lower:  # Bearish expansion
                    entry_px = curr_cl
                    tp = entry_px - 2.5 * atr
                    sl = entry_px + 1.5 * atr
                    bar_ts = int(self.candles[i].get("open_time", self.candles[i].get("timestamp_ms", 0)))
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H4_BEAR_{i}_{bar_ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=bar_ts,
                            direction=TradeDirection.SHORT,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H4_VOLATILITY_EXPANSION", "atr": atr},
                        )
                    )

        return opportunities

    # -------------------------------------------------------------------------
    # H5: Trend Continuation After Consolidation (Trend Flag)
    # -------------------------------------------------------------------------
    def generate_h5_opportunities(
        self,
        trend_ema_period: int = 50,
        consolidation_bars: int = 4,
        horizon_bars: int = 6,
    ) -> list[InvestmentOpportunity]:
        """Generate H5 Trend Continuation opportunities."""
        if self.n_bars < trend_ema_period + consolidation_bars + 5:
            return []

        closes = np.array([float(c["close"]) for c in self.candles])
        highs = np.array([float(c["high"]) for c in self.candles])
        lows = np.array([float(c["low"]) for c in self.candles])

        opportunities: list[InvestmentOpportunity] = []

        for i in range(trend_ema_period + consolidation_bars, self.n_bars - horizon_bars):
            # Compute EMA50
            ema_window = closes[i - trend_ema_period + 1 : i + 1]
            ema_val = float(np.mean(ema_window))  # simple baseline approximation

            # Consolidation range over prior N bars
            c_highs = highs[i - consolidation_bars : i]
            c_lows = lows[i - consolidation_bars : i]
            c_max = float(np.max(c_highs))
            c_min = float(np.min(c_lows))
            c_range = c_max - c_min
            curr_cl = closes[i]

            atr_approx = float(np.mean(highs[i - 10 : i] - lows[i - 10 : i]))

            # Tight consolidation condition: consolidation range < 1.2x ATR
            is_tight = c_range <= 1.2 * atr_approx

            if is_tight:
                if curr_cl > ema_val and curr_cl > c_max:  # Bullish breakout of consolidation in uptrend
                    entry_px = curr_cl
                    tp = entry_px + 2.0 * atr_approx
                    sl = c_min
                    bar_ts = int(self.candles[i].get("open_time", 0))
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H5_BULL_{i}_{bar_ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=bar_ts,
                            direction=TradeDirection.LONG,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H5_TREND_FLAG", "ema": ema_val},
                        )
                    )
                elif curr_cl < ema_val and curr_cl < c_min:  # Bearish breakout of consolidation in downtrend
                    entry_px = curr_cl
                    tp = entry_px - 2.0 * atr_approx
                    sl = c_max
                    bar_ts = int(self.candles[i].get("open_time", 0))
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H5_BEAR_{i}_{bar_ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=bar_ts,
                            direction=TradeDirection.SHORT,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H5_TREND_FLAG", "ema": ema_val},
                        )
                    )

        return opportunities

    # -------------------------------------------------------------------------
    # H6: Failed Breakout With Strong Rejection (Enhanced H2)
    # -------------------------------------------------------------------------
    def generate_h6_opportunities(
        self,
        lookback_bars: int = 20,
        min_rejection_wick_ratio: float = 0.50,
        horizon_bars: int = 6,
    ) -> list[InvestmentOpportunity]:
        """Generate H6 Failed Breakout Rejection opportunities."""
        if self.n_bars < lookback_bars + 5:
            return []

        opportunities: list[InvestmentOpportunity] = []
        for i in range(lookback_bars, self.n_bars - horizon_bars):
            bar = self.candles[i]
            op = float(bar["open"])
            hi = float(bar["high"])
            lo = float(bar["low"])
            cl = float(bar["close"])
            rng = hi - lo
            if rng <= 1e-9:
                continue

            prev_highs = [float(self.candles[j]["high"]) for j in range(i - lookback_bars, i)]
            prev_lows = [float(self.candles[j]["low"]) for j in range(i - lookback_bars, i)]
            level_high = max(prev_highs)
            level_low = min(prev_lows)

            upper_wick = hi - max(op, cl)
            lower_wick = min(op, cl) - lo

            # Bearish rejection of high: pierced level_high, but closed below it with upper wick >= 50%
            if hi > level_high and cl < level_high and (upper_wick / rng) >= min_rejection_wick_ratio:
                entry_px = cl
                sl = hi * 1.001  # just above rejection wick
                tp = entry_px - 2.0 * (sl - entry_px)
                bar_ts = int(bar.get("open_time", 0))
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H6_REJECT_HIGH_{i}_{bar_ts}",
                        symbol=self.symbol,
                        entry_bar_index=i,
                        entry_timestamp_ms=bar_ts,
                        direction=TradeDirection.SHORT,
                        entry_price=entry_px,
                        take_profit_price=tp,
                        stop_loss_price=sl,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H6_FAILED_BREAKOUT_REJECTION"},
                    )
                )

            # Bullish rejection of low: pierced level_low, but closed above it with lower wick >= 50%
            elif lo < level_low and cl > level_low and (lower_wick / rng) >= min_rejection_wick_ratio:
                entry_px = cl
                sl = lo * 0.999
                tp = entry_px + 2.0 * (entry_px - sl)
                bar_ts = int(bar.get("open_time", 0))
                opportunities.append(
                    InvestmentOpportunity(
                        opportunity_id=f"H6_REJECT_LOW_{i}_{bar_ts}",
                        symbol=self.symbol,
                        entry_bar_index=i,
                        entry_timestamp_ms=bar_ts,
                        direction=TradeDirection.LONG,
                        entry_price=entry_px,
                        take_profit_price=tp,
                        stop_loss_price=sl,
                        max_holding_bars=horizon_bars,
                        metadata={"hypothesis": "H6_FAILED_BREAKOUT_REJECTION"},
                    )
                )

        return opportunities

    # -------------------------------------------------------------------------
    # H7: Session Transition and Liquidity Regime Changes
    # -------------------------------------------------------------------------
    def generate_h7_opportunities(
        self,
        horizon_bars: int = 8,
    ) -> list[InvestmentOpportunity]:
        """Generate H7 London-NY transition expansion opportunities."""
        opportunities: list[InvestmentOpportunity] = []
        for i in range(20, self.n_bars - horizon_bars):
            bar = self.candles[i]
            ts = int(bar.get("open_time", 0))
            hour_utc = (ts // 3_600_000) % 24
            min_utc = (ts // 60_000) % 60

            # Transition window: 12:00 to 13:30 UTC
            if hour_utc == 12 and min_utc == 0:
                # Morning range from 07:00 to 12:00 (London morning)
                morning_bars = [self.candles[j] for j in range(max(0, i - 20), i)]
                m_hi = max(float(b["high"]) for b in morning_bars)
                m_lo = min(float(b["low"]) for b in morning_bars)
                cl = float(bar["close"])

                if cl > m_hi:
                    entry_px = cl
                    tp = entry_px + (m_hi - m_lo) * 1.5
                    sl = m_lo
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H7_TRANS_BULL_{i}_{ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=ts,
                            direction=TradeDirection.LONG,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H7_SESSION_TRANSITION"},
                        )
                    )
                elif cl < m_lo:
                    entry_px = cl
                    tp = entry_px - (m_hi - m_lo) * 1.5
                    sl = m_hi
                    opportunities.append(
                        InvestmentOpportunity(
                            opportunity_id=f"H7_TRANS_BEAR_{i}_{ts}",
                            symbol=self.symbol,
                            entry_bar_index=i,
                            entry_timestamp_ms=ts,
                            direction=TradeDirection.SHORT,
                            entry_price=entry_px,
                            take_profit_price=tp,
                            stop_loss_price=sl,
                            max_holding_bars=horizon_bars,
                            metadata={"hypothesis": "H7_SESSION_TRANSITION"},
                        )
                    )

        return opportunities
