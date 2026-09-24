"""Download historical 5m BTCUSDT candles from 2021-01-01 through 2025-12-31 and rebuild canonical datasets."""

from __future__ import annotations

import time
from pathlib import Path
import pandas as pd

from coin_behavior_engine.config.loader import load_config
from coin_behavior_engine.ingestion.binance import BinanceMarketDataProvider
from coin_behavior_engine.ingestion.storage import RawStorageManager
from coin_behavior_engine.normalization.canonical import CanonicalNormalizer
from coin_behavior_engine.timeframes.aggregator import TimeframeAggregator
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_ms, to_utc_datetime
from coin_behavior_engine.validation.validator import DataValidator


def download_historical_range(
    start_dt_str: str = "2021-01-01 00:00:00",
    end_dt_str: str = "2025-12-31 23:59:59",
    batch_size: int = 1000
):
    config = load_config()
    storage = RawStorageManager(config.paths.raw_dir)
    provider = BinanceMarketDataProvider(
        base_url=config.data_source.base_url,
        klines_endpoint=config.data_source.klines_endpoint,
        rate_limit_pause_sec=0.03,  # fast yet courteous
        max_retries=5,
        timeout_sec=15.0,
    )

    symbol = config.asset.symbol
    interval = config.asset.primary_timeframe

    start_ts = to_utc_ms(start_dt_str)
    end_ts = to_utc_ms(end_dt_str)

    logger.info(f"Targeting historical range: {start_dt_str} ({start_ts}) to {end_dt_str} ({end_ts})")

    # Check what we already have in raw storage
    existing_raw = storage.load_raw_data(symbol, interval)
    existing_timestamps = set()
    if not existing_raw.empty and "timestamp_open" in existing_raw.columns:
        existing_timestamps = set(existing_raw["timestamp_open"].astype("int64").values)
        logger.info(f"Found {len(existing_timestamps)} existing candles in raw storage.")

    current_start = start_ts
    total_downloaded = 0
    buffer = []
    save_interval = 25000  # flush to disk every 25 batches

    t0 = time.time()
    call_count = 0

    while current_start <= end_ts:
        records = provider.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=current_start,
            end_time=end_ts,
            limit=batch_size,
        )
        call_count += 1

        if not records:
            logger.info("No more records returned from Binance.")
            break

        # Filter out records already in existing_timestamps
        new_records = [r for r in records if int(r[0]) not in existing_timestamps]
        for r in new_records:
            existing_timestamps.add(int(r[0]))
        buffer.extend(new_records)
        total_downloaded += len(new_records)

        last_open_time = int(records[-1][0])
        # Next start time is after the last candle's open time
        next_start = last_open_time + (5 * 60 * 1000)

        if call_count % 25 == 0 or len(buffer) >= save_interval:
            cur_dt = to_utc_datetime(last_open_time)
            elapsed = time.time() - t0
            logger.info(
                f"Batch {call_count}: Reached {cur_dt} (added {len(buffer)} new, total downloaded: {total_downloaded}) "
                f"[{elapsed:.1f}s elapsed]"
            )
            if buffer:
                storage.save_raw_batches(symbol, interval, buffer, source_provider="binance")
                buffer = []

        if next_start <= current_start:
            logger.warning(f"Timestamp did not advance ({current_start} -> {next_start}). Stopping loop.")
            break

        current_start = next_start

    # Flush remaining buffer
    if buffer:
        storage.save_raw_batches(symbol, interval, buffer, source_provider="binance")

    provider.close()
    elapsed = time.time() - t0
    logger.info(f"Download complete! Added {total_downloaded} historical candles in {elapsed:.1f}s ({call_count} calls).")


def build_canonical_and_derived():
    config = load_config()
    storage = RawStorageManager(config.paths.raw_dir)
    normalizer = CanonicalNormalizer(config.paths.normalized_dir)
    symbol = config.asset.symbol
    interval = config.asset.primary_timeframe

    logger.info("Loading complete raw dataset...")
    raw_df = storage.load_raw_data(symbol, interval)
    logger.info(f"Loaded raw dataset with {len(raw_df)} candles.")

    logger.info("Normalizing full 2021-2026 dataset...")
    norm_df = normalizer.normalize(raw_df, symbol=symbol)
    normalizer.save_canonical(norm_df, symbol=symbol, interval=interval)
    logger.info(f"Saved normalized 5m dataset with {len(norm_df)} rows. Range: {norm_df['datetime_open'].min()} to {norm_df['datetime_open'].max()}")

    # Validate normalized data
    validator = DataValidator(expected_interval_ms=300_000)
    report = validator.validate(norm_df)
    logger.info(
        f"Validation Result: Passed={report['validation_passed']}, "
        f"Missing={report['missing_candles_count']}, Severity={report['severity_summary']}"
    )

    logger.info("Aggregating multi-timeframe datasets (15m, 1h, 4h, 1d)...")
    aggregator = TimeframeAggregator(derived_dir=config.paths.derived_dir)
    derived = aggregator.build_all_timeframes(norm_df, symbol=symbol)
    for tf, df_tf in derived.items():
        logger.info(f"Derived {tf}: {len(df_tf)} candles ({df_tf['datetime_open'].min()} to {df_tf['datetime_open'].max()})")


if __name__ == "__main__":
    download_historical_range("2021-01-01 00:00:00", "2025-12-31 23:59:59")
    build_canonical_and_derived()
