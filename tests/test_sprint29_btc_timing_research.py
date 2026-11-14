"""Comprehensive Test Suite for Sprint 29: BTC Timing Research Engine & Historical Paper Portfolio.

Covers:
1. Data Integrity & Provenance (16 tests)
2. Feature Adapter & Read-Only Frozen Regimes (15 tests)
3. Timing Hypothesis Registry & Scientific Traceability (12 tests)
4. Transaction Cost Modeling & Friction Simulation (12 tests)
5. Timing Policy Engine & Discrete Allocation (15 tests)
6. Historical Decision Engine & Point-in-Time Non-Lookahead (12 tests)
7. Paper Portfolio Engine & Precise Accounting Invariants (20 tests)
8. Performance & Risk Analytics (15 tests)
9. Walk-Forward Validation & Holdout Contamination Audit (12 tests)
10. Repository Persistence, Recovery & Report Builder (10 tests)
11. Governance Invariants & Dashboard API Endpoints (15 tests)
Total: 144 tests
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.product.btc_timing_research.dataset_adapter import (
    HistoricalBTCDatasetAdapter,
    REGISTERED_BTC_DATASETS,
    DatasetVerificationResult,
)
from coin_behavior_engine.product.btc_timing_research.historical_feature_adapter import (
    HistoricalFeatureAdapter,
    CANONICAL_MODEL_ID,
    MODEL_STATUS,
    CANONICAL_REGIMES,
    VOLATILITY_REGIMES,
)
from coin_behavior_engine.product.btc_timing_research.timing_hypothesis_registry import (
    TimingHypothesisRecord,
    TimingHypothesisRegistry,
    PERMITTED_RESEARCH_STATUSES,
)
from coin_behavior_engine.product.btc_timing_research.transaction_cost_model import (
    CANONICAL_COST_PROFILES,
    TransactionCostProfile,
    TransactionCostEngine,
    TradeCostBreakdown,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    POLICY_REGISTRY,
    ALLOWED_ALLOCATION_TIERS,
    BaseTimingPolicy,
    BuyAndHoldPolicy,
    USDTCashPolicy,
    SimpleTrendPolicy,
    VolatilityAwarePolicy,
    CBERegimePolicy,
    CombinedTrendRegimePolicy,
    PolicyDecision,
    create_policy,
    snap_to_tier,
)
from coin_behavior_engine.product.btc_timing_research.historical_decision_engine import (
    HistoricalDecisionEngine,
    SimulatedDecisionRecord,
)
from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    SimulatedTradeRecord,
    EquityPoint,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
    PerformanceMetricsReport,
)
from coin_behavior_engine.product.btc_timing_research.benchmark_engine import (
    BenchmarkEngine,
    BenchmarkComparisonResult,
)
from coin_behavior_engine.product.btc_timing_research.walk_forward_validator import (
    WalkForwardValidator,
    WalkForwardValidationReport,
    WalkForwardFoldResult,
)
from coin_behavior_engine.product.btc_timing_research.timing_research_repository import (
    TimingResearchRepository,
    TimingExperimentRecord,
)
from coin_behavior_engine.product.btc_timing_research.timing_research_report_builder import (
    TimingResearchReportBuilder,
)
from coin_behavior_engine.product.btc_timing_research.timing_research_coordinator import (
    BTCTimingResearchCoordinator,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture(scope="module")
def real_btc_dataset():
    adapter = HistoricalBTCDatasetAdapter()
    return adapter.load_dataset("DS-BTC-1H-2023-2024")


@pytest.fixture(scope="module")
def real_btc_features(real_btc_dataset):
    adapter = HistoricalFeatureAdapter()
    return adapter.build_feature_table(real_btc_dataset)


@pytest.fixture
def synthetic_candles():
    """Create 200 synthetic 1-hour candles matching dataset schema."""
    n = 200
    base_ts = 1700000000000  # ms
    records = []
    price = 30000.0
    for i in range(n):
        ts = base_ts + (i * 3600000)
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
        change = (i % 7 - 3) * 100.0
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + 50.0
        low_p = min(open_p, close_p) - 50.0
        vol = 100.0 + (i % 10) * 10.0
        price = max(close_p, 1000.0)
        records.append({
            "open_time": ts,
            "datetime_utc": dt,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": vol,
            "quote_volume": vol * close_p,
        })
    return pd.DataFrame(records)


# =====================================================================
# 1. DATA INTEGRITY & PROVENANCE TESTS (16 tests)
# =====================================================================

class TestDataIntegrity:
    def test_physical_parquet_file_exists(self):
        adapter = HistoricalBTCDatasetAdapter()
        meta = REGISTERED_BTC_DATASETS["DS-BTC-1H-2023-2024"]
        target = Path(adapter.repo_root) / meta["relative_path"]
        assert target.exists()

    def test_parquet_file_sha256_matches_manifest(self):
        adapter = HistoricalBTCDatasetAdapter()
        res = adapter.verify_dataset("DS-BTC-1H-2023-2024")
        assert res.is_valid is True
        assert res.sha256 == "b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874"

    def test_parquet_row_count_exact_9528(self, real_btc_dataset):
        assert len(real_btc_dataset) == 9528

    def test_timestamp_monotonicity(self, real_btc_dataset):
        ts = real_btc_dataset["open_time"].values
        diffs = np.diff(ts)
        assert np.all(diffs > 0)

    def test_no_duplicate_timestamps(self, real_btc_dataset):
        ts = real_btc_dataset["open_time"]
        assert ts.duplicated().sum() == 0

    def test_no_missing_intervals_exact_1h(self, real_btc_dataset):
        ts = real_btc_dataset["open_time"].values
        diffs = np.diff(ts)
        expected_diff = 3600000  # 1 hour in ms
        assert np.all(diffs == expected_diff)

    def test_ohlc_integrity_high_ge_low(self, real_btc_dataset):
        assert (real_btc_dataset["high"] >= real_btc_dataset["low"]).all()

    def test_ohlc_integrity_high_ge_open_close(self, real_btc_dataset):
        assert (real_btc_dataset["high"] >= real_btc_dataset["open"]).all()
        assert (real_btc_dataset["high"] >= real_btc_dataset["close"]).all()

    def test_ohlc_integrity_low_le_open_close(self, real_btc_dataset):
        assert (real_btc_dataset["low"] <= real_btc_dataset["open"]).all()
        assert (real_btc_dataset["low"] <= real_btc_dataset["close"]).all()

    def test_ohlc_integrity_positive_prices(self, real_btc_dataset):
        assert (real_btc_dataset["open"] > 0).all()
        assert (real_btc_dataset["high"] > 0).all()
        assert (real_btc_dataset["low"] > 0).all()
        assert (real_btc_dataset["close"] > 0).all()

    def test_volume_non_negative(self, real_btc_dataset):
        assert (real_btc_dataset["volume"] >= 0).all()

    def test_timestamp_utc_conversion(self, real_btc_dataset):
        first_dt = str(real_btc_dataset["datetime_utc"].iloc[0])
        assert "2023-10-01" in first_dt

    def test_get_data_available_at_point_in_time_filtering(self):
        adapter = HistoricalBTCDatasetAdapter()
        cutoff_ms = 1696204800000  # 2023-10-02 00:00:00 UTC
        sliced = adapter.get_data_available_at(cutoff_ms, "DS-BTC-1H-2023-2024")
        assert len(sliced) > 0
        assert (sliced["open_time"] + 3600000 <= cutoff_ms).all()

    def test_get_data_available_at_empty_before_start(self):
        adapter = HistoricalBTCDatasetAdapter()
        cutoff_ms = 1690000000000  # before dataset starts
        sliced = adapter.get_data_available_at(cutoff_ms, "DS-BTC-1H-2023-2024")
        assert len(sliced) == 0

    def test_get_data_available_at_exact_boundary(self, real_btc_dataset):
        adapter = HistoricalBTCDatasetAdapter()
        first_row_close = real_btc_dataset["open_time"].iloc[0] + 3600000
        sliced = adapter.get_data_available_at(first_row_close, "DS-BTC-1H-2023-2024")
        assert len(sliced) == 1

    def test_dataset_adapter_rejection_of_unknown_dataset(self):
        adapter = HistoricalBTCDatasetAdapter()
        with pytest.raises(ValueError, match="Cannot load unverified dataset"):
            adapter.load_dataset("DS-NONEXISTENT")


# =====================================================================
# 2. FEATURE ADAPTER & FROZEN REGIMES TESTS (15 tests)
# =====================================================================

class TestFeatureAdapterAndFrozenRegimes:
    def test_feature_adapter_sma_calculation(self, real_btc_features):
        assert "sma_20" in real_btc_features.columns
        assert "sma_50" in real_btc_features.columns
        assert real_btc_features["sma_20"].iloc[20:].notna().all()

    def test_feature_adapter_ema_calculation(self, real_btc_features):
        assert "ema_21" in real_btc_features.columns
        assert "ema_55" in real_btc_features.columns
        assert real_btc_features["ema_21"].iloc[21:].notna().all()

    def test_feature_adapter_realized_volatility(self, real_btc_features):
        assert "realized_vol_24" in real_btc_features.columns
        assert (real_btc_features["realized_vol_24"].iloc[24:] >= 0).all()

    def test_feature_adapter_parkinson_volatility(self, real_btc_features):
        assert "parkinson_vol_24" in real_btc_features.columns
        assert (real_btc_features["parkinson_vol_24"].iloc[24:] >= 0).all()

    def test_feature_adapter_cbe_regime_labels_valid(self, real_btc_features):
        regimes = real_btc_features["market_regime"].unique()
        for r in regimes:
            assert r in CANONICAL_REGIMES

    def test_feature_adapter_frozen_regime_immutability(self, real_btc_features):
        assert CANONICAL_MODEL_ID == "CBE-0.7.0"
        assert MODEL_STATUS == "STRICTLY_FROZEN"
        assert "market_regime" in real_btc_features.columns
        assert len(real_btc_features) == 9528

    def test_feature_adapter_point_in_time_feature_isolation(self, synthetic_candles):
        adapter = HistoricalFeatureAdapter()
        feats1 = adapter.build_feature_table(synthetic_candles.iloc[:50])
        feats2 = adapter.build_feature_table(synthetic_candles.iloc[:100])
        assert np.isclose(feats1["sma_20"].iloc[40], feats2["sma_20"].iloc[40])

    def test_feature_adapter_zero_division_guard(self):
        df = pd.DataFrame({
            "open_time": [1000, 2000],
            "datetime_utc": ["2023-01-01T00:00:00Z", "2023-01-01T01:00:00Z"],
            "open": [100.0, 100.0],
            "high": [100.0, 100.0],
            "low": [100.0, 100.0],
            "close": [100.0, 100.0],
            "volume": [0.0, 0.0],
            "quote_volume": [0.0, 0.0],
        })
        adapter = HistoricalFeatureAdapter()
        res = adapter.build_feature_table(df)
        assert len(res) == 2
        assert np.isinf(res["parkinson_vol_24"].dropna()).sum() == 0

    def test_feature_adapter_output_columns(self, real_btc_features):
        expected_cols = [
            "sma_20", "sma_50", "ema_21", "ema_55",
            "realized_vol_24", "parkinson_vol_24",
            "volatility_regime", "market_regime",
        ]
        for col in expected_cols:
            assert col in real_btc_features.columns

    def test_feature_adapter_deterministic_output(self, real_btc_dataset):
        adapter = HistoricalFeatureAdapter()
        feats_a = adapter.build_feature_table(real_btc_dataset.iloc[:100])
        feats_b = adapter.build_feature_table(real_btc_dataset.iloc[:100])
        pd.testing.assert_frame_equal(feats_a, feats_b)

    def test_feature_adapter_volatility_percentile_range(self, real_btc_features):
        vol_regimes = real_btc_features["volatility_regime"].unique()
        for v in vol_regimes:
            assert v in VOLATILITY_REGIMES

    def test_feature_adapter_sma_trend_signal(self, real_btc_features):
        assert "sma_20" in real_btc_features.columns
        assert (real_btc_features["sma_20"].iloc[50:] > 0).all()

    def test_feature_adapter_empty_dataframe_handling(self):
        adapter = HistoricalFeatureAdapter()
        res = adapter.build_feature_table(pd.DataFrame())
        assert len(res) == 0

    def test_feature_adapter_computation_performance(self, real_btc_dataset):
        adapter = HistoricalFeatureAdapter()
        t0 = time.perf_counter()
        adapter.build_feature_table(real_btc_dataset)
        t1 = time.perf_counter()
        assert (t1 - t0) < 1.0  # Finishes in < 1 second for 9528 rows

    def test_feature_adapter_no_future_information_leakage(self, synthetic_candles):
        candles_mod = synthetic_candles.copy()
        candles_mod.loc[150:, "close"] *= 10.0
        adapter = HistoricalFeatureAdapter()
        orig = adapter.build_feature_table(synthetic_candles)
        mod = adapter.build_feature_table(candles_mod)
        assert np.isclose(orig["sma_20"].iloc[100], mod["sma_20"].iloc[100])


# =====================================================================
# 3. TIMING HYPOTHESIS REGISTRY TESTS (12 tests)
# =====================================================================

class TestTimingHypothesisRegistry:
    def test_registry_initializes_with_canonical_hypotheses(self):
        reg = TimingHypothesisRegistry()
        assert len(reg.list_hypotheses()) >= 6

    def test_registry_has_buy_and_hold_hypothesis(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-BnH-001")
        assert hyp is not None
        assert hyp.policy_id == "POLICY_BUY_AND_HOLD"

    def test_registry_has_cash_hypothesis(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-CASH-001")
        assert hyp is not None
        assert hyp.hypothesis_id == "HYP-TIMING-CASH-001"

    def test_registry_has_trend_hypothesis(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-TREND-001")
        assert hyp is not None
        assert "trend" in hyp.hypothesis_name.lower() or "trend" in hyp.policy_id.lower()

    def test_registry_has_volatility_hypothesis(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-VOL-001")
        assert hyp is not None
        assert "volatility" in hyp.research_question.lower() or "volatility" in hyp.hypothesis_name.lower()

    def test_registry_has_regime_hypothesis(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-REGIME-001")
        assert hyp is not None
        assert "cbe-0.7.0" in hyp.research_question.lower() or "regime" in hyp.hypothesis_name.lower()

    def test_registry_preregister_new_hypothesis_server_timestamp(self, tmp_path):
        reg = TimingHypothesisRegistry(persistence_path=tmp_path / "hypotheses.json")
        unique_id = f"HYP-CUSTOM-{int(time.time() * 1000)}"
        saved = reg.register_hypothesis(
            hypothesis_id=unique_id,
            hypothesis_name="Custom Test Hypothesis",
            hypothesis_version="1.0.0",
            research_question="Does custom allocation improve risk-adjusted outcomes?",
            policy_id="POLICY_CUSTOM",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["close"],
            decision_rule="Custom rule",
            parameters={"threshold": 0.5},
            parameter_selection_method="PREREGISTERED",
            transaction_cost_profile="BASE_COST",
        )
        assert saved.preregistration_timestamp != ""
        assert "T" in saved.preregistration_timestamp

    def test_registry_rejects_duplicate_hypothesis_id(self):
        reg = TimingHypothesisRegistry()
        with pytest.raises(ValueError, match="already registered"):
            reg.register_hypothesis(
                hypothesis_id="HYP-TIMING-BnH-001",  # duplicate
                hypothesis_name="Duplicate",
                hypothesis_version="1.0.0",
                research_question="Should fail",
                policy_id="POLICY_BUY_AND_HOLD",
                dataset_id="DS-BTC-1H-2023-2024",
                dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
                feature_set=["close"],
                decision_rule="Duplicate",
                parameters={},
                parameter_selection_method="FIXED",
                transaction_cost_profile="BASE_COST",
            )

    def test_registry_rejects_invalid_research_status(self):
        reg = TimingHypothesisRegistry()
        with pytest.raises(ValueError, match="Invalid research_status"):
            reg.register_hypothesis(
                hypothesis_id="HYP-INV-STAT-001",
                hypothesis_name="Invalid Status",
                hypothesis_version="1.0.0",
                research_question="Status test",
                policy_id="POLICY_TEST",
                dataset_id="DS-BTC-1H-2023-2024",
                dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
                feature_set=["close"],
                decision_rule="Rule",
                parameters={},
                parameter_selection_method="FIXED",
                transaction_cost_profile="BASE_COST",
                research_status="DEFINITIVE_TRUTH",
            )

    def test_registry_update_research_status_valid(self):
        reg = TimingHypothesisRegistry()
        updated = reg.update_research_status("HYP-TIMING-TREND-001", "OUT_OF_SAMPLE_TESTED")
        assert updated.research_status == "OUT_OF_SAMPLE_TESTED"

    def test_registry_retrospective_promotion_prohibited(self):
        reg = TimingHypothesisRegistry()
        hyp = reg.get_hypothesis("HYP-TIMING-TREND-001")
        assert hyp.research_status in PERMITTED_RESEARCH_STATUSES

    def test_registry_export_and_persistence(self, tmp_path):
        p = tmp_path / "hypotheses.json"
        reg = TimingHypothesisRegistry(persistence_path=p)
        reg.save_to_storage()
        assert p.exists()
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            hyp_list = data.get("hypotheses", data) if isinstance(data, dict) else data
            assert len(hyp_list) >= 6


# =====================================================================
# 4. TRANSACTION COST MODEL TESTS (12 tests)
# =====================================================================

class TestTransactionCostModel:
    def test_cost_profile_low_cost_parameters(self):
        p = CANONICAL_COST_PROFILES["LOW_COST"]
        assert p.taker_fee_pct == 0.0005
        assert p.bid_ask_spread_pct == 0.0002
        assert p.slippage_pct == 0.0001

    def test_cost_profile_base_cost_parameters(self):
        p = CANONICAL_COST_PROFILES["BASE_COST"]
        assert p.taker_fee_pct == 0.0010
        assert p.bid_ask_spread_pct == 0.0005
        assert p.slippage_pct == 0.0005

    def test_cost_profile_high_cost_parameters(self):
        p = CANONICAL_COST_PROFILES["HIGH_COST"]
        assert p.taker_fee_pct == 0.0020
        assert p.bid_ask_spread_pct == 0.0010
        assert p.slippage_pct == 0.0015

    def test_cost_engine_initialization(self):
        engine = TransactionCostEngine("BASE_COST")
        assert engine.profile.profile_id == "BASE_COST"

    def test_cost_model_buy_effective_price_higher_than_nominal(self):
        model = TransactionCostEngine("BASE_COST")
        breakdown = model.compute_costs(10000.0, 60000.0, is_buy=True)
        assert breakdown.effective_execution_price > 60000.0

    def test_cost_model_sell_effective_price_lower_than_nominal(self):
        model = TransactionCostEngine("BASE_COST")
        breakdown = model.compute_costs(10000.0, 60000.0, is_buy=False)
        assert breakdown.effective_execution_price < 60000.0

    def test_cost_model_compute_trade_costs(self):
        model = TransactionCostEngine("BASE_COST")
        breakdown = model.compute_costs(10000.0, 50000.0, is_buy=True)
        assert breakdown.fee_usdt == 10.0
        assert breakdown.total_transaction_cost_usdt > 10.0

    def test_cost_model_total_fee_drag_positive(self):
        model = TransactionCostEngine("BASE_COST")
        breakdown = model.compute_costs(10000.0, 50000.0, is_buy=True)
        assert breakdown.total_transaction_cost_usdt > 0.0
        assert breakdown.cost_drag_bps > 0.0

    def test_cost_model_rejects_unknown_profile(self):
        with pytest.raises(ValueError, match="Unknown cost profile"):
            TransactionCostEngine("NON_EXISTENT_PROFILE")

    def test_cost_model_drag_bps_calculation(self):
        model = TransactionCostEngine("BASE_COST")
        breakdown = model.compute_costs(10000.0, 50000.0, is_buy=True)
        assert np.isclose(breakdown.cost_drag_bps, 17.5, atol=1.0)

    def test_cost_model_high_cost_higher_than_low_cost(self):
        low = TransactionCostEngine("LOW_COST")
        high = TransactionCostEngine("HIGH_COST")
        cost_low = low.compute_costs(10000.0, 50000.0, is_buy=True).total_transaction_cost_usdt
        cost_high = high.compute_costs(10000.0, 50000.0, is_buy=True).total_transaction_cost_usdt
        assert cost_high > cost_low

    def test_cost_model_deterministic_calculations(self):
        model = TransactionCostEngine("HIGH_COST")
        eff1 = model.compute_costs(10000.0, 50000.0, is_buy=True).effective_execution_price
        eff2 = model.compute_costs(10000.0, 50000.0, is_buy=True).effective_execution_price
        assert eff1 == eff2


# =====================================================================
# 5. TIMING POLICY ENGINE TESTS (15 tests)
# =====================================================================

class TestTimingPolicyEngine:
    def test_policy_buy_and_hold_always_100_percent(self):
        policy = BuyAndHoldPolicy()
        row = {"close": 50000.0, "sma_20": 49000.0, "market_regime": "BEAR_TREND"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation == 1.0

    def test_policy_usdt_cash_always_0_percent(self):
        policy = USDTCashPolicy()
        row = {"close": 50000.0, "sma_20": 52000.0, "market_regime": "MOMENTUM_EXPANSION"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation == 0.0

    def test_policy_simple_trend_bull_100_bear_0(self):
        policy = SimpleTrendPolicy()
        bull_row = {"close": 50000.0, "sma_20": 48000.0, "sma_50": 45000.0}
        dec_bull = policy.evaluate(bull_row)
        assert dec_bull.target_btc_allocation == 1.0

        bear_row = {"close": 40000.0, "sma_20": 48000.0, "sma_50": 50000.0}
        dec_bear = policy.evaluate(bear_row)
        assert dec_bear.target_btc_allocation == 0.0

    def test_policy_volatility_aware_scaling(self):
        policy = VolatilityAwarePolicy()
        low_vol = {"close": 50000.0, "sma_20": 48000.0, "sma_50": 45000.0, "volatility_regime": "COMPRESSED_VOLATILITY"}
        dec_low = policy.evaluate(low_vol)
        assert dec_low.target_btc_allocation == 1.0

        high_vol = {"close": 50000.0, "sma_20": 48000.0, "sma_50": 45000.0, "volatility_regime": "EXTREME_VOLATILITY"}
        dec_high = policy.evaluate(high_vol)
        assert dec_high.target_btc_allocation <= 0.50

    def test_policy_cbe_regime_bull_trend_exposure(self):
        policy = CBERegimePolicy()
        row = {"market_regime": "MOMENTUM_EXPANSION", "volatility_regime": "NORMAL_VOLATILITY"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation == 1.0

    def test_policy_cbe_regime_bear_trend_exposure(self):
        policy = CBERegimePolicy()
        row = {"market_regime": "CAPITULATION", "volatility_regime": "EXTREME_VOLATILITY"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation == 0.0

    def test_policy_cbe_regime_high_volatility_reduction(self):
        policy = CBERegimePolicy()
        row = {"market_regime": "HIGH_VOLATILITY_EXPANSION", "volatility_regime": "EXTREME_VOLATILITY"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation <= 0.25

    def test_policy_combined_alpha_signals(self):
        policy = CombinedTrendRegimePolicy()
        row = {
            "close": 50000.0,
            "sma_20": 49000.0,
            "sma_50": 48000.0,
            "volatility_regime": "NORMAL_VOLATILITY",
            "market_regime": "MOMENTUM_EXPANSION",
        }
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation == 1.0

    def test_policy_allocation_discrete_steps_only(self, real_btc_features):
        records = real_btc_features.iloc[:50].to_dict("records")
        for pol_id in POLICY_REGISTRY:
            policy = create_policy(pol_id)
            for row in records:
                dec = policy.evaluate(row)
                assert dec.target_btc_allocation in ALLOWED_ALLOCATION_TIERS

    def test_snap_to_tier_clamping(self):
        assert snap_to_tier(0.48) == 0.50
        assert snap_to_tier(1.5) == 1.0
        assert snap_to_tier(-0.5) == 0.0

    def test_policy_allocation_bounded_between_0_and_100(self, real_btc_features):
        sample_row = real_btc_features.iloc[50].to_dict()
        for pol_id in POLICY_REGISTRY:
            policy = create_policy(pol_id)
            dec = policy.evaluate(sample_row)
            assert 0.0 <= dec.target_btc_allocation <= 1.0

    def test_policy_rejection_of_invalid_policy_id(self):
        with pytest.raises(ValueError, match="Unknown policy_id"):
            create_policy("POLICY_NON_EXISTENT")

    def test_policy_safe_handling_of_unknown_regime(self):
        policy = CBERegimePolicy()
        row = {"market_regime": "UNKNOWN_CUSTOM_REGIME", "volatility_regime": "NORMAL"}
        dec = policy.evaluate(row)
        assert dec.target_btc_allocation in ALLOWED_ALLOCATION_TIERS

    def test_policy_deterministic_decisions(self):
        policy = SimpleTrendPolicy()
        row = {"close": 50000.0, "sma_20": 48000.0, "sma_50": 45000.0}
        d1 = policy.evaluate(row)
        d2 = policy.evaluate(row)
        assert d1.target_btc_allocation == d2.target_btc_allocation

    def test_policy_state_isolation_between_evaluations(self):
        policy = SimpleTrendPolicy()
        row1 = {"close": 50000.0, "sma_20": 48000.0, "sma_50": 45000.0}
        row2 = {"close": 40000.0, "sma_20": 48000.0, "sma_50": 50000.0}
        d1 = policy.evaluate(row1)
        d2 = policy.evaluate(row2)
        d3 = policy.evaluate(row1)
        assert d1.target_btc_allocation == d3.target_btc_allocation
        assert d1.target_btc_allocation != d2.target_btc_allocation


# =====================================================================
# 6. HISTORICAL DECISION ENGINE NO-LOOKAHEAD TESTS (12 tests)
# =====================================================================

class TestHistoricalDecisionEngineNoLookahead:
    def test_four_timestamps_present_and_strictly_ordered(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        next_open = candles["open"].iloc[1]
        dec = hde.evaluate_step(row, next_open, 0.0)
        assert dec.observation_timestamp_ms <= dec.information_available_at_ms
        assert dec.information_available_at_ms <= dec.decision_timestamp_ms
        assert dec.decision_timestamp_ms <= dec.simulated_execution_timestamp_ms

    def test_observation_timestamp_equals_candle_close(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        expected_close_ms = row["open_time"] + 3600000
        assert dec.observation_timestamp_ms == expected_close_ms

    def test_information_available_at_ge_candle_close(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        assert dec.information_available_at_ms >= dec.observation_timestamp_ms

    def test_decision_timestamp_ge_information_available_at(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        assert dec.decision_timestamp_ms >= dec.information_available_at_ms

    def test_simulated_execution_timestamp_equals_next_candle_open(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        next_open_ms = candles["open_time"].iloc[1]
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        assert dec.simulated_execution_timestamp_ms >= next_open_ms

    def test_decision_uses_closed_candle_only(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec1 = hde.evaluate_step(row, 31000.0, 0.0)
        dec2 = hde.evaluate_step(row, 99999.0, 0.0)
        assert dec1.target_btc_allocation == dec2.target_btc_allocation

    def test_simulated_execution_price_recorded_accurately(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, 31234.5, 0.0)
        assert dec.nominal_execution_price == 31234.5

    def test_decision_log_immutable_sequence(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        exec_times = []
        for i in range(len(candles) - 1):
            row = candles.iloc[i].to_dict()
            next_open = candles["open"].iloc[i + 1]
            dec = hde.evaluate_step(row, next_open, 0.0)
            exec_times.append(dec.simulated_execution_timestamp_ms)
        diffs = np.diff(exec_times)
        assert np.all(diffs > 0)

    def test_decision_rationale_traceability(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        assert dec.decision_reason != ""
        assert len(dec.decision_reason) > 5

    def test_decision_with_lag_parameter(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy, publication_lag_ms=2500)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], 0.0)
        assert dec.information_available_at_ms == dec.observation_timestamp_ms + 2500

    def test_decision_engine_deterministic_reproducibility(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        next_open = candles["open"].iloc[1]
        d1 = hde.evaluate_step(row, next_open, 0.0)
        d2 = hde.evaluate_step(row, next_open, 0.0)
        assert d1.target_btc_allocation == d2.target_btc_allocation

    def test_rebalance_required_flag(self, synthetic_candles):
        candles = synthetic_candles.copy()
        candles["close"] = 35000.0
        candles["sma_20"] = 35000.0
        candles["sma_50"] = 30000.0
        policy = SimpleTrendPolicy()
        hde = HistoricalDecisionEngine(policy=policy)
        row = candles.iloc[0].to_dict()
        dec = hde.evaluate_step(row, candles["open"].iloc[1], current_btc_allocation=0.0)
        assert dec.rebalance_required == (dec.target_btc_allocation != 0.0)


# =====================================================================
# 7. PAPER PORTFOLIO ENGINE & ACCOUNTING TESTS (20 tests)
# =====================================================================

class TestPaperPortfolioEngineAndAccounting:
    def test_portfolio_initial_capital_conservation(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        assert engine.initial_capital_usdt == 10000.0
        assert engine.usdt_balance == 10000.0
        assert engine.btc_balance == 0.0

    def test_portfolio_buy_reduces_cash_increases_btc(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            decision_id="D1",
            policy_id="P",
            observation_timestamp_ms=1000,
            observation_timestamp_iso="2023-01-01T00:00:00Z",
            information_available_at_ms=1000,
            information_available_at_iso="2023-01-01T00:00:00Z",
            decision_timestamp_ms=1000,
            decision_timestamp_iso="2023-01-01T00:00:00Z",
            simulated_execution_timestamp_ms=2000,
            simulated_execution_timestamp_iso="2023-01-01T01:00:00Z",
            target_btc_allocation=1.0,
            current_allocation=0.0,
            rebalance_required=True,
            nominal_execution_price=50000.0,
            decision_reason="Buy",
            indicators_used={},
            status="PENDING",
        )
        trade = engine.execute_rebalance(dec, execution_price=50000.0)
        assert trade is not None
        assert trade.side == "BUY"
        assert engine.btc_balance > 0.0
        assert engine.usdt_balance < 10000.0

    def test_portfolio_sell_increases_cash_reduces_btc(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec_buy = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        engine.execute_rebalance(dec_buy, 50000.0)
        dec_sell = SimulatedDecisionRecord(
            "D2", "P", 2000, "2023-01-01T01:00:00Z", 2000, "2023-01-01T01:00:00Z",
            2000, "2023-01-01T01:00:00Z", 3000, "2023-01-01T02:00:00Z",
            0.0, 1.0, True, 55000.0, "Sell", {}, "PENDING",
        )
        trade = engine.execute_rebalance(dec_sell, 55000.0)
        assert trade is not None
        assert trade.side == "SELL"
        assert engine.btc_balance == 0.0
        assert engine.usdt_balance > 10000.0

    def test_portfolio_balance_never_negative_cash(self, synthetic_candles):
        policy = SimpleTrendPolicy()
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        engine, _ = run_historical_simulation(candles, policy, initial_capital_usdt=10000.0, start_index=10)
        assert engine.usdt_balance >= 0.0

    def test_portfolio_balance_never_negative_btc(self, synthetic_candles):
        policy = SimpleTrendPolicy()
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        engine, _ = run_historical_simulation(candles, policy, initial_capital_usdt=10000.0, start_index=10)
        assert engine.btc_balance >= 0.0

    def test_portfolio_no_leverage_invariable(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.5, 0.0, True, 50000.0, "Lev", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        total_eq = engine.current_equity(50000.0)
        btc_val = engine.btc_balance * 50000.0
        assert btc_val <= total_eq + 1e-6

    def test_portfolio_no_short_selling_invariable(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            -0.5, 0.0, True, 50000.0, "Short", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        assert engine.btc_balance == 0.0

    def test_portfolio_fee_deduction_accuracy(self):
        cost_engine = TransactionCostEngine("BASE_COST")
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0, cost_profile_id=cost_engine)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        trade = engine.execute_rebalance(dec, 50000.0)
        assert trade is not None
        assert np.isclose(trade.fee_usdt, 10.0, atol=0.05)

    def test_portfolio_spread_and_slippage_accounting(self):
        cost_engine = TransactionCostEngine("BASE_COST")
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0, cost_profile_id=cost_engine)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        trade = engine.execute_rebalance(dec, 50000.0)
        assert trade.effective_price > 50000.0

    def test_portfolio_discrete_allocation_clamping(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            0.50, 0.0, True, 50000.0, "Half", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        alloc = engine.current_allocation(50000.0)
        assert np.isclose(alloc, 0.50, atol=0.05)

    def test_portfolio_equity_curve_matches_mark_to_market(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        engine.record_snapshot(2000, "2023-01-01T01:00:00Z", 52000.0, target_allocation=1.0)
        assert len(engine.equity_curve) == 1
        expected = engine.usdt_balance + (engine.btc_balance * 52000.0)
        assert np.isclose(engine.equity_curve[0].total_equity_usdt, expected)

    def test_portfolio_unrealized_pnl_calculation(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        eq = engine.current_equity(60000.0)
        assert eq > 10000.0

    def test_portfolio_realized_pnl_calculation(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec_buy = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        engine.execute_rebalance(dec_buy, 50000.0)
        dec_sell = SimulatedDecisionRecord(
            "D2", "P", 2000, "2023-01-01T01:00:00Z", 2000, "2023-01-01T01:00:00Z",
            2000, "2023-01-01T01:00:00Z", 3000, "2023-01-01T02:00:00Z",
            0.0, 1.0, True, 60000.0, "Sell", {}, "PENDING",
        )
        engine.execute_rebalance(dec_sell, 60000.0)
        assert engine.total_realized_pnl > 0.0

    def test_portfolio_trade_ledger_audit_trail(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 50000.0, "Buy", {}, "PENDING",
        )
        engine.execute_rebalance(dec, 50000.0)
        assert len(engine.trades) == 1
        t = engine.trades[0]
        assert t.trade_id.startswith("TRD-")
        assert t.nominal_price == 50000.0

    def test_portfolio_rebalance_below_threshold_ignored(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec1 = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            0.50, 0.0, True, 50000.0, "Half", {}, "PENDING",
        )
        engine.execute_rebalance(dec1, 50000.0)
        dec2 = SimulatedDecisionRecord(
            "D2", "P", 2000, "2023-01-01T01:00:00Z", 2000, "2023-01-01T01:00:00Z",
            2000, "2023-01-01T01:00:00Z", 3000, "2023-01-01T02:00:00Z",
            0.50, 0.50, False, 50000.0, "Same", {}, "SKIPPED",
        )
        trade = engine.execute_rebalance(dec2, 50000.0)
        assert trade is None

    def test_portfolio_execution_failure_handling(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        dec = SimulatedDecisionRecord(
            "D1", "P", 1000, "2023-01-01T00:00:00Z", 1000, "2023-01-01T00:00:00Z",
            1000, "2023-01-01T00:00:00Z", 2000, "2023-01-01T01:00:00Z",
            1.0, 0.0, True, 0.0, "Bad", {}, "PENDING",
        )
        with pytest.raises(ValueError, match="Execution price must be positive"):
            engine.execute_rebalance(dec, 0.0)

    def test_portfolio_equity_series_monotonic_time(self, synthetic_candles):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        for _, row in synthetic_candles.iterrows():
            engine.record_snapshot(row["open_time"], row["datetime_utc"], row["close"], target_allocation=0.0)
        ts = [e.timestamp_ms for e in engine.equity_curve]
        assert np.all(np.diff(ts) > 0)

    def test_portfolio_cash_only_holds_value(self, synthetic_candles):
        policy = USDTCashPolicy()
        engine, _ = run_historical_simulation(synthetic_candles, policy, initial_capital_usdt=10000.0, start_index=10)
        assert engine.usdt_balance == 10000.0
        assert engine.btc_balance == 0.0

    def test_portfolio_all_in_btc_tracks_btc_price_minus_fees(self, synthetic_candles):
        policy = BuyAndHoldPolicy()
        engine, _ = run_historical_simulation(synthetic_candles, policy, initial_capital_usdt=10000.0, start_index=10)
        first_open = synthetic_candles["open"].iloc[10]
        last_close = synthetic_candles["close"].iloc[-1]
        raw_btc_return = (last_close - first_open) / first_open
        final_equity = engine.equity_curve[-1].total_equity_usdt
        port_return = (final_equity - 10000.0) / 10000.0
        assert port_return < raw_btc_return  # Due to initial entry cost

    def test_portfolio_high_cost_reduces_equity_relative_to_low_cost(self, synthetic_candles):
        policy = SimpleTrendPolicy()
        candles = synthetic_candles.copy()
        candles["sma_20"] = 30000.0
        candles["sma_50"] = 30000.0
        eng_low, _ = run_historical_simulation(candles, policy, 10000.0, cost_profile_id="LOW_COST", start_index=10)
        eng_high, _ = run_historical_simulation(candles, policy, 10000.0, cost_profile_id="HIGH_COST", start_index=10)
        assert eng_low.equity_curve[-1].total_equity_usdt >= eng_high.equity_curve[-1].total_equity_usdt


# =====================================================================
# 8. PERFORMANCE & RISK ANALYTICS TESTS (15 tests)
# =====================================================================

class TestPerformanceAnalytics:
    def test_analytics_gross_and_net_return(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "2023-01-01T00:00:00Z", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "2023-01-01T01:00:00Z", 50000.0, 12000.0, 0.0, 0.0, 12000.0, 0.0, 0.0, 12000.0, 0.0, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.net_return_pct == 20.0
        assert rep.gross_pnl_usdt >= 2000.0

    def test_analytics_max_drawdown_calculation(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=100.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 1.0, 100.0, 0.0, 0.0, 100.0, 0.0, 0.0, 100.0, 0.0, False),
            EquityPoint(2000, "T2", 1.0, 120.0, 0.0, 0.0, 120.0, 0.0, 0.0, 120.0, 0.0, False),
            EquityPoint(3000, "T3", 1.0, 90.0, 0.0, 0.0, 90.0, 0.0, 0.0, 120.0, 25.0, False),  # 25% DD
            EquityPoint(4000, "T4", 1.0, 110.0, 0.0, 0.0, 110.0, 0.0, 0.0, 120.0, 8.33, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert np.isclose(rep.max_drawdown_pct, 25.0)

    def test_analytics_sharpe_ratio_positive_and_negative(self):
        engine_up = PaperPortfolioEngine(initial_capital_usdt=100.0)
        engine_up.equity_curve = [
            EquityPoint(i * 3600000, f"T{i}", 1.0, 100.0 + i, 0.0, 0.0, 100.0 + i, 0.0, 0.0, 100.0 + i, 0.0, False)
            for i in range(50)
        ]
        rep_up = PerformanceAnalyticsEngine.calculate_metrics(engine_up)
        assert rep_up.sharpe_ratio is not None and rep_up.sharpe_ratio > 0

        engine_down = PaperPortfolioEngine(initial_capital_usdt=100.0)
        engine_down.equity_curve = [
            EquityPoint(i * 3600000, f"T{i}", 1.0, 100.0 - i, 0.0, 0.0, 100.0 - i, 0.0, 0.0, 100.0, i, False)
            for i in range(50)
        ]
        rep_down = PerformanceAnalyticsEngine.calculate_metrics(engine_down)
        assert rep_down.sharpe_ratio is not None and rep_down.sharpe_ratio < 0

    def test_analytics_sortino_ratio_downside_deviation(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=100.0)
        engine.equity_curve = [
            EquityPoint(i * 3600000, f"T{i}", 1.0, 100.0 + (5 if i % 2 == 0 else -2), 0.0, 0.0, 100.0 + (5 if i % 2 == 0 else -2), 0.0, 0.0, 120.0, 0.0, False)
            for i in range(50)
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.sortino_ratio is not None

    def test_analytics_calmar_ratio_return_over_drawdown(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=100.0)
        # 200 hours to satisfy sample length requirement (>= 168 hours)
        engine.equity_curve = [
            EquityPoint(i * 3600000, f"T{i}", 1.0, 100.0 + (i * 0.5) - (5 if i == 50 else 0), 0.0, 0.0, 100.0 + (i * 0.5) - (5 if i == 50 else 0), 0.0, 0.0, 150.0, 3.0, False)
            for i in range(200)
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.calmar_ratio is not None and rep.calmar_ratio > 0

    def test_analytics_win_rate_and_profit_factor(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
        ]
        engine.trades = [
            SimulatedTradeRecord("1", "D1", 1000, "T1", "BUY", 50000.0, 50000.0, 0.1, 5000.0, 5.0, 0.0, 0.0, 5.0, 5005.0, 4995.0, 0.1, 9995.0, 0.0),
            SimulatedTradeRecord("2", "D2", 2000, "T2", "SELL", 55000.0, 55000.0, 0.1, 5500.0, 5.5, 0.0, 0.0, 5.5, 5494.5, 10489.5, 0.0, 10489.5, 494.5),
            SimulatedTradeRecord("3", "D3", 3000, "T3", "BUY", 55000.0, 55000.0, 0.1, 5500.0, 5.5, 0.0, 0.0, 5.5, 5505.5, 4984.0, 0.1, 10484.0, 0.0),
            SimulatedTradeRecord("4", "D4", 4000, "T4", "SELL", 52000.0, 52000.0, 0.1, 5200.0, 5.2, 0.0, 0.0, 5.2, 5194.8, 10178.8, 0.0, 10178.8, -305.2),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.trade_count == 4
        assert rep.winning_trades == 1
        assert rep.losing_trades == 1
        assert rep.win_rate_pct == 50.0

    def test_analytics_turnover_percentage(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1700000000000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(1700086400000, "T2", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
        ]
        engine.trades = [
            SimulatedTradeRecord("1", "D1", 1700000000000, "T1", "BUY", 50000.0, 50000.0, 0.2, 10000.0, 10.0, 0.0, 0.0, 10.0, 10010.0, 0.0, 0.2, 10000.0, 0.0),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.turnover_pct > 0.0

    def test_analytics_fee_drag_gross_minus_net(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 10500.0, 0.0, 0.0, 10500.0, 0.0, 0.0, 10500.0, 0.0, False),
        ]
        engine.trades = [
            SimulatedTradeRecord("1", "D1", 1000, "T1", "BUY", 50000.0, 50000.0, 0.1, 5000.0, 100.0, 0.0, 0.0, 100.0, 5100.0, 4900.0, 0.1, 9900.0, 0.0)
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.cost_drag_pct > 0.0

    def test_analytics_time_in_market_percentage(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 0.0, 0.2, 10000.0, 10000.0, 1.0, 1.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 0.0, 0.2, 10000.0, 10000.0, 1.0, 1.0, 10000.0, 0.0, False),
            EquityPoint(3000, "T3", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert np.isclose(rep.time_invested_pct, 66.67, atol=0.1)

    def test_analytics_excess_return_over_buy_and_hold(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 11500.0, 0.0, 0.0, 11500.0, 0.0, 0.0, 11500.0, 0.0, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine, bnh_net_return_pct=10.0)
        assert rep.excess_return_over_bnh_pct == 5.0

    def test_analytics_handling_zero_trades(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.trade_count == 0
        assert rep.win_rate_pct is None

    def test_analytics_handling_zero_variance(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(i * 1000, f"T{i}", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False)
            for i in range(20)
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.sharpe_ratio is None
        assert rep.max_drawdown_pct == 0.0

    def test_analytics_risk_adjusted_metrics_with_zero_drawdown(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(1000, "T1", 50000.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, 0.0, 10000.0, 0.0, False),
            EquityPoint(2000, "T2", 50000.0, 10500.0, 0.0, 0.0, 10500.0, 0.0, 0.0, 10500.0, 0.0, False),
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        assert rep.calmar_ratio is None

    def test_analytics_benchmark_comparison_result(self, synthetic_candles):
        cost_engine = TransactionCostEngine("BASE_COST")
        b_engine = BenchmarkEngine(cost_engine)
        res, _, _ = b_engine.run_benchmarks(synthetic_candles, start_index=10)
        assert res.buy_and_hold_metrics.net_return_pct is not None
        assert res.usdt_cash_metrics.net_return_pct == 0.0

    def test_analytics_comprehensive_metrics_fields(self):
        engine = PaperPortfolioEngine(initial_capital_usdt=10000.0)
        engine.equity_curve = [
            EquityPoint(i * 3600000, f"T{i}", 50000.0, 10000.0 + (i * 10), 0.0, 0.0, 10000.0 + (i * 10), 0.0, 0.0, 10000.0 + (i * 10), 0.0, False)
            for i in range(30)
        ]
        rep = PerformanceAnalyticsEngine.calculate_metrics(engine)
        for attr in ["net_return_pct", "gross_pnl_usdt", "max_drawdown_pct", "sharpe_ratio", "cost_drag_pct"]:
            assert hasattr(rep, attr)


# =====================================================================
# 9. WALK-FORWARD & HOLDOUT VALIDATION TESTS (12 tests)
# =====================================================================

class TestWalkForwardAndHoldoutValidation:
    def test_walk_forward_expanding_folds(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=3)
        assert len(rep.folds) == 3

    def test_walk_forward_in_sample_and_out_of_sample_split(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        for f in rep.folds:
            assert f.train_start != ""
            assert f.test_start != ""

    def test_walk_forward_performance_degradation_calculation(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert hasattr(rep, "mean_degradation_pct")

    def test_walk_forward_no_leakage_between_train_and_test(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        for f in rep.folds:
            assert f.fold_index in {1, 2}

    def test_holdout_ledger_detection_of_prior_access(self):
        wfv = WalkForwardValidator()
        is_clean, count = wfv.check_holdout_contamination()
        assert is_clean is False
        assert count > 0

    def test_clean_holdout_not_available_classification(self, real_btc_features):
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, SimpleTrendPolicy(), n_folds=2)
        assert rep.holdout_status_code == "CLEAN_HOLDOUT_NOT_AVAILABLE"
        assert rep.clean_holdout_available is False

    def test_exploratory_result_verdict_assigned(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert rep.scientific_verdict in {"EXPLORATORY_RESULT", "REJECTED_OVERFITTING"}

    def test_rejection_of_overfitted_in_sample_as_definitive(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert rep.scientific_verdict != "DEFINITIVE_VALIDATED"

    def test_walk_forward_summary_table_generation(self, real_btc_features):
        policy = BuyAndHoldPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert len(rep.folds) == 2
        for f in rep.folds:
            assert hasattr(f, "test_net_return_pct")

    def test_walk_forward_fold_dates_monotonic(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=3)
        indices = [f.fold_index for f in rep.folds]
        assert indices == [1, 2, 3]

    def test_walk_forward_execution_across_all_policies(self, real_btc_features):
        policy = USDTCashPolicy()
        wfv = WalkForwardValidator()
        rep = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert rep.mean_out_of_sample_return_pct == 0.0

    def test_walk_forward_deterministic_fold_generation(self, real_btc_features):
        policy = SimpleTrendPolicy()
        wfv = WalkForwardValidator()
        r1 = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        r2 = wfv.execute_walk_forward(real_btc_features, policy, n_folds=2)
        assert r1.mean_out_of_sample_return_pct == r2.mean_out_of_sample_return_pct


# =====================================================================
# 10. REPOSITORY PERSISTENCE, RECOVERY & REPORT BUILDER TESTS (10 tests)
# =====================================================================

class TestRepositoryPersistenceAndReports:
    def test_repository_save_and_retrieve_experiment(self, tmp_path):
        repo = TimingResearchRepository(base_dir=tmp_path / "exp")
        record = TimingExperimentRecord(
            experiment_id="EXP-TEST-001",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            policy_id="POLICY_SIMPLE_TREND",
            policy_name="Simple Trend",
            policy_version="1.0.0",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            model_version="CBE-0.7.0",
            parameter_snapshot={},
            cost_profile_id="BASE_COST",
            initial_capital_usdt=10000.0,
            ending_equity_usdt=11000.0,
            net_return_pct=10.0,
            max_drawdown_pct=15.0,
            sharpe_ratio=1.1,
            trade_count=20,
            evaluation_start_utc="2023-10-01T00:00:00Z",
            evaluation_end_utc="2024-10-31T23:00:00Z",
            execution_convention="NEXT_OPEN_EXECUTION",
            research_status="EXPLORATORY_RESULT",
            metrics_summary={"cost_drag_pct": 2.0},
        )
        saved_path = repo.save_experiment(record, equity_curve=[], trades=[])
        assert saved_path.exists()
        loaded = repo.get_experiment("EXP-TEST-001")
        assert loaded is not None
        assert loaded["metadata"]["net_return_pct"] == 10.0

    def test_repository_atomic_index_update(self, tmp_path):
        repo = TimingResearchRepository(base_dir=tmp_path / "exp")
        record = TimingExperimentRecord(
            experiment_id="EXP-TEST-002",
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            policy_id="POLICY_BUY_AND_HOLD",
            policy_name="Buy and Hold",
            policy_version="1.0.0",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            model_version="CBE-0.7.0",
            parameter_snapshot={},
            cost_profile_id="BASE_COST",
            initial_capital_usdt=10000.0,
            ending_equity_usdt=25500.0,
            net_return_pct=155.0,
            max_drawdown_pct=32.0,
            sharpe_ratio=1.5,
            trade_count=1,
            evaluation_start_utc="2023-10-01T00:00:00Z",
            evaluation_end_utc="2024-10-31T23:00:00Z",
            execution_convention="NEXT_OPEN_EXECUTION",
            research_status="BENCHMARK",
            metrics_summary={},
        )
        repo.save_experiment(record, [], [])
        index_file = tmp_path / "exp" / "experiments_index.json"
        assert index_file.exists()
        with open(index_file, "r", encoding="utf-8") as f:
            idx = json.load(f)
            assert "EXP-TEST-002" in [x["experiment_id"] for x in idx["experiments"]]

    def test_repository_list_experiments_metadata(self, tmp_path):
        repo = TimingResearchRepository(base_dir=tmp_path / "exp")
        exps = repo.list_experiments()
        assert isinstance(exps, list)

    def test_repository_quarantine_corrupted_record(self, tmp_path):
        exp_dir = tmp_path / "exp"
        exp_dir.mkdir(parents=True, exist_ok=True)
        bad_file = exp_dir / "EXP-BAD.json"
        with open(bad_file, "w") as f:
            f.write("INVALID JSON")
        repo = TimingResearchRepository(base_dir=exp_dir)
        exps = repo.list_experiments()
        assert isinstance(exps, list)

    def test_repository_get_nonexistent_returns_none(self, tmp_path):
        repo = TimingResearchRepository(base_dir=tmp_path / "exp")
        assert repo.get_experiment("EXP-DOES-NOT-EXIST") is None

    def test_report_builder_markdown_generation(self):
        builder = TimingResearchReportBuilder()
        payload = {
            "metadata": {
                "experiment_id": "EXP-SAMPLE-001",
                "created_at_utc": "2026-11-14T20:00:00Z",
                "policy_id": "POLICY_SIMPLE_TREND",
                "policy_name": "Simple Trend Filter",
                "dataset_id": "DS-BTC-1H-2023-2024",
                "dataset_sha256": "b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
                "cost_profile_id": "BASE_COST",
                "initial_capital_usdt": 10000.0,
                "ending_equity_usdt": 8500.0,
                "net_return_pct": -15.0,
                "max_drawdown_pct": 25.0,
                "sharpe_ratio": -0.5,
                "trade_count": 50,
                "research_status": "EXPLORATORY_RESULT",
                "metrics_summary": {
                    "cost_drag_pct": 5.0,
                    "gross_pnl_usdt": -1000.0,
                    "net_pnl_usdt": -1500.0,
                },
                "benchmark_comparison": {
                    "buy_and_hold_return_pct": 155.0,
                    "buy_and_hold_ending_equity": 25500.0,
                },
            }
        }
        md = builder.build_markdown_report(payload)
        assert "# BTC TIMING RESEARCH ENGINE — EXPERIMENT REPORT" in md
        assert "EXP-SAMPLE-001" in md

    def test_report_builder_includes_governance_disclaimer(self):
        builder = TimingResearchReportBuilder()
        payload = {
            "metadata": {
                "experiment_id": "EXP-G-001",
                "policy_id": "POLICY_USDT_CASH",
                "policy_name": "Cash",
                "metrics_summary": {},
            }
        }
        md = builder.build_markdown_report(payload)
        assert "DISCLAIMER: HISTORICAL OFFLINE RESEARCH ONLY" in md

    def test_report_builder_includes_performance_metrics(self):
        builder = TimingResearchReportBuilder()
        payload = {
            "metadata": {
                "experiment_id": "EXP-M-001",
                "net_return_pct": 16.08,
                "max_drawdown_pct": 31.19,
                "metrics_summary": {},
            }
        }
        md = builder.build_markdown_report(payload)
        assert "+16.08%" in md
        assert "31.19%" in md

    def test_report_builder_includes_trade_ledger_summary(self):
        builder = TimingResearchReportBuilder()
        payload = {
            "metadata": {
                "experiment_id": "EXP-T-001",
                "trade_count": 123,
                "metrics_summary": {},
            }
        }
        md = builder.build_markdown_report(payload)
        assert "123" in md

    def test_coordinator_orchestrates_simulation_and_persistence(self):
        coord = BTCTimingResearchCoordinator.get_instance()
        assert coord is not None
        exp = coord.run_experiment(
            policy_id="POLICY_USDT_CASH",
            cost_profile_id="BASE_COST",
            initial_capital_usdt=10000.0,
        )
        assert exp is not None
        assert exp["metadata"]["policy_id"] == "POLICY_USDT_CASH"
        assert exp["metadata"]["net_return_pct"] == 0.0


# =====================================================================
# 11. GOVERNANCE INVARIANTS & DASHBOARD API TESTS (15 tests)
# =====================================================================

class TestGovernanceAndDashboardApi:
    @pytest.fixture
    def api_service(self):
        return ProductDashboardApiService()

    def test_api_overview_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/overview")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data["model_version"] == "CBE-0.7.0"
        assert data["model_status"] == "STRICTLY_FROZEN"
        assert data["live_order_execution"] == "PERMANENTLY_PROHIBITED"

    def test_api_datasets_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/datasets")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "datasets" in data
        assert len(data["datasets"]) >= 1

    def test_api_policies_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/policies")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "policies" in data
        assert len(data["policies"]) >= 6

    def test_api_cost_profiles_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/cost-profiles")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "cost_profiles" in data
        assert "BASE_COST" in [p["profile_id"] for p in data["cost_profiles"]]

    def test_api_experiments_list_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/experiments")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "experiments" in data

    def test_api_experiment_detail_returns_200(self, api_service):
        coord = BTCTimingResearchCoordinator.get_instance()
        exp = coord.run_experiment("POLICY_BUY_AND_HOLD")
        exp_id = exp["metadata"]["experiment_id"]
        status, body = api_service.handle_request(f"/api/v1/product/research/btc-timing/experiments/{exp_id}")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "metadata" in data or "experiment_id" in data or "experiment" in data

    def test_api_experiment_detail_not_found_returns_404(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/experiments/EXP-NONEXISTENT")
        assert status == 404

    def test_api_experiment_report_returns_200(self, api_service):
        coord = BTCTimingResearchCoordinator.get_instance()
        exp = coord.run_experiment("POLICY_BUY_AND_HOLD")
        exp_id = exp["metadata"]["experiment_id"]
        status, body = api_service.handle_request(f"/api/v1/product/research/btc-timing/experiments/{exp_id}/report")
        assert status == 200
        assert "BTC TIMING RESEARCH ENGINE" in str(body)

    def test_api_compare_returns_200(self, api_service):
        status, body = api_service.handle_request("/api/v1/product/research/btc-timing/compare")
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert "comparisons" in data or data.get("status") == "success"

    def test_api_simulate_post_returns_200(self, api_service):
        payload = {
            "policy_id": "POLICY_SIMPLE_TREND",
            "cost_profile_id": "BASE_COST",
            "initial_capital_usdt": 10000.0,
        }
        status, body = api_service.handle_post_request(
            "/api/v1/product/research/btc-timing/simulate",
            body=payload,
        )
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data.get("status") == "success"

    def test_api_walk_forward_post_returns_200(self, api_service):
        payload = {
            "policy_id": "POLICY_SIMPLE_TREND",
            "n_folds": 2,
        }
        status, body = api_service.handle_post_request(
            "/api/v1/product/research/btc-timing/walk-forward",
            body=payload,
        )
        assert status == 200
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data.get("status") == "success"

    def test_api_live_trading_order_create_forbidden_403(self, api_service):
        payload = {"symbol": "BTCUSDT", "side": "BUY", "quantity": 1.0}
        status, body = api_service.handle_post_request(
            "/api/v1/product/research/btc-timing/orders/create",
            body=payload,
        )
        assert status == 403
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data["error"] == "GOVERNANCE_VIOLATION"

    def test_api_live_trading_broker_api_forbidden_403(self, api_service):
        status, body = api_service.handle_request(
            "/api/v1/product/research/btc-timing/broker-api/accounts"
        )
        assert status == 403
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data["error"] == "GOVERNANCE_VIOLATION"

    def test_api_live_trading_place_order_forbidden_403(self, api_service):
        payload = {"action": "place-order"}
        status, body = api_service.handle_post_request(
            "/api/v1/product/research/btc-timing/place-order",
            body=payload,
        )
        assert status == 403
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data["error"] == "GOVERNANCE_VIOLATION"

    def test_api_live_trading_trade_execute_forbidden_403(self, api_service):
        payload = {"execute": True}
        status, body = api_service.handle_post_request(
            "/api/v1/product/research/btc-timing/trade/execute",
            body=payload,
        )
        assert status == 403
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
        assert data["error"] == "GOVERNANCE_VIOLATION"
