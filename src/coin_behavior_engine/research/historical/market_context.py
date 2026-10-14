"""Historical market context, regime detection, and OHLCV liquidity proxies.

Includes:
- Trend vs Range conditions (Directional efficiency ratio, trend slope).
- Volatility regime classification (rolling percentile ranks).
- Relative Volume (RVOL vs rolling session window).
- OHLCV Liquidity Proxies (Amihud illiquidity, Corwin-Schultz spread proxy).
  NOTE: These are purely OHLCV-derived mathematical proxies, NOT true L2/L3 order-book metrics.
- Time-of-day / Day-of-week cyclical indicators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MarketContextFeatures:
    """Market context and regime metrics for a single bar."""

    bar_index: int
    timestamp_ms: int

    # Trend vs Range
    efficiency_ratio: float  # Kaufman efficiency ratio: 0.0 (pure chop/range) to 1.0 (pure trend)
    is_trending: bool
    is_ranging: bool
    trend_direction: int  # 1 for bull, -1 for bear, 0 for flat

    # Volatility Regimes
    volatility_percentile: float  # 0.0 to 1.0 percentile rank over rolling window
    volatility_regime: str  # "LOW", "NORMAL", "HIGH", "EXTREME"

    # Volume
    relative_volume: float  # Current volume / rolling average volume

    # OHLCV Liquidity Proxies (EXPLICIT PROXIES - NOT ORDER BOOK METRICS)
    amihud_illiquidity_proxy: float
    corwin_schultz_spread_proxy: float
    is_ohlcv_liquidity_proxy: bool = True
    liquidity_proxy_disclaimer: str = (
        "Calculated from OHLCV prices and volumes. This is a statistical proxy, "
        "not actual Level 2 or Level 3 order book depth or quoted spread."
    )

    # Cyclical / Time features
    hour_utc: int = 0
    minute_utc: int = 0
    day_of_week: int = 0  # 0=Monday, 6=Sunday
    is_weekend: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketContextExtractor:
    """Extracts market context, volatility regimes, and liquidity proxies."""

    def __init__(
        self,
        efficiency_window: int = 20,
        volatility_window: int = 288,  # 24 hours of 5m bars
        volume_window: int = 288,
    ) -> None:
        self.efficiency_window = efficiency_window
        self.volatility_window = volatility_window
        self.volume_window = volume_window

    def extract_context(
        self,
        candles: Sequence[Mapping[str, Any]],
    ) -> list[MarketContextFeatures]:
        """Compute chronological context features for candles without lookahead."""
        n = len(candles)
        if n == 0:
            return []

        results: list[MarketContextFeatures] = []
        recent_ranges: list[float] = []
        recent_volumes: list[float] = []

        for i in range(n):
            c = candles[i]
            ts = int(c.get("open_time", c.get("timestamp_ms", c.get("timestamp", i))))
            op = float(c["open"])
            hi = float(c["high"])
            lo = float(c["low"])
            cl = float(c["close"])
            vol = float(c.get("volume", 0.0))

            dt_utc = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            hour_utc = dt_utc.hour
            minute_utc = dt_utc.minute
            dow = dt_utc.weekday()
            is_wknd = dow in (5, 6)

            bar_range = (hi - lo) / max(cl, 1e-6)
            recent_ranges.append(bar_range)
            recent_volumes.append(vol)

            # 1. Kaufman Efficiency Ratio over efficiency_window
            if i >= self.efficiency_window:
                start_c = float(candles[i - self.efficiency_window]["close"])
                net_change = abs(cl - start_c)
                gross_change = sum(
                    abs(float(candles[k]["close"]) - float(candles[k - 1]["close"]))
                    for k in range(i - self.efficiency_window + 1, i + 1)
                )
                er = (net_change / gross_change) if gross_change > 1e-9 else 0.0
                er = max(0.0, min(1.0, er))
                trend_dir = 1 if cl > start_c else (-1 if cl < start_c else 0)
            else:
                er = 0.5
                trend_dir = 0

            is_trend = er > 0.40
            is_range = er <= 0.40

            # 2. Volatility percentile rank over rolling window
            vol_history = recent_ranges[-self.volatility_window:]
            if len(vol_history) > 1:
                rank = sum(1 for v in vol_history if v <= bar_range) / len(vol_history)
            else:
                rank = 0.50

            if rank < 0.25:
                regime = "LOW"
            elif rank < 0.75:
                regime = "NORMAL"
            elif rank < 0.95:
                regime = "HIGH"
            else:
                regime = "EXTREME"

            # 3. Relative Volume (RVOL)
            vol_hist = recent_volumes[-self.volume_window:]
            avg_vol = sum(vol_hist) / len(vol_hist) if vol_hist else vol
            rvol = (vol / avg_vol) if avg_vol > 1e-9 else 1.0

            # 4. Amihud Illiquidity Proxy: |Return| / (Price * Volume)
            # Scaled by 1e6 for readability
            ret = abs(cl - op) / max(op, 1e-6)
            dollar_vol = cl * vol
            if dollar_vol > 1e-4:
                amihud = (ret / dollar_vol) * 1e6
            else:
                amihud = 0.0

            # 5. Corwin-Schultz (2012) High-Low Spread Proxy
            # Uses high-to-low ratio of two consecutive bars
            cs_spread = 0.0
            if i >= 1:
                prev_c = candles[i - 1]
                prev_hi = float(prev_c["high"])
                prev_lo = float(prev_c["low"])

                # Log price ratios
                if prev_lo > 0 and lo > 0:
                    gamma = math.log(max(hi, prev_hi) / min(lo, prev_lo)) ** 2
                    beta = (math.log(prev_hi / prev_lo) ** 2) + (math.log(hi / lo) ** 2)
                    denom = 3.0 - 2.0 * math.sqrt(2.0)
                    alpha = ((math.sqrt(2.0 * beta) - math.sqrt(beta)) / denom) - math.sqrt(max(0.0, gamma / denom))
                    if alpha < 0:
                        cs_spread = 0.0
                    else:
                        exp_alpha = math.exp(alpha)
                        cs_spread = 2.0 * (exp_alpha - 1.0) / (1.0 + exp_alpha)
            else:
                cs_spread = 0.0

            results.append(
                MarketContextFeatures(
                    bar_index=i,
                    timestamp_ms=ts,
                    efficiency_ratio=er,
                    is_trending=is_trend,
                    is_ranging=is_range,
                    trend_direction=trend_dir,
                    volatility_percentile=rank,
                    volatility_regime=regime,
                    relative_volume=rvol,
                    amihud_illiquidity_proxy=amihud,
                    corwin_schultz_spread_proxy=cs_spread,
                    is_ohlcv_liquidity_proxy=True,
                    hour_utc=hour_utc,
                    minute_utc=minute_utc,
                    day_of_week=dow,
                    is_weekend=is_wknd,
                )
            )

        return results
