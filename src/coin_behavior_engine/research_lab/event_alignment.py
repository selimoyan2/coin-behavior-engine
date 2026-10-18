"""Time-aware event alignment and market impact measurement engine.

Sprint 11.03: Market Behavior Research Lab.
Aligns timestamped events with market candle timelines to compute pre- and post-event
abnormal returns across multiple horizons (-5m, +1m, +5m, +15m, +60m, +4h, +24h).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    EventIntelligenceRecord,
)


@dataclass
class EventAlignmentResult:
    event_id: str
    category: str
    headline: str
    published_at_utc: str
    first_observed_at_utc: str
    event_severity: float
    direction_hypothesis: str
    candle_ts_event: int
    price_at_event: float
    price_pre_5m: Optional[float] = None
    price_post_1m: Optional[float] = None
    price_post_5m: Optional[float] = None
    price_post_15m: Optional[float] = None
    price_post_60m: Optional[float] = None
    price_post_4h: Optional[float] = None
    price_post_24h: Optional[float] = None
    return_pre_5m_pct: Optional[float] = None
    return_post_1m_pct: Optional[float] = None
    return_post_5m_pct: Optional[float] = None
    return_post_15m_pct: Optional[float] = None
    return_post_60m_pct: Optional[float] = None
    return_post_4h_pct: Optional[float] = None
    return_post_24h_pct: Optional[float] = None
    market_reaction_assessment: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category,
            "headline": self.headline,
            "published_at_utc": self.published_at_utc,
            "first_observed_at_utc": self.first_observed_at_utc,
            "event_severity": self.event_severity,
            "direction_hypothesis": self.direction_hypothesis,
            "price_at_event": self.price_at_event,
            "return_pre_5m_pct": self.return_pre_5m_pct,
            "return_post_5m_pct": self.return_post_5m_pct,
            "return_post_15m_pct": self.return_post_15m_pct,
            "return_post_60m_pct": self.return_post_60m_pct,
            "return_post_4h_pct": self.return_post_4h_pct,
            "return_post_24h_pct": self.return_post_24h_pct,
            "market_reaction_assessment": self.market_reaction_assessment,
        }


class EventMarketAligner:
    """Measures price reactions surrounding discrete market intelligence events."""

    @classmethod
    def align_events(
        cls,
        events: List[EventIntelligenceRecord],
        candles: List[CandleData],
    ) -> List[EventAlignmentResult]:
        """Align each event with candle timeline and calculate multi-horizon reactions."""
        if not candles:
            return []

        # Build fast timestamp index of closed candles
        ts_map: Dict[int, CandleData] = {c.timestamp_open: c for c in candles}
        candle_ts_list = sorted(ts_map.keys())
        alignments: List[EventAlignmentResult] = []

        for evt in events:
            # Parse event epoch ms
            try:
                dt_evt = datetime.fromisoformat(evt.published_at_utc.replace("Z", "+00:00"))
                evt_ms = int(dt_evt.timestamp() * 1000)
            except Exception:
                continue

            # Find closest candle timestamp at or immediately following event publication
            eligible_ts = [ts for ts in candle_ts_list if ts >= evt_ms]
            if not eligible_ts:
                continue
            event_candle_ts = eligible_ts[0]
            event_candle = ts_map[event_candle_ts]
            p_event = event_candle.close

            # Target timestamps
            ts_pre_5m = event_candle_ts - 300_000
            ts_post_1m = event_candle_ts + 60_000
            ts_post_5m = event_candle_ts + 300_000
            ts_post_15m = event_candle_ts + 900_000
            ts_post_60m = event_candle_ts + 3_600_000
            ts_post_4h = event_candle_ts + 14_400_000
            ts_post_24h = event_candle_ts + 86_400_000

            def get_price_near(target_ts: int) -> Optional[float]:
                c = ts_map.get(target_ts)
                if c:
                    return c.close
                # Search nearest within 2-minute tolerance
                near = [ts for ts in candle_ts_list if abs(ts - target_ts) <= 120_000]
                if near:
                    return ts_map[near[0]].close
                return None

            p_pre_5m = get_price_near(ts_pre_5m)
            p_post_1m = get_price_near(ts_post_1m)
            p_post_5m = get_price_near(ts_post_5m)
            p_post_15m = get_price_near(ts_post_15m)
            p_post_60m = get_price_near(ts_post_60m)
            p_post_4h = get_price_near(ts_post_4h)
            p_post_24h = get_price_near(ts_post_24h)

            def calc_ret(p: Optional[float]) -> Optional[float]:
                if p is not None and p_event > 0:
                    return round(((p - p_event) / p_event) * 100.0, 4)
                return None

            def calc_pre_ret(p: Optional[float]) -> Optional[float]:
                if p is not None and p > 0:
                    return round(((p_event - p) / p) * 100.0, 4)
                return None

            ret_pre_5m = calc_pre_ret(p_pre_5m)
            ret_post_1m = calc_ret(p_post_1m)
            ret_post_5m = calc_ret(p_post_5m)
            ret_post_15m = calc_ret(p_post_15m)
            ret_post_60m = calc_ret(p_post_60m)
            ret_post_4h = calc_ret(p_post_4h)
            ret_post_24h = calc_ret(p_post_24h)

            # Classify observed market reaction
            assessment = "NEUTRAL_RESPONSE"
            if ret_post_60m is not None:
                if ret_post_60m < -1.0:
                    assessment = "STRONG_NEGATIVE_REACTION" if evt.event_direction_hypothesis == "BEARISH" else "SURPRISE_SELLOFF"
                elif ret_post_60m > 1.0:
                    assessment = "STRONG_POSITIVE_REACTION" if evt.event_direction_hypothesis == "BULLISH" else "SURPRISE_RALLY"
                elif abs(ret_post_60m) < 0.2:
                    assessment = "MARKET_ABSORBED_MINIMAL_IMPACT"

            # Update event record in-place for downstream features
            evt.abnormal_return_5m_post = ret_post_5m
            evt.abnormal_return_60m_post = ret_post_60m
            evt.observed_market_impact = assessment

            res = EventAlignmentResult(
                event_id=evt.event_id,
                category=evt.category.value,
                headline=evt.headline,
                published_at_utc=evt.published_at_utc,
                first_observed_at_utc=evt.first_observed_at_utc,
                event_severity=evt.event_severity,
                direction_hypothesis=evt.event_direction_hypothesis,
                candle_ts_event=event_candle_ts,
                price_at_event=p_event,
                price_pre_5m=p_pre_5m,
                price_post_1m=p_post_1m,
                price_post_5m=p_post_5m,
                price_post_15m=p_post_15m,
                price_post_60m=p_post_60m,
                price_post_4h=p_post_4h,
                price_post_24h=p_post_24h,
                return_pre_5m_pct=ret_pre_5m,
                return_post_1m_pct=ret_post_1m,
                return_post_5m_pct=ret_post_5m,
                return_post_15m_pct=ret_post_15m,
                return_post_60m_pct=ret_post_60m,
                return_post_4h_pct=ret_post_4h,
                return_post_24h_pct=ret_post_24h,
                market_reaction_assessment=assessment,
            )
            alignments.append(res)

        return alignments

    @classmethod
    def export_event_timeline_csv(
        cls,
        alignments: List[EventAlignmentResult],
        output_csv: Path,
    ) -> None:
        """Export aligned event timeline to CSV."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [a.to_dict() for a in alignments]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)
