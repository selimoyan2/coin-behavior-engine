"""Return-based statistical features: simple/log returns, drawdowns, displacements."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Compute base 1-bar simple and log returns."""
    res = pd.DataFrame(index=df.index)
    close = df["close"]
    
    # 1-bar returns
    res["return_simple"] = close.pct_change().fillna(0.0)
    res["return_log"] = np.log(close / close.shift(1)).fillna(0.0)
    
    return res


def compute_displacement_and_drawdown(
    df: pd.DataFrame,
    windows: dict[str, int]
) -> pd.DataFrame:
    """Compute price displacements and rolling drawdowns across multiple windows."""
    res = pd.DataFrame(index=df.index)
    close = df["close"]
    high = df["high"]
    low = df["low"]

    for name, w in windows.items():
        # Price displacement over window w
        res[f"displacement_{name}"] = ((close - close.shift(w)) / close.shift(w)).fillna(0.0)

        # Rolling high and low over window w
        roll_high = high.rolling(window=w, min_periods=max(2, w // 4)).max()
        roll_low = low.rolling(window=w, min_periods=max(2, w // 4)).min()

        # Distance from rolling extremes (percentage)
        res[f"dist_from_high_{name}"] = ((roll_high - close) / roll_high).fillna(0.0)
        res[f"dist_from_low_{name}"] = ((close - roll_low) / roll_low).fillna(0.0)

        # Rolling drawdown (negative value representing drop from rolling peak)
        roll_peak = close.rolling(window=w, min_periods=max(2, w // 4)).max()
        res[f"drawdown_{name}"] = ((close - roll_peak) / roll_peak).fillna(0.0)

        # Linear trend slope (normalized) over window w
        # Closed-form linear regression slope of normalized close price
        # x is 0 .. w-1, slope = cov(x, y) / var(x)
        if w <= 144 and len(close) >= w:
            close_vals = close.to_numpy(dtype=float)
            x = np.arange(w, dtype=float)
            x_dev = x - x.mean()
            var_x = (x_dev ** 2).sum()
            kernel = x_dev / var_x

            # 1D convolution for linear slope
            raw_slope = np.convolve(close_vals, kernel[::-1], mode="valid")
            roll_mean = close.rolling(window=w, min_periods=w).mean().to_numpy()

            norm_slope = np.zeros(len(close), dtype=float)
            valid_means = roll_mean[w - 1 :]
            denom = np.where(valid_means != 0, valid_means, 1.0)
            norm_slope[w - 1 :] = raw_slope / denom

            res[f"trend_slope_{name}"] = pd.Series(norm_slope, index=df.index).fillna(0.0)

    return res
