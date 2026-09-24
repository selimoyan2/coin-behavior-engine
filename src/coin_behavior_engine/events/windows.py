"""Event window extraction and historical outcome evaluation (strictly separated)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime

WINDOW_HOURS_MAP = {
    "1h": 1,
    "4h": 4,
    "12h": 12,
    "24h": 24,
    "3d": 72,
    "7d": 168,
}


class EventWindowExtractor:
    """
    Extracts contextual PRE and POST observation windows for detected events.
    Architectural guarantee: POST outcomes are never merged into feature signals.
    """

    def __init__(
        self,
        timeframe_minutes: int = 5,
        failed_expansion_threshold_pct: float = 0.003
    ):
        self.tf_min = timeframe_minutes
        self.failed_thresh = failed_expansion_threshold_pct

    def evaluate_event_outcomes(
        self,
        events_df: pd.DataFrame,
        canonical_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculates PRE metrics and POST outcomes for every event in events_df.
        """
        if events_df.empty or canonical_df.empty:
            return events_df

        df = canonical_df.copy()
        if "timestamp_open" not in df.columns:
            raise KeyError("canonical_df must contain timestamp_open.")

        # Index by timestamp_open for fast lookup
        ts_index_map = {ts: idx for idx, ts in enumerate(df["timestamp_open"])}
        n_bars = len(df)

        close_arr = df["close"].to_numpy(dtype=float)
        high_arr = df["high"].to_numpy(dtype=float)
        low_arr = df["low"].to_numpy(dtype=float)
        vol_arr = df["volume"].to_numpy(dtype=float) if "volume" in df.columns else np.zeros(n_bars)

        enriched_rows = []
        for _, ev in events_df.iterrows():
            ev_dict = ev.to_dict()
            ts = int(ev["timestamp_open"])

            if ts not in ts_index_map:
                enriched_rows.append(ev_dict)
                continue

            idx = ts_index_map[ts]
            close_price = close_arr[idx]

            # 1. PRE-EVENT METRICS (using only past data idx - bars : idx)
            for w_label, hours in WINDOW_HOURS_MAP.items():
                bars = int(round(hours * 60 / self.tf_min))
                pre_idx = max(0, idx - bars)
                pre_close = close_arr[pre_idx]
                pre_ret = (close_price - pre_close) / pre_close if pre_close > 0 else 0.0
                ev_dict[f"pre_return_{w_label}"] = round(pre_ret, 5)

                if bars > 1:
                    ev_dict[f"pre_vol_mean_{w_label}"] = round(float(np.mean(vol_arr[pre_idx : idx + 1])), 2)

            # 2. POST-EVENT OUTCOMES (strictly isolated future outcome evaluation)
            for w_label, hours in WINDOW_HOURS_MAP.items():
                bars = int(round(hours * 60 / self.tf_min))
                post_idx = min(n_bars - 1, idx + bars)
                post_close = close_arr[post_idx]
                post_ret = (post_close - close_price) / close_price if close_price > 0 else 0.0
                ev_dict[f"post_return_{w_label}"] = round(post_ret, 5)

                if post_idx > idx:
                    max_high = float(np.max(high_arr[idx : post_idx + 1]))
                    min_low = float(np.min(low_arr[idx : post_idx + 1]))
                    mfe = (max_high - close_price) / close_price
                    mae = (min_low - close_price) / close_price
                    ev_dict[f"post_mfe_{w_label}"] = round(mfe, 5)
                    ev_dict[f"post_mae_{w_label}"] = round(mae, 5)

            # 3. FALSE-POSITIVE & CONTINUATION CLASSIFICATION
            etype = str(ev.get("event_type", ""))
            post_ret_4h = ev_dict.get("post_return_4h", 0.0)

            if "UPWARD" in etype or "BREAKOUT" in etype:
                if post_ret_4h < self.failed_thresh:
                    outcome_class = "FAILED_EXPANSION" if "UPWARD" in etype else "FALSE_BREAKOUT_CANDIDATE"
                else:
                    outcome_class = "EVENT_CONTINUATION"
            elif "DOWNWARD" in etype or "BREAKDOWN" in etype:
                if post_ret_4h > -self.failed_thresh:
                    outcome_class = "FAILED_EXPANSION" if "DOWNWARD" in etype else "FALSE_BREAKDOWN_CANDIDATE"
                else:
                    outcome_class = "EVENT_CONTINUATION"
            elif "COMPRESSION" in etype:
                outcome_class = "COMPRESSION_REGIME"
            else:
                outcome_class = "EVENT_OBSERVATION"

            ev_dict["outcome_classification"] = outcome_class
            enriched_rows.append(ev_dict)

        result_df = pd.DataFrame(enriched_rows)
        logger.info(f"Evaluated pre/post windows and outcomes for {len(result_df)} events.")
        return result_df
