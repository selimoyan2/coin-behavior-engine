"""Unified Command Line Interface for Coin Behavior Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

from coin_behavior_engine.config.loader import load_config
from coin_behavior_engine.ingestion.binance import BinanceMarketDataProvider
from coin_behavior_engine.ingestion.storage import RawStorageManager
from coin_behavior_engine.normalization.canonical import CanonicalNormalizer
from coin_behavior_engine.reporting.charts import ResearchChartGenerator
from coin_behavior_engine.reporting.markdown import ResearchReportGenerator
from coin_behavior_engine.research.behavior_map import BehaviorMapEngine
from coin_behavior_engine.timeframes.aggregator import TimeframeAggregator
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_ms
from coin_behavior_engine.validation.reporter import DataQualityReporter
from coin_behavior_engine.validation.validator import DataValidator


def cmd_download(config):
    """Download historical 5m BTCUSDT candles from Binance."""
    logger.info("--- STEP 1: DOWNLOAD RAW 5M BTCUSDT DATA ---")
    storage = RawStorageManager(config.paths.raw_dir)
    provider = BinanceMarketDataProvider(
        base_url=config.data_source.base_url,
        klines_endpoint=config.data_source.klines_endpoint,
        rate_limit_pause_sec=config.data_source.rate_limit_pause_sec,
        max_retries=config.data_source.max_retries,
        timeout_sec=config.data_source.timeout_sec,
    )

    symbol = config.asset.symbol
    interval = config.asset.primary_timeframe

    # Determine start timestamp (resumable)
    latest_stored = storage.get_latest_stored_timestamp(symbol, interval)
    if latest_stored:
        start_ts = latest_stored + 1
        logger.info(f"Resuming download from existing raw timestamp: {start_ts}")
    else:
        start_ts = to_utc_ms(config.time_range.start_utc)
        logger.info(f"Starting fresh download from {config.time_range.start_utc} ({start_ts} ms)")

    end_ts = to_utc_ms(config.time_range.end_utc) if config.time_range.end_utc else None

    # Fetch in batches of 1000
    all_new_records = []
    current_start = start_ts
    batch_count = 0

    while True:
        records = provider.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=current_start,
            end_time=end_ts,
            limit=config.data_source.request_limit,
        )
        if not records:
            break

        all_new_records.extend(records)
        batch_count += 1
        last_kline_open = records[-1][0]
        logger.info(f"Fetched batch {batch_count}: {len(records)} candles (last open: {last_kline_open})")

        # If fetched less than limit, we reached the latest available candle
        if len(records) < config.data_source.request_limit:
            break

        # Move to next candle
        current_start = last_kline_open + 1

    # Save to immutable raw storage
    added = storage.save_raw_batches(symbol, interval, all_new_records, source_provider="binance")
    provider.close()
    logger.info(f"Download complete. Total new raw records added: {added}")
    return added


def cmd_validate(config):
    """Normalize raw data to canonical format and validate quality."""
    logger.info("--- STEP 2: NORMALIZE & VALIDATE DATASET ---")
    storage = RawStorageManager(config.paths.raw_dir)
    normalizer = CanonicalNormalizer(config.paths.normalized_dir)
    validator = DataValidator(
        expected_interval_ms=300_000,
        max_allowed_consecutive_missing=config.validation.max_allowed_consecutive_missing,
        strict_ohlc_check=config.validation.strict_ohlc_check,
    )
    reporter = DataQualityReporter(config.paths.reports_dir)

    raw_df = storage.load_raw_data(config.asset.symbol, config.asset.primary_timeframe)
    if raw_df.empty:
        raise RuntimeError("No raw data found. Run 'download' command first.")

    canonical_df = normalizer.normalize(raw_df, symbol=config.asset.symbol)
    normalizer.save_canonical(canonical_df, symbol=config.asset.symbol, interval=config.asset.primary_timeframe)

    report = validator.validate(canonical_df)
    reporter.save_report(report)
    reporter.print_summary(report)
    return report


def cmd_build(config):
    """Aggregate canonical 5m candles into 15m, 1h, 4h, 1d timeframes."""
    logger.info("--- STEP 3: BUILD HIGHER TIMEFRAMES ---")
    normalizer = CanonicalNormalizer(config.paths.normalized_dir)
    aggregator = TimeframeAggregator(config.paths.derived_dir)

    canonical_df = normalizer.load_canonical(config.asset.symbol, config.asset.primary_timeframe)
    timeframe_dfs = aggregator.build_all_timeframes(
        canonical_df,
        symbol=config.asset.symbol,
        timeframes=config.asset.derived_timeframes
    )
    logger.info(f"Built {len(timeframe_dfs)} higher timeframes successfully.")
    return timeframe_dfs


def cmd_research(config):
    """Run feature extraction, regime detection, event discovery, behavior map, and report generation."""
    logger.info("--- STEP 4: RUN RESEARCH PIPELINE & BEHAVIOR MAP ---")
    normalizer = CanonicalNormalizer(config.paths.normalized_dir)
    aggregator = TimeframeAggregator(config.paths.derived_dir)

    # Load canonical 5m
    canonical_5m = normalizer.load_canonical(config.asset.symbol, config.asset.primary_timeframe)

    timeframe_dfs = {"5m": canonical_5m}
    for tf in config.asset.derived_timeframes:
        tf_path = Path(config.paths.derived_dir) / f"{config.asset.symbol.lower()}_{tf}.parquet"
        if tf_path.exists():
            timeframe_dfs[tf] = pd.read_parquet(tf_path)
        else:
            timeframe_dfs[tf] = aggregator.aggregate(canonical_5m, tf)

    # Run Behavior Map Engine
    engine = BehaviorMapEngine(config)
    results = engine.run(timeframe_dfs)

    # Generate charts
    chart_gen = ResearchChartGenerator(config.paths.charts_dir)
    features_5m = results["features_by_tf"]["5m"]
    events_5m = results["events_5m"]
    regimes_5m = results["regimes_5m"]
    sept21 = results["september_21_audit"]

    chart_gen.generate_all_charts(features_5m, events_5m, regimes_5m, sept21)

    # Generate SPRINT_01_RESEARCH_REPORT.md
    reporter = DataQualityReporter(config.paths.reports_dir)
    data_quality_path = Path(config.paths.reports_dir) / "data_quality.json"
    if data_quality_path.exists():
        import json
        with open(data_quality_path, "r", encoding="utf-8") as f:
            data_quality = json.load(f)
    else:
        data_quality = {}

    report_gen = ResearchReportGenerator(config.paths.reports_dir)
    report_gen.generate_report(
        data_quality=data_quality,
        behavior_summary=results["behavior_summary"],
        events_df=events_5m,
        regimes_df=regimes_5m,
        global_events_df=results["global_events"],
        sept21_audit=sept21,
    )

    logger.info("Sprint 01 Research Pipeline completed successfully.")
    return results


def main():
    parser = argparse.ArgumentParser(description="Coin Behavior Engine CLI")
    parser.add_argument("command", choices=["download", "validate", "build", "research", "all"], help="Command to run")
    parser.add_argument("--config", default="config/research.yaml", help="Path to research.yaml")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "download":
        cmd_download(config)
    elif args.command == "validate":
        cmd_validate(config)
    elif args.command == "build":
        cmd_build(config)
    elif args.command == "research":
        cmd_research(config)
    elif args.command == "all":
        cmd_download(config)
        cmd_validate(config)
        cmd_build(config)
        cmd_research(config)


if __name__ == "__main__":
    main()
