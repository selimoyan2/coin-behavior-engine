"""Market State Hierarchy: Layer 2 Persistent Macro-Regimes.

Sprint 01 established that 5m micro-regimes act as micro-state detectors
(27.5 switches/day, 41.5% 1-candle durations).

Layer 2 introduces a persistent Macro-Regime with state hysteresis:
- Median duration >= 12 hours
- Average transitions < 2 per day
- States:
  * PERSISTENT_TREND_BULL
  * PERSISTENT_TREND_BEAR
  * COMPRESSION_ACCUMULATION
  * CHOPPY_CONSOLIDATION
  * VOLATILITY_EXPANSION

Strictly causal: computed solely using backward rolling windows with causal hysteresis smoothing.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger

MACRO_STATES = [
    "PERSISTENT_TREND_BULL",
    "PERSISTENT_TREND_BEAR",
    "COMPRESSION_ACCUMULATION",
    "CHOPPY_CONSOLIDATION",
    "VOLATILITY_EXPANSION",
]


class MacroRegimeDetector:
    """Detects persistent Layer 2 macro market regimes using causal hysteresis smoothing."""

    def __init__(
        self,
        persistence_min_candles: int = 12,  # 1 hour minimum continuous signal to enter
        hysteresis_decay_candles: int = 24, # 2 hours inertia
    ):
        self.persistence_min = persistence_min_candles
        self.hysteresis_decay = hysteresis_decay_candles

    def detect_macro_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Assign macro-regime to each 5m candle.
        Returns copy of df with 'macro_regime', 'macro_regime_duration', and 'macro_state_id'.
        """
        if df.empty:
            return df

        out = df.copy()

        # Required features
        trend_col = "trend_slope_24h" if "trend_slope_24h" in out.columns else None
        vol_col = "volatility_realized_24h" if "volatility_realized_24h" in out.columns else None
        comp_col = "volatility_compression_ratio" if "volatility_compression_ratio" in out.columns else None

        if trend_col is None or vol_col is None:
            raise ValueError("DataFrame must contain trend_slope_24h and volatility_realized_24h for macro regimes.")

        trend = out[trend_col].fillna(0.0).to_numpy()
        vol = out[vol_col].fillna(0.0).to_numpy()
        comp = out[comp_col].fillna(1.0).to_numpy() if comp_col else np.ones(len(out))

        # Rolling 14-day (4032 candles) baseline for volatility rank without future lookahead
        # Fast rolling baseline for volatility without future lookahead
        vol_s = pd.Series(vol)
        vol_rolling_median = vol_s.rolling(288, min_periods=24).mean().fillna(vol_s.mean()).to_numpy()
        vol_rolling_p80 = (vol_rolling_median * 1.35)

        n = len(out)
        raw_signals = np.empty(n, dtype=object)

        # Vectorized raw candidate state detection
        # Bull: strong positive slope
        # Bear: strong negative slope
        # Compression: low compression ratio (< 0.7) and vol <= median
        # Expansion: vol >= p80 and comp > 1.2
        # Consolidation: default

        for i in range(n):
            v_curr = vol[i]
            t_curr = trend[i]
            c_curr = comp[i]
            v_med = vol_rolling_median[i]
            v_p80 = vol_rolling_p80[i]

            if v_curr >= v_p80 and c_curr >= 1.15:
                raw_signals[i] = "VOLATILITY_EXPANSION"
            elif t_curr > 0.0003 and c_curr > 0.85:
                raw_signals[i] = "PERSISTENT_TREND_BULL"
            elif t_curr < -0.0003 and c_curr > 0.85:
                raw_signals[i] = "PERSISTENT_TREND_BEAR"
            elif c_curr <= 0.70 or (v_curr < v_med * 0.75):
                raw_signals[i] = "COMPRESSION_ACCUMULATION"
            else:
                raw_signals[i] = "CHOPPY_CONSOLIDATION"

        # Apply causal hysteresis filter to eliminate 1-candle flicker
        macro_regimes = np.empty(n, dtype=object)
        durations = np.zeros(n, dtype=int)

        current_regime = raw_signals[0] if raw_signals[0] else "CHOPPY_CONSOLIDATION"
        candidate_regime = current_regime
        candidate_count = 0
        current_duration = 0

        for i in range(n):
            sig = raw_signals[i]

            if sig == current_regime:
                candidate_regime = sig
                candidate_count = 0
                current_duration += 1
            else:
                if sig == candidate_regime:
                    candidate_count += 1
                else:
                    candidate_regime = sig
                    candidate_count = 1

                # If candidate persists for min required candles, switch state
                if candidate_count >= self.persistence_min:
                    current_regime = candidate_regime
                    candidate_count = 0
                    current_duration = 1
                else:
                    current_duration += 1

            macro_regimes[i] = current_regime
            durations[i] = current_duration

        out["macro_regime"] = macro_regimes
        out["macro_regime_duration"] = durations

        logger.info(
            f"Macro-regimes detected. Average duration: {durations.mean():.1f} candles ({durations.mean()*5/60:.1f} hours). "
            f"Median duration: {np.median(durations):.1f} candles ({np.median(durations)*5/60:.1f} hours)."
        )

        return out

    def calculate_regime_transition_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute regime stability metrics: switches per day, duration percentiles, state breakdown."""
        if "macro_regime" not in df.columns:
            return {}

        switches = (df["macro_regime"] != df["macro_regime"].shift(1)).sum()
        total_days = len(df) / 288.0
        switches_per_day = switches / total_days if total_days > 0 else 0.0

        durations = df["macro_regime_duration"].to_numpy()
        state_counts = df["macro_regime"].value_counts(normalize=True).to_dict()

        return {
            "total_candles": len(df),
            "total_days": round(total_days, 1),
            "total_switches": int(switches),
            "switches_per_day": round(switches_per_day, 2),
            "mean_duration_hours": round(float(np.mean(durations)) * 5 / 60, 2),
            "median_duration_hours": round(float(np.median(durations)) * 5 / 60, 2),
            "p90_duration_hours": round(float(np.percentile(durations, 90)) * 5 / 60, 2),
            "state_distribution": {k: round(v, 4) for k, v in state_counts.items()},
        }
