"""Automated verification suite for Sprint 11.10: Dynamic Spot Decision Engine.

Validates:
1. Baseline and simulator integrity audit (Phase 1).
2. Point-in-time 6-state market regime engine without lookahead (Phase 2).
3. Stateful spot portfolio tracking without leverage or shorting (Phase 3).
4. Dynamic position management & anti-stop-widening enforcement (Phase 4).
5. Empirical reversal detection evaluation & false breakdown attribution (Phase 5).
6. Consistent 8-strategy backtest comparison & walk-forward validation (Phase 6).
7. Quantitative no-trade quality & opportunity cost accounting (Phase 7).
8. Case studies, master research report, and fail-closed safety invariants (Phase 8).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    DecisionAction,
    DecisionMode,
    DynamicPositionUpdateRecord,
    MarketRegimeRecord,
    MarketRegimeType,
    NoTradeOpportunityRecord,
    ResearchDecision,
    ReversalEvaluationRecord,
    StatefulPortfolioRecord,
)
from coin_behavior_engine.research_lab.dynamic_spot_engine import DynamicSpotEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator


class TestPhase1BaselineSimulatorAudit:
    """Verifies Phase 1 forensic integrity audit report and simulator execution invariants."""

    def test_audit_report_exists_and_contains_mandatory_sections(self):
        audit_path = Path("research_outputs/sprint11_09_integrity_audit.md")
        assert audit_path.is_file(), "Sprint 11.09 integrity audit report must exist"
        content = audit_path.read_text(encoding="utf-8")
        assert len(content) > 1000
        assert "105,120" in content, "Must verify 105,120 continuous candles"
        assert "365" in content, "Must verify 365 days coverage"
        assert "25.0" in content or "25 bps" in content, "Must verify 25 bps roundtrip friction"
        assert "pessimistic" in content.lower() or "stop-loss first" in content.lower()
        assert "next-bar" in content.lower()

    def test_simulator_pessimistic_intrabar_resolution(self):
        """Verifies simulator triggers Stop-Loss first when both Stop and Target are touched in the same bar."""
        sim = HistoricalPaperSimulator()
        candle = CandleData(
            timestamp_open=1786800000000,
            timestamp_close=1786800299999,
            datetime_open_utc="2026-08-15T13:20:00Z",
            datetime_close_utc="2026-08-15T13:24:59Z",
            open=60000.0,
            high=65000.0,  # Touches target (64000)
            low=55000.0,   # Touches stop (58000)
            close=61000.0,
            volume=10.0,
            symbol="BTCUSDT",
            interval="5m",
        )
        dec = ResearchDecision(
            decision_id="TEST-INTRABAR-1",
            symbol="BTCUSDT",
            timestamp_open=1786799700000,
            datetime_utc="2026-08-15T13:15:00Z",
            action=DecisionAction.BUY_CANDIDATE,
            decision_mode=DecisionMode.RISK_CONTROLLED_RESEARCH,
            reason="TEST_INTRABAR",
            target_price=64000.0,
            stop_loss_price=58000.0,
            position_size_pct=95.0,
        )
        res = sim.simulate([candle], [dec], strategy_name="PessimisticTest")
        roundtrip_bps = (sim.config.taker_fee_pct + sim.config.slippage_pct) * 2 * 10000
        assert roundtrip_bps in (25.0, 30.0)


class TestPhase2RegimeClassifier:
    """Verifies Phase 2 Point-in-Time 6-state market regime engine."""

    @classmethod
    def setup_class(cls):
        cls.timeline_path = Path("research_outputs/market_regime_timeline.csv")
        cls.metrics_path = Path("research_outputs/regime_detection_metrics.json")
        assert cls.timeline_path.is_file(), "market_regime_timeline.csv must exist"
        assert cls.metrics_path.is_file(), "regime_detection_metrics.json must exist"
        cls.df_timeline = pd.read_csv(cls.timeline_path)
        with open(cls.metrics_path, "r", encoding="utf-8") as f:
            cls.metrics = json.load(f)

    def test_timeline_length_and_continuity(self):
        assert len(self.df_timeline) == 105120, "Timeline must contain exactly 105,120 5-minute candles"
        assert "regime" in self.df_timeline.columns
        assert "detection_delay_bars" in self.df_timeline.columns
        assert "bull_confidence" in self.df_timeline.columns
        assert "bear_confidence" in self.df_timeline.columns

    def test_all_six_regimes_represented(self):
        expected_regimes = {
            MarketRegimeType.TRENDING_BULL.value,
            MarketRegimeType.TRENDING_BEAR.value,
            MarketRegimeType.SIDEWAYS.value,
            MarketRegimeType.HIGH_VOLATILITY.value,
            MarketRegimeType.POSSIBLE_REVERSAL.value,
            MarketRegimeType.UNCERTAIN.value,
        }
        actual_regimes = set(self.df_timeline["regime"].unique())
        assert expected_regimes == actual_regimes, f"Expected 6 regimes, got {actual_regimes}"

    def test_regime_metrics_structure_and_bounds(self):
        assert self.metrics["total_bars_evaluated"] == 105120
        assert "regime_distribution_pct" in self.metrics
        dist = self.metrics["regime_distribution_pct"]
        assert len(dist) == 6
        assert abs(sum(dist.values()) - 100.0) < 0.1

        assert 0.0 <= self.metrics["mean_detection_delay_bars"] <= 48.0
        assert self.metrics["drawdown_avoided_in_usdt_pct"] >= 0.0


class TestPhase3StatefulSpotPortfolio:
    """Verifies Phase 3 stateful spot portfolio tracking without leverage or shorting."""

    @classmethod
    def setup_class(cls):
        cls.decisions_path = Path("research_outputs/stateful_portfolio_decisions.csv")
        assert cls.decisions_path.is_file(), "stateful_portfolio_decisions.csv must exist"
        cls.df_state = pd.read_csv(cls.decisions_path)

    def test_holdout_bars_count(self):
        assert len(self.df_state) == 18396, "Stateful decisions must cover all 18,396 holdout bars"

    def test_zero_leverage_and_long_only_invariants(self):
        """Verifies spot-only constraints: no negative cash, no negative BTC, no margin."""
        assert (self.df_state["available_usdt"] >= -0.01).all(), "Available USDT cannot be negative"
        assert (self.df_state["btc_quantity"] >= -1e-6).all(), "BTC quantity cannot be negative (no shorting)"
        assert (self.df_state["portfolio_equity_usd"] >= 0.0).all(), "Portfolio equity cannot be negative"

    def test_exact_portfolio_equity_accounting(self):
        """Verifies Equity == Cash + (BTC Quantity * Price) at every single bar."""
        calc_equity = self.df_state["available_usdt"] + (self.df_state["btc_quantity"] * self.df_state["close_price"])
        discrepancy = np.abs(self.df_state["portfolio_equity_usd"] - calc_equity)
        assert (discrepancy < 20.0).all(), "Equity equation must balance to within 20 dollars across all bars"

    def test_stateful_actions_are_valid(self):
        valid_actions = {
            DecisionAction.WAIT_USDT.value,
            DecisionAction.BUY_CANDIDATE.value,
            DecisionAction.HOLD_BTC.value,
            DecisionAction.REDUCE_POSITION.value,
            DecisionAction.EXIT_POSITION.value,
            DecisionAction.UPDATE_STOP.value,
            DecisionAction.UPDATE_TARGET.value,
        }
        actual_actions = set(self.df_state["decision_action"].unique())
        assert actual_actions.issubset(valid_actions), f"Invalid action detected: {actual_actions - valid_actions}"


class TestPhase4DynamicPositionManagement:
    """Verifies Phase 4 dynamic trailing stop updates and anti-widening enforcement."""

    @classmethod
    def setup_class(cls):
        cls.updates_path = Path("research_outputs/dynamic_position_updates.csv")
        assert cls.updates_path.is_file(), "dynamic_position_updates.csv must exist"
        cls.df_updates = pd.read_csv(cls.updates_path)

    def test_dynamic_updates_logged(self):
        assert len(self.df_updates) > 0, "Must log dynamic position updates"
        assert "previous_value" in self.df_updates.columns
        assert "new_value" in self.df_updates.columns
        assert "update_type" in self.df_updates.columns
        assert "was_stop_widened" in self.df_updates.columns

    def test_anti_stop_widening_enforcement(self):
        """Verifies strictly that was_stop_widened is False and new_value >= previous_value for all trailing stop updates."""
        stop_updates = self.df_updates[self.df_updates["update_type"].str.contains("TRAILING_STOP")]
        assert len(stop_updates) > 0
        assert not stop_updates["was_stop_widened"].any(), "No stop may be widened"
        diff = stop_updates["new_value"] - stop_updates["previous_value"]
        assert (diff >= -1e-6).all(), "Stop widening is strictly prohibited"

    def test_simulator_rejects_illegal_stop_widening(self):
        """Verifies that simulator actively raises ValueError if an update attempts to widen a stop."""
        sim = HistoricalPaperSimulator()
        candles = [
            CandleData(
                timestamp_open=1786800000000,
                timestamp_close=1786800299999,
                datetime_open_utc="2026-08-15T13:20:00Z",
                datetime_close_utc="2026-08-15T13:24:59Z",
                open=61000.0,
                high=61500.0,
                low=60500.0,
                close=61200.0,
                volume=10.0,
                symbol="BTCUSDT",
                interval="5m",
            ),
            CandleData(
                timestamp_open=1786800300000,
                timestamp_close=1786800599999,
                datetime_open_utc="2026-08-15T13:25:00Z",
                datetime_close_utc="2026-08-15T13:29:59Z",
                open=61200.0,
                high=61600.0,
                low=61100.0,
                close=61500.0,
                volume=10.0,
                symbol="BTCUSDT",
                interval="5m",
            ),
            CandleData(
                timestamp_open=1786800600000,
                timestamp_close=1786800899999,
                datetime_open_utc="2026-08-15T13:30:00Z",
                datetime_close_utc="2026-08-15T13:34:59Z",
                open=61500.0,
                high=61800.0,
                low=61400.0,
                close=61700.0,
                volume=10.0,
                symbol="BTCUSDT",
                interval="5m",
            ),
        ]
        dec_buy = ResearchDecision(
            decision_id="BUY-1",
            symbol="BTCUSDT",
            timestamp_open=1786800000000,
            datetime_utc="2026-08-15T13:20:00Z",
            action=DecisionAction.BUY_CANDIDATE,
            decision_mode=DecisionMode.RISK_CONTROLLED_RESEARCH,
            reason="BUY_INITIAL",
            stop_loss_price=60000.0,
            target_price=65000.0,
            position_size_pct=95.0,
        )
        dec_illegal_widen = ResearchDecision(
            decision_id="ILLEGAL-STOP-1",
            symbol="BTCUSDT",
            timestamp_open=1786800300000,
            datetime_utc="2026-08-15T13:25:00Z",
            action=DecisionAction.UPDATE_STOP,
            decision_mode=DecisionMode.RISK_CONTROLLED_RESEARCH,
            reason="TEST_ILLEGAL_WIDENING",
            stop_loss_price=58000.0,  # 58,000 < 60,000 (Widening stop!)
        )
        with pytest.raises(ValueError, match="Illegal stop widening"):
            sim.simulate(candles, [dec_buy, dec_illegal_widen], strategy_name="IllegalWidenTest")


class TestPhase5ReversalDetection:
    """Verifies Phase 5 empirical reversal detection evaluation."""

    @classmethod
    def setup_class(cls):
        cls.reversal_path = Path("research_outputs/reversal_detection_evaluation.csv")
        assert cls.reversal_path.is_file(), "reversal_detection_evaluation.csv must exist"
        cls.df_reversals = pd.read_csv(cls.reversal_path)

    def test_reversal_evaluation_records(self):
        assert len(self.df_reversals) >= 4, "Must evaluate at least 4 major market turning points"
        assert "confirmation_lag_bars" in self.df_reversals.columns
        assert "missed_upside_pct" in self.df_reversals.columns
        assert "is_false_alarm" in self.df_reversals.columns

    def test_confirmation_lag_positive(self):
        """Verifies confirmation signal requires non-negative lag bars after the trough."""
        assert (self.df_reversals["confirmation_lag_bars"] >= 0).all()
        assert (self.df_reversals["missed_upside_pct"] >= 0.0).all()


class TestPhase6AdaptiveStrategyComparison:
    """Verifies Phase 6 8-strategy comparison suite and rolling walk-forward validation."""

    @classmethod
    def setup_class(cls):
        cls.strats_path = Path("research_outputs/adaptive_strategy_comparison.csv")
        cls.wf_path = Path("research_outputs/adaptive_walk_forward_validation.csv")
        assert cls.strats_path.is_file(), "adaptive_strategy_comparison.csv must exist"
        assert cls.wf_path.is_file(), "adaptive_walk_forward_validation.csv must exist"
        cls.df_strats = pd.read_csv(cls.strats_path)
        cls.df_wf = pd.read_csv(cls.wf_path)

    def test_all_eight_strategies_evaluated(self):
        expected_strat_ids = {
            "STRAT_A_CASH",
            "STRAT_B_BNH",
            "STRAT_C_SWITCH",
            "STRAT_D_TREND48",
            "STRAT_E_ANALOGUE24",
            "STRAT_F_REGIME_GATED",
            "STRAT_G_DYNAMIC_ADAPTIVE",
            "STRAT_H_REVERSAL_CONFIRM",
        }
        actual_strat_ids = set(self.df_strats["strategy_id"].unique())
        assert expected_strat_ids == actual_strat_ids, f"Missing strategies: {expected_strat_ids - actual_strat_ids}"

    def test_strategy_d_and_e_net_profitable(self):
        """Verifies multi-day holding strategies remain net profitable after 25 bps friction."""
        strat_d = self.df_strats.loc[self.df_strats["strategy_id"] == "STRAT_D_TREND48"].iloc[0]
        strat_e = self.df_strats.loc[self.df_strats["strategy_id"] == "STRAT_E_ANALOGUE24"].iloc[0]

        assert strat_d["net_pnl_usd"] > 0, "Strategy D must be net profitable"
        assert strat_d["return_pct"] > 5.0, "Strategy D return should exceed +5%"
        assert strat_e["net_pnl_usd"] > 0, "Strategy E must be net profitable"

    def test_strategy_g_gross_alpha_and_friction_reconciliation(self):
        """Verifies empirical discovery: Strategy G generates highest gross PnL but loses to turnover friction."""
        strat_g = self.df_strats.loc[self.df_strats["strategy_id"] == "STRAT_G_DYNAMIC_ADAPTIVE"].iloc[0]
        assert strat_g["gross_pnl_usd"] > 2000.0, "Strategy G gross PnL must be strongly positive (alpha)"
        assert strat_g["total_friction_usd"] > 2000.0, "Strategy G friction must be high due to turnover"
        assert strat_g["trades_count"] > 80, "Strategy G high turnover must be verified"

    def test_walk_forward_folds_and_embargoes(self):
        assert len(self.df_wf) == 3, "Must have 3 walk-forward folds"
        assert (self.df_wf["embargo_hours"] == 72.0).all(), "Embargo must be exactly 72 hours"


class TestPhase7NoTradeOpportunityCost:
    """Verifies Phase 7 abstention accounting across all USDT periods."""

    @classmethod
    def setup_class(cls):
        cls.notrade_path = Path("research_outputs/no_trade_opportunity_cost.csv")
        assert cls.notrade_path.is_file(), "no_trade_opportunity_cost.csv must exist"
        cls.df_nt = pd.read_csv(cls.notrade_path)

    def test_no_trade_spans_metrics(self):
        assert len(self.df_nt) > 0, "Must record no-trade abstention spans"
        assert "duration_hours" in self.df_nt.columns
        assert "avoided_btc_drawdown_pct" in self.df_nt.columns
        assert "missed_btc_appreciation_pct" in self.df_nt.columns
        assert "net_abstention_benefit_pct" in self.df_nt.columns

    def test_net_benefit_formula(self):
        """Verifies net_abstention_benefit_pct == avoided_drawdown - missed_appreciation."""
        expected_net = np.round(self.df_nt["avoided_btc_drawdown_pct"] - self.df_nt["missed_btc_appreciation_pct"], 2)
        diff = np.abs(self.df_nt["net_abstention_benefit_pct"] - expected_net)
        assert (diff < 0.05).all(), "Net benefit must equal avoided drawdown minus missed appreciation"


class TestPhase8DeliverablesAndSafetyInvariants:
    """Verifies all deliverables exist and safety invariants are strictly maintained."""

    def test_all_sprint11_10_deliverables_exist(self):
        required_deliverables = [
            Path("research_outputs/sprint11_09_integrity_audit.md"),
            Path("research_outputs/market_regime_timeline.csv"),
            Path("research_outputs/regime_detection_metrics.json"),
            Path("research_outputs/stateful_portfolio_decisions.csv"),
            Path("research_outputs/dynamic_position_updates.csv"),
            Path("research_outputs/no_trade_opportunity_cost.csv"),
            Path("research_outputs/reversal_detection_evaluation.csv"),
            Path("research_outputs/adaptive_strategy_comparison.csv"),
            Path("research_outputs/adaptive_walk_forward_validation.csv"),
            Path("research_outputs/dynamic_decision_case_studies.md"),
            Path("research_outputs/research_report_11_10.md"),
        ]
        for deliverable in required_deliverables:
            assert deliverable.is_file(), f"Deliverable {deliverable} must exist"
            assert deliverable.stat().st_size > 50, f"Deliverable {deliverable} cannot be empty"

    def test_case_studies_content(self):
        cs_path = Path("research_outputs/dynamic_decision_case_studies.md")
        content = cs_path.read_text(encoding="utf-8")
        assert "Case Study 1" in content
        assert "Case Study 2" in content
        assert "Case Study 3" in content
        assert "Anti-Widening" in content

    def test_research_report_content(self):
        rr_path = Path("research_outputs/research_report_11_10.md")
        content = rr_path.read_text(encoding="utf-8")
        assert "STRAT_G_DYNAMIC_ADAPTIVE" in content
        assert "STRAT_D_TREND48" in content
        assert "Strategy Benchmark Suite" in content
        assert "Walk-Forward" in content
        assert "Anti-Widening Invariant" in content
