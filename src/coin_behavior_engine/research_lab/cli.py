"""Command-line interface and reproducible runner for CBE Research Lab.

Sprint 11.05: Verified Market Intelligence & Behavioral Prediction Validation.
Provides autonomous, reproducible execution of:
1. Independent baseline audit and sample independence evaluation
2. Verified multi-provider news collection (Fed, SEC, Binance, BLS, Liquidations)
3. Point-in-time Market Context Engine with contradiction & priced-in modeling
4. Behavioral pattern research on event-conditioned market states
5. Multi-model prediction comparison against statistical baselines
6. Historical paper trading simulation with Cash and Buy & Hold benchmarks
7. First Market Reality case study with primary permalinks and citations
8. Comprehensive deliverables generation and run manifest tracking
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

from coin_behavior_engine.research_lab.baseline_auditor import BaselineAuditor
from coin_behavior_engine.research_lab.behavioral_patterns import BehavioralPatternResearcher
from coin_behavior_engine.research_lab.case_study import MarketRealityCaseStudyGenerator
from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.context_engine import MarketContextEngine
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
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
from coin_behavior_engine.research_lab.news_adapters import NewsIngestionCoordinator
from coin_behavior_engine.research_lab.pattern_engine import BehavioralPatternEngine
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.reporting import ResearchLabReporter
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cbe_research_lab")


def get_current_git_commit() -> str:
    """Retrieve git HEAD commit hash for reproducibility manifest."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def run_research_pipeline(
    symbol: str = "BTCUSDT",
    days: int = 25,
    output_dir: Path = Path("research_outputs"),
    offline_parquet: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.05 research pipeline."""
    config = ResearchLabConfig(
        symbol=symbol,
        output_dir=output_dir,
    )
    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Pipeline (Commit: {git_commit[:8]}) ===")

    # ---------------------------------------------------------
    # Gate A: Data Acquisition & Aggregation Invariants
    # ---------------------------------------------------------
    cache_file = config.data_dir / f"binance_{symbol}_1m_recent.parquet"
    candles_1m: List[CandleData] = []

    if offline_parquet and offline_parquet.is_file():
        logger.info(f"Loading provided offline parquet: {offline_parquet}...")
        df = pd.read_parquet(offline_parquet)
        candles_1m = [
            CandleData(
                timestamp_open=int(r["timestamp_open"]),
                timestamp_close=int(r["timestamp_close"]),
                datetime_open_utc=str(r["datetime_open_utc"]),
                datetime_close_utc=str(r["datetime_close_utc"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                interval="1m",
            )
            for _, r in df.iterrows()
        ]
    elif cache_file.is_file():
        logger.info(f"Loading cached 1m candles from {cache_file}...")
        df = pd.read_parquet(cache_file)
        candles_1m = [
            CandleData(
                timestamp_open=int(r["timestamp_open"]),
                timestamp_close=int(r["timestamp_close"]),
                datetime_open_utc=str(r["datetime_open_utc"]),
                datetime_close_utc=str(r["datetime_close_utc"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                interval="1m",
            )
            for _, r in df.iterrows()
        ]
    elif config.allow_network_download:
        logger.info(f"Acquiring {days} days of historical 1m klines from Binance Spot REST API...")
        adapter = BinanceHistoricalAdapter(config)
        try:
            candles_1m = adapter.fetch_historical_range(symbol=symbol, interval="1m", days=days)
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
    # Gate B: Data Quality Audit
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
    # Gate D: Phase 2 Verified Historical News Ingestion
    # ---------------------------------------------------------
    logger.info("Executing Phase 2 verified multi-provider news ingestion...")
    start_utc = candles_5m[0].datetime_open_utc
    end_utc = candles_5m[-1].datetime_close_utc
    coordinator = NewsIngestionCoordinator()
    verified_events = coordinator.ingest_all_events(start_utc=start_utc, end_utc=end_utc)
    logger.info(f"Ingested {len(verified_events)} verified historical events.")

    # Export verified_event_dataset.csv
    event_dataset_csv = config.output_dir / "verified_event_dataset.csv"
    NewsIngestionCoordinator.export_verified_event_dataset_csv(verified_events, event_dataset_csv)
    logger.info(f"Exported verified event dataset to {event_dataset_csv}")

    # Export event_provenance_audit.json
    provenance_json = config.output_dir / "event_provenance_audit.json"
    NewsIngestionCoordinator.export_provenance_audit_json(verified_events, provenance_json)
    logger.info(f"Exported event provenance audit to {provenance_json}")

    # Also keep event_source_verification.csv updated for backward compatibility
    EventIntelligenceStore.export_event_source_verification_csv(verified_events, config.output_dir / "event_source_verification.csv")

    # ---------------------------------------------------------
    # Gate E: Phase 3 Market Context Engine & Timeline
    # ---------------------------------------------------------
    logger.info("Generating Phase 3 point-in-time Market Context timeline...")
    context_engine = MarketContextEngine(verified_events)
    context_timeline = context_engine.generate_timeline(candles_5m, lookback_hours=36.0)
    context_timeline_csv = config.output_dir / "market_context_timeline.csv"
    MarketContextEngine.export_timeline_csv(context_timeline, context_timeline_csv)
    logger.info(f"Exported market context timeline to {context_timeline_csv}")

    # ---------------------------------------------------------
    # Gate F: Phase 4 Behavioral Pattern Research
    # ---------------------------------------------------------
    logger.info("Executing Phase 4 behavioral pattern discovery and evaluation...")
    pattern_records = BehavioralPatternResearcher.evaluate_all_patterns(
        candles=candles_5m,
        features=features,
        context_timeline=context_timeline,
    )
    pattern_eval_csv = config.output_dir / "behavioral_pattern_evaluation.csv"
    BehavioralPatternResearcher.export_pattern_evaluation_csv(pattern_records, pattern_eval_csv)
    pattern_df = pd.DataFrame([r.to_dict() for r in pattern_records])
    logger.info(f"Exported behavioral pattern evaluation to {pattern_eval_csv}")

    # ---------------------------------------------------------
    # Gate G: Phase 1 & 5 Independent Baseline Comparison & Prediction Audit
    # ---------------------------------------------------------
    logger.info("Executing Phase 1 & 5 statistical baseline comparisons across 15m, 1h, 4h horizons...")
    baseline_records = BaselineAuditor.run_full_baseline_comparison(
        candles=candles_5m,
        features=features,
        context_timeline=context_timeline,
    )
    baseline_csv = config.output_dir / "prediction_baseline_comparison.csv"
    BaselineAuditor.export_baseline_comparison_csv(baseline_records, baseline_csv)
    baseline_df = pd.DataFrame([r.to_dict() for r in baseline_records])
    logger.info(f"Exported prediction baseline comparison to {baseline_csv}")

    # Generate predictions.csv and prediction_evaluation.csv for backward compatibility
    predictions_1h = BaselineAuditor.generate_model_predictions(candles_5m, features, context_timeline, horizon="1h")["Model_B_Context_Aware"]
    pred_csv = config.output_dir / "predictions.csv"
    ProbabilityEngine.export_predictions_csv(predictions_1h, pred_csv)
    pred_eval_rows = ProbabilityEngine.evaluate_predictions(predictions_1h, candles_5m, horizon_bars=12)
    pred_eval_csv = config.output_dir / "prediction_evaluation.csv"
    ProbabilityEngine.export_prediction_evaluation_csv(pred_eval_rows, pred_eval_csv)

    # ---------------------------------------------------------
    # Gate H: Phase 6 Multi-Strategy Historical Simulation & Benchmarking
    # ---------------------------------------------------------
    logger.info("Executing Phase 6 historical paper trading simulations (Strategies A, B, C)...")
    evaluator = StrategyEvaluator(config)
    sim_results = evaluator.run_strategy_comparison(candles_5m, features, events=verified_events)

    comparison_df = evaluator.generate_comparison_table(sim_results)
    
    # Export context_aware_backtest.csv
    backtest_csv = config.output_dir / "context_aware_backtest.csv"
    evaluator.export_comparison_csv(comparison_df, backtest_csv)
    logger.info(f"Exported context-aware backtest comparison to {backtest_csv}")

    # Also keep corrected_strategy_comparison.csv and strategy_comparison.csv updated
    evaluator.export_comparison_csv(comparison_df, config.output_dir / "corrected_strategy_comparison.csv")
    evaluator.export_comparison_csv(comparison_df, config.output_dir / "strategy_comparison.csv")

    # Combine all executed paper trades across strategies into paper_trades.csv
    all_paper_trades = []
    for s_name, res in sim_results.items():
        if res.trades:
            all_paper_trades.extend(res.trades)
    
    paper_trades_csv = config.output_dir / "paper_trades.csv"
    HistoricalPaperSimulator.export_trades_csv(all_paper_trades, paper_trades_csv)
    logger.info(f"Exported all {len(all_paper_trades)} paper trades to {paper_trades_csv}")

    # Also export hypothetical_trades.csv and equity_curve.csv for backward compatibility
    strat_a = sim_results["Strategy_A_Technical_Only"]
    HistoricalPaperSimulator.export_trades_csv(strat_a.trades if strat_a else [], config.output_dir / "hypothetical_trades.csv")
    HistoricalPaperSimulator.export_equity_series_csv(strat_a.equity_series if strat_a else [], config.output_dir / "equity_curve.csv")

    # ---------------------------------------------------------
    # Gate I: Retrospective Counterfactual Trade Analysis
    # ---------------------------------------------------------
    logger.info("Conducting retrospective counterfactual trade analysis...")
    trades_for_cf = strat_a.trades if (strat_a and strat_a.trades) else []
    cf_records = CounterfactualAnalyzer.analyze_significant_trades(
        trades=trades_for_cf,
        candles=candles_5m,
        features=features,
        top_n=10,
    )
    cf_csv = config.output_dir / "trade_counterfactuals.csv"
    CounterfactualAnalyzer.export_counterfactuals_csv(cf_records, cf_csv)

    # ---------------------------------------------------------
    # Gate J: Phase 7 Market Reality Case Study
    # ---------------------------------------------------------
    logger.info("Generating Phase 7 Market Reality Case Study...")
    case_study_md = config.output_dir / "market_reality_case_study.md"
    MarketRealityCaseStudyGenerator.generate_case_study_markdown(
        output_file=case_study_md,
        candles=candles_5m,
        features=features,
        context_timeline=context_timeline,
        events=verified_events,
        trades=all_paper_trades,
    )
    logger.info(f"Exported market reality case study to {case_study_md}")

    # ---------------------------------------------------------
    # Gate K: Phase 8 Master Research Report, Plots & Manifest
    # ---------------------------------------------------------
    logger.info("Rendering strategy equity curves comparison chart...")
    chart_png = config.output_dir / "equity_curves.png"
    ResearchLabReporter.plot_equity_and_drawdown(sim_results, candles_5m, chart_png)
    # Also update strategy_equity_curves.png for compatibility
    ResearchLabReporter.plot_equity_and_drawdown(sim_results, candles_5m, config.output_dir / "strategy_equity_curves.png")

    logger.info("Generating Sprint 11.05 Master Research Report...")
    report_md = config.output_dir / "research_report_11_05.md"
    ResearchLabReporter.generate_research_report_11_05_markdown(
        symbol=symbol,
        interval="5m",
        start_utc=start_utc,
        end_utc=end_utc,
        total_candles=len(candles_5m),
        results=sim_results,
        comparison_df=comparison_df,
        baseline_comparison_df=baseline_df,
        pattern_df=pattern_df,
        total_verified_events=len(verified_events),
        output_file=report_md,
    )
    logger.info(f"Exported master research report to {report_md}")

    # Generate run_manifest_11_05.json
    manifest_json = config.output_dir / "run_manifest_11_05.json"
    ResearchLabReporter.generate_run_manifest_11_05(
        symbol=symbol,
        interval="5m",
        candle_count=len(candles_5m),
        start_utc=start_utc,
        end_utc=end_utc,
        git_commit=git_commit,
        results=sim_results,
        total_verified_events=len(verified_events),
        output_file=manifest_json,
    )
    logger.info(f"Exported run manifest to {manifest_json}")

    logger.info("=== CBE Research Lab Sprint 11.05 Pipeline Completed Successfully ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(config.output_dir),
        "total_candles": len(candles_5m),
        "total_verified_events": len(verified_events),
        "results": sim_results,
    }


def main():
    parser = argparse.ArgumentParser(description="CBE Research Lab Runner — Sprint 11.05")
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
        offline_parquet=off_p,
    )


if __name__ == "__main__":
    main()
