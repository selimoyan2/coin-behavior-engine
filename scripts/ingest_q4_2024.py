"""Ingest Q4 2024 (October, November, December 2024) BTCUSDT spot klines from Binance Vision.

Verifies SHA-256 against official checksum files.
Validates candle continuity and invariants (0 gaps, 0 duplicates).
Saves 5m, aggregates to 15m and 1h, and writes provenance records.
Reserved strictly as a genuinely untouched, chronological virgin holdout.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd

from coin_behavior_engine.research.historical.binance_archival_ingestion import (
    BinanceArchivalDownloader,
)
from coin_behavior_engine.research.historical.dataset_contract import (
    HistoricalDatasetStore,
    HistoricalMarketSpec,
)
from coin_behavior_engine.research.historical.timeframe_aggregator import (
    HistoricalTimeframeAggregator,
)
from coin_behavior_engine.research.historical.validation import (
    HistoricalCandleValidator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_q4_2024")


def main() -> None:
    downloader = BinanceArchivalDownloader(max_budget_mb=100.0)
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    validator = HistoricalCandleValidator()
    aggregator = HistoricalTimeframeAggregator(drop_incomplete_bars=True)

    all_5m_candles = []
    months = [10, 11, 12]

    for m in months:
        logger.info(f"Downloading and verifying BTCUSDT 2024-{m:02d}...")
        zip_bytes, sha256_hash, verified = downloader.download_and_verify_monthly_archive(
            symbol="BTCUSDT", interval="5m", year=2024, month=m
        )
        assert verified, f"Checksum verification failed for 2024-{m:02d}"
        candles = downloader.parse_archive_candles(zip_bytes)
        logger.info(f"Parsed {len(candles)} candles for 2024-{m:02d}")
        all_5m_candles.extend(candles)

    # Sort and validate all Q4 5m candles
    all_5m_candles.sort(key=lambda c: int(c["timestamp_open"]))
    val_report = validator.validate(all_5m_candles)
    logger.info(
        f"Validation report for Q4 2024 5m: is_valid={val_report.is_valid}, "
        f"gaps={val_report.gap_count}, total={val_report.total_candles}"
    )
    assert val_report.is_valid, f"Validation failed: {val_report.errors}"
    assert len(all_5m_candles) == 26496, f"Expected 26496 bars, got {len(all_5m_candles)}"

    # Convert 5m to DataFrame and save
    df_5m = pd.DataFrame(all_5m_candles)
    spec_5m = HistoricalMarketSpec(
        symbol="BTCUSDT",
        interval="5m",
        dataset_tag="q4_2024",
        start_timestamp_ms=int(df_5m["timestamp_open"].iloc[0]),
        end_timestamp_ms=int(df_5m["timestamp_open"].iloc[-1]),
    )
    prov_5m = store.save_dataset_atomic(spec_5m, df_5m, provenance_source="HISTORICAL_BINANCE_ARCHIVE_Q4_2024")
    logger.info(f"Saved 5m Q4 2024: {prov_5m.total_bars} bars, SHA-256: {prov_5m.sha256_checksum}")

    # Aggregate to 15m
    candles_15m, rep_15m = aggregator.aggregate(all_5m_candles, target_interval="15m")
    logger.info(f"Aggregated 15m: {len(candles_15m)} bars, vol_conserved={rep_15m.is_volume_conserved}")
    assert len(candles_15m) == 8832, f"Expected 8832 bars, got {len(candles_15m)}"
    assert rep_15m.is_volume_conserved, "15m volume not conserved"

    df_15m = pd.DataFrame(candles_15m)
    spec_15m = HistoricalMarketSpec(
        symbol="BTCUSDT",
        interval="15m",
        dataset_tag="q4_2024",
        start_timestamp_ms=int(df_15m["timestamp_open"].iloc[0]),
        end_timestamp_ms=int(df_15m["timestamp_open"].iloc[-1]),
    )
    prov_15m = store.save_dataset_atomic(spec_15m, df_15m, provenance_source="HISTORICAL_BINANCE_ARCHIVE_Q4_2024")
    logger.info(f"Saved 15m Q4 2024: {prov_15m.total_bars} bars, SHA-256: {prov_15m.sha256_checksum}")

    # Aggregate to 1h
    candles_1h, rep_1h = aggregator.aggregate(all_5m_candles, target_interval="1h")
    logger.info(f"Aggregated 1h: {len(candles_1h)} bars, vol_conserved={rep_1h.is_volume_conserved}")
    assert len(candles_1h) == 2208, f"Expected 2208 bars, got {len(candles_1h)}"
    assert rep_1h.is_volume_conserved, "1h volume not conserved"

    df_1h = pd.DataFrame(candles_1h)
    spec_1h = HistoricalMarketSpec(
        symbol="BTCUSDT",
        interval="1h",
        dataset_tag="q4_2024",
        start_timestamp_ms=int(df_1h["timestamp_open"].iloc[0]),
        end_timestamp_ms=int(df_1h["timestamp_open"].iloc[-1]),
    )
    prov_1h = store.save_dataset_atomic(spec_1h, df_1h, provenance_source="HISTORICAL_BINANCE_ARCHIVE_Q4_2024")
    logger.info(f"Saved 1h Q4 2024: {prov_1h.total_bars} bars, SHA-256: {prov_1h.sha256_checksum}")

    print("Q4 2024 Ingestion successfully completed!")


if __name__ == "__main__":
    main()
