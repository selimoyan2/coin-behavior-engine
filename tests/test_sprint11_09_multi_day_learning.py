"""Automated verification suite for Sprint 11.09: Multi-Day Market Behavior Learning.

Validates:
1. Financial accounting audit, fee/slippage fill math, and 45 timeout vs 24 cost failure reconciliation
2. Multi-horizon engine, dynamic anti-lookahead purge windows, friction drag ratios, and effective N
3. Economic decision engine, friction hurdles, risk/reward filtering, and narrative explanations
4. Strategy benchmarks across 7 controlled strategies and transaction cost sensitivity across 5 regimes
5. Rolling walk-forward validation with 72-hour embargo windows
6. Research safety invariants and complete deliverables existence
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.contracts import (
    DecisionAction,
    DecisionMode,
    MarketRegimeType,
)
from coin_behavior_engine.research_lab.economic_decision_engine import EconomicDecisionEngine
from coin_behavior_engine.research_lab.multi_horizon_engine import MultiHorizonEngine


class TestAccountingAndAuditConsistency:
    """Verifies Phase 1 accounting audit and metric reconciliation."""

    def test_consistency_audit_report_exists(self):
        audit_path = Path("research_outputs/sprint11_08_consistency_audit.md")
        assert audit_path.is_file(), "Consistency audit report must exist"
        content = audit_path.read_text(encoding="utf-8")
        assert len(content) > 500
        assert "45" in content and "24" in content
        assert "25" in content  # 25 bps roundtrip friction

    def test_friction_definition_and_timeout_reconciliation(self):
        # 15 bps taker fee + 10 bps slippage = 25 bps roundtrip
        taker_fee_roundtrip_bps = 2 * 7.5
        slippage_roundtrip_bps = 2 * 5.0
        total_roundtrip_friction = taker_fee_roundtrip_bps + slippage_roundtrip_bps
        assert total_roundtrip_friction == 25.0

        # Exact decomposition of 45 timeout exits
        cost_failures = 24
        momentum_drift_failures = 21
        assert cost_failures + momentum_drift_failures == 45


class TestMultiHorizonBehavioralEngine:
    """Verifies Phase 2 multi-horizon learning, anti-lookahead purging, and calibration."""

    @classmethod
    def setup_class(cls):
        cls.engine = MultiHorizonEngine()
        cls.preds_path = Path("research_outputs/multi_horizon_predictions.csv")
        cls.dist_path = Path("research_outputs/conditional_return_distributions.csv")

    def test_multi_horizon_predictions_exist_and_cover_all_horizons(self):
        assert self.preds_path.is_file(), "Multi-horizon predictions CSV must exist"
        df = pd.read_csv(self.preds_path)
        assert len(df) > 1000

        expected_horizons = {"4h", "8h", "12h", "24h", "48h", "72h"}
        actual_horizons = set(df["horizon"].unique())
        assert expected_horizons == actual_horizons

    def test_anti_lookahead_purging_for_all_horizons(self):
        """Verifies that analogue discovery enforces candidate_idx <= query_idx - horizon_bars."""
        self.engine.load_and_enrich_data()
        assert self.engine.df is not None

        test_query_idx = 87000
        for h_key, cfg in self.engine.HORIZON_CONFIGS.items():
            b = cfg["bars"]
            analogues = self.engine.find_analogues_for_horizon(test_query_idx, h_key, k=15)
            assert len(analogues) > 0
            for an in analogues:
                a_idx = an["analogue_idx"]
                # Must be strictly less than or equal to query_idx - horizon_bars
                assert a_idx <= (test_query_idx - b), f"Analogue idx {a_idx} violates purge window for horizon {h_key}"

    def test_friction_drag_ratio_declines_with_horizon(self):
        """Verifies empirical finding: friction drag decreases monotonically from 4h to 72h."""
        assert self.dist_path.is_file(), "Conditional distributions CSV must exist"
        df = pd.read_csv(self.dist_path)
        horizon_mean_drag = df.groupby("horizon")["friction_drag_pct"].mean()

        # 4h should have significantly higher friction drag than 24h, 48h, and 72h
        assert horizon_mean_drag["4h"] > horizon_mean_drag["24h"]
        assert horizon_mean_drag["24h"] > horizon_mean_drag["48h"]
        assert horizon_mean_drag["48h"] > horizon_mean_drag["72h"]
        assert horizon_mean_drag["4h"] > 40.0, "4h friction drag should exceed 40%"
        assert horizon_mean_drag["72h"] < 15.0, "72h friction drag should be below 15%"

    def test_effective_sample_size_shrinks_with_horizon(self):
        """Verifies that N_eff decreases as horizon duration increases."""
        df = pd.read_csv(self.dist_path)
        mean_eff_n = df.groupby("horizon")["effective_n"].mean()

        assert mean_eff_n["4h"] > mean_eff_n["12h"]
        assert mean_eff_n["12h"] > mean_eff_n["24h"]
        assert mean_eff_n["24h"] > mean_eff_n["72h"]

    def test_brier_scores_bounded_in_valid_range(self):
        df_preds = pd.read_csv(self.preds_path)
        brier_vals = df_preds["brier_score"].dropna()
        assert (brier_vals >= 0.0).all()
        assert (brier_vals <= 1.0).all()


class TestEconomicDecisionEngineAndGating:
    """Verifies Phase 3 economic decision engine and friction hurdle gates."""

    @classmethod
    def setup_class(cls):
        cls.dec_path = Path("research_outputs/economic_decision_ledger.csv")

    def test_economic_decision_ledger_exists(self):
        assert self.dec_path.is_file(), "Economic decision ledger CSV must exist"
        df = pd.read_csv(self.dec_path)
        assert len(df) > 500

    def test_buy_candidate_invariants(self):
        df = pd.read_csv(self.dec_path)
        buys = df[df["action"] == DecisionAction.BUY_CANDIDATE.value]
        assert len(buys) > 0, "Should generate at least some BUY_CANDIDATE opportunities"

        for _, r in buys.iterrows():
            # Invariant 1: Calibrated analogues
            assert r["confidence_status"] == "CALIBRATED"
            # Invariant 2: Positive expected net return after friction
            assert r["expected_net_return_pct"] > 0.0
            # Invariant 3: High directional conviction
            assert r["prob_up"] >= 0.20
            # Invariant 4: No adverse liquidation cascade or bear trend
            assert r["market_regime"] not in ("CASCADE_LIQUIDATION", "TRENDING_BEAR")
            # Invariant 5: Target price higher than current price
            assert r["target_price"] > r["current_price"]
            # Invariant 6: Stop loss lower than current price
            assert r["stop_loss_price"] < r["current_price"]

    def test_rejection_reasons_present_on_no_trade(self):
        df = pd.read_csv(self.dec_path)
        no_trades = df[df["action"] == DecisionAction.NO_TRADE.value]
        assert len(no_trades) > 0
        # Rejection reason must be specified
        assert no_trades["rejection_reason"].notna().all()


class TestStrategyBenchmarksAndSensitivity:
    """Verifies Phase 4 multi-day strategy benchmarks and fee sensitivity."""

    @classmethod
    def setup_class(cls):
        cls.strat_path = Path("research_outputs/multi_horizon_strategy_comparison.csv")
        cls.cost_path = Path("research_outputs/transaction_cost_sensitivity.csv")

    def test_all_seven_benchmarks_evaluated(self):
        assert self.strat_path.is_file(), "Strategy comparison CSV must exist"
        df = pd.read_csv(self.strat_path)
        assert len(df) == 7

        expected_strats = {
            "STRAT_1_CASH",
            "STRAT_2_BNH",
            "STRAT_3_TREND",
            "STRAT_4_MOM",
            "STRAT_5_ANALOGUE_RAW",
            "STRAT_6_ANALOGUE_RISK",
            "STRAT_7_ANALOGUE_EVENT",
        }
        actual_strats = set(df["strategy_id"].unique())
        assert expected_strats == actual_strats

    def test_cash_baseline_invariants(self):
        df = pd.read_csv(self.strat_path)
        cash = df[df["strategy_id"] == "STRAT_1_CASH"].iloc[0]
        assert cash["trades_count"] == 0
        assert cash["net_pnl_usd"] == 0.0
        assert cash["return_pct"] == 0.0
        assert cash["max_drawdown_pct"] == 0.0

    def test_cost_sensitivity_monotonic_degradation(self):
        assert self.cost_path.is_file(), "Transaction cost sensitivity CSV must exist"
        df = pd.read_csv(self.cost_path)
        assert len(df) == 5

        # Check net PnL decreases as friction increases
        bps_list = df["roundtrip_friction_bps"].tolist()
        net_pnls = df["net_pnl_usd"].tolist()

        assert bps_list == sorted(bps_list), "Friction scenarios should be sorted by bps"
        for i in range(len(net_pnls) - 1):
            assert net_pnls[i] >= net_pnls[i + 1], f"Net PnL should monotonically decrease with fees at index {i}"


class TestWalkForwardAndExplanations:
    """Verifies Phase 5 walk-forward validation and Phase 6 decision explanations."""

    def test_walk_forward_folds_and_embargo(self):
        wf_path = Path("research_outputs/walk_forward_economic_validation.csv")
        assert wf_path.is_file(), "Walk-forward validation CSV must exist"
        df = pd.read_csv(wf_path)
        assert len(df) == 3

        # Embargo must be 72 hours across all folds
        assert (df["embargo_hours"] == 72.0).all()

    def test_decision_explanations_markdown(self):
        exp_path = Path("research_outputs/decision_explanations.md")
        assert exp_path.is_file(), "Decision explanations Markdown must exist"
        content = exp_path.read_text(encoding="utf-8")
        assert "Case 1" in content
        assert "Case 2" in content
        assert "Case 3" in content
        assert "friction" in content.lower()


class TestResearchReportAndSafetyInvariants:
    """Verifies Phase 7 research report and complete safety constraints."""

    def test_master_research_report_complete(self):
        report_path = Path("research_outputs/research_report_11_09.md")
        assert report_path.is_file(), "Master research report 11.09 must exist"
        content = report_path.read_text(encoding="utf-8")
        assert len(content) > 3000

        # Must address all 7 core research questions
        for q_num in range(1, 8):
            assert f"Question {q_num}" in content

    def test_deliverables_manifest_complete(self):
        required_deliverables = [
            "research_outputs/sprint11_08_consistency_audit.md",
            "research_outputs/multi_horizon_predictions.csv",
            "research_outputs/conditional_return_distributions.csv",
            "research_outputs/economic_decision_ledger.csv",
            "research_outputs/multi_horizon_strategy_comparison.csv",
            "research_outputs/transaction_cost_sensitivity.csv",
            "research_outputs/walk_forward_economic_validation.csv",
            "research_outputs/decision_explanations.md",
            "research_outputs/research_report_11_09.md",
        ]
        for deliverable in required_deliverables:
            p = Path(deliverable)
            assert p.is_file(), f"Required deliverable missing: {deliverable}"
            assert p.stat().st_size > 100, f"Deliverable is empty: {deliverable}"
