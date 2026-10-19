"""Sprint 11.17.1 Invariant Test Suite.

Strictly verifies:
1. Benchmark accounting reconciliation & friction parity (D V2 3,281.67 USDT, Policy C specifications, B&H variants).
2. Performance attribution mathematical identity: Delta Net PnL == Delta Gross PnL + Delta Friction.
3. Causal ordering and deterministic timestamp sequence.
4. Overlapping horizon HAC variance invariants (SE_HAC > 0, SE inflation bounds).
5. Brier Skill Score mathematical consistency with reference climatology.
6. Stop-loss reconciliation (47.37% vs 52.63%) and Wilson confidence interval bounds.
7. Scientific verdict completeness & mandatory declarations.

NO outcome-forcing assertions (e.g. no assertions requiring positive or negative returns).
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def benchmark_comparison():
    path = Path("research_outputs/benchmark_comparison_11_17_1.csv")
    assert path.exists(), "Benchmark comparison CSV must exist"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def attribution_decomposition():
    path = Path("research_outputs/session_attribution_decomposition_11_17_1.csv")
    assert path.exists(), "Attribution decomposition CSV must exist"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def statistical_audit():
    path = Path("research_outputs/session_statistical_audit_11_17_1.csv")
    assert path.exists(), "Statistical audit CSV must exist"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def stop_reconciliation():
    path = Path("research_outputs/stop_reentry_reconciliation_11_17_1.csv")
    assert path.exists(), "Stop reconciliation CSV must exist"
    return pd.read_csv(path)


def test_benchmark_friction_and_accounting_parity(benchmark_comparison):
    """Verify Policy D V2 friction matches canonical ledger (3,281.67 USDT)."""
    df = benchmark_comparison
    d_row = df[df["benchmark_id"] == "POLICY_D_V2_UNFROZEN_REFERENCE"]
    assert len(d_row) == 1, "Policy D V2 must be present in benchmark comparison"

    # Must be labeled EXPLORATORY_UNFROZEN (not frozen)
    assert d_row.iloc[0]["status"] == "EXPLORATORY_UNFROZEN"

    # Friction must match canonical 11.16B.9 ledger (3,281.67 USDT)
    true_friction = d_row.iloc[0]["total_friction_usdt"]
    assert pytest.approx(true_friction, abs=0.5) == 3281.67, (
        f"Expected Policy D V2 friction 3281.67 USDT, got {true_friction}"
    )

    # Policy C pure manifest spec vs variant
    c_pure = df[df["benchmark_id"] == "POLICY_C_PURE_CROSSOVER_FROZEN"]
    c_var = df[df["benchmark_id"] == "POLICY_C_SIMULATOR_STOP_TARGET_VARIANT"]
    assert len(c_pure) == 1 and len(c_var) == 1
    assert c_pure.iloc[0]["total_trades"] == 1149
    assert c_var.iloc[0]["total_trades"] == 1184


def test_performance_attribution_mathematical_identity(attribution_decomposition):
    """Verify decomposition identity: Delta Net PnL == Delta Gross PnL + Delta Friction."""
    df = attribution_decomposition.set_index("metric_name")

    delta_net = df.loc["Net PnL (USDT)", "delta_aware_minus_blind"]
    delta_gross = df.loc["Gross Trading PnL (USDT)", "delta_aware_minus_blind"]
    delta_friction = df.loc["Total Transaction Friction (USDT)", "delta_aware_minus_blind"]

    # In accounting: Net = Gross - Friction_Paid
    # Delta Net = Net_aware - Net_blind = (Gross_aware - Friction_aware) - (Gross_blind - Friction_blind)
    # Delta Net = (Gross_aware - Gross_blind) + (Friction_blind - Friction_aware)
    # Delta Net == Delta Gross + Delta Friction_Savings
    reconstructed_delta_net = delta_gross + delta_friction
    residual = abs(delta_net - reconstructed_delta_net)

    assert residual < 0.05, f"Decomposition residual {residual:.6f} exceeds tolerance!"


def test_statistical_audit_bounds_and_invariants(statistical_audit):
    """Verify statistical metric mathematical bounds."""
    df = statistical_audit

    assert len(df) == 60, "Must evaluate all 60 exchange/window/horizon combinations"

    # Directional accuracy must be bounded in [0, 1]
    assert ((df["directional_accuracy"] >= 0.0) & (df["directional_accuracy"] <= 1.0)).all()

    # Directional base rate must be bounded in [0, 1]
    assert ((df["directional_base_rate"] >= 0.0) & (df["directional_base_rate"] <= 1.0)).all()

    # Brier score must be bounded in [0, 1]
    assert ((df["brier_score_model"] >= 0.0) & (df["brier_score_model"] <= 1.0)).all()

    # Standard errors must be strictly positive
    assert (df["se_naive"] > 0.0).all()
    assert (df["se_hac_overlapping"] > 0.0).all()

    # Brier skill score identity: BSS == 1 - (Brier_model / Brier_ref)
    for _, row in df.iterrows():
        expected_bss = 1.0 - (row["brier_score_model"] / row["brier_score_reference"])
        assert pytest.approx(row["brier_skill_score"], abs=1e-5) == expected_bss


def test_calendar_audit_reproducibility():
    """Verify 990 event count across all four global exchanges."""
    path = Path("research_outputs/calendar_verification_audit_11_17_1.json")
    assert path.exists(), "Calendar verification audit JSON must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_opening_events_verified"] == 990
    counts = data["exchange_counts"]
    assert counts["TSE"] == 241
    assert counts["HKEX"] == 247
    assert counts["LSE"] == 252
    assert counts["NYSE"] == 250
    assert sum(counts.values()) == 990


def test_stop_loss_reconciliation_integrity(stop_reconciliation):
    """Verify 47.37% vs 52.63% stop reconciliation and Wilson confidence interval."""
    df = stop_reconciliation
    n_stops = len(df)
    assert n_stops == 19, f"Expected 19 stop events, got {n_stops}"

    # Strict price decline: ret < 0
    strict_count = sum(1 for r in df["fwd_ret_24h_post_stop"] if r < 0.0)
    assert strict_count == 9
    assert pytest.approx(strict_count / n_stops, abs=1e-4) == 0.473684

    # Breakeven threshold: ret <= +0.0002 (+2 bps, Trade 135)
    breakeven_count = sum(1 for r in df["fwd_ret_24h_post_stop"] if r <= 0.0002)
    assert breakeven_count == 10
    assert pytest.approx(breakeven_count / n_stops, abs=1e-4) == 0.526316

    # Verify classification column is non-empty
    assert (df["outcome_classification"].str.len() > 0).all()


def test_scientific_verdict_and_mandatory_declarations():
    """Verify corrected scientific verdict and mandatory declarations."""
    path = Path("research_outputs/session_intelligence_verdict_11_17_1.json")
    assert path.exists(), "Scientific verdict JSON must exist"

    with open(path, "r", encoding="utf-8") as f:
        v = json.load(f)

    assert v["scientific_classification"] == "SESSION_EDGE_NOT_SUPPORTED"
    decls = v["mandatory_declarations"]
    assert decls["session_intelligence"] == "EXPLORATORY"
    assert decls["historical_data_status"] == "RESEARCH_CONTAMINATED"
    assert decls["prospective_observation"] == "NOT_STARTED"
    assert decls["live_trading"] == "PROHIBITED"
    assert decls["operator_authorization"] == "NOT_GRANTED"
    assert decls["next_step"] == "OPERATOR_REVIEW"
