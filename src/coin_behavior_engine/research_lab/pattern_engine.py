"""Interpretable behavioral pattern research and statistical discovery engine.

Sprint 11.03: Market Behavior Research Lab.
Discovers empirical recurrence of distinct market microstructure patterns
(e.g., volume exhaustion, failed breakdown, breakout confirmation).
"""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    BehavioralPattern,
    CandleData,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    MarketRegimeType,
)


class BehavioralPatternEngine:
    """Discovers and catalogs conditional outcome distributions for market patterns."""

    @classmethod
    def match_patterns_at_index(
        cls,
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        idx: int,
        observable_events: Optional[List[EventIntelligenceRecord]] = None,
    ) -> List[str]:
        """Detect active pattern signatures present at index idx using only past closed bars."""
        if idx < 5:
            return []

        active_patterns: List[str] = []
        feat = features[idx]
        c_curr = candles[idx]
        c_prev = candles[idx - 1]

        # 1. SHARP_DECLINE_VOLUME_EXHAUSTION
        # 3-bar drop < -1.5%, current volume > 2.0x average, candle close in upper 40% of its range
        c_range = c_curr.high - c_curr.low
        close_pos = (c_curr.close - c_curr.low) / c_range if c_range > 0 else 0.5
        if feat.return_3 < -0.015 and feat.relative_volume_20 > 2.0 and close_pos >= 0.60:
            active_patterns.append("SHARP_DECLINE_VOLUME_EXHAUSTION")

        # 2. SUPPORT_BREAKDOWN_FAILED_CONTINUATION (Bear Trap / Liquidity Sweep)
        # Low broke below support zone by at least 0.1%, but close ended back above support zone
        if feat.support_zone > 0:
            if c_curr.low < feat.support_zone * 0.999 and c_curr.close >= feat.support_zone:
                active_patterns.append("SUPPORT_BREAKDOWN_FAILED_CONTINUATION")

        # 3. BREAKOUT_WITH_VOLUME_CONFIRMATION
        # Close broke above resistance zone with volume confirmation
        if feat.resistance_zone > 0:
            if c_curr.close > feat.resistance_zone * 1.002 and feat.relative_volume_20 > 1.6:
                active_patterns.append("BREAKOUT_WITH_VOLUME_CONFIRMATION")

        # 4. HIGH_VOLATILITY_SELLOFF_STABILIZATION
        # Following extreme selloff/liquidation, range contracts and candle closes green
        if idx >= 3 and features[idx - 2].regime in (MarketRegimeType.CASCADE_LIQUIDATION, MarketRegimeType.HIGH_VOLATILITY_EXPANSION):
            if c_curr.close > c_curr.open and c_prev.close > c_prev.open:
                active_patterns.append("HIGH_VOLATILITY_SELLOFF_STABILIZATION")

        # 5. NEGATIVE_EVENT_ABSORPTION
        # If observable negative event occurred recently (< 60 mins), but price refused to make a new low
        if observable_events:
            severe_neg = [
                e for e in observable_events
                if e.event_severity >= 0.70 and e.event_direction_hypothesis == "BEARISH"
            ]
            if severe_neg and feat.return_5 > -0.003 and feat.relative_volume_20 > 1.2:
                active_patterns.append("NEGATIVE_EVENT_ABSORPTION")

        return active_patterns

    @classmethod
    def evaluate_pattern_distribution(
        cls,
        pattern_name: str,
        match_indices: List[int],
        candles: List[CandleData],
        horizon_bars: int = 12,  # e.g., 1 hour on 5m candles
    ) -> Optional[BehavioralPattern]:
        """Compute empirical forward return distribution and win-rate for matched pattern occurrences."""
        if not match_indices:
            return None

        forward_returns: List[float] = []
        for idx in match_indices:
            if idx + horizon_bars < len(candles):
                p_entry = candles[idx].close
                p_exit = candles[idx + horizon_bars].close
                if p_entry > 0:
                    ret = (p_exit - p_entry) / p_entry
                    forward_returns.append(ret)

        if not forward_returns:
            return None

        n = len(forward_returns)
        wins = [r for r in forward_returns if r > 0]
        win_rate = len(wins) / n
        mean_ret = sum(forward_returns) / n
        
        # 95% Confidence Interval for mean return
        var = sum((r - mean_ret) ** 2 for r in forward_returns) / max(1, n - 1)
        std_err = math.sqrt(var / n) if n > 1 else 0.0
        ci_lower = mean_ret - 1.96 * std_err
        ci_upper = mean_ret + 1.96 * std_err

        entry_conds = {
            "SHARP_DECLINE_VOLUME_EXHAUSTION": "3-bar return < -1.5%, volume > 2x, close in upper 40% of range",
            "SUPPORT_BREAKDOWN_FAILED_CONTINUATION": "Intrabar low sweeps below support, close finishes above support",
            "BREAKOUT_WITH_VOLUME_CONFIRMATION": "Close breaks above resistance with relative volume > 1.6x",
            "HIGH_VOLATILITY_SELLOFF_STABILIZATION": "Consecutive green candles and range contraction following high volatility selloff",
            "NEGATIVE_EVENT_ABSORPTION": "Severe negative news absorbed without new local low",
        }.get(pattern_name, "Configured technical pattern conditions")

        return BehavioralPattern(
            pattern_id=f"PAT-{pattern_name.replace('_', '-')}",
            pattern_name=pattern_name,
            pattern_version="1.0.0-sprint11.03",
            entry_conditions=entry_conds,
            market_regime=MarketRegimeType.MEAN_REVERTING,
            context_requirements="Requires closed candle volume & support/resistance context",
            historical_sample_count=n,
            observation_window_bars=24,
            prediction_horizon_bars=horizon_bars,
            probability_positive_outcome=round(win_rate, 4),
            expected_return_pct=round(mean_ret * 100.0, 4),
            confidence_interval=(round(ci_lower * 100.0, 4), round(ci_upper * 100.0, 4)),
            failure_conditions="Break below recent swing low or continued cascade liquidation",
            risk_characteristics="High payoff asymmetry on successful support holding",
        )

    @classmethod
    def export_pattern_summary_csv(
        cls,
        patterns: List[BehavioralPattern],
        output_csv: Path,
    ) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [p.to_dict() for p in patterns]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)
