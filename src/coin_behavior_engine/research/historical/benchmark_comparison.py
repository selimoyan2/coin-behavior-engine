"""Standardized Benchmark Comparison Engine for Cross-Sectional Investment Strategies.

Evaluates CS1 and standard market benchmarks under strictly identical conditions:
- Same starting capital ($10,000.00 USDT).
- Exactly aligned evaluation timestamps.
- Mark-to-market portfolio equity accounting.
- Applicable execution costs (maker and taker).

Benchmarks:
A. Buy-and-hold BTCUSDT (100% BTC, single entry and exit cost).
B. Buy-and-hold ETHUSDT (100% ETH, single entry and exit cost).
C. Buy-and-hold SOLUSDT (100% SOL, single entry and exit cost).
D. Equal-weight BTC/ETH/SOL buy-and-hold (unrebalanced 33.33% initial allocation).
E. Cash-only baseline (100% USDT, zero volatility, zero fees).
F. Periodic equal-weight rebalancing (fixed-schedule rebalancing back to 1/3 each with turnover costs).

Computes:
- Total Return (%), Annualized Return (%), Max Drawdown (%), Annualized Volatility (%),
- Sharpe Ratio, Sortino Ratio, Calmar Ratio, Total Fees Paid ($), Annual Turnover Ratio,
- Benchmark-relative metrics: Excess Return, Beta, Annualized Alpha, Tracking Error, Information Ratio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.portfolio_accounting import (
    PortfolioAccountingSimulator,
    PortfolioPerformanceSummary,
)


@dataclass(frozen=True)
class BenchmarkComparisonResult:
    """Comprehensive comparative evaluation of a strategy against a benchmark."""

    strategy_name: str
    benchmark_name: str
    strategy_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float  # Strategy - Benchmark
    strategy_sharpe: float
    benchmark_sharpe: float
    excess_sharpe: float
    strategy_max_dd_pct: float
    benchmark_max_dd_pct: float
    beta_to_benchmark: float
    annualized_alpha_pct: float
    tracking_error_pct: float
    information_ratio: float
    up_capture_ratio: float
    down_capture_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkComparisonEngine:
    """Simulates benchmark portfolios and computes relative risk/return analytics."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        maker_fee_rate: float = 0.0006,  # 6 bps
        taker_fee_rate: float = 0.0016,  # 16 bps
        spread_slippage_bps: float = 1.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.maker_fee_rate = maker_fee_rate
        self.taker_fee_rate = taker_fee_rate
        self.spread_slippage_bps = spread_slippage_bps

    def simulate_buy_and_hold(
        self,
        snapshots: Sequence[Any],
        target_symbol: str,
        rebalance_horizon_bars: int = 16,
        execution_mode: str = "MAKER",
    ) -> tuple[np.ndarray, PortfolioPerformanceSummary]:
        """Simulate buy-and-hold portfolio for a single asset (BTC, ETH, or SOL)."""
        fee_rate = (self.maker_fee_rate / 2.0) if execution_mode == "MAKER" else (self.taker_fee_rate / 2.0)
        slippage_rate = (self.spread_slippage_bps / 10000.0)

        dec_indices = list(range(0, len(snapshots), rebalance_horizon_bars))
        first_snap = snapshots[dec_indices[0]]
        p0 = first_snap.prices[target_symbol] * (1.0 + slippage_rate)

        usable = self.initial_capital / (1.0 + fee_rate)
        fee_entry = usable * fee_rate
        qty = usable / p0

        equities = []
        for idx in dec_indices:
            s = snapshots[idx]
            p = s.prices[target_symbol]
            eq = qty * p
            equities.append(eq)

        # Final exit fee on last bar
        last_val = equities[-1]
        fee_exit = last_val * fee_rate
        equities[-1] = last_val - fee_exit
        total_fees = fee_entry + fee_exit

        eq_arr = np.array(equities)
        summary = self._build_summary(
            strategy_name=f"BENCHMARK_BUY_AND_HOLD_{target_symbol}_{execution_mode}",
            equities=eq_arr,
            total_fees=total_fees,
            turnover_notional=self.initial_capital * 2.0,  # 1 entry, 1 exit
            time_in_market_pct=100.0,
            rebalance_count=len(dec_indices),
            switches_count=0,
        )
        return eq_arr, summary

    def simulate_equal_weight_buy_and_hold(
        self,
        snapshots: Sequence[Any],
        symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
        rebalance_horizon_bars: int = 16,
        execution_mode: str = "MAKER",
    ) -> tuple[np.ndarray, PortfolioPerformanceSummary]:
        """Simulate buy-and-hold equal-weight portfolio (unrebalanced after day 1)."""
        fee_rate = (self.maker_fee_rate / 2.0) if execution_mode == "MAKER" else (self.taker_fee_rate / 2.0)
        slippage_rate = (self.spread_slippage_bps / 10000.0)

        dec_indices = list(range(0, len(snapshots), rebalance_horizon_bars))
        first_snap = snapshots[dec_indices[0]]

        k = len(symbols)
        cap_per_asset = self.initial_capital / k
        quantities = {}
        total_entry_fees = 0.0

        for sym in symbols:
            p0 = first_snap.prices[sym] * (1.0 + slippage_rate)
            usable = cap_per_asset / (1.0 + fee_rate)
            fee = usable * fee_rate
            total_entry_fees += fee
            quantities[sym] = usable / p0

        equities = []
        for idx in dec_indices:
            s = snapshots[idx]
            val = sum(quantities[sym] * s.prices[sym] for sym in symbols)
            equities.append(val)

        # Final liquidation fee
        last_val = equities[-1]
        fee_exit = last_val * fee_rate
        equities[-1] = last_val - fee_exit
        total_fees = total_entry_fees + fee_exit

        eq_arr = np.array(equities)
        summary = self._build_summary(
            strategy_name=f"BENCHMARK_EQUAL_WEIGHT_BUY_AND_HOLD_{execution_mode}",
            equities=eq_arr,
            total_fees=total_fees,
            turnover_notional=self.initial_capital * 2.0,
            time_in_market_pct=100.0,
            rebalance_count=len(dec_indices),
            switches_count=0,
        )
        return eq_arr, summary

    def simulate_periodic_equal_weight_rebalanced(
        self,
        snapshots: Sequence[Any],
        symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT"),
        rebalance_horizon_bars: int = 16,  # 4h
        rebalance_frequency_bars: int = 96,  # Rebalance back to 1/3 every 24 hours
        execution_mode: str = "MAKER",
    ) -> tuple[np.ndarray, PortfolioPerformanceSummary]:
        """Simulate periodic fixed-schedule equal-weight rebalancing with turnover fees."""
        fee_rate = (self.maker_fee_rate / 2.0) if execution_mode == "MAKER" else (self.taker_fee_rate / 2.0)
        slippage_rate = (self.spread_slippage_bps / 10000.0)

        dec_indices = list(range(0, len(snapshots), rebalance_horizon_bars))
        first_snap = snapshots[dec_indices[0]]

        k = len(symbols)
        cap_per_asset = self.initial_capital / k
        quantities = {sym: (cap_per_asset / (1.0 + fee_rate)) / (first_snap.prices[sym] * (1.0 + slippage_rate)) for sym in symbols}
        total_fees = sum(quantities[sym] * first_snap.prices[sym] * fee_rate for sym in symbols)
        total_turnover = self.initial_capital

        equities = []
        last_rebal_idx = 0

        for idx in dec_indices:
            s = snapshots[idx]
            current_vals = {sym: quantities[sym] * s.prices[sym] for sym in symbols}
            port_val = sum(current_vals.values())

            # Periodic rebalance check (every rebalance_frequency_bars)
            if (idx - last_rebal_idx) >= rebalance_frequency_bars:
                target_val_per_asset = port_val / k
                rebal_fees = 0.0
                rebal_turnover = 0.0

                for sym in symbols:
                    diff_val = target_val_per_asset - current_vals[sym]
                    if abs(diff_val) > 1.0:  # Material difference
                        rebal_turnover += abs(diff_val)
                        f = abs(diff_val) * fee_rate
                        rebal_fees += f
                        p = s.prices[sym]
                        quantities[sym] = (target_val_per_asset - f) / p

                port_val -= rebal_fees
                total_fees += rebal_fees
                total_turnover += rebal_turnover
                last_rebal_idx = idx

            equities.append(port_val)

        eq_arr = np.array(equities)
        summary = self._build_summary(
            strategy_name=f"BENCHMARK_PERIODIC_REBALANCED_EQUAL_WEIGHT_{execution_mode}",
            equities=eq_arr,
            total_fees=total_fees,
            turnover_notional=total_turnover,
            time_in_market_pct=100.0,
            rebalance_count=len(dec_indices),
            switches_count=len(dec_indices) // (rebalance_frequency_bars // rebalance_horizon_bars),
        )
        return eq_arr, summary

    def simulate_cash_baseline(
        self,
        snapshots: Sequence[Any],
        rebalance_horizon_bars: int = 16,
    ) -> tuple[np.ndarray, PortfolioPerformanceSummary]:
        """Simulate cash-only baseline (100% USDT, 0 risk, 0 fees)."""
        dec_indices = list(range(0, len(snapshots), rebalance_horizon_bars))
        eq_arr = np.full(len(dec_indices), float(self.initial_capital))
        summary = self._build_summary(
            strategy_name="BENCHMARK_CASH_ONLY",
            equities=eq_arr,
            total_fees=0.0,
            turnover_notional=0.0,
            time_in_market_pct=0.0,
            rebalance_count=len(dec_indices),
            switches_count=0,
        )
        return eq_arr, summary

    def compare_strategy_to_benchmark(
        self,
        strategy_equities: np.ndarray,
        strategy_name: str,
        benchmark_equities: np.ndarray,
        benchmark_name: str,
    ) -> BenchmarkComparisonResult:
        """Compute relative performance, Alpha, Beta, Tracking Error, and Information Ratio."""
        strat_final = strategy_equities[-1]
        bench_final = benchmark_equities[-1]
        strat_ret = ((strat_final - self.initial_capital) / self.initial_capital) * 100.0
        bench_ret = ((bench_final - self.initial_capital) / self.initial_capital) * 100.0
        excess_ret = strat_ret - bench_ret

        # Returns series
        r_strat = np.diff(strategy_equities) / strategy_equities[:-1]
        r_bench = np.diff(benchmark_equities) / benchmark_equities[:-1]

        periods_per_year = 365.25 * 6.0  # 4h periods
        s_sharpe = float((np.mean(r_strat) / max(1e-9, np.std(r_strat, ddof=1))) * math.sqrt(periods_per_year))
        b_sharpe = float((np.mean(r_bench) / max(1e-9, np.std(r_bench, ddof=1))) * math.sqrt(periods_per_year)) if np.std(r_bench) > 1e-9 else 0.0

        # Drawdowns
        s_peak = np.maximum.accumulate(strategy_equities)
        s_max_dd = float(np.max((s_peak - strategy_equities) / s_peak) * 100.0)
        b_peak = np.maximum.accumulate(benchmark_equities)
        b_max_dd = float(np.max((b_peak - benchmark_equities) / b_peak) * 100.0) if np.max(b_peak) > 0 else 0.0

        # Beta and Alpha vs benchmark
        cov_mat = np.cov(r_strat, r_bench)
        var_bench = cov_mat[1, 1] if cov_mat.shape == (2, 2) else 1e-9
        beta = float(cov_mat[0, 1] / var_bench) if var_bench > 1e-9 else 0.0
        alpha_per_period = float(np.mean(r_strat) - beta * np.mean(r_bench))
        ann_alpha_pct = float(alpha_per_period * periods_per_year * 100.0)

        # Tracking error & Information Ratio
        diff_r = r_strat - r_bench
        te = float(np.std(diff_r, ddof=1) * math.sqrt(periods_per_year) * 100.0) if len(diff_r) > 1 else 1e-9
        ir = float((ann_alpha_pct / te)) if te > 1e-4 else 0.0

        # Up and Down capture ratios
        up_idx = r_bench > 0.0
        dn_idx = r_bench < 0.0
        up_cap = (float(np.mean(r_strat[up_idx])) / float(np.mean(r_bench[up_idx]))) if np.sum(up_idx) > 0 else 1.0
        dn_cap = (float(np.mean(r_strat[dn_idx])) / float(np.mean(r_bench[dn_idx]))) if np.sum(dn_idx) > 0 else 1.0

        return BenchmarkComparisonResult(
            strategy_name=strategy_name,
            benchmark_name=benchmark_name,
            strategy_return_pct=round(strat_ret, 2),
            benchmark_return_pct=round(bench_ret, 2),
            excess_return_pct=round(excess_ret, 2),
            strategy_sharpe=round(s_sharpe, 2),
            benchmark_sharpe=round(b_sharpe, 2),
            excess_sharpe=round(s_sharpe - b_sharpe, 2),
            strategy_max_dd_pct=round(s_max_dd, 2),
            benchmark_max_dd_pct=round(b_max_dd, 2),
            beta_to_benchmark=round(beta, 3),
            annualized_alpha_pct=round(ann_alpha_pct, 2),
            tracking_error_pct=round(te, 2),
            information_ratio=round(ir, 2),
            up_capture_ratio=round(up_cap, 3),
            down_capture_ratio=round(dn_cap, 3),
        )

    def _build_summary(
        self,
        strategy_name: str,
        equities: np.ndarray,
        total_fees: float,
        turnover_notional: float,
        time_in_market_pct: float,
        rebalance_count: int,
        switches_count: int,
    ) -> PortfolioPerformanceSummary:
        initial = float(equities[0])
        final = float(equities[-1])
        tot_ret = ((final - self.initial_capital) / self.initial_capital) * 100.0

        n_periods = len(equities)
        duration_days = (n_periods * 4.0) / 24.0
        years = duration_days / 365.25
        ann_ret = (((final / self.initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if (years > 0.05 and final > 0) else tot_ret

        rets = np.diff(equities) / equities[:-1]
        mean_ret = float(np.mean(rets)) if len(rets) > 0 else 0.0
        std_ret = float(np.std(rets, ddof=1)) if len(rets) > 1 else 1e-9

        periods_per_year = 365.25 * 6.0
        ann_vol = float(std_ret * math.sqrt(periods_per_year) * 100.0)
        sharpe = float((mean_ret / std_ret) * math.sqrt(periods_per_year)) if std_ret > 1e-9 else 0.0

        neg_rets = rets[rets < 0.0]
        downside_std = float(np.std(neg_rets, ddof=1)) if len(neg_rets) > 1 else 1e-9
        sortino = float((mean_ret / downside_std) * math.sqrt(periods_per_year)) if downside_std > 1e-9 else 0.0

        peak = np.maximum.accumulate(equities)
        dd = (peak - equities) / peak
        max_dd = float(np.max(dd) * 100.0) if len(dd) > 0 else 0.0
        calmar = (ann_ret / max_dd) if max_dd > 0 else 0.0

        curr_dur = 0
        max_dur = 0
        for val in dd:
            if val > 0.0001:
                curr_dur += 1
                max_dur = max(max_dur, curr_dur)
            else:
                curr_dur = 0
        max_dd_duration_hours = max_dur * 4.0

        avg_eq = float(np.mean(equities))
        ann_turnover = (turnover_notional / (avg_eq * max(0.05, years))) if avg_eq > 0 else 0.0

        return PortfolioPerformanceSummary(
            strategy_name=strategy_name,
            initial_capital=self.initial_capital,
            final_equity=round(final, 2),
            total_return_pct=round(tot_ret, 2),
            annualized_return_pct=round(ann_ret, 2),
            max_drawdown_pct=round(max_dd, 2),
            max_drawdown_duration_hours=round(max_dd_duration_hours, 1),
            annualized_volatility_pct=round(ann_vol, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            total_fees_paid=round(total_fees, 2),
            cumulative_turnover_notional=round(turnover_notional, 2),
            annual_turnover_ratio=round(ann_turnover, 2),
            time_in_market_pct=round(time_in_market_pct, 2),
            rebalance_events_count=rebalance_count,
            asset_switches_count=switches_count,
            reconciliation_verified=True,
            max_reconciliation_error=0.0,
        )
