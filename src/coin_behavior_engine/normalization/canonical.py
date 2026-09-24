"""Canonical dataset normalization ensuring explicit typing and chronological integrity."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime


class CanonicalNormalizer:
    """Normalizes raw market klines into strongly-typed canonical datasets."""

    def __init__(self, normalized_dir: str | Path = "data/normalized"):
        self.normalized_dir = Path(normalized_dir)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

    def normalize(self, raw_df: pd.DataFrame, symbol: str = "BTCUSDT") -> pd.DataFrame:
        """
        Convert raw dataframe into canonical representation.
        Enforces strict types, UTC datetimes, deduplication, and chronological sorting.
        """
        if raw_df.empty:
            raise ValueError("Cannot normalize empty raw dataset.")

        df = raw_df.copy()

        # Handle column names if raw has 'base_volume'
        rename_map = {
            "base_volume": "volume",
        }
        df = df.rename(columns=rename_map)

        # Explicit typing
        numeric_float_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]
        for col in numeric_float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

        # Trade count to int64
        if "trade_count" in df.columns:
            df["trade_count"] = pd.to_numeric(df["trade_count"], errors="coerce").fillna(0).astype("int64")

        # Timestamps
        df["timestamp_open"] = pd.to_numeric(df["timestamp_open"], errors="coerce").astype("int64")
        df["timestamp_close"] = pd.to_numeric(df["timestamp_close"], errors="coerce").astype("int64")

        # UTC datetimes
        df["datetime_open"] = pd.to_datetime(df["timestamp_open"], unit="ms", utc=True)
        df["datetime_close"] = pd.to_datetime(df["timestamp_close"], unit="ms", utc=True)

        # Deduplicate and sort chronologically
        df = df.drop_duplicates(subset=["timestamp_open"]).sort_values("timestamp_open").reset_index(drop=True)

        # Add asset metadata column
        df["symbol"] = symbol.upper()

        return df

    def save_canonical(self, df: pd.DataFrame, symbol: str, interval: str) -> Path:
        """Save normalized canonical parquet file."""
        target_path = self.normalized_dir / f"{symbol.lower()}_{interval}.parquet"
        temp_path = target_path.with_suffix(".tmp.parquet")
        df.to_parquet(temp_path, index=False)
        temp_path.replace(target_path)
        logger.info(f"Saved canonical dataset to {target_path} ({len(df)} records).")
        return target_path

    def load_canonical(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load normalized canonical dataset."""
        target_path = self.normalized_dir / f"{symbol.lower()}_{interval}.parquet"
        if not target_path.exists():
            raise FileNotFoundError(f"Canonical dataset {target_path} does not exist.")
        return pd.read_parquet(target_path)
