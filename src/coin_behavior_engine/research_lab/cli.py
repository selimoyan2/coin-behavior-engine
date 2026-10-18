"""Command-line interface and reproducible runner for CBE Research Lab.

Sprint 11.04: Research Integrity, Verified Market Context & First Reliable Strategy Benchmark.
Provides autonomous, reproducible execution of data acquisition, boundary reconciliation,
quality audit, HTF pattern discovery, strategy evaluation, counterfactual analysis, and reporting.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    CaseStudyResult,
    DecisionAction,
    DecisionMode,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    MarketRegimeType,
    ProbabilisticPrediction,
    ResearchDecision,
    SimulationRunResult,
)
from coin_behavior_engine.research_lab.counterfactuals import CounterfactualAnalyzer
from coin_behavior_engine.research_lab.data_quality import DataQualityValidator
from coin_behavior_engine.research_lab.evaluation import StrategyEvaluator
from coin_behavior_engine.research_lab.event_alignment import EventMarketAligner
from coin_behavior_engine.research_lab.event_intelligence import EventIntelligenceStore
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.historical_data import (
    BinanceHistoricalAdapter,
    LiveCaptureEvidenceAdapter,
    TimeframeAggregator,
)
from coin_behavior_engine.research_lab.pattern_engine import BehavioralPatternEngine
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.reporting import ResearchLabReporter
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cbe_research_lab.cli")


def resolve_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN_COMMIT"


def run_research_pipeline(
    symbol: str = "BTCUSDT",
    days: int = 25,
    output_dir: Optional[Path] = None,
    offline_parquet_path: Optional[Path] = None,
    evidence_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute complete end-to-end research lab workflow for Sprint 11.04."""
    config = ResearchLabConfig()
    if output_dir:
        config.output_dir = output_dir
    config.output_dir.mkdir(parents=True, exist_ok=True)

    git_commit = resolve_git_commit()
    logger.info(f"=== CBE Research Lab Pipeline (Commit: {git_commit[:8]}) ===")

    # ---------------------------------------------------------
    # Gate B: Historical Market Data Acquisition & Boundary Reconciliation
    # ---------------------------------------------------------
    adapter = BinanceHistoricalAdapter(config)
    cache_file = config.data_dir / f"binance_{symbol}_1m_recent.parquet"
    candles_1m: List[CandleData] = []

    # Priority 1: Check if already cached
    if cache_file.is_file():
        logger.info(f"Loading cached 1m candles from {cache_file}...")
        try:
            candles_1m = adapter.load_from_cache(cache_file)
        except Exception as e:
            logger.warning(f"Could not load cache: {e}. Re-acquiring...")

    # Priority 2: Fetch via Binance public REST if online and cache empty
    if not candles_1m and config.allow_network_download:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = now_ms - (days * 86_400 * 1000)
        logger.info(f"Acquiring {days} days of {symbol} 1m candles from Binance Spot REST API...")
        try:
            candles_1m = adapter.fetch_range(
                symbol=symbol,
                interval="1m",
                start_time_ms=start_ms,
                end_time_ms=now_ms,
                progress_callback=lambda count, last_utc: logger.info(f"  Fetched {count:,} candles (latest: {last_utc})"),
            )
            if candles_1m:
                adapter.save_to_cache(candles_1m, cache_file)
        except Exception as e:
            logger.warning(f"Live network acquisition failed: {e}.")

    if not candles_1m:
        raise RuntimeError("No market data available: cache file not found and network download failed.")

    # Timeframe Aggregation: Enforce strict boundary completeness (no partial boundary buckets)
    logger.info(f"Reconciling {len(candles_1m):,} 1m candles into strictly closed 5m, 1h, and 4h series...")
    candles_5m = TimeframeAggregator.aggregate(candles_1m, target_interval="5m", symbol=symbol, allow_partial_boundaries=False)
    candles_1h = TimeframeAggregator.aggregate(candles_5m, target_interval="1h", symbol=symbol, allow_partial_boundaries=False)
    candles_4h = TimeframeAggregator.aggregate(candles_5m, target_interval="4h", symbol=symbol, allow_partial_boundaries=False)

    logger.info(f"Dataset reconciled: {len(candles_5m):,} complete 5m candles ({candles_5m[0].datetime_open_utc} -> {candles_5m[-1].datetime_close_utc}).")
    logger.info(f"Higher timeframes: {len(candles_1h):,} 1h candles, {len(candles_4h):,} 4h candles.")

    # ---------------------------------------------------------
    # Gate B.1: Data Quality Audit
    # ---------------------------------------------------------
    logger.info("Auditing dataset quality & OHLCV invariants...")
    quality_report = DataQualityValidator.validate(candles_5m, symbol=symbol, interval="5m")
    quality_file = config.output_dir / "dataset_quality.json"
    quality_report.save_json(quality_file)
    logger.info(f"Data quality audit completed: passed={quality_report.passed}, gaps={quality_report.gaps_count}, inversions={quality_report.ohlcv_inversions_count}")

    # ---------------------------------------------------------
    # Gate C: Feature Extraction with HTF Alignment & Divergences
    # ---------------------------------------------------------
    logger.info("Computing causal features with 1h/4h alignment and price-volume divergence...")
    features = MarketBehaviorFeatureEngine.compute_all(
        candles_5m,
        lookback_bars=24,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
    )

    # ---------------------------------------------------------
    # Gate D: Event Intelligence, Audit Verification & Export
    # ---------------------------------------------------------
    logger.info("Loading and auditing historical event intelligence catalog...")
    event_store = EventIntelligenceStore.load_curated_october_2026_events()
    all_events = event_store.all_events()

    # Export event_source_verification.csv
    event_verify_csv = config.output_dir / "event_source_verification.csv"
    EventIntelligenceStore.export_event_source_verification_csv(all_events, event_verify_csv)
    logger.info(f"Exported event source verification matrix to {event_verify_csv}")

    # Align events with timeline
    alignments = EventMarketAligner.align_events(all_events, candles_5m)
    timeline_csv = config.output_dir / "event_timeline.csv"
    EventMarketAligner.export_event_timeline_csv(alignments, timeline_csv)

    # ---------------------------------------------------------
    # Gate E: Behavioral Pattern Discovery
    # ---------------------------------------------------------
    logger.info("Scanning for empirical microstructure patterns...")
    pattern_matches: Dict[str, List[int]] = {
        "SHARP_DECLINE_VOLUME_EXHAUSTION": [],
        "SUPPORT_BREAKDOWN_FAILED_CONTINUATION": [],
        "BREAKOUT_WITH_VOLUME_CONFIRMATION": [],
        "HIGH_VOLATILITY_SELLOFF_STABILIZATION": [],
        "NEGATIVE_EVENT_ABSORPTION": [],
    }

    for idx in range(len(candles_5m)):
        c_utc = candles_5m[idx].datetime_open_utc
        obs = event_store.events_observable_at(c_utc, lookback_hours=12.0)
        pats = BehavioralPatternEngine.match_patterns_at_index(candles_5m, features, idx, observable_events=obs)
        for p in pats:
            if p in pattern_matches:
                pattern_matches[p].append(idx)

    discovered_patterns = []
    for pat_name, idx_list in pattern_matches.items():
        pat_obj = BehavioralPatternEngine.evaluate_pattern_distribution(
            pat_name, idx_list, candles_5m, horizon_bars=12
        )
        if pat_obj:
            discovered_patterns.append(pat_obj)

    pattern_csv = config.output_dir / "pattern_summary.csv"
    BehavioralPatternEngine.export_pattern_summary_csv(discovered_patterns, pattern_csv)

    # ---------------------------------------------------------
    # Gate F: Multi-Horizon Probabilistic Predictions & Evaluation
    # ---------------------------------------------------------
    logger.info("Generating multi-horizon probabilistic predictions (15m, 1h, 4h)...")
    predictions = []
    for idx in range(len(candles_5m)):
        c_utc = candles_5m[idx].datetime_open_utc
        obs = event_store.events_observable_at(c_utc, lookback_hours=12.0)
        active_pats = [p for p, idxs in pattern_matches.items() if idx in idxs]
        pred = ProbabilityEngine.generate_prediction(
            features[idx], active_pats, observable_events=obs if obs else None, prediction_horizon="1h"
        )
        predictions.append(pred)

    pred_csv = config.output_dir / "predictions.csv"
    ProbabilityEngine.export_predictions_csv(predictions, pred_csv)

    # Evaluate predictions against forward outcomes
    logger.info("Evaluating forward prediction accuracy and calibration...")
    pred_eval_rows = ProbabilityEngine.evaluate_predictions(predictions, candles_5m, horizon_bars=12)
    pred_eval_csv = config.output_dir / "prediction_evaluation.csv"
    ProbabilityEngine.export_prediction_evaluation_csv(pred_eval_rows, pred_eval_csv)
    logger.info(f"Exported prediction evaluation to {pred_eval_csv}")

    # ---------------------------------------------------------
    # Gate G & H: Multi-Strategy Historical Simulation & Benchmarking
    # ---------------------------------------------------------
    logger.info("Executing reconciled historical paper trading simulations (Strategies A, B, C)...")
    evaluator = StrategyEvaluator(config)
    sim_results = evaluator.run_strategy_comparison(candles_5m, features, events=all_events)

    comparison_df = evaluator.generate_comparison_table(sim_results)
    comparison_csv = config.output_dir / "corrected_strategy_comparison.csv"
    evaluator.export_comparison_csv(comparison_df, comparison_csv)
    logger.info(f"Exported corrected strategy comparison table to {comparison_csv}")

    # Also keep strategy_comparison.csv updated for compatibility
    evaluator.export_comparison_csv(comparison_df, config.output_dir / "strategy_comparison.csv")

    # Run Chronological Split Evaluations (Train 50%, Val 25%, Test 25%)
    logger.info("Running chronological out-of-sample split evaluations...")
    split_results = evaluator.run_split_evaluation(candles_5m, features, events=all_events)

    # Run Parameter Sensitivity Tests
    logger.info("Running fee and slippage sensitivity tests...")
    sensitivity_df = evaluator.run_sensitivity_tests(candles_5m, features)

    # ---------------------------------------------------------
    # Gate I: Retrospective Counterfactual Analysis
    # ---------------------------------------------------------
    logger.info("Conducting retrospective counterfactual trade analysis...")
    strat_a = sim_results["Strategy_A_Technical_Only"]
    trades_for_cf = strat_a.trades if strat_a.trades else []
    cf_records = CounterfactualAnalyzer.analyze_significant_trades(
        trades=trades_for_cf,
        candles=candles_5m,
        features=features,
        top_n=10,
    )
    cf_csv = config.output_dir / "trade_counterfactuals.csv"
    CounterfactualAnalyzer.export_counterfactuals_csv(cf_records, cf_csv)
    logger.info(f"Exported counterfactual trade analysis to {cf_csv}")

    # Export execution trades and equity curves
    trades_csv = config.output_dir / "hypothetical_trades.csv"
    HistoricalPaperSimulator.export_trades_csv(strat_a.trades, trades_csv)
    equity_csv = config.output_dir / "equity_curve.csv"
    HistoricalPaperSimulator.export_equity_series_csv(strat_a.equity_series, equity_csv)

    # ---------------------------------------------------------
    # Gate J: Visualizations & Comprehensive Markdown Deliverables
    # ---------------------------------------------------------
    logger.info("Rendering strategy equity curves comparison chart...")
    chart_png = config.output_dir / "strategy_equity_curves.png"
    ResearchLabReporter.plot_equity_and_drawdown(sim_results, candles_5m, chart_png)
    # Also update equity_curves.png for compatibility
    ResearchLabReporter.plot_equity_and_drawdown(sim_results, candles_5m, config.output_dir / "equity_curves.png")

    logger.info("Generating research integrity audit report...")
    audit_md = config.output_dir / "research_integrity_audit.md"
    ResearchLabReporter.generate_integrity_audit_markdown(audit_md)

    logger.info("Generating empirical market behavior findings report...")
    findings_md = config.output_dir / "market_behavior_findings.md"
    ResearchLabReporter.generate_market_behavior_findings_markdown(findings_md)

    logger.info("Generating Sprint 11.04 master research report...")
    report_md = config.output_dir / "research_report_11_04.md"
    ResearchLabReporter.generate_research_report_11_04_markdown(
        symbol=symbol,
        interval="5m",
        start_utc=candles_5m[0].datetime_open_utc,
        end_utc=candles_5m[-1].datetime_close_utc,
        total_candles=len(candles_5m),
        results=sim_results,
        comparison_df=comparison_df,
        split_results=split_results,
        sensitivity_df=sensitivity_df,
        output_file=report_md,
    )

    # Generate run manifest
    manifest_json = config.output_dir / "run_manifest_11_04.json"
    ResearchLabReporter.generate_run_manifest(
        symbol=symbol,
        interval="5m",
        candle_count=len(candles_5m),
        start_utc=candles_5m[0].datetime_open_utc,
        end_utc=candles_5m[-1].datetime_close_utc,
        git_commit=git_commit,
        results=sim_results,
        output_file=manifest_json,
    )

    logger.info("=== CBE Research Lab Pipeline Completed Successfully ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(config.output_dir),
        "total_candles": len(candles_5m),
        "results": sim_results,
        "split_results": split_results,
    }


def main():
    parser = argparse.ArgumentParser(description="CBE Research Lab Runner — Sprint 11.04")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument("--days", type=int, default=25, help="Number of days to acquire and analyze (default: 25)")
    parser.add_argument("--output-dir", default="research_outputs", help="Output directory for research artifacts")
    parser.add_argument("--offline-parquet", default=None, help="Path to local parquet fallback file if offline")
    args = parser.parse_args()

    out_p = Path(args.output_dir)
    off_p = Path(args.offline_parquet) if args.offline_parquet else None

    run_research_pipeline(
        symbol=args.symbol,
        days=args.days,
        output_dir=out_p,
        offline_parquet_path=off_p,
    )


if __name__ == "__main__":
    main()
