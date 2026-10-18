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
from coin_behavior_engine.research_lab.provenance_auditor import HistoricalNewsProvenanceAuditor
from coin_behavior_engine.research_lab.ablation_engine import ControlledAblationEngine

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

    # ---------------------------------------------------------
    # Gate L: Sprint 11.06 Phase A Historical News Provenance Audit
    # ---------------------------------------------------------
    logger.info("Executing Sprint 11.06 Phase A Historical News Provenance Audit...")
    prov_auditor = HistoricalNewsProvenanceAuditor()
    prov_records = prov_auditor.audit_all_events()
    prov_csv = config.output_dir / "historical_news_provenance_audit.csv"
    HistoricalNewsProvenanceAuditor.export_audit_csv(prov_records, prov_csv)
    logger.info(f"Exported historical news provenance audit to {prov_csv}")

    cov_report_md = config.output_dir / "verified_event_coverage_report.md"
    HistoricalNewsProvenanceAuditor.generate_coverage_report_markdown(prov_records, cov_report_md)
    logger.info(f"Exported verified event coverage report to {cov_report_md}")

    # ---------------------------------------------------------
    # Gate M: Sprint 11.06 Phases B-G Controlled Ablation Experiments
    # ---------------------------------------------------------
    logger.info("Executing Sprint 11.06 Controlled Ablation Experiments & Regime Validation...")
    ablation_engine = ControlledAblationEngine(config)

    # Phase B: Independent Reproduction
    repro_json = config.output_dir / "reproduced_sprint11_05_results.json"
    ablation_engine.reproduce_sprint11_05_results(candles_5m, features, verified_events, repro_json)

    # Phase C: Controlled Ablation Experiments (100 Seeds)
    ablation_csv = config.output_dir / "context_ablation_experiments.csv"
    ablation_records = ablation_engine.run_ablation_experiments(candles_5m, features, verified_events, ablation_csv, num_seeds=100)

    # Phase D: Rejected Trade Attribution
    rejection_csv = config.output_dir / "rejected_trade_attribution.csv"
    rejection_records = ablation_engine.run_rejected_trade_attribution(candles_5m, features, verified_events, rejection_csv)

    # Phase E: Market Regime Comparison
    regime_csv = config.output_dir / "market_regime_comparison.csv"
    ablation_engine.run_market_regime_comparison(candles_5m, features, verified_events, regime_csv)

    # Phase F & G: Statistical Report, Master Report & Manifest
    stat_report_md = config.output_dir / "context_edge_statistical_report.md"
    ControlledAblationEngine.generate_statistical_report_markdown(ablation_records, stat_report_md)

    master_report_md = config.output_dir / "research_report_11_06.md"
    ControlledAblationEngine.generate_master_report_markdown(
        symbol=symbol,
        interval="5m",
        total_candles=len(candles_5m),
        ablation_records=ablation_records,
        provenance_records_count=len(prov_records),
        rejection_records_count=len(rejection_records),
        output_file=master_report_md,
    )

    manifest_11_06_json = config.output_dir / "run_manifest_11_06.json"
    ControlledAblationEngine.generate_run_manifest_11_06(
        symbol=symbol,
        interval="5m",
        candle_count=len(candles_5m),
        git_commit=git_commit,
        ablation_records=ablation_records,
        output_file=manifest_11_06_json,
    )

    logger.info("=== CBE Research Lab Sprint 11.05 & 11.06 Pipelines Completed Successfully ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(config.output_dir),
        "total_candles": len(candles_5m),
        "total_verified_events": len(verified_events),
        "results": sim_results,
        "ablation_records": ablation_records,
        "git_commit": git_commit,
    }


def run_sprint11_07_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.07 Behavioral Learning & Backtesting pipeline."""
    from coin_behavior_engine.research_lab.methodology_auditor import MethodologyAuditor
    from coin_behavior_engine.research_lab.market_state_builder import MarketStateBuilder
    from coin_behavior_engine.research_lab.analogue_engine import HistoricalAnalogueEngine
    from coin_behavior_engine.research_lab.walk_forward_engine import WalkForwardEngine
    from coin_behavior_engine.research_lab.behavior_case_studies import BehaviorCaseStudiesGenerator

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.07 Pipeline (Commit: {git_commit[:8]}) ===")

    # Phase 1: Methodology Audit
    logger.info("Executing Phase 1: Methodology Audit...")
    med_auditor = MethodologyAuditor(output_dir=output_dir)
    audit_report = med_auditor.run_audit()

    # Phase 2 & 3: Historical Dataset Assembly & Market State Builder
    logger.info("Executing Phase 2 & 3: Historical Dataset Assembly & State Features...")
    state_builder = MarketStateBuilder(output_dir=output_dir)
    df_state, manifest = state_builder.run_pipeline()

    # Phase 4 & 5: Empirical Historical Analogue Search Engine & Probabilistic Predictions
    logger.info("Executing Phase 4 & 5: Historical Analogue Engine & Brier Calibration...")
    analogue_engine = HistoricalAnalogueEngine(output_dir=output_dir)
    analogue_results = analogue_engine.run_full_pipeline()

    # Phase 6, 7 & 8: Walk-Forward Backtesting & Strategy Benchmark Suite
    logger.info("Executing Phase 6, 7 & 8: Walk-Forward Folds & Paper Simulation Suite...")
    wf_engine = WalkForwardEngine(output_dir=output_dir)
    wf_results = wf_engine.run_full_pipeline()

    # Phase 9 & 10: Market Behavior Case Studies & Master Research Report
    logger.info("Executing Phase 9 & 10: Case Studies & Master Research Report...")
    case_gen = BehaviorCaseStudiesGenerator(output_dir=output_dir)
    case_gen.run_all()

    logger.info("=== CBE Research Lab Sprint 11.07 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "total_candles": len(df_state),
        "analogue_results": analogue_results,
        "walk_forward_results": wf_results,
        "git_commit": git_commit,
    }


def run_sprint11_08_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.08 Predictive Integrity & Decision Quality pipeline."""
    from coin_behavior_engine.research_lab.accounting_auditor import AccountingAuditor
    from coin_behavior_engine.research_lab.predictive_auditor import PredictiveAuditor
    from coin_behavior_engine.research_lab.decision_quality_auditor import DecisionQualityAuditor

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.08 Pipeline (Commit: {git_commit[:8]}) ===")

    # Phase 1: Financial Accounting Forensics & Reconciliation
    logger.info("Executing Phase 1: Accounting Forensics & Ledger Reconciliation...")
    acct_auditor = AccountingAuditor(output_dir=output_dir)
    acct_summaries = acct_auditor.run_reconciliation()

    # Phase 2: Prediction Metric Validation
    logger.info("Executing Phase 2: Prediction Metric Validation & Baseline Auditing...")
    pred_auditor = PredictiveAuditor(output_dir=output_dir)
    pred_metrics = pred_auditor.run_prediction_audit()

    # Phase 3-7: Analogue Safety, Failure Attribution, Horizon Research, Controlled Experiments & Dashboard Snapshot
    logger.info("Executing Phase 3-7: Analogue Safety, Failure Attribution & Controlled Experiments...")
    dq_auditor = DecisionQualityAuditor(output_dir=output_dir)
    dq_results = dq_auditor.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.08 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "accounting_summaries": acct_summaries,
        "prediction_metrics": pred_metrics,
        "decision_quality_results": dq_results,
        "git_commit": git_commit,
    }


def run_sprint11_09_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.09 Multi-Day Behavioral Learning & Economic Decision Validation pipeline."""
    from coin_behavior_engine.research_lab.multi_horizon_engine import MultiHorizonEngine
    from coin_behavior_engine.research_lab.economic_decision_engine import EconomicDecisionEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.09 Pipeline (Commit: {git_commit[:8]}) ===")

    # Phase 2: Multi-Horizon Behavioral Learning & Empirical Calibration
    logger.info("Executing Phase 2: Multi-Horizon Behavioral Learning Engine...")
    multi_engine = MultiHorizonEngine(output_dir=output_dir)
    df_preds, df_dist = multi_engine.run_multi_horizon_evaluation()

    # Phase 3-6: Economic Decision Engine, Benchmarks, Cost Sensitivity & Walk-Forward Validation
    logger.info("Executing Phase 3-6: Economic Decision Engine, Strategy Benchmarks & Walk-Forward Validation...")
    eco_engine = EconomicDecisionEngine(output_dir=output_dir)
    df_dec = eco_engine.generate_economic_decisions(target_horizon="24h")
    df_strat, df_cost = eco_engine.run_strategy_benchmarks()
    df_wf = eco_engine.run_walk_forward_validation()
    eco_engine.generate_decision_explanations()

    logger.info("=== CBE Research Lab Sprint 11.09 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "total_predictions": len(df_preds),
        "total_distributions": len(df_dist),
        "total_decisions": len(df_dec),
        "total_benchmarks": len(df_strat),
        "total_walk_forward_folds": len(df_wf),
        "git_commit": git_commit,
    }


def run_sprint11_10_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.10 Dynamic Spot Decision Engine pipeline."""
    from coin_behavior_engine.research_lab.dynamic_spot_engine import DynamicSpotEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.10 Pipeline (Commit: {git_commit[:8]}) ===")

    engine = DynamicSpotEngine(output_dir=output_dir)
    results = engine.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.10 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def run_sprint11_11_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.11 Decision Failure Forensics & Patient Adaptive Spot Engine pipeline."""
    from coin_behavior_engine.research_lab.patient_spot_engine import PatientSpotEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.11 Pipeline (Commit: {git_commit[:8]}) ===")

    engine = PatientSpotEngine(output_dir=output_dir)
    results = engine.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.11 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def run_sprint11_12_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.12 Financial Truth Audit & Benchmark Integrity Lock pipeline."""
    from coin_behavior_engine.research_lab.canonical_truth_engine import CanonicalTruthEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.12 Pipeline (Commit: {git_commit[:8]}) ===")

    engine = CanonicalTruthEngine(output_dir=output_dir)
    results = engine.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.12 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def run_sprint11_13_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.13 Canonical Reproduction Gate & Reporting Repair pipeline."""
    from coin_behavior_engine.research_lab.canonical_reproduction_gate import CanonicalReproductionGateEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.13 Pipeline (Commit: {git_commit[:8]}) ===")

    engine = CanonicalReproductionGateEngine(output_dir=output_dir)
    results = engine.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.13 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def run_sprint11_14_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.14 Market Regime Intelligence & Selective Entry pipeline."""
    from coin_behavior_engine.research_lab.selective_entry_engine import SelectiveEntryEngine

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.14 Pipeline (Commit: {git_commit[:8]}) ===")

    engine = SelectiveEntryEngine(output_dir=output_dir)
    results = engine.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.14 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def run_sprint11_15_pipeline(output_dir: Path = Path("research_outputs")) -> Dict[str, Any]:
    """Execute end-to-end Sprint 11.15 Prospective Research Readiness & Shadow Decision Protocol."""
    from coin_behavior_engine.research_lab.shadow_decision_protocol import ShadowDecisionReadinessPipeline

    git_commit = get_current_git_commit()
    logger.info(f"=== CBE Research Lab Sprint 11.15 Pipeline (Commit: {git_commit[:8]}) ===")

    pipeline = ShadowDecisionReadinessPipeline(output_dir=output_dir)
    results = pipeline.run_full_pipeline()

    logger.info("=== CBE Research Lab Sprint 11.15 Complete ===")
    return {
        "status": "COMPLETE",
        "output_dir": str(output_dir),
        "results": results,
        "git_commit": git_commit,
    }


def main():
    parser = argparse.ArgumentParser(description="CBE Research Lab Runner — Sprint 11.05 to 11.15")
    parser.add_argument("--sprint", default="11.15", choices=["11.05", "11.06", "11.07", "11.08", "11.09", "11.10", "11.11", "11.12", "11.13", "11.14", "11.15"], help="Sprint pipeline to execute (default: 11.15)")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    parser.add_argument("--days", type=int, default=25, help="Number of days to acquire and analyze (default: 25)")
    parser.add_argument("--output-dir", default="research_outputs", help="Output directory for research artifacts")
    parser.add_argument("--offline-parquet", default=None, help="Path to local parquet fallback file if offline")
    args = parser.parse_args()

    out_p = Path(args.output_dir)
    off_p = Path(args.offline_parquet) if args.offline_parquet else None

    if args.sprint == "11.15":
        run_sprint11_15_pipeline(output_dir=out_p)
    elif args.sprint == "11.14":
        run_sprint11_14_pipeline(output_dir=out_p)
    elif args.sprint == "11.13":
        run_sprint11_13_pipeline(output_dir=out_p)
    elif args.sprint == "11.12":
        run_sprint11_12_pipeline(output_dir=out_p)
    elif args.sprint == "11.11":
        run_sprint11_11_pipeline(output_dir=out_p)
    elif args.sprint == "11.10":
        run_sprint11_10_pipeline(output_dir=out_p)
    elif args.sprint == "11.09":
        run_sprint11_09_pipeline(output_dir=out_p)
    elif args.sprint == "11.08":
        run_sprint11_08_pipeline(output_dir=out_p)
    elif args.sprint == "11.07":
        run_sprint11_07_pipeline(output_dir=out_p)
    else:
        run_research_pipeline(
            symbol=args.symbol,
            days=args.days,
            output_dir=out_p,
            offline_parquet=off_p,
        )


if __name__ == "__main__":
    main()

