"""Volume features: rolling volume stats, volume z-scores, volume acceleration."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_volume_features(
    df: pd.DataFrame,
    windows: dict[str, int]
) -> pd.DataFrame:
    """Compute volume rolling stats, z-scores, and volume acceleration."""
    res = pd.DataFrame(index=df.index)
    vol = df["volume"]

    # Taker buy volume ratio (if available)
    if "taker_buy_base_volume" in df.columns:
        res["taker_buy_ratio"] = (
            (df["taker_buy_base_volume"] / vol.replace(0, np.nan))
            .fillna(0.5)
            .clip(0.0, 1.0)
        )

    for name, w in windows.items():
        min_p = max(2, w // 4)
        v_mean = vol.rolling(window=w, min_periods=min_p).mean()
        v_std = vol.rolling(window=w, min_periods=min_p).std().replace(0, np.nan)
        v_median = vol.rolling(window=w, min_periods=min_p).median()

        res[f"volume_mean_{name}"] = v_mean.fillna(0.0)
        res[f"volume_median_{name}"] = v_median.fillna(0.0)
        res[f"volume_std_{name}"] = v_std.fillna(0.0)

        # Volume z-score
        res[f"volume_zscore_{name}"] = ((vol - v_mean) / v_std).fillna(0.0).clip(-5.0, 15.0)

        # Volume acceleration: current volume relative to rolling mean
        res[f"volume_acceleration_{name}"] = (
            (vol / v_mean.replace(0, np.nan))
            .fillna(1.0)
            .clip(lower=0.01, upper=50.0)
        )

    return res
