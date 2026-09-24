"""Distributional features: rolling skewness, kurtosis, quantiles, MAD, robust z-scores."""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import pandas as pd


def compute_distribution_features(
    df: pd.DataFrame,
    windows: dict[str, int],
    mad_multiplier: float = 1.4826
) -> pd.DataFrame:
    """Compute rolling skewness, kurtosis, quantiles, and robust MAD statistics."""
    res = pd.DataFrame(index=df.index)
    log_ret = np.log(df["close"] / df["close"].shift(1)).fillna(0.0)

    for name, w in windows.items():
        min_p = max(5, w // 4)

        # Skewness & Kurtosis for medium and baseline windows
        if w in (windows.get("medium"), windows.get("baseline"), windows.get("long")):
            res[f"return_skew_{name}"] = log_ret.rolling(window=w, min_periods=min_p).skew().fillna(0.0)
            res[f"return_kurt_{name}"] = log_ret.rolling(window=w, min_periods=min_p).kurt().fillna(0.0)

        # Standard mean and std
        r_mean = log_ret.rolling(window=w, min_periods=min_p).mean()
        r_std = log_ret.rolling(window=w, min_periods=min_p).std().replace(0, np.nan)
        res[f"return_zscore_{name}"] = ((log_ret - r_mean) / r_std).fillna(0.0).clip(-10.0, 10.0)

        # Rolling median
        r_med = log_ret.rolling(window=w, min_periods=min_p).median()
        res[f"return_median_{name}"] = r_med.fillna(0.0)

        # Fast Vectorized Rolling MAD on returns for short/medium windows
        if w <= 144 and len(log_ret) >= w:
            ret_vals = log_ret.to_numpy(dtype=float)
            windows_arr = sliding_window_view(ret_vals, window_shape=w)
            med = np.median(windows_arr, axis=1, keepdims=True)
            mad_vals = np.median(np.abs(windows_arr - med), axis=1)

            mad_full = np.zeros(len(log_ret), dtype=float)
            mad_full[w - 1 :] = mad_vals
            roll_mad = pd.Series(mad_full, index=df.index).replace(0, np.nan)
            res[f"return_mad_{name}"] = roll_mad.fillna(0.0)
            res[f"return_robust_zscore_{name}"] = (
                (log_ret - r_med) / (mad_multiplier * roll_mad)
            ).fillna(0.0).clip(-10.0, 10.0)

    return res
