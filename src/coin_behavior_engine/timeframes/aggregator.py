"""Timeframe aggregation engine building 15m, 1h, 4h, 1d candles from 5m data."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import pandas as pd

from coin_behavior_engine.utils.logging import logger

TIMEFRAME_FREQ_MAP = {
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


class TimeframeAggregator:
    """Aggregates canonical 5-minute candles into higher-order timeframes."""

    def __init__(self, derived_dir: str | Path = "data/derived"):
        self.derived_dir = Path(derived_dir)
        self.derived_dir.mkdir(parents=True, exist_ok=True)

    def aggregate(self, df_5m: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """
        Aggregate 5m candles into target_timeframe.
        open=first, high=max, low=min, close=last, volumes=sum, trade_count=sum.
        """
        if target_timeframe not in TIMEFRAME_FREQ_MAP:
            raise ValueError(f"Unsupported timeframe: {target_timeframe}. Choose from {list(TIMEFRAME_FREQ_MAP.keys())}")

        freq = TIMEFRAME_FREQ_MAP[target_timeframe]
        df = df_5m.copy()

        # Set datetime_open as index for resampling
        if not isinstance(df.index, pd.DatetimeIndex):
            if "datetime_open" not in df.columns:
                df["datetime_open"] = pd.to_datetime(df["timestamp_open"], unit="ms", utc=True)
            df = df.set_index("datetime_open")

        agg_dict: dict[str, str] = {
            "timestamp_open": "first",
            "timestamp_close": "last",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }

        # Optional volume / trades columns
        optional_sums = [
            "quote_volume",
            "trade_count",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]
        for col in optional_sums:
            if col in df.columns:
                agg_dict[col] = "sum"

        # Resample closed='left', label='left' aligns with standard exchange candle boundaries
        resampled = df.resample(freq, closed="left", label="left").agg(agg_dict)

        # Drop empty bins (e.g. gaps where no trades occurred)
        resampled = resampled.dropna(subset=["close"]).reset_index()

        # Re-derive datetime_close and format types
        resampled["timestamp_open"] = resampled["timestamp_open"].astype("int64")
        resampled["timestamp_close"] = resampled["timestamp_close"].astype("int64")
        resampled["datetime_close"] = pd.to_datetime(resampled["timestamp_close"], unit="ms", utc=True)

        if "trade_count" in resampled.columns:
            resampled["trade_count"] = resampled["trade_count"].astype("int64")

        # Preserve symbol
        if "symbol" in df.columns:
            resampled["symbol"] = df["symbol"].iloc[0]

        resampled["timeframe"] = target_timeframe
        return resampled

    def build_all_timeframes(
        self,
        df_5m: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframes: List[str] | None = None
    ) -> Dict[str, pd.DataFrame]:
        """Generate and save all higher timeframes."""
        if timeframes is None:
            timeframes = ["15m", "1h", "4h", "1d"]

        results: Dict[str, pd.DataFrame] = {}
        for tf in timeframes:
            agg_df = self.aggregate(df_5m, tf)
            out_file = self.derived_dir / f"{symbol.lower()}_{tf}.parquet"
            agg_df.to_parquet(out_file, index=False)
            logger.info(f"Generated {tf} timeframe: {len(agg_df)} candles saved to {out_file}")
            results[tf] = agg_df

        return results
