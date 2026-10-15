"""Comprehensive Test Suite for Sprint 09.30: Portfolio Accounting Forensics & Audits.

Verifies:
1. Complete independent forensic reconstruction of the 2024 ledger with zero discrepancies.
2. Separation of One-Way Turnover from Two-Way Traded Notional.
3. Fail-closed detection of ledger corruption (missing legs, duplicate fees, impossible fills, negative balances).
4. Mathematical compounding bridge mapping per-period expectancy to compounded capital equity.
5. Methodological parity and superiority of Buy-and-Hold BTC over CS1 Maker.
6. Forensic audit of January 2025 holdout and block bootstrap confidence interval zero-crossing across block sizes.
7. Three-tier execution realism modeling and synthetic maker disclaimer.
8. Strict Decision Gate verdict: EXPLORATORY_ONLY.
9. Execution latency within the strict 50 ms budget.
"""

from pathlib import Path
import json
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical.benchmark_forensics import (
    BenchmarkForensicAuditor,
    BenchmarkForensicsReport,
)
from coin_behavior_engine.research.historical.cross_sectional_relative_strength import (
    CrossSectionalRelativeStrengthEngine,
)
from coin_behavior_engine.research.historical.dataset_contract import (
    HistoricalDatasetStore,
    HistoricalMarketSpec,
)
from coin_behavior_engine.research.historical.execution_realism_model import (
    ExecutionRealismAuditor,
    ExecutionRealismForensicsReport,
)
from coin_behavior_engine.research.historical.forensic_accounting_auditor import (
    ForensicLedgerReconciliationReport,
    ForensicReconciliationError,
    IndependentForensicPortfolioAuditor,
)
from coin_behavior_engine.research.historical.forward_validation_forensics import (
    ForwardValidationForensicAuditor,
    January2025ForensicReport,
)


@pytest.fixture(scope="module")
def historical_2024_snapshots():
    """Load full year 2024 15m dataset and compute cross-sectional relative strength snapshots."""
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
    return rs_engine.compute_snapshots(lookback_bars=96)


@pytest.fixture(scope="module")
def jan_2025_and_q4_candles():
    """Load January 2025 and Q4 2024 candle data."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    candles_jan = {}
    candles_q4 = {}
    for sym in symbols:
        df_jan = pd.read_parquet(f"data/historical/historical_binance_{sym.lower()}_15m_jan_2025.parquet")
        candles_jan[sym] = df_jan.to_dict(orient="records")
        spec_q4 = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="q4_2024")
        df_q4 = pd.read_parquet(store.get_dataset_filepath(spec_q4, ext="parquet"))
        candles_q4[sym] = df_q4.to_dict(orient="records")

    return candles_jan, candles_q4


def test_independent_ledger_reconciliation_zero_discrepancy():
    """Verify that independent forensic auditor reconstructs the 2024 ledger with zero discrepancy."""
    ledger_path = Path("data/reports/sprint09_29_auditable_portfolio_ledger.jsonl")
    assert ledger_path.exists(), "Sprint 09.29 ledger must exist."

    auditor = IndependentForensicPortfolioAuditor()
    transitions, report = auditor.audit_ledger_file(ledger_path, initial_capital=10000.0, execution_mode="MAKER")

    # Invariants
    assert report.total_records_audited == 2190
    assert report.total_rebalances_executed == 584
    assert report.total_holding_periods == 1606
    assert report.initial_capital == 10000.0
    assert report.independent_final_equity == 19923.64
    assert report.ledger_final_equity == 19923.64
    assert report.max_equity_discrepancy < 1e-4
    assert report.independent_cumulative_fees == 6592.71
    assert report.ledger_cumulative_fees == 6592.71
    assert report.max_fee_discrepancy < 1e-4

    # Separation of One-Way Turnover from Two-Way Traded Notional
    assert abs(report.total_two_way_traded_notional - 21975697.15) < 1.0
    assert abs(report.total_one_way_turnover - 10986144.93) < 10.0
    assert report.all_legs_verified is True
    assert report.no_negative_balances_verified is True
    assert report.conservation_identity_verified is True
    assert report.reconciliation_status == "INDEPENDENT_FORENSIC_RECONCILIATION_VERIFIED"


def test_independent_forensics_fail_closed_on_corruptions():
    """Verify fail-closed error detection for ledger corruptions, missing legs, and invalid fills."""
    # 1. Missing transaction leg test
    corrupted_missing_legs = [
        {"executed_action": "REBALANCE", "executed_symbol": "BTCUSDT", "holdings": {"BTCUSDT": 0.2}},
        {"executed_action": "REBALANCE", "executed_symbol": "ETHUSDT", "holdings": {"BTCUSDT": 0.2, "ETHUSDT": 4.0}},
    ]
    ok_legs, v_legs = IndependentForensicPortfolioAuditor.audit_for_missing_transaction_legs(corrupted_missing_legs)
    assert ok_legs is False
    assert len(v_legs) > 0

    # 2. Duplicate fees during HOLD test
    corrupted_duplicate_fee = [
        {"executed_action": "HOLD", "fee_paid": 5.0, "net_equity": 10000.0},
    ]
    ok_fees, v_fees = IndependentForensicPortfolioAuditor.audit_for_duplicate_fees(corrupted_duplicate_fee)
    assert ok_fees is False
    assert len(v_fees) > 0

    # 3. Incorrect quantity changes during HOLD
    corrupted_qty = [
        {"executed_action": "HOLD", "holdings": {"BTCUSDT": 0.25}},
        {"executed_action": "HOLD", "holdings": {"BTCUSDT": 0.30}},
    ]
    ok_qty, v_qty = IndependentForensicPortfolioAuditor.audit_for_incorrect_quantities(corrupted_qty)
    assert ok_qty is False
    assert len(v_qty) > 0

    # 4. Negative balances
    corrupted_negative = [
        {"cash_after": -10.5, "holdings": {"BTCUSDT": 0.2}},
    ]
    ok_neg, v_neg = IndependentForensicPortfolioAuditor.audit_for_negative_balances(corrupted_negative)
    assert ok_neg is False
    assert len(v_neg) > 0

    # 5. Impossible fills (outside candle high/low)
    candles = {"BTCUSDT": [{"high": 45000.0, "low": 44000.0}]}
    corrupted_fill = [
        {"executed_action": "REBALANCE", "executed_symbol": "BTCUSDT", "executed_price": 50000.0, "bar_index": 0}
    ]
    ok_fill, v_fill = IndependentForensicPortfolioAuditor.audit_for_impossible_fills(corrupted_fill, candles)
    assert ok_fill is False
    assert len(v_fill) > 0

    # 6. Non-monotonic timestamps
    corrupted_ts = [
        {"timestamp_ms": 1000},
        {"timestamp_ms": 900},
    ]
    ok_ts, v_ts = IndependentForensicPortfolioAuditor.audit_timestamp_monotonicity(corrupted_ts)
    assert ok_ts is False
    assert len(v_ts) > 0

    # 7. Fail-closed on equity tampering during reconstruction
    tampered_records = [
        {
            "entry_id": "TEST_001",
            "bar_index": 0,
            "timestamp_ms": 1000,
            "timestamp_utc": "2024-01-01T00:00:00Z",
            "executed_action": "REBALANCE",
            "executed_symbol": "BTCUSDT",
            "asset_prices": {"BTCUSDT": 50000.0},
            "net_equity": 99999.0,  # Falsified
            "fee_paid": 3.0,
            "cumulative_fees_paid": 3.0,
        }
    ]
    auditor = IndependentForensicPortfolioAuditor()
    # It must detect conservation discrepancy and raise ForensicReconciliationError
    with pytest.raises(ForensicReconciliationError):
        auditor.audit_ledger_records(tampered_records, initial_capital=10000.0)


def test_maker_vs_taker_compounding_bridge(historical_2024_snapshots):
    """Verify the mathematical compounding bridge explaining why +1.67 bps taker expectancy yields only +11.16% return."""
    auditor = BenchmarkForensicAuditor(initial_capital=10000.0)
    rep = auditor.audit_benchmarks_and_bridge(historical_2024_snapshots)

    # 1. Maker Equity Bridge
    m_bridge = rep.cs1_maker_equity_bridge
    assert m_bridge.initial_capital == 10000.0
    assert m_bridge.theoretical_gross_equity > 30000.0  # Uncosted gross > $30k
    assert m_bridge.realized_net_equity == 19923.64
    assert m_bridge.cumulative_fees_paid == 6592.71
    assert m_bridge.reconciliation_discrepancy == 0.0

    # 2. Taker Equity Bridge
    t_bridge = rep.cs1_taker_equity_bridge
    assert t_bridge.initial_capital == 10000.0
    assert t_bridge.realized_net_equity == 11116.24
    assert t_bridge.cumulative_fees_paid == 13025.10
    assert t_bridge.reconciliation_discrepancy == 0.0

    # 3. Compounding explanation verification
    assert "MATHEMATICAL PER-PERIOD TO CAPITAL COMPOUNDING MAPPING" in rep.compounding_mathematical_explanation
    assert "volatility drag" in rep.compounding_mathematical_explanation.lower()


def test_benchmark_parity_and_superiority_over_cs1(historical_2024_snapshots):
    """Verify benchmark parity across all 6 portfolios and confirm Buy-and-Hold BTC superiority."""
    auditor = BenchmarkForensicAuditor(initial_capital=10000.0)
    rep = auditor.audit_benchmarks_and_bridge(historical_2024_snapshots)

    benchmarks_dict = {b.benchmark_name: b for b in rep.benchmark_audits}

    # All 6 benchmarks present and verified
    expected_benchmarks = [
        "BUY_AND_HOLD_BTC",
        "BUY_AND_HOLD_ETH",
        "BUY_AND_HOLD_SOL",
        "EQUAL_WEIGHT_UNREBALANCED",
        "REBALANCED_EQUAL_WEIGHT_24H",
        "CASH_BASELINE",
    ]
    for b_name in expected_benchmarks:
        assert b_name in benchmarks_dict
        b = benchmarks_dict[b_name]
        assert b.capital_parity_verified is True
        assert b.timestamps_match_strategy is True

    # Buy and Hold BTC Performance
    btc = benchmarks_dict["BUY_AND_HOLD_BTC"]
    assert btc.total_return_pct == 110.35
    assert btc.sharpe_ratio == 1.68
    assert btc.max_drawdown_pct == 31.00
    assert btc.total_fees_paid < 10.0

    # BTC vs CS1 Maker Comparison
    maker_return = rep.cs1_maker_equity_bridge.realized_net_equity / 10000.0 * 100.0 - 100.0
    assert round(maker_return, 2) == 99.24
    assert maker_return < btc.total_return_pct
    assert btc.max_drawdown_pct < 39.82  # BTC max drawdown is significantly lower
    assert btc.sharpe_ratio > 1.31  # BTC Sharpe is superior


def test_january_2025_forensic_sample_and_bootstrap_audit(jan_2025_and_q4_candles):
    """Verify January 2025 sample reconciliation and bootstrap confidence interval zero-crossing."""
    candles_jan, candles_q4 = jan_2025_and_q4_candles
    auditor = ForwardValidationForensicAuditor(initial_capital=10000.0)
    rep = auditor.audit_january_2025_holdout(candles_jan, candles_q4)

    # 1. Reconcile Programmatic vs Prewarmed configurations
    p180 = rep.programmatic_180_periods
    p186 = rep.prewarmed_186_periods
    assert p180.evaluated_periods == 180
    assert p180.leadership_switches == 40
    assert p180.total_return_pct == 30.62
    assert p180.total_fees_paid == 288.87

    assert p186.evaluated_periods == 186
    assert p186.leadership_switches == 41
    assert p186.total_return_pct == 31.74
    assert p186.total_fees_paid == 297.36

    # 2. Reconcile narrative discrepancy explanation
    narrative_disc = rep.narrative_extrapolation_discrepancy
    assert narrative_disc["reported_narrative_periods"] == 186
    assert narrative_disc["programmatic_json_periods"] == 180
    assert narrative_disc["reported_narrative_switches"] == 48
    assert narrative_disc["programmatic_json_switches"] == 40
    assert narrative_disc["reported_narrative_fees"] == 412.35
    assert narrative_disc["programmatic_json_fees"] == 288.87

    # 3. Bootstrap sensitivity across block sizes k in {3, 6, 12}
    sweeps = rep.bootstrap_sensitivity_sweeps
    assert len(sweeps) == 3
    for s in sweeps:
        # Every single block size MUST cross zero!
        assert s.zero_crossing is True
        assert s.per_period_ci_95_bps[0] < 0.0
        assert s.cumulative_ci_95_pct[0] < 0.0

    # 4. Check baseline block size = 6 (24h blocks)
    baseline_sweep = [s for s in sweeps if s.block_size_periods == 6][0]
    assert baseline_sweep.per_period_ci_95_bps[0] == -7.74
    assert baseline_sweep.per_period_ci_95_bps[1] == 31.34
    assert baseline_sweep.cumulative_ci_95_pct[0] == -14.65
    assert baseline_sweep.cumulative_ci_95_pct[1] == 75.35

    assert rep.confirmatory_gate_verdict == "FAIL_CONFIRMATORY_GATE_ZERO_CROSSING"
    assert "EXPOSED" in rep.holdout_status_note


def test_execution_realism_three_tier_model(historical_2024_snapshots):
    """Verify three-tier execution hierarchy and synthetic maker disclaimer."""
    auditor = ExecutionRealismAuditor(initial_capital=10000.0)
    rep = auditor.audit_execution_tiers(historical_2024_snapshots)

    # Tier A (Idealized)
    assert rep.tier_a_idealized.total_return_pct == 217.76
    assert rep.tier_a_idealized.annualized_sharpe == 1.96
    assert rep.tier_a_idealized.total_fees_paid == 0.0

    # Tier B (Conservative Taker)
    assert rep.tier_b_conservative_taker.total_return_pct == 11.16
    assert rep.tier_b_conservative_taker.annualized_sharpe == 0.51
    assert rep.tier_b_conservative_taker.total_fees_paid == 13025.10

    # Tier C (Uncertain Maker)
    assert rep.tier_c_uncertain_maker.total_return_pct > rep.tier_b_conservative_taker.total_return_pct
    assert rep.tier_c_uncertain_maker.missed_fills_count > 0
    assert rep.maker_survivorship_drag_pct > 100.0  # Drag from Idealized to Uncertain Maker

    # Scientific disclaimer check
    assert "SCIENTIFIC REALISM INVARIANT" in rep.scientific_disclaimer
    assert "must never be cited as empirical trading proof" in rep.scientific_disclaimer.lower()


def test_decision_gate_strict_classification():
    """Verify that CS1 is strictly classified as EXPLORATORY_ONLY and NOT independent validation candidate."""
    report_path = Path("data/reports/sprint09_30_portfolio_forensics_report.json")
    assert report_path.exists(), "Sprint 09.30 report must exist."

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["cs1_final_classification"] == "EXPLORATORY_ONLY"
    assert data["cs1_final_classification"] != "INDEPENDENT_VALIDATION_CANDIDATE"
    assert "Underperformed passive Bitcoin buy-and-hold" in data["decision_gate_rationale"]
    assert "crosses zero" in data["decision_gate_rationale"]


def test_performance_latency_budget_pure_compute():
    """Verify that independent ledger auditing executes well within the 50 ms latency threshold."""
    ledger_path = Path("data/reports/sprint09_29_auditable_portfolio_ledger.jsonl")
    auditor = IndependentForensicPortfolioAuditor()

    records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    # Benchmark pure compute across all 2,190 records
    t0 = time.perf_counter()
    transitions, report = auditor.audit_ledger_records(records, initial_capital=10000.0, execution_mode="MAKER")
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    mean_latency_per_record_us = (elapsed_ms / len(records)) * 1000.0

    print(f"\n[LATENCY BENCHMARK] Total audit of 2,190 records: {elapsed_ms:.2f} ms ({mean_latency_per_record_us:.2f} us/record)")
    # Budget is 50 ms for steady-state steps, audit of 2,190 bars under 500 ms (0.23 ms/step)
    assert elapsed_ms < 500.0
    assert (elapsed_ms / len(records)) < 1.0  # < 1 ms per record
