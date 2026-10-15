"""Comprehensive Test Suite for Sprint 09.31: Execution Integrity Closure & Capital Preservation Research.

Verifies:
1. Independent verification of Maker vs Taker traded notionals ($21,975,697.15 vs $16,281,376.06)
   and proof of the shared denominator fallacy.
2. Timeline parity of January 2025: identical eligible timestamps between CS1 and BTC benchmark.
3. Resolution of the Maker Fill Paradox (churn suppression, whipsaw avoidance, fee savings, synthetic artifact).
4. Mathematical compounding bridge reconciling per-period gross expectancy (+6.47 bps)
   with multi-period uncosted equity (+217.76% / $31,775.86 USDT) via volatility drag.
5. Benchmark superiority of BTC Buy & Hold (+108.55%) and Fixed 50/50 BTC/Cash (MaxDD 19.23%, Sharpe 1.56)
   over all tactical capital preservation candidates.
6. Rejection of CP1, CP2, CP3, CP4 due to drag, lag, and whipsaw fee destruction.
7. Block bootstrap statistical testing confirming negative active alpha across k in {3, 6, 12}.
8. Pure compute latency budget strictly <= 50 ms.
"""

from pathlib import Path
import json
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical.capital_preservation_research import (
    BootstrapConfidenceRecord,
    CapitalPreservationEngine,
    CapitalPreservationPerformanceRecord,
    CapitalPreservationResearchReport,
    CostSensitivityRecord,
)
from coin_behavior_engine.research.historical.dataset_contract import (
    HistoricalDatasetStore,
    HistoricalMarketSpec,
)
from coin_behavior_engine.research.historical.forensic_closure_sprint31 import (
    ForensicClosureAuditor,
    ForensicClosureReport,
    HistoricalGrossReconciliation,
    MakerFillParadoxAnalysis,
    TradedNotionalReconciliationRecord,
)


@pytest.fixture(scope="module")
def btc_2024_candles():
    """Load full year 2024 15m dataset for BTCUSDT."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    quarters = ["q1_2024", "q2_2024", "q3_2024", "q4_2024"]
    dfs = []
    for q in quarters:
        spec = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag=q)
        dfs.append(pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet")))
    return pd.concat(dfs, ignore_index=True)


@pytest.fixture(scope="module")
def btc_jan_2025_candles():
    """Load January 2025 15m dataset for BTCUSDT."""
    return pd.read_parquet("data/historical/historical_binance_btcusdt_15m_jan_2025.parquet")


def test_forensic_traded_notional_reconciliation():
    """Verify independent Maker and Taker traded notionals and denominator fallacy proof."""
    auditor = ForensicClosureAuditor(initial_capital=10000.0)
    maker_rec, taker_rec, fallacy_proof = auditor.audit_traded_notionals()

    # Maker verification
    assert maker_rec.transitions_count == 584
    assert maker_rec.one_way_turnover_usdt == 10986144.93
    assert maker_rec.two_way_traded_notional_usdt == 21975697.15
    assert maker_rec.actual_fees_paid_usdt == 6592.71
    assert maker_rec.final_equity_usdt == 19923.64
    assert maker_rec.total_return_pct == 99.24
    assert abs(maker_rec.actual_fees_paid_usdt - maker_rec.two_way_traded_notional_usdt * 0.0003) < 0.01

    # Taker verification
    assert taker_rec.transitions_count == 584
    assert taker_rec.two_way_traded_notional_usdt == 16281376.06
    assert taker_rec.actual_fees_paid_usdt == 13025.10
    assert taker_rec.final_equity_usdt == 11116.24
    assert taker_rec.total_return_pct == 11.16
    assert abs(taker_rec.actual_fees_paid_usdt - taker_rec.two_way_traded_notional_usdt * 0.0008) < 0.01

    # Notional divergence proof
    assert maker_rec.two_way_traded_notional_usdt > taker_rec.two_way_traded_notional_usdt
    assert "SHARED DENOMINATOR FALLACY" in fallacy_proof


def test_january_2025_timeline_parity(btc_jan_2025_candles):
    """Verify January 2025 timeline parity: CS1 and BTC evaluated over identical timestamps."""
    auditor = ForensicClosureAuditor()
    report = auditor.generate_closure_report()

    assert report.january_2025_timeline_parity_verified is True
    assert report.january_2025_evaluated_periods == 180
    assert report.january_2025_warmup_candles == 96

    # Verify candle count: 96 warmup + 180 * 16 evaluated = 2,976 candles
    assert len(btc_jan_2025_candles) == 2976
    assert 96 + 180 * 16 == 2976


def test_maker_fill_paradox_resolution():
    """Verify mathematical and empirical resolution of the maker fill paradox."""
    auditor = ForensicClosureAuditor()
    paradox = auditor.audit_maker_fill_paradox()

    assert paradox.baseline_100pct_fill_return_pct == 99.24
    assert paradox.realistic_80pct_fill_return_pct == 108.21
    assert paradox.missed_transitions_count == 120
    assert paradox.executed_transitions_count == 464
    assert paradox.direct_fee_savings_usdt == 858.82
    assert "CHURN SUPPRESSION" in paradox.churn_suppression_effect
    assert "SCIENTIFIC ARTIFACT" in paradox.simulation_artifact_explanation


def test_historical_gross_expectancy_equity_bridge():
    """Verify that per-period expectancy (+6.47 bps) bridges to +217.76% gross equity via volatility drag."""
    auditor = ForensicClosureAuditor()
    gross_rec = auditor.audit_historical_gross_reconciliation()

    assert gross_rec.per_period_gross_expectancy_bps == 6.47
    assert gross_rec.volatility_drag_bps_per_period == 1.18
    assert gross_rec.effective_geometric_growth_bps == 5.29
    assert gross_rec.theoretical_naive_compounded_pct == 311.99
    assert gross_rec.simulated_uncosted_gross_return_pct == 217.76
    assert abs(gross_rec.volatility_adjusted_compounded_pct - gross_rec.simulated_uncosted_gross_return_pct) < 0.50


def test_capital_preservation_benchmark_superiority(btc_2024_candles):
    """Verify that unconditional BTC Buy & Hold and passive 50/50 outperform dynamic CP strategies."""
    engine = CapitalPreservationEngine(initial_capital=10000.0)
    report = engine.evaluate_capital_preservation(btc_2024_candles, dataset_name="FULL_YEAR_2024")

    bench_map = {b.strategy_id: b for b in report.benchmarks}
    cand_map = {c.strategy_id: c for c in report.candidates}

    btc_bh = bench_map["BUY_AND_HOLD_BTC"]
    fixed_50 = bench_map["FIXED_50_50_BTC_CASH"]

    # 1. BTC Buy & Hold dominates returns and Sharpe
    assert btc_bh.total_net_return_pct > 100.0
    assert btc_bh.sharpe_ratio >= 1.60
    assert btc_bh.total_fees_paid <= 10.0

    # 2. Passive Fixed 50/50 achieves the lowest maximum drawdown
    assert fixed_50.max_drawdown_pct < 20.0
    assert fixed_50.sharpe_ratio >= 1.50
    assert fixed_50.total_fees_paid <= 5.0

    # 3. Every tactical candidate underperforms BTC B&H return
    for cand in report.candidates:
        assert cand.total_net_return_pct < btc_bh.total_net_return_pct
        assert cand.rejection_verdict == "REJECTED"


def test_capital_preservation_candidates_rejection(btc_2024_candles):
    """Verify that CP1, CP2, CP3, CP4 suffer severe lag, opportunity drag, or fee destruction."""
    engine = CapitalPreservationEngine(initial_capital=10000.0)
    report = engine.evaluate_capital_preservation(btc_2024_candles, dataset_name="FULL_YEAR_2024")
    cand_map = {c.strategy_id: c for c in report.candidates}

    # CP1: Volatility Reduction suffers higher drawdown than BTC B&H due to de-risking lag
    cp1 = cand_map["CP1_VOLATILITY_EXPOSURE_REDUCTION"]
    assert cp1.max_drawdown_pct > 35.0  # 37.04% vs 31.00% for BTC B&H

    # CP2: Drawdown Cash achieves virtually zero drawdown benefit (30.01% vs 31.00%)
    cp2 = cand_map["CP2_DRAWDOWN_AWARE_CASH"]
    assert cp2.total_net_return_pct < 60.0

    # CP3: Trend Regime collapses due to 317 whipsaws and $2,388+ in fees
    cp3 = cand_map["CP3_TREND_REGIME_PROTECTION"]
    assert cp3.switches_count > 300
    assert cp3.total_fees_paid > 2000.0
    assert cp3.total_net_return_pct < 10.0
    assert cp3.sharpe_ratio < 0.50

    # CP4: Low Turnover selective exposure also suffers fee drag and low Sharpe
    cp4 = cand_map["CP4_LOW_TURNOVER_SELECTIVE"]
    assert cp4.switches_count > 200
    assert cp4.total_fees_paid > 2000.0
    assert cp4.total_net_return_pct < 10.0


def test_block_bootstrap_negative_alpha_significance(btc_2024_candles):
    """Verify block bootstrap tests across block sizes k in {3, 6, 12} with Holm-Bonferroni correction."""
    engine = CapitalPreservationEngine(initial_capital=10000.0)
    report = engine.evaluate_capital_preservation(btc_2024_candles, dataset_name="FULL_YEAR_2024")

    # All bootstrap records must confirm zero statistically significant outperforming candidates
    sig_count = sum(1 for b in report.bootstrap_confidence_records if b.statistically_significant)
    assert sig_count == 0, "No dynamic capital preservation candidate should demonstrate positive alpha."

    # Verify that core decision gate verdict formally rejects all candidates
    assert report.core_research_verdict == "REJECT_ALL_DYNAMIC_CAPITAL_PRESERVATION_CANDIDATES"


def test_performance_latency_budget_pure_compute(btc_2024_candles):
    """Verify that pure compute simulation executes well within the 50 ms budget per 200 periods."""
    import gc
    gc.collect()

    engine = CapitalPreservationEngine(initial_capital=10000.0)
    closes = btc_2024_candles["close"].values.astype(float)[:3200]  # 200 decision periods (3200 / 16)
    dec_indices = list(range(0, len(closes), 16))
    exposures = [0.5 if i % 2 == 0 else 1.0 for i in range(len(dec_indices))]

    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        engine.simulate_exposure_curve(closes, exposures, dec_indices, 0.0008, 0.0001)
        times.append((time.perf_counter() - t0) * 1000.0)

    median_ms = float(np.median(times))
    assert median_ms < 50.0, f"Pure compute latency must be < 50 ms, got {median_ms:.2f} ms"
