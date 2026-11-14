"""BTC Timing Research Coordinator & Facade (Module 29.13).

Main orchestration service uniting dataset loading, feature extraction, policy evaluation,
paper portfolio execution, benchmark comparisons, persistence, and report generation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from coin_behavior_engine.product.btc_timing_research.benchmark_engine import (
    BenchmarkComparisonResult,
    BenchmarkEngine,
)
from coin_behavior_engine.product.btc_timing_research.dataset_adapter import (
    HistoricalBTCDatasetAdapter,
)
from coin_behavior_engine.product.btc_timing_research.historical_feature_adapter import (
    HistoricalFeatureAdapter,
)
from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
    PerformanceMetricsReport,
)
from coin_behavior_engine.product.btc_timing_research.timing_hypothesis_registry import (
    TimingHypothesisRegistry,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    POLICY_REGISTRY,
    BaseTimingPolicy,
    create_policy,
)
from coin_behavior_engine.product.btc_timing_research.timing_research_report_builder import (
    TimingResearchReportBuilder,
)
from coin_behavior_engine.product.btc_timing_research.timing_research_repository import (
    TimingExperimentRecord,
    TimingResearchRepository,
)
from coin_behavior_engine.product.btc_timing_research.transaction_cost_model import (
    CANONICAL_COST_PROFILES,
)
from coin_behavior_engine.product.btc_timing_research.walk_forward_validator import (
    WalkForwardValidationReport,
    WalkForwardValidator,
)

logger = logging.getLogger(__name__)


class BTCTimingResearchCoordinator:
    """Central orchestrator for Sprint 29 BTC Timing Research."""

    _instance: Optional[BTCTimingResearchCoordinator] = None

    @classmethod
    def get_instance(cls) -> BTCTimingResearchCoordinator:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.dataset_adapter = HistoricalBTCDatasetAdapter()
        self.feature_adapter = HistoricalFeatureAdapter()
        self.hypothesis_registry = TimingHypothesisRegistry()
        self.repository = TimingResearchRepository()
        self.walk_forward_validator = WalkForwardValidator()
        self.report_builder = TimingResearchReportBuilder()

        # Cache for engineered features per dataset
        self._feature_cache: Dict[str, pd.DataFrame] = {}

        # Ensure canonical baseline experiments exist
        self._ensure_baseline_experiments()

    def get_feature_table(self, dataset_id: str = "DS-BTC-1H-2023-2024") -> pd.DataFrame:
        """Load and cache point-in-time features for dataset."""
        if dataset_id in self._feature_cache:
            return self._feature_cache[dataset_id]

        raw_df = self.dataset_adapter.load_dataset(dataset_id)
        feat_df = self.feature_adapter.build_feature_table(raw_df)
        self._feature_cache[dataset_id] = feat_df
        return feat_df

    def run_experiment(
        self,
        policy_id: str,
        dataset_id: str = "DS-BTC-1H-2023-2024",
        parameters: Optional[Dict[str, Any]] = None,
        cost_profile_id: str = "BASE_COST",
        initial_capital_usdt: float = 10000.0,
        start_index: int = 50,
        end_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute a full historical paper timing experiment."""
        verif = self.dataset_adapter.verify_dataset(dataset_id)
        if not verif.is_valid:
            raise ValueError(f"Dataset {dataset_id} verification failed: {verif.error_message}")

        df_features = self.get_feature_table(dataset_id)
        if end_index is not None:
            df_features = df_features.iloc[:end_index].copy()

        policy = create_policy(policy_id, parameters)

        # 1. Run Candidate Policy Simulation
        engine, decisions = run_historical_simulation(
            df_features=df_features,
            policy=policy,
            initial_capital_usdt=initial_capital_usdt,
            cost_profile_id=cost_profile_id,
            start_index=start_index,
        )

        # 2. Run Synchronized Benchmarks for Fair Comparison
        bmark_engine = BenchmarkEngine(
            initial_capital_usdt=initial_capital_usdt,
            cost_profile_id=cost_profile_id,
        )
        bmark_res, bnh_engine, cash_engine = bmark_engine.run_benchmarks(
            df_features=df_features,
            start_index=start_index,
        )

        # 3. Calculate Performance Metrics with Benchmark Integration
        metrics = PerformanceAnalyticsEngine.calculate_metrics(
            engine=engine,
            bnh_net_return_pct=bmark_res.buy_and_hold_metrics.net_return_pct,
        )

        exp_id = f"EXP-{policy_id[:10]}-{uuid.uuid4().hex[:8].upper()}"
        start_candle = df_features.iloc[start_index]
        end_candle = df_features.iloc[-1]

        bmark_comp = {
            "buy_and_hold_ending_equity": bmark_res.buy_and_hold_ending_equity,
            "buy_and_hold_return_pct": bmark_res.buy_and_hold_metrics.net_return_pct,
            "buy_and_hold_max_dd_pct": bmark_res.buy_and_hold_metrics.max_drawdown_pct,
            "buy_and_hold_sharpe": bmark_res.buy_and_hold_metrics.sharpe_ratio,
            "usdt_cash_ending_equity": bmark_res.usdt_cash_ending_equity,
            "btc_price_start": bmark_res.btc_price_start,
            "btc_price_end": bmark_res.btc_price_end,
            "btc_price_change_pct": bmark_res.btc_price_change_pct,
        }

        record = TimingExperimentRecord(
            experiment_id=exp_id,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            policy_id=policy.policy_id,
            policy_name=policy.name,
            policy_version="1.0.0",
            dataset_id=dataset_id,
            dataset_sha256=verif.sha256,
            model_version="CBE-0.7.0",
            parameter_snapshot=parameters or {},
            cost_profile_id=cost_profile_id,
            initial_capital_usdt=round(initial_capital_usdt, 2),
            ending_equity_usdt=metrics.ending_equity_usdt,
            net_return_pct=metrics.net_return_pct,
            max_drawdown_pct=metrics.max_drawdown_pct,
            sharpe_ratio=metrics.sharpe_ratio,
            trade_count=metrics.trade_count,
            evaluation_start_utc=str(start_candle.get("datetime_utc", "")),
            evaluation_end_utc=str(end_candle.get("datetime_utc", "")),
            execution_convention="NEXT_CANDLE_OPEN",
            research_status="HISTORICAL_SIMULATION_COMPLETED",
            metrics_summary=metrics.to_dict(),
            benchmark_comparison=bmark_comp,
            notes="Executed offline via BTCTimingResearchCoordinator.",
        )

        # 4. Persist to storage
        self.repository.save_experiment(record, engine.equity_curve, engine.trades)

        payload = self.repository.get_experiment(exp_id)
        return payload or {"experiment_id": exp_id, "metadata": record.to_dict()}

    def compare_all_policies(
        self,
        dataset_id: str = "DS-BTC-1H-2023-2024",
        cost_profile_id: str = "BASE_COST",
        initial_capital_usdt: float = 10000.0,
    ) -> List[Dict[str, Any]]:
        """Run and compare all supported timing policies side by side."""
        results = []
        for pid in POLICY_REGISTRY.keys():
            try:
                res = self.run_experiment(
                    policy_id=pid,
                    dataset_id=dataset_id,
                    cost_profile_id=cost_profile_id,
                    initial_capital_usdt=initial_capital_usdt,
                )
                meta = res.get("metadata", {})
                results.append(meta)
            except Exception as e:
                logger.error(f"Failed policy comparison for {pid}: {e}")
        return results

    def _ensure_baseline_experiments(self) -> None:
        """Seed initial experiments if repository index is empty."""
        exps = self.repository.list_experiments()
        if len(exps) < 3:
            logger.info("Initializing baseline timing experiments in repository...")
            for pid in ["POLICY_BUY_AND_HOLD", "POLICY_USDT_CASH", "POLICY_SIMPLE_TREND", "POLICY_VOLATILITY_AWARE", "POLICY_CBE_REGIME"]:
                try:
                    self.run_experiment(
                        policy_id=pid,
                        dataset_id="DS-BTC-1H-2023-2024",
                        cost_profile_id="BASE_COST",
                        initial_capital_usdt=10000.0,
                    )
                except Exception as e:
                    logger.warning(f"Could not seed baseline experiment for {pid}: {e}")
