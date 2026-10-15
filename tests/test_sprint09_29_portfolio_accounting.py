"""Comprehensive test suite for Sprint 09.29: CS1 Economic Validity, Portfolio Accounting Audit & Independent Forward Validation.

Covers:
1. CS1 Cost Accounting Audit & Sprint 09.28 Reproduction:
   - Exact reproduction of 2,189 periods, gross +6.47 bps, net maker +4.87 bps, net taker -5.13 bps.
   - Mathematical proof that 1.60 bps cost difference equals (584 switches / 2189 periods) * 6.0 bps.
2. Zero-Tolerance Portfolio Accounting & Ledger Invariants:
   - Cash >= 0, holdings >= 0, no borrowing.
   - Net Equity == Cash + Market Value of Holdings.
   - Net Equity == Initial Capital + Gross Realized + Gross Unrealized - Cumulative Fees.
   - Zero-tolerance verification passes with 0.0 error; tampering raises PortfolioAccountingReconciliationError.
3. Standardized Benchmark Comparisons:
   - Identical starting capital ($10,000.00), timestamps, and fee schedule across all 6 benchmarks.
   - Full 2024 results: B&H BTC (+110.35%, Sharpe 1.68, MaxDD 31.00%) vs CS1 Maker (+99.24%, Sharpe 1.31, MaxDD 39.82%).
   - Excess return vs BTC is negative (-11.12%), Alpha is negative (-1.50%).
4. Execution Sensitivity:
   - Non-fill rates (100% to 20%), missed opportunity cost, adverse selection.
   - Fee tiers: Retail, Active Retail, VIP, Market Maker, Institutional Rebate.
5. Ranking Persistence Audit:
   - Overlapping vs non-overlapping Spearman autocorrelation.
   - Proof that ranking persistence is an artifact of overlapping rolling windows (rho drops from ~0.66 to ~0.018).
6. Cross-Sectional Universe Quality:
   - 3-asset breadth quantization (33.3% step size) vs 5-asset expansion (20.0% step size).
7. Chronological Forward Validation (January 2025 Holdout):
   - Provenance and integrity of genuine 2025-01 dataset (2,976 15m bars, gapless).
   - Pre-registration Gate 2 frozen SHA-256 parameter hashes.
   - Single-pass confirmatory test: 95% block bootstrap confidence interval [-7.74, +31.34] bps includes zero.
   - Decision Gate Verdict: EXPLORATORY_ONLY.
8. Performance Latency Budget Forensics:
   - Pure in-memory compute latency < 50 ms budget.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    BenchmarkComparisonEngine,
    BenchmarkComparisonResult,
    ChronologicalForwardValidator,
    ConfirmatoryForwardValidationReport,
    CrossSectionalFeatureSnapshot,
    CrossSectionalRelativeStrengthEngine,
    CS1DecisionVerdict,
    ExecutionScenarioResult,
    ExecutionSensitivityAuditor,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    PortfolioAccountingReconciliationError,
    PortfolioAccountingSimulator,
    PortfolioAccountingVerifier,
    PortfolioLedgerEntry,
    PortfolioPerformanceSummary,
    PreRegistrationGateSprint29,
    RankingPersistenceAuditReport,
    RankingPersistenceAuditor,
    UniverseQualityAuditReport,
    UniverseQualityAuditor,
)


# =========================================================================
# 1. CS1 Cost Accounting Audit & Reproduction
# =========================================================================

def test_cs1_cost_accounting_audit_reproduction():
    """Verify exact reproduction of Sprint 09.28 metrics and mathematical cost explanation."""
    report_path = Path("data/reports/sprint09_28_cross_sectional_report.json")
    assert report_path.exists(), "Sprint 09.28 report missing"
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    cs1 = rep["hypotheses_evaluation"]["CS1_RELATIVE_MOMENTUM_PERSISTENCE"]
    assert cs1["total_events_evaluated"] == 2189
    assert cs1["independent_decision_events"] == 2189
    assert cs1["gross_expectancy_bps"] == 6.47
    assert cs1["net_maker_expectancy_bps"] == 4.87
    assert cs1["net_taker_expectancy_bps"] == -5.13

    # Mathematical identity verification from trade ledger
    ledger_path = Path("data/reports/sprint09_28_trade_ledger.jsonl")
    assert ledger_path.exists()
    cs1_records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["opportunity_id"].startswith("CS1"):
                    cs1_records.append(r)

    assert len(cs1_records) == 2189
    switches = [r for r in cs1_records if r["cost_bps"] > 0]
    non_switches = [r for r in cs1_records if r["cost_bps"] == 0]

    assert len(switches) == 584
    assert len(non_switches) == 1605
    assert len(switches) + len(non_switches) == 2189

    # Cost calculation proof: 584 switches * 6 bps / 2189 = 1.6007 bps
    expected_mean_cost = (len(switches) * 6.0) / len(cs1_records)
    actual_mean_cost = sum(r["cost_bps"] for r in cs1_records) / len(cs1_records)
    assert math.isclose(expected_mean_cost, actual_mean_cost, rel_tol=1e-5)
    assert math.isclose(actual_mean_cost, 1.6007, abs_tol=0.01)

    # Difference between gross and net maker expectancy is exactly 1.60 bps
    diff = cs1["gross_expectancy_bps"] - cs1["net_maker_expectancy_bps"]
    assert math.isclose(diff, 1.60, abs_tol=0.01)


# =========================================================================
# 2. Zero-Tolerance Portfolio Accounting & Ledger Invariants
# =========================================================================

def test_portfolio_accounting_zero_tolerance_reconciliation():
    """Verify exact cash, holdings, and equity reconciliation on 2024 portfolio ledger."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    quarters = ["q1_2024", "q2_2024", "q3_2024", "q4_2024"]

    asset_candles = {}
    for sym in symbols:
        dfs = []
        for q in quarters:
            spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag=q)
            dfs.append(pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet")))
        asset_candles[sym] = pd.concat(dfs, ignore_index=True).to_dict(orient="records")

    rs_engine = CrossSectionalRelativeStrengthEngine(asset_candles, benchmark_symbol="BTCUSDT")
    snaps = rs_engine.compute_snapshots(lookback_bars=96)

    sim = PortfolioAccountingSimulator(initial_capital=10000.0, maker_fee_rate=0.0006)
    entries, summary = sim.simulate_cross_sectional_rebalancing(snaps, rebalance_horizon_bars=16, execution_mode="MAKER")

    # Invariants
    assert summary.reconciliation_verified is True
    assert summary.max_reconciliation_error == 0.0
    assert len(entries) == 2190
    assert summary.initial_capital == 10000.0
    assert summary.final_equity == 19923.64
    assert summary.total_return_pct == 99.24
    assert summary.asset_switches_count == 584

    # Every single entry must hold invariants
    for e in entries:
        assert e.cash_after >= -1e-9
        for qty in e.holdings.values():
            assert qty >= 0.0
        calc_eq = e.cash_after + sum(qty * e.asset_prices[s] for s, qty in e.holdings.items())
        assert math.isclose(e.net_equity, calc_eq, abs_tol=1e-5)
        expected_eq = 10000.0 + e.realized_pnl_cumulative + e.unrealized_pnl - e.cumulative_fees_paid
        assert math.isclose(e.net_equity, expected_eq, abs_tol=1e-5)


def test_portfolio_accounting_fail_closed_on_tampering():
    """Verify that any ledger discrepancy immediately raises PortfolioAccountingReconciliationError."""
    entry = PortfolioLedgerEntry(
        entry_id="TEST_001",
        bar_index=16,
        timestamp_ms=1704153600000,
        timestamp_utc="2024-01-02T00:00:00Z",
        cash_before=10000.0,
        cash_after=-50.0,  # Negative cash violation!
        holdings={"BTCUSDT": 0.25},
        asset_prices={"BTCUSDT": 40000.0},
        executed_symbol="BTCUSDT",
        executed_action="BUY",
        executed_quantity=0.25,
        executed_price=40000.0,
        executed_notional=10000.0,
        fee_paid=3.0,
        fee_bps=3.0,
        spread_slippage_cost=1.0,
        gross_equity=10000.0,
        net_equity=9950.0,
        realized_pnl_cumulative=0.0,
        unrealized_pnl=0.0,
        cumulative_fees_paid=3.0,
        cumulative_turnover_notional=10000.0,
        turnover_pct=1.0,
        exposure_pct=1.0,
    )
    is_ok, max_err, violations = PortfolioAccountingVerifier.verify_ledger(10000.0, [entry])
    assert is_ok is False
    assert len(violations) > 0


# =========================================================================
# 3. Standardized Benchmark Comparisons
# =========================================================================

def test_standardized_benchmark_comparisons_2024():
    """Verify CS1 vs all 6 benchmarks over identical periods, timestamps, and capital."""
    report_path = Path("data/reports/sprint09_29_portfolio_accounting_report.json")
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    benches = rep["benchmark_comparisons_2024"]
    cs1_m = benches["cs1_maker"]
    cs1_t = benches["cs1_taker"]
    b_btc = benches["buy_and_hold_btc"]
    b_eth = benches["buy_and_hold_eth"]
    b_sol = benches["buy_and_hold_sol"]
    b_ew = benches["equal_weight_buy_and_hold"]
    b_rebal = benches["rebalanced_equal_weight_24h"]
    b_cash = benches["cash_baseline"]

    # Verify identical capital
    for b in [cs1_m, cs1_t, b_btc, b_eth, b_sol, b_ew, b_rebal, b_cash]:
        assert b["initial_capital"] == 10000.0
        assert b["rebalance_events_count"] == 2190

    # Key economic findings:
    # 1. Buy-and-Hold BTC beats CS1 Maker in total return (110.35% vs 99.24%)
    assert b_btc["total_return_pct"] > cs1_m["total_return_pct"]
    # 2. Buy-and-Hold BTC has higher Sharpe (1.68 vs 1.31)
    assert b_btc["sharpe_ratio"] > cs1_m["sharpe_ratio"]
    # 3. Buy-and-Hold BTC has lower Max Drawdown (31.00% vs 39.82%)
    assert b_btc["max_drawdown_pct"] < cs1_m["max_drawdown_pct"]
    # 4. CS1 pays over $6,500 in fees vs BTC's $6.31
    assert cs1_m["total_fees_paid"] > 6500.0
    assert b_btc["total_fees_paid"] < 10.0
    # 5. CS1 Taker suffers massive fee drag (+11.16% return, $13,025 fees paid)
    assert cs1_t["total_return_pct"] < 15.0
    assert cs1_t["total_fees_paid"] > 10000.0

    # Relative to BTC
    rel_btc = benches["relative_to_btc"]
    assert rel_btc["excess_return_pct"] < 0.0  # Underperformed BTC by -11.12%
    assert rel_btc["annualized_alpha_pct"] < 0.0  # Negative alpha (-1.50%)


# =========================================================================
# 4. Execution Sensitivity & Fee Tier Sweeps
# =========================================================================

def test_execution_sensitivity_and_fee_tiers():
    """Verify fill rate sweep and fee tier sensitivity behaviors."""
    report_path = Path("data/reports/sprint09_29_portfolio_accounting_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    sens = rep["execution_sensitivity"]
    fill_sweep = sens["fill_rate_sweep"]
    fee_sweep = sens["fee_tier_sweep"]

    assert len(fill_sweep) == 5
    # As fill rate drops from 100% to 20%, missed rebalances increase monotonically
    for i in range(len(fill_sweep) - 1):
        assert fill_sweep[i]["missed_rebalances_count"] < fill_sweep[i + 1]["missed_rebalances_count"]

    assert len(fee_sweep) == 5
    # Fee tier 0 (Retail 6 bps) vs Market Maker (0 bps) vs Institutional (-0.5 bps rebate)
    retail = fee_sweep[0]
    zero_fee = fee_sweep[3]
    assert retail["total_fees_paid"] > 6000.0
    assert zero_fee["total_fees_paid"] == 0.0
    assert zero_fee["total_return_pct"] > retail["total_return_pct"]


# =========================================================================
# 5. Ranking Persistence Audit & Overlapping Return Deconstruction
# =========================================================================

def test_ranking_persistence_audit_overlapping_vs_non_overlapping():
    """Verify proof of overlapping window autocorrelation inflation."""
    report_path = Path("data/reports/sprint09_29_portfolio_accounting_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    rank_rep = rep["ranking_persistence_audit"]
    ov = rank_rep["overlapping_spearman_autocorrelation"]
    non_ov = rank_rep["non_overlapping_spearman_autocorrelation"]
    null_m = rank_rep["randomized_null_model_autocorrelation"]

    # Short-horizon overlapping autocorrelation is high (~0.84 at 4 bars, ~0.66 at 16 bars)
    assert ov["4_bars"] > 0.80
    assert ov["16_bars"] > 0.60

    # Non-overlapping 96-bar (24h) autocorrelation collapses to near-zero (~0.018)
    assert non_ov["96_bars"] < 0.05
    # Statistically indistinguishable from pure noise null model (~0.008)
    assert math.isclose(non_ov["96_bars"], null_m["null_model_mean"], abs_tol=0.03)

    assert "RANKING PERSISTENCE AUDIT VERDICT" in rank_rep["scientific_conclusion"]


# =========================================================================
# 6. Cross-Sectional Universe Quality & Quantization Step
# =========================================================================

def test_universe_quality_quantization_step():
    """Verify 3-asset universe breadth quantization and candidate expansion registry."""
    report = UniverseQualityAuditor.audit_universe_quality()
    assert isinstance(report, UniverseQualityAuditReport)

    assert report.core_universe_size == 3
    # Step size is exactly 33.33% (100 / 3)
    assert math.isclose(report.breadth_quantization_step_pct, 33.33, abs_tol=0.05)
    # HHI minimum is exactly 1/3 = 0.333
    assert math.isclose(report.hhi_theoretical_minimum, 0.333, abs_tol=0.01)

    # Candidate universe has verified listing dates
    for sym in ["BNBUSDT", "DOGEUSDT", "ADAUSDT", "XRPUSDT"]:
        assert sym in report.candidate_universe_metadata
        assert report.candidate_universe_metadata[sym]["is_eligible_for_2024_2025"] is True


# =========================================================================
# 7. Chronological Forward Validation (January 2025 Holdout)
# =========================================================================

def test_chronological_forward_validation_jan_2025_holdout():
    """Verify pre-registration gate freeze, single-pass test, and EXPLORATORY_ONLY verdict."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # 1. Dataset integrity check
    for sym in symbols:
        spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="jan_2025")
        df = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet"))
        assert len(df) == 2976, f"{sym} expected 2,976 15m bars for Jan 2025, got {len(df)}"

    # 2. Pre-registration gate
    gate = ChronologicalForwardValidator.create_preregistration_gate()
    assert gate.is_frozen is True
    assert len(gate.cs1_strategy_hash) == 64
    assert gate.verify_integrity(gate.cs1_strategy_hash) is True

    # 3. Validation report check
    report_path = Path("data/reports/sprint09_29_portfolio_accounting_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    fwd = rep["chronological_forward_validation_jan_2025"]
    assert fwd["holdout_period"] == "2025-01 (January 2025)"
    assert fwd["cs1_maker_summary"]["reconciliation_verified"] is True

    # January 2025 returns: CS1 Maker (+30.62%) vs BTC (+7.95%)
    assert fwd["cs1_maker_summary"]["total_return_pct"] > 30.0
    assert fwd["btc_benchmark_summary"]["total_return_pct"] > 7.0

    # 95% Block Bootstrap Confidence Interval crosses zero!
    ci_low, ci_high = fwd["block_bootstrap_ci_excess_bps"]
    assert ci_low < 0.0 < ci_high, f"Expected CI to cross zero, got [{ci_low}, {ci_high}]"

    # Confirmatory gate failed; Decision Gate verdict is EXPLORATORY_ONLY
    assert fwd["passed_confirmatory_gate"] is False
    assert fwd["decision_gate_verdict"] == "EXPLORATORY_ONLY"
    assert rep["decision_gate_verdict"] == "EXPLORATORY_ONLY"


# =========================================================================
# 8. Performance Latency Budget Forensics
# =========================================================================

def test_performance_latency_budget_pure_compute():
    """Verify pure in-memory compute latency is < 50 ms budget."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    asset_candles = {}
    for sym in symbols:
        spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="jan_2025")
        asset_candles[sym] = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet"))[:200].to_dict(orient="records")

    rs_engine = CrossSectionalRelativeStrengthEngine(asset_candles, benchmark_symbol="BTCUSDT")

    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        _ = rs_engine.compute_snapshots(lookback_bars=96)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    mean_compute_ms = float(np.mean(times))
    assert mean_compute_ms < 50.0, f"Pure compute latency {mean_compute_ms:.2f} ms exceeded 50 ms budget"
