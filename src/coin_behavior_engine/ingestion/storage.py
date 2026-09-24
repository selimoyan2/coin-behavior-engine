"""Immutable raw market data storage manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime

RAW_COLUMNS = [
    "timestamp_open",
    "open",
    "high",
    "low",
    "close",
    "base_volume",
    "timestamp_close",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]


class RawStorageManager:
    """Manages raw immutable candle data with deduplication and provenance metadata."""

    def __init__(self, raw_dir: str | Path = "data/raw"):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def get_raw_filepath(self, symbol: str, interval: str) -> Path:
        """Standardized raw storage file path."""
        return self.raw_dir / f"{symbol.lower()}_{interval}_raw.parquet"

    def get_metadata_filepath(self, symbol: str, interval: str) -> Path:
        """Metadata JSON file path tracking ingestion history and provenance."""
        return self.raw_dir / f"{symbol.lower()}_{interval}_metadata.json"

    def load_raw_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load raw candles if present; otherwise return an empty DataFrame with schema."""
        filepath = self.get_raw_filepath(symbol, interval)
        if not filepath.exists():
            return pd.DataFrame(columns=RAW_COLUMNS[:11])
        df = pd.read_parquet(filepath)
        return df

    def get_latest_stored_timestamp(self, symbol: str, interval: str) -> Optional[int]:
        """Return the maximum timestamp_open (ms) currently recorded in raw storage."""
        df = self.load_raw_data(symbol, interval)
        if df.empty or "timestamp_open" not in df.columns:
            return None
        return int(df["timestamp_open"].max())

    def save_raw_batches(
        self,
        symbol: str,
        interval: str,
        new_records: List[List[Any]],
        source_provider: str = "binance"
    ) -> int:
        """
        Merge new records into raw storage idempotently.
        Ensures immutability of existing data and deduplication on timestamp_open.
        """
        if not new_records:
            return 0

        new_df = pd.DataFrame(new_records, columns=RAW_COLUMNS[:len(new_records[0])])
        # Drop ignore column if present
        if "ignore" in new_df.columns:
            new_df = new_df.drop(columns=["ignore"])

        existing_df = self.load_raw_data(symbol, interval)
        if not existing_df.empty:
            combined = pd.concat([existing_df, new_df], ignore_index=True)
            # Deduplicate by timestamp_open, keeping the first occurrence
            combined = combined.drop_duplicates(subset=["timestamp_open"], keep="first")
        else:
            combined = new_df.drop_duplicates(subset=["timestamp_open"], keep="first")

        combined = combined.sort_values("timestamp_open").reset_index(drop=True)

        target_file = self.get_raw_filepath(symbol, interval)
        # Atomic write to prevent file corruption
        temp_file = target_file.with_suffix(".tmp.parquet")
        combined.to_parquet(temp_file, index=False)
        temp_file.replace(target_file)

        # Update metadata provenance
        meta_file = self.get_metadata_filepath(symbol, interval)
        metadata = {
            "symbol": symbol,
            "interval": interval,
            "provider": source_provider,
            "total_records": len(combined),
            "earliest_timestamp": int(combined["timestamp_open"].min()) if not combined.empty else None,
            "latest_timestamp": int(combined["timestamp_open"].max()) if not combined.empty else None,
            "earliest_utc": str(to_utc_datetime(int(combined["timestamp_open"].min()))) if not combined.empty else None,
            "latest_utc": str(to_utc_datetime(int(combined["timestamp_open"].max()))) if not combined.empty else None,
            "last_updated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        added = len(combined) - len(existing_df)
        logger.info(f"Raw storage updated: {len(combined)} total records (+{added} new).")
        return added
