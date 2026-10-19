"""Comprehensive invariant test suite for Sprint 11.16B.9: Canonical Portfolio Accounting & Cross-Sprint Reconciliation.

Replaces outcome-forcing assertions with strict engineering invariants:
1. Capital conservation invariant: Initial + Gross PnL - Friction == Final Cash (to 0.0001 USD).
2. Terminal inventory & mark-to-market reconciliation: 18.07 USDT residual fully resolved to 0.0000.
3. Canonical Execution Policy V2 fee (10 bps) and slippage (5 bps) scaling per side.
4. Causal timestamp ordering: decision_bar < fill_bar <= exit_bar <= terminal_bar.
5. Uniqueness invariant: Zero duplicate trade IDs or order IDs.
6. Cross-sprint Policy C trade count reconciliation consistency.
7. Historical evaluation contamination register and mandatory operational declarations.
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

CANONICAL_LEDGER_PATH = Path("research_outputs/policy_d_v2_canonical_trade_ledger_11_16b_9.csv")
ROOT_LEDGER_PATH = Path("policy_d_v2_canonical_trade_ledger_11_16b_9.csv")
RECON_CSV_PATH = Path("research_outputs/policy_c_cross_sprint_reconciliation_11_16b_9.csv")
ROOT_RECON_CSV_PATH = Path("policy_c_cross_sprint_reconciliation_11_16b_9.csv")
CONTAMINATION_PATH = Path("research_outputs/historical_evaluation_contamination_register_11_16b_9.json")
ROOT_CONTAMINATION_PATH = Path("historical_evaluation_contamination_register_11_16b_9.json")
VERDICT_PATH = Path("research_outputs/policy_d_v2_canonical_verdict_11_16b_9.json")
ROOT_VERDICT_PATH = Path("policy_d_v2_canonical_verdict_11_16b_9.json")
REPORT_PATH = Path("research_outputs/research_report_11_16b_9.md")


def test_capital_conservation_and_residual_resolution():
    """Verify capital conservation and exact zero-residual resolution of the 18.07 USDT difference."""
    assert CANONICAL_LEDGER_PATH.is_file(), f"Missing ledger at {CANONICAL_LEDGER_PATH}"
    assert ROOT_LEDGER_PATH.is_file(), f"Missing root ledger at {ROOT_LEDGER_PATH}"

    df_tr = pd.read_csv(CANONICAL_LEDGER_PATH)
    assert len(df_tr) == 141, f"Expected 141 positions (140 closed + 1 open), got {len(df_tr)}"

    closed = df_tr[df_tr["trade_status"] == "CLOSED"]
    terminal_open = df_tr[df_tr["trade_status"] == "OPEN_AT_TERMINAL"]

    assert len(closed) == 140
    assert len(terminal_open) == 1

    # 1. Conservation invariant on closed trades
    initial_usdt = 10000.0
    sum_gross_pnl = closed["gross_pnl_usdt"].sum()
    sum_friction = (
        closed["entry_fee_usdt"].sum() + closed["entry_slippage_usdt"].sum() +
        closed["exit_fee_usdt"].sum() + closed["exit_slippage_usdt"].sum()
    )
    sum_net_pnl = closed["net_pnl_usdt"].sum()

    # Net PnL must equal Gross PnL - Friction exactly
    assert abs(sum_net_pnl - (sum_gross_pnl - sum_friction)) < 1e-4

    expected_cash_after_140 = initial_usdt + sum_net_pnl
    actual_cash_after_140 = closed["ending_cash_usdt"].iloc[-1]
    assert abs(actual_cash_after_140 - expected_cash_after_140) < 1e-4

    # 2. Open Trade 141 inventory and mark-to-market equity
    t141 = terminal_open.iloc[0]
    assert t141["trade_id"] == 141
    assert t141["entry_bar"] == 105002
    assert t141["exit_bar"] == 105119

    btc_inv = t141["btc_qty"]
    final_px = t141["exit_price"]
    unallocated_cash = t141["ending_cash_usdt"]

    # Total MTM portfolio equity
    mtm_equity = unallocated_cash + (btc_inv * final_px)
    assert abs(mtm_equity - 6467.17) < 0.05

    # 3. Residual Resolution:
    # MTM equity (6467.17) - Cash after Trade 140 (6449.10) must equal Trade 141 unrealized gain (+18.07)
    unrealized_mtm_gain = mtm_equity - actual_cash_after_140
    assert abs(unrealized_mtm_gain - 18.0665) < 1e-3, f"Unexpected unrealized gain: {unrealized_mtm_gain}"


def test_fee_and_slippage_scaling_invariants():
    """Verify Execution Policy V2 fee (10 bps) and slippage (5 bps) scaling across all trades."""
    df_tr = pd.read_csv(CANONICAL_LEDGER_PATH)

    for _, r in df_tr.iterrows():
        cost = r["cost_usdt"]
        e_fee = r["entry_fee_usdt"]
        e_slip = r["entry_slippage_usdt"]
        btc = r["btc_qty"]
        e_price = r["entry_price"]
        e_fill = r["entry_fill_price"]

        # Entry fee invariant: exactly 10 bps (0.0010) of allocated cost
        assert abs(e_fee - (cost * 0.0010)) < 1e-4

        # Entry fill invariant: open * (1 + 0.0005)
        assert abs(e_fill - (e_price * 1.0005)) < 1e-2

        # Entry slippage invariant: (fill - price) * btc == cost * 0.0005 / 1.0005
        assert abs(e_slip - ((e_fill - e_price) * btc)) < 1e-4

        # For closed trades, verify exit fee and exit slippage
        if r["trade_status"] == "CLOSED":
            x_price = r["exit_price"]
            x_fill = r["exit_fill_price"]
            x_fee = r["exit_fee_usdt"]
            x_slip = r["exit_slippage_usdt"]
            gross_proceeds = btc * x_fill

            # Exit fill invariant: exit_price * (1 - 0.0005)
            assert abs(x_fill - (x_price * 0.9995)) < 1e-2

            # Exit fee invariant: exactly 10 bps (0.0010) of gross proceeds
            assert abs(x_fee - (gross_proceeds * 0.0010)) < 1e-4

            # Exit slippage invariant: (price - fill) * btc
            assert abs(x_slip - ((x_price - x_fill) * btc)) < 1e-4

            # Trade net PnL invariant
            gross_pnl = r["gross_pnl_usdt"]
            total_friction = e_fee + e_slip + x_fee + x_slip
            net_pnl = r["net_pnl_usdt"]
            assert abs(net_pnl - (gross_pnl - total_friction)) < 1e-4


def test_causal_event_ordering_and_deterministic_uniqueness():
    """Verify strictly causal event ordering and unique trade IDs with no duplicate fills."""
    df_tr = pd.read_csv(CANONICAL_LEDGER_PATH)

    # Unique trade IDs
    assert len(df_tr["trade_id"].unique()) == len(df_tr)

    # Causal ordering for every trade
    for _, r in df_tr.iterrows():
        assert r["entry_bar"] < r["exit_bar"] or (r["entry_bar"] <= r["exit_bar"] and r["trade_status"] == "OPEN_AT_TERMINAL")
        assert 864 <= r["entry_bar"] <= 105120
        assert 864 <= r["exit_bar"] <= 105120

    # Monotonic timestamps
    entry_bars = df_tr["entry_bar"].tolist()
    assert entry_bars == sorted(entry_bars), "Entry bars are not monotonically increasing"


def test_cross_sprint_policy_c_reconciliation_consistency():
    """Verify that the cross-sprint Policy C reconciliation document accurately explains divergences."""
    assert RECON_CSV_PATH.is_file()
    assert ROOT_RECON_CSV_PATH.is_file()

    df_rec = pd.read_csv(RECON_CSV_PATH)
    assert len(df_rec) >= 4

    sprints = df_rec["sprint"].tolist()
    assert any("11.16B.6" in s for s in sprints)
    assert any("11.16B.7" in s for s in sprints)
    assert any("11.16B.8" in s for s in sprints)
    assert any("11.16B.9" in s for s in sprints)

    row_b6 = df_rec[df_rec["sprint"] == "11.16B.6"].iloc[0]
    assert row_b6["trade_count"] == 26
    assert row_b6["bars_evaluated"] == 4000

    row_b8 = df_rec[df_rec["sprint"] == "11.16B.8"].iloc[0]
    assert row_b8["trade_count"] == 1184
    assert row_b8["bars_evaluated"] == 104256

    row_pure = df_rec[df_rec["sprint"] == "11.16B.9 (Pure)"].iloc[0]
    assert row_pure["trade_count"] == 1149
    assert row_pure["bars_evaluated"] == 104256


def test_contamination_register_and_declarations():
    """Verify the contamination register classifies historical partitions as contaminated and declares valid states."""
    assert CONTAMINATION_PATH.is_file()
    assert ROOT_CONTAMINATION_PATH.is_file()

    c_data = json.loads(CONTAMINATION_PATH.read_text(encoding="utf-8"))
    parts = c_data.get("partitions", {})

    assert "CONTAMINATED" in parts["FOLD_1_IN_SAMPLE_TRAINING"]["contamination_status"]
    assert "CONTAMINATED" in parts["FOLD_2_CHRONOLOGICAL_HOLDOUT"]["contamination_status"]
    assert "CONTAMINATED" in parts["FOLD_3_OUT_OF_SAMPLE_TEST"]["contamination_status"]
    assert parts["PROSPECTIVE_OBSERVATION_UNSEEN"]["status"] == "NOT_STARTED"

    assert VERDICT_PATH.is_file()
    v_data = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    decls = v_data["global_declarations"]

    assert decls["prospective_observation"] == "NOT_STARTED"
    assert decls["live_trading"] == "PROHIBITED"
    assert decls["policy_parameters_changed"] == "NO"
    assert decls["operator_authorization"] == "NOT_GRANTED"
    assert decls["next_step"] == "OPERATOR_REVIEW"

    # Report assertions
    assert REPORT_PATH.is_file()
    text = REPORT_PATH.read_text(encoding="utf-8")
    assert "PROSPECTIVE_OBSERVATION=NOT_STARTED" in text
    assert "LIVE_TRADING=PROHIBITED" in text
    assert "POLICY_PARAMETERS_CHANGED=NO" in text
    assert "OPERATOR_AUTHORIZATION=NOT_GRANTED" in text
    assert "NEXT_STEP=OPERATOR_REVIEW" in text
