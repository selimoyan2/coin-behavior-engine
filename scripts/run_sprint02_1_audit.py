"""Master Execution Script for Sprint 02.1: Directional Information & Historical Analogue Integrity Audit.

Runs all 26 audit dimensions and compiles SPRINT_02_1_DIRECTIONAL_AUDIT.md.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.audit.directional import DirectionalAuditor


def main() -> None:
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("STARTING SPRINT 02.1 DIRECTIONAL & ANALOGUE INTEGRITY AUDIT")
    logger.info("=" * 70)

    cache_path = Path("data/derived/features_with_outcomes_5m.parquet")
    if not cache_path.exists():
        logger.error(f"Required features cache {cache_path} not found. Please precompute features first.")
        sys.exit(1)

    logger.info(f"Loading cached dataset from {cache_path}...")
    df = pd.read_parquet(cache_path)
    logger.info(f"Loaded {len(df):,} candles with {len(df.columns)} columns across partitions.")

    import argparse
    parser = argparse.ArgumentParser(description="Sprint 02.1 Directional Audit Runner")
    parser.add_argument("--force-rerun", action="store_true", help="Force re-execution of all 26 audits")
    args = parser.parse_args()

    reports_dir = Path("data/reports/sprint02_1")
    auditor = DirectionalAuditor(df, reports_dir=reports_dir)

    expected_csvs = [
        "baseline_comparison.csv",
        "horizon_directional_stability.csv",
        "yearly_directional_stability.csv",
        "placebo_test_results.csv",
        "directional_confidence_intervals.csv",
        "probability_calibration.csv",
        "taker_buy_volume_audit.csv",
        "multitimeframe_claim_audit.csv",
    ]
    all_csvs_present = all((reports_dir / f).exists() for f in expected_csvs)

    if not args.force_rerun and all_csvs_present:
        logger.info("Found existing generated audit artifacts. Compiling markdown report from disk...")
        auditor.compile_report_from_disk()
    else:
        logger.info("Executing all 26 audit dimensions...")
        auditor.run_all_audits(sample_size=200)

    elapsed = time.time() - t0
    logger.info("=" * 70)
    logger.info(f"AUDIT RUN COMPLETED IN {elapsed:.2f}s")
    logger.info("=" * 70)

    # Verify generated report artifacts
    expected_artifacts = [
        "directional_result_reconstruction.json",
        "direction_definition.json",
        "class_balance_by_year.csv",
        "class_balance_by_regime.csv",
        "baseline_comparison.csv",
        "temporal_causality_audit.json",
        "embargo_sensitivity.csv",
        "event_deduplication_sensitivity.csv",
        "knn_sensitivity.csv",
        "distance_metric_sensitivity.csv",
        "macro_regime_contribution.csv",
        "yearly_directional_stability.csv",
        "walkforward_directional_results.csv",
        "directional_confidence_intervals.csv",
        "vote_strength_analysis.csv",
        "probability_calibration.csv",
        "coverage_information_curve.csv",
        "up_down_asymmetry.csv",
        "regime_conditional_performance.csv",
        "horizon_directional_stability.csv",
        "placebo_test_results.csv",
        "feature_ablation.csv",
        "taker_buy_volume_audit.csv",
        "multitimeframe_claim_audit.csv",
        "multiple_testing_audit.csv",
        "parameter_inventory_sprint02_1.csv",
        "SPRINT_02_1_DIRECTIONAL_AUDIT.md",
    ]

    all_exist = True
    for art in expected_artifacts:
        p = reports_dir / art
        if p.exists():
            sz = p.stat().st_size
            logger.info(f"  [OK] {art:<42} ({sz:,} bytes)")
        else:
            logger.error(f"  [FAIL] Missing artifact: {art}")
            all_exist = False

    if all_exist:
        logger.info("All 27 required artifacts generated successfully.")
    else:
        logger.error("Some artifacts were missing!")
        sys.exit(1)


if __name__ == "__main__":
    main()
