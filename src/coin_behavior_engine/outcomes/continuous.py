"""Continuous multi-horizon forward outcome generator for market behavior research.

Replaces binary follow-through heuristics with rigorous continuous distributions:
- Horizons: 15m (3c), 30m (6c), 1h (12c), 2h (24c), 4h (48c), 8h (96c), 12h (144c), 24h (288c), 3d (864c), 7d (2016c)
- Forward Metrics:
  * Signed Return: (P_{t+h} - P_t) / P_t
  * Absolute Return: |Signed Return|
  * MFE (Maximum Favorable Excursion): (max(H_{t+1..t+h}) - P_t) / P_t
  * MAE (Maximum Adverse Excursion): (P_t - min(L_{t+1..t+h})) / P_t
  * High-Low Range: (max(H) - min(L)) / P_t
  * Realized Volatility: forward std of 5m log returns
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger

HORIZONS_5M: Dict[str, int] = {
    "15m": 3,
    "30m": 6,
    "1h": 12,
    "2h": 24,
    "4h": 48,
    "8h": 96,
    "12h": 144,
    "24h": 288,
    "3d": 864,
    "7d": 2016,
}


class ContinuousOutcomeEngine:
    """Computes vectorized forward outcome distributions across multiple horizons."""

    def __init__(self, horizons: Dict[str, int] | None = None):
        self.horizons = horizons or HORIZONS_5M

    def compute_forward_outcomes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all multi-horizon forward outcome metrics on a 5m canonical dataframe.
        Appends columns with prefix 'fwd_' and returns a copy.
        """
        if df.empty:
            return df

        required = ["close", "high", "low"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column '{col}' for outcome computation.")

        out_df = df.copy()
        close = out_df["close"]
        high = out_df["high"]
        low = out_df["low"]

        # Log returns for forward realized volatility
        log_ret = np.log(close / close.shift(1)).fillna(0.0)

        # Precompute reversed series for fast rolling calculations
        rev_high = high.iloc[::-1]
        rev_low = low.iloc[::-1]
        rev_log_ret = log_ret.iloc[::-1]

        logger.info(f"Computing continuous forward outcomes across {len(self.horizons)} horizons...")

        for h_label, h_steps in self.horizons.items():
            # 1. Forward Close & Signed Return
            fwd_close = close.shift(-h_steps)
            signed_ret = (fwd_close - close) / close
            abs_ret = signed_ret.abs()

            # 2. Forward Max High & Min Low over (t+1 .. t+h)
            fwd_max_high = rev_high.rolling(h_steps, min_periods=h_steps).max().iloc[::-1].shift(-1)
            fwd_min_low = rev_low.rolling(h_steps, min_periods=h_steps).min().iloc[::-1].shift(-1)

            # 3. MFE and MAE (directional for long perspective; inverse for short)
            mfe_long = (fwd_max_high - close) / close
            mae_long = (close - fwd_min_low) / close

            # 4. Forward Range
            fwd_range = (fwd_max_high - fwd_min_low) / close

            # 5. Forward Realized Volatility (sample std of 5m log returns in window)
            fwd_vol = rev_log_ret.rolling(h_steps, min_periods=h_steps).std().iloc[::-1].shift(-1)

            # Assign columns
            out_df[f"fwd_ret_{h_label}"] = signed_ret
            out_df[f"fwd_abs_ret_{h_label}"] = abs_ret
            out_df[f"fwd_mfe_{h_label}"] = mfe_long
            out_df[f"fwd_mae_{h_label}"] = mae_long
            out_df[f"fwd_range_{h_label}"] = fwd_range
            out_df[f"fwd_vol_{h_label}"] = fwd_vol

        return out_df

    def summarize_outcome_distributions(
        self,
        df: pd.DataFrame,
        mask: pd.Series | None = None
    ) -> pd.DataFrame:
        """
        Summarize continuous outcome distributions across horizons:
        mean, median, std, p5, p25, p75, p95, skewness, kurtosis.
        """
        subset = df[mask] if mask is not None else df
        summary_rows = []

        for h_label in self.horizons.keys():
            col_ret = f"fwd_ret_{h_label}"
            col_abs = f"fwd_abs_ret_{h_label}"
            col_mfe = f"fwd_mfe_{h_label}"
            col_mae = f"fwd_mae_{h_label}"
            col_vol = f"fwd_vol_{h_label}"

            if col_ret not in subset.columns:
                continue

            s_ret = subset[col_ret].dropna()
            s_abs = subset[col_abs].dropna()
            s_mfe = subset[col_mfe].dropna()
            s_mae = subset[col_mae].dropna()

            if len(s_ret) == 0:
                continue

            summary_rows.append({
                "horizon": h_label,
                "n_samples": len(s_ret),
                "mean_signed_ret": float(s_ret.mean()),
                "median_signed_ret": float(s_ret.median()),
                "std_signed_ret": float(s_ret.std()),
                "skew_signed_ret": float(s_ret.skew()),
                "mean_abs_ret": float(s_abs.mean()),
                "median_abs_ret": float(s_abs.median()),
                "p75_abs_ret": float(s_abs.quantile(0.75)),
                "p95_abs_ret": float(s_abs.quantile(0.95)),
                "mean_mfe": float(s_mfe.mean()),
                "mean_mae": float(s_mae.mean()),
                "mfe_mae_ratio": float(s_mfe.mean() / s_mae.mean()) if s_mae.mean() != 0 else np.nan,
            })

        return pd.DataFrame(summary_rows)
