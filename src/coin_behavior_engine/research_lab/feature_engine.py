"""Timestamp-safe market behavior and microstructure feature engine.

Sprint 11.03: Market Behavior Research Lab.
Extracts momentum, volatility, volume divergence, and dynamic support/resistance
with strict anti-leakage guarantees.
"""

from __future__ import annotations

import math
from typing import List, Optional

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    MarketBehaviorFeatures,
    MarketRegimeType,
)
from coin_behavior_engine.research_lab.market_regime import MarketRegimeDetector


class MarketBehaviorFeatureEngine:
    """Computes explainable, causal market features without future leakage."""

    @classmethod
    def compute_features_at_index(
        cls,
        candles: List[CandleData],
        idx: int,
        lookback_bars: int = 24,
    ) -> MarketBehaviorFeatures:
        """Compute complete feature vector for candle at idx using ONLY candles[:idx + 1]."""
        c_curr = candles[idx]
        curr_close = c_curr.close
        
        # Default empty features if warmup is insufficient
        features = MarketBehaviorFeatures(
            timestamp_open=c_curr.timestamp_open,
            datetime_utc=c_curr.datetime_open_utc,
            close_price=curr_close,
        )

        if idx < 1:
            return features

        # 1. Multi-horizon returns
        features.return_1 = (curr_close - candles[idx - 1].close) / candles[idx - 1].close
        if idx >= 3:
            features.return_3 = (curr_close - candles[idx - 3].close) / candles[idx - 3].close
        if idx >= 5:
            features.return_5 = (curr_close - candles[idx - 5].close) / candles[idx - 5].close
        if idx >= 12:
            features.return_12 = (curr_close - candles[idx - 12].close) / candles[idx - 12].close
            features.momentum_12 = features.return_12
        if idx >= 24:
            features.return_24 = (curr_close - candles[idx - 24].close) / candles[idx - 24].close
            features.momentum_24 = features.return_24

        # 2. Volatility (ATR-14 and Realized Volatility over 24 bars)
        atr_window = min(idx, 14)
        if atr_window >= 1:
            trs = []
            for k in range(idx - atr_window + 1, idx + 1):
                tr = max(
                    candles[k].high - candles[k].low,
                    abs(candles[k].high - candles[k - 1].close),
                    abs(candles[k].low - candles[k - 1].close),
                )
                trs.append(tr)
            features.atr_14 = sum(trs) / len(trs) if trs else 0.0

        vol_window = min(idx, 24)
        if vol_window >= 2:
            rets = []
            for k in range(idx - vol_window + 1, idx + 1):
                rets.append((candles[k].close - candles[k - 1].close) / candles[k - 1].close)
            mean_ret = sum(rets) / len(rets)
            var = sum((r - mean_ret) ** 2 for r in rets) / (len(rets) - 1)
            features.volatility_realized_24 = math.sqrt(max(0.0, var))

        # 3. Volume analysis & relative volume
        vol_lookback = min(idx, 20)
        if vol_lookback >= 2:
            past_vols = [candles[k].volume for k in range(idx - vol_lookback, idx)]
            avg_vol = sum(past_vols) / len(past_vols) if past_vols else 1.0
            features.relative_volume_20 = (c_curr.volume / avg_vol) if avg_vol > 0 else 1.0

            # Correlation between price return and volume
            vol_rets = [
                (candles[k].close - candles[k - 1].close) / candles[k - 1].close
                for k in range(idx - vol_lookback + 1, idx + 1)
            ]
            slice_vols = [candles[k].volume for k in range(idx - vol_lookback + 1, idx + 1)]
            if len(vol_rets) == len(slice_vols) and len(vol_rets) > 2:
                m_r = sum(vol_rets) / len(vol_rets)
                m_v = sum(slice_vols) / len(slice_vols)
                cov = sum((r - m_r) * (v - m_v) for r, v in zip(vol_rets, slice_vols))
                var_r = sum((r - m_r) ** 2 for r in vol_rets)
                var_v = sum((v - m_v) ** 2 for v in slice_vols)
                denom = math.sqrt(max(1e-12, var_r * var_v))
                features.price_volume_corr_20 = cov / denom

        # 4. Rolling extremes & support/resistance
        history_window = min(idx + 1, 48)
        window_highs = [candles[k].high for k in range(idx - history_window + 1, idx + 1)]
        window_lows = [candles[k].low for k in range(idx - history_window + 1, idx + 1)]
        features.rolling_high_24 = max(window_highs)
        features.rolling_low_24 = min(window_lows)

        if features.rolling_high_24 > 0:
            features.drawdown_from_peak_pct = (curr_close - features.rolling_high_24) / features.rolling_high_24
        if features.rolling_low_24 > 0:
            features.runup_from_trough_pct = (curr_close - features.rolling_low_24) / features.rolling_low_24

        # Swing highs and lows (using only confirmed past bars: peak must be at least 2 bars in the past)
        swing_highs = []
        swing_lows = []
        for j in range(max(2, idx - 40), idx - 1):
            # Peak condition
            if (
                candles[j].high > candles[j - 1].high
                and candles[j].high > candles[j - 2].high
                and candles[j].high > candles[j + 1].high
            ):
                swing_highs.append(candles[j].high)
            # Trough condition
            if (
                candles[j].low < candles[j - 1].low
                and candles[j].low < candles[j - 2].low
                and candles[j].low < candles[j + 1].low
            ):
                swing_lows.append(candles[j].low)

        # Dynamic Support: highest swing low or rolling low strictly below current price
        supp_candidates = [s for s in swing_lows if s < curr_close]
        if supp_candidates:
            features.support_zone = max(supp_candidates)
            features.swing_low = features.support_zone
        else:
            features.support_zone = features.rolling_low_24

        # Dynamic Resistance: lowest swing high or rolling high strictly above current price
        res_candidates = [s for s in swing_highs if s > curr_close]
        if res_candidates:
            features.resistance_zone = min(res_candidates)
            features.swing_high = features.resistance_zone
        else:
            features.resistance_zone = features.rolling_high_24

        if curr_close > 0:
            features.distance_to_support_pct = (curr_close - features.support_zone) / curr_close
            features.distance_to_resistance_pct = (features.resistance_zone - curr_close) / curr_close

        # 5. Market regime classification
        features.regime = MarketRegimeDetector.detect_regime(candles, idx, lookback_bars=lookback_bars)

        # 6. Volatility compression / expansion ratio (ATR14 vs ATR100)
        long_window = min(idx, 100)
        if long_window >= 14:
            long_trs = []
            for k in range(idx - long_window + 1, idx + 1):
                tr = max(
                    candles[k].high - candles[k].low,
                    abs(candles[k].high - candles[k - 1].close),
                    abs(candles[k].low - candles[k - 1].close),
                )
                long_trs.append(tr)
            long_atr = sum(long_trs) / len(long_trs) if long_trs else 1.0
            features.volatility_compression_ratio = round(features.atr_14 / long_atr, 3) if long_atr > 0 else 1.0

        # 7. Price-Volume Divergence detection (12-bar window)
        if idx >= 12:
            recent_low = min(c.low for c in candles[idx - 6 : idx + 1])
            prior_low = min(c.low for c in candles[idx - 12 : idx - 6])
            recent_high = max(c.high for c in candles[idx - 6 : idx + 1])
            prior_high = max(c.high for c in candles[idx - 12 : idx - 6])

            recent_vol = sum(c.volume for c in candles[idx - 6 : idx + 1]) / 6.0
            prior_vol = sum(c.volume for c in candles[idx - 12 : idx - 6]) / 6.0

            if recent_low < prior_low and recent_vol < prior_vol * 0.8:
                features.price_volume_divergence = "BULLISH_DIV"  # Price lower low with fading selling volume
            elif recent_high > prior_high and recent_vol < prior_vol * 0.8:
                features.price_volume_divergence = "BEARISH_DIV"  # Price higher high with fading buying volume
            else:
                features.price_volume_divergence = "NONE"

        return features

    @classmethod
    def compute_all(
        cls,
        candles: List[CandleData],
        lookback_bars: int = 24,
        candles_1h: Optional[List[CandleData]] = None,
        candles_4h: Optional[List[CandleData]] = None,
    ) -> List[MarketBehaviorFeatures]:
        """Compute features for all candles chronologically with optional HTF alignment."""
        features_list = [
            cls.compute_features_at_index(candles, i, lookback_bars=lookback_bars)
            for i in range(len(candles))
        ]

        # Multi-timeframe mapping with strict anti-leakage
        # For each 5m candle, map only the latest 1h and 4h candles that CLOSED BEFORE the 5m candle opened
        if candles_1h:
            h1_ts = [c.timestamp_close for c in candles_1h]
            h1_regimes = [MarketRegimeDetector.detect_regime(candles_1h, k, lookback_bars=12) for k in range(len(candles_1h))]
            h1_trends = []
            for k in range(len(candles_1h)):
                look = min(k, 12)
                t_ret = (candles_1h[k].close - candles_1h[k - look].close) / candles_1h[k - look].close if look > 0 and candles_1h[k - look].close > 0 else 0.0
                h1_trends.append(t_ret)

            for i, c in enumerate(candles):
                # Search for latest 1h candle with timestamp_close <= c.timestamp_open
                eligible_idx = [k for k, close_ts in enumerate(h1_ts) if close_ts <= c.timestamp_open]
                if eligible_idx:
                    latest_k = eligible_idx[-1]
                    features_list[i].htf_1h_regime = h1_regimes[latest_k]
                    features_list[i].htf_1h_trend_pct = round(h1_trends[latest_k] * 100.0, 3)

        if candles_4h:
            h4_ts = [c.timestamp_close for c in candles_4h]
            h4_regimes = [MarketRegimeDetector.detect_regime(candles_4h, k, lookback_bars=6) for k in range(len(candles_4h))]
            h4_trends = []
            for k in range(len(candles_4h)):
                look = min(k, 6)
                t_ret = (candles_4h[k].close - candles_4h[k - look].close) / candles_4h[k - look].close if look > 0 and candles_4h[k - look].close > 0 else 0.0
                h4_trends.append(t_ret)

            for i, c in enumerate(candles):
                eligible_idx = [k for k, close_ts in enumerate(h4_ts) if close_ts <= c.timestamp_open]
                if eligible_idx:
                    latest_k = eligible_idx[-1]
                    features_list[i].htf_4h_regime = h4_regimes[latest_k]
                    features_list[i].htf_4h_trend_pct = round(h4_trends[latest_k] * 100.0, 3)

        # Compute HTF alignment
        for feat in features_list:
            feat.is_htf_trend_aligned = bool(
                feat.htf_1h_trend_pct > 0.1
                and feat.htf_4h_trend_pct > -0.2
                and feat.htf_1h_regime != MarketRegimeType.TRENDING_BEAR
                and feat.htf_4h_regime != MarketRegimeType.CASCADE_LIQUIDATION
            )

        return features_list
