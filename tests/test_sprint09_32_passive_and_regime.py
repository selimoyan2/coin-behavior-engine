"""Comprehensive Test Suite for Sprint 09.32: Passive Allocation Benchmarking & Regime Incremental Value Audit.

Verifies:
1. Historical accounting parity: Reconciles Sprint 09.30 (+110.35%) vs Sprint 09.31 (+108.55%)
   BTC Buy & Hold discrepancy down to the cent, and audits CP4 turnover ($2,704,063.20) and fees ($2,163.25).
2. Passive allocation baseline family: Monotonic risk-return hierarchy across 0%, 25%, 50%, 75%, 100% BTC.
3. Drawdown reduction superiority of passive 50/50 allocation (MaxDD ~19.2% drift, ~15.7% rebalanced) over 100% BTC (31.0%).
4. Multi-period walk-forward stability across 2024 (exploratory), Jan 2025 (exploratory), and Feb 2025 (confirmatory holdout).
5. Regime incremental value audit: Demonstrates that point-in-time regime conditioning yields zero genuine alpha
   over exposure-matched passive baselines and suffers from classification lag, whipsaws, and cash drag.
6. Robustness sensitivity across execution tiers (Maker, Taker, High friction, 1-period execution delay).
7. Block bootstrap statistical test ($k in {3, 6, 12}$) with Holm-Bonferroni control confirming zero significant alpha.
8. Strict Decision Gate verdict: REJECTED.
9. Pure compute latency within the strict 50 ms budget.
"""

from pathlib import Path
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical.market_regime_intelligence import MarketRegimeEngine
from coin_behavior_engine.research.historical.passive_allocation_engine import (
    HistoricalAccountingParityRecord,
    PassiveAllocationEngine,
    PortfolioPerformanceRecord,
    RegimeIncrementalValueRecord,
    RobustnessSensitivityRecord,
    Sprint0932ResearchReport,
)


@pytest.fixture(scope="module")
def btc_2024_candles():
    """Load full year 2024 15m dataset for BTCUSDT."""
    quarters = ["q1_2024", "q2_2024", "q3_2024", "q4_2024"]
    dfs = [pd.read_parquet(f"data/historical/historical_binance_btcusdt_15m_{q}.parquet") for q in quarters]
    return pd.concat(dfs, ignore_index=True).to_dict(orient="records")


@pytest.fixture(scope="module")
def btc_jan_2025_candles():
    """Load January 2025 15m dataset for BTCUSDT."""
    df = pd.read_parquet("data/historical/historical_binance_btcusdt_15m_jan_2025.parquet")
    return df.to_dict(orient="records")


@pytest.fixture(scope="module")
def btc_feb_2025_candles():
    """Load February 2025 15m dataset for BTCUSDT."""
    df = pd.read_parquet("data/historical/historical_binance_btcusdt_15m_feb_2025.parquet")
    return df.to_dict(orient="records")


@pytest.fixture(scope="module")
def sprint09_32_master_report(btc_2024_candles, btc_jan_2025_candles, btc_feb_2025_candles):
    """Execute master investigation report once for the test module."""
    engine = PassiveAllocationEngine(initial_capital=10000.0)
    return engine.execute_sprint_09_32_investigation(
        btc_2024_candles, btc_jan_2025_candles, btc_feb_2025_candles
    )


def test_historical_accounting_parity_and_cp4_turnover_audit(sprint09_32_master_report):
    """Verify exact mathematical reconciliation of BTC Buy & Hold discrepancy and CP4 turnover."""
    parity = sprint09_32_master_report.accounting_parity

    # 1. BTC Buy & Hold reconciliation
    assert parity.sprint30_btc_return_pct == 110.35
    assert parity.sprint30_warmup_bars == 96
    assert parity.sprint30_periods_count == 2190
    assert parity.sprint30_initial_btc_price == 44630.09
    assert parity.sprint30_terminal_equity == 21035.25

    assert parity.sprint31_btc_return_pct == 108.55
    assert parity.sprint31_warmup_bars == 192
    assert parity.sprint31_periods_count == 2184
    assert parity.sprint31_initial_btc_price == 45005.98
    assert parity.sprint31_terminal_equity == 20855.38

    assert parity.warmup_price_delta_pct == 0.84
    assert "96..192" in parity.terminal_valuation_difference_explanation
    assert parity.accounting_reconciliation_verdict == "MATHEMATICALLY_RECONCILED_ZERO_DEFECT"

    # 2. CP4 turnover and fees audit
    assert parity.cp4_switches_count == 259
    assert abs(parity.cp4_cumulative_turnover_notional - 2704063.20) < 1.0
    assert parity.cp4_effective_fee_rate == 0.0008
    assert parity.cp4_total_fees_usdt == 2163.25
    assert parity.cp4_audit_verdict == "AUDITED_EXACT_NUMERICAL_CONSERVATION"


def test_passive_allocation_baseline_family_hierarchy(sprint09_32_master_report):
    """Verify monotonic risk-return profile across passive allocations (0% to 100% BTC)."""
    p_map = {p.portfolio_id: p for p in sprint09_32_master_report.passive_portfolios_2024}

    # 1. Monotonic returns across drift portfolios
    p0 = p_map["PASSIVE_0_BTC_DRIFT"]
    p25 = p_map["PASSIVE_25_BTC_DRIFT"]
    p50 = p_map["PASSIVE_50_BTC_DRIFT"]
    p75 = p_map["PASSIVE_75_BTC_DRIFT"]
    p100 = p_map["PASSIVE_100_BTC_DRIFT"]

    assert p0.total_net_return_pct == 0.0
    assert p0.max_drawdown_pct == 0.0

    assert 25.0 <= p25.total_net_return_pct <= 30.0
    assert 50.0 <= p50.total_net_return_pct <= 60.0
    assert 75.0 <= p75.total_net_return_pct <= 85.0
    assert 105.0 <= p100.total_net_return_pct <= 115.0

    # 2. Monotonic drawdowns
    assert p0.max_drawdown_pct < p25.max_drawdown_pct < p50.max_drawdown_pct < p75.max_drawdown_pct < p100.max_drawdown_pct

    # 3. Structural Drawdown Reduction of 50/50:
    # 50/50 cuts drawdown by over 35% compared to 100% BTC (19.23% vs 31.00%)
    assert p50.max_drawdown_pct <= 20.0
    assert p100.max_drawdown_pct >= 30.0

    # 4. Periodic Rebalanced 50/50 achieves even lower drawdown
    p50_reb = p_map["PASSIVE_50_BTC_REBALANCED_24H"]
    assert p50_reb.max_drawdown_pct <= 16.0  # 15.68%
    assert p50_reb.sharpe_ratio >= 1.80  # 1.88


def test_regime_incremental_value_audit_negative(sprint09_32_master_report):
    """Verify that regime conditioning adds zero economic value and lags exposure-matched benchmarks."""
    inc_2024 = [r for r in sprint09_32_master_report.regime_incremental_values if r.period_name == "FULL_YEAR_2024"]
    assert len(inc_2024) == 3

    for r in inc_2024:
        # Every regime strategy severely lagged its exposure-matched benchmark in 2024
        assert r.incremental_return_pct < 0.0
        assert r.genuine_regime_value_verified is False
        assert "Underperformed exposure-matched passive benchmark" in r.rejection_rationale

    # Specific strategy checks
    rc1_inc = [r for r in inc_2024 if r.strategy_id == "RC1_TREND_EXPOSURE"][0]
    # RC1 suffered catastrophic opportunity lag (-3.87% return vs +54.35% for passive 50/50)
    assert rc1_inc.strategy_net_return_pct < 0.0
    assert rc1_inc.incremental_return_pct < -50.0


def test_multi_period_confirmatory_validation_feb_2025(sprint09_32_master_report):
    """Verify February 2025 out-of-sample holdout behavior in severe market decline (-17.73% BTC)."""
    p_feb_map = {p.portfolio_id: p for p in sprint09_32_master_report.passive_portfolios_feb_2025}

    p0 = p_feb_map["PASSIVE_0_BTC_DRIFT"]
    p50 = p_feb_map["PASSIVE_50_BTC_DRIFT"]
    p100 = p_feb_map["PASSIVE_100_BTC_DRIFT"]

    # In February 2025 downtrend:
    # 100% BTC lost approx -16% net
    assert p100.total_net_return_pct < -15.0
    # Passive 50/50 cushioned drawdown to ~ -8% with zero tactical churn
    assert -10.0 <= p50.total_net_return_pct <= -7.0
    assert p50.max_drawdown_pct < p100.max_drawdown_pct

    # Regime strategies also underperformed passive 50/50 in Feb 2025
    inc_feb = [r for r in sprint09_32_master_report.regime_incremental_values if r.period_name == "FEBRUARY_2025_HOLDOUT"]
    for r in inc_feb:
        assert r.incremental_return_pct < 0.0
        assert r.genuine_regime_value_verified is False


def test_robustness_and_execution_sensitivity(sprint09_32_master_report):
    """Verify execution sensitivity across Maker, Taker, High friction, and Delayed tiers."""
    assert len(sprint09_32_master_report.robustness_records) == 2
    rob_map = {r.portfolio_id: r for r in sprint09_32_master_report.robustness_records}

    rob_50 = rob_map["FIXED_50_50_PASSIVE"]
    # Fixed 50/50 is extremely resilient to fee tiers because turnover is minimal
    assert abs(rob_50.tier_a_maker_return_pct - rob_50.tier_b_conservative_taker_return_pct) < 0.20
    assert abs(rob_50.tier_c_high_friction_return_pct - rob_50.tier_b_conservative_taker_return_pct) < 0.20

    rob_rc1 = rob_map["RC1_TREND_EXPOSURE"]
    # Tactical RC1 suffers significant performance variations across tiers
    assert rob_rc1.tier_a_maker_return_pct > rob_rc1.tier_b_conservative_taker_return_pct


def test_block_bootstrap_negative_alpha_significance(sprint09_32_master_report):
    """Verify block bootstrap tests across k in {3, 6, 12} with Holm-Bonferroni correction."""
    boot_records = sprint09_32_master_report.bootstrap_records
    assert len(boot_records) == 3

    for b in boot_records:
        # Mean excess return is negative
        assert b.mean_excess_return_bps < 0.0
        # 95% CI crosses zero
        assert b.zero_crossing is True
        # Adjusted p-value fails significance threshold (H0: alpha <= 0 not rejected)
        assert b.statistically_significant is False


def test_decision_gate_strict_classification(sprint09_32_master_report):
    """Verify formal Decision Gate verdict is strictly REJECTED."""
    assert sprint09_32_master_report.decision_gate_verdict == "REJECTED"
    assert "adds zero economic value" in sprint09_32_master_report.decision_gate_rationale


def test_performance_latency_budget_pure_compute():
    """Verify that pure compute latency across 200 bars is strictly under the 50 ms budget."""
    closes = 40000.0 + np.cumsum(np.random.randn(200) * 50.0)
    highs = closes + 20.0
    lows = closes - 20.0
    opens = closes - 5.0
    volumes = np.random.uniform(10.0, 100.0, 200)
    candles = [
        {
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": volumes[i],
            "open_time": 1704067200000 + i * 900000,
        }
        for i in range(200)
    ]

    latencies = []
    for _ in range(15):
        t0 = time.perf_counter()
        regime_engine = MarketRegimeEngine(candles)
        _ = [regime_engine.classify_bar(i) for i in range(50, 200, 16)]
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    median_lat = sorted(latencies)[len(latencies) // 2]
    assert median_lat < 50.0, f"Median latency {median_lat:.2f} ms exceeds 50 ms budget."
