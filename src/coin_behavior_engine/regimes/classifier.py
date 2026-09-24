"""Regime episode aggregation and characteristic tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.config.schema import RegimesConfig
from coin_behavior_engine.regimes.detector import assign_bar_regimes
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime


class RegimeClassifier:
    """Detects and structures continuous market regime blocks."""

    def __init__(self, regimes_cfg: Optional[RegimesConfig] = None):
        self.cfg = regimes_cfg or RegimesConfig()

    def detect_regimes(self, features_df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
        """
        Assigns bar-level regimes and aggregates into distinct regime episodes.
        Returns:
            bar_regimes: pd.Series of regime label per bar
            regimes_table: pd.DataFrame of regime episodes
        """
        logger.info(f"Classifying market regimes over {len(features_df)} bars...")
        bar_regimes = assign_bar_regimes(features_df, self.cfg)

        # Smooth transient 1-bar spikes if min_duration > 1
        min_bars = self.cfg.min_regime_duration_bars
        smoothed = bar_regimes.copy()

        # Build contiguous regime blocks using fast numpy arrays
        blocks: List[Dict[str, Any]] = []
        n = len(features_df)
        if n == 0:
            return bar_regimes, pd.DataFrame()

        close_arr = features_df["close"].to_numpy(dtype=float)
        ts_open_arr = features_df["timestamp_open"].to_numpy(dtype=int)
        ts_close_arr = features_df["timestamp_close"].to_numpy(dtype=int)
        vol_arr = features_df["volume"].to_numpy(dtype=float)
        ret_arr = features_df["return_simple"].to_numpy(dtype=float) if "return_simple" in features_df.columns else np.zeros(n)
        labels_arr = smoothed.to_numpy()

        start_idx = 0
        current_label = labels_arr[0]

        for i in range(1, n):
            label = labels_arr[i]
            if label != current_label:
                # Close block
                end_idx = i - 1
                duration = end_idx - start_idx + 1

                start_ts = int(ts_open_arr[start_idx])
                end_ts = int(ts_close_arr[end_idx])

                close_start = close_arr[start_idx]
                close_end = close_arr[end_idx]
                displacement = (close_end - close_start) / close_start if close_start > 0 else 0.0

                mean_vol = float(np.mean(vol_arr[start_idx : end_idx + 1]))
                realized_vol = float(np.std(ret_arr[start_idx : end_idx + 1]))

                blocks.append({
                    "regime_id": len(blocks) + 1,
                    "regime_label": current_label,
                    "start_timestamp": start_ts,
                    "end_timestamp": end_ts,
                    "start_utc": str(to_utc_datetime(start_ts)),
                    "end_utc": str(to_utc_datetime(end_ts)),
                    "duration_bars": duration,
                    "duration_hours": round(duration * 5 / 60, 2),  # for 5m bars
                    "total_displacement_pct": round(displacement * 100, 3),
                    "mean_volume": round(mean_vol, 2),
                    "realized_volatility": round(realized_vol, 6),
                })

                start_idx = i
                current_label = label

        # Last block
        end_idx = n - 1
        duration = end_idx - start_idx + 1
        start_ts = int(ts_open_arr[start_idx])
        end_ts = int(ts_close_arr[end_idx])
        close_start = close_arr[start_idx]
        close_end = close_arr[end_idx]
        displacement = (close_end - close_start) / close_start if close_start > 0 else 0.0

        blocks.append({
            "regime_id": len(blocks) + 1,
            "regime_label": current_label,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "start_utc": str(to_utc_datetime(start_ts)),
            "end_utc": str(to_utc_datetime(end_ts)),
            "duration_bars": duration,
            "duration_hours": round(duration * 5 / 60, 2),
            "total_displacement_pct": round(displacement * 100, 3),
            "mean_volume": round(float(np.mean(vol_arr[start_idx : end_idx + 1])), 2),
            "realized_volatility": round(float(np.std(ret_arr[start_idx : end_idx + 1])), 6),
        })

        regimes_df = pd.DataFrame(blocks)
        logger.info(f"Identified {len(regimes_df)} distinct regime blocks.")
        return bar_regimes, regimes_df
