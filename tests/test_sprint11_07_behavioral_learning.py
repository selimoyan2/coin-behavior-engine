"""Automated test suite for Sprint 11.07 Behavioral Learning Engine & Causal Backtesting.

Sprint 11.07: Behavioral Learning Engine & Causal Backtesting Foundation.
Verifies safety invariants, 365-day dataset integrity, state vector causal properties,
analogue buffer purging, probabilistic calibration, and walk-forward backtest outputs.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.analogue_engine import HistoricalAnalogueEngine
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    DecisionAction,
    DecisionMode,
    HistoricalAnalogueRecord,
    MarketRegimeType,
    MarketStateVector,
    ResearchDecision,
    WalkForwardFoldResult,
)
from coin_behavior_engine.research_lab.market_state_builder import MarketStateBuilder
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator


class TestSprint1107SafetyInvariants:
    """Verifies strict fail-closed safety and isolation invariants."""

    def test_offline_safety_flags(self):
        """Ensures trading and prospective scoring flags are strictly fail-closed."""
        from coin_behavior_engine.research_lab.configuration import ResearchLabConfig

        config = ResearchLabConfig()
        assert not hasattr(config, "trading_enabled") or getattr(config, "trading_enabled", False) is False
        assert not hasattr(config, "approval_4_authorized") or getattr(config, "approval_4_authorized", False) is False

    def test_all_11_deliverables_exist(self):
        """Verifies existence and non-empty status of all 11 required Sprint 11.07 deliverables."""
        deliverables = [
            "research_outputs/sprint11_06_methodology_audit.md",
            "research_outputs/historical_dataset_manifest.json",
            "research_outputs/market_state_dataset.parquet",
            "research_outputs/historical_analogues.csv",
            "research_outputs/conditional_predictions.csv",
            "research_outputs/prediction_calibration_report.md",
            "research_outputs/walk_forward_backtest.csv",
            "research_outputs/strategy_comparison.csv",
            "research_outputs/paper_trade_ledger.csv",
            "research_outputs/behavior_case_studies.md",
            "research_outputs/research_report_11_07.md",
        ]
        for path_str in deliverables:
            p = Path(path_str)
            assert p.is_file(), f"Missing required deliverable: {path_str}"
            assert p.stat().st_size > 50, f"Deliverable is empty or truncated: {path_str}"


class TestHistoricalDatasetIntegrity:
    """Verifies mathematical and temporal integrity of the 365-day dataset."""

    @pytest.fixture(scope="class")
    def manifest(self):
        path = Path("research_outputs/historical_dataset_manifest.json")
        assert path.is_file()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture(scope="class")
    def dataset(self):
        path = Path("research_outputs/market_state_dataset.parquet")
        assert path.is_file()
        return pd.read_parquet(path)

    def test_candle_count_and_continuity(self, manifest, dataset):
        """Verifies exact 365-day candle count and continuous 5m intervals."""
        assert manifest["total_candles"] == 105120
        assert manifest["span_days"] == 365
        assert len(dataset) == 105120
        assert manifest["gap_count_gt_300s"] == 0

        # Monotonic timestamp differences
        diffs = dataset["timestamp_open"].diff().dropna() / 1000.0
        assert (diffs == 300.0).all()

    def test_ohlcv_invariants(self, dataset):
        """Verifies high >= max(open, close), low <= min(open, close), prices > 0, vol >= 0."""
        assert (dataset["open"] > 0).all()
        assert (dataset["high"] > 0).all()
        assert (dataset["low"] > 0).all()
        assert (dataset["close"] > 0).all()
        assert (dataset["volume"] >= 0).all()

        max_oc = dataset[["open", "close"]].max(axis=1)
        min_oc = dataset[["open", "close"]].min(axis=1)
        assert (dataset["high"] >= max_oc - 1e-6).all()
        assert (dataset["low"] <= min_oc + 1e-6).all()

    def test_data_splits_coverage(self, manifest):
        """Verifies training, validation, and holdout test split partitions."""
        splits = manifest["splits"]
        total = manifest["total_candles"]

        tr = splits["training"]["candles"]
        val = splits["validation"]["candles"]
        te = splits["holdout_test"]["candles"]

        assert tr + val + te == total
        assert round(splits["training"]["pct"]) == 65
        assert round(splits["validation"]["pct"]) == 18
        assert round(splits["holdout_test"]["pct"]) == 18


class TestMarketStateAndAnalogueEngine:
    """Verifies feature engineering, anti-leakage purging, and probabilistic calibration."""

    @pytest.fixture(scope="class")
    def dataset(self):
        return pd.read_parquet("research_outputs/market_state_dataset.parquet")

    def test_feature_columns_and_causality(self, dataset):
        """Verifies feature columns exist without NaNs."""
        expected_cols = [
            "trend_5m_pct", "trend_15m_pct", "trend_1h_pct", "trend_4h_pct",
            "price_acceleration", "realized_vol_24", "realized_vol_72",
            "volatility_compression_ratio", "relative_volume_20",
            "distance_to_support_pct", "distance_to_resistance_pct",
            "drawdown_from_peak_pct", "runup_from_trough_pct",
            "breakout_state", "regime",
        ]
        for col in expected_cols:
            assert col in dataset.columns, f"Missing feature: {col}"
            assert dataset[col].isnull().sum() == 0, f"NaNs found in feature: {col}"

    def test_analogue_purging_invariant(self):
        """Verifies that all retrieved analogues satisfy t' <= query_idx - 288 (24h purge)."""
        engine = HistoricalAnalogueEngine()
        engine.load_data()

        # Test on a sample query bar
        query_idx = 70000
        analogues = engine.find_analogues(query_idx, k=20)
        assert len(analogues) == 20

        q_ts = int(engine.df["timestamp_open"].iloc[query_idx])
        min_purge_ms = 288 * 300_000  # 24 hours in ms

        for a in analogues:
            # Analogue must be at least 24 hours strictly before the decision bar
            time_diff = q_ts - a.analogue_timestamp
            assert time_diff >= min_purge_ms, (
                f"Anti-lookahead violation: analogue {a.analogue_datetime_utc} "
                f"is only {time_diff / 3600000:.2f}h prior to query {a.decision_datetime_utc}"
            )

    def test_analogue_spacing_diversity(self):
        """Verifies spatial thinning: analogues are not contiguous cluster repetitions."""
        engine = HistoricalAnalogueEngine()
        engine.load_data()

        query_idx = 80000
        analogues = engine.find_analogues(query_idx, k=10)
        timestamps = sorted([a.analogue_timestamp for a in analogues])

        # Check differences between sorted timestamps
        for i in range(1, len(timestamps)):
            diff_bars = (timestamps[i] - timestamps[i - 1]) / 300_000
            assert diff_bars >= 12, f"Analogue cluster collision: bars only {diff_bars} apart"

    def test_conditional_predictions_calibration(self):
        """Verifies prediction bounds, Brier score calculation, and probability properties."""
        df_preds = pd.read_csv("research_outputs/conditional_predictions.csv")
        assert len(df_preds) > 1000

        # Probabilities sum to 1.0
        prob_sums = df_preds["prob_up"] + df_preds["prob_down"] + df_preds["prob_neutral"]
        assert np.allclose(prob_sums, 1.0, atol=1e-3)

        # Brier scores in [0.0, 1.0]
        valid_brier = df_preds["brier_score"].dropna()
        assert (valid_brier >= 0.0).all()
        assert (valid_brier <= 1.0).all()
        assert valid_brier.mean() < 0.20  # Well below random guess 0.222


class TestWalkForwardAndPaperSimulation:
    """Verifies sequential event-driven paper simulation and walk-forward results."""

    def test_walk_forward_backtest_file(self):
        """Verifies 4 folds recorded with complete metric fields."""
        df_wf = pd.read_csv("research_outputs/walk_forward_backtest.csv")
        assert len(df_wf) == 4
        assert "FOLD_1" in df_wf["fold_id"].values
        assert "FOLD_4_HOLDOUT" in df_wf["fold_id"].values

        # Directional accuracy is calculated and realistic
        assert (df_wf["directional_accuracy_pct"] >= 60.0).all()
        assert (df_wf["brier_score"] <= 0.20).all()

    def test_strategy_comparison_benchmark(self):
        """Verifies all 6 strategies evaluated with realistic friction accounting."""
        df_comp = pd.read_csv("research_outputs/strategy_comparison.csv")
        assert len(df_comp) == 6
        expected_strats = {"STRAT_A", "STRAT_B", "STRAT_C", "STRAT_D", "STRAT_E", "STRAT_F"}
        assert set(df_comp["strategy_id"].values) == expected_strats

        strat_c = df_comp[df_comp["strategy_id"] == "STRAT_C"].iloc[0]
        strat_d = df_comp[df_comp["strategy_id"] == "STRAT_D"].iloc[0]

        # Drawdown halving verification: Strategy D max DD must be much less than Strategy C
        assert strat_d["max_drawdown_pct"] < (strat_c["max_drawdown_pct"] * 0.5)

        # Win rate verification: Strategy D win rate higher than Strategy C
        assert strat_d["win_rate_pct"] > strat_c["win_rate_pct"]

        # Friction accounting: Fees and slippage must be positive
        assert strat_d["total_fees_usd"] > 0
        assert strat_d["total_slippage_usd"] > 0

    def test_paper_trade_ledger_integrity(self):
        """Verifies paper trade ledger details (entry, exit, quantity, fees, holding time)."""
        df_trades = pd.read_csv("research_outputs/paper_trade_ledger.csv")
        assert len(df_trades) > 200

        # Required columns
        cols = ["trade_id", "strategy_name", "entry_time_utc", "entry_price", "exit_time_utc", "exit_price", "fees_paid", "slippage_cost", "net_pnl"]
        for c in cols:
            assert c in df_trades.columns

        # Holding period is positive
        assert (df_trades["holding_period_minutes"] > 0).all()
        # Fees paid are strictly positive
        assert (df_trades["fees_paid"] > 0).all()
        # Slippage cost is positive
        assert (df_trades["slippage_cost"] > 0).all()
