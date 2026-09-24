"""Market regime classification using statistical state rules."""

from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.config.schema import RegimesConfig


def assign_bar_regimes(
    features_df: pd.DataFrame,
    regimes_cfg: RegimesConfig
) -> pd.Series:
    """Vectorized bar regime assignment across full time series."""
    vol_rank = features_df["rank_volatility"] if "rank_volatility" in features_df else pd.Series(0.5, index=features_df.index)
    slope = features_df["trend_slope_medium"] if "trend_slope_medium" in features_df else pd.Series(0.0, index=features_df.index)
    disp = features_df["displacement_medium"] if "displacement_medium" in features_df else pd.Series(0.0, index=features_df.index)
    range_exp = features_df["range_expansion_medium"] if "range_expansion_medium" in features_df else pd.Series(1.0, index=features_df.index)

    vol_low = regimes_cfg.volatility_low_percentile
    vol_high = regimes_cfg.volatility_high_percentile
    slope_thresh = 0.00015

    conds = [
        (vol_rank <= vol_low) & (range_exp < 1.0),
        (slope > slope_thresh) & (disp > 0.005),
        (slope < -slope_thresh) & (disp < -0.005),
        (vol_rank >= vol_high),
        (slope.abs() <= slope_thresh) & (vol_rank > vol_low) & (vol_rank < vol_high),
    ]
    choices = [
        "LOW_VOLATILITY_COMPRESSION",
        "TRENDING_UP",
        "TRENDING_DOWN",
        "HIGH_VOLATILITY",
        "SIDEWAYS",
    ]
    labels = np.select(conds, choices, default="TRANSITION")
    return pd.Series(labels, index=features_df.index, name="regime_label")
