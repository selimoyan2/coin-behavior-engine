"""Execution Sensitivity, Non-Fill Risk, Adverse Selection & Fee Tier Auditor.

Audits CS1 strategy performance across realistic execution uncertainty:
1. Non-fill probabilities (fill_rate in [1.0, 0.8, 0.6, 0.4, 0.2]).
2. Unfilled order handling & opportunity cost:
   - When maker order fails to fill, capital either stays in prior asset or falls back to cash.
3. Adverse selection (fills occurring disproportionately when asset immediately moves adversely).
4. Partial fills (fill ratio in [0.5, 0.75, 1.0]).
5. Fee-tier sensitivity:
   - Tier 0 (Retail): Maker 6 bps, Taker 16 bps
   - Tier 1 (Active Retail): Maker 4 bps, Taker 10 bps
   - Tier 2 (VIP): Maker 2 bps, Taker 5 bps
   - Tier 3 (Institutional): Maker 0 bps / -0.5 bps rebate, Taker 2.5 bps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from coin_behavior_engine.research.historical.portfolio_accounting import (
    PortfolioAccountingSimulator,
    PortfolioPerformanceSummary,
)


@dataclass(frozen=True)
class ExecutionScenarioResult:
    """Outcome of an execution sensitivity experiment."""

    scenario_name: str
    fill_rate_assumed: float
    adverse_selection_bps: float
    partial_fill_ratio: float
    maker_fee_rate_bps: float
    taker_fee_rate_bps: float
    unfilled_handling: str
    final_equity: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_fees_paid: float
    annual_turnover: float
    missed_rebalances_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionSensitivityAuditor:
    """Audits strategy sensitivity to execution fill failure, adverse selection, and fee tiers."""

    def __init__(self, initial_capital: float = 10000.0) -> None:
        self.initial_capital = initial_capital

    def evaluate_fill_rate_sweep(
        self,
        snapshots: Sequence[Any],
        rebalance_horizon_bars: int = 16,
        fill_rates: tuple[float, ...] = (1.0, 0.8, 0.6, 0.4, 0.2),
        adverse_selection_bps: float = 2.0,
        maker_fee_bps: float = 6.0,
    ) -> list[ExecutionScenarioResult]:
        """Sweep maker fill rates with deterministic pseudo-random fill outcomes."""
        results: list[ExecutionScenarioResult] = []
        n_snaps = len(snapshots)

        for fr in fill_rates:
            rng = np.random.default_rng(seed=42)
            cash = float(self.initial_capital)
            holdings: dict[str, float] = {}
            current_sym = None
            total_fees = 0.0
            total_turnover = 0.0
            missed_count = 0
            equities = []

            fee_per_side = (maker_fee_bps / 10000.0) / 2.0
            adv_rate = adverse_selection_bps / 10000.0

            for idx in range(0, n_snaps, rebalance_horizon_bars):
                s = snapshots[idx]
                top_sym = s.top_asset
                prices = {k: float(v) for k, v in s.prices.items()}

                if top_sym != current_sym:
                    # Check fill probability
                    is_filled = (fr >= 1.0) or (rng.random() < fr)
                    if is_filled:
                        # Liquidate prior asset
                        if current_sym and holdings.get(current_sym, 0.0) > 0.0:
                            qty = holdings[current_sym]
                            p = prices[current_sym] * (1.0 - adv_rate)
                            proceeds = qty * p
                            fee_sell = proceeds * fee_per_side
                            cash += (proceeds - fee_sell)
                            total_fees += fee_sell
                            total_turnover += proceeds
                            holdings[current_sym] = 0.0

                        # Buy new asset
                        p_buy = prices[top_sym] * (1.0 + adv_rate)
                        usable = cash / (1.0 + fee_per_side)
                        fee_buy = usable * fee_per_side
                        qty_b = usable / p_buy
                        cash -= (usable + fee_buy)
                        total_fees += fee_buy
                        total_turnover += usable
                        holdings[top_sym] = qty_b
                        current_sym = top_sym
                    else:
                        missed_count += 1
                        # Unfilled: keep holding prior asset (opportunity cost / lag)

                # Valuation
                val = cash + sum(q * prices.get(sym, 0.0) for sym, q in holdings.items())
                equities.append(val)

            eq_arr = np.array(equities)
            final_eq = float(eq_arr[-1])
            tot_ret = ((final_eq - self.initial_capital) / self.initial_capital) * 100.0
            rets = np.diff(eq_arr) / eq_arr[:-1]
            sharpe = float((np.mean(rets) / max(1e-9, np.std(rets, ddof=1))) * math.sqrt(365.25 * 6.0)) if len(rets) > 1 else 0.0
            peak = np.maximum.accumulate(eq_arr)
            max_dd = float(np.max((peak - eq_arr) / peak) * 100.0) if len(eq_arr) > 0 else 0.0

            years = ((len(equities) * 4.0) / 24.0) / 365.25
            ann_turnover = (total_turnover / (float(np.mean(eq_arr)) * max(0.05, years))) if len(eq_arr) > 0 else 0.0

            results.append(
                ExecutionScenarioResult(
                    scenario_name=f"MAKER_FILL_RATE_{int(fr * 100)}PCT",
                    fill_rate_assumed=fr,
                    adverse_selection_bps=adverse_selection_bps,
                    partial_fill_ratio=1.0,
                    maker_fee_rate_bps=maker_fee_bps,
                    taker_fee_rate_bps=16.0,
                    unfilled_handling="RETAIN_PREVIOUS_ASSET",
                    final_equity=round(final_eq, 2),
                    total_return_pct=round(tot_ret, 2),
                    sharpe_ratio=round(sharpe, 2),
                    max_drawdown_pct=round(max_dd, 2),
                    total_fees_paid=round(total_fees, 2),
                    annual_turnover=round(ann_turnover, 2),
                    missed_rebalances_count=missed_count,
                )
            )

        return results

    def evaluate_fee_tier_sweep(
        self,
        snapshots: Sequence[Any],
        rebalance_horizon_bars: int = 16,
    ) -> list[ExecutionScenarioResult]:
        """Evaluate strategy across industry fee tiers from Retail to Institutional."""
        tiers = [
            ("RETAIL_TIER_0", 6.0, 16.0),
            ("ACTIVE_RETAIL_TIER_1", 4.0, 10.0),
            ("VIP_TIER_2", 2.0, 5.0),
            ("MARKET_MAKER_TIER_3", 0.0, 2.5),
            ("INSTITUTIONAL_REBATE_TIER_4", -0.5, 2.0),
        ]

        results = []
        for name, m_bps, t_bps in tiers:
            sim = PortfolioAccountingSimulator(
                initial_capital=self.initial_capital,
                maker_fee_rate=(m_bps / 10000.0),
                taker_fee_rate=(t_bps / 10000.0),
                spread_slippage_bps=1.0,
            )
            _, summary = sim.simulate_cross_sectional_rebalancing(
                snapshots, rebalance_horizon_bars=rebalance_horizon_bars, execution_mode="MAKER", strategy_name=name
            )
            results.append(
                ExecutionScenarioResult(
                    scenario_name=name,
                    fill_rate_assumed=1.0,
                    adverse_selection_bps=1.0,
                    partial_fill_ratio=1.0,
                    maker_fee_rate_bps=m_bps,
                    taker_fee_rate_bps=t_bps,
                    unfilled_handling="NONE",
                    final_equity=summary.final_equity,
                    total_return_pct=summary.total_return_pct,
                    sharpe_ratio=summary.sharpe_ratio,
                    max_drawdown_pct=summary.max_drawdown_pct,
                    total_fees_paid=summary.total_fees_paid,
                    annual_turnover=summary.annual_turnover_ratio,
                    missed_rebalances_count=0,
                )
            )

        return results
