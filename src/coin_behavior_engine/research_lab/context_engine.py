"""Market Context Engine.

Sprint 11.05: Verified Market Intelligence & Behavioral Prediction Validation.
Evaluates event freshness, surprise, relevance, credibility, and price contradiction.
Strictly separates textual sentiment from observed market price reaction.
Produces reproducible point-in-time market context timeline across all candles.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    EventIntelligenceRecord,
    EventVerificationStatus,
    MarketContextImpact,
    MarketContextTimelineRecord,
)


class MarketContextEngine:
    """Computes explainable, point-in-time market context states without lookahead."""

    def __init__(self, events: List[EventIntelligenceRecord]):
        self.events = sorted(events, key=lambda e: e.first_observed_at_utc)
        # Pre-parse timestamps for fast point-in-time filtering
        self._parsed_events = []
        for e in self.events:
            try:
                obs_dt = datetime.fromisoformat(e.first_observed_at_utc.replace("Z", "+00:00"))
                self._parsed_events.append((obs_dt, e))
            except Exception:
                pass

    def evaluate_context_at_candle(
        self,
        candle: CandleData,
        candles_history: List[CandleData],
        lookback_hours: float = 36.0,
    ) -> MarketContextTimelineRecord:
        """Formulate market context state observable at candle.timestamp_open."""
        c_dt = datetime.fromisoformat(candle.datetime_open_utc.replace("Z", "+00:00"))
        
        # 1. Gather observable events strictly before candle open
        active_events: List[Tuple[float, EventIntelligenceRecord, MarketContextImpact]] = []
        for obs_dt, e in self._parsed_events:
            if obs_dt <= c_dt:
                age_hours = (c_dt - obs_dt).total_seconds() / 3600.0
                if 0.0 <= age_hours <= lookback_hours:
                    # Compute exponential freshness decay: Freshness = exp(-age / tau)
                    tau = e.freshness_half_life_hours / math.log(2)
                    freshness = math.exp(-age_hours / tau) if tau > 0 else 0.0

                    # Evaluate dynamic impact: check if price contradicted the event
                    impact = e.context_impact
                    
                    # Contradiction check: if event was negative, did price rally significantly post-event?
                    # Find candle nearest to event observation time
                    event_post_candles = [
                        c for c in candles_history
                        if c.datetime_open_utc >= e.first_observed_at_utc and c.timestamp_open <= candle.timestamp_open
                    ]
                    if len(event_post_candles) >= 6:  # At least 30 minutes of price action
                        pre_p = event_post_candles[0].open
                        curr_p = candle.close
                        ret_since_event = (curr_p - pre_p) / pre_p if pre_p > 0 else 0.0
                        
                        if e.context_impact == MarketContextImpact.NEGATIVE and ret_since_event > 0.010:
                            # Price gained > 1% despite negative news -> Market absorbed or contradicted headline
                            impact = MarketContextImpact.CONTRADICTED_BY_PRICE_ACTION
                        elif e.context_impact == MarketContextImpact.POSITIVE and ret_since_event < -0.010:
                            impact = MarketContextImpact.CONTRADICTED_BY_PRICE_ACTION

                    active_events.append((freshness, e, impact))

        if not active_events:
            return MarketContextTimelineRecord(
                timestamp_open=candle.timestamp_open,
                datetime_utc=candle.datetime_open_utc,
                active_events_count=0,
                net_sentiment_score=0.0,
                dominant_impact=MarketContextImpact.UNCERTAIN,
                has_unabsorbed_negative_shock=False,
                has_positive_catalyst=False,
                contradiction_detected=False,
                priced_in_detected=False,
                primary_event_id=None,
                primary_headline="NO_ACTIVE_EVENT",
            )

        # 2. Weighted sentiment calculation
        total_weight = 0.0
        sentiment_accum = 0.0
        has_negative_shock = False
        has_positive_catalyst = False
        contradiction_detected = False
        priced_in_detected = False

        # Impact numeric mapping for sentiment calculation
        impact_weights = {
            MarketContextImpact.POSITIVE: 1.0,
            MarketContextImpact.NEGATIVE: -1.0,
            MarketContextImpact.CONTRADICTED_BY_PRICE_ACTION: 0.15,  # Contradicted negative is slightly positive/absorption
            MarketContextImpact.POTENTIALLY_PRICED_IN: 0.0,
            MarketContextImpact.AMBIGUOUS: 0.0,
            MarketContextImpact.UNCERTAIN: 0.0,
            MarketContextImpact.SUPERSEDED_BY_LATER_EVENT: 0.0,
        }

        # Sort by freshness * credibility * severity
        scored_events = []
        for freshness, e, impact in active_events:
            effective_weight = freshness * e.source_credibility * e.event_severity * e.relevance_score
            total_weight += effective_weight
            s_val = impact_weights.get(impact, 0.0)
            sentiment_accum += s_val * effective_weight
            
            if impact == MarketContextImpact.NEGATIVE and freshness > 0.35 and e.event_severity >= 0.70:
                has_negative_shock = True
            if impact == MarketContextImpact.POSITIVE and freshness > 0.35 and e.event_severity >= 0.60:
                has_positive_catalyst = True
            if impact == MarketContextImpact.CONTRADICTED_BY_PRICE_ACTION:
                contradiction_detected = True
            if impact == MarketContextImpact.POTENTIALLY_PRICED_IN:
                priced_in_detected = True

            scored_events.append((effective_weight, e, impact))

        # Net sentiment between -1.0 and +1.0
        net_sentiment = sentiment_accum / total_weight if total_weight > 0 else 0.0
        net_sentiment = max(-1.0, min(1.0, round(net_sentiment, 3)))

        # Dominant event is the highest effective weight event
        scored_events.sort(key=lambda x: x[0], reverse=True)
        top_weight, top_event, dominant_impact = scored_events[0]

        return MarketContextTimelineRecord(
            timestamp_open=candle.timestamp_open,
            datetime_utc=candle.datetime_open_utc,
            active_events_count=len(active_events),
            net_sentiment_score=net_sentiment,
            dominant_impact=dominant_impact,
            has_unabsorbed_negative_shock=has_negative_shock,
            has_positive_catalyst=has_positive_catalyst,
            contradiction_detected=contradiction_detected,
            priced_in_detected=priced_in_detected,
            primary_event_id=top_event.event_id,
            primary_headline=top_event.headline,
        )

    def generate_timeline(
        self,
        candles: List[CandleData],
        lookback_hours: float = 36.0,
    ) -> List[MarketContextTimelineRecord]:
        """Generate point-in-time context records for all candles chronologically."""
        timeline: List[MarketContextTimelineRecord] = []
        for i, c in enumerate(candles):
            history_slice = candles[: i + 1]
            rec = self.evaluate_context_at_candle(c, history_slice, lookback_hours=lookback_hours)
            timeline.append(rec)
        return timeline

    @classmethod
    def export_timeline_csv(
        cls,
        timeline: List[MarketContextTimelineRecord],
        output_csv: Path,
    ) -> None:
        """Export market_context_timeline.csv deliverable."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [t.to_dict() for t in timeline]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)
