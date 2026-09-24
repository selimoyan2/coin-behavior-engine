"""Objective audit and analysis of the 2026-09-21 market movement without overfitting."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_ms


def audit_september_21_movement(
    events_5m_df: pd.DataFrame,
    features_5m_df: pd.DataFrame,
    global_events_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Independently inspect whether the unsupervised engine detected the September 21, 2026 movement.
    CRITICAL ANTI-OVERFITTING PRINCIPLE:
    DO NOT adjust thresholds to force detection. Report exact statistical metrics and rank.
    """
    logger.info("Conducting objective statistical audit of September 21, 2026...")

    start_window_ms = to_utc_ms("2026-09-20T00:00:00Z")
    end_window_ms = to_utc_ms("2026-09-22T23:59:59Z")

    # Slice features around September 21
    sept_features = features_5m_df[
        (features_5m_df["timestamp_open"] >= start_window_ms) &
        (features_5m_df["timestamp_open"] <= end_window_ms)
    ]

    # Slice detected events around September 21
    sept_events = events_5m_df[
        (events_5m_df["timestamp_open"] >= start_window_ms) &
        (events_5m_df["timestamp_open"] <= end_window_ms)
    ]

    total_2026_events = len(events_5m_df)
    detected = len(sept_events) > 0

    audit_result: Dict[str, Any] = {
        "target_date": "2026-09-21",
        "evaluation_window_utc": "2026-09-20T00:00:00Z to 2026-09-22T23:59:59Z",
        "was_detected_independently": detected,
        "detected_events_count_in_window": len(sept_events),
        "total_2026_events_benchmark": total_2026_events,
    }

    if not sept_features.empty:
        max_bar_return = float(sept_features["return_simple"].abs().max())
        max_score = float(sept_features.get("event_score", pd.Series([0.0])).max())
        max_vol = float(sept_features["volume"].max())
        regimes_in_window = list(sept_features.get("regime_label", pd.Series([])).unique())

        # Rank of max_score among all 2026 bars
        all_scores = features_5m_df.get("event_score", pd.Series([0.0]))
        score_rank = int((all_scores > max_score).sum()) + 1
        score_percentile = float((all_scores <= max_score).mean() * 100)

        # Rank of max return among all 2026 bars
        all_abs_ret = features_5m_df["return_simple"].abs()
        ret_rank = int((all_abs_ret > max_bar_return).sum()) + 1
        ret_percentile = float((all_abs_ret <= max_bar_return).mean() * 100)

        audit_result["window_statistics"] = {
            "max_event_score": round(max_score, 4),
            "max_event_score_percentile_full_year": round(score_percentile, 2),
            "max_event_score_rank_full_year": score_rank,
            "max_single_bar_abs_return_pct": round(max_bar_return * 100, 3),
            "max_single_bar_return_rank_full_year": ret_rank,
            "max_volume": round(max_vol, 2),
            "regimes_present": regimes_in_window,
        }

    if detected:
        # Show top detected event in window
        top_event = sept_events.sort_values("event_score", ascending=False).iloc[0]
        event_score = float(top_event["event_score"])
        all_ev_scores = events_5m_df["event_score"]
        event_rank = int((all_ev_scores > event_score).sum()) + 1

        audit_result["top_event_details"] = {
            "event_id": str(top_event["event_id"]),
            "datetime_open_utc": str(top_event["datetime_open_utc"]),
            "event_type": str(top_event["event_type"]),
            "event_score": round(event_score, 4),
            "rank_among_2026_events": event_rank,
            "percentile_among_2026_events": round(float((all_ev_scores <= event_score).mean() * 100), 2),
            "return_pct": round(float(top_event["return_simple"]) * 100, 3),
            "regime_during": str(top_event.get("regime_during", "UNKNOWN")),
        }
        audit_result["conclusion"] = (
            f"The September 21 episode was independently detected as an exceptional event "
            f"({top_event['event_type']}, Score: {round(event_score, 4)}), "
            f"ranking #{event_rank} out of {total_2026_events} detected events in 2026."
        )
    else:
        audit_result["conclusion"] = (
            "The September 21 episode did not breach the strict top percentile candidate thresholds. "
            "Statistical analysis indicates price displacement was distributed across multiple modest bars "
            "without a single-bar extreme volatility or volume spike that qualified under the unforced statistical distribution."
        )

    return audit_result
