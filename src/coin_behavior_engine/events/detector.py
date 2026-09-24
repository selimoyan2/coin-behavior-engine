"""Adaptive event anomaly scoring and classification engine."""

from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.config.schema import EventsConfig
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime


def compute_composite_event_score(
    features_df: pd.DataFrame,
    events_cfg: EventsConfig
) -> pd.Series:
    """
    Compute adaptive composite anomaly score in [0.0, 1.0].
    Weighted combination of empirical percentile ranks:
    - return extremity
    - range expansion
    - volume surge
    - volatility expansion
    """
    w = events_cfg.weights
    rank_ret = features_df.get("rank_abs_return", 0.5)
    rank_range = features_df.get("rank_normalized_range", 0.5)
    rank_vol = features_df.get("rank_volume", 0.5)
    rank_vola = features_df.get("rank_volatility", 0.5)

    score = (
        w.return_abnormality * rank_ret
        + w.range_abnormality * rank_range
        + w.volume_abnormality * rank_vol
        + w.volatility_expansion * rank_vola
    )
    return pd.Series(score, index=features_df.index, name="event_score")


def assign_event_types(df: pd.DataFrame, score_threshold: float = 0.95) -> pd.Series:
    """Vectorized classification of candidate market behavior anomalies."""
    score = df["event_score"]
    ret = df.get("return_simple", pd.Series(0.0, index=df.index))
    vol_rank = df.get("rank_volume", pd.Series(0.5, index=df.index))
    vola_rank = df.get("rank_volatility", pd.Series(0.5, index=df.index))
    range_rank = df.get("rank_normalized_range", pd.Series(0.5, index=df.index))
    dist_high = df.get("dist_from_high_short", pd.Series(0.05, index=df.index))
    dist_low = df.get("dist_from_low_short", pd.Series(0.05, index=df.index))
    disp = df.get("displacement_medium", pd.Series(0.0, index=df.index))

    conds = [
        (vola_rank <= 0.15) & (range_rank <= 0.15) & (score <= 0.25),
        (score >= score_threshold) & (dist_high <= 0.0005) & (disp > 0.005) & (ret > 0),
        (score >= score_threshold) & (dist_low <= 0.0005) & (disp < -0.005) & (ret < 0),
        (score >= score_threshold) & (((disp < -0.015) & (ret > 0.008)) | ((disp > 0.015) & (ret < -0.008))),
        (score >= score_threshold) & (ret > 0),
        (score >= score_threshold) & (ret < 0),
        (score >= score_threshold) & (vol_rank >= 0.98) & (range_rank < 0.80),
        (score >= score_threshold) & (vola_rank >= 0.98),
        (score >= score_threshold),
    ]
    choices = [
        "COMPRESSION",
        "BREAKOUT_CANDIDATE",
        "BREAKDOWN_CANDIDATE",
        "REVERSAL_CANDIDATE",
        "UPWARD_EXPANSION",
        "DOWNWARD_EXPANSION",
        "VOLUME_EXPANSION",
        "VOLATILITY_EXPANSION",
        "ANOMALY_CANDIDATE",
    ]
    types = np.select(conds, choices, default=None)
    return pd.Series(types, index=df.index)


class EventDetector:
    """Discovers significant market events from statistical distributions."""

    def __init__(self, events_cfg: Optional[EventsConfig] = None):
        self.cfg = events_cfg or EventsConfig()

    def detect_events(self, features_df: pd.DataFrame, timeframe: str = "5m") -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Calculates event scores and extracts significant market events.
        Returns:
            df_with_scores: original features with event_score and event_type
            events_df: filtered table of detected significant events
        """
        df = features_df.copy()
        df["event_score"] = compute_composite_event_score(df, self.cfg)

        thresh = self.cfg.candidate_percentile_threshold
        sig_thresh = self.cfg.significant_event_percentile_threshold

        df["event_type"] = assign_event_types(df, score_threshold=thresh)

        # Extract events that meet candidate or significant threshold or are COMPRESSION
        mask = (df["event_score"] >= thresh) | (df["event_type"] == "COMPRESSION")
        candidates = df[mask].copy()

        event_rows = {
            "timeframe": timeframe,
            "timestamp_open": candidates["timestamp_open"].astype("int64").values,
            "timestamp_close": candidates["timestamp_close"].astype("int64").values,
            "datetime_open_utc": candidates["datetime_open"].astype(str).values if "datetime_open" in candidates.columns else [str(to_utc_datetime(int(ts))) for ts in candidates["timestamp_open"].values],
            "event_type": candidates["event_type"].fillna("ANOMALY_CANDIDATE").astype(str).values,
            "event_score": candidates["event_score"].round(4).values,
            "is_significant": (candidates["event_score"] >= sig_thresh).values,
            "close_price": candidates["close"].astype(float).values,
            "return_simple": candidates["return_simple"].fillna(0.0).astype(float).values if "return_simple" in candidates.columns else np.zeros(len(candidates)),
            "normalized_range": candidates["normalized_range"].fillna(0.0).astype(float).values if "normalized_range" in candidates.columns else np.zeros(len(candidates)),
            "volume": candidates["volume"].fillna(0.0).astype(float).values if "volume" in candidates.columns else np.zeros(len(candidates)),
            "volatility_realized": candidates["volatility_realized_short"].fillna(0.0).astype(float).values if "volatility_realized_short" in candidates.columns else np.zeros(len(candidates)),
            "regime_during": candidates["regime_label"].fillna("UNKNOWN").astype(str).values if "regime_label" in candidates.columns else np.full(len(candidates), "UNKNOWN"),
        }
        events_df = pd.DataFrame(event_rows)
        if not events_df.empty:
            events_df["event_id"] = [f"{timeframe}_{i+1}" for i in range(len(events_df))]

        logger.info(f"Detected {len(events_df)} candidate/significant events for {timeframe}.")
        return df, events_df
