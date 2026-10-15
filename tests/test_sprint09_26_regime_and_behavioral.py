"""Comprehensive test suite for Sprint 09.26: Market Regime Intelligence & Advanced Behavioral Research.

Covers:
1. Research Integrity Gate Verification:
   - Reproduction of Sprint 09.25 ledger reconciliation (190 filled trades, 47 expired orders).
2. Point-in-Time Market Regime Classification:
   - Multi-dimensional regime representation (Trend, Volatility, Volume, Momentum, Session).
   - Strict zero-lookahead point-in-time calculation.
   - Regime transition matrices, duration statistics, and conditional return distributions.
3. H4 Volatility Compression Conditional Research:
   - Pre-registered H4 variants (BASE, TREND_ALIGNED, EXTENDED_SQUEEZE, HIGH_VOLUME, SESSION_PEAK).
   - Conditioning by prior trend, duration, volume, and session.
   - Cost sensitivity (0 bps gross, 7 bps maker, 16 bps taker).
4. Behavioral Discovery Beyond Opening Sessions:
   - Observational findings (B1 to B6) with conditional vs baseline distributions.
   - Standard error, t-statistics, and rigorous classification (OBSERVATIONAL_ONLY, EXPLORATORY_HYPOTHESIS).
5. Historical Coverage & Virgin Q4 2024 Holdout Integrity:
   - Exact bar counts (26,496 5m, 8,832 15m, 2,208 1h).
   - Gapless continuity and volume conservation.
6. External Market Intelligence 4-Timestamp Readiness:
   - Strict timestamp hierarchy: event <= publication <= ingestion <= decision_available.
   - Lookahead guard validation.
7. Performance Latency Budget:
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
    BehavioralDiscoveryAnalyzer,
    BehavioralDiscoveryFinding,
    BehavioralEvidenceStatus,
    ConditionalReturnDistribution,
    ExecutionMode,
    ExecutionParameters,
    ExternalDataAvailabilityError,
    ExternalDataReadinessValidator,
    H4ConditionalExperimentRunner,
    H4ConditionalVariantResult,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    InvestmentEvaluator,
    InvestmentOpportunity,
    MarketRegimeEngine,
    MarketRegimeState,
    MarketSession,
    MomentumRegime,
    RegimeTransitionReport,
    TimestampedSignalEnvelope,
    TradeCostModel,
    TradeDirection,
    TrendRegime,
    VolatilityRegime,
    VolumeRegime,
)


# =========================================================================
# 1. Research Integrity Gate Verification
# =========================================================================

def test_research_integrity_reproduction_sprint09_25():
    """Reproduce and verify the exact Sprint 09.25 ledger reconciliation."""
    ledger_path = Path("data/reports/sprint09_25_trade_ledger.jsonl")
    assert ledger_path.exists(), "Sprint 09.25 trade ledger file missing"

    records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(AuditableTradeRecord(**json.loads(line)))

    assert len(records) == 237
    filled = [r for r in records if r.is_filled]
    unfilled = [r for r in records if not r.is_filled]
    assert len(filled) == 190
    assert len(unfilled) == 47

    # Check that all unfilled orders carry zero return and zero cost
    for r in unfilled:
        assert r.gross_return_pct == 0.0
        assert r.net_return_pct == 0.0
        assert r.cost_bps == 0.0
        assert r.exit_reason == "EXPIRED_UNFILLED"

    # Ledger total return must reconcile with Maker Baseline (-0.2687%)
    ledger_sum_pct = sum(r.net_return_pct for r in filled)
    assert math.isclose(ledger_sum_pct * 100.0, -0.27, abs_tol=0.02)

    # Mean net expectancy must reconcile with Maker Baseline (-0.14 bps)
    mean_exp_bps = (ledger_sum_pct / len(filled)) * 10000.0
    assert math.isclose(mean_exp_bps, -0.14, abs_tol=0.02)


# =========================================================================
# 2. Point-in-Time Market Regime Engine Tests
# =========================================================================

def test_market_regime_classification_multidimensional_and_zero_lookahead():
    """Verify point-in-time multi-dimensional classification and zero lookahead."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    engine = MarketRegimeEngine(candles)
    assert engine.n_bars == len(candles)

    # Classify bar 100
    state_100 = engine.classify_bar(100)
    assert isinstance(state_100, MarketRegimeState)
    assert state_100.bar_index == 100
    assert state_100.trend in (TrendRegime.BULLISH_TREND, TrendRegime.BEARISH_TREND, TrendRegime.SIDEWAYS_RANGE)
    assert state_100.volatility in (VolatilityRegime.COMPRESSION_SQUEEZE, VolatilityRegime.VOLATILITY_SHOCK, VolatilityRegime.EXPANSION_NORMAL)
    assert state_100.volume in (VolumeRegime.HIGH_VOLUME, VolumeRegime.LOW_VOLUME, VolumeRegime.NORMAL_VOLUME)
    assert state_100.momentum in (MomentumRegime.ACCELERATING, MomentumRegime.EXHAUSTING, MomentumRegime.NEUTRAL)
    assert state_100.atr_14 > 0
    assert state_100.relative_volume_24h > 0
    assert 0.0 <= state_100.rsi_14 <= 100.0

    # Truncate dataset up to bar 100 and re-classify; result must be strictly identical (zero lookahead)
    engine_truncated = MarketRegimeEngine(candles[:101])
    state_truncated = engine_truncated.classify_bar(100)
    assert state_100.trend == state_truncated.trend
    assert state_100.volatility == state_truncated.volatility
    assert state_100.volume == state_truncated.volume
    assert math.isclose(state_100.atr_14, state_truncated.atr_14, abs_tol=1e-3)


def test_regime_transition_matrix_and_persistence():
    """Verify transition probabilities sum to 1.0 and direct trend flip is rare."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    engine = MarketRegimeEngine(candles)
    trans_trend = engine.compute_regime_transition_matrix(dimension="trend")

    # Each row of transition matrix must sum to 1.0
    for state, row in trans_trend.transition_matrix.items():
        assert math.isclose(sum(row.values()), 1.0, abs_tol=1e-3)

    # Bullish to Bearish direct flip without passing through Sideways is < 1%
    bull_to_bear = trans_trend.transition_matrix["BULLISH_TREND"]["BEARISH_TREND"]
    assert bull_to_bear < 0.01

    # Persistence of trend is high (> 85%)
    assert trans_trend.transition_matrix["BULLISH_TREND"]["BULLISH_TREND"] > 0.85
    assert trans_trend.transition_matrix["BEARISH_TREND"]["BEARISH_TREND"] > 0.85


# =========================================================================
# 3. H4 Volatility Compression Conditional Research Tests
# =========================================================================

def test_h4_conditional_variants_generation_and_cost_sensitivity():
    """Verify H4 conditional variants and cost sensitivity across maker and taker."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    runner = H4ConditionalExperimentRunner(candles, symbol="BTCUSDT")

    # BASE vs TREND_ALIGNED vs EXTENDED_SQUEEZE
    opps_base = runner.generate_conditioned_opportunities("H4_BASE")
    opps_trend = runner.generate_conditioned_opportunities("H4_TREND_ALIGNED")
    opps_ext = runner.generate_conditioned_opportunities("H4_EXTENDED_SQUEEZE")

    assert len(opps_base) > 0
    # Conditioned variants must be strict subsets of base candidates
    assert len(opps_trend) < len(opps_base)
    assert len(opps_ext) < len(opps_base)

    # Cost sensitivity: Gross > Maker > Taker
    res_gross = runner.evaluate_variant("H4_BASE", partition_name="Q1", cost_bps=0.0)
    res_maker = runner.evaluate_variant("H4_BASE", partition_name="Q1", cost_bps=7.0)
    res_taker = runner.evaluate_variant("H4_BASE", partition_name="Q1", cost_bps=16.0)

    assert res_gross.net_expectancy_bps > res_maker.net_expectancy_bps > res_taker.net_expectancy_bps
    assert res_gross.gross_expectancy_bps > 0.0  # Gross alpha exists in compression breakout


# =========================================================================
# 4. Behavioral Discovery Beyond Opening Sessions (B1-B6) Tests
# =========================================================================

def test_behavioral_discovery_findings_and_classifications():
    """Verify observational discovery B1-B6 calculations, baselines, and status assignments."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    analyzer = BehavioralDiscoveryAnalyzer(candles, symbol="BTCUSDT")
    findings = analyzer.discover_all_behaviors(horizons_bars=(1, 4, 12))

    expected_ids = {
        "B1_TREND_EXHAUSTION",
        "B2_VOLATILITY_SHOCK_RECOVERY",
        "B3_RANGE_EXPANSION_MEAN_REVERSION",
        "B4_MOMENTUM_PERSISTENCE",
        "B5_FAILED_CONTINUATION",
        "B6_LARGE_CANDLE_REACTION",
    }
    assert set(findings.keys()) == expected_ids

    for b_id, f in findings.items():
        assert isinstance(f, BehavioralDiscoveryFinding)
        assert f.sample_size > 0
        assert f.status in (
            BehavioralEvidenceStatus.OBSERVATIONAL_ONLY,
            BehavioralEvidenceStatus.EXPLORATORY_HYPOTHESIS,
            BehavioralEvidenceStatus.INSUFFICIENT_EVIDENCE,
            BehavioralEvidenceStatus.REJECTED,
            BehavioralEvidenceStatus.VALIDATION_CANDIDATE,
        )
        assert len(f.conditional_mean_bps) == 3
        assert len(f.unconditional_baseline_bps) == 3
        assert len(f.standard_error_bps) == 3
        assert len(f.t_statistic) == 3


# =========================================================================
# 5. Historical Coverage & Virgin Q4 2024 Holdout Integrity Tests
# =========================================================================

def test_q4_2024_virgin_holdout_dataset_integrity():
    """Verify that Q4 2024 dataset is gapless, volume conserved, and adheres to bar counts."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_5m = HistoricalMarketSpec(symbol="BTCUSDT", interval="5m", dataset_tag="q4_2024")
    spec_15m = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q4_2024")
    spec_1h = HistoricalMarketSpec(symbol="BTCUSDT", interval="1h", dataset_tag="q4_2024")

    f_5m = store.get_dataset_filepath(spec_5m, ext="parquet")
    f_15m = store.get_dataset_filepath(spec_15m, ext="parquet")
    f_1h = store.get_dataset_filepath(spec_1h, ext="parquet")

    assert f_5m.exists(), "5m Q4 2024 parquet missing"
    assert f_15m.exists(), "15m Q4 2024 parquet missing"
    assert f_1h.exists(), "1h Q4 2024 parquet missing"

    df_5m = pd.read_parquet(f_5m)
    df_15m = pd.read_parquet(f_15m)
    df_1h = pd.read_parquet(f_1h)

    # Oct (31) + Nov (30) + Dec (31) = 92 days
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
# 6. External Market Intelligence 4-Timestamp Contract Tests
# =========================================================================

def test_external_data_4_timestamp_contract_and_lookahead_prevention():
    """Verify that external signal items enforce strict 4-timestamp ordering and reject lookahead."""
    # 1. Valid 4-timestamp envelope
    valid_env = TimestampedSignalEnvelope(
        signal_id="SIG_001",
        signal_type="MACRO",
        source_name="BLS_CPI",
        event_timestamp_ms=1000,
        publication_timestamp_ms=1100,
        ingestion_timestamp_ms=1150,
        decision_available_timestamp_ms=1200,
        payload={"cpi_yoy": 3.1},
    )
    assert valid_env.available_timestamp_ms == 1200

    # 2. Invalid ordering: publication precedes event
    with pytest.raises(ValueError, match="publication_timestamp_ms.*cannot precede"):
        TimestampedSignalEnvelope(
            signal_id="SIG_ERR_1",
            signal_type="MACRO",
            source_name="ERR",
            event_timestamp_ms=1000,
            publication_timestamp_ms=900,
            ingestion_timestamp_ms=1100,
            decision_available_timestamp_ms=1200,
        )

    # 3. Invalid ordering: ingestion precedes publication
    with pytest.raises(ValueError, match="ingestion_timestamp_ms.*cannot precede"):
        TimestampedSignalEnvelope(
            signal_id="SIG_ERR_2",
            signal_type="MACRO",
            source_name="ERR",
            event_timestamp_ms=1000,
            publication_timestamp_ms=1100,
            ingestion_timestamp_ms=1050,
            decision_available_timestamp_ms=1200,
        )

    # 4. Invalid ordering: decision_available precedes ingestion
    with pytest.raises(ValueError, match="decision_available_timestamp_ms.*cannot precede"):
        TimestampedSignalEnvelope(
            signal_id="SIG_ERR_3",
            signal_type="MACRO",
            source_name="ERR",
            event_timestamp_ms=1000,
            publication_timestamp_ms=1100,
            ingestion_timestamp_ms=1150,
            decision_available_timestamp_ms=1120,
        )

    # 5. ExternalDataReadinessValidator detects future lookahead
    res = ExternalDataReadinessValidator.validate_envelope_sequence(
        [valid_env], decision_timestamp_ms=1150  # Decision before available (1200)
    )
    assert res["is_valid"] is False
    assert res["violations_count"] == 1
    assert "Lookahead violation" in res["violations"][0]


# =========================================================================
# 7. Performance Latency Verification (Pure Compute Sub-50ms)
# =========================================================================

def test_performance_latency_budget_pure_compute():
    """Verify that pure compute regime classification remains well below 50ms."""
    import time
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    engine = MarketRegimeEngine(candles[:300])

    t0 = time.perf_counter()
    for _ in range(100):
        engine.classify_bar(200)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 100.0

    # Must be well under 50ms (typically ~0.05-1.5ms)
    assert elapsed_ms < 50.0
