"""Multi-timeframe event linkage: associating events across 5m, 15m, 1h, 4h, 1d."""

from __future__ import annotations

from typing import Any, Dict, List
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime


class MultiTimeframeLinker:
    """Links overlapping events across multiple timeframes into unified global events."""

    def __init__(self, tolerance_minutes: int = 30):
        self.tolerance_ms = tolerance_minutes * 60 * 1000

    def link_events(
        self,
        events_by_tf: Dict[str, pd.DataFrame]
    ) -> tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Cluster events from multiple timeframes based on temporal overlap / proximity.
        Returns:
            global_events_df: Unified multi-timeframe events
            updated_events_by_tf: Individual timeframe events updated with global_event_id
        """
        all_events = []
        for tf, ev_df in events_by_tf.items():
            if ev_df.empty:
                continue
            copied = ev_df.copy()
            copied["origin_tf"] = tf
            all_events.append(copied)

        if not all_events:
            return pd.DataFrame(), events_by_tf

        combined = pd.concat(all_events, ignore_index=True)
        # Sort chronologically by timestamp_open, then descending by event_score
        combined = combined.sort_values(by=["timestamp_open", "event_score"], ascending=[True, False]).reset_index(drop=True)

        global_events: List[Dict[str, Any]] = []
        child_links: Dict[str, str] = {}  # local_event_id -> global_event_id

        # Cluster events
        active_cluster: List[pd.Series] = []

        for _, row in combined.iterrows():
            if not active_cluster:
                active_cluster.append(row)
                continue

            last_open = min(r["timestamp_open"] for r in active_cluster)
            last_close = max(r["timestamp_close"] for r in active_cluster)

            curr_open = row["timestamp_open"]

            # If current event opens within tolerance of active cluster
            if curr_open <= last_close + self.tolerance_ms:
                active_cluster.append(row)
            else:
                # Flush active cluster
                gev = self._form_global_event(active_cluster, len(global_events) + 1)
                global_events.append(gev)
                for r in active_cluster:
                    child_links[r["event_id"]] = gev["global_event_id"]

                active_cluster = [row]

        if active_cluster:
            gev = self._form_global_event(active_cluster, len(global_events) + 1)
            global_events.append(gev)
            for r in active_cluster:
                child_links[r["event_id"]] = gev["global_event_id"]

        global_df = pd.DataFrame(global_events)

        # Update original event dataframes with global_event_id
        updated_dict = {}
        for tf, ev_df in events_by_tf.items():
            if ev_df.empty:
                updated_dict[tf] = ev_df
                continue
            copied = ev_df.copy()
            copied["global_event_id"] = copied["event_id"].map(child_links)
            updated_dict[tf] = copied

        logger.info(f"Multi-timeframe linkage complete: formed {len(global_df)} global events.")
        return global_df, updated_dict

    def _form_global_event(self, cluster: List[pd.Series], index: int) -> Dict[str, Any]:
        """Aggregate a cluster of timeframe observations into a single global event."""
        cluster_df = pd.DataFrame(cluster)
        gid = f"GEV_{index:04d}"

        start_ts = int(cluster_df["timestamp_open"].min())
        end_ts = int(cluster_df["timestamp_close"].max())
        max_score = float(cluster_df["event_score"].max())

        # Highest scoring observation dictates primary classification
        best_row = cluster_df.sort_values("event_score", ascending=False).iloc[0]
        primary_type = str(best_row["event_type"])

        participating_tfs = sorted(list(cluster_df["origin_tf"].unique()))
        child_ids = list(cluster_df["event_id"])

        return {
            "global_event_id": gid,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "start_utc": str(to_utc_datetime(start_ts)),
            "end_utc": str(to_utc_datetime(end_ts)),
            "duration_minutes": int((end_ts - start_ts) / 60_000),
            "primary_event_type": primary_type,
            "max_event_score": round(max_score, 4),
            "participating_timeframes": participating_tfs,
            "timeframe_count": len(participating_tfs),
            "child_event_ids": child_ids,
            "max_abs_return": round(float(cluster_df["return_simple"].abs().max()), 5),
            "regime_context": str(best_row.get("regime_during", "UNKNOWN")),
        }
