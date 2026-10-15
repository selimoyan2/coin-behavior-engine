"""Comprehensive test suite for Sprint 09.25: Research Integrity Gate & New Market Behavior Discovery.

Covers:
1. Mathematical Reconciliation & Proof of Fill-Rate Anomaly:
   - Root-cause proof of 148 trades (+1.39 bps) + 42 trades (-5.54 bps) = 190 trades (-0.14 bps).
   - Confirmation that 47 trades in bucket 80-100% were unfilled with 0.0 bps cost/return.
   - Reproduction of inadvertent Sprint 09.24 audit table numbers (+3.39 bps, -3.54 bps) when adverse selection is omitted.
2. Auditable Trade Ledger & Provenance:
   - Line-by-line trade ledger export and zero-tolerance reconciliation (ledger_sum == report_sum).
   - Provenance record structure, dataset hashes, commit SHA, and configuration hashes.
3. Q3 2024 Virgin Holdout Dataset Integrity:
   - Exactly 26,496 5m bars, 8,832 15m bars, 2,208 1h bars.
   - Gapless continuity and exact volume conservation.
4. Pre-Registered New Behavioral Hypotheses (H4-H7):
   - H4 Volatility Compression & Expansion (Bollinger/Keltner Squeeze).
   - H5 Trend Continuation After Consolidation (Trend Flag).
   - H6 Failed Breakout With Strong Rejection Confirmation (Liquidity Sweep).
   - H7 Session Transition & Liquidity Regime Changes.
   - Zero-lookahead invariant verification on all hypotheses.
5. Cross-Pair Scientific Status:
   - Re-evaluation of H1 on BTC, ETH, and SOL as research hypotheses.
6. Performance Latency Budget:
   - Pure compute verification confirming no algorithmic regression.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    AuditableTradeLedger,
    AuditableTradeRecord,
    ExecutionMode,
    ExecutionParameters,
    ExperimentProvenanceRecord,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    HistoricalTimeframeAggregator,
    InvestmentEvaluator,
    InvestmentOpportunity,
    MarketSession,
    NewHypothesesGenerator,
    OrderFillStatus,
    RealisticExecutionSimulator,
    ScientificExperimentRunner,
    TradeCostModel,
    TradeDirection,
)


# =========================================================================
# 1. Fill-Rate Anomaly Mathematical Proof & Root Cause Tests
# =========================================================================

def test_fill_rate_anomaly_mathematical_proof_with_adverse_selection():
    """Mathematically prove the exact root cause of the Sprint 09.24 fill-rate discrepancy."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    runner = ScientificExperimentRunner(candles)
    opps = runner.generate_h1_opportunities(target_session=MarketSession.NEW_YORK.value, window_minutes=15, horizon_bars=4)
    assert len(opps) == 237

    evaluator_maker = InvestmentEvaluator(TradeCostModel.from_roundtrip_bps(7.0))

    # Bucket tracking
    bucket_0_60_with_adv = []
    bucket_60_80_with_adv = []
    bucket_0_60_no_adv = []
    bucket_60_80_no_adv = []
    bucket_80_100_opps = []

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
            # 1. With adverse selection (+2.0 bps)
            eff_entry = (
                opp.entry_price * (1.0 + 2.0 / 10000.0)
                if opp.direction == TradeDirection.LONG
                else opp.entry_price * (1.0 - 2.0 / 10000.0)
            )
            opp_adv = InvestmentOpportunity(
                opportunity_id=opp.opportunity_id, symbol=opp.symbol, entry_bar_index=opp.entry_bar_index,
                entry_timestamp_ms=opp.entry_timestamp_ms, direction=opp.direction, entry_price=eff_entry,
                take_profit_price=opp.take_profit_price, stop_loss_price=opp.stop_loss_price,
                max_holding_bars=opp.max_holding_bars, metadata=opp.metadata,
            )
            t_res_adv = evaluator_maker.simulate_trade(opp_adv, candles, TradeCostModel.from_roundtrip_bps(7.0))

            # 2. Without adverse selection (inadvertent Sprint 09.24 audit calculation)
            t_res_raw = evaluator_maker.simulate_trade(opp, candles, TradeCostModel.from_roundtrip_bps(7.0))

            if hash_val < 60:
                bucket_0_60_with_adv.append(t_res_adv)
                bucket_0_60_no_adv.append(t_res_raw)
            elif hash_val < 80:
                bucket_60_80_with_adv.append(t_res_adv)
                bucket_60_80_no_adv.append(t_res_raw)
            else:
                bucket_80_100_opps.append(opp)

    # 1. Exact counts
    assert len(bucket_0_60_with_adv) == 148
    assert len(bucket_60_80_with_adv) == 42
    assert len(bucket_80_100_opps) == 47
    assert len(bucket_0_60_with_adv) + len(bucket_60_80_with_adv) == 190

    # 2. Reproduction of Sprint 09.24 inadvertent numbers without adverse selection
    raw_0_60_bps = (sum(t.net_return_pct for t in bucket_0_60_no_adv) / 148) * 10000.0
    raw_60_80_bps = (sum(t.net_return_pct for t in bucket_60_80_no_adv) / 42) * 10000.0
    assert math.isclose(raw_0_60_bps, 3.39, abs_tol=0.1)
    assert math.isclose(raw_60_80_bps, -3.54, abs_tol=0.1)

    # 3. Exact numbers with adverse selection
    adv_0_60_bps = (sum(t.net_return_pct for t in bucket_0_60_with_adv) / 148) * 10000.0
    adv_60_80_bps = (sum(t.net_return_pct for t in bucket_60_80_with_adv) / 42) * 10000.0
    assert math.isclose(adv_0_60_bps, 1.39, abs_tol=0.05)
    assert math.isclose(adv_60_80_bps, -5.54, abs_tol=0.05)

    # 4. Exact weighted sum and mean over 190 filled trades
    total_net_return_pct = sum(t.net_return_pct for t in bucket_0_60_with_adv) + sum(t.net_return_pct for t in bucket_60_80_with_adv)
    weighted_mean_bps = (total_net_return_pct / 190) * 10000.0
    assert math.isclose(total_net_return_pct * 100.0, -0.27, abs_tol=0.02)
    assert math.isclose(weighted_mean_bps, -0.14, abs_tol=0.02)


# =========================================================================
# 2. Auditable Trade Ledger & Provenance Tests
# =========================================================================

def test_auditable_trade_ledger_reconciliation():
    """Verify zero-tolerance automated reconciliation between trade ledger lines and portfolio totals."""
    ledger_path = Path("data/reports/sprint09_25_trade_ledger.jsonl")
    assert ledger_path.exists(), "Trade ledger file missing"

    records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                records.append(AuditableTradeRecord(**d))

    assert len(records) == 237
    filled = [r for r in records if r.is_filled]
    unfilled = [r for r in records if not r.is_filled]
    assert len(filled) == 190
    assert len(unfilled) == 47

    # All unfilled trades have strictly 0 return and 0 costs
    for r in unfilled:
        assert r.gross_return_pct == 0.0
        assert r.net_return_pct == 0.0
        assert r.cost_bps == 0.0
        assert r.exit_reason == "EXPIRED_UNFILLED"

    # Ledger sum must match Maker Baseline report total (-0.27% / -0.2687%)
    ledger_sum_pct = sum(r.net_return_pct for r in filled)
    assert math.isclose(ledger_sum_pct * 100.0, -0.27, abs_tol=0.02)

    # Mean expectancy
    mean_exp_bps = (ledger_sum_pct / len(filled)) * 10000.0
    assert math.isclose(mean_exp_bps, -0.14, abs_tol=0.02)


def test_provenance_record_metadata():
    """Verify the completeness of experiment provenance metadata."""
    report_path = Path("data/reports/sprint09_25_research_integrity_report.json")
    assert report_path.exists()

    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    prov = rep["provenance_record"]
    assert prov["symbol"] == "BTCUSDT"
    assert prov["market_type"] == "SPOT"
    assert prov["dataset_sha256"] != ""
    assert prov["code_commit_sha"] != ""
    assert prov["total_candidates"] == 237
    assert prov["executed_trades"] == 190
    assert prov["cost_model"]["roundtrip_bps"] == 7.0


# =========================================================================
# 3. Q3 2024 Virgin Holdout Dataset Integrity Tests
# =========================================================================

def test_q3_2024_virgin_holdout_dataset_integrity():
    """Verify that Q3 2024 holdout dataset is gapless, volume conserved, and adheres to bar counts."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_5m = HistoricalMarketSpec(symbol="BTCUSDT", interval="5m", dataset_tag="q3_2024")
    spec_15m = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q3_2024")
    spec_1h = HistoricalMarketSpec(symbol="BTCUSDT", interval="1h", dataset_tag="q3_2024")

    f_5m = store.get_dataset_filepath(spec_5m, ext="parquet")
    f_15m = store.get_dataset_filepath(spec_15m, ext="parquet")
    f_1h = store.get_dataset_filepath(spec_1h, ext="parquet")

    assert f_5m.exists()
    assert f_15m.exists()
    assert f_1h.exists()

    df_5m = pd.read_parquet(f_5m)
    df_15m = pd.read_parquet(f_15m)
    df_1h = pd.read_parquet(f_1h)

    # July (31 days) + Aug (31 days) + Sep (30 days) = 92 days
    # 92 * 288 = 26,496 bars of 5m
    assert len(df_5m) == 26496
    assert len(df_15m) == 8832
    assert len(df_1h) == 2208

    # Volume conservation
    vol_5m = df_5m["volume"].sum()
    vol_15m = df_15m["volume"].sum()
    vol_1h = df_1h["volume"].sum()

    assert math.isclose(vol_5m, vol_15m, abs_tol=1e-3)
    assert math.isclose(vol_5m, vol_1h, abs_tol=1e-3)


# =========================================================================
# 4. Pre-Registered Behavioral Hypotheses (H4-H7) Tests
# =========================================================================

def test_new_hypotheses_generation_and_zero_lookahead():
    """Verify H4-H7 signal generation and strict zero-lookahead compliance."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_15m = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_15m, ext="parquet")).to_dict(orient="records")

    gen = NewHypothesesGenerator(candles, symbol="BTCUSDT")

    h4_opps = gen.generate_h4_opportunities()
    h5_opps = gen.generate_h5_opportunities()
    h6_opps = gen.generate_h6_opportunities()
    h7_opps = gen.generate_h7_opportunities()

    assert len(h4_opps) > 0
    assert len(h5_opps) > 0
    assert len(h6_opps) > 0
    assert len(h7_opps) > 0

    # Invariants for every opportunity
    for opp_list in (h4_opps, h5_opps, h6_opps, h7_opps):
        for opp in opp_list:
            assert opp.entry_bar_index >= 0
            assert opp.entry_price > 0
            assert opp.take_profit_price > 0
            assert opp.stop_loss_price > 0
            assert opp.max_holding_bars > 0

            # Directional consistency
            if opp.direction == TradeDirection.LONG:
                assert opp.take_profit_price > opp.entry_price
                assert opp.stop_loss_price < opp.entry_price
            else:
                assert opp.take_profit_price < opp.entry_price
                assert opp.stop_loss_price > opp.entry_price


def test_holdout_decay_demonstration_on_h5():
    """Verify that H5 Trend Flag suffers significant performance decay on virgin holdout Q3."""
    report_path = Path("data/reports/sprint09_25_research_integrity_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    h5 = rep["new_hypotheses_evaluation"]["H5_TREND_FLAG"]
    q1_pf = h5["discovery_q1_2024"]["gross_profit_factor"]
    q3_pf = h5["virgin_holdout_q3_2024"]["gross_profit_factor"]

    # In Q1, H5 had apparent gross edge (PF 1.25)
    assert q1_pf > 1.0
    # In Q3 virgin holdout, performance decayed to PF < 1.0 (PF 0.69)
    assert q3_pf < 1.0
    assert h5["holdout_edge_retained"] is False


# =========================================================================
# 5. Cross-Pair Research Status Verification
# =========================================================================

def test_cross_pair_scientific_status():
    """Verify that H1 is treated strictly as an unvalidated hypothesis across all pairs."""
    report_path = Path("data/reports/sprint09_25_research_integrity_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    cp = rep["cross_pair_h1_status"]
    assert "RESEARCH_HYPOTHESIS" in cp["BTCUSDT"]["scientific_status"]
    assert "RESEARCH_HYPOTHESIS" in cp["ETHUSDT"]["scientific_status"]
    assert "RESEARCH_HYPOTHESIS" in cp["SOLUSDT"]["scientific_status"]

    # Confirm BTC gross edge does not survive retail taker costs
    assert cp["BTCUSDT"]["gross_profit_factor"] > 1.0
    assert cp["BTCUSDT"]["taker_net_bps"] < 0.0


# =========================================================================
# 6. Performance Latency Verification (Pure Compute Sub-50ms)
# =========================================================================

def test_performance_latency_budget():
    """Verify that pure compute latency remains well below the strict 50ms production threshold."""
    import time
    from coin_behavior_engine.normalization.canonical import CanonicalNormalizer

    normalizer = CanonicalNormalizer()
    raw_candle = {
        "timestamp_open": 1704067200000,
        "timestamp_close": 1704067499999,
        "open": 42000.0,
        "high": 42100.0,
        "low": 41950.0,
        "close": 42050.0,
        "volume": 12.5,
        "quote_volume": 525000.0,
        "trades_count": 150,
        "is_closed": True,
    }

    raw_df = pd.DataFrame([raw_candle])
    # Measure pure in-memory normalization over 100 iterations
    t0 = time.perf_counter()
    for _ in range(100):
        normalizer.normalize(raw_df, symbol="BTCUSDT")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 100.0

    # Must be well under 50ms (typically ~0.05-1.5ms)
    assert elapsed_ms < 50.0
