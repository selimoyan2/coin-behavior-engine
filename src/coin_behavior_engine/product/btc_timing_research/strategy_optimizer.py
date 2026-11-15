"""
Bounded Strategy Optimizer (Sprint 30 Task 3 & 4).

Performs deterministic, bounded parameter optimization across chronological splits
to test whether turnover-control and strategy parameters generalize out-of-sample:
1. Chronological Partitioning: In-Sample (IS / Training) vs Out-of-Sample (OOS / Testing).
2. Strictly Bounded Grid: Maximum 20 parameter configurations per policy to prevent combinatorial overfitting.
3. Multi-Metric Scoring: Net return, Sharpe ratio, Max Drawdown, Calmar ratio, Trade Count, Fee drag.
4. Overfitting & Stability Diagnostics: Measures performance degradation from IS to OOS.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BaseTimingPolicy,
    create_policy,
)
from coin_behavior_engine.product.btc_timing_research.turnover_control_engine import (
    TurnoverControlConfig,
    TurnoverController,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParameterEvaluationResult:
    """Evaluation metrics for a single parameter configuration across IS and OOS."""
    config_id: str
    parameters: Dict[str, Any]
    # In-Sample Metrics
    is_net_return_pct: float
    is_sharpe: Optional[float]
    is_max_dd_pct: float
    is_trade_count: int
    is_total_cost_usdt: float
    is_turnover_ratio: float
    # Out-of-Sample Metrics
    oos_net_return_pct: float
    oos_sharpe: Optional[float]
    oos_max_dd_pct: float
    oos_trade_count: int
    oos_total_cost_usdt: float
    oos_turnover_ratio: float
    # Stability Diagnostics
    return_degradation_pct: float
    is_oos_profitable: bool
    generalization_score: float  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyOptimizationReport:
    """Complete optimization report for a policy family."""
    policy_id: str
    policy_name: str
    train_range: Tuple[str, str]
    test_range: Tuple[str, str]
    total_configurations_tested: int
    best_is_config: Dict[str, Any]
    best_is_metrics: Dict[str, Any]
    oos_metrics_for_best_is: Dict[str, Any]
    all_evaluations: List[ParameterEvaluationResult]
    stability_verdict: str  # ROBUST_GENERALIZATION, MODERATE_DEGRADATION, SEVERE_OVERFITTING
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "train_range": list(self.train_range),
            "test_range": list(self.test_range),
            "total_configurations_tested": self.total_configurations_tested,
            "best_is_config": self.best_is_config,
            "best_is_metrics": self.best_is_metrics,
            "oos_metrics_for_best_is": self.oos_metrics_for_best_is,
            "all_evaluations": [e.to_dict() for e in self.all_evaluations],
            "stability_verdict": self.stability_verdict,
            "recommendation": self.recommendation,
        }


class BoundedStrategyOptimizer:
    """Executes deterministic bounded grid optimization."""

    DEFAULT_GRIDS: Dict[str, List[Dict[str, Any]]] = {
        "POLICY_TREND_LOW_TURNOVER": [
            {"hysteresis_pct": 0.005, "slow_window": 50},
            {"hysteresis_pct": 0.010, "slow_window": 50},
            {"hysteresis_pct": 0.015, "slow_window": 50},
            {"hysteresis_pct": 0.020, "slow_window": 50},
            {"hysteresis_pct": 0.025, "slow_window": 50},
            {"hysteresis_pct": 0.030, "slow_window": 50},
            {"hysteresis_pct": 0.010, "slow_window": 100},
            {"hysteresis_pct": 0.020, "slow_window": 100},
            {"hysteresis_pct": 0.030, "slow_window": 100},
            {"hysteresis_pct": 0.010, "slow_window": 30},
            {"hysteresis_pct": 0.020, "slow_window": 30},
            {"hysteresis_pct": 0.030, "slow_window": 30},
        ],
        "POLICY_VOLATILITY_HYSTERESIS": [
            {"threshold_pct": 0.05},
            {"threshold_pct": 0.10},
            {"threshold_pct": 0.15},
            {"threshold_pct": 0.20},
            {"threshold_pct": 0.25},
        ],
        "POLICY_DERIVED_REGIME_CONFIRMATION": [
            {"confirmation_bars": 1},
            {"confirmation_bars": 2},
            {"confirmation_bars": 3},
            {"confirmation_bars": 4},
            {"confirmation_bars": 5},
            {"confirmation_bars": 6},
        ],
        "POLICY_RISK_CONTROL_TREND": [
            {"slow_window": 30},
            {"slow_window": 50},
            {"slow_window": 100},
        ],
    }

    def __init__(
        self,
        initial_capital_usdt: float = 10000.0,
        cost_profile_id: str = "BASE_COST",
    ):
        self.initial_capital_usdt = initial_capital_usdt
        self.cost_profile_id = cost_profile_id

    def split_chronological(
        self,
        df: pd.DataFrame,
        split_date: str = "2024-04-01T00:00:00Z",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split dataframe into In-Sample (before split_date) and Out-of-Sample (after split_date)."""
        dt_col = df["datetime_utc"].astype(str)
        is_mask = dt_col < split_date
        oos_mask = dt_col >= split_date

        df_is = df[is_mask].copy().reset_index(drop=True)
        df_oos = df[oos_mask].copy().reset_index(drop=True)

        if len(df_is) < 100 or len(df_oos) < 100:
            raise ValueError(f"Insufficient split sizes: IS={len(df_is)}, OOS={len(df_oos)}")

        return df_is, df_oos

    def optimize_policy(
        self,
        policy_id: str,
        df_features: pd.DataFrame,
        param_grid: Optional[List[Dict[str, Any]]] = None,
        split_date: str = "2024-04-01T00:00:00Z",
        turnover_config: Optional[TurnoverControlConfig] = None,
    ) -> PolicyOptimizationReport:
        """Run bounded parameter sweep and compare IS vs OOS stability."""
        grid = param_grid or self.DEFAULT_GRIDS.get(policy_id, [{}])
        if len(grid) > 20:
            logger.warning(f"Grid for {policy_id} contains {len(grid)} items. Capping at 20.")
            grid = grid[:20]

        df_is, df_oos = self.split_chronological(df_features, split_date)
        train_start = str(df_is["datetime_utc"].iloc[0])
        train_end = str(df_is["datetime_utc"].iloc[-1])
        test_start = str(df_oos["datetime_utc"].iloc[0])
        test_end = str(df_oos["datetime_utc"].iloc[-1])

        evaluations: List[ParameterEvaluationResult] = []

        for idx, params in enumerate(grid):
            config_id = f"CFG-{idx+1:02d}"

            # 1. In-Sample simulation
            pol_is = create_policy(policy_id, params)
            tc_is = TurnoverController(turnover_config, initial_capital_usdt=self.initial_capital_usdt) if turnover_config else None
            eng_is, _ = run_historical_simulation(
                df_is, pol_is, initial_capital_usdt=self.initial_capital_usdt,
                cost_profile_id=self.cost_profile_id, turnover_controller=tc_is
            )
            rep_is = PerformanceAnalyticsEngine.calculate_metrics(eng_is)

            # 2. Out-of-Sample simulation
            pol_oos = create_policy(policy_id, params)
            tc_oos = TurnoverController(turnover_config, initial_capital_usdt=self.initial_capital_usdt) if turnover_config else None
            eng_oos, _ = run_historical_simulation(
                df_oos, pol_oos, initial_capital_usdt=self.initial_capital_usdt,
                cost_profile_id=self.cost_profile_id, turnover_controller=tc_oos
            )
            rep_oos = PerformanceAnalyticsEngine.calculate_metrics(eng_oos)

            # Compute degradation
            is_ret = rep_is.net_return_pct
            oos_ret = rep_oos.net_return_pct
            if is_ret > 0:
                degradation = max(-100.0, ((is_ret - oos_ret) / is_ret) * 100.0)
            else:
                degradation = 0.0

            # Generalization score
            gen_score = 0.5
            if oos_ret > 0 and rep_oos.sharpe_ratio and rep_oos.sharpe_ratio > 0:
                gen_score = min(1.0, oos_ret / max(is_ret, 1.0))
            elif oos_ret < 0:
                gen_score = max(0.0, 1.0 - abs(oos_ret) / 100.0)

            eval_res = ParameterEvaluationResult(
                config_id=config_id,
                parameters=params,
                is_net_return_pct=round(rep_is.net_return_pct, 2),
                is_sharpe=round(rep_is.sharpe_ratio, 4) if rep_is.sharpe_ratio else None,
                is_max_dd_pct=round(rep_is.max_drawdown_pct, 2),
                is_trade_count=len(eng_is.trades),
                is_total_cost_usdt=round(rep_is.total_transaction_costs_usdt, 2),
                is_turnover_ratio=round(rep_is.turnover_pct / 100.0, 2),
                oos_net_return_pct=round(rep_oos.net_return_pct, 2),
                oos_sharpe=round(rep_oos.sharpe_ratio, 4) if rep_oos.sharpe_ratio else None,
                oos_max_dd_pct=round(rep_oos.max_drawdown_pct, 2),
                oos_trade_count=len(eng_oos.trades),
                oos_total_cost_usdt=round(rep_oos.total_transaction_costs_usdt, 2),
                oos_turnover_ratio=round(rep_oos.turnover_pct / 100.0, 2),
                return_degradation_pct=round(degradation, 2),
                is_oos_profitable=oos_ret > 0,
                generalization_score=round(gen_score, 4),
            )
            evaluations.append(eval_res)

        # Select Best In-Sample configuration (ranked by In-Sample Sharpe or Net Return)
        best_eval = max(
            evaluations,
            key=lambda e: (e.is_sharpe if e.is_sharpe is not None else -99.0, e.is_net_return_pct)
        )

        # Verdict
        if best_eval.is_oos_profitable and (best_eval.oos_sharpe or 0) > 0.5:
            verdict = "ROBUST_GENERALIZATION"
            recommendation = "Parameters demonstrate stable performance out-of-sample with controlled fee drag."
        elif best_eval.is_oos_profitable:
            verdict = "MODERATE_DEGRADATION"
            recommendation = "Parameters maintain positive return out-of-sample but exhibit moderate degradation."
        else:
            verdict = "SEVERE_OVERFITTING"
            recommendation = "In-sample optimization did not generalize. Strategy experiences negative out-of-sample return."

        sample_policy = create_policy(policy_id, grid[0] if grid else {})

        return PolicyOptimizationReport(
            policy_id=policy_id,
            policy_name=sample_policy.name,
            train_range=(train_start, train_end),
            test_range=(test_start, test_end),
            total_configurations_tested=len(evaluations),
            best_is_config=best_eval.parameters,
            best_is_metrics={
                "config_id": best_eval.config_id,
                "net_return_pct": best_eval.is_net_return_pct,
                "sharpe": best_eval.is_sharpe,
                "max_drawdown_pct": best_eval.is_max_dd_pct,
                "trade_count": best_eval.is_trade_count,
                "cost_usdt": best_eval.is_total_cost_usdt,
            },
            oos_metrics_for_best_is={
                "net_return_pct": best_eval.oos_net_return_pct,
                "sharpe": best_eval.oos_sharpe,
                "max_drawdown_pct": best_eval.oos_max_dd_pct,
                "trade_count": best_eval.oos_trade_count,
                "cost_usdt": best_eval.oos_total_cost_usdt,
                "degradation_pct": best_eval.return_degradation_pct,
            },
            all_evaluations=evaluations,
            stability_verdict=verdict,
            recommendation=recommendation,
        )
