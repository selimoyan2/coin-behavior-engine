"""Historical Feature Adapter (Module 29.2).

Extracts point-in-time technical and behavioral features from historical BTC candles
and integrates read-only outputs from the frozen CBE-0.7.0 scientific model:
1. Moving average trend indicators (SMA, EMA).
2. Parkinson rolling volatility (using historical high-low).
3. Realized volatility (rolling log-return standard deviation).
4. Frozen CBE-0.7.0 regime classifications (read-only mapping).
5. Volatility regime categorization.
6. Strict no-lookahead guarantee: only completed historical candles are used.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_MODEL_ID = "CBE-0.7.0"
MODEL_STATUS = "STRICTLY_FROZEN"

# Read-only regime thresholds from CBE-0.7.0
FROZEN_REGIME_THRESHOLDS: Dict[str, float] = {
    "parkinson_rolling_window": 24,
    "vol_compressed_quantile": 0.25,
    "vol_elevated_quantile": 0.75,
    "vol_extreme_quantile": 0.90,
    "return_z_capitulation": -1.75,
    "return_z_momentum": 1.25,
    "return_z_distribution": -0.75,
    "return_z_recovery": 0.35,
}

CANONICAL_REGIMES = (
    "CONSOLIDATION_RANGING",
    "RECOVERY_ACCUMULATION",
    "MOMENTUM_EXPANSION",
    "DISTRIBUTION",
    "HIGH_VOLATILITY_EXPANSION",
    "CAPITULATION",
)

VOLATILITY_REGIMES = (
    "COMPRESSED_VOLATILITY",
    "NORMAL_VOLATILITY",
    "ELEVATED_VOLATILITY",
    "EXTREME_VOLATILITY",
)


class HistoricalFeatureAdapter:
    """Computes past-only technical features and extracts frozen CBE-0.7.0 model outputs."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or FROZEN_REGIME_THRESHOLDS

    @staticmethod
    def compute_sma(series: pd.Series, window: int) -> pd.Series:
        """Compute rolling Simple Moving Average on past observations."""
        return series.rolling(window=window, min_periods=window).mean()

    @staticmethod
    def compute_ema(series: pd.Series, span: int) -> pd.Series:
        """Compute Exponential Moving Average on past observations."""
        return series.ewm(span=span, adjust=False, min_periods=span).mean()

    @staticmethod
    def compute_parkinson_volatility(
        high: pd.Series, low: pd.Series, window: int = 24
    ) -> pd.Series:
        """Compute Parkinson rolling volatility estimator based on high/low ratio."""
        # Parkinson formula: sqrt( 1 / (4 * ln(2) * N) * sum( ln(H/L)^2 ) )
        hl_ratio = np.log(high / np.maximum(low, 1e-9))
        hl_sq = hl_ratio ** 2
        factor = 1.0 / (4.0 * math.log(2.0))
        rolling_mean_sq = hl_sq.rolling(window=window, min_periods=window).mean()
        vol = np.sqrt(factor * rolling_mean_sq)
        return vol

    @staticmethod
    def compute_realized_volatility(close: pd.Series, window: int = 24) -> pd.Series:
        """Compute annualized rolling realized volatility of log returns."""
        log_ret = np.log(close / close.shift(1))
        # Hourly data: sqrt(24 * 365) ~ sqrt(8760) ~ 93.59
        annual_factor = math.sqrt(8760)
        return log_ret.rolling(window=window, min_periods=window).std() * annual_factor

    def compute_cbe_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute CBE-0.7.0 canonical market and volatility regimes chronologically.

        Strictly read-only implementation of frozen CBE-0.7.0 rules.
        """
        out = pd.DataFrame(index=df.index)
        n = len(df)
        if n < 30:
            out["market_regime"] = "CONSOLIDATION_RANGING"
            out["volatility_regime"] = "NORMAL_VOLATILITY"
            out["parkinson_vol"] = 0.0
            return out

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Parkinson volatility (window=24)
        p_window = int(self.thresholds.get("parkinson_rolling_window", 24))
        p_vol = self.compute_parkinson_volatility(high, low, window=p_window)
        out["parkinson_vol"] = p_vol.fillna(0.0)

        # 24h log returns & standardized z-scores
        ret_24h = (close - close.shift(p_window)) / close.shift(p_window)
        ret_mean = ret_24h.rolling(window=168, min_periods=p_window).mean()
        ret_std = ret_24h.rolling(window=168, min_periods=p_window).std().replace(0.0, 1e-6)
        ret_z = (ret_24h - ret_mean) / ret_std
        ret_z = ret_z.fillna(0.0)

        # Rolling volatility quantiles (using 168h = 7 days rolling window for past-only reference)
        vol_q25 = p_vol.rolling(window=168, min_periods=p_window).quantile(self.thresholds["vol_compressed_quantile"]).fillna(0.01)
        vol_q75 = p_vol.rolling(window=168, min_periods=p_window).quantile(self.thresholds["vol_elevated_quantile"]).fillna(0.02)
        vol_q90 = p_vol.rolling(window=168, min_periods=p_window).quantile(self.thresholds["vol_extreme_quantile"]).fillna(0.03)

        vol_regimes: List[str] = []
        market_regimes: List[str] = []

        v_arr = p_vol.fillna(0.0).to_numpy()
        z_arr = ret_z.fillna(0.0).to_numpy()
        q25_arr = vol_q25.to_numpy()
        q75_arr = vol_q75.to_numpy()
        q90_arr = vol_q90.to_numpy()
        z_cap = float(self.thresholds["return_z_capitulation"])
        z_mom = float(self.thresholds["return_z_momentum"])
        z_dist = float(self.thresholds["return_z_distribution"])
        z_rec = float(self.thresholds["return_z_recovery"])

        for i in range(n):
            v = float(v_arr[i])
            z = float(z_arr[i])

            # Volatility regime assignment
            if v < q25_arr[i]:
                v_reg = "COMPRESSED_VOLATILITY"
            elif v < q75_arr[i]:
                v_reg = "NORMAL_VOLATILITY"
            elif v < q90_arr[i]:
                v_reg = "ELEVATED_VOLATILITY"
            else:
                v_reg = "EXTREME_VOLATILITY"
            vol_regimes.append(v_reg)

            # Market regime assignment according to frozen CBE-0.7.0 thresholds
            if v >= q90_arr[i]:
                m_reg = "HIGH_VOLATILITY_EXPANSION"
            elif z <= z_cap:
                m_reg = "CAPITULATION"
            elif z >= z_mom:
                m_reg = "MOMENTUM_EXPANSION"
            elif z <= z_dist:
                m_reg = "DISTRIBUTION"
            elif z >= z_rec:
                m_reg = "RECOVERY_ACCUMULATION"
            else:
                m_reg = "CONSOLIDATION_RANGING"
            market_regimes.append(m_reg)

        out["volatility_regime"] = vol_regimes
        out["market_regime"] = market_regimes
        return out

    def build_feature_table(
        self,
        df: pd.DataFrame,
        trend_short_window: int = 20,
        trend_long_window: int = 50,
    ) -> pd.DataFrame:
        """Construct full point-in-time feature DataFrame.

        All indicators are computed strictly on completed historical observations.
        """
        if df.empty:
            return pd.DataFrame()
        features = df.copy()

        # Moving averages
        features[f"sma_{trend_short_window}"] = self.compute_sma(features["close"], trend_short_window)
        features[f"sma_{trend_long_window}"] = self.compute_sma(features["close"], trend_long_window)
        features["ema_21"] = self.compute_ema(features["close"], 21)
        features["ema_55"] = self.compute_ema(features["close"], 55)

        # Volatility
        features["parkinson_vol_24"] = self.compute_parkinson_volatility(features["high"], features["low"], window=24)
        features["realized_vol_24"] = self.compute_realized_volatility(features["close"], window=24)

        # Regimes from frozen CBE-0.7.0
        regimes_df = self.compute_cbe_regimes(features)
        features["market_regime"] = regimes_df["market_regime"]
        features["volatility_regime"] = regimes_df["volatility_regime"]

        return features
