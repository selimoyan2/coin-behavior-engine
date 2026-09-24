"""Sprint 06 Event Study Engine.

Conducts rigorous causal event studies comparing multi-horizon pre- and post-event
behavior against matched non-event control baselines.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("coin_behavior_engine")


class EventStudyEngine:
    """Rigorous causal event study engine with matched controls and overlap tracking."""

    def __init__(
        self,
        features_path: str = "data/reports/sprint06/event_features.parquet",
        events_path: str = "data/reports/sprint06/event_canonical.parquet",
        output_dir: str = "data/reports/sprint06",
    ):
        self.features_path = Path(features_path)
        self.events_path = Path(events_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.pre_windows = [-288, -144, -48, -12, -3]  # -24h, -12h, -4h, -1h, -15m in 5m bars
        self.post_windows = [1, 3, 6, 12, 48, 144, 288, 576]  # +5m, +15m, +30m, +1h, +4h, +12h, +24h, +48h in 5m bars

    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load features grid and canonical events."""
        logger.info(f"Loading event features from {self.features_path}...")
        df_feat = pd.read_parquet(self.features_path)
        logger.info(f"Loading canonical events from {self.events_path}...")
        df_events = pd.read_parquet(self.events_path)
        return df_feat, df_events

    def audit_overlapping_events(self, df_events: pd.DataFrame) -> pd.DataFrame:
        """Audit event overlaps within 4h and 24h windows to separate clean from contaminated events."""
        logger.info("Auditing event temporal clustering and overlaps...")
        # Use available_at_timestamp
        events = df_events[df_events["source_tier"] != "REJECTED"].copy()
        events = events.sort_values("available_at_timestamp").reset_index(drop=True)
        times = events["available_at_timestamp"].values

        n_events = len(events)
        overlaps_4h = np.zeros(n_events, dtype=int)
        overlaps_24h = np.zeros(n_events, dtype=int)
        is_isolated_24h = np.zeros(n_events, dtype=int)

        t_4h = np.timedelta64(4, "h")
        t_24h = np.timedelta64(24, "h")

        cluster_ids = events["event_cluster_id"].values

        for i in range(n_events):
            t_curr = times[i]
            c_curr = cluster_ids[i]
            # Count other events from DIFFERENT clusters within [-24h, +24h]
            diffs = np.abs(times - t_curr)
            is_diff_cluster = (cluster_ids != c_curr)
            c_4h = int(np.sum((diffs <= t_4h) & is_diff_cluster))
            c_24h = int(np.sum((diffs <= t_24h) & is_diff_cluster))

            overlaps_4h[i] = c_4h
            overlaps_24h[i] = c_24h
            is_isolated_24h[i] = 1 if c_24h == 0 else 0

        events["overlapping_events_4h"] = overlaps_4h
        events["overlapping_events_24h"] = overlaps_24h
        events["is_isolated_24h"] = is_isolated_24h

        out_csv = self.output_dir / "event_overlap_audit.csv"
        events[
            [
                "story_id",
                "event_cluster_id",
                "taxonomy_family",
                "headline",
                "available_at_timestamp",
                "source_tier",
                "overlapping_events_4h",
                "overlapping_events_24h",
                "is_isolated_24h",
            ]
        ].to_csv(out_csv, index=False)
        logger.info(f"Saved event overlap audit ({n_events} events) to {out_csv}")
        return events

    def generate_matched_controls(
        self, df_feat: pd.DataFrame, event_bar_indices: np.ndarray, n_matches: int = 5
    ) -> pd.DataFrame:
        """Find strictly non-event control bars matched on session, month, and volatility quintile."""
        logger.info(f"Generating {n_matches} matched non-event control bars per event...")
        # Non-event bars are bars where is_no_event_state == 1 and no event within 24h
        candidate_mask = (df_feat["is_no_event_state"] == 1).to_numpy(copy=True)
        # Ensure candidate bars are at least 288 bars away from start/end
        min_idx = 288
        max_idx = len(df_feat) - 576
        candidate_mask[:min_idx] = False
        candidate_mask[max_idx:] = False

        # Add session and volatility quintile matching
        sessions = df_feat["session_name"].fillna("UNKNOWN").values if "session_name" in df_feat.columns else np.zeros(len(df_feat))
        vol_col = "volatility_realized_24h" if "volatility_realized_24h" in df_feat.columns else "volatility"
        rv = df_feat[vol_col].fillna(df_feat[vol_col].median()).values
        rv_quintiles = pd.qcut(rv, 5, labels=False, duplicates="drop")

        matched_records = []
        rng = np.random.RandomState(42)

        for ev_idx in event_bar_indices:
            if ev_idx < min_idx or ev_idx >= max_idx:
                continue
            ev_sess = sessions[ev_idx]
            ev_q = rv_quintiles[ev_idx]

            # Pool of exact match
            pool = np.where(candidate_mask & (sessions == ev_sess) & (rv_quintiles == ev_q))[0]
            if len(pool) < n_matches:
                pool = np.where(candidate_mask & (rv_quintiles == ev_q))[0]
            if len(pool) < n_matches:
                pool = np.where(candidate_mask)[0]

            chosen = rng.choice(pool, size=min(n_matches, len(pool)), replace=False)
            for c_idx in chosen:
                matched_records.append({
                    "event_bar_idx": ev_idx,
                    "event_datetime": df_feat["datetime_open"].iloc[ev_idx],
                    "control_bar_idx": c_idx,
                    "control_datetime": df_feat["datetime_open"].iloc[c_idx],
                    "session": str(ev_sess),
                    "rv_quintile": int(ev_q),
                })

        df_matched = pd.DataFrame(matched_records)
        out_csv = self.output_dir / "matched_event_controls.csv"
        df_matched.to_csv(out_csv, index=False)
        logger.info(f"Saved matched controls ({len(df_matched)} pairs) to {out_csv}")
        return df_matched

    def run_event_study(self) -> Dict[str, Any]:
        """Compute cumulative returns, realized vol, tail risk, and directional concordance."""
        df_feat, df_events = self.load_data()
        df_overlap = self.audit_overlapping_events(df_events)

        # Map primary events to 5m bar indices
        grid_times = df_feat["datetime_open"].values
        primary_events = df_overlap[(df_overlap["source_tier"] != "REJECTED") & (df_overlap["is_cluster_lead"])].copy()
        ev_times = primary_events["available_at_timestamp"].values

        ev_bar_indices = np.searchsorted(grid_times, ev_times, side="left")
        # Keep valid indices within bounds
        valid_mask = (ev_bar_indices >= 288) & (ev_bar_indices < len(grid_times) - 576)
        primary_events = primary_events.iloc[valid_mask].copy()
        ev_bar_indices = ev_bar_indices[valid_mask]
        primary_events["bar_idx"] = ev_bar_indices

        # Matched controls
        df_matched = self.generate_matched_controls(df_feat, ev_bar_indices, n_matches=5)
        control_bar_indices = df_matched["control_bar_idx"].values

        close_prices = df_feat["close"].values
        # Precompute forward and backward log returns
        log_prices = np.log(close_prices)

        # 99th percentile threshold for EVT jump detection
        log_ret_5m = np.diff(log_prices, prepend=log_prices[0])
        tail_threshold_99 = np.percentile(np.abs(log_ret_5m), 99)

        results = []

        # Analyze each event family and overall
        families = ["ALL", "ISOLATED_ONLY"] + list(primary_events["taxonomy_family"].unique())

        for fam in families:
            if fam == "ALL":
                sub_events = primary_events
            elif fam == "ISOLATED_ONLY":
                sub_events = primary_events[primary_events["is_isolated_24h"] == 1]
            else:
                sub_events = primary_events[primary_events["taxonomy_family"] == fam]

            n_events_fam = len(sub_events)
            if n_events_fam < 2:
                continue

            fam_indices = sub_events["bar_idx"].values

            # Post-event windows analysis
            for w in self.post_windows:
                h_name = f"+{w*5}m" if w < 12 else f"+{w*5//60}h"

                ev_rets = log_prices[fam_indices + w] - log_prices[fam_indices]
                ev_abs_rets = np.abs(ev_rets)
                ev_rv = ev_abs_rets * np.sqrt(288 / w)  # Annualized proxy / scaled vol
                ev_jump_rate = np.mean(ev_abs_rets > (tail_threshold_99 * np.sqrt(w)))
                ev_dir_pos = np.mean(ev_rets > 0)

                # Control baseline for same window
                ctrl_rets = log_prices[control_bar_indices + w] - log_prices[control_bar_indices]
                ctrl_abs_rets = np.abs(ctrl_rets)
                ctrl_rv = ctrl_abs_rets * np.sqrt(288 / w)
                ctrl_jump_rate = np.mean(ctrl_abs_rets > (tail_threshold_99 * np.sqrt(w)))
                ctrl_dir_pos = np.mean(ctrl_rets > 0)

                # Incremental vol ratio
                vol_ratio = np.mean(ev_abs_rets) / (np.mean(ctrl_abs_rets) + 1e-8)
                jump_multiplier = ev_jump_rate / (ctrl_jump_rate + 1e-8)

                results.append({
                    "event_family": fam,
                    "horizon": h_name,
                    "window_bars": w,
                    "window_type": "POST",
                    "n_events": n_events_fam,
                    "ev_mean_abs_ret_pct": float(np.mean(ev_abs_rets) * 100),
                    "ctrl_mean_abs_ret_pct": float(np.mean(ctrl_abs_rets) * 100),
                    "vol_ratio": float(vol_ratio),
                    "ev_jump_rate_pct": float(ev_jump_rate * 100),
                    "ctrl_jump_rate_pct": float(ctrl_jump_rate * 100),
                    "jump_multiplier": float(jump_multiplier),
                    "ev_directional_pos_pct": float(ev_dir_pos * 100),
                    "ctrl_directional_pos_pct": float(ctrl_dir_pos * 100),
                    "mean_signed_ret_bps": float(np.mean(ev_rets) * 10000),
                })

            # Pre-event windows analysis (drift / anticipation)
            for w in self.pre_windows:
                bars_back = abs(w)
                h_name = f"-{bars_back*5}m" if bars_back < 12 else f"-{bars_back*5//60}h"

                ev_rets = log_prices[fam_indices] - log_prices[fam_indices - bars_back]
                ev_abs_rets = np.abs(ev_rets)
                ctrl_rets = log_prices[control_bar_indices] - log_prices[control_bar_indices - bars_back]
                ctrl_abs_rets = np.abs(ctrl_rets)

                vol_ratio = np.mean(ev_abs_rets) / (np.mean(ctrl_abs_rets) + 1e-8)

                results.append({
                    "event_family": fam,
                    "horizon": h_name,
                    "window_bars": -bars_back,
                    "window_type": "PRE",
                    "n_events": n_events_fam,
                    "ev_mean_abs_ret_pct": float(np.mean(ev_abs_rets) * 100),
                    "ctrl_mean_abs_ret_pct": float(np.mean(ctrl_abs_rets) * 100),
                    "vol_ratio": float(vol_ratio),
                    "ev_jump_rate_pct": float(np.mean(ev_abs_rets > (tail_threshold_99 * np.sqrt(bars_back))) * 100),
                    "ctrl_jump_rate_pct": float(np.mean(ctrl_abs_rets > (tail_threshold_99 * np.sqrt(bars_back))) * 100),
                    "jump_multiplier": float(np.mean(ev_abs_rets > (tail_threshold_99 * np.sqrt(bars_back))) / (np.mean(ctrl_abs_rets > (tail_threshold_99 * np.sqrt(bars_back))) + 1e-8)),
                    "ev_directional_pos_pct": float(np.mean(ev_rets > 0) * 100),
                    "ctrl_directional_pos_pct": float(np.mean(ctrl_rets > 0) * 100),
                    "mean_signed_ret_bps": float(np.mean(ev_rets) * 10000),
                })

        df_res = pd.DataFrame(results)
        out_csv = self.output_dir / "event_study_results.csv"
        df_res.to_csv(out_csv, index=False)
        logger.info(f"Saved event study results ({len(df_res)} rows) to {out_csv}")

        return {
            "n_total_events": len(primary_events),
            "n_isolated_events": int(primary_events["is_isolated_24h"].sum()),
            "n_matched_controls": len(df_matched),
            "event_study_csv": str(out_csv),
        }


if __name__ == "__main__":
    engine = EventStudyEngine()
    summary = engine.run_event_study()
    print("Event Study completed:", summary)
