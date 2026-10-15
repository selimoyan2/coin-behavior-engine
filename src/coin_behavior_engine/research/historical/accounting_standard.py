"""Canonical Accounting Standard for Historical Market Research (Sprint 09.33).

Defines, standardizes, and validates mathematical definitions across the Coin Behavior Engine:
1. Capital, Equity, Cash, and Holdings.
2. One-Way Turnover vs Two-Way Traded Notional (resolving Shared Denominator Fallacy).
3. Fee Schedules (Maker 3 bps/side, Taker 8 bps/side, Slippage 1-3 bps).
4. Arithmetic Expectancy, Volatility Drag, and Geometric Compounding Bridge:
   g ~= mu - 0.5 * sigma^2
5. Max Drawdown, Recovery Duration, Sharpe, Sortino, Calmar.
6. Warmup Window Parity: Standardizing timeline alignment across differing feature warmup lengths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class AccountingConceptDefinition:
    """Formal definition and mathematical formula for an accounting metric."""
    concept_id: str
    canonical_name: str
    unit: str
    mathematical_formula: str
    plain_english_definition: str
    historical_pitfall_or_defect: str
    resolution_standard: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CanonicalAccountingStandard:
    """Standardized accounting definitions, formulas, and verification utilities."""

    @staticmethod
    def get_canonical_definitions() -> List[AccountingConceptDefinition]:
        """Return the complete library of approved accounting definitions."""
        return [
            AccountingConceptDefinition(
                concept_id="STARTING_CAPITAL",
                canonical_name="Starting Capital (C_0)",
                unit="USDT",
                mathematical_formula="C_0 = 10,000.00 USDT",
                plain_english_definition="Initial liquid capital available in portfolio currency at evaluation start.",
                historical_pitfall_or_defect="Varying initial capital across experiments preventing direct dollar-level comparison.",
                resolution_standard="Strict invariant: exactly 10,000.00 USDT for all Spot portfolio simulations.",
            ),
            AccountingConceptDefinition(
                concept_id="PORTFOLIO_EQUITY",
                canonical_name="Total Portfolio Equity (E_t)",
                unit="USDT",
                mathematical_formula="E_t = Cash_t + sum_i (Quantity_{i,t} * Price_{i,t})",
                plain_english_definition="Mark-to-market total portfolio liquidation value at bar close t.",
                historical_pitfall_or_defect="Summing raw trade percentage returns without compounding or cash weighting.",
                resolution_standard="Track exact cash ledger and asset balances. Marked to market at every period close.",
            ),
            AccountingConceptDefinition(
                concept_id="ONE_WAY_TURNOVER",
                canonical_name="One-Way Portfolio Turnover",
                unit="USDT",
                mathematical_formula="Turnover_1way = sum_t min(Purchases_t, Sales_t) or Net_Capital_Rotated",
                plain_english_definition="Nominal amount of capital rotated out of one asset into another.",
                historical_pitfall_or_defect="Confusing one-way rebalancing turnover with total exchange execution volume.",
                resolution_standard="Strictly separate One-Way Turnover from Two-Way Traded Notional. One-way = ~0.5 * Two-way for full rebalance.",
            ),
            AccountingConceptDefinition(
                concept_id="TWO_WAY_TRADED_NOTIONAL",
                canonical_name="Two-Way Traded Notional (Execution Volume)",
                unit="USDT",
                mathematical_formula="Notional_2way = sum_t (Buy_Notional_t + Sell_Notional_t)",
                plain_english_definition="Gross traded volume sent to the exchange, which forms the fee assessment base.",
                historical_pitfall_or_defect="Shared Denominator Fallacy: applying Taker fee rates to Maker traded notional.",
                resolution_standard="Compute fees strictly on actual executed notional of the specific execution tier.",
            ),
            AccountingConceptDefinition(
                concept_id="TRANSACTION_FEES",
                canonical_name="Exchange Transaction Fees (Fees_t)",
                unit="USDT",
                mathematical_formula="Fees_t = Trade_Notional_t * Fee_Rate_Side (Maker=0.0003, Taker=0.0008)",
                plain_english_definition="Direct fee cash extracted by the exchange on execution.",
                historical_pitfall_or_defect="Assuming zero fees or subtracting fees linearly from arithmetic trade return.",
                resolution_standard="Deduct fee directly from cash/usable balance before executing order quantity.",
            ),
            AccountingConceptDefinition(
                concept_id="ARITHMETIC_EXPECTANCY",
                canonical_name="Arithmetic Mean Expectancy (mu)",
                unit="bps per period",
                mathematical_formula="mu = (1/N) * sum_{i=1}^N r_i",
                plain_english_definition="Unweighted average per-period return across N decision periods.",
                historical_pitfall_or_defect="Assuming arithmetic expectancy compounds directly into capital growth (naive compounding).",
                resolution_standard="Acknowledge volatility drag and compute true geometric compounding growth.",
            ),
            AccountingConceptDefinition(
                concept_id="VOLATILITY_DRAG",
                canonical_name="Volatility Drag (delta)",
                unit="bps per period",
                mathematical_formula="delta ~= 0.5 * sigma^2",
                plain_english_definition="Reduction in geometric compound growth caused by return dispersion / variance.",
                historical_pitfall_or_defect="Discrepancy between +6.47 bps arithmetic mean and +217.76% gross equity (vs naive +312%).",
                resolution_standard="Reconcile with exact Taylor approximation: g = mu - 0.5 * sigma^2.",
            ),
            AccountingConceptDefinition(
                concept_id="GEOMETRIC_GROWTH_RATE",
                canonical_name="Effective Geometric Growth Rate (g)",
                unit="bps per period",
                mathematical_formula="g = exp( (1/N) * sum_t ln(1 + r_t) ) - 1 ~= mu - 0.5 * sigma^2",
                plain_english_definition="Actual compound growth rate per period experienced by invested capital.",
                historical_pitfall_or_defect="Projecting long-term equity from arithmetic trade returns without volatility adjustment.",
                resolution_standard="Mandatory bridge between arithmetic expectancy and realized terminal equity.",
            ),
            AccountingConceptDefinition(
                concept_id="MAXIMUM_DRAWDOWN",
                canonical_name="Maximum Drawdown (MaxDD)",
                unit="percentage (%)",
                mathematical_formula="MaxDD = max_{t} [ (Peak_t - E_t) / Peak_t * 100% ] where Peak_t = max_{tau <= t} E_{tau}",
                plain_english_definition="Worst observed peak-to-trough equity drop over the investment period.",
                historical_pitfall_or_defect="Measuring drawdown across closed trades only, ignoring continuous bar-level equity curve.",
                resolution_standard="Evaluate equity at every bar close, tracking high-water mark continuously.",
            ),
            AccountingConceptDefinition(
                concept_id="SHARPE_RATIO",
                canonical_name="Annualized Sharpe Ratio",
                unit="dimensionless ratio",
                mathematical_formula="Sharpe = (Annualized_Return - R_f) / Annualized_Volatility (R_f = 0.0%)",
                plain_english_definition="Reward per unit of total risk over risk-free baseline (cash zero interest).",
                historical_pitfall_or_defect="Inconsistent annualization factors (e.g. sqrt(365) vs sqrt(2190) for 4h periods).",
                resolution_standard="Standard annualization factor: sqrt(periods_per_year) = sqrt(2190) for 4h, sqrt(8760) for 1h.",
            ),
            AccountingConceptDefinition(
                concept_id="WARMUP_TIMELINE_PARITY",
                canonical_name="Warmup Timeline Parity Standard",
                unit="bars / timestamps",
                mathematical_formula="T_start = max_k (Warmup_Bars_k). Comparative eval begins at T_start for all strategies.",
                plain_english_definition="Requirement that all strategies and benchmarks begin evaluation on the exact same timestamp.",
                historical_pitfall_or_defect="Comparing Sprint 30 BTC (+110.35% at 96 bars) vs Sprint 31 BTC (+108.55% at 192 bars).",
                resolution_standard="If warmup horizons differ, either align to max warmup or document the price delta explicitly.",
            ),
        ]

    @staticmethod
    def verify_compounding_bridge(
        returns: Sequence[float],
    ) -> Tuple[float, float, float, float, float]:
        """Compute arithmetic mean, variance, volatility drag, geometric rate, and compound return."""
        r_arr = np.array(returns, dtype=float)
        n = len(r_arr)
        if n == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0

        mean_bps = float(np.mean(r_arr) * 10000.0)
        var = float(np.var(r_arr))
        vol_drag_bps = float(0.5 * var * 10000.0)
        geom_bps = mean_bps - vol_drag_bps

        compounded_tot_pct = float((np.prod(1.0 + r_arr) - 1.0) * 100.0)
        naive_compounded_pct = float(((1.0 + mean_bps / 10000.0) ** n - 1.0) * 100.0)

        return mean_bps, vol_drag_bps, geom_bps, compounded_tot_pct, naive_compounded_pct
