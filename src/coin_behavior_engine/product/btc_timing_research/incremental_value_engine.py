"""
Incremental Value Assessment Engine (Sprint 30 Task 4).

Rigorously measures whether market regime classifications add genuine incremental
risk-adjusted value beyond simple price and volatility indicators:

Evaluates 5 tiers:
1. Baseline A: Buy & Hold (Passive benchmark)
2. Baseline B: Simple Trend Filter (Dual moving average)
3. Baseline C: Trend + Volatility Scaling
4. Experiment D: Trend + Canonical CBE-0.7.0 Model
   -> Grounded in Task 1 audit: marked STRICTLY as NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE
5. Experiment E: Trend + Derived Research Regime Filter
   -> Evaluates actual historical performance of the derived heuristic research classifier.

Computes:
- Net Returns, Sharpe, Sortino, Max Drawdown
- Incremental Return vs Baseline B (Simple Trend)
- Incremental Sharpe vs Baseline B
- Tracking Error and Information Ratio
- Cost drag and turnover ratio
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.model_parity_auditor import (
    AUDIT_VERDICT_NOT_ESTABLISHED,
)
from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
    PerformanceMetricsReport,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    create_policy,
)
from coin_behavior_engine.product.btc_timing_research.turnover_control_engine import (
    TurnoverControlConfig,
    TurnoverController,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyIncrementalMetrics:
    """Metrics for a single policy in the incremental hierarchy."""
    policy_tier: str       # BASELINE_A, BASELINE_B, BASELINE_C, EXPERIMENT_D, EXPERIMENT_E
    policy_id: str
    policy_name: str
    evaluable: bool
    status_reason: str
    net_return_pct: Optional[float]
    annualized_sharpe: Optional[float]
    max_drawdown_pct: Optional[float]
    trade_count: Optional[int]
    total_cost_usdt: Optional[float]
    turnover_ratio: Optional[float]
    incremental_return_vs_trend: Optional[float]
    incremental_sharpe_vs_trend: Optional[float]
    tracking_error_pct: Optional[float]
    information_ratio: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IncrementalValueReport:
    """Comprehensive incremental value assessment report."""
    dataset_id: str
    start_date: str
    end_date: str
    baseline_a_bnh: PolicyIncrementalMetrics
    baseline_b_trend: PolicyIncrementalMetrics
    baseline_c_vol: PolicyIncrementalMetrics
    experiment_d_canonical_cbe: PolicyIncrementalMetrics
    experiment_e_derived_regime: PolicyIncrementalMetrics
    canonical_evaluation_status: str  # NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE
    derived_regime_incremental_verdict: str  # NO_INCREMENTAL_VALUE, MARGINAL_VALUE, SUBSTANTIAL_VALUE
    key_findings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "baseline_a_bnh": self.baseline_a_bnh.to_dict(),
            "baseline_b_trend": self.baseline_b_trend.to_dict(),
            "baseline_c_vol": self.baseline_c_vol.to_dict(),
            "experiment_d_canonical_cbe": self.experiment_d_canonical_cbe.to_dict(),
            "experiment_e_derived_regime": self.experiment_e_derived_regime.to_dict(),
            "canonical_evaluation_status": self.canonical_evaluation_status,
            "derived_regime_incremental_verdict": self.derived_regime_incremental_verdict,
            "key_findings": self.key_findings,
        }


class IncrementalValueTester:
    """Evaluates incremental value of market regimes."""

    def __init__(
        self,
        initial_capital_usdt: float = 10000.0,
        cost_profile_id: str = "BASE_COST",
    ):
        self.initial_capital_usdt = initial_capital_usdt
        self.cost_profile_id = cost_profile_id

    def evaluate_hierarchy(
        self,
        df_features: pd.DataFrame,
        dataset_id: str = "DS-BTC-1H-2023-2024",
        turnover_config: Optional[TurnoverControlConfig] = None,
    ) -> IncrementalValueReport:
        """Run all hierarchical tiers and compute comparative value added."""
        start_date = str(df_features["datetime_utc"].iloc[0])
        end_date = str(df_features["datetime_utc"].iloc[-1])

        # 1. Baseline A: Buy & Hold
        pol_a = create_policy("POLICY_BUY_AND_HOLD")
        eng_a, _ = run_historical_simulation(df_features, pol_a, self.initial_capital_usdt, self.cost_profile_id)
        rep_a = PerformanceAnalyticsEngine.calculate_metrics(eng_a)
        returns_a = self._extract_returns(eng_a)

        # 2. Baseline B: Simple Trend
        pol_b = create_policy("POLICY_SIMPLE_TREND")
        tc_b = TurnoverController(turnover_config, self.initial_capital_usdt) if turnover_config else None
        eng_b, _ = run_historical_simulation(df_features, pol_b, self.initial_capital_usdt, self.cost_profile_id, turnover_controller=tc_b)
        rep_b = PerformanceAnalyticsEngine.calculate_metrics(eng_b, bnh_net_return_pct=rep_a.net_return_pct)
        returns_b = self._extract_returns(eng_b)

        # 3. Baseline C: Trend + Volatility Aware
        pol_c = create_policy("POLICY_VOLATILITY_AWARE")
        tc_c = TurnoverController(turnover_config, self.initial_capital_usdt) if turnover_config else None
        eng_c, _ = run_historical_simulation(df_features, pol_c, self.initial_capital_usdt, self.cost_profile_id, turnover_controller=tc_c)
        rep_c = PerformanceAnalyticsEngine.calculate_metrics(eng_c, bnh_net_return_pct=rep_a.net_return_pct)
        returns_c = self._extract_returns(eng_c)

        # 4. Experiment D: Canonical CBE-0.7.0
        # STRICT RULE: Must be marked NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE
        metrics_d = PolicyIncrementalMetrics(
            policy_tier="EXPERIMENT_D",
            policy_id="CANONICAL_CBE_0_7_0_REGIME",
            policy_name="Canonical CBE-0.7.0 Market State Classifier",
            evaluable=False,
            status_reason="NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE: Task 1 audit proved adapter produces derived heuristic quantiles, not canonical CBE-0.7.0 state space.",
            net_return_pct=None,
            annualized_sharpe=None,
            max_drawdown_pct=None,
            trade_count=None,
            total_cost_usdt=None,
            turnover_ratio=None,
            incremental_return_vs_trend=None,
            incremental_sharpe_vs_trend=None,
            tracking_error_pct=None,
            information_ratio=None,
        )

        # 5. Experiment E: Derived Research Regime (Combined Trend & Regime)
        pol_e = create_policy("POLICY_COMBINED_TREND_REGIME")
        tc_e = TurnoverController(turnover_config, self.initial_capital_usdt) if turnover_config else None
        eng_e, _ = run_historical_simulation(df_features, pol_e, self.initial_capital_usdt, self.cost_profile_id, turnover_controller=tc_e)
        rep_e = PerformanceAnalyticsEngine.calculate_metrics(eng_e, bnh_net_return_pct=rep_a.net_return_pct)
        returns_e = self._extract_returns(eng_e)

        # Compute relative statistics vs Baseline B
        te_c, ir_c = self._compute_tracking_error_and_ir(returns_c, returns_b)
        te_e, ir_e = self._compute_tracking_error_and_ir(returns_e, returns_b)

        metrics_a = PolicyIncrementalMetrics(
            policy_tier="BASELINE_A",
            policy_id="POLICY_BUY_AND_HOLD",
            policy_name="Buy and Hold (Passive Benchmark)",
            evaluable=True,
            status_reason="Active passive benchmark.",
            net_return_pct=round(rep_a.net_return_pct, 2),
            annualized_sharpe=round(rep_a.sharpe_ratio, 4) if rep_a.sharpe_ratio else None,
            max_drawdown_pct=round(rep_a.max_drawdown_pct, 2),
            trade_count=len(eng_a.trades),
            total_cost_usdt=round(rep_a.total_transaction_costs_usdt, 2),
            turnover_ratio=round(rep_a.turnover_pct / 100.0, 2),
            incremental_return_vs_trend=round(rep_a.net_return_pct - rep_b.net_return_pct, 2),
            incremental_sharpe_vs_trend=round((rep_a.sharpe_ratio or 0) - (rep_b.sharpe_ratio or 0), 4),
            tracking_error_pct=None,
            information_ratio=None,
        )

        metrics_b = PolicyIncrementalMetrics(
            policy_tier="BASELINE_B",
            policy_id="POLICY_SIMPLE_TREND",
            policy_name="Simple Moving Average Trend Filter",
            evaluable=True,
            status_reason="Base trend indicator.",
            net_return_pct=round(rep_b.net_return_pct, 2),
            annualized_sharpe=round(rep_b.sharpe_ratio, 4) if rep_b.sharpe_ratio else None,
            max_drawdown_pct=round(rep_b.max_drawdown_pct, 2),
            trade_count=len(eng_b.trades),
            total_cost_usdt=round(rep_b.total_transaction_costs_usdt, 2),
            turnover_ratio=round(rep_b.turnover_pct / 100.0, 2),
            incremental_return_vs_trend=0.0,
            incremental_sharpe_vs_trend=0.0,
            tracking_error_pct=0.0,
            information_ratio=0.0,
        )

        metrics_c = PolicyIncrementalMetrics(
            policy_tier="BASELINE_C",
            policy_id="POLICY_VOLATILITY_AWARE",
            policy_name="Parkinson Volatility Scaling",
            evaluable=True,
            status_reason="Volatility-scaled benchmark.",
            net_return_pct=round(rep_c.net_return_pct, 2),
            annualized_sharpe=round(rep_c.sharpe_ratio, 4) if rep_c.sharpe_ratio else None,
            max_drawdown_pct=round(rep_c.max_drawdown_pct, 2),
            trade_count=len(eng_c.trades),
            total_cost_usdt=round(rep_c.total_transaction_costs_usdt, 2),
            turnover_ratio=round(rep_c.turnover_pct / 100.0, 2),
            incremental_return_vs_trend=round(rep_c.net_return_pct - rep_b.net_return_pct, 2),
            incremental_sharpe_vs_trend=round((rep_c.sharpe_ratio or 0) - (rep_b.sharpe_ratio or 0), 4),
            tracking_error_pct=round(te_c * 100.0, 2) if te_c else None,
            information_ratio=round(ir_c, 4) if ir_c else None,
        )

        metrics_e = PolicyIncrementalMetrics(
            policy_tier="EXPERIMENT_E",
            policy_id="POLICY_COMBINED_TREND_REGIME",
            policy_name="Trend & Derived Research Regime Filter",
            evaluable=True,
            status_reason="Evaluated using derived research heuristic regime classification.",
            net_return_pct=round(rep_e.net_return_pct, 2),
            annualized_sharpe=round(rep_e.sharpe_ratio, 4) if rep_e.sharpe_ratio else None,
            max_drawdown_pct=round(rep_e.max_drawdown_pct, 2),
            trade_count=len(eng_e.trades),
            total_cost_usdt=round(rep_e.total_transaction_costs_usdt, 2),
            turnover_ratio=round(rep_e.turnover_pct / 100.0, 2),
            incremental_return_vs_trend=round(rep_e.net_return_pct - rep_b.net_return_pct, 2),
            incremental_sharpe_vs_trend=round((rep_e.sharpe_ratio or 0) - (rep_b.sharpe_ratio or 0), 4),
            tracking_error_pct=round(te_e * 100.0, 2) if te_e else None,
            information_ratio=round(ir_e, 4) if ir_e else None,
        )

        # Verdict on Derived Regime
        inc_ret = rep_e.net_return_pct - rep_b.net_return_pct
        inc_sharpe = (rep_e.sharpe_ratio or 0) - (rep_b.sharpe_ratio or 0)
        if inc_ret > 10.0 and inc_sharpe > 0.3:
            verdict_e = "SUBSTANTIAL_INCREMENTAL_VALUE"
        elif inc_ret > 0.0 and inc_sharpe > 0.0:
            verdict_e = "MARGINAL_INCREMENTAL_VALUE"
        else:
            verdict_e = "NO_INCREMENTAL_VALUE"

        findings = [
            f"Canonical CBE-0.7.0 state outputs were unavailable in historical research dataset; Experiment D recorded as NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE.",
            f"Baseline A (Buy & Hold) delivered {rep_a.net_return_pct:.2f}% net return with {rep_a.max_drawdown_pct:.2f}% maximum drawdown.",
            f"Baseline B (Simple Trend) achieved {rep_b.net_return_pct:.2f}% net return incurring ${rep_b.total_transaction_costs_usdt:.2f} in transaction fees across {len(eng_b.trades)} trades.",
            f"Experiment E (Trend + Derived Research Regime) delivered {rep_e.net_return_pct:.2f}% net return (Incremental vs Simple Trend: {inc_ret:+.2f}%).",
            f"Incremental Information Ratio of Derived Regime vs Simple Trend is {ir_e:.4f} with tracking error {te_e*100:.2f}%.",
        ]

        return IncrementalValueReport(
            dataset_id=dataset_id,
            start_date=start_date,
            end_date=end_date,
            baseline_a_bnh=metrics_a,
            baseline_b_trend=metrics_b,
            baseline_c_vol=metrics_c,
            experiment_d_canonical_cbe=metrics_d,
            experiment_e_derived_regime=metrics_e,
            canonical_evaluation_status="NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE",
            derived_regime_incremental_verdict=verdict_e,
            key_findings=findings,
        )

    @staticmethod
    def _extract_returns(engine: PaperPortfolioEngine) -> List[float]:
        curve = engine.equity_curve
        if len(curve) < 2:
            return []
        rets = []
        for i in range(1, len(curve)):
            prev = curve[i - 1].total_equity_usdt
            curr = curve[i].total_equity_usdt
            rets.append((curr - prev) / max(prev, 1e-6))
        return rets

    @staticmethod
    def _compute_tracking_error_and_ir(
        rets_policy: List[float], rets_benchmark: List[float]
    ) -> Tuple[float, float]:
        if not rets_policy or not rets_benchmark or len(rets_policy) != len(rets_benchmark):
            return 0.0, 0.0
        diff = np.array(rets_policy) - np.array(rets_benchmark)
        std_diff = np.std(diff)
        if std_diff <= 1e-8:
            return 0.0, 0.0
        annual_factor = math.sqrt(8760)
        annual_te = std_diff * annual_factor
        annual_excess = np.mean(diff) * 8760
        ir = annual_excess / max(annual_te, 1e-6)
        return float(annual_te), float(ir)
