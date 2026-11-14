"""Historical Benchmark Engine (Module 29.9).

Executes and manages synchronized baseline benchmarks (Buy-and-Hold and USDT Cash)
across identical historical evaluation windows and transaction cost profiles.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
    PerformanceMetricsReport,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BuyAndHoldPolicy,
    USDTCashPolicy,
)


@dataclass(frozen=True)
class BenchmarkComparisonResult:
    """Synchronized benchmark metrics for an evaluation window."""
    buy_and_hold_metrics: PerformanceMetricsReport
    usdt_cash_metrics: PerformanceMetricsReport
    buy_and_hold_ending_equity: float
    usdt_cash_ending_equity: float
    btc_price_start: float
    btc_price_end: float
    btc_price_change_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "buy_and_hold_metrics": self.buy_and_hold_metrics.to_dict(),
            "usdt_cash_metrics": self.usdt_cash_metrics.to_dict(),
            "buy_and_hold_ending_equity": self.buy_and_hold_ending_equity,
            "usdt_cash_ending_equity": self.usdt_cash_ending_equity,
            "btc_price_start": self.btc_price_start,
            "btc_price_end": self.btc_price_end,
            "btc_price_change_pct": self.btc_price_change_pct,
        }


class BenchmarkEngine:
    """Executes Buy-and-Hold and USDT Cash benchmarks deterministically."""

    def __init__(
        self,
        initial_capital_usdt: Any = 10000.0,
        cost_profile_id: str = "BASE_COST",
    ):
        from coin_behavior_engine.product.btc_timing_research.transaction_cost_model import TransactionCostEngine
        if isinstance(initial_capital_usdt, TransactionCostEngine):
            self.cost_profile_id = initial_capital_usdt.profile.profile_id
            self.initial_capital_usdt = 10000.0
        elif isinstance(initial_capital_usdt, str):
            self.cost_profile_id = initial_capital_usdt
            self.initial_capital_usdt = 10000.0
        else:
            self.initial_capital_usdt = float(initial_capital_usdt)
            self.cost_profile_id = cost_profile_id

    def run_benchmarks(
        self,
        df_features: pd.DataFrame,
        start_index: int = 50,
    ) -> Tuple[BenchmarkComparisonResult, PaperPortfolioEngine, PaperPortfolioEngine]:
        """Run synchronized Buy-and-Hold and USDT Cash benchmarks."""
        # 1. Buy and Hold
        bnh_policy = BuyAndHoldPolicy()
        bnh_engine, _ = run_historical_simulation(
            df_features=df_features,
            policy=bnh_policy,
            initial_capital_usdt=self.initial_capital_usdt,
            cost_profile_id=self.cost_profile_id,
            start_index=start_index,
        )
        bnh_metrics = PerformanceAnalyticsEngine.calculate_metrics(
            engine=bnh_engine,
            bnh_net_return_pct=None,
        )

        # 2. USDT Cash
        cash_policy = USDTCashPolicy()
        cash_engine, _ = run_historical_simulation(
            df_features=df_features,
            policy=cash_policy,
            initial_capital_usdt=self.initial_capital_usdt,
            cost_profile_id=self.cost_profile_id,
            start_index=start_index,
        )
        cash_metrics = PerformanceAnalyticsEngine.calculate_metrics(
            engine=cash_engine,
            bnh_net_return_pct=bnh_metrics.net_return_pct,
        )

        # BTC price change over the evaluation period
        start_price = float(df_features.iloc[start_index]["open"])
        end_price = float(df_features.iloc[-1]["close"])
        btc_change_pct = round(((end_price - start_price) / start_price) * 100.0, 2)

        res = BenchmarkComparisonResult(
            buy_and_hold_metrics=bnh_metrics,
            usdt_cash_metrics=cash_metrics,
            buy_and_hold_ending_equity=bnh_metrics.ending_equity_usdt,
            usdt_cash_ending_equity=cash_metrics.ending_equity_usdt,
            btc_price_start=round(start_price, 2),
            btc_price_end=round(end_price, 2),
            btc_price_change_pct=btc_change_pct,
        )
        return res, bnh_engine, cash_engine
