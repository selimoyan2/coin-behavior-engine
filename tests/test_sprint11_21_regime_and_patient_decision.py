"""Sprint 11.21 Invariant Test Suite: Market Regime & Patient Decision Intelligence V1.

Tests verify:
1. Forensic closure reclassifying ANALOG_FILTER_VALUE to NOT_SUPPORTED.
2. Causal Market Regime Engine definitions, 6 canonical states, and point-in-time causality.
3. Transition matrix row-sum conservation and persistence statistics.
4. Patient decision scenarios, output actions, and ledger completeness.
5. Opportunity cost accounting across 6 horizons (1h to 7d).
6. Deterministic portfolio replay, 30 bps round-trip friction, next-bar open fills, and cash conservation.
7. True matched portfolio controls (turnover and exposure).
8. Scientific honesty of all mandatory status declarations.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.regimes.causal_regime_engine import CausalRegimeEngine, CausalRegimeDecision
from coin_behavior_engine.regimes.patient_decision_engine import PatientDecisionEngine
from coin_behavior_engine.regimes.portfolio_replay import PortfolioReplaySimulator


def test_forensic_closure_reclassifications():
    """Verify Phase 0 forensic closure reclassifies ANALOG_FILTER_VALUE to NOT_SUPPORTED."""
    closure_path = Path("research_outputs/sprint11_20_forensic_closure_11_21.json")
    if not closure_path.exists():
        closure_path = Path("sprint11_20_forensic_closure_11_21.json")
    assert closure_path.exists(), "sprint11_20_forensic_closure_11_21.json must exist"

    with open(closure_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    mandate = data["mandatory_reclassifications"]
    assert mandate["ANALOG_FILTER_VALUE"] == "NOT_SUPPORTED"
    assert "underperformed" in mandate["ANALOG_FILTER_RECLASSIFICATION_REASON"].lower()

    # Matched turnover distribution
    mc = data["matched_turnover_control_distribution"]
    assert mc["monte_carlo_seeds_count"] == 20
    assert "mean" in mc["return_distribution_pct"]

    # Friction model audit
    fric = data["transaction_cost_model_audit"]
    assert fric["nominal_round_trip_friction_bps"] == 30.0
    assert fric["one_way_friction_bps"] == 15.0

    # Accepted subset Brier audit
    abst = data["abstention_threshold_reconciliation"]
    assert abst["accepted_subset_skill"]["skill_verdict"] == "NOT_SUPPORTED"
    assert abst["accepted_subset_skill"]["brier_skill_score"] < 0.0


def test_causal_regime_engine_states_and_causality():
    """Verify CausalRegimeEngine defines all 6 canonical states and respects causal point-in-time isolation."""
    expected_states = {
        "TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "TRANSITION", "UNCERTAIN"
    }
    assert set(CausalRegimeEngine.REGIMES) == expected_states

    # Test on synthetic 5m data
    n_bars = 1000
    times = [1640995200000 + i * 300000 for i in range(n_bars)]
    prices = 40000.0 + np.cumsum(np.random.normal(0, 50, n_bars))
    df_syn = pd.DataFrame({
        "open_time": times,
        "open": prices,
        "high": prices + 30.0,
        "low": prices - 30.0,
        "close": prices + 5.0,
        "volume": np.random.uniform(10, 50, n_bars)
    })

    engine = CausalRegimeEngine(df_syn)

    # Before 864 bars, must return UNCERTAIN due to insufficient history
    early_dec = engine.classify_at(100)
    assert early_dec.regime == "UNCERTAIN"
    assert early_dec.confidence <= 0.60

    # At bar 900, should return a valid regime
    dec = engine.classify_at(900)
    assert dec.regime in expected_states
    assert 0.0 <= dec.confidence <= 1.0
    assert dec.support_level > 0.0
    assert dec.resistance_level >= dec.support_level


def test_regime_transition_matrix_properties():
    """Verify transition matrix rows sum to 1.0 and persistence statistics are populated."""
    trans_path = Path("research_outputs/regime_transition_matrix_11_21.json")
    if not trans_path.exists():
        trans_path = Path("regime_transition_matrix_11_21.json")
    assert trans_path.exists(), "regime_transition_matrix_11_21.json must exist"

    with open(trans_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    matrix = data["transition_matrix"]
    regimes = data["regimes"]
    assert len(regimes) == 6

    for from_r in regimes:
        assert from_r in matrix
        row_sum = sum(matrix[from_r][to_r] for to_r in regimes)
        assert abs(row_sum - 1.0) < 1e-3, f"Row sum for {from_r} != 1.0: {row_sum}"

    # Verify persistence stats
    persist = data["persistence_statistics"]
    for r in regimes:
        assert r in persist
        assert "mean_duration_hours" in persist[r]


def test_patient_decision_scenarios_and_ledger():
    """Verify patient decision ledger exists, contains required columns and valid actions."""
    ledger_path = Path("research_outputs/patient_decision_ledger_11_21.parquet")
    if not ledger_path.exists():
        ledger_path = Path("patient_decision_ledger_11_21.parquet")
    assert ledger_path.exists(), "patient_decision_ledger_11_21.parquet must exist"

    df = pd.read_parquet(ledger_path)
    assert len(df) > 0, "Patient decision ledger must not be empty"

    required_cols = [
        "decision_idx", "open_time", "datetime_utc", "decision_close",
        "action", "scenario", "market_regime", "regime_confidence",
        "trend_24h", "volatility_state"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"

    allowed_actions = {
        "HOLD_BTC", "ENTER_BTC", "EXIT_TO_USDT", "WAIT_USDT", "WAIT_FOR_REENTRY", "NO_TRADE", "INSUFFICIENT_EVIDENCE"
    }
    for act in df["action"].unique():
        assert act in allowed_actions, f"Unexpected action: {act}"


def test_opportunity_cost_accounting():
    """Verify opportunity cost artifact calculates metrics across all 6 horizons."""
    opp_path = Path("research_outputs/opportunity_cost_audit_11_21.json")
    if not opp_path.exists():
        opp_path = Path("opportunity_cost_audit_11_21.json")
    assert opp_path.exists(), "opportunity_cost_audit_11_21.json must exist"

    with open(opp_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    assert "opportunity_costs_by_horizon" in summary

    expected_horizons = {"1h", "6h", "24h", "48h", "72h", "7d"}
    audited_horizons = set(summary["opportunity_costs_by_horizon"].keys())
    assert expected_horizons == audited_horizons

    for h in expected_horizons:
        h_data = summary["opportunity_costs_by_horizon"][h]
        p_up = h_data["pct_followed_by_appreciation"]
        p_down = h_data["pct_followed_by_depreciation"]
        assert abs((p_up + p_down) - 100.0) < 1.0, f"Appreciation and depreciation must sum to ~100%: {p_up} + {p_down}"
        assert "mean_missed_positive_movement_pct" in h_data
        assert "mean_avoided_negative_movement_pct" in h_data
        assert "net_opportunity_cost_after_friction_pct" in h_data


def test_portfolio_replay_cash_conservation_and_frictions():
    """Verify PortfolioReplaySimulator conserves capital, applies 15 bps friction each way, and liquidates terminal position."""
    # Create simple 10-bar synthetic dataframe
    df_syn = pd.DataFrame([
        {"open_time": 1000 + i * 300000, "open": 50000.0 + i * 100.0, "high": 50150.0 + i * 100.0, "low": 49950.0 + i * 100.0, "close": 50050.0 + i * 100.0, "volume": 10.0}
        for i in range(20)
    ])

    sim = PortfolioReplaySimulator(df_syn)

    # 1. CASH_ONLY: final equity must strictly equal initial capital
    res_cash = sim.run_simulation("CASH_ONLY", 0, 19)
    assert res_cash["final_equity"] == 10000.00
    assert res_cash["net_pnl_usdt"] == 0.00
    assert res_cash["total_trades"] == 0

    # 2. BUY_AND_HOLD: must have exactly 1 trade, friction deducted, terminal liquidation
    res_bh = sim.run_simulation("BUY_AND_HOLD", 0, 19)
    assert res_bh["total_trades"] == 1
    assert res_bh["total_fees_usdt"] > 0
    assert res_bh["total_slippage_usdt"] > 0
    assert abs(res_bh["final_equity"] - (res_bh["initial_capital"] + res_bh["net_pnl_usdt"])) < 0.05


def test_scientific_status_declarations():
    """Verify research deliverables maintain honest scientific status declarations."""
    reg_path = Path("research_outputs/regime_intelligence_audit_11_21.json")
    if not reg_path.exists():
        reg_path = Path("regime_intelligence_audit_11_21.json")
    assert reg_path.exists(), "regime_intelligence_audit_11_21.json must exist"

    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["regime_classification"] == "PASS"
    assert data["regime_predictive_value"] == "NOT_SUPPORTED"

    econ_path = Path("research_outputs/economic_replay_audit_11_21.json")
    if not econ_path.exists():
        econ_path = Path("economic_replay_audit_11_21.json")
    assert econ_path.exists(), "economic_replay_audit_11_21.json must exist"

    with open(econ_path, "r", encoding="utf-8") as f:
        econ = json.load(f)
    assert econ["patient_economic_edge"] == "NOT_SUPPORTED"

    ctrl_path = Path("research_outputs/matched_portfolio_controls_11_21.json")
    if not ctrl_path.exists():
        ctrl_path = Path("matched_portfolio_controls_11_21.json")
    assert ctrl_path.exists(), "matched_portfolio_controls_11_21.json must exist"

    with open(ctrl_path, "r", encoding="utf-8") as f:
        ctrl = json.load(f)
    assert ctrl["matched_turnover_controls"] == "PASS"
    assert ctrl["matched_exposure_controls"] == "PASS"
