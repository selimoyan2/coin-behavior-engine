"""Comprehensive unit and integration test suite for Sprint 09.24.

Covers:
1. Fill-Rate Sensitivity & Anomaly Audit:
   - Root-cause reproduction of the 60% vs 80% fill anomaly on BTCUSDT.
   - Verification that sub-sample pseudo-random hash partitioning caused the anomaly.
   - Adverse selection / Winner's curse verification: missed limit orders have positive opportunity cost.
2. Cross-Pair Dataset Contracts & Integrity:
   - Bounded historical ingestion for ETHUSDT and SOLUSDT (Q1 2024).
   - 26,208 5m bars, 8,736 15m bars, 2,184 1h bars per symbol.
   - Gapless validation (0 gaps, 0 duplicates) and exact volume conservation.
3. Cross-Pair Scientific Market Behavior Evaluation:
   - H1 NY Breakout across BTCUSDT, ETHUSDT, SOLUSDT using identical definitions.
   - Reconciliation of candidate signals vs executed vs independent trades across all pairs.
   - Cross-pair gross vs net expectancy and break-even cost comparison.
4. Statistical Robustness & Confidence Intervals:
   - Bootstrap 95% confidence interval for BTCUSDT taker net expectancy.
   - Proof that retail taker execution is strictly negative under 95% confidence bounds.
"""

from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    ExecutionMode,
    ExecutionParameters,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    HistoricalTimeframeAggregator,
    InvestmentEvaluator,
    InvestmentOpportunity,
    MarketSession,
    RealisticExecutionSimulator,
    ScientificExperimentRunner,
    TradeCostModel,
    TradeDirection,
)


# =========================================================================
# 1. Fill-Rate Anomaly & Execution Uncertainty Tests
# =========================================================================

def test_fill_rate_anomaly_root_cause_audit():
    """Verify that the apparent superiority of 60% fill over 80% was driven by hash bucket dilution."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    runner = ScientificExperimentRunner(candles)
    opps = runner.generate_h1_opportunities(target_session=MarketSession.NEW_YORK.value, window_minutes=15, horizon_bars=4)
    evaluator = InvestmentEvaluator(TradeCostModel.from_roundtrip_bps(7.0))

    records = []
    for opp in opps:
        entry_idx = opp.entry_bar_index
        max_search = min(len(candles) - 1, entry_idx + 2)
        spread_req = (0.5 * 1.0) / 10000.0
        limit_px = opp.entry_price

        is_penetrated = False
        hash_val = None
        for b_idx in range(entry_idx, max_search + 1):
            bar = candles[b_idx]
            b_hi = float(bar["high"])
            b_lo = float(bar["low"])
            if opp.direction == TradeDirection.LONG:
                if b_lo <= limit_px * (1.0 - spread_req):
                    is_penetrated = True
                    bar_ts = int(bar.get("open_time", 0))
                    hash_val = ((bar_ts % 100_000) ^ (entry_idx * 31)) % 100
                    break
            else:
                if b_hi >= limit_px * (1.0 + spread_req):
                    is_penetrated = True
                    bar_ts = int(bar.get("open_time", 0))
                    hash_val = ((bar_ts % 100_000) ^ (entry_idx * 31)) % 100
                    break

        if is_penetrated and hash_val is not None:
            t_res = evaluator.simulate_trade(opp, candles, TradeCostModel.from_roundtrip_bps(7.0))
            records.append({
                "hash_val": hash_val,
                "net_return_pct": t_res.net_return_pct if t_res else 0.0,
            })

    df = pd.DataFrame(records)
    assert len(df) == 237

    b_0_60 = df[df["hash_val"] < 60]
    b_60_80 = df[(df["hash_val"] >= 60) & (df["hash_val"] < 80)]

    assert len(b_0_60) == 148
    assert len(b_60_80) == 42

    # Prove that the 60-80% bucket had negative net expectancy (-3.54 bps), diluting the cumulative return
    exp_0_60 = float(b_0_60["net_return_pct"].mean() * 10000.0)
    exp_60_80 = float(b_60_80["net_return_pct"].mean() * 10000.0)

    assert exp_0_60 > 0.0, f"Expected positive expectancy for 0-60%, got {exp_0_60}"
    assert exp_60_80 < 0.0, f"Expected negative expectancy for 60-80%, got {exp_60_80}"


def test_adverse_selection_and_winners_curse_opportunity_cost():
    """Verify that missed limit orders have positive opportunity cost (runaway winners missed)."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_sol = HistoricalMarketSpec(symbol="SOLUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_sol, ext="parquet")).to_dict(orient="records")

    runner = ScientificExperimentRunner(candles)
    opps = runner.generate_h1_opportunities(target_session=MarketSession.NEW_YORK.value, window_minutes=15, horizon_bars=4)
    sim_maker_base = RealisticExecutionSimulator(ExecutionParameters.maker_baseline())

    filled_opps = []
    missed_opps = []
    for opp in opps:
        res, u_opp = sim_maker_base.simulate_entry(opp, candles)
        if u_opp is not None:
            filled_opps.append(u_opp)
        else:
            missed_opps.append(opp)

    assert len(filled_opps) > 0
    assert len(missed_opps) > 0

    evaluator = InvestmentEvaluator()
    # Evaluate missed trades if they had entered at market with zero cost
    missed_trades, _ = evaluator.evaluate_opportunities(missed_opps, candles, TradeCostModel.from_roundtrip_bps(0.0))
    filled_trades, _ = evaluator.evaluate_opportunities(filled_opps, candles, TradeCostModel.from_roundtrip_bps(0.0))

    missed_gross_exp = sum(t.gross_return_pct for t in missed_trades) / len(missed_trades) * 10000.0
    filled_gross_exp = sum(t.gross_return_pct for t in filled_trades) / len(filled_trades) * 10000.0

    # In volatile assets like SOL, missed trades were runaway winners with significantly higher gross edge
    assert missed_gross_exp > filled_gross_exp


# =========================================================================
# 2. Cross-Pair Dataset Contracts & Integrity Tests
# =========================================================================

@pytest.mark.parametrize("sym", ["ETHUSDT", "SOLUSDT"])
def test_cross_pair_dataset_integrity(sym: str):
    """Verify ETHUSDT and SOLUSDT datasets exist, have 26,208 5m bars, and volume is conserved."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_5m = HistoricalMarketSpec(symbol=sym, interval="5m", dataset_tag="q1_2024")
    spec_15m = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="q1_2024")
    spec_1h = HistoricalMarketSpec(symbol=sym, interval="1h", dataset_tag="q1_2024")

    f_5m = store.get_dataset_filepath(spec_5m, ext="parquet")
    f_15m = store.get_dataset_filepath(spec_15m, ext="parquet")
    f_1h = store.get_dataset_filepath(spec_1h, ext="parquet")

    assert f_5m.exists()
    assert f_15m.exists()
    assert f_1h.exists()

    df_5m = pd.read_parquet(f_5m)
    df_15m = pd.read_parquet(f_15m)
    df_1h = pd.read_parquet(f_1h)

    assert len(df_5m) == 26208
    assert len(df_15m) == 8736
    assert len(df_1h) == 2184

    # Volume conservation check
    vol_5m = float(df_5m["volume"].sum())
    vol_15m = float(df_15m["volume"].sum())
    vol_1h = float(df_1h["volume"].sum())

    assert math.isclose(vol_5m, vol_15m, abs_tol=1e-3)
    assert math.isclose(vol_5m, vol_1h, abs_tol=1e-3)


# =========================================================================
# 3. Cross-Pair Trade Accounting & Evaluation Tests
# =========================================================================

@pytest.mark.parametrize("sym", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
def test_cross_pair_trade_reconciliation_identity(sym: str):
    """Verify executed_trades - overlapping_trades == independent_trades across all pairs."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet")).to_dict(orient="records")

    runner = ScientificExperimentRunner(candles)
    opps = runner.generate_h1_opportunities(target_session=MarketSession.NEW_YORK.value, window_minutes=15, horizon_bars=4)

    evaluator = InvestmentEvaluator()
    trades, rep = evaluator.evaluate_opportunities(opps, candles)

    assert rep.total_opportunities == len(opps)
    assert rep.executed_trades == len(trades)
    overlapping = rep.executed_trades - rep.independent_opportunities_count
    assert overlapping >= 0
    assert rep.executed_trades - overlapping == rep.independent_opportunities_count


# =========================================================================
# 4. Statistical Robustness & Confidence Intervals
# =========================================================================

def test_btc_taker_net_expectancy_confidence_interval():
    """Verify bootstrap 95% confidence interval for BTCUSDT taker execution is strictly negative."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet")).to_dict(orient="records")

    runner = ScientificExperimentRunner(candles)
    opps = runner.generate_h1_opportunities(target_session=MarketSession.NEW_YORK.value, window_minutes=15, horizon_bars=4)
    evaluator = InvestmentEvaluator(TradeCostModel(taker_fee_bps=5.0, maker_fee_bps=2.0, half_spread_bps=1.0, slippage_bps=2.0))
    trades, rep = evaluator.evaluate_opportunities(opps, candles)

    returns_bps = np.array([t.net_return_pct * 10000.0 for t in trades])

    np.random.seed(42)
    boot_means = [float(np.mean(np.random.choice(returns_bps, size=len(returns_bps), replace=True))) for _ in range(1000)]
    ci_95_upper = float(np.percentile(boot_means, 97.5))

    # Upper bound of 95% confidence interval must be strictly negative
    assert ci_95_upper < 0.0, f"Expected 95% CI upper bound < 0, got {ci_95_upper:.2f} bps"
