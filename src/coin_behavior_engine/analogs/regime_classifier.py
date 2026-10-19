"""Point-in-Time Market Regime Classifier for Sprint 11.19.

Classifies market state into:
- TREND_UP
- TREND_DOWN
- RANGE
- HIGH_VOLATILITY
- UNCERTAIN

Strict Invariants:
1. Evaluates exclusively on past information (t <= T_0). Zero future return leakage.
2. Distinguishes genuine sideways range from temporary pauses inside strong macro trends.
3. Provides reproducible classification logic with continuous confidence score [0.0, 1.0].
4. Evaluates forward transition probabilities (Breakout Up, Breakdown Down, Remained Intact).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.analogs.feature_store import FeatureVector


@dataclass(frozen=True)
class RegimeDecision:
    """Regime classification outcome at decision moment T_0."""
    regime: str
    confidence: float
    is_genuine_range: bool
    is_trend_pause: bool
    rationale: str
    key_metrics: Dict[str, float]


class MarketRegimeClassifier:
    """Classifies market regime point-in-time and audits range resolution dynamics."""

    REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "UNCERTAIN"]

    def __init__(
        self,
        high_vol_atr_threshold: float = 0.008,     # 0.8% 5m ATR
        high_vol_ann_threshold: float = 1.00,      # 100% annualized 24h volatility
        trend_strength_threshold: float = 1.0,     # EMA separation > 1x ATR
        range_max_width_pct: float = 0.045,        # 24h range width < 4.5%
        min_boundary_tests: int = 2                # At least 2 touches of support and resistance
    ):
        self.high_vol_atr_threshold = high_vol_atr_threshold
        self.high_vol_ann_threshold = high_vol_ann_threshold
        self.trend_strength_threshold = trend_strength_threshold
        self.range_max_width_pct = range_max_width_pct
        self.min_boundary_tests = min_boundary_tests

    def classify(self, fv: FeatureVector) -> RegimeDecision:
        """Point-in-time regime classification for a single FeatureVector."""
        if not fv.is_valid_window:
            return RegimeDecision(
                regime="UNCERTAIN",
                confidence=0.50,
                is_genuine_range=False,
                is_trend_pause=False,
                rationale=f"Invalid feature window: {fv.rejection_reason}",
                key_metrics={"atr_pct": fv.atr_5m_pct, "trend_strength": fv.trend_strength}
            )

        # 1. High Volatility Check
        if fv.atr_5m_pct >= self.high_vol_atr_threshold or fv.realized_vol_24h >= self.high_vol_ann_threshold:
            conf = min(0.95, 0.65 + (fv.atr_5m_pct / self.high_vol_atr_threshold - 1.0) * 0.3)
            return RegimeDecision(
                regime="HIGH_VOLATILITY",
                confidence=round(conf, 4),
                is_genuine_range=False,
                is_trend_pause=False,
                rationale=f"ATR% ({fv.atr_5m_pct:.4f}) or 24h realized vol ({fv.realized_vol_24h:.2f}) exceeds extreme boundary",
                key_metrics={"atr_pct": fv.atr_5m_pct, "realized_vol_24h": fv.realized_vol_24h}
            )

        # 2. Trend Up Check
        is_trend_up = (
            fv.trend_strength >= self.trend_strength_threshold
            and fv.trend_persistence_4h >= 0.65
            and fv.ret_24h > 0.01
            and fv.drawdown_high_24h >= -0.035
        )
        if is_trend_up:
            conf = min(0.95, 0.60 + (fv.trend_strength / 3.0) * 0.25 + fv.trend_persistence_4h * 0.15)
            return RegimeDecision(
                regime="TREND_UP",
                confidence=round(conf, 4),
                is_genuine_range=False,
                is_trend_pause=False,
                rationale=f"Consistent bullish momentum: trend_strength={fv.trend_strength:.2f}, persistence={fv.trend_persistence_4h:.2f}",
                key_metrics={"trend_strength": fv.trend_strength, "ret_24h": fv.ret_24h, "persistence": fv.trend_persistence_4h}
            )

        # 3. Trend Down Check
        is_trend_down = (
            fv.trend_strength <= -self.trend_strength_threshold
            and fv.trend_persistence_4h <= 0.35
            and fv.ret_24h < -0.01
            and fv.recovery_low_24h <= 0.035
        )
        if is_trend_down:
            conf = min(0.95, 0.60 + (abs(fv.trend_strength) / 3.0) * 0.25 + (1.0 - fv.trend_persistence_4h) * 0.15)
            return RegimeDecision(
                regime="TREND_DOWN",
                confidence=round(conf, 4),
                is_genuine_range=False,
                is_trend_pause=False,
                rationale=f"Consistent bearish momentum: trend_strength={fv.trend_strength:.2f}, persistence={fv.trend_persistence_4h:.2f}",
                key_metrics={"trend_strength": fv.trend_strength, "ret_24h": fv.ret_24h, "persistence": fv.trend_persistence_4h}
            )

        # 4. Range Check
        is_range_candidate = (
            abs(fv.trend_strength) <= 0.85
            and fv.range_width_pct_24h <= self.range_max_width_pct
            and abs(fv.ret_24h) <= 0.02
            and fv.support_tests_24h >= self.min_boundary_tests
            and fv.resistance_tests_24h >= self.min_boundary_tests
        )

        if is_range_candidate:
            # Check if this is a temporary consolidation pause inside a strong macro move
            is_macro_pause = abs(fv.ret_72h) >= 0.06
            conf = 0.80 if not is_macro_pause else 0.62
            return RegimeDecision(
                regime="RANGE",
                confidence=conf,
                is_genuine_range=not is_macro_pause,
                is_trend_pause=is_macro_pause,
                rationale="Established 24h horizontal boundaries with repeated support/resistance touches" + (" (Macro trend pause)" if is_macro_pause else " (Genuine range)"),
                key_metrics={
                    "range_width_pct": fv.range_width_pct_24h,
                    "support_tests": fv.support_tests_24h,
                    "resistance_tests": fv.resistance_tests_24h,
                    "ret_72h": fv.ret_72h
                }
            )

        # 5. Default: Uncertain / Chop
        return RegimeDecision(
            regime="UNCERTAIN",
            confidence=0.55,
            is_genuine_range=False,
            is_trend_pause=False,
            rationale="Conflicting momentum, intermediate volatility, or lack of established boundary structure",
            key_metrics={"trend_strength": fv.trend_strength, "range_width": fv.range_width_pct_24h}
        )

    def analyze_range_breakout_statistics(
        self,
        df_5m: pd.DataFrame,
        sample_indices: List[int],
        forward_horizon_bars: int = 288  # 24 hours
    ) -> Dict[str, Any]:
        """Measure historically how identified ranges later resolved over forward_horizon_bars."""
        breakout_up = 0
        breakdown_down = 0
        remained_intact = 0
        total_ranges = len(sample_indices)

        if total_ranges == 0:
            return {
                "total_ranges_evaluated": 0,
                "breakout_up_rate": 0.0,
                "breakdown_down_rate": 0.0,
                "remained_intact_rate": 0.0
            }

        high_arr = df_5m["high"].to_numpy()
        low_arr = df_5m["low"].to_numpy()
        close_arr = df_5m["close"].to_numpy()
        n_bars = len(df_5m)

        for idx in sample_indices:
            if idx + forward_horizon_bars >= n_bars or idx < 288:
                continue

            # 24h established range bounds at idx
            r_high = high_arr[idx - 288:idx].max()
            r_low = low_arr[idx - 288:idx].min()
            buffer = (r_high - r_low) * 0.10  # 10% breakout threshold buffer

            fwd_high = high_arr[idx + 1:idx + 1 + forward_horizon_bars].max()
            fwd_low = low_arr[idx + 1:idx + 1 + forward_horizon_bars].min()

            broke_up = fwd_high > (r_high + buffer)
            broke_down = fwd_low < (r_low - buffer)

            if broke_up and not broke_down:
                breakout_up += 1
            elif broke_down and not broke_up:
                breakdown_down += 1
            elif broke_up and broke_down:
                # Determine which was touched first
                up_first = False
                for step in range(idx + 1, idx + 1 + forward_horizon_bars):
                    if high_arr[step] > (r_high + buffer):
                        up_first = True
                        break
                    elif low_arr[step] < (r_low - buffer):
                        up_first = False
                        break
                if up_first:
                    breakout_up += 1
                else:
                    breakdown_down += 1
            else:
                remained_intact += 1

        evaluated = breakout_up + breakdown_down + remained_intact
        return {
            "total_ranges_evaluated": evaluated,
            "breakout_up_count": breakout_up,
            "breakdown_down_count": breakdown_down,
            "remained_intact_count": remained_intact,
            "breakout_up_rate_pct": round((breakout_up / evaluated) * 100.0, 2) if evaluated else 0.0,
            "breakdown_down_rate_pct": round((breakdown_down / evaluated) * 100.0, 2) if evaluated else 0.0,
            "remained_intact_rate_pct": round((remained_intact / evaluated) * 100.0, 2) if evaluated else 0.0
        }
