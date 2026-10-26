"""
CBE — Regime Episode Forensics Engine
Tarihsel Rejim Bölüm (Episode) İnceleme Laboratuvarı

Provides episode-level segmentation, persistence drilldown, price change,
realized volatility, verified macro event intersections, and bounded paginated
search queries across canonical regime transitions.
Strictly preserves right-censoring without fabricating exit transitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.historical_regime_transition_lab import HistoricalRegimeTransitionLabEngine
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine, MacroEventRecord

DISCLAIMER_TR = (
    "Bu analiz yalnızca tarihsel piyasa davranışı araştırması amacıyla hazırlanmıştır. "
    "Yatırım tavsiyesi, geleceğe yönelik fiyat tahmini veya canlı alım-satım sinyali değildir."
)

FROZEN_MODEL_VERSION = "CBE-0.7.0"


@dataclass
class RegimeEpisodeRecord:
    episode_id: str
    regime_id: str
    regime_label_tr: str
    start_timestamp: str
    end_timestamp: str
    duration_bars: int
    duration_hours: float
    duration_days: float
    entry_transition: Optional[str]
    exit_transition: Optional[str]
    start_price: float
    end_price: float
    price_change_pct: float
    realized_volatility: float
    verified_macro_events: List[Dict[str, Any]]
    source_partition_ids: List[str]
    censoring_status: str  # "COMPLETED" or "RIGHT_CENSORED"
    methodology_version: str = FROZEN_MODEL_VERSION


class RegimeEpisodeForensicsEngine:
    """Historical regime episode forensic segmentation and bounded query engine."""

    _episodes_cache: Optional[List[RegimeEpisodeRecord]] = None
    _episodes_by_id: Optional[Dict[str, RegimeEpisodeRecord]] = None

    @classmethod
    def get_all_episodes(cls) -> List[RegimeEpisodeRecord]:
        """Load, segment, and cache all historical regime episodes from canonical timeline."""
        if cls._episodes_cache is not None:
            return cls._episodes_cache

        df = HistoricalRegimeTransitionLabEngine.load_canonical_timeline()
        if df.empty:
            cls._episodes_cache = []
            cls._episodes_by_id = {}
            return []

        # Load verified macro events for timestamp intersection
        macro_events = MacroEventComparisonEngine.load_events()
        verified_events = [e for e in macro_events if e.verification_status == "VERIFIED_POINT_IN_TIME" and e.release_at_utc]

        event_tuples = []
        for ev in verified_events:
            try:
                ev_dt = datetime.fromisoformat(ev.release_at_utc.replace("Z", "+00:00"))
                event_tuples.append((ev_dt, ev))
            except Exception:
                pass

        regimes = df["regime"].to_numpy()
        dt_strs = df["datetime_utc"].to_numpy()
        closes = df["close_price"].to_numpy()
        n = len(regimes)

        # Detect transition change points
        change_indices = np.where(regimes[:-1] != regimes[1:])[0] + 1
        start_indices = np.concatenate(([0], change_indices))
        end_indices = np.concatenate((change_indices - 1, [n - 1]))

        episodes: List[RegimeEpisodeRecord] = []
        episodes_by_id: Dict[str, RegimeEpisodeRecord] = {}
        total_episodes = len(start_indices)

        for ep_idx in range(total_episodes):
            s_idx = int(start_indices[ep_idx])
            e_idx = int(end_indices[ep_idx])

            reg_id = str(regimes[s_idx])
            reg_label = HistoricalRegimeTransitionLabEngine.REGIME_LABELS_TR.get(reg_id, reg_id)
            start_iso = str(dt_strs[s_idx])
            end_iso = str(dt_strs[e_idx])

            bars = e_idx - s_idx + 1
            # In canonical timeline, interval is 5m (5/60 = 0.08333h)
            hours = round(bars * (5.0 / 60.0), 4)
            days = round(hours / 24.0, 4)

            # Entry transition: regime of previous episode
            entry_tr = str(regimes[s_idx - 1]) if s_idx > 0 else None

            # Exit transition: None if right-censored, else regime of next episode
            is_censored = (ep_idx == total_episodes - 1)
            exit_tr = None if is_censored else str(regimes[e_idx + 1])
            censoring_status = "RIGHT_CENSORED" if is_censored else "COMPLETED"

            p_start = float(closes[s_idx])
            p_end = float(closes[e_idx])
            price_chg = round(((p_end - p_start) / p_start) * 100.0, 4) if p_start > 0 else 0.0

            # Realized volatility within episode
            if bars >= 2:
                ep_closes = closes[s_idx : e_idx + 1]
                log_rets = np.diff(np.log(ep_closes))
                # Annualized from 5m bars: 105,120 5m bars per year
                vol = float(np.std(log_rets) * np.sqrt(105120))
                vol = round(vol, 4) if not math.isnan(vol) else 0.0
            else:
                vol = 0.0

            # Find verified macro events within [start_iso, end_iso]
            associated_events = []
            try:
                dt_start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                dt_end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                for ev_dt, ev in event_tuples:
                    if dt_start <= ev_dt <= dt_end:
                        associated_events.append({
                            "event_id": ev.event_id,
                            "event_name": ev.event_name,
                            "category": ev.event_category,
                            "release_at_utc": ev.release_at_utc,
                            "surprise_status": ev.surprise_status,
                        })
            except Exception:
                pass

            # Safe logical partition IDs
            months = set()
            try:
                months.add(start_iso[:7])
                months.add(end_iso[:7])
            except Exception:
                months.add("2026-UNKNOWN")
            source_partitions = [f"BTCUSDT-5m-{m}.parquet" for m in sorted(months)]

            ep_clean_date = start_iso.replace("-", "").replace(":", "").replace("T", "")[:12]
            episode_id = f"EP-{reg_id[:3]}-{ep_clean_date}-{ep_idx + 1:05d}"

            rec = RegimeEpisodeRecord(
                episode_id=episode_id,
                regime_id=reg_id,
                regime_label_tr=reg_label,
                start_timestamp=start_iso,
                end_timestamp=end_iso,
                duration_bars=bars,
                duration_hours=hours,
                duration_days=days,
                entry_transition=entry_tr,
                exit_transition=exit_tr,
                start_price=p_start,
                end_price=p_end,
                price_change_pct=price_chg,
                realized_volatility=vol,
                verified_macro_events=associated_events,
                source_partition_ids=source_partitions,
                censoring_status=censoring_status,
                methodology_version=FROZEN_MODEL_VERSION,
            )
            episodes.append(rec)
            episodes_by_id[episode_id] = rec

        cls._episodes_cache = episodes
        cls._episodes_by_id = episodes_by_id
        return episodes

    @classmethod
    def get_episode_by_id(cls, episode_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve single episode by unique ID."""
        cls.get_all_episodes()
        if cls._episodes_by_id and episode_id in cls._episodes_by_id:
            return asdict(cls._episodes_by_id[episode_id])
        return None

    @classmethod
    def query_episodes(
        cls,
        regime: Optional[str] = None,
        year: Optional[int] = None,
        min_duration_hours: Optional[float] = None,
        max_duration_hours: Optional[float] = None,
        min_volatility: Optional[float] = None,
        max_volatility: Optional[float] = None,
        has_macro_event: Optional[bool] = None,
        macro_category: Optional[str] = None,
        censoring_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Execute bounded, paginated search queries across historical regime episodes.
        """
        all_eps = cls.get_all_episodes()
        page = max(1, page)
        page_size = max(1, min(page_size, 200))  # Bounded to max 200 items per page

        filtered: List[RegimeEpisodeRecord] = []

        for ep in all_eps:
            if regime and regime != "ALL" and ep.regime_id != regime:
                continue

            if year is not None:
                try:
                    ep_year = int(ep.start_timestamp[:4])
                    if ep_year != year:
                        continue
                except Exception:
                    continue

            if min_duration_hours is not None and ep.duration_hours < min_duration_hours:
                continue
            if max_duration_hours is not None and ep.duration_hours > max_duration_hours:
                continue

            if min_volatility is not None and ep.realized_volatility < min_volatility:
                continue
            if max_volatility is not None and ep.realized_volatility > max_volatility:
                continue

            if has_macro_event is not None:
                has_events = len(ep.verified_macro_events) > 0
                if has_events != has_macro_event:
                    continue

            if macro_category and macro_category != "ALL":
                cats = [e.get("category") for e in ep.verified_macro_events]
                if macro_category not in cats:
                    continue

            if censoring_status and censoring_status != "ALL":
                if ep.censoring_status != censoring_status:
                    continue

            filtered.append(ep)

        total_count = len(filtered)
        total_pages = max(1, math.ceil(total_count / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_records = filtered[start_idx:end_idx]

        # Aggregate summary statistics for filtered population
        durations = [e.duration_hours for e in filtered]
        vols = [e.realized_volatility for e in filtered]
        macro_intersect_count = sum(1 for e in filtered if len(e.verified_macro_events) > 0)
        censored_count = sum(1 for e in filtered if e.censoring_status == "RIGHT_CENSORED")

        summary_stats = {
            "total_episodes_matched": total_count,
            "mean_duration_hours": round(float(np.mean(durations)), 4) if durations else 0.0,
            "median_duration_hours": round(float(np.median(durations)), 4) if durations else 0.0,
            "max_duration_hours": round(float(np.max(durations)), 4) if durations else 0.0,
            "mean_realized_volatility": round(float(np.mean(vols)), 4) if vols else 0.0,
            "macro_event_associated_count": macro_intersect_count,
            "right_censored_count": censored_count,
        }

        return {
            "status": "SUCCESS",
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "summary_stats": summary_stats,
            "episodes": [asdict(e) for e in paged_records],
            "disclaimer_tr": DISCLAIMER_TR,
        }
