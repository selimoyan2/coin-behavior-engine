"""Script to run complete derivatives ingestion and normalization."""

import time
from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.derivatives.ingestion import DerivativesIngestionEngine
from coin_behavior_engine.derivatives.data_catalog import DerivativesDataCatalog


def main():
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("STARTING SPRINT 03 DERIVATIVES DATA INGESTION & FORENSICS")
    logger.info("=" * 70)

    # 1. Generate forensic data catalog & quality documentation
    catalog = DerivativesDataCatalog()
    catalog.generate_catalog()
    catalog.generate_quality_audit()
    catalog.generate_coverage_matrix()

    # 2. Ingest & normalize data
    engine = DerivativesIngestionEngine(max_workers=32)

    logger.info("1/3 Syncing Perpetual 5m Klines...")
    df_perp = engine.sync_perpetual_klines(2021, 2026)
    logger.info(f"Perpetual klines: {len(df_perp):,} rows, start={df_perp['datetime_open'].min()}, end={df_perp['datetime_open'].max()}")

    logger.info("2/3 Syncing Funding Rates...")
    df_fund = engine.sync_funding_rates(2021, 2026)
    logger.info(f"Funding rates: {len(df_fund):,} records, start={df_fund['datetime_calc'].min()}, end={df_fund['datetime_calc'].max()}")

    logger.info("3/3 Syncing Daily Metrics (OI, Positioning, Taker Ratio)...")
    df_met = engine.sync_metrics(2021, 2026)
    logger.info(f"Daily metrics: {len(df_met):,} records, start={df_met['datetime_open'].min()}, end={df_met['datetime_open'].max()}")

    elapsed = time.time() - t0
    logger.info("=" * 70)
    logger.info(f"DERIVATIVES INGESTION COMPLETED IN {elapsed:.2f}s")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
