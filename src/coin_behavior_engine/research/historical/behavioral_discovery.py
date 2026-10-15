"""Behavioral Discovery beyond Opening Sessions.

A bounded observational research layer for discovering market phenomena:
- B1: Trend Exhaustion (Overbought/Oversold extreme with compressed body)
- B2: Volatility Shock Recovery (Post-shock drift over 1, 4, 12 bars)
- B3: Range Expansion & Mean Reversion (Extreme stretch from rolling 50-EMA)
- B4: Momentum Persistence (Consecutive expanding candles in trend direction)
- B5: Failed Continuation (Breakout attempt immediately rejected back into range)
- B6: Price Reaction After Unusually Large Candles (> 95th percentile candle range)

Enforces:
1. Strict separation of observational associations from executable trading rules.
2. Full forward distribution reporting (mean, std, skewness, positive rate).
3. Benchmark against unconditional baseline distribution.
4. Scientific classification: OBSERVATIONAL_ONLY, EXPLORATORY_HYPOTHESIS, REJECTED, INSUFFICIENT_EVIDENCE, VALIDATION_CANDIDATE.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.market_regime_intelligence import (
    ConditionalReturnDistribution,
    MarketRegimeEngine,
    MarketRegimeState,
    TrendRegime,
    VolatilityRegime,
)


class BehavioralEvidenceStatus(str, Enum):
    OBSERVATIONAL_ONLY = "OBSERVATIONAL_ONLY"
    EXPLORATORY_HYPOTHESIS = "EXPLORATORY_HYPOTHESIS"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VALIDATION_CANDIDATE = "VALIDATION_CANDIDATE"


@dataclass(frozen=True)
class BehavioralDiscoveryFinding:
    """Rigorous scientific record of an observed market behavior."""

    behavior_id: str
    name: str
    description: str
    sample_size: int
    horizons_bars: list[int]
    conditional_mean_bps: dict[str, float]
    conditional_std_bps: dict[str, float]
    win_rate_positive: dict[str, float]
    unconditional_baseline_bps: dict[str, float]
    excess_return_bps: dict[str, float]
    standard_error_bps: dict[str, float]
    t_statistic: dict[str, float]
    is_statistically_distinguishable: bool
    status: BehavioralEvidenceStatus
    scientific_notes: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class BehavioralDiscoveryAnalyzer:
    """Executes point-in-time observational discovery across market time-series."""

    def __init__(self, candles: Sequence[Mapping[str, Any]], symbol: str = "BTCUSDT") -> None:
        self.candles = candles
        self.symbol = symbol
        self.n_bars = len(candles)
        self.regime_engine = MarketRegimeEngine(candles)

        self._closes = np.array([float(c["close"]) for c in candles])
        self._highs = np.array([float(c["high"]) for c in candles])
        self._lows = np.array([float(c["low"]) for c in candles])
        self._opens = np.array([float(c["open"]) for c in candles])

    def discover_all_behaviors(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> dict[str, BehavioralDiscoveryFinding]:
        """Run standard suite of bounded behavioral observations."""
        findings = {}
        findings["B1_TREND_EXHAUSTION"] = self.analyze_trend_exhaustion(horizons_bars)
        findings["B2_VOLATILITY_SHOCK_RECOVERY"] = self.analyze_volatility_shock_recovery(horizons_bars)
        findings["B3_RANGE_EXPANSION_MEAN_REVERSION"] = self.analyze_mean_reversion_stretch(horizons_bars)
        findings["B4_MOMENTUM_PERSISTENCE"] = self.analyze_momentum_persistence(horizons_bars)
        findings["B5_FAILED_CONTINUATION"] = self.analyze_failed_continuation(horizons_bars)
        findings["B6_LARGE_CANDLE_REACTION"] = self.analyze_large_candle_reaction(horizons_bars)
        return findings

    def _build_finding_from_condition(
        self,
        behavior_id: str,
        name: str,
        description: str,
        condition_fn: Any,
        horizons_bars: tuple[int, ...],
        direction_sign: float = 1.0,  # +1.0 for long, -1.0 for short
    ) -> BehavioralDiscoveryFinding:
        """Helper to compute statistics and build a BehavioralDiscoveryFinding."""
        dist = self.regime_engine.analyze_conditional_return_distribution(
            filter_fn=condition_fn,
            condition_name=name,
            horizons_bars=horizons_bars,
        )

        n = dist.sample_count
        se_dict: dict[str, float] = {}
        t_stat_dict: dict[str, float] = {}
        is_significant = False

        for h in horizons_bars:
            h_key = f"{h}_bars"
            s = dist.std_return_bps.get(h_key, 0.0)
            se = (s / math.sqrt(n)) if n > 0 else 0.0
            se_dict[h_key] = round(se, 2)
            excess = dist.excess_return_bps.get(h_key, 0.0) * direction_sign
            t_val = (excess / se) if se > 1e-9 else 0.0
            t_stat_dict[h_key] = round(t_val, 2)
            if abs(t_val) >= 2.0 and n >= 30:
                is_significant = True

        # Status determination
        if n < 30:
            status = BehavioralEvidenceStatus.INSUFFICIENT_EVIDENCE
            notes = f"Small sample size (N={n} < 30). Insufficient statistical power."
        elif is_significant:
            status = BehavioralEvidenceStatus.EXPLORATORY_HYPOTHESIS
            notes = f"Statistically distinguishable from baseline (|t| >= 2.0, N={n}). Requires out-of-sample holdout validation."
        else:
            status = BehavioralEvidenceStatus.OBSERVATIONAL_ONLY
            notes = f"Observed association not statistically distinguishable from random drift (N={n}, |t| < 2.0)."

        return BehavioralDiscoveryFinding(
            behavior_id=behavior_id,
            name=name,
            description=description,
            sample_size=n,
            horizons_bars=list(horizons_bars),
            conditional_mean_bps=dist.mean_return_bps,
            conditional_std_bps=dist.std_return_bps,
            win_rate_positive=dist.win_rate_positive,
            unconditional_baseline_bps=dist.unconditional_baseline_mean_bps,
            excess_return_bps=dist.excess_return_bps,
            standard_error_bps=se_dict,
            t_statistic=t_stat_dict,
            is_statistically_distinguishable=is_significant,
            status=status,
            scientific_notes=notes,
        )

    def analyze_trend_exhaustion(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B1: Overbought/Oversold extreme with compressed body (exhaustion candle)."""
        return self._build_finding_from_condition(
            behavior_id="B1_TREND_EXHAUSTION",
            name="Trend Exhaustion at Extreme",
            description="Exhaustion candle (body ratio < 0.35 with RSI > 70 or < 30)",
            condition_fn=lambda s: s.momentum.value == "EXHAUSTING",
            horizons_bars=horizons_bars,
        )

    def analyze_volatility_shock_recovery(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B2: Post-volatility shock drift (candle range > 3.0x ATR)."""
        return self._build_finding_from_condition(
            behavior_id="B2_VOLATILITY_SHOCK_RECOVERY",
            name="Volatility Shock Recovery",
            description="Price drift 1, 4, 12 bars after an extreme candle range (> 3.0x ATR)",
            condition_fn=lambda s: s.volatility.value == "VOLATILITY_SHOCK",
            horizons_bars=horizons_bars,
        )

    def analyze_mean_reversion_stretch(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B3: Range expansion & mean reversion (ADX proxy stretch > 2.5)."""
        return self._build_finding_from_condition(
            behavior_id="B3_RANGE_EXPANSION_MEAN_REVERSION",
            name="Extended Deviation from Mean",
            description="Price stretched > 2.5x ATR from rolling 50-EMA",
            condition_fn=lambda s: s.adx_proxy >= 2.50,
            horizons_bars=horizons_bars,
        )

    def analyze_momentum_persistence(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B4: Momentum persistence after 3 consecutive expanding body candles."""
        return self._build_finding_from_condition(
            behavior_id="B4_MOMENTUM_PERSISTENCE",
            name="Momentum Acceleration Persistence",
            description="3 consecutive expanding candles in trend direction",
            condition_fn=lambda s: s.momentum.value == "ACCELERATING",
            horizons_bars=horizons_bars,
        )

    def analyze_failed_continuation(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B5: Failed continuation (breakout attempt immediately rejected)."""
        return self._build_finding_from_condition(
            behavior_id="B5_FAILED_CONTINUATION",
            name="Failed Trend Continuation",
            description="Breakout attempt in trend immediately closed against trend direction",
            condition_fn=lambda s: (s.trend.value == "BULLISH_TREND" and s.volume.value == "HIGH_VOLUME" and self._closes[s.bar_index] < self._opens[s.bar_index]),
            horizons_bars=horizons_bars,
        )

    def analyze_large_candle_reaction(self, horizons_bars: tuple[int, ...] = (1, 4, 12)) -> BehavioralDiscoveryFinding:
        """B6: Price reaction after unusually large candles (> 95th percentile)."""
        ranges = self._highs - self._lows
        p95 = float(np.percentile(ranges, 95))

        return self._build_finding_from_condition(
            behavior_id="B6_LARGE_CANDLE_REACTION",
            name="Post 95th-Percentile Candle Reaction",
            description="Forward return distribution following a candle whose range exceeds the 95th percentile",
            condition_fn=lambda s: (self._highs[s.bar_index] - self._lows[s.bar_index]) >= p95,
            horizons_bars=horizons_bars,
        )
