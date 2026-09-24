"""Information Decay Surface across pre-event lookbacks and forward outcome horizons.

Computes a 2D surface:
- X-axis: Lookback offset before event (T-5m, T-15m, T-30m, T-1h, T-2h, T-4h, T-8h, T-12h, T-24h)
- Y-axis: Forward outcome horizon (15m, 30m, 1h, 2h, 4h, 8h, 12h, 24h, 3d, 7d)
- Z-axis: Information metric (Spearman rank correlation, Mutual Information, or Absolute Effect Size)
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.outcomes.continuous import HORIZONS_5M
from coin_behavior_engine.snapshots.extractor import SNAPSHOT_OFFSETS_5M


class InformationDecaySurfaceEngine:
    """Computes information decay grid across lookbacks and forward horizons."""

    def __init__(
        self,
        lookbacks: Dict[str, int] | None = None,
        horizons: Dict[str, int] | None = None,
    ):
        self.lookbacks = lookbacks or SNAPSHOT_OFFSETS_5M
        self.horizons = horizons or HORIZONS_5M

    def compute_decay_surface(
        self,
        df: pd.DataFrame,
        event_indices: List[int],
        feature_name: str = "volatility_compression_ratio",
        target_metric: str = "fwd_abs_ret",  # or fwd_ret, fwd_range
    ) -> pd.DataFrame:
        """
        Compute information metric for (lookback_offset, forward_horizon).
        Returns a pivot DataFrame: rows=horizons, cols=lookbacks.
        """
        if df.empty or not event_indices:
            return pd.DataFrame()

        rows = []
        n_rows = len(df)
        feat_array = df[feature_name].to_numpy() if feature_name in df.columns else np.full(n_rows, np.nan)
        ev_arr = np.array(event_indices, dtype=int)

        for h_label in self.horizons.keys():
            col_target = f"{target_metric}_{h_label}"
            if col_target not in df.columns:
                continue
            targ_array = df[col_target].to_numpy()

            for lb_label, lb_steps in self.lookbacks.items():
                snap_indices = ev_arr - lb_steps
                valid_mask = (
                    (snap_indices >= 0)
                    & (snap_indices < n_rows)
                    & (ev_arr >= 0)
                    & (ev_arr < n_rows)
                )
                valid_snaps = snap_indices[valid_mask]
                valid_evs = ev_arr[valid_mask]

                x_raw = feat_array[valid_snaps]
                y_raw = targ_array[valid_evs]

                finite_mask = np.isfinite(x_raw) & np.isfinite(y_raw)
                x_vals = x_raw[finite_mask]
                y_vals = y_raw[finite_mask]

                if len(x_vals) >= 10:
                    corr, pval = stats.spearmanr(x_vals, y_vals)
                    rows.append({
                        "forward_horizon": h_label,
                        "lookback_offset": lb_label,
                        "lookback_steps": lb_steps,
                        "spearman_corr": round(float(corr), 4),
                        "abs_spearman_corr": round(abs(float(corr)), 4),
                        "p_value": float(pval),
                        "n_samples": len(x_vals),
                    })
                else:
                    rows.append({
                        "forward_horizon": h_label,
                        "lookback_offset": lb_label,
                        "lookback_steps": lb_steps,
                        "spearman_corr": 0.0,
                        "abs_spearman_corr": 0.0,
                        "p_value": 1.0,
                        "n_samples": len(x_vals),
                    })

        res_df = pd.DataFrame(rows)
        return res_df
