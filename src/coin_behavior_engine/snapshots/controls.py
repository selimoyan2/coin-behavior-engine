"""Deterministic Matched Control Engine for pre-event comparison.

For each event E_i at T_i, identifies non-event control timestamps C_i matching:
1. Calendar Year
2. Time of Day (+/- 1 UTC hour)
3. Day of Week (weekday vs weekend)
4. Volatility Decile (+/- 1 decile of 24h realized volatility)
5. Trend Decile (+/- 1 decile of 24h return momentum)
Strict Exclusion: No control timestamp can be within 24 hours (+/- 288 candles) of ANY event.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


class MatchedControlEngine:
    """Finds deterministic matched non-event control samples."""

    def __init__(
        self,
        event_exclusion_window_candles: int = 288,  # +/- 24h
        random_seed: int = 42,
    ):
        self.exclusion_window = event_exclusion_window_candles
        self.random_seed = random_seed

    def build_exclusion_mask(self, n_rows: int, event_indices: List[int]) -> np.ndarray:
        """Create a boolean mask where True indicates index is within exclusion window of an event."""
        mask = np.zeros(n_rows, dtype=bool)
        for idx in event_indices:
            start = max(0, idx - self.exclusion_window)
            end = min(n_rows, idx + self.exclusion_window + 1)
            mask[start:end] = True
        return mask

    def find_matched_controls(
        self,
        df: pd.DataFrame,
        event_indices: List[int],
        vol_col: str = "volatility_realized_24h",
        trend_col: str = "return_log_24h",
    ) -> pd.DataFrame:
        """
        Identify matched control indices for each event index.
        Returns a DataFrame mapping event_idx to control_idx with matching diagnostic metrics.
        """
        if df.empty or not event_indices:
            return pd.DataFrame()

        n_rows = len(df)
        exclusion_mask = self.build_exclusion_mask(n_rows, event_indices)

        # Candidate pool is valid candles not in exclusion window and not NaN in matching features
        dt_series = pd.to_datetime(df["datetime_open"], utc=True)
        years = dt_series.dt.year.to_numpy()
        hours = dt_series.dt.hour.to_numpy()
        is_weekend = (dt_series.dt.dayofweek >= 5).to_numpy()

        # Decile computations on non-null values
        vol_vals = df[vol_col].to_numpy()
        trend_vals = df[trend_col].to_numpy()

        # Use qcut or percentile ranks for robust deciles
        vol_deciles = pd.qcut(df[vol_col].rank(method="first"), 10, labels=False).to_numpy()
        trend_deciles = pd.qcut(df[trend_col].rank(method="first"), 10, labels=False).to_numpy()

        candidate_indices = np.where(~exclusion_mask & ~np.isnan(vol_vals) & ~np.isnan(trend_vals))[0]

        logger.info(
            f"Control matching: {len(event_indices)} events vs {len(candidate_indices)} non-event candidates "
            f"({len(candidate_indices) / n_rows:.1%} of dataset eligible as controls)."
        )

        matched_pairs = []

        # Candidate lookup array
        cand_years = years[candidate_indices]
        cand_hours = hours[candidate_indices]
        cand_weekend = is_weekend[candidate_indices]
        cand_vol_dec = vol_deciles[candidate_indices]
        cand_trend_dec = trend_deciles[candidate_indices]
        cand_vol = vol_vals[candidate_indices]
        cand_trend = trend_vals[candidate_indices]

        # Normalized scales for distance metric
        vol_std = np.nanstd(vol_vals) if np.nanstd(vol_vals) > 0 else 1.0
        trend_std = np.nanstd(trend_vals) if np.nanstd(trend_vals) > 0 else 1.0

        for event_idx in event_indices:
            e_year = years[event_idx]
            e_hour = hours[event_idx]
            e_wknd = is_weekend[event_idx]
            e_v_dec = vol_deciles[event_idx]
            e_t_dec = trend_deciles[event_idx]
            e_v = vol_vals[event_idx]
            e_t = trend_vals[event_idx]

            # Matching filter:
            # 1. Same year
            # 2. Same weekend status
            # 3. Hour diff <= 1 (handling circular 23 to 0)
            hour_diff = np.minimum(np.abs(cand_hours - e_hour), 24 - np.abs(cand_hours - e_hour))
            match_mask = (
                (cand_years == e_year) &
                (cand_weekend == e_wknd) &
                (hour_diff <= 1) &
                (np.abs(cand_vol_dec - e_v_dec) <= 1) &
                (np.abs(cand_trend_dec - e_t_dec) <= 1)
            )

            matched_cands = candidate_indices[match_mask]

            if len(matched_cands) == 0:
                # Relax decile restriction to +/- 2 if strict matching finds 0
                match_mask_relaxed = (
                    (cand_years == e_year) &
                    (cand_weekend == e_wknd) &
                    (hour_diff <= 2) &
                    (np.abs(cand_vol_dec - e_v_dec) <= 2) &
                    (np.abs(cand_trend_dec - e_t_dec) <= 2)
                )
                matched_cands = candidate_indices[match_mask_relaxed]

            if len(matched_cands) == 0:
                continue

            # Deterministic selection: minimum normalized Euclidean distance in (vol, trend)
            sub_vol = vol_vals[matched_cands]
            sub_trend = trend_vals[matched_cands]
            dists = ((sub_vol - e_v) / vol_std) ** 2 + ((sub_trend - e_t) / trend_std) ** 2
            best_idx = matched_cands[np.argmin(dists)]

            matched_pairs.append({
                "event_idx": int(event_idx),
                "event_time": str(df.at[event_idx, "datetime_open"]),
                "control_idx": int(best_idx),
                "control_time": str(df.at[best_idx, "datetime_open"]),
                "distance": float(np.min(dists)),
                "year_match": bool(years[event_idx] == years[best_idx]),
                "hour_diff": int(min(abs(hours[event_idx] - hours[best_idx]), 24 - abs(hours[event_idx] - hours[best_idx]))),
                "weekend_match": bool(is_weekend[event_idx] == is_weekend[best_idx]),
                "vol_decile_event": int(e_v_dec),
                "vol_decile_control": int(vol_deciles[best_idx]),
                "trend_decile_event": int(e_t_dec),
                "trend_decile_control": int(trend_deciles[best_idx]),
            })

        result_df = pd.DataFrame(matched_pairs)
        logger.info(f"Successfully matched {len(result_df)} / {len(event_indices)} events with controls.")
        return result_df
