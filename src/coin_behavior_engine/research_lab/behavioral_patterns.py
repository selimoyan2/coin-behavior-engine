"""Behavioral Pattern Research Engine.

Sprint 11.05: Verified Market Intelligence & Behavioral Prediction Validation.
Evaluates event-conditioned microstructure patterns:
- PANIC_SELL_CASCADE: Negative news + support breakdown + volatility expansion
- NEGATIVE_NEWS_ABSORPTION: Negative news + support hold + volume absorption
- BULL_TRAP_WEAK_DEMAND: Positive news + resistance test with fading volume
- BEAR_TRAP_LIQUIDITY_SWEEP: Breakdown to new low quickly reclaimed
- V_SHAPED_REBOUND: Oversold plunge followed by immediate reversal bar
- VOLATILITY_EXPANSION_CONTINUATION: Macro event breakout aligned with 4h trend
Strictly requires adequate sample sizes; reports INSUFFICIENT_SAMPLES rather than manufacturing edge.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    BehavioralPatternEvaluationRecord,
    CandleData,
    MarketBehaviorFeatures,
    MarketContextImpact,
    MarketContextTimelineRecord,
    MarketRegimeType,
)

logger = logging.getLogger("cbe_behavioral_patterns")


class BehavioralPatternResearcher:
    """Discovers and empirically verifies event-conditioned market patterns."""

    @classmethod
    def evaluate_all_patterns(
        cls,
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        context_timeline: List[MarketContextTimelineRecord],
    ) -> List[BehavioralPatternEvaluationRecord]:
        """Scan and evaluate all defined behavioral patterns across dataset."""
        n = min(len(candles), len(features), len(context_timeline))
        
        # 1. Identify pattern occurrences
        occurrences: Dict[str, List[int]] = {
            "PANIC_SELL_CASCADE": [],
            "NEGATIVE_NEWS_ABSORPTION": [],
            "BULL_TRAP_WEAK_DEMAND": [],
            "BEAR_TRAP_LIQUIDITY_SWEEP": [],
            "V_SHAPED_REBOUND": [],
            "VOLATILITY_EXPANSION_CONTINUATION": [],
        }

        for i in range(24, n - 48):  # Ensure warmup and forward evaluation window
            c = candles[i]
            f = features[i]
            ctx = context_timeline[i]

            # Pattern 1: PANIC_SELL_CASCADE (Breakdown on negative news)
            if (
                ctx.has_unabsorbed_negative_shock
                and f.regime in [MarketRegimeType.TRENDING_BEAR, MarketRegimeType.CASCADE_LIQUIDATION]
                and f.relative_volume_20 > 1.4
                and c.close < f.rolling_low_24
            ):
                occurrences["PANIC_SELL_CASCADE"].append(i)

            # Pattern 2: NEGATIVE_NEWS_ABSORPTION (Negative news absorbed at support)
            if (
                ctx.dominant_impact == MarketContextImpact.NEGATIVE
                and f.distance_to_support_pct < 0.8
                and (f.price_volume_divergence == "BULLISH_DIV" or ctx.contradiction_detected)
                and c.close >= c.open
            ):
                occurrences["NEGATIVE_NEWS_ABSORPTION"].append(i)

            # Pattern 3: BULL_TRAP_WEAK_DEMAND (Positive catalyst fails at resistance)
            if (
                (ctx.has_positive_catalyst or ctx.net_sentiment_score > 0.25)
                and f.distance_to_resistance_pct < 0.6
                and f.relative_volume_20 < 0.85
                and c.close < c.open
            ):
                occurrences["BULL_TRAP_WEAK_DEMAND"].append(i)

            # Pattern 4: BEAR_TRAP_LIQUIDITY_SWEEP (Quick reclaim of broken support)
            if i >= 3:
                prior_3_lows = [candles[k].low for k in range(i - 3, i)]
                if (
                    min(prior_3_lows) < f.support_zone
                    and c.close > f.support_zone
                    and f.relative_volume_20 > 1.2
                ):
                    occurrences["BEAR_TRAP_LIQUIDITY_SWEEP"].append(i)

            # Pattern 5: V_SHAPED_REBOUND (Sharp plunge followed by full-bar recovery)
            if i >= 3:
                ret_3 = (c.close - candles[i - 3].open) / candles[i - 3].open
                bar_ret = (c.close - c.open) / c.open
                if ret_3 < -0.020 and bar_ret > 0.008 and c.close >= c.high - (c.high - c.low) * 0.15:
                    occurrences["V_SHAPED_REBOUND"].append(i)

            # Pattern 6: VOLATILITY_EXPANSION_CONTINUATION (Breakout aligned with 4h trend on macro event)
            if (
                ctx.active_events_count > 0
                and f.volatility_compression_ratio > 1.15
                and f.is_htf_trend_aligned
                and f.regime in [MarketRegimeType.TRENDING_BULL, MarketRegimeType.TRENDING_BEAR]
            ):
                occurrences["VOLATILITY_EXPANSION_CONTINUATION"].append(i)

        # 2. Evaluate forward outcomes for each pattern
        evaluation_records: List[BehavioralPatternEvaluationRecord] = []

        descriptions = {
            "PANIC_SELL_CASCADE": "Negative news catalyst triggers accelerated breakdown below support with expanding volume.",
            "NEGATIVE_NEWS_ABSORPTION": "Institutional buyers absorb sell orders into negative headlines, stabilizing price above support.",
            "BULL_TRAP_WEAK_DEMAND": "Positive news fails to attract genuine spot demand; distribution at resistance on low volume.",
            "BEAR_TRAP_LIQUIDITY_SWEEP": "Price briefly breaches support to sweep stop-losses before violently reclaiming the range.",
            "V_SHAPED_REBOUND": "Exhaustion selling triggers immediate high-volume green reversal candle.",
            "VOLATILITY_EXPANSION_CONTINUATION": "Macro event catalyst resolves volatility compression in the direction of the 4-hour trend.",
        }

        for p_name, idxs in occurrences.items():
            count = len(idxs)
            if count == 0:
                evaluation_records.append(BehavioralPatternEvaluationRecord(
                    pattern_id=f"PAT-{p_name[:4]}",
                    pattern_name=p_name,
                    sample_count=0,
                    sufficient_evidence=False,
                    win_rate_15m=0.0,
                    expected_return_15m=0.0,
                    win_rate_1h=0.0,
                    expected_return_1h=0.0,
                    win_rate_4h=0.0,
                    expected_return_4h=0.0,
                    failure_rate=0.0,
                    risk_assessment="No empirical samples detected in observation period.",
                    empirical_status="INSUFFICIENT_SAMPLES",
                ))
                continue

            # Directional target: Long for absorption, sweep, rebound, bull continuation; Short for panic cascade, bull trap
            is_bullish_pattern = p_name in [
                "NEGATIVE_NEWS_ABSORPTION",
                "BEAR_TRAP_LIQUIDITY_SWEEP",
                "V_SHAPED_REBOUND",
            ]
            if p_name == "VOLATILITY_EXPANSION_CONTINUATION":
                # Aligned with 4h regime at trigger
                # We measure return in direction of trade
                pass

            rets_15m, rets_1h, rets_4h = [], [], []
            wins_15m, wins_1h, wins_4h = 0, 0, 0
            failures = 0

            for idx in idxs:
                entry_p = candles[idx].close
                p_15m = candles[idx + 3].close
                p_1h = candles[idx + 12].close
                p_4h = candles[idx + 48].close

                # Direction multiplier: +1 for long, -1 for short
                direction = 1.0 if is_bullish_pattern else -1.0
                if p_name == "VOLATILITY_EXPANSION_CONTINUATION":
                    direction = 1.0 if features[idx].regime == MarketRegimeType.TRENDING_BULL else -1.0

                r15 = ((p_15m - entry_p) / entry_p) * 100.0 * direction
                r1h = ((p_1h - entry_p) / entry_p) * 100.0 * direction
                r4h = ((p_4h - entry_p) / entry_p) * 100.0 * direction

                rets_15m.append(r15)
                rets_1h.append(r1h)
                rets_4h.append(r4h)

                if r15 > 0:
                    wins_15m += 1
                if r1h > 0:
                    wins_1h += 1
                if r4h > 0:
                    wins_4h += 1
                if r1h < -0.80:  # Severe stop-out failure
                    failures += 1

            wr_15m = round((wins_15m / count) * 100.0, 1)
            wr_1h = round((wins_1h / count) * 100.0, 1)
            wr_4h = round((wins_4h / count) * 100.0, 1)
            exp_15m = round(sum(rets_15m) / count, 3)
            exp_1h = round(sum(rets_1h) / count, 3)
            exp_4h = round(sum(rets_4h) / count, 3)
            fail_rate = round((failures / count) * 100.0, 1)

            # Determine empirical status
            if count < 5:
                status = "INSUFFICIENT_SAMPLES"
                risk_note = f"Sample count ({count}) is too small to establish statistical significance; treat as unconfirmed hypothesis."
            elif wr_1h > 55.0 and exp_1h > 0.40:
                status = "VALIDATED"
                risk_note = f"Demonstrates positive edge across {count} instances with favorable win rate ({wr_1h}% at 1h)."
            elif wr_1h < 45.0 or exp_1h < 0.0:
                status = "FALSIFIED"
                risk_note = f"Empirical win rate ({wr_1h}%) and negative expectancy ({exp_1h}%) fail to validate profitable edge."
            else:
                status = "INCONCLUSIVE"
                risk_note = f"Moderate win rate ({wr_1h}%) does not overcome execution frictions (0.70% round-trip hurdle)."

            evaluation_records.append(BehavioralPatternEvaluationRecord(
                pattern_id=f"PAT-{p_name[:6]}",
                pattern_name=p_name,
                sample_count=count,
                sufficient_evidence=(count >= 5),
                win_rate_15m=wr_15m,
                expected_return_15m=exp_15m,
                win_rate_1h=wr_1h,
                expected_return_1h=exp_1h,
                win_rate_4h=wr_4h,
                expected_return_4h=exp_4h,
                failure_rate=fail_rate,
                risk_assessment=risk_note,
                empirical_status=status,
            ))

        return evaluation_records

    @classmethod
    def export_pattern_evaluation_csv(
        cls,
        records: List[BehavioralPatternEvaluationRecord],
        output_csv: Path,
    ) -> None:
        """Export behavioral_pattern_evaluation.csv deliverable."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [r.to_dict() for r in records]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)
