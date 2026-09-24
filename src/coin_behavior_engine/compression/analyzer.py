"""Compression state analysis and breakout differentiation.

Differentiates compression episodes into:
- Category A: Compression followed by upward expansion (+2% in 24h)
- Category B: Compression followed by downward expansion (-2% in 24h)
- Category C: False / no expansion (resolved into chop or < 1% move)

Analyzes:
- Compression episode duration (candles)
- Minimum compression ratio reached
- Volume trend during compression (decaying vs accumulating)
- Taker buy volume ratio drift (is buying pressure accumulating before upward breakout?)
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


class CompressionEpisodeAnalyzer:
    """Analyzes contiguous compression episodes and categorizes their breakout outcomes."""

    def __init__(
        self,
        expansion_horizon_candles: int = 288,  # 24h
        expansion_threshold_pct: float = 0.02, # 2.0%
        chop_threshold_pct: float = 0.01,      # < 1.0% is chop/false
    ):
        self.expansion_horizon = expansion_horizon_candles
        self.expansion_threshold = expansion_threshold_pct
        self.chop_threshold = chop_threshold_pct

    def identify_compression_episodes(
        self,
        df: pd.DataFrame,
        compression_col: str = "regime",
        compression_value: str = "COMPRESSION",
    ) -> List[Dict[str, Any]]:
        """Identify contiguous runs of compression and extract their characteristics."""
        if df.empty or compression_col not in df.columns:
            return []

        if compression_value is None or compression_value == "COMPRESSION":
            is_comp = df[compression_col].astype(str).str.contains("COMPRESSION").to_numpy()
        else:
            is_comp = (df[compression_col] == compression_value).to_numpy()
        n = len(df)
        episodes = []

        in_episode = False
        start_idx = 0

        for i in range(n):
            if is_comp[i] and not in_episode:
                in_episode = True
                start_idx = i
            elif not is_comp[i] and in_episode:
                in_episode = False
                end_idx = i - 1
                duration = end_idx - start_idx + 1
                if duration >= 6:  # At least 30 minutes of compression
                    episodes.append((start_idx, end_idx, duration))

        if in_episode:
            end_idx = n - 1
            duration = end_idx - start_idx + 1
            if duration >= 6:
                episodes.append((start_idx, end_idx, duration))

        logger.info(f"Identified {len(episodes)} compression episodes (>= 30m duration).")

        analyzed_episodes = []
        close = df["close"].to_numpy()
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        comp_ratio = df["volatility_compression_ratio"].to_numpy() if "volatility_compression_ratio" in df.columns else np.ones(n)
        volume = df["volume"].to_numpy() if "volume" in df.columns else np.ones(n)
        taker_ratio = df["volume_buy_ratio"].to_numpy() if "volume_buy_ratio" in df.columns else np.full(n, 0.5)

        for start_idx, end_idx, duration in episodes:
            # Episode features
            c_start = close[start_idx]
            c_end = close[end_idx]
            min_comp = float(np.min(comp_ratio[start_idx:end_idx + 1]))
            mean_comp = float(np.mean(comp_ratio[start_idx:end_idx + 1]))
            mean_vol = float(np.mean(volume[start_idx:end_idx + 1]))

            # Volume trend inside episode (first half vs second half)
            half = max(1, duration // 2)
            vol_first_half = np.mean(volume[start_idx:start_idx + half])
            vol_second_half = np.mean(volume[start_idx + half:end_idx + 1])
            vol_trend_ratio = float(vol_second_half / vol_first_half) if vol_first_half > 0 else 1.0

            # Taker buy drift
            taker_first_half = np.mean(taker_ratio[start_idx:start_idx + half])
            taker_second_half = np.mean(taker_ratio[start_idx + half:end_idx + 1])
            taker_drift = float(taker_second_half - taker_first_half)

            # Forward outcome after compression ends
            fwd_end = min(n - 1, end_idx + self.expansion_horizon)
            if fwd_end <= end_idx:
                continue

            max_fwd_high = np.max(high[end_idx + 1:fwd_end + 1])
            min_fwd_low = np.min(low[end_idx + 1:fwd_end + 1])
            final_fwd_close = close[fwd_end]

            up_move = (max_fwd_high - c_end) / c_end
            down_move = (c_end - min_fwd_low) / c_end
            net_return = (final_fwd_close - c_end) / c_end

            # Categorize breakout
            if up_move >= self.expansion_threshold and up_move > down_move * 1.3:
                category = "CATEGORY_A_UPWARD_EXPANSION"
            elif down_move >= self.expansion_threshold and down_move > up_move * 1.3:
                category = "CATEGORY_B_DOWNWARD_EXPANSION"
            else:
                category = "CATEGORY_C_FALSE_OR_CHOP"

            analyzed_episodes.append({
                "start_idx": start_idx,
                "end_idx": end_idx,
                "start_time": str(df.at[start_idx, "datetime_open"]) if "datetime_open" in df.columns else start_idx,
                "end_time": str(df.at[end_idx, "datetime_open"]) if "datetime_open" in df.columns else end_idx,
                "duration_candles": duration,
                "duration_hours": round(duration * 5 / 60, 2),
                "min_compression_ratio": round(min_comp, 4),
                "mean_compression_ratio": round(mean_comp, 4),
                "vol_trend_ratio": round(vol_trend_ratio, 4),
                "mean_taker_buy_ratio": round(float(np.mean(taker_ratio[start_idx:end_idx + 1])), 4),
                "taker_drift": round(taker_drift, 4),
                "up_move_max": round(up_move, 4),
                "down_move_max": round(down_move, 4),
                "net_return_24h": round(net_return, 4),
                "outcome_category": category,
            })

        return analyzed_episodes
