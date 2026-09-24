"""Pre-event feature snapshot extractor.

Extracts feature vectors at fixed intervals strictly prior to detected significant events:
T-5m (1c), T-15m (3c), T-30m (6c), T-1h (12c), T-2h (24c), T-4h (48c), T-8h (96c), T-12h (144c), T-24h (288c).

Guarantees 100% causal isolation: only data available at or before T-offset is accessed.
"""

from __future__ import annotations

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from coin_behavior_engine.utils.logging import logger

SNAPSHOT_OFFSETS_5M: Dict[str, int] = {
    "T_minus_5m": 1,
    "T_minus_15m": 3,
    "T_minus_30m": 6,
    "T_minus_1h": 12,
    "T_minus_2h": 24,
    "T_minus_4h": 48,
    "T_minus_8h": 96,
    "T_minus_12h": 144,
    "T_minus_24h": 288,
}

FEATURE_COLS_DEFAULT = [
    "volatility_realized_24h",
    "volatility_compression_ratio",
    "volume_zscore_24h",
    "volume_buy_ratio",
    "return_log_1h",
    "return_log_24h",
    "trend_slope_24h",
    "event_score",
]


class PreEventSnapshotExtractor:
    """Extracts pre-event snapshot feature vectors for statistical comparison."""

    def __init__(
        self,
        offsets: Dict[str, int] | None = None,
        feature_cols: List[str] | None = None,
    ):
        self.offsets = offsets or SNAPSHOT_OFFSETS_5M
        self.feature_cols = feature_cols or FEATURE_COLS_DEFAULT

    def extract_snapshots_for_events(
        self,
        df: pd.DataFrame,
        event_indices: List[int],
    ) -> Dict[str, pd.DataFrame]:
        """
        Extract snapshot dataframes for each offset across all given event indices.
        Returns a dict: offset_name -> DataFrame of features at that offset.
        """
        # Ensure available feature columns
        available_features = [col for col in self.feature_cols if col in df.columns]
        if not available_features:
            raise ValueError(f"None of requested feature cols {self.feature_cols} found in DataFrame.")

        snapshots_by_offset = {}

        for offset_name, offset_steps in self.offsets.items():
            ev_arr = np.array(event_indices, dtype=int)
            snap_arr = ev_arr - offset_steps
            valid_mask = (snap_arr >= 0) & (snap_arr < len(df))
            v_ev = ev_arr[valid_mask]
            v_snap = snap_arr[valid_mask]

            sub_feats = df.iloc[v_snap][available_features].copy().reset_index(drop=True)
            sub_feats["event_idx"] = v_ev
            sub_feats["snapshot_idx"] = v_snap
            sub_feats["offset_name"] = offset_name
            sub_feats["offset_steps"] = offset_steps
            snapshots_by_offset[offset_name] = sub_feats

        return snapshots_by_offset
