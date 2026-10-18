"""Market regime detection and classification engine.

Sprint 11.03: Market Behavior Research Lab.
Classifies price action into explainable, behavioral market regimes without lookahead.
"""

from __future__ import annotations

import math
from typing import List, Optional

from coin_behavior_engine.research_lab.contracts import CandleData, MarketRegimeType


class MarketRegimeDetector:
    """Classifies market behavior states deterministically using past closed candles."""

    @classmethod
    def detect_regime(
        cls,
        candles: List[CandleData],
        current_idx: int,
        lookback_bars: int = 24,
    ) -> MarketRegimeType:
        """Classify market regime at current_idx using strictly candles[:current_idx + 1]."""
        if current_idx < lookback_bars:
            return MarketRegimeType.UNCERTAIN

        slice_bars = candles[current_idx - lookback_bars + 1 : current_idx + 1]
        closes = [c.close for c in slice_bars]
        volumes = [c.volume for c in slice_bars]

        curr_close = closes[-1]
        start_close = closes[0]
        ret_lookback = (curr_close - start_close) / start_close if start_close > 0 else 0.0

        # Compute ATR over lookback
        trs = []
        for i in range(1, len(slice_bars)):
            c_curr = slice_bars[i]
            c_prev = slice_bars[i - 1]
            tr = max(
                c_curr.high - c_curr.low,
                abs(c_curr.high - c_prev.close),
                abs(c_curr.low - c_prev.close),
            )
            trs.append(tr)
        
        atr = sum(trs) / len(trs) if trs else 0.0
        atr_pct = (atr / curr_close) if curr_close > 0 else 0.0

        # Compute recent 3-bar return & volume spike
        recent_3_ret = (curr_close - closes[-4]) / closes[-4] if len(closes) >= 4 and closes[-4] > 0 else 0.0
        avg_vol = sum(volumes[:-1]) / (len(volumes) - 1) if len(volumes) > 1 else 1.0
        curr_vol = volumes[-1]
        vol_ratio = (curr_vol / avg_vol) if avg_vol > 0 else 1.0

        # 1. Cascade liquidation regime: sharp drop + huge volume explosion
        if recent_3_ret < -0.025 and vol_ratio > 2.2:
            return MarketRegimeType.CASCADE_LIQUIDATION

        # 2. Trending Bull: Strong directional move up
        if ret_lookback > (1.8 * atr_pct) and curr_close > (sum(closes) / len(closes)):
            return MarketRegimeType.TRENDING_BULL

        # 3. Trending Bear: Strong directional move down
        if ret_lookback < -(1.8 * atr_pct) and curr_close < (sum(closes) / len(closes)):
            return MarketRegimeType.TRENDING_BEAR

        # 4. High volatility expansion: ATR exceptionally elevated
        if atr_pct > 0.015:  # > 1.5% per bar interval
            return MarketRegimeType.HIGH_VOLATILITY_EXPANSION

        # 5. Low volatility compression: ATR very narrow, price tightly bounded
        if atr_pct < 0.003:  # < 0.3% per bar interval
            return MarketRegimeType.LOW_VOLATILITY_COMPRESSION

        # 6. Default to mean reverting when oscillating
        return MarketRegimeType.MEAN_REVERTING

    @classmethod
    def classify_all(
        cls,
        candles: List[CandleData],
        lookback_bars: int = 24,
    ) -> List[MarketRegimeType]:
        """Classify regimes for all candles in sequence."""
        return [cls.detect_regime(candles, idx, lookback_bars) for idx in range(len(candles))]

