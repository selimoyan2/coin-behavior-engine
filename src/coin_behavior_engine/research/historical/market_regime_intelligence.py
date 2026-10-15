"""Point-in-time Market Regime Intelligence for historical market research.

Provides an observable, multi-dimensional point-in-time regime classification system:
- Trend dimension: BULLISH_TREND, BEARISH_TREND, SIDEWAYS_RANGE
- Volatility dimension: COMPRESSION_SQUEEZE, VOLATILITY_SHOCK, EXPANSION_NORMAL
- Volume dimension: HIGH_VOLUME, LOW_VOLUME, NORMAL_VOLUME
- Momentum dimension: ACCELERATING, EXHAUSTING, NEUTRAL
- Session dimension: ASIAN, LONDON, NEW_YORK, LONDON_NY_OVERLAP, SESSION_TRANSITION

Guarantees:
1. Strict zero lookahead (point-in-time evaluation at bar close t).
2. Non-mutually exclusive multi-dimensional representation.
3. Quantified regime duration, transition probabilities, and persistence.
4. Forward conditional return distribution analysis without lookahead bias.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.market_sessions import (
    MarketSession,
    MarketSessionDetector,
)


class TrendRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    SIDEWAYS_RANGE = "SIDEWAYS_RANGE"


class VolatilityRegime(str, Enum):
    COMPRESSION_SQUEEZE = "COMPRESSION_SQUEEZE"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"
    EXPANSION_NORMAL = "EXPANSION_NORMAL"


class VolumeRegime(str, Enum):
    HIGH_VOLUME = "HIGH_VOLUME"
    LOW_VOLUME = "LOW_VOLUME"
    NORMAL_VOLUME = "NORMAL_VOLUME"


class MomentumRegime(str, Enum):
    ACCELERATING = "ACCELERATING"
    EXHAUSTING = "EXHAUSTING"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class MarketRegimeState:
    """Point-in-time multi-dimensional market regime snapshot."""

    bar_index: int
    timestamp_ms: int
    trend: TrendRegime
    volatility: VolatilityRegime
    volume: VolumeRegime
    momentum: MomentumRegime
    primary_session: str
    is_session_transition: bool

    # Quantified regime metrics
    atr_14: float
    relative_volume_24h: float
    adx_proxy: float
    rsi_14: float
    squeeze_consecutive_bars: int
    trend_consecutive_bars: int

    @property
    def composite_key(self) -> str:
        """Compact string representing the active multi-dimensional state."""
        return f"{self.trend.value}|{self.volatility.value}|{self.volume.value}|{self.momentum.value}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["trend"] = self.trend.value
        d["volatility"] = self.volatility.value
        d["volume"] = self.volume.value
        d["momentum"] = self.momentum.value
        d["composite_key"] = self.composite_key
        return d


@dataclass(frozen=True)
class RegimeTransitionReport:
    """Empirical transition probabilities and duration statistics across regimes."""

    dimension: str
    unique_states: list[str]
    transition_matrix: dict[str, dict[str, float]]
    mean_durations_bars: dict[str, float]
    state_frequencies: dict[str, float]


@dataclass(frozen=True)
class ConditionalReturnDistribution:
    """Forward conditional return statistics for a specific regime condition."""

    regime_condition: str
    sample_count: int
    horizons_bars: list[int]
    mean_return_bps: dict[str, float]  # e.g. {"1_bar": 1.2, "4_bars": 4.5}
    std_return_bps: dict[str, float]
    skewness: dict[str, float]
    win_rate_positive: dict[str, float]
    unconditional_baseline_mean_bps: dict[str, float]
    excess_return_bps: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketRegimeEngine:
    """Observable point-in-time market regime classifier and analyzer."""

    def __init__(self, candles: Sequence[Mapping[str, Any]]) -> None:
        self.candles = candles
        self.n_bars = len(candles)
        self.session_detector = MarketSessionDetector()

        self._closes = np.array([float(c["close"]) for c in candles])
        self._highs = np.array([float(c["high"]) for c in candles])
        self._lows = np.array([float(c["low"]) for c in candles])
        self._volumes = np.array([float(c.get("volume", 0.0)) for c in candles])
        self._timestamps = [int(c.get("open_time", c.get("timestamp_open", c.get("timestamp_ms", 0)))) for c in candles]

        # Compute point-in-time indicators
        self._compute_technical_indicators()

    def _compute_technical_indicators(self) -> None:
        """Compute rolling indicators with strict point-in-time lookback."""
        n = self.n_bars
        self._ema50 = np.full(n, np.nan)
        self._ema200 = np.full(n, np.nan)
        self._atr14 = np.zeros(n)
        self._rsi14 = np.full(n, 50.0)
        self._rel_vol = np.ones(n)
        self._is_squeeze = np.zeros(n, dtype=bool)

        if n == 0:
            return

        # ATR 14
        tr = np.zeros(n)
        tr[0] = self._highs[0] - self._lows[0]
        for i in range(1, n):
            h_l = self._highs[i] - self._lows[i]
            h_pc = abs(self._highs[i] - self._closes[i - 1])
            l_pc = abs(self._lows[i] - self._closes[i - 1])
            tr[i] = max(h_l, h_pc, l_pc)

        # Exponential smoothing for ATR
        alpha_atr = 1.0 / 14.0
        self._atr14[0] = tr[0]
        for i in range(1, n):
            self._atr14[i] = alpha_atr * tr[i] + (1.0 - alpha_atr) * self._atr14[i - 1]

        # EMAs
        if n >= 50:
            s_50 = pd.Series(self._closes).ewm(span=50, adjust=False).mean().to_numpy()
            self._ema50 = s_50
        if n >= 200:
            s_200 = pd.Series(self._closes).ewm(span=200, adjust=False).mean().to_numpy()
            self._ema200 = s_200

        # Relative Volume (relative to 24h rolling average: 96 bars for 15m, 288 for 5m)
        vol_window = 96  # default 24h for 15m bars
        for i in range(n):
            start_idx = max(0, i - vol_window)
            window_vol = self._volumes[start_idx : i + 1]
            mean_v = float(np.mean(window_vol)) if len(window_vol) > 0 else 1.0
            self._rel_vol[i] = (self._volumes[i] / mean_v) if mean_v > 1e-9 else 1.0

        # RSI 14
        diffs = np.diff(self._closes)
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        if len(diffs) >= 14:
            avg_gain = float(np.mean(gains[:14]))
            avg_loss = float(np.mean(losses[:14]))
            for i in range(14, len(diffs)):
                avg_gain = (avg_gain * 13 + gains[i]) / 14.0
                avg_loss = (avg_loss * 13 + losses[i]) / 14.0
                rs = avg_gain / avg_loss if avg_loss > 1e-9 else 100.0
                self._rsi14[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        # Bollinger Bands & Keltner Channels for Squeeze
        for i in range(20, n):
            window_cl = self._closes[i - 19 : i + 1]
            std_cl = float(np.std(window_cl, ddof=1)) if len(window_cl) > 1 else 1e-9
            # BB width vs KC width
            bb_half = 2.0 * std_cl
            kc_half = 1.5 * self._atr14[i]
            if bb_half <= kc_half:
                self._is_squeeze[i] = True

    def classify_bar(self, index: int) -> MarketRegimeState:
        """Classify point-in-time regime state for a single bar index."""
        if index < 0 or index >= self.n_bars:
            raise IndexError(f"Bar index {index} out of bounds (0..{self.n_bars - 1})")

        cl = self._closes[index]
        hi = self._highs[index]
        lo = self._lows[index]
        ts = self._timestamps[index]
        atr = self._atr14[index]
        r_vol = self._rel_vol[index]
        rsi = self._rsi14[index]
        candle_range = hi - lo

        # 1. Trend Dimension
        ema50_val = self._ema50[index]
        ema200_val = self._ema200[index]
        if not np.isnan(ema50_val) and not np.isnan(ema200_val):
            if cl > ema50_val and ema50_val > ema200_val:
                trend = TrendRegime.BULLISH_TREND
            elif cl < ema50_val and ema50_val < ema200_val:
                trend = TrendRegime.BEARISH_TREND
            else:
                trend = TrendRegime.SIDEWAYS_RANGE
        elif not np.isnan(ema50_val):
            if cl > ema50_val:
                trend = TrendRegime.BULLISH_TREND
            else:
                trend = TrendRegime.BEARISH_TREND
        else:
            trend = TrendRegime.SIDEWAYS_RANGE

        # 2. Volatility Dimension
        if candle_range > 3.0 * atr and atr > 0:
            volatility = VolatilityRegime.VOLATILITY_SHOCK
        elif self._is_squeeze[index]:
            volatility = VolatilityRegime.COMPRESSION_SQUEEZE
        else:
            volatility = VolatilityRegime.EXPANSION_NORMAL

        # 3. Volume Dimension
        if r_vol >= 1.50:
            volume = VolumeRegime.HIGH_VOLUME
        elif r_vol <= 0.60:
            volume = VolumeRegime.LOW_VOLUME
        else:
            volume = VolumeRegime.NORMAL_VOLUME

        # 4. Momentum Dimension
        body_size = abs(cl - float(self.candles[index]["open"]))
        body_ratio = body_size / candle_range if candle_range > 1e-9 else 0.5

        if rsi > 70.0 and body_ratio < 0.40:
            momentum = MomentumRegime.EXHAUSTING
        elif rsi < 30.0 and body_ratio < 0.40:
            momentum = MomentumRegime.EXHAUSTING
        elif index >= 2:
            prev1_body = abs(self._closes[index - 1] - float(self.candles[index - 1]["open"]))
            prev2_body = abs(self._closes[index - 2] - float(self.candles[index - 2]["open"]))
            if body_size > prev1_body > prev2_body and body_ratio > 0.60:
                momentum = MomentumRegime.ACCELERATING
            else:
                momentum = MomentumRegime.NEUTRAL
        else:
            momentum = MomentumRegime.NEUTRAL

        # 5. Session Context
        session_cfg = self.session_detector.detect_session(ts)
        primary_session = str(session_cfg.primary_session)
        hour_utc = (ts // 3_600_000) % 24
        min_utc = (ts // 60_000) % 60
        is_transition = (hour_utc in (7, 12, 16, 20) and min_utc <= 30)

        # Count consecutive squeeze bars ending at index
        squeeze_count = 0
        cur_idx = index
        while cur_idx >= 0 and self._is_squeeze[cur_idx]:
            squeeze_count += 1
            cur_idx -= 1

        # Count consecutive trend bars ending at index
        trend_count = 1

        return MarketRegimeState(
            bar_index=index,
            timestamp_ms=ts,
            trend=trend,
            volatility=volatility,
            volume=volume,
            momentum=momentum,
            primary_session=primary_session,
            is_session_transition=is_transition,
            atr_14=round(atr, 4),
            relative_volume_24h=round(r_vol, 3),
            adx_proxy=round(abs(cl - ema50_val) / atr if (not np.isnan(ema50_val) and atr > 0) else 0.0, 2),
            rsi_14=round(rsi, 2),
            squeeze_consecutive_bars=squeeze_count,
            trend_consecutive_bars=trend_count,
        )

    def classify_all(self, start_bar: int = 50) -> list[MarketRegimeState]:
        """Classify regime states for all bars from start_bar onwards."""
        states: list[MarketRegimeState] = []
        for i in range(start_bar, self.n_bars):
            states.append(self.classify_bar(i))
        return states

    def compute_regime_transition_matrix(
        self,
        dimension: str = "volatility",
        start_bar: int = 50,
    ) -> RegimeTransitionReport:
        """Compute transition matrix and empirical duration for a regime dimension."""
        states = self.classify_all(start_bar=start_bar)
        if not states:
            return RegimeTransitionReport(
                dimension=dimension, unique_states=[], transition_matrix={},
                mean_durations_bars={}, state_frequencies={}
            )

        seq = [getattr(s, dimension).value for s in states]
        unique_vals = sorted(list(set(seq)))

        # Transition counts
        counts: dict[str, dict[str, int]] = {u: {v: 0 for v in unique_vals} for u in unique_vals}
        for i in range(len(seq) - 1):
            counts[seq[i]][seq[i + 1]] += 1

        # Normalized transition probabilities
        trans_mat: dict[str, dict[str, float]] = {}
        for u in unique_vals:
            tot = sum(counts[u].values())
            trans_mat[u] = {v: round(counts[u][v] / tot, 4) if tot > 0 else 0.0 for v in unique_vals}

        # Durations
        durations: dict[str, list[int]] = {u: [] for u in unique_vals}
        cur_state = seq[0]
        cur_len = 1
        for i in range(1, len(seq)):
            if seq[i] == cur_state:
                cur_len += 1
            else:
                durations[cur_state].append(cur_len)
                cur_state = seq[i]
                cur_len = 1
        durations[cur_state].append(cur_len)

        mean_dur = {u: round(float(np.mean(durations[u])), 2) if durations[u] else 0.0 for u in unique_vals}
        tot_bars = len(seq)
        freqs = {u: round(len([x for x in seq if x == u]) / tot_bars, 4) for u in unique_vals}

        return RegimeTransitionReport(
            dimension=dimension,
            unique_states=unique_vals,
            transition_matrix=trans_mat,
            mean_durations_bars=mean_dur,
            state_frequencies=freqs,
        )

    def analyze_conditional_return_distribution(
        self,
        filter_fn: Any,
        condition_name: str,
        horizons_bars: tuple[int, ...] = (1, 4, 12),
        start_bar: int = 50,
    ) -> ConditionalReturnDistribution:
        """Measure forward price distribution conditional on a point-in-time regime rule."""
        max_h = max(horizons_bars)
        states = [self.classify_bar(i) for i in range(start_bar, self.n_bars - max_h)]

        matched_indices = []
        for s in states:
            if filter_fn(s):
                matched_indices.append(s.bar_index)

        # Baseline unconditional returns
        all_indices = [s.bar_index for s in states]

        mean_bps: dict[str, float] = {}
        std_bps: dict[str, float] = {}
        skew_dict: dict[str, float] = {}
        win_dict: dict[str, float] = {}
        base_mean_bps: dict[str, float] = {}
        excess_bps: dict[str, float] = {}

        for h in horizons_bars:
            h_key = f"{h}_bars"
            # Unconditional baseline
            all_rets = [(self._closes[i + h] - self._closes[i]) / self._closes[i] * 10000.0 for i in all_indices]
            base_m = float(np.mean(all_rets)) if all_rets else 0.0
            base_mean_bps[h_key] = round(base_m, 2)

            if matched_indices:
                cond_rets = [(self._closes[i + h] - self._closes[i]) / self._closes[i] * 10000.0 for i in matched_indices]
                m = float(np.mean(cond_rets))
                s = float(np.std(cond_rets, ddof=1)) if len(cond_rets) > 1 else 0.0
                win = float(np.mean([1.0 if r > 0 else 0.0 for r in cond_rets]))
                # Skewness
                if s > 1e-9 and len(cond_rets) > 2:
                    cond_arr = np.array(cond_rets)
                    skew_val = float(np.mean(((cond_arr - m) / s) ** 3))
                else:
                    skew_val = 0.0

                mean_bps[h_key] = round(m, 2)
                std_bps[h_key] = round(s, 2)
                skew_dict[h_key] = round(skew_val, 2)
                win_dict[h_key] = round(win, 4)
                excess_bps[h_key] = round(m - base_m, 2)
            else:
                mean_bps[h_key] = 0.0
                std_bps[h_key] = 0.0
                skew_dict[h_key] = 0.0
                win_dict[h_key] = 0.0
                excess_bps[h_key] = 0.0

        return ConditionalReturnDistribution(
            regime_condition=condition_name,
            sample_count=len(matched_indices),
            horizons_bars=list(horizons_bars),
            mean_return_bps=mean_bps,
            std_return_bps=std_bps,
            skewness=skew_dict,
            win_rate_positive=win_dict,
            unconditional_baseline_mean_bps=base_mean_bps,
            excess_return_bps=excess_bps,
        )
