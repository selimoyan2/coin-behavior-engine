"""Market Breadth Engine for cryptocurrency cross-sectional research.

Quantifies aggregate market participation and breadth regimes across the asset universe:
- Advance / Decline percentage (fraction of universe positive over rolling horizons).
- Percentage of universe trading above rolling EMA50.
- Percentage of universe classified as BULLISH_TREND by MarketRegimeEngine.
- Aggregate universe volume momentum and breadth thrust detection.
- Breadth divergence (BTC trend advance vs internal market participation).

Point-in-time calculation with zero future leakage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.market_regime_intelligence import (
    MarketRegimeEngine,
    TrendRegime,
)


@dataclass(frozen=True)
class MarketBreadthSnapshot:
    """Point-in-time market breadth state across the cryptocurrency universe."""

    bar_index: int
    timestamp_ms: int
    timestamp_utc: str
    advance_decline_ratio_24h: float  # Fraction of assets positive over 24h (0.0 to 1.0)
    pct_above_ema50: float  # Fraction of assets with close > EMA50
    pct_in_bullish_trend: float  # Fraction of assets in BULLISH_TREND
    mean_universe_volume_multiple: float  # Average relative volume across assets
    is_broad_advance: bool  # >= 66% of universe advancing
    is_narrow_advance: bool  # Benchmark advancing while <= 33% of universe advances
    breadth_thrust_detected: bool  # Breadth surged from < 0.30 to > 0.70 in 16 bars
    breadth_divergence_bearish: bool  # BTC higher high while breadth lower

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketBreadthEngine:
    """Computes point-in-time market breadth across multi-asset universe."""

    def __init__(
        self,
        asset_candles: Mapping[str, Sequence[Mapping[str, Any]]],
        benchmark_symbol: str = "BTCUSDT",
    ) -> None:
        self.benchmark_symbol = benchmark_symbol
        self.symbols = sorted(list(asset_candles.keys()))

        # Align candles on open_time
        dfs = {}
        for sym, c_list in asset_candles.items():
            df = pd.DataFrame(c_list)
            ts_col = "timestamp_open" if "timestamp_open" in df.columns else "open_time"
            df["ts"] = df[ts_col].astype(int)
            df = df.drop_duplicates("ts").sort_values("ts").set_index("ts")
            dfs[sym] = df

        common_ts = set(dfs[self.symbols[0]].index)
        for sym in self.symbols[1:]:
            common_ts = common_ts.intersection(set(dfs[sym].index))

        sorted_ts = sorted(list(common_ts))
        self.timestamps = sorted_ts
        self.n_bars = len(sorted_ts)

        self._closes: dict[str, np.ndarray] = {}
        self._volumes: dict[str, np.ndarray] = {}
        self._ema50: dict[str, np.ndarray] = {}
        self._regime_states: dict[str, list[TrendRegime]] = {}

        for sym in self.symbols:
            sub = dfs[sym].loc[sorted_ts]
            c_arr = sub["close"].astype(float).to_numpy()
            self._closes[sym] = c_arr
            self._volumes[sym] = sub["volume"].astype(float).to_numpy()
            self._ema50[sym] = pd.Series(c_arr).ewm(span=50, adjust=False).mean().to_numpy()

            # Classify regimes using MarketRegimeEngine
            candles_sym = sub.reset_index().to_dict(orient="records")
            r_engine = MarketRegimeEngine(candles_sym)
            trends = [r_engine.classify_bar(i).trend for i in range(len(candles_sym))]
            self._regime_states[sym] = trends

    def compute_breadth_snapshots(self, lookback_bars: int = 96) -> list[MarketBreadthSnapshot]:
        """Compute point-in-time breadth snapshots for all valid bars."""
        snapshots = []
        n = self.n_bars
        n_assets = len(self.symbols)

        # 24h rolling mean volume per asset
        vol_means = {}
        for sym in self.symbols:
            s_vol = pd.Series(self._volumes[sym]).rolling(window=96, min_periods=1).mean().to_numpy()
            vol_means[sym] = s_vol

        history_pct_ema: list[float] = []

        for t in range(lookback_bars, n):
            ts_ms = self.timestamps[t]
            ts_utc = pd.Timestamp(ts_ms, unit="ms", tz="UTC").isoformat()

            # 1. Advance / Decline over 24h
            advancing = 0
            above_ema50 = 0
            bullish_trends = 0
            rel_vols = []

            for sym in self.symbols:
                p_now = self._closes[sym][t]
                p_past = self._closes[sym][t - lookback_bars]
                if p_now > p_past:
                    advancing += 1

                if p_now > self._ema50[sym][t]:
                    above_ema50 += 1

                if self._regime_states[sym][t] == TrendRegime.BULLISH_TREND:
                    bullish_trends += 1

                v_curr = self._volumes[sym][t]
                v_avg = vol_means[sym][t]
                r_v = (v_curr / v_avg) if v_avg > 1e-9 else 1.0
                rel_vols.append(r_v)

            ad_ratio = advancing / n_assets
            pct_ema = above_ema50 / n_assets
            pct_bull = bullish_trends / n_assets
            mean_rel_vol = float(np.mean(rel_vols))
            history_pct_ema.append(pct_ema)

            is_broad = ad_ratio >= 0.66
            is_narrow = (self._closes[self.benchmark_symbol][t] > self._closes[self.benchmark_symbol][t - lookback_bars]) and (ad_ratio <= 0.34)

            # Breadth thrust: rose from <= 0.33 to >= 0.67 within last 16 bars
            thrust = False
            if len(history_pct_ema) >= 16:
                past_min = min(history_pct_ema[-16:-8])
                curr_max = max(history_pct_ema[-8:])
                if past_min <= 0.34 and curr_max >= 0.67:
                    thrust = True

            # Breadth divergence: BTC price making 48-bar high while pct_above_ema50 is lower than its 48-bar high
            div_bearish = False
            if t >= lookback_bars + 48:
                btc_p = self._closes[self.benchmark_symbol]
                if btc_p[t] >= np.max(btc_p[t - 48 : t]) and pct_ema < 0.66:
                    div_bearish = True

            snapshots.append(
                MarketBreadthSnapshot(
                    bar_index=t,
                    timestamp_ms=ts_ms,
                    timestamp_utc=ts_utc,
                    advance_decline_ratio_24h=round(ad_ratio, 3),
                    pct_above_ema50=round(pct_ema, 3),
                    pct_in_bullish_trend=round(pct_bull, 3),
                    mean_universe_volume_multiple=round(mean_rel_vol, 2),
                    is_broad_advance=is_broad,
                    is_narrow_advance=is_narrow,
                    breadth_thrust_detected=thrust,
                    breadth_divergence_bearish=div_bearish,
                )
            )

        return snapshots
