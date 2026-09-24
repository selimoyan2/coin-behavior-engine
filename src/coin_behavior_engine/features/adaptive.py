"""Adaptive normalization: rolling empirical percentile ranks, robust scoring."""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
import pandas as pd


def rolling_percentile_rank(series: pd.Series, window: int = 288) -> pd.Series:
    """
    Calculate the empirical percentile rank of each value relative to its rolling past window.
    Strictly look-ahead free (uses only observations up to current timestamp t).
    Returns values in range [0.0, 1.0].
    """
    n = len(series)
    if n == 0:
        return pd.Series([], index=series.index, dtype=float)

    values = series.to_numpy(dtype=float)
    ranks = np.full(n, 0.5, dtype=float)

    if n < window:
        # Fallback for short series
        for i in range(n):
            sub = values[: i + 1]
            valid = sub[~np.isnan(sub)]
            if len(valid) > 0:
                ranks[i] = (valid <= values[i]).mean()
        return pd.Series(ranks, index=series.index, dtype=float)

    # Initial warm-up period (0 to window - 2)
    for i in range(window - 1):
        sub = values[: i + 1]
        valid = sub[~np.isnan(sub)]
        if len(valid) > 0:
            ranks[i] = (valid <= values[i]).mean()

    # Fully vectorized calculation for main body
    windows = sliding_window_view(values, window_shape=window)
    targets = values[window - 1 :, None]
    ranks[window - 1 :] = (windows <= targets).mean(axis=1)

    return pd.Series(ranks, index=series.index, dtype=float)


def compute_adaptive_features(
    df: pd.DataFrame,
    feature_df: pd.DataFrame,
    distribution_window: int = 288
) -> pd.DataFrame:
    """
    Compute adaptive contextual features:
    - Abs return rolling percentile
    - Normalized range rolling percentile
    - Volume rolling percentile
    - Realized volatility rolling percentile
    """
    res = pd.DataFrame(index=df.index)

    abs_ret = feature_df["return_simple"].abs()
    norm_range = feature_df.get("normalized_range", (df["high"] - df["low"]) / df["close"])
    vol = df["volume"]
    realized_vol = feature_df.get("volatility_realized_short", abs_ret)

    res["rank_abs_return"] = rolling_percentile_rank(abs_ret, window=distribution_window)
    res["rank_normalized_range"] = rolling_percentile_rank(norm_range, window=distribution_window)
    res["rank_volume"] = rolling_percentile_rank(vol, window=distribution_window)
    res["rank_volatility"] = rolling_percentile_rank(realized_vol, window=distribution_window)

    return res
