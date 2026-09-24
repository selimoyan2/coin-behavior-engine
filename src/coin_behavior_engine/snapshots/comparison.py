"""Statistical comparison between pre-event snapshots and matched controls.

Computes:
- Cohen's d effect size
- Two-sample Kolmogorov-Smirnov test (D, p-value)
- Percentile distributions (p10, p50, p90)
- Distribution divergence metrics
"""

from __future__ import annotations

from typing import Dict, List, Any
import numpy as np
import pandas as pd
from scipy import stats

from coin_behavior_engine.utils.logging import logger


def compute_cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d effect size between two independent samples."""
    g1 = group1[~np.isnan(group1)]
    g2 = group2[~np.isnan(group2)]
    if len(g1) < 2 or len(g2) < 2:
        return 0.0

    n1, n2 = len(g1), len(g2)
    s1, s2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    pooled_se = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))

    if pooled_se == 0 or np.isnan(pooled_se):
        return 0.0

    return float((np.mean(g1) - np.mean(g2)) / pooled_se)


class SnapshotStatisticalComparator:
    """Compares feature values between pre-event snapshot windows and matched control windows."""

    def __init__(self, feature_cols: List[str] | None = None):
        self.feature_cols = feature_cols

    def compare_feature(
        self,
        event_vals: np.ndarray,
        control_vals: np.ndarray,
    ) -> Dict[str, Any]:
        """Perform full statistical battery on a single feature comparing event vs control."""
        ev = event_vals[~np.isnan(event_vals)]
        ct = control_vals[~np.isnan(control_vals)]

        if len(ev) < 5 or len(ct) < 5:
            return {
                "n_event": len(ev),
                "n_control": len(ct),
                "cohens_d": np.nan,
                "ks_stat": np.nan,
                "ks_pvalue": np.nan,
                "event_mean": np.nan,
                "control_mean": np.nan,
                "event_median": np.nan,
                "control_median": np.nan,
                "shift_direction": "INSUFFICIENT_DATA",
            }

        d = compute_cohens_d(ev, ct)
        ks_res = stats.ks_2samp(ev, ct)

        e_mean = float(np.mean(ev))
        c_mean = float(np.mean(ct))
        e_med = float(np.median(ev))
        c_med = float(np.median(ct))

        direction = "NEUTRAL"
        if abs(d) >= 0.2:
            direction = "HIGHER_PRE_EVENT" if d > 0 else "LOWER_PRE_EVENT"

        return {
            "n_event": len(ev),
            "n_control": len(ct),
            "cohens_d": round(d, 4),
            "ks_stat": round(float(ks_res.statistic), 4),
            "ks_pvalue": float(ks_res.pvalue),
            "is_significant_p01": bool(ks_res.pvalue < 0.01),
            "event_mean": round(e_mean, 4),
            "control_mean": round(c_mean, 4),
            "event_median": round(e_med, 4),
            "control_median": round(c_med, 4),
            "event_p10": round(float(np.percentile(ev, 10)), 4),
            "event_p90": round(float(np.percentile(ev, 90)), 4),
            "control_p10": round(float(np.percentile(ct, 10)), 4),
            "control_p90": round(float(np.percentile(ct, 90)), 4),
            "shift_direction": direction,
        }

    def compare_all_snapshots(
        self,
        event_snapshots_by_offset: Dict[str, pd.DataFrame],
        control_snapshots_by_offset: Dict[str, pd.DataFrame],
        feature_cols: List[str],
    ) -> pd.DataFrame:
        """
        Compare all features across all snapshot horizons.
        Returns tabular summary suitable for reports and CSV output.
        """
        records = []
        for offset_name, ev_df in event_snapshots_by_offset.items():
            ct_df = control_snapshots_by_offset.get(offset_name)
            if ct_df is None or ct_df.empty:
                continue

            for feat in feature_cols:
                if feat not in ev_df.columns or feat not in ct_df.columns:
                    continue

                stats_dict = self.compare_feature(
                    ev_df[feat].to_numpy(dtype=float),
                    ct_df[feat].to_numpy(dtype=float),
                )
                stats_dict["offset"] = offset_name
                stats_dict["feature"] = feat
                records.append(stats_dict)

        df_res = pd.DataFrame(records)
        return df_res
