"""Causal Market Regime Recognition Engine V1.

Sprint 11.21 Phase 1:
Classifies market state strictly point-in-time (t <= T_0) using closed 5m candles.
Six required canonical states:
1. TREND_UP: Sustained upward momentum, positive multi-horizon alignment, low drawdown.
2. TREND_DOWN: Sustained downward momentum, negative multi-horizon alignment, low recovery.
3. RANGE: Bounded price action between rolling support/resistance, low net drift, compressed ATR.
4. HIGH_VOLATILITY: Extreme ATR% or realized volatility exceeding historical volatility bands.
5. TRANSITION: Volatility expansion out of compression, failed breakouts, or conflicting short vs long horizons.
6. UNCERTAIN: Conflicted signals, insufficient history, or data quality flags.

Zero lookahead leakage: all indicators use past closed candles only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CausalRegimeDecision:
    """Point-in-time regime classification outcome."""
    regime: str
    confidence: float
    rationale: str
    support_level: float
    resistance_level: float
    range_width_pct: float
    features: Dict[str, float]


class CausalRegimeEngine:
    """Causal market regime classifier and empirical transition dynamics auditor."""

    REGIMES = [
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "HIGH_VOLATILITY",
        "TRANSITION",
        "UNCERTAIN"
    ]

    def __init__(
        self,
        df_5m: pd.DataFrame,
        high_vol_atr_threshold: float = 0.0080,    # 0.80% 5m ATR
        high_vol_realized_threshold: float = 0.90, # 90% annualized volatility
        trend_min_persistence: float = 0.65,       # 65% of bars above/below EMA
        range_max_width_pct: float = 0.045,       # 24h range width < 4.5%
        compression_atr_threshold: float = 0.0035 # ATR < 0.35% implies compression
    ):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.n_bars = len(self.df_5m)
        self.high_vol_atr = high_vol_atr_threshold
        self.high_vol_realized = high_vol_realized_threshold
        self.trend_min_persistence = trend_min_persistence
        self.range_max_width_pct = range_max_width_pct
        self.compression_atr = compression_atr_threshold

        self._precompute_features()

    def _precompute_features(self) -> None:
        """Precompute rolling causal features across the entire historical series."""
        close = self.df_5m["close"].to_numpy(dtype=np.float64)
        high = self.df_5m["high"].to_numpy(dtype=np.float64)
        low = self.df_5m["low"].to_numpy(dtype=np.float64)
        volume = self.df_5m["volume"].to_numpy(dtype=np.float64)

        # 1. Multi-horizon log returns
        # 1h = 12 bars, 4h = 48 bars, 24h = 288 bars, 72h = 864 bars
        self.ret_1h = np.full(self.n_bars, 0.0)
        self.ret_4h = np.full(self.n_bars, 0.0)
        self.ret_24h = np.full(self.n_bars, 0.0)
        self.ret_72h = np.full(self.n_bars, 0.0)

        self.ret_1h[12:] = np.log(close[12:] / close[:-12])
        self.ret_4h[48:] = np.log(close[48:] / close[:-48])
        self.ret_24h[288:] = np.log(close[288:] / close[:-288])
        self.ret_72h[864:] = np.log(close[864:] / close[:-864])

        # 2. EMAs: EMA-12, EMA-48, EMA-288
        s_close = pd.Series(close)
        self.ema_12 = s_close.ewm(span=12, adjust=False).mean().to_numpy()
        self.ema_48 = s_close.ewm(span=48, adjust=False).mean().to_numpy()
        self.ema_288 = s_close.ewm(span=288, adjust=False).mean().to_numpy()

        # Trend slope: 24h slope of EMA-288
        ema_diff = np.diff(self.ema_288, prepend=self.ema_288[0])
        self.trend_slope = (ema_diff / np.maximum(close, 1.0)) * 288.0

        # Trend persistence: fraction of last 48 bars where close > EMA-48
        is_above_ema48 = (close > self.ema_48).astype(float)
        self.persistence_4h = pd.Series(is_above_ema48).rolling(48, min_periods=12).mean().to_numpy()

        # 3. Realized Volatility: rolling 24h (288 bars) std of 5m log returns, annualized (sqrt(288 * 365))
        log_rets = np.diff(np.log(close), prepend=0.0)
        s_rets = pd.Series(log_rets)
        self.realized_vol_24h = (s_rets.rolling(288, min_periods=48).std().to_numpy()) * np.sqrt(288.0 * 365.0)

        # 4. ATR normalized by price (14-bar ATR)
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
        atr_14 = pd.Series(tr).ewm(span=14, adjust=False).mean().to_numpy()
        self.atr_pct = atr_14 / np.maximum(close, 1.0)

        # 5. Volume expansion: rolling 24h vol / rolling 7d vol (2016 bars)
        s_vol = pd.Series(volume)
        vol_24h = s_vol.rolling(288, min_periods=48).mean().to_numpy()
        vol_7d = s_vol.rolling(2016, min_periods=288).mean().to_numpy()
        self.volume_ratio_24h = np.where(vol_7d > 1e-6, vol_24h / vol_7d, 1.0)

        # 6. Rolling Support & Resistance (288 bars = 24h)
        s_high = pd.Series(high)
        s_low = pd.Series(low)
        self.high_24h = s_high.rolling(288, min_periods=48).max().to_numpy()
        self.low_24h = s_low.rolling(288, min_periods=48).min().to_numpy()
        self.high_72h = s_high.rolling(864, min_periods=288).max().to_numpy()
        self.low_72h = s_low.rolling(864, min_periods=288).min().to_numpy()

        self.drawdown_72h = (close - self.high_72h) / np.maximum(self.high_72h, 1.0)
        self.recovery_72h = (close - self.low_72h) / np.maximum(self.low_72h, 1.0)

        self.range_width_pct = (self.high_24h - self.low_24h) / np.maximum(close, 1.0)
        self.dist_support_pct = (close - self.low_24h) / np.maximum(close, 1.0)
        self.dist_resistance_pct = (self.high_24h - close) / np.maximum(close, 1.0)

    def classify_at(self, idx: int) -> CausalRegimeDecision:
        """Classify regime strictly point-in-time at candle index idx."""
        if idx < 864:  # Minimum 72 hours for multi-horizon indicators
            return CausalRegimeDecision(
                regime="UNCERTAIN",
                confidence=0.50,
                rationale="Insufficient history (< 864 bars) for causal feature estimation",
                support_level=float(self.low_24h[idx]) if idx >= 48 else 0.0,
                resistance_level=float(self.high_24h[idx]) if idx >= 48 else 0.0,
                range_width_pct=float(self.range_width_pct[idx]) if idx >= 48 else 0.0,
                features={}
            )

        c_close = float(self.df_5m.iloc[idx]["close"])
        c_atr = float(self.atr_pct[idx])
        c_vol = float(self.realized_vol_24h[idx])
        c_ret_1h = float(self.ret_1h[idx])
        c_ret_4h = float(self.ret_4h[idx])
        c_ret_24h = float(self.ret_24h[idx])
        c_ret_72h = float(self.ret_72h[idx])
        c_slope = float(self.trend_slope[idx])
        c_pers = float(self.persistence_4h[idx])
        c_width = float(self.range_width_pct[idx])
        c_dd = float(self.drawdown_72h[idx])
        c_rec = float(self.recovery_72h[idx])
        c_vol_ratio = float(self.volume_ratio_24h[idx])

        features = {
            "atr_pct": c_atr,
            "realized_vol_24h": c_vol,
            "ret_1h": c_ret_1h,
            "ret_4h": c_ret_4h,
            "ret_24h": c_ret_24h,
            "ret_72h": c_ret_72h,
            "trend_slope": c_slope,
            "persistence_4h": c_pers,
            "range_width_pct": c_width,
            "drawdown_72h": c_dd,
            "recovery_72h": c_rec,
            "volume_ratio_24h": c_vol_ratio
        }

        sup = float(self.low_24h[idx])
        res = float(self.high_24h[idx])

        # Priority 1: High Volatility Instability
        if c_atr >= self.high_vol_atr or c_vol >= self.high_vol_realized:
            conf = min(0.95, 0.70 + (c_atr / self.high_vol_atr - 1.0) * 0.25)
            return CausalRegimeDecision(
                regime="HIGH_VOLATILITY",
                confidence=round(conf, 4),
                rationale=f"Elevated volatility: ATR%={c_atr*100:.2f}%, RealizedVol={c_vol*100:.1f}%",
                support_level=sup,
                resistance_level=res,
                range_width_pct=c_width,
                features=features
            )

        # Priority 2: Transition Detection (Breakout expansion or sharp horizon conflict)
        # Conditions:
        # a) Short-term return sharp opposite to 24h/72h trend (counter-trend shock)
        # b) Volatility expansion out of tight range (ATR jumping while volume expands > 1.5x)
        # c) Price breaking 24h high/low with conflicting momentum
        is_transition = False
        trans_reason = ""

        if (c_ret_1h < -0.012 and c_ret_24h > 0.02) or (c_ret_1h > 0.012 and c_ret_24h < -0.02):
            is_transition = True
            trans_reason = f"Sharp horizon conflict: 1h ret={c_ret_1h*100:.2f}% vs 24h ret={c_ret_24h*100:.2f}%"
        elif c_vol_ratio > 1.6 and c_width < self.range_max_width_pct and abs(c_ret_4h) > 0.015:
            is_transition = True
            trans_reason = f"Volume breakout from range: vol_ratio={c_vol_ratio:.2f}, 4h ret={c_ret_4h*100:.2f}%"

        if is_transition:
            return CausalRegimeDecision(
                regime="TRANSITION",
                confidence=0.75,
                rationale=trans_reason,
                support_level=sup,
                resistance_level=res,
                range_width_pct=c_width,
                features=features
            )

        # Priority 3: Trend Up
        is_trend_up = (
            c_ret_24h > 0.012
            and c_ret_72h > 0.015
            and c_pers >= self.trend_min_persistence
            and c_slope > 0.002
            and c_dd > -0.035
        )
        if is_trend_up:
            conf = min(0.95, 0.65 + c_pers * 0.2 + (c_ret_24h / 0.05) * 0.1)
            return CausalRegimeDecision(
                regime="TREND_UP",
                confidence=round(conf, 4),
                rationale=f"Bullish trend alignment: 24h={c_ret_24h*100:.2f}%, 72h={c_ret_72h*100:.2f}%, persistence={c_pers:.2f}",
                support_level=sup,
                resistance_level=res,
                range_width_pct=c_width,
                features=features
            )

        # Priority 4: Trend Down
        is_trend_down = (
            c_ret_24h < -0.012
            and c_ret_72h < -0.015
            and c_pers <= (1.0 - self.trend_min_persistence)
            and c_slope < -0.002
            and c_rec < 0.035
        )
        if is_trend_down:
            conf = min(0.95, 0.65 + (1.0 - c_pers) * 0.2 + (abs(c_ret_24h) / 0.05) * 0.1)
            return CausalRegimeDecision(
                regime="TREND_DOWN",
                confidence=round(conf, 4),
                rationale=f"Bearish trend alignment: 24h={c_ret_24h*100:.2f}%, 72h={c_ret_72h*100:.2f}%, persistence={c_pers:.2f}",
                support_level=sup,
                resistance_level=res,
                range_width_pct=c_width,
                features=features
            )

        # Priority 5: Range Consolidation
        is_range = (
            c_width <= self.range_max_width_pct
            and abs(c_ret_24h) <= 0.018
            and abs(c_ret_72h) <= 0.035
            and 0.35 <= c_pers <= 0.65
        )
        if is_range:
            conf = min(0.92, 0.65 + (1.0 - c_width / self.range_max_width_pct) * 0.25)
            return CausalRegimeDecision(
                regime="RANGE",
                confidence=round(conf, 4),
                rationale=f"Sideways range: 24h width={c_width*100:.2f}%, net 24h drift={c_ret_24h*100:.2f}%",
                support_level=sup,
                resistance_level=res,
                range_width_pct=c_width,
                features=features
            )

        # Priority 6: Uncertain
        return CausalRegimeDecision(
            regime="UNCERTAIN",
            confidence=0.55,
            rationale="Ambiguous market state: mixed trend persistence and return dispersion",
            support_level=sup,
            resistance_level=res,
            range_width_pct=c_width,
            features=features
        )

    def compute_regime_series(self, sample_step_bars: int = 12) -> Tuple[pd.DataFrame, np.ndarray, Dict[str, Any]]:
        """Compute regime classifications and calculate transition matrix and persistence."""
        indices = np.arange(864, self.n_bars, sample_step_bars)
        records = []
        regimes_seq = []

        for idx in indices:
            dec = self.classify_at(idx)
            records.append({
                "bar_idx": idx,
                "open_time": int(self.df_5m.iloc[idx]["open_time"]),
                "datetime_utc": str(pd.to_datetime(int(self.df_5m.iloc[idx]["open_time"]), unit="ms", utc=True)),
                "close": float(self.df_5m.iloc[idx]["close"]),
                "regime": dec.regime,
                "confidence": dec.confidence,
                "range_width_pct": dec.range_width_pct,
                "support_level": dec.support_level,
                "resistance_level": dec.resistance_level
            })
            regimes_seq.append(dec.regime)

        df_regimes = pd.DataFrame(records)

        # Transition Matrix (6x6)
        reg_to_idx = {r: i for i, r in enumerate(self.REGIMES)}
        n_reg = len(self.REGIMES)
        trans_counts = np.zeros((n_reg, n_reg), dtype=np.int64)

        for i in range(len(regimes_seq) - 1):
            curr_r = reg_to_idx[regimes_seq[i]]
            next_r = reg_to_idx[regimes_seq[i + 1]]
            trans_counts[curr_r, next_r] += 1

        trans_matrix = np.zeros((n_reg, n_reg), dtype=np.float64)
        for i in range(n_reg):
            row_sum = np.sum(trans_counts[i, :])
            if row_sum > 0:
                trans_matrix[i, :] = trans_counts[i, :] / row_sum
            else:
                trans_matrix[i, i] = 1.0

        # Regime Persistence (average contiguous episodes)
        durations: Dict[str, List[int]] = {r: [] for r in self.REGIMES}
        curr_state = regimes_seq[0]
        curr_len = 1

        for r in regimes_seq[1:]:
            if r == curr_state:
                curr_len += 1
            else:
                durations[curr_state].append(curr_len * sample_step_bars)
                curr_state = r
                curr_len = 1
        durations[curr_state].append(curr_len * sample_step_bars)

        persistence_stats = {}
        for r in self.REGIMES:
            d_list = durations[r]
            if d_list:
                mean_bars = float(np.mean(d_list))
                mean_hours = mean_bars * 5.0 / 60.0
                persistence_stats[r] = {
                    "total_episodes": len(d_list),
                    "mean_duration_bars": round(mean_bars, 1),
                    "mean_duration_hours": round(mean_hours, 2),
                    "max_duration_hours": round(float(np.max(d_list)) * 5.0 / 60.0, 2)
                }
            else:
                persistence_stats[r] = {
                    "total_episodes": 0,
                    "mean_duration_bars": 0.0,
                    "mean_duration_hours": 0.0,
                    "max_duration_hours": 0.0
                }

        # Distribution of regimes
        regime_counts = df_regimes["regime"].value_counts().to_dict()
        regime_dist_pct = {r: round((regime_counts.get(r, 0) / len(df_regimes)) * 100.0, 2) for r in self.REGIMES}

        summary = {
            "total_sampled_moments": len(df_regimes),
            "step_bars": sample_step_bars,
            "step_hours": sample_step_bars * 5 / 60,
            "regime_distribution_pct": regime_dist_pct,
            "regime_persistence": persistence_stats,
            "transition_matrix": {
                from_r: {to_r: round(trans_matrix[i, j], 4) for j, to_r in enumerate(self.REGIMES)}
                for i, from_r in enumerate(self.REGIMES)
            }
        }

        return df_regimes, trans_matrix, summary
