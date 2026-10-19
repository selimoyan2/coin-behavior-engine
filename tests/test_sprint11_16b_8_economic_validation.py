"""Comprehensive test suite for Sprint 11.16B.8: Independent ATR Recalculation & Policy D V2 Economic Validation.

Verifies:
1. Pure independent recalculation of moving averages, True Range, ATR, and gate intersections from raw market data.
2. Distinct statistical distributions of 24h rolling annualized volatility vs 5m ATR percentage.
3. Trade ledger accounting, conservation invariants, 30 bps roundtrip friction audit, and negative expectancy.
4. Chronological walk-forward consistency across Train, Holdout, and Test partitions.
5. Analogue incremental-value feasibility (zero trades meeting 0.60 hurdle, no incremental alpha).
6. Scientific verdict JSON and mandatory operational declarations.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

DATASET_PATH = Path("research_outputs/market_state_dataset.parquet")
LEDGER_PATH = Path("research_outputs/policy_d_v2_trade_ledger_11_16b_8.csv")
ROOT_LEDGER_PATH = Path("policy_d_v2_trade_ledger_11_16b_8.csv")
WALK_FORWARD_PATH = Path("research_outputs/walk_forward_evaluation_11_16b_8.csv")
ROOT_WALK_FORWARD_PATH = Path("walk_forward_evaluation_11_16b_8.csv")
ANALOGUE_FEASIBILITY_PATH = Path("research_outputs/policy_e_v2_feasibility_analysis_11_16b_8.csv")
ROOT_ANALOGUE_FEASIBILITY_PATH = Path("policy_e_v2_feasibility_analysis_11_16b_8.csv")
ANALOGUE_VERDICT_PATH = Path("research_outputs/policy_e_v2_feasibility_verdict_11_16b_8.json")
SCIENTIFIC_VERDICT_PATH = Path("research_outputs/policy_d_v2_scientific_verdict_11_16b_8.json")
ROOT_SCIENTIFIC_VERDICT_PATH = Path("policy_d_v2_scientific_verdict_11_16b_8.json")
REPORT_PATH = Path("research_outputs/research_report_11_16b_8.md")


def test_independent_gate_recalculation_matches_exact_counts():
    """Verify that recalculating all gates independently from raw OHLCV reproduces Sprint 11.16B.7 counts."""
    assert DATASET_PATH.is_file(), f"Dataset missing: {DATASET_PATH}"
    df = pd.read_parquet(DATASET_PATH)
    n = len(df)
    assert n == 105120

    c = df["close"].values
    h = df["high"].values
    l = df["low"].values

    # Moving averages
    sma_288 = pd.Series(c).rolling(288).mean().values
    sma_864 = pd.Series(c).rolling(864).mean().values

    # 14-bar True Range & ATR
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr_14 = pd.Series(tr).rolling(14).mean().values
    atr_pct = atr_14 / c

    warmup = 864
    valid_slice = slice(warmup, n)

    trend_aligned = (c[valid_slice] > sma_288[valid_slice]) & (c[valid_slice] > sma_864[valid_slice])
    anti_chase = c[valid_slice] <= (sma_288[valid_slice] * 1.0225)
    struct_eligible = trend_aligned & anti_chase
    frozen_atr = (atr_pct[valid_slice] >= 0.015) & (atr_pct[valid_slice] <= 0.065)
    combined_d_frozen = struct_eligible & frozen_atr

    corrected_atr = (atr_pct[valid_slice] >= 0.0005) & (atr_pct[valid_slice] <= 0.0035)
    combined_d_corrected = struct_eligible & corrected_atr

    assert len(c[valid_slice]) == 104256
    assert int(trend_aligned.sum()) == 38569
    assert int(anti_chase.sum()) == 100330
    assert int(struct_eligible.sum()) == 34813
    assert int(frozen_atr.sum()) == 4
    assert int(combined_d_frozen.sum()) == 0
    assert int(corrected_atr.sum()) == 89675
    assert int(combined_d_corrected.sum()) == 31092


def test_volatility_measures_statistical_separation():
    """Verify that 24h rolling annualized volatility and 5m ATR percentage are distinct non-interchangeable measures."""
    assert SCIENTIFIC_VERDICT_PATH.is_file()
    data = json.loads(SCIENTIFIC_VERDICT_PATH.read_text(encoding="utf-8"))
    vol_comp = data["volatility_definition_comparison"]

    v24 = vol_comp["vol_24h_annualized_log_ret"]
    a5m = vol_comp["atr_5m_fraction"]

    # vol_24h is in percent per annum (~41% mean)
    assert 35.0 <= v24["mean"] <= 45.0
    assert 30.0 <= v24["median"] <= 45.0

    # atr_5m is in fraction per 5m bar (~0.0016 mean)
    assert 0.0010 <= a5m["mean"] <= 0.0020
    assert 0.0010 <= a5m["median"] <= 0.0018

    # Non-interchangeable
    assert vol_comp["mathematical_interchangeability"] == "FALSE_DIFFERENT_UNITS_AND_HORIZONS"


def test_policy_d_v2_trade_ledger_and_accounting_integrity():
    """Verify Policy D V2 trade ledger accounting, friction reconciliation, and negative expectancy."""
    assert LEDGER_PATH.is_file()
    assert ROOT_LEDGER_PATH.is_file()

    df_tr = pd.read_csv(LEDGER_PATH)
    assert len(df_tr) == 140, f"Expected 140 trades, found {len(df_tr)}"

    # Check columns
    required_cols = [
        "trade_id", "entry_bar", "entry_price", "entry_fill_price", "btc_qty",
        "cost_usdt", "entry_fee_usdt", "entry_slippage_usdt", "exit_bar",
        "exit_price", "exit_fill_price", "exit_reason", "exit_fee_usdt",
        "exit_slippage_usdt", "gross_pnl_usdt", "net_pnl_usdt", "holding_bars",
        "ending_equity_usdt"
    ]
    for col in required_cols:
        assert col in df_tr.columns, f"Missing column {col} in trade ledger"

    # Check friction accounting for every single trade
    for _, row in df_tr.iterrows():
        total_friction = (
            row["entry_fee_usdt"] + row["entry_slippage_usdt"] +
            row["exit_fee_usdt"] + row["exit_slippage_usdt"]
        )
        calculated_net_pnl = row["gross_pnl_usdt"] - total_friction
        assert abs(row["net_pnl_usdt"] - calculated_net_pnl) < 1e-2, "PnL friction reconciliation mismatch"

    # Check overall strategy metrics
    total_net_pnl = df_tr["net_pnl_usdt"].sum()
    total_fees = df_tr["entry_fee_usdt"].sum() + df_tr["exit_fee_usdt"].sum()
    total_slip = df_tr["entry_slippage_usdt"].sum() + df_tr["exit_slippage_usdt"].sum()
    total_friction = total_fees + total_slip

    assert total_net_pnl < -3000.0, f"Expected severe loss, found {total_net_pnl}"
    assert total_friction > 3000.0, f"Expected >3000 USDT friction, found {total_friction}"

    # Win rate must be < 35%
    win_rate = (df_tr["net_pnl_usdt"] > 0).mean() * 100.0
    assert 20.0 <= win_rate <= 35.0, f"Unexpected win rate: {win_rate}"

    # Exits dominated by trend violations
    exits = df_tr["exit_reason"].value_counts()
    assert exits["TREND_VIOLATION"] > 100


def test_walk_forward_evaluation_matrix():
    """Verify walk-forward evaluation across partitions confirms persistent negative alpha."""
    assert WALK_FORWARD_PATH.is_file()
    assert ROOT_WALK_FORWARD_PATH.is_file()

    df_wf = pd.read_csv(WALK_FORWARD_PATH)
    assert len(df_wf) == 24  # 4 partitions x 6 policies

    partitions = set(df_wf["partition"].unique())
    assert partitions == {"FULL_CANONICAL", "FOLD_1_TRAIN", "FOLD_2_HOLDOUT", "FOLD_3_TEST"}

    # Policy A must always be 0.00% return
    df_a = df_wf[df_wf["policy_id"] == "POLICY_A_USDT_CASH"]
    assert (df_a["net_return_pct"] == 0.0).all()

    # Policy D V2 must be negative in all partitions
    df_d2 = df_wf[df_wf["policy_id"] == "POLICY_D_V2_CORRECTED_ATR"]
    assert (df_d2["net_return_pct"] <= 0.0).all(), "Policy D V2 unexpectedly positive in a partition"

    # Full canonical return must match -35.33%
    full_d2 = df_d2[df_d2["partition"] == "FULL_CANONICAL"].iloc[0]
    assert abs(full_d2["net_return_pct"] - (-35.33)) < 0.5


def test_analogue_feasibility_zero_alpha():
    """Verify that analogue filter with frozen 0.60 hurdle yields 0 trades and adds no incremental alpha."""
    assert ANALOGUE_FEASIBILITY_PATH.is_file()
    assert ANALOGUE_VERDICT_PATH.is_file()

    df_ana = pd.read_csv(ANALOGUE_FEASIBILITY_PATH)
    assert len(df_ana) == 140

    # 0 trades can pass the frozen 0.60 hurdle
    assert df_ana["passed_hurdle_60"].sum() == 0

    verdict_data = json.loads(ANALOGUE_VERDICT_PATH.read_text(encoding="utf-8"))
    assert verdict_data["incremental_alpha_demonstrated"] is False
    assert verdict_data["policy_e_v2_status"] == "EXPLORATORY_REJECTED_NO_ALPHA"


def test_scientific_verdict_and_mandatory_declarations():
    """Verify final scientific verdict rejects Policy D V2 and declares mandatory operational states."""
    assert SCIENTIFIC_VERDICT_PATH.is_file()
    assert ROOT_SCIENTIFIC_VERDICT_PATH.is_file()

    verdict_data = json.loads(SCIENTIFIC_VERDICT_PATH.read_text(encoding="utf-8"))
    decls = verdict_data["global_declarations"]

    assert decls["policy_d_v2_status"] == "EXPLORATORY_UNFROZEN"
    assert decls["prospective_observation"] == "NOT_STARTED"
    assert decls["live_trading"] == "PROHIBITED"
    assert decls["operator_authorization"] == "NOT_GRANTED"
    assert decls["next_step"] == "OPERATOR_REVIEW"

    sci_verdict = verdict_data["scientific_economic_verdict"]
    assert sci_verdict["verdict"] == "ECONOMIC_VALIDATION_FAILED"
    assert sci_verdict["prospective_readiness"] == "REJECTED_FOR_PROSPECTIVE_OBSERVATION"

    # Also verify research report contains required declarations
    assert REPORT_PATH.is_file()
    rep_text = REPORT_PATH.read_text(encoding="utf-8")
    assert "POLICY_D_V2_STATUS=EXPLORATORY_UNFROZEN" in rep_text
    assert "PROSPECTIVE_OBSERVATION=NOT_STARTED" in rep_text
    assert "LIVE_TRADING=PROHIBITED" in rep_text
    assert "OPERATOR_AUTHORIZATION=NOT_GRANTED" in rep_text
    assert "NEXT_STEP=OPERATOR_REVIEW" in rep_text
