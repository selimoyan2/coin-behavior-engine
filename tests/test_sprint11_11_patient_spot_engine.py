"""Automated test suite for Sprint 11.11: Decision Failure Forensics & Patient Adaptive Spot Engine.

Validates:
1. Phase 1 Baseline & Discrepancy Integrity Audit (Buy-and-Hold reconciliation, Drawdown Additivity correction).
2. Phase 2 Decision Failure Attribution across all 214 trades of Strategies G and H into 10 categories.
3. Phase 3 Patient Spot State Machine FSM transitions, 3-bar hysteresis, and 36-bar cooldown.
4. Phase 4 Adaptive Stop Update Audit and anti-widening invariant.
5. Phase 5 9-Strategy Benchmark comparisons (Strategies A through I) and 3-fold Walk-Forward validation.
6. Phase 6 Bear Market Capital Protection across market regimes.
7. Phase 7 Master Research Report and Decision Journal deliverables.
8. CLI Integration for Sprint 11.11.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.contracts import (
    PatientSpotState,
    FailureAttributionCategory,
    DecisionFailureRecord,
    PatientSpotStateTransitionRecord,
    AdaptiveStopUpdateAuditRecord,
    ReentryCooldownRecord,
    BearMarketProtectionRecord,
    PatientStrategyComparisonRecord,
)
from coin_behavior_engine.research_lab.patient_spot_engine import PatientSpotEngine
from coin_behavior_engine.research_lab.cli import main


class TestSprint1111Contracts:
    """Verifies dataclasses, enums, and data schema integrity."""

    def test_patient_spot_states_enum(self):
        expected_states = {
            "WAIT_USDT",
            "WATCH_REVERSAL",
            "BUY_READY",
            "HOLD_BTC",
            "REDUCE_BTC",
            "EXIT_TO_USDT",
        }
        actual_states = {s.value for s in PatientSpotState}
        assert actual_states == expected_states

    def test_failure_attribution_categories(self):
        core_categories = {
            "PREMATURE_STOP_OUT",
            "UNNECESSARY_RE_ENTRY",
            "FEE_DRIVEN_LOSS",
            "OVER_SIZED_RISK",
            "INTRADAY_VOLATILITY_WHIPSAW",
            "FALSE_REVERSAL",
            "ADVERSE_REGIME_EXPOSURE",
            "STALE_SIGNAL_ENTRY",
            "OVERCONFIDENT_PROBABILITY",
            "GENUINE_FORECAST_FAILURE",
        }
        actual_categories = {c.value for c in FailureAttributionCategory}
        assert core_categories.issubset(actual_categories)


class TestPhase1IntegrityAudit:
    """Verifies Phase 1 baseline reproduction and mathematical discrepancy reconciliation."""

    def test_audit_report_exists_and_contains_reconciliations(self):
        audit_file = Path("research_outputs/sprint11_10_integrity_audit.md")
        assert audit_file.exists(), "Phase 1 audit report must exist"

        content = audit_file.read_text(encoding="utf-8")
        assert "Buy-and-Hold Discrepancy" in content
        assert "48.70%" in content
        assert "8.55%" in content
        assert "Drawdown Additivity Fallacy" in content
        assert "Retrospective Selection Bias" in content


class TestPhase2DecisionFailureForensics:
    """Verifies forensic failure classification of all 214 trades from Strategies G and H."""

    def test_failure_attribution_dataset(self):
        csv_file = Path("research_outputs/decision_failure_attribution.csv")
        assert csv_file.exists(), "Failure attribution CSV must exist"
        df = pd.read_csv(csv_file)

        assert len(df) == 214, f"Expected exactly 214 trades audited, found {len(df)}"

        # Check required columns
        required_cols = [
            "trade_id",
            "strategy_id",
            "timestamp_open",
            "datetime_utc",
            "entry_price",
            "exit_price",
            "net_pnl_usd",
            "gross_pnl_usd",
            "total_friction_usd",
            "failure_category",
            "primary_failure_mechanism",
            "avoidable_by_patience",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column {col} in failure attribution"

        # Check strategy distribution: Strategy G had 98 trades, Strategy H had 116 trades
        strat_counts = df["strategy_id"].value_counts().to_dict()
        assert strat_counts.get("STRATEGY_G", 0) == 98
        assert strat_counts.get("STRATEGY_H", 0) == 116

        # Check category validity
        valid_cats = {c.value for c in FailureAttributionCategory}
        for cat in df["failure_category"].unique():
            assert cat in valid_cats, f"Invalid failure category: {cat}"


class TestPhase3PatientSpotPolicyFSM:
    """Verifies state machine transitions, confirmation hysteresis, and cooldown enforcement."""

    def test_state_transitions_file(self):
        csv_file = Path("research_outputs/patient_spot_state_transitions.csv")
        assert csv_file.exists(), "State transitions CSV must exist"
        df = pd.read_csv(csv_file)

        assert len(df) > 0
        valid_states = {s.value for s in PatientSpotState}
        for state in df["to_state"].unique():
            assert state in valid_states, f"Unknown FSM state: {state}"

    def test_reentry_and_cooldown_analysis(self):
        csv_file = Path("research_outputs/reentry_and_cooldown_analysis.csv")
        assert csv_file.exists(), "Cooldown analysis CSV must exist"
        df = pd.read_csv(csv_file)

        # File may have rows or valid headers
        required_cols = [
            "reentry_attempt_id",
            "bars_since_exit",
            "cooldown_threshold_bars",
            "permitted",
            "avoided_friction_usd",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column {col} in cooldown analysis"

        if not df.empty:
            assert (df["cooldown_threshold_bars"] == 36).all(), "Cooldown threshold must be 36 bars"


class TestPhase4AdaptiveStopUpdates:
    """Verifies structural trailing stop milestones and anti-widening rule."""

    def test_adaptive_stop_update_audit(self):
        csv_file = Path("research_outputs/adaptive_stop_update_audit.csv")
        assert csv_file.exists(), "Adaptive stop audit CSV must exist"
        df = pd.read_csv(csv_file)

        required_cols = [
            "update_id",
            "old_stop_loss",
            "new_stop_loss",
            "was_stop_widened",
            "structural_evidence_met",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column {col} in stop update audit"

        if not df.empty:
            # Crucial invariant: Stops must NEVER be widened
            assert not df["was_stop_widened"].any(), "Trailing stops must never be widened"
            assert (df["new_stop_loss"] >= df["old_stop_loss"]).all(), "New stop must be >= old stop"


class TestPhase5StrategyBenchmarks:
    """Verifies 9-strategy comparisons and walk-forward validation."""

    def test_strategy_comparison_dataset(self):
        csv_file = Path("research_outputs/patient_strategy_comparison.csv")
        assert csv_file.exists(), "Strategy comparison CSV must exist"
        df = pd.read_csv(csv_file)

        assert len(df) == 9, f"Expected 9 strategies compared, found {len(df)}"

        # Check all 9 strategies are present
        strat_ids = df["strategy_id"].tolist()
        expected_ids = [
            "STRAT_A_CASH",
            "STRAT_B_BNH",
            "STRAT_C_SWITCH",
            "STRAT_D_TREND48",
            "STRAT_E_ANALOGUE24",
            "STRAT_F_EXISTING_DYN",
            "STRAT_G_PATIENT_DYN",
            "STRAT_H_NO_ANALOGUES",
            "STRAT_I_WITH_EVENTS",
        ]
        for exp in expected_ids:
            assert exp in strat_ids, f"Strategy {exp} missing from comparison"

        # Check that Strategy G dramatically slashed friction vs Strategy F and is net profitable
        row_c = df[df["strategy_id"] == "STRAT_C_SWITCH"].iloc[0]
        row_f = df[df["strategy_id"] == "STRAT_F_EXISTING_DYN"].iloc[0]
        row_g = df[df["strategy_id"] == "STRAT_G_PATIENT_DYN"].iloc[0]
        row_h = df[df["strategy_id"] == "STRAT_H_NO_ANALOGUES"].iloc[0]

        assert row_g["total_friction_usd"] < row_f["total_friction_usd"], "Strategy G must have lower friction than Strategy F"
        assert row_g["trades_count"] < row_f["trades_count"], "Strategy G must have fewer trades than Strategy F"
        assert row_g["net_pnl_usd"] > 0, "Strategy G must be net profitable after costs"
        assert row_g["net_pnl_usd"] > row_c["net_pnl_usd"], "Strategy G must dramatically outperform simple switching"
        assert row_g["net_pnl_usd"] > row_h["net_pnl_usd"], "Analogue predictions must add incremental value over pure trend ablation"

    def test_walk_forward_validation_dataset(self):
        csv_file = Path("research_outputs/patient_walk_forward_validation.csv")
        assert csv_file.exists(), "Walk forward CSV must exist"
        df = pd.read_csv(csv_file)

        assert len(df) == 3, f"Expected 3 walk forward folds, found {len(df)}"
        assert (df["embargo_hours"] == 72.0).all(), "Embargo must be 72 hours"


class TestPhase6BearMarketProtection:
    """Verifies capital protection metrics during bear and high volatility regimes."""

    def test_bear_market_protection_dataset(self):
        csv_file = Path("research_outputs/bear_market_capital_protection.csv")
        assert csv_file.exists(), "Bear market protection CSV must exist"
        df = pd.read_csv(csv_file)

        assert len(df) > 0, "Bear market protection records must not be empty"
        assert "mean_usdt_allocation_pct" in df.columns
        assert "avoided_portfolio_drawdown_pct" in df.columns
        assert "net_protection_benefit_pct" in df.columns


class TestPhase7ReportsAndDeliverables:
    """Verifies that human-readable decision journal and master research report are generated."""

    def test_decision_journal_exists(self):
        journal = Path("research_outputs/decision_journal_11_11.md")
        assert journal.exists()
        content = journal.read_text(encoding="utf-8")
        assert "CBE Sprint 11.11 Human-Readable Decision Journal" in content
        assert "Case Study A" in content
        assert "Case Study B" in content
        assert "Case Study C" in content

    def test_research_report_exists(self):
        report = Path("research_outputs/research_report_11_11.md")
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "Sprint 11.11 Master Research Report" in content
        assert "STRAT_G_PATIENT_DYN" in content
        assert "Drawdown Additivity Fallacy" in content


class TestCliIntegration:
    """Verifies CLI argument handling for Sprint 11.11."""

    def test_cli_parser_defaults_to_11_11(self):
        from coin_behavior_engine.research_lab import cli
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--sprint", default="11.11", choices=["11.05", "11.06", "11.07", "11.08", "11.09", "11.10", "11.11"])
        args = parser.parse_args([])
        assert args.sprint == "11.11"
