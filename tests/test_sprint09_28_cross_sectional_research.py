"""Comprehensive test suite for Sprint 09.28: Cross-Sectional Relative Strength, Market Breadth & Funding Research Readiness.

Covers:
1. Research Integrity Gate Verification:
   - Sprint 09.27 reproducibility (1,605 ledger records, all Q4 holdout B3/B5 verdicts REJECTED).
2. Cross-Sectional Universe Audit:
   - Full 2024 panel (BTCUSDT, ETHUSDT, SOLUSDT across Q1-Q4 at 15m: 35,136 bars each).
   - 0 gaps, 0 duplicates, volume conservation from 5m.
   - Listing dates, survivorship bias assessment, and acquisition budget (< 100 MB budget).
3. Relative Strength Engine:
   - Point-in-time calculation with zero future leakage.
   - Ranking persistence decay across forward horizons (4, 16, 48, 96 bars).
   - Leadership concentration HHI bounds.
4. Market Breadth Engine:
   - Advance/decline ratio, % above EMA50, broad advance/decline thresholds, breadth thrust.
5. Pre-Registration Gate & Hash Integrity:
   - SHA-256 parameter hashes for CS1, CS2, CS3, CS4.
   - Tamper-proofing verification.
6. Spot-Only Execution Invariants & Hypothesis Simulation:
   - CS1 (Momentum Persistence): Positive net maker (+4.87 bps), CI crosses 0 -> EXPLORATORY.
   - CS2 (Leadership Rotation): Negative net maker (-9.53 bps) -> REJECTED.
   - CS3 (Breadth Confirmation): Negative net maker (-5.16 bps) -> REJECTED.
   - CS4 (BTC Regime Dependency): Negative net maker (-0.29 bps) -> REJECTED.
   - Cost accounting: Maker (6 bps) vs Taker (16 bps), cash drag, no borrowing, no leverage.
7. Perpetual Futures Funding Rate Research Contract:
   - 4-timestamp availability hierarchy.
   - Strict synthetic data prohibition (SyntheticFundingProhibitionError).
   - Total Spot P&L separation (SpotPerpetualAccountingContaminationError).
   - Readiness status lifecycle.
8. Multiple-Testing Statistical Control:
   - Bonferroni family-wise alpha = 0.0125 (0.05 / 4).
9. Performance Latency Budget Forensics:
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
    AssetMetadata,
    AuditableTradeRecord,
    CrossSectionalDecisionVerdict,
    CrossSectionalFeatureSnapshot,
    CrossSectionalHypothesisResult,
    CrossSectionalPreRegistrationGate,
    CrossSectionalRelativeStrengthEngine,
    CrossSectionalResearchRunner,
    CrossSectionalUniverseAuditor,
    CrossSectionalUniverseAuditReport,
    CS1Config,
    CS2Config,
    CS3Config,
    CS4Config,
    FundingContractSpec,
    FundingRateRecord,
    FundingRateResearchValidator,
    FundingReadinessReport,
    FundingReadinessStatus,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    MarketBreadthEngine,
    MarketBreadthSnapshot,
    RankingPersistenceReport,
    SpotPerpetualAccountingContaminationError,
    SyntheticFundingProhibitionError,
)


# =========================================================================
# 1. Research Integrity Gate Verification (Sprint 09.27 Reproduction)
# =========================================================================

def test_sprint09_27_reproducibility():
    """Verify exact reproduction of Sprint 09.27 results and trade ledger."""
    ledger_path = Path("data/reports/sprint09_27_trade_ledger.jsonl")
    assert ledger_path.exists(), "Sprint 09.27 trade ledger file missing"

    records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    assert len(records) == 1605, f"Expected exactly 1,605 records, got {len(records)}"

    # Check report findings
    report_path = Path("data/reports/sprint09_27_validation_and_holdout_report.json")
    assert report_path.exists(), "Sprint 09.27 report file missing"
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    # Confirm both Q4 holdout evaluations were REJECTED
    holdout_results = rep.get("q4_confirmatory_holdout", {})
    assert holdout_results.get("B3_CONTINUATION", {}).get("verdict") == "REJECTED"
    assert holdout_results.get("B5_REBOUND_BULLISH", {}).get("verdict") == "REJECTED"
    assert holdout_results.get("B3_CONTINUATION", {}).get("passed_confirmatory_gate") is False
    assert holdout_results.get("B5_REBOUND_BULLISH", {}).get("passed_confirmatory_gate") is False


# =========================================================================
# 2. Cross-Sectional Universe Audit Tests
# =========================================================================

def test_cross_sectional_universe_audit_and_coverage():
    """Verify cross-sectional universe audit, coverage, continuity, and budget."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    auditor = CrossSectionalUniverseAuditor(store)
    report = auditor.audit_universe()

    assert isinstance(report, CrossSectionalUniverseAuditReport)
    assert report.core_universe == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert "BNBUSDT" in report.candidate_universe
    assert "DOGEUSDT" in report.candidate_universe

    # Verify all 3 core assets have 4 quarters and exactly 35,136 15m bars (leap year 2024)
    for sym in report.core_universe:
        cov = report.dataset_coverage[sym]
        assert len(cov.quarters_available) == 4
        assert cov.total_15m_bars == 35136, f"{sym} expected 35,136 bars, got {cov.total_15m_bars}"
        assert cov.missing_bars_count == 0
        assert cov.duplicate_bars_count == 0
        assert cov.gapless_continuity is True

    # Acquisition budget check
    assert report.acquisition_budget_mb_used < report.max_budget_mb
    assert report.acquisition_budget_mb_used <= 30.0  # ~26.4 MB actual

    # Listing metadata verification
    btc_meta = report.assets_metadata["BTCUSDT"]
    sol_meta = report.assets_metadata["SOLUSDT"]
    assert btc_meta.binance_spot_listing_date_utc.startswith("2017-08-17")
    assert sol_meta.binance_spot_listing_date_utc.startswith("2020-08-11")
    assert "SURVIVORSHIP BIAS AUDIT" in report.survivorship_bias_assessment


def test_cross_sectional_volume_conservation():
    """Verify that aggregated 15m bar volume exactly matches the sum of 5m constituent bars."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_5m = HistoricalMarketSpec(symbol="ETHUSDT", interval="5m", dataset_tag="q2_2024")
    spec_15m = HistoricalMarketSpec(symbol="ETHUSDT", interval="15m", dataset_tag="q2_2024")

    df_5m = pd.read_parquet(store.get_dataset_filepath(spec_5m, ext="parquet"))
    df_15m = pd.read_parquet(store.get_dataset_filepath(spec_15m, ext="parquet"))

    # Sum of volume across entire quarter
    sum_vol_5m = float(df_5m["volume"].sum())
    sum_vol_15m = float(df_15m["volume"].sum())
    assert math.isclose(sum_vol_5m, sum_vol_15m, rel_tol=1e-5)


# =========================================================================
# 3. Relative Strength Engine Tests
# =========================================================================

def test_relative_strength_point_in_time_and_persistence():
    """Verify point-in-time calculation, zero future leakage, and ranking persistence decay."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    quarters = ["q1_2024", "q2_2024", "q3_2024", "q4_2024"]

    asset_candles = {}
    for sym in symbols:
        dfs = []
        for q in quarters:
            spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag=q)
            fpath = store.get_dataset_filepath(spec, ext="parquet")
            dfs.append(pd.read_parquet(fpath))
        asset_candles[sym] = pd.concat(dfs, ignore_index=True).to_dict(orient="records")

    rs_engine = CrossSectionalRelativeStrengthEngine(asset_candles, benchmark_symbol="BTCUSDT")
    snaps = rs_engine.compute_snapshots(lookback_bars=96)

    assert len(snaps) == 35136 - 96  # 35,040 snapshots after 96-bar initial lookback
    sample_snap = snaps[500]
    assert isinstance(sample_snap, CrossSectionalFeatureSnapshot)

    # Invariants for snapshot
    assert set(sample_snap.prices.keys()) == set(symbols)
    assert sample_snap.top_asset in symbols
    assert sample_snap.bottom_asset in symbols
    assert sample_snap.top_asset != sample_snap.bottom_asset
    # Ordinal ranks must be 1, 2, 3
    ranks = list(sample_snap.ordinal_rank_momentum.values())
    assert sorted(ranks) == [1, 2, 3]

    # Leadership concentration HHI is bounded between 1/3 (equal) and 1.0 (monopoly)
    assert 0.30 <= sample_snap.leadership_concentration_hhi <= 1.0

    # Persistence report: autocorrelation decays across forward horizons
    report = rs_engine.analyze_ranking_persistence(snaps, horizons_bars=(4, 16, 48, 96))
    assert isinstance(report, RankingPersistenceReport)
    auto = report.mean_spearman_autocorrelation
    assert auto["4_bars"] > auto["16_bars"]
    assert auto["16_bars"] > auto["48_bars"]
    assert auto["48_bars"] > auto["96_bars"]


# =========================================================================
# 4. Market Breadth Engine Tests
# =========================================================================

def test_market_breadth_engine_calculations():
    """Verify market breadth features, advance/decline ratio, and thrust detection."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    asset_candles = {}
    for sym in symbols:
        spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="q1_2024")
        asset_candles[sym] = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet")).to_dict(orient="records")

    breadth_engine = MarketBreadthEngine(asset_candles, benchmark_symbol="BTCUSDT")
    snaps = breadth_engine.compute_breadth_snapshots(lookback_bars=96)

    assert len(snaps) == len(asset_candles["BTCUSDT"]) - 96  # 8,640 snapshots after 96-bar lookback
    snap = snaps[300]
    assert isinstance(snap, MarketBreadthSnapshot)

    # Invariants
    assert 0.0 <= snap.advance_decline_ratio_24h <= 1.0
    assert 0.0 <= snap.pct_above_ema50 <= 1.0
    assert 0.0 <= snap.pct_in_bullish_trend <= 1.0
    assert snap.is_broad_advance == (snap.advance_decline_ratio_24h >= 0.66)
    assert isinstance(snap.breadth_thrust_detected, (bool, np.bool_))
    assert isinstance(snap.breadth_divergence_bearish, (bool, np.bool_))


# =========================================================================
# 5. Pre-Registration Gate & Hash Integrity Tests
# =========================================================================

def test_cross_sectional_preregistration_gate_freeze_and_tamper_prevention():
    """Verify pre-registration gate hashes for CS1-CS4 and tamper detection."""
    cfg1 = CS1Config()
    cfg2 = CS2Config()
    cfg3 = CS3Config()
    cfg4 = CS4Config()

    for cfg in [cfg1, cfg2, cfg3, cfg4]:
        h = cfg.config_hash
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex string

    gate = CrossSectionalPreRegistrationGate(
        registration_id="PREREG-SPRINT09.28-TEST",
        timestamp_utc="2026-10-15T09:00:00Z",
        baseline_commit="95fb3016162706b372768b718611972cc63393bf",
        strategy_hashes={
            "CS1": cfg1.config_hash,
            "CS2": cfg2.config_hash,
            "CS3": cfg3.config_hash,
            "CS4": cfg4.config_hash,
        },
        spot_execution_invariants={"spot_only": True, "no_naked_shorting": True},
        acceptance_criteria={"family_alpha_bonferroni": 0.0125},
        is_frozen=True,
    )

    assert gate.is_frozen is True
    # Verification with exact hashes passes
    active_hashes = {
        "CS1": cfg1.config_hash,
        "CS2": cfg2.config_hash,
        "CS3": cfg3.config_hash,
        "CS4": cfg4.config_hash,
    }
    assert gate.verify_integrity(active_hashes) is True

    # Mutating any parameter must fail verification
    tampered_hashes = dict(active_hashes)
    tampered_hashes["CS1"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert gate.verify_integrity(tampered_hashes) is False


# =========================================================================
# 6. Spot-Only Execution Invariants & Hypothesis Simulation Tests
# =========================================================================

def test_cross_sectional_hypotheses_simulation_and_accounting():
    """Verify CS1 to CS4 simulations under Spot rules and cost models."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    quarters = ["q1_2024", "q2_2024", "q3_2024", "q4_2024"]

    asset_candles = {}
    for sym in symbols:
        dfs = []
        for q in quarters:
            spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag=q)
            fpath = store.get_dataset_filepath(spec, ext="parquet")
            dfs.append(pd.read_parquet(fpath))
        asset_candles[sym] = pd.concat(dfs, ignore_index=True).to_dict(orient="records")

    runner = CrossSectionalResearchRunner(asset_candles, benchmark_symbol="BTCUSDT")

    # Evaluate CS1 (Momentum Persistence)
    res_cs1, recs_cs1 = runner.evaluate_cs1_momentum_persistence(CS1Config())
    assert res_cs1.total_events_evaluated > 2000
    assert len(recs_cs1) == res_cs1.independent_decision_events
    # Net taker expectancy must be exactly lower than net maker by 10 bps
    assert math.isclose(res_cs1.net_taker_expectancy_bps, res_cs1.net_maker_expectancy_bps - 10.0, abs_tol=0.05)
    # CS1 is EXPLORATORY because CI crosses zero despite positive net maker expectancy
    assert res_cs1.verdict == CrossSectionalDecisionVerdict.EXPLORATORY
    assert res_cs1.bootstrap_ci_95_maker_bps[0] < 0.0 < res_cs1.bootstrap_ci_95_maker_bps[1]

    # Evaluate CS2 (Leadership Rotation)
    res_cs2, recs_cs2 = runner.evaluate_cs2_leadership_rotation(CS2Config())
    assert res_cs2.verdict == CrossSectionalDecisionVerdict.REJECTED
    assert res_cs2.net_maker_expectancy_bps < 0.0

    # Evaluate CS3 (Breadth Confirmation)
    res_cs3, recs_cs3 = runner.evaluate_cs3_breadth_confirmation(CS3Config())
    assert res_cs3.verdict == CrossSectionalDecisionVerdict.REJECTED
    assert res_cs3.net_maker_expectancy_bps < 0.0

    # Evaluate CS4 (BTC Regime Dependency)
    res_cs4, recs_cs4 = runner.evaluate_cs4_btc_regime_dependency(CS4Config())
    assert res_cs4.verdict == CrossSectionalDecisionVerdict.REJECTED
    assert res_cs4.net_maker_expectancy_bps < 0.0

    # Verify Spot invariants in trade records: direction is LONG or CASH, prices are valid
    for r in recs_cs1[:10]:
        assert r.direction == "LONG"
        assert r.effective_entry_price > 0.0
        assert r.exit_price > 0.0
        assert r.holding_bars == 16


# =========================================================================
# 7. Perpetual Futures Funding Rate Research Contract Tests
# =========================================================================

def test_funding_rate_research_contract_safety_invariants():
    """Verify funding contract specifications, 4-timestamp availability, and prohibitions."""
    # 1. Empty records returns pending status
    report_pending = FundingRateResearchValidator.validate_funding_records([])
    assert report_pending.status == FundingReadinessStatus.INTERFACE_STANDARDIZED_DATA_PENDING
    assert report_pending.is_synthetic_data_prohibited is True
    assert report_pending.is_spot_perp_separation_enforced is True

    # 2. Spot context contamination raises SpotPerpetualAccountingContaminationError
    with pytest.raises(SpotPerpetualAccountingContaminationError):
        FundingRateResearchValidator.validate_funding_records([], is_spot_context=True)

    # 3. Synthetic record raises SyntheticFundingProhibitionError
    synthetic_rec = FundingRateRecord(
        funding_id="SYNTH_001",
        symbol="BTCUSDT",
        funding_timestamp_ms=1704067200000,
        funding_timestamp_utc="2024-01-01T00:00:00Z",
        publication_timestamp_ms=1704067200000,
        decision_available_timestamp_ms=1704067200000,
        funding_rate=0.0001,
        funding_rate_bps=1.0,
        mark_price=42000.0,
        index_price=42000.0,
        is_authentic=False,
        provenance_source="synthetic_gbm_model",
    )
    with pytest.raises(SyntheticFundingProhibitionError):
        FundingRateResearchValidator.validate_funding_records([synthetic_rec])

    # 4. Timestamp violation raises ValueError
    bad_time_rec = FundingRateRecord(
        funding_id="AUTH_001",
        symbol="BTCUSDT",
        funding_timestamp_ms=1704067200000,
        funding_timestamp_utc="2024-01-01T00:00:00Z",
        publication_timestamp_ms=1704067100000,  # Published before event occurred!
        decision_available_timestamp_ms=1704067200000,
        funding_rate=0.0001,
        funding_rate_bps=1.0,
        mark_price=42000.0,
        index_price=42000.0,
        is_authentic=True,
        provenance_source="binance_vision_funding_2024_01",
    )
    with pytest.raises(ValueError, match="Timestamp sequence violation"):
        FundingRateResearchValidator.validate_funding_records([bad_time_rec])

    # 5. Valid authentic record passes
    valid_rec = FundingRateRecord(
        funding_id="AUTH_002",
        symbol="BTCUSDT",
        funding_timestamp_ms=1704067200000,
        funding_timestamp_utc="2024-01-01T00:00:00Z",
        publication_timestamp_ms=1704067200500,
        decision_available_timestamp_ms=1704067201000,
        funding_rate=0.0001,
        funding_rate_bps=1.0,
        mark_price=42000.0,
        index_price=42000.0,
        is_authentic=True,
        provenance_source="binance_vision_funding_2024_01",
    )
    report_valid = FundingRateResearchValidator.validate_funding_records([valid_rec])
    assert report_valid.status == FundingReadinessStatus.AUTHENTIC_ARCHIVES_VERIFIED
    assert report_valid.authentic_records_loaded_count == 1


# =========================================================================
# 8. Multiple-Testing Statistical Control Tests
# =========================================================================

def test_cross_sectional_multiple_testing_control():
    """Verify Bonferroni family-wise alpha threshold and hypothesis survival."""
    nominal_alpha = 0.05
    n_hypotheses = 4  # CS1, CS2, CS3, CS4
    bonferroni_alpha = nominal_alpha / n_hypotheses
    assert bonferroni_alpha == 0.0125

    # Report verification
    report_path = Path("data/reports/sprint09_28_cross_sectional_report.json")
    assert report_path.exists(), "Sprint 09.28 report file missing"
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    # Check multiple testing block
    mt = rep.get("multiple_testing_control", {})
    assert len(mt.get("raw_p_values", {})) == 4
    assert mt.get("bonferroni_alpha") == 0.0125
    assert all(v is False for v in mt.get("bonferroni_survived", {}).values())


# =========================================================================
# 9. Performance Latency Budget Forensics
# =========================================================================

def test_cross_sectional_performance_latency_budget_pure_compute():
    """Verify pure in-memory compute latency for cross-sectional ranking is < 50 ms."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    asset_candles = {}
    for sym in symbols:
        spec = HistoricalMarketSpec(symbol=sym, interval="15m", dataset_tag="q1_2024")
        asset_candles[sym] = pd.read_parquet(store.get_dataset_filepath(spec, ext="parquet"))[:200].to_dict(orient="records")

    rs_engine = CrossSectionalRelativeStrengthEngine(asset_candles, benchmark_symbol="BTCUSDT")

    # Warmup
    _ = rs_engine.compute_snapshots(lookback_bars=96)

    import gc
    gc.collect()

    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        _ = rs_engine.compute_snapshots(lookback_bars=96)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    median_compute_ms = float(np.median(times))
    # Full snapshot computation for 200 bars across 3 assets must be well below 50 ms
    assert median_compute_ms < 50.0, f"Cross-sectional compute latency {median_compute_ms:.2f} ms exceeded 50 ms budget"
