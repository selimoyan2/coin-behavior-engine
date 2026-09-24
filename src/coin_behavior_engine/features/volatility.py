"""Volatility features: True Range, Realized Volatility, Range Expansion/Contraction."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_true_range(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate True Range (TR) and Normalized True Range (NTR)."""
    res = pd.DataFrame(index=df.index)
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    c1 = high - low
    c2 = (high - prev_close).abs()
    c3 = (low - prev_close).abs()

    tr = np.maximum(c1, np.maximum(c2, c3))
    tr.iloc[0] = c1.iloc[0]  # First candle fallback

    res["true_range"] = tr
    res["normalized_range"] = tr / df["close"]
    return res


def compute_volatility_features(
    df: pd.DataFrame,
    windows: dict[str, int]
) -> pd.DataFrame:
    """Compute realized volatility, range expansion, and volatility acceleration."""
    res = pd.DataFrame(index=df.index)
    tr_df = compute_true_range(df)
    res["true_range"] = tr_df["true_range"]
    res["normalized_range"] = tr_df["normalized_range"]

    log_ret = np.log(df["close"] / df["close"].shift(1)).fillna(0.0)

    for name, w in windows.items():
        min_p = max(2, w // 4)
        # Realized volatility (rolling std of log returns annualized/scaled)
        roll_vol = log_ret.rolling(window=w, min_periods=min_p).std().fillna(0.0)
        res[f"volatility_realized_{name}"] = roll_vol

        # Rolling mean normalized range (ATR-like proxy)
        roll_atr = res["normalized_range"].rolling(window=w, min_periods=min_p).mean().fillna(0.0)
        res[f"rolling_atr_{name}"] = roll_atr

        # Range expansion ratio: current normalized range relative to rolling ATR
        res[f"range_expansion_{name}"] = (
            (res["normalized_range"] / (roll_atr.replace(0, np.nan)))
            .fillna(1.0)
            .clip(lower=0.1, upper=20.0)
        )

        # Range contraction ratio: rolling ATR relative to current range
        res[f"range_contraction_{name}"] = (
            (roll_atr / (res["normalized_range"].replace(0, np.nan)))
            .fillna(1.0)
            .clip(lower=0.1, upper=20.0)
        )

        # Volatility acceleration: rolling vol / lagged rolling vol
        lag_w = max(1, w // 2)
        lagged_vol = roll_vol.shift(lag_w)
        res[f"volatility_acceleration_{name}"] = (
            (roll_vol / lagged_vol.replace(0, np.nan))
            .fillna(1.0)
            .clip(lower=0.05, upper=15.0)
        )

    return res
