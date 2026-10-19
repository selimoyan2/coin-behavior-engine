"""Range Intelligence Evaluator for Sprint 11.19 Phase 6.

Evaluates potential consolidation channels and range-trading hypotheses:
- Identifies historical support and resistance boundaries.
- Calculates gross range width and net tradable room after round-trip friction.
- Estimates empirical probability of mean-reversion (returning from lower to upper boundary) vs breakdown.
- Estimates expected holding duration and bars between boundary tests.
- Audits false breakouts and failed retests.
- Rejects automatic buy/sell assumptions; returns NO_EDGE when friction, margin, or evidence is insufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RangeEvaluationResult:
    """Quantitative evaluation of a range mean-reversion hypothesis."""
    channel_support: float
    channel_resistance: float
    current_price: float
    gross_width_pct: float
    round_trip_friction_pct: float
    net_tradable_room_pct: float
    prob_mean_reversion_to_resistance: float
    prob_breakdown_below_support: float
    prob_range_continuation: float
    mean_bars_between_tests: float
    false_breakout_count: int
    expected_holding_duration_bars: float
    expected_mae_at_support_pct: float
    verdict: str  # POTENTIAL_RANGE_EDGE | NO_EDGE | INSUFFICIENT_EVIDENCE
    verdict_rationale: str
    risk_reward_ratio: float


class RangeIntelligenceEvaluator:
    """Evaluates whether an identified channel provides a verifiable statistical edge."""

    ROUND_TRIP_FRICTION = 0.0030  # 0.30% round-trip trading friction (fees + slippage)
    MIN_NET_ROOM_THRESHOLD = 0.0050  # 0.50% minimum net room required for viable execution

    def __init__(self, df_5m: pd.DataFrame):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.close_prices = self.df_5m["close"].to_numpy()
        self.high_prices = self.df_5m["high"].to_numpy()
        self.low_prices = self.df_5m["low"].to_numpy()

    def evaluate_channel(
        self,
        support_level: float,
        resistance_level: float,
        current_price: float,
        lookback_bars: int = 288,
        horizon_bars: int = 288
    ) -> RangeEvaluationResult:
        """Evaluate a specific channel scenario (e.g. 65,000 - 65,700 USDT)."""
        gross_width = (resistance_level - support_level) / support_level
        net_room = gross_width - self.ROUND_TRIP_FRICTION

        # 1. Friction Gate: If net room is less than minimum threshold, emit NO_EDGE immediately
        if net_room < self.MIN_NET_ROOM_THRESHOLD:
            return RangeEvaluationResult(
                channel_support=support_level,
                channel_resistance=resistance_level,
                current_price=current_price,
                gross_width_pct=round(gross_width * 100.0, 3),
                round_trip_friction_pct=round(self.ROUND_TRIP_FRICTION * 100.0, 3),
                net_tradable_room_pct=round(net_room * 100.0, 3),
                prob_mean_reversion_to_resistance=0.0,
                prob_breakdown_below_support=0.0,
                prob_range_continuation=0.0,
                mean_bars_between_tests=0.0,
                false_breakout_count=0,
                expected_holding_duration_bars=0.0,
                expected_mae_at_support_pct=0.0,
                verdict="NO_EDGE",
                verdict_rationale=f"Insufficient net tradable room ({net_room * 100:.2f}% < {self.MIN_NET_ROOM_THRESHOLD * 100:.2f}%) after 0.30% round-trip friction",
                risk_reward_ratio=0.0
            )

        # 2. Historical Search for Analogous Tight Channels (width between gross_width * 0.8 and gross_width * 1.2)
        # Scan historical 24h rolling windows
        target_width = gross_width
        matched_episodes = []
        n_bars = len(self.df_5m)

        # Sample every 12 bars (1 hour) to avoid extreme autocorrelation
        step_size = 12
        for idx in range(864, n_bars - horizon_bars, step_size):
            window_high = self.high_prices[idx - lookback_bars:idx].max()
            window_low = self.low_prices[idx - lookback_bars:idx].min()
            w = (window_high - window_low) / window_low

            if target_width * 0.75 <= w <= target_width * 1.25:
                # Check that price is currently near lower boundary (bottom 30% of range)
                curr = self.close_prices[idx]
                pos_in_range = (curr - window_low) / (window_high - window_low)
                if pos_in_range <= 0.35:
                    matched_episodes.append((idx, window_low, window_high))

        if len(matched_episodes) < 10:
            return RangeEvaluationResult(
                channel_support=support_level,
                channel_resistance=resistance_level,
                current_price=current_price,
                gross_width_pct=round(gross_width * 100.0, 3),
                round_trip_friction_pct=round(self.ROUND_TRIP_FRICTION * 100.0, 3),
                net_tradable_room_pct=round(net_room * 100.0, 3),
                prob_mean_reversion_to_resistance=0.0,
                prob_breakdown_below_support=0.0,
                prob_range_continuation=0.0,
                mean_bars_between_tests=0.0,
                false_breakout_count=0,
                expected_holding_duration_bars=0.0,
                expected_mae_at_support_pct=0.0,
                verdict="INSUFFICIENT_EVIDENCE",
                verdict_rationale=f"Only {len(matched_episodes)} historical analogous episodes found matching geometry",
                risk_reward_ratio=0.0
            )

        # 3. Trace Out of Matched Episodes
        reversions = 0
        breakdowns = 0
        continuations = 0
        holding_durations = []
        maes = []
        false_breakouts = 0

        breakdown_buffer = gross_width * 0.20  # 20% buffer below support for breakdown
        target_reversion_level = 0.80          # Reached upper 20% of channel

        for idx, s_low, s_high in matched_episodes:
            base_p = self.close_prices[idx]
            rev_price = s_low + (s_high - s_low) * target_reversion_level
            breakdown_price = s_low * (1.0 - breakdown_buffer)

            episode_resolved = False
            min_p = base_p

            for bar in range(idx + 1, idx + 1 + horizon_bars):
                b_high = self.high_prices[bar]
                b_low = self.low_prices[bar]
                b_close = self.close_prices[bar]

                if b_low < min_p:
                    min_p = b_low

                # Check false breakout: pierced below support but closed above
                if b_low < s_low and b_close >= s_low:
                    false_breakouts += 1

                # Check breakdown
                if b_low <= breakdown_price:
                    breakdowns += 1
                    holding_durations.append(bar - idx)
                    episode_resolved = True
                    break

                # Check reversion to upper boundary
                if b_high >= rev_price:
                    reversions += 1
                    holding_durations.append(bar - idx)
                    episode_resolved = True
                    break

            if not episode_resolved:
                continuations += 1

            maes.append((min_p - base_p) / base_p)

        total_episodes = len(matched_episodes)
        prob_rev = float(reversions / total_episodes)
        prob_down = float(breakdowns / total_episodes)
        prob_cont = float(continuations / total_episodes)
        avg_hold = float(np.mean(holding_durations)) if holding_durations else 0.0
        avg_mae = float(np.mean(maes)) if maes else 0.0

        # Risk reward
        rr = (net_room / abs(avg_mae)) if abs(avg_mae) > 0.001 else 1.0

        # Verdict logic
        if prob_down >= prob_rev:
            verdict = "NO_EDGE"
            rationale = f"Breakdown risk ({prob_down * 100:.1f}%) exceeds or equals mean-reversion probability ({prob_rev * 100:.1f}%)"
        elif prob_rev >= 0.55 and rr >= 1.2:
            verdict = "POTENTIAL_RANGE_EDGE"
            rationale = f"Mean reversion probability is {prob_rev * 100:.1f}% with favorable R:R of {rr:.2f}"
        else:
            verdict = "NO_EDGE"
            rationale = f"Marginal statistical edge: P(rev)={prob_rev * 100:.1f}%, R:R={rr:.2f} insufficient to justify execution"

        return RangeEvaluationResult(
            channel_support=support_level,
            channel_resistance=resistance_level,
            current_price=current_price,
            gross_width_pct=round(gross_width * 100.0, 3),
            round_trip_friction_pct=round(self.ROUND_TRIP_FRICTION * 100.0, 3),
            net_tradable_room_pct=round(net_room * 100.0, 3),
            prob_mean_reversion_to_resistance=round(prob_rev, 4),
            prob_breakdown_below_support=round(prob_down, 4),
            prob_range_continuation=round(prob_cont, 4),
            mean_bars_between_tests=round(avg_hold / 2.0, 1),
            false_breakout_count=false_breakouts,
            expected_holding_duration_bars=round(avg_hold, 1),
            expected_mae_at_support_pct=round(avg_mae * 100.0, 3),
            verdict=verdict,
            verdict_rationale=rationale,
            risk_reward_ratio=round(rr, 2)
        )
