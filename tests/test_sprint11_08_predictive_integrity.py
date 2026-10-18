"""Automated test suite for Sprint 11.08 Predictive Integrity & Decision Quality.

Sprint 11.08: Predictive Integrity, Portfolio Accounting & Decision Quality Optimization.
Verifies safety invariants, trade-by-trade financial reconciliation equations,
baseline Brier scoring, analogue anti-lookahead causality, decision failure attribution,
horizon friction hurdles, and controlled decision strategy benchmarks.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest


class TestSprint1108SafetyInvariants:
    """Verifies strict fail-closed safety and isolation invariants."""

    def test_offline_safety_flags(self):
        """Ensures trading and prospective scoring flags are strictly fail-closed."""
        from coin_behavior_engine.research_lab.configuration import ResearchLabConfig

        config = ResearchLabConfig()
        assert not hasattr(config, "trading_enabled") or getattr(config, "trading_enabled", False) is False
        assert not hasattr(config, "approval_4_authorized") or getattr(config, "approval_4_authorized", False) is False

    def test_all_10_deliverables_exist(self):
        """Verifies existence and non-empty status of all 10 required Sprint 11.08 deliverables."""
        deliverables = [
            "research_outputs/sprint11_07_accounting_audit.md",
            "research_outputs/reconciled_trade_ledger.csv",
            "research_outputs/portfolio_equity_reconciliation.csv",
            "research_outputs/prediction_metric_audit.md",
            "research_outputs/analogue_leakage_audit.csv",
            "research_outputs/decision_failure_attribution.csv",
            "research_outputs/holding_horizon_comparison.csv",
            "research_outputs/decision_strategy_comparison.csv",
            "research_outputs/research_dashboard_snapshot.json",
            "research_outputs/research_report_11_08.md",
        ]
        for path_str in deliverables:
            p = Path(path_str)
            assert p.is_file(), f"Missing required deliverable: {path_str}"
            assert p.stat().st_size > 50, f"Deliverable is empty or truncated: {path_str}"


class TestFinancialAccountingReconciliation:
    """Verifies financial reconciliation equations without double counting."""

    @pytest.fixture(scope="class")
    def ledger(self):
        path = Path("research_outputs/reconciled_trade_ledger.csv")
        assert path.is_file()
        return pd.read_csv(path)

    @pytest.fixture(scope="class")
    def equity(self):
        path = Path("research_outputs/portfolio_equity_reconciliation.csv")
        assert path.is_file()
        return pd.read_csv(path)

    def test_trade_reconciliation_math(self, ledger):
        """Verifies raw_pnl - slippage - fees == net_pnl for every closed trade."""
        diff = (ledger["raw_gross_pnl_usd"] - ledger["slippage_incurred_usd"] - ledger["fees_incurred_usd"]) - ledger["realized_net_pnl_usd"]
        assert (diff.abs() < 0.05).all(), "Trade math discrepancy detected in ledger"
        assert ledger["reconciliation_valid"].all()

    def test_strategy_d_exact_reconciliation(self, ledger):
        """Verifies Strategy D figures: Raw +$837.41 - Slip $512.30 - Fees $1025.11 == Net -$700.00."""
        d_trades = ledger[ledger["strategy_name"] == "Strategy_D_Analogue"]
        assert len(d_trades) == 55

        raw_sum = round(d_trades["raw_gross_pnl_usd"].sum(), 2)
        slip_sum = round(d_trades["slippage_incurred_usd"].sum(), 2)
        fee_sum = round(d_trades["fees_incurred_usd"].sum(), 2)
        net_sum = round(d_trades["realized_net_pnl_usd"].sum(), 2)

        assert abs(raw_sum - 837.41) < 1.0
        assert abs(slip_sum - 512.30) < 1.0
        assert abs(fee_sum - 1025.11) < 1.0
        assert abs(net_sum - (-700.00)) < 1.0
        assert abs((raw_sum - slip_sum - fee_sum) - net_sum) < 0.10

    def test_portfolio_equity_tracking(self, equity):
        """Verifies equity series monotonicity and peak tracking."""
        d_eq = equity[equity["strategy_name"] == "Strategy_D_Analogue"]
        assert len(d_eq) == 55

        # Check peak equity is >= running equity
        assert (d_eq["peak_equity_usd"] >= d_eq["running_equity_usd"] - 1e-4).all()
        # Final equity equals initial capital + total net PnL
        final_eq = float(d_eq["running_equity_usd"].iloc[-1])
        assert abs(final_eq - 9300.0) < 1.0


class TestPredictionMetricAudit:
    """Verifies baseline Brier calculations and directional edge determinations."""

    @pytest.fixture(scope="class")
    def predictions(self):
        path = Path("research_outputs/conditional_predictions.csv")
        assert path.is_file()
        return pd.read_csv(path)

    def test_class_imbalance_and_majority_baseline(self, predictions):
        """Verifies majority class is NEUTRAL at ~70.8%."""
        neutral_pct = (predictions["actual_direction"] == "NEUTRAL").mean() * 100.0
        assert round(neutral_pct, 1) == 70.8

    def test_directional_binary_accuracy_coinflip(self, predictions):
        """Verifies binary accuracy conditional on moves is ~51.9%."""
        moves = predictions[predictions["actual_direction"].isin(["UP", "DOWN"])].copy()
        dir_acc = ((moves["prob_up"] > moves["prob_down"]) == (moves["actual_direction"] == "UP")).mean()
        assert 50.0 <= (dir_acc * 100.0) <= 53.0

    def test_unconditional_frequency_brier_superiority(self, predictions):
        """Verifies model Brier does not beat empirical unconditional prior."""
        model_brier = predictions["brier_score"].mean()

        y_u = (predictions["actual_direction"] == "UP").astype(float)
        y_d = (predictions["actual_direction"] == "DOWN").astype(float)
        y_n = (predictions["actual_direction"] == "NEUTRAL").astype(float)

        p_u = (predictions["actual_direction"] == "UP").mean()
        p_d = (predictions["actual_direction"] == "DOWN").mean()
        p_n = (predictions["actual_direction"] == "NEUTRAL").mean()

        emp_brier = (((p_u - y_u) ** 2 + (p_d - y_d) ** 2 + (p_n - y_n) ** 2) / 3.0).mean()

        # Empirical baseline is lower (better) than model Brier
        assert emp_brier <= model_brier


class TestAnalogueSafetyAndDecisionFailures:
    """Verifies analogue anti-lookahead and trade failure attribution."""

    def test_analogue_temporal_safety(self):
        """Verifies that all analogues strictly preceded decision time by >= 24 hours."""
        df_audit = pd.read_csv("research_outputs/analogue_leakage_audit.csv")
        assert len(df_audit) > 1000
        assert (df_audit["audit_verdict"] == "PASS_STRICT_CAUSALITY").all()
        assert (df_audit["time_difference_hours"] >= 24.0).all()
        assert df_audit["is_strictly_prior"].all()
        assert df_audit["is_outcome_horizon_observable"].all()

    def test_decision_failure_attribution(self):
        """Verifies trade failure breakdown for Strategy D."""
        df_attr = pd.read_csv("research_outputs/decision_failure_attribution.csv")
        assert len(df_attr) == 55

        # Check failure categories exist
        cats = df_attr["failure_category"].unique()
        assert "EXCESSIVE_TRADING_COST" in cats or "INSUFFICIENT_MOMENTUM_DRIFT" in cats
        assert "STOP_LOSS_REVERSAL" in cats
        assert "PROFITABLE_TARGET_REACHED" in cats

        # Sum of net PnL is -$700.00
        assert abs(df_attr["net_pnl_usd"].sum() - (-700.00)) < 1.0

    def test_holding_horizon_friction_hurdles(self):
        """Verifies holding horizon drag ratios and viability classifications."""
        df_hz = pd.read_csv("research_outputs/holding_horizon_comparison.csv")
        assert len(df_hz) == 4

        # 15m drag is > 100% of mean move
        hz_15m = df_hz[df_hz["horizon"] == "15m"].iloc[0]
        assert hz_15m["friction_drag_pct_of_mean"] > 100.0
        assert hz_15m["commercial_viability"] == "UNVIABLE_UNDER_TAKER_FEES"

        # 24h drag is < 20% of mean move
        hz_24h = df_hz[df_hz["horizon"] == "24h"].iloc[0]
        assert hz_24h["friction_drag_pct_of_mean"] < 20.0
        assert hz_24h["commercial_viability"] == "COMMERCIALLY_VIABLE"

    def test_controlled_decision_experiments(self):
        """Verifies Models A through G and Model D's >90% loss reduction."""
        df_exp = pd.read_csv("research_outputs/decision_strategy_comparison.csv")
        assert len(df_exp) == 7

        m_c = df_exp[df_exp["model_id"] == "MODEL_C"].iloc[0]
        m_d = df_exp[df_exp["model_id"] == "MODEL_D"].iloc[0]

        # Model D reduced trades from 55 to 20
        assert m_c["trades_count"] == 55
        assert m_d["trades_count"] == 20

        # Model D reduced loss from -$700 to -$64.74 (> 90% loss reduction)
        assert abs(m_d["net_pnl_usd"]) < (abs(m_c["net_pnl_usd"]) * 0.15)
        # Model D halved max drawdown
        assert m_d["max_drawdown_pct"] <= (m_c["max_drawdown_pct"] * 0.55)

    def test_dashboard_snapshot_schema(self):
        """Verifies research dashboard snapshot schema and fail-closed flags."""
        path = Path("research_outputs/research_dashboard_snapshot.json")
        assert path.is_file()
        with open(path, "r", encoding="utf-8") as f:
            snap = json.load(f)

        assert snap["snapshot_metadata"]["validation_status"] == "OFFLINE_RESEARCH_VERIFIED_FAIL_CLOSED"
        assert snap["snapshot_metadata"]["trading_enabled"] is False
        assert snap["snapshot_metadata"]["approval_4_authorized"] is False
        assert "latest_market_state" in snap
        assert "prediction_probabilities" in snap
        assert "similar_historical_examples" in snap
        assert "recommended_research_decision" in snap
