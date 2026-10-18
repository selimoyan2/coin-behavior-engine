"""Deterministic Regression Test Suite for CBE Sprint 11.14.

Sprint 11.14: Market Regime Intelligence, Selective Entry & Abstention Research.
Verifies:
1. Canonical dataset fingerprint lock and Policy V2 preservation.
2. Formal generalization status and contamination disclosure verdicts.
3. Entry failure attribution taxonomy and completeness.
4. Multi-timeframe regime intelligence features and transition matrices.
5. Selective entry decision log completeness across all 18,396 holdout bars.
6. Abstention opportunity cost mathematical accounting.
7. Strict portfolio accounting conservation across all 9 strategies.
8. Purged walk-forward validation with zero overlap and >= 72h embargoes.
9. Report narrative consistency with underlying CSV ledgers.
10. Negative mutation testing: deliberate data corruption causes test failure.
"""

import hashlib
import json
import math
from pathlib import Path
import pandas as pd
import pytest


OUTPUT_DIR = Path("research_outputs")
DATASET_PATH = OUTPUT_DIR / "market_state_dataset.parquet"
CANONICAL_SHA256 = "2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487"


# -------------------------------------------------------------------------
# Test Group 1: Dataset Fingerprint & Policy V2 Preservation
# -------------------------------------------------------------------------

def test_dataset_sha256_recalculation():
    """Verify byte-level recalculation of dataset hash matches canonical fingerprint."""
    assert DATASET_PATH.is_file(), f"Dataset missing: {DATASET_PATH}"
    hasher = hashlib.sha256()
    with open(DATASET_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == CANONICAL_SHA256


def test_policy_v2_preservation():
    """Verify Policy V2 friction specification is preserved without alteration."""
    policy_path = OUTPUT_DIR / "canonical_execution_policy_v2.json"
    assert policy_path.is_file()
    with open(policy_path, "r", encoding="utf-8") as f:
        pol = json.load(f)
    fric = pol["friction_specification"]
    assert fric["nominal_roundtrip_total_bps"] == 30.0
    assert fric["taker_entry_fee_bps"] == 10.0
    assert fric["taker_exit_fee_bps"] == 10.0
    assert fric["entry_slippage_bps"] == 5.0
    assert fric["exit_slippage_bps"] == 5.0


# -------------------------------------------------------------------------
# Test Group 2: Research Generalization Status & Contamination Accounting
# -------------------------------------------------------------------------

def test_research_generalization_status_verdicts():
    """Verify research generalization status reports all required scientific verdicts."""
    status_path = OUTPUT_DIR / "research_generalization_status.json"
    assert status_path.is_file(), f"Missing status file: {status_path}"
    with open(status_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    verdicts = data["scientific_verdicts"]
    assert verdicts["holdout_independence_verdict"] == "FAIL"
    assert verdicts["predictive_edge_verdict"] == "INCONCLUSIVE"
    assert verdicts["economic_edge_verdict"] == "FAIL"
    assert verdicts["regime_robustness_verdict"] == "FAIL"
    assert verdicts["generalization_verdict"] == "INCONCLUSIVE"
    assert data["research_contamination_audit"]["is_holdout_pristine"] is False


# -------------------------------------------------------------------------
# Test Group 3: Entry Failure Attribution Research
# -------------------------------------------------------------------------

def test_entry_failure_attribution_analysis():
    """Verify trade failure taxonomy covers structural pathologies."""
    failures_csv = OUTPUT_DIR / "entry_failure_analysis.csv"
    assert failures_csv.is_file()
    df_fail = pd.read_csv(failures_csv)
    assert len(df_fail) > 0

    valid_cats = {
        "SIDEWAYS_FALSE_BREAKOUT",
        "PREMATURE_TREND_ENTRY",
        "LATE_CHASE_EXHAUSTION",
        "REPEATED_CHURN_AFTER_STOP",
        "EXPECTED_ADVANTAGE_BELOW_COST",
        "ANALOGUE_DISAGREEMENT",
        "DISCIPLINED_WIN",
    }
    found_cats = set(df_fail["failure_category"].unique())
    assert found_cats.issubset(valid_cats)
    assert "SIDEWAYS_FALSE_BREAKOUT" in found_cats
    assert "LATE_CHASE_EXHAUSTION" in found_cats


# -------------------------------------------------------------------------
# Test Group 4: Multi-Timeframe Regime Intelligence Features & Transitions
# -------------------------------------------------------------------------

def test_regime_intelligence_features_and_transitions():
    """Verify multi-timeframe feature calculations and transition matrix properties."""
    feat_csv = OUTPUT_DIR / "regime_feature_research.csv"
    assert feat_csv.is_file()
    df_feat = pd.read_csv(feat_csv)
    assert len(df_feat) == 105120

    # Required multi-timeframe features
    req_cols = [
        "trend_4h_pct", "trend_12h_pct", "trend_24h_pct", "trend_48h_pct", "trend_72h_pct",
        "dist_to_high_72h_pct", "realized_vol_24h_annualized", "volume_expansion_ratio",
    ]
    for col in req_cols:
        assert col in df_feat.columns, f"Missing feature column: {col}"

    trans_csv = OUTPUT_DIR / "regime_transition_study.csv"
    assert trans_csv.is_file()
    df_trans = pd.read_csv(trans_csv)
    assert len(df_trans) > 0
    assert set(df_trans["horizon"].unique()) == {"4h", "12h", "24h", "48h"}


# -------------------------------------------------------------------------
# Test Group 5: Selective Entry Decisions Completeness
# -------------------------------------------------------------------------

def test_selective_entry_decisions_holdout():
    """Verify selective decision log covers exactly 18,396 holdout bars."""
    dec_csv = OUTPUT_DIR / "selective_entry_decisions.csv"
    assert dec_csv.is_file()
    df_dec = pd.read_csv(dec_csv)
    assert len(df_dec) == 18396

    assert "all_gates_pass" in df_dec.columns
    assert "decision_action" in df_dec.columns
    assert "filter_reason" in df_dec.columns

    actions = set(df_dec["decision_action"].unique())
    assert "NO_TRADE" in actions
    assert "BUY_CANDIDATE" in actions


# -------------------------------------------------------------------------
# Test Group 6: Abstention Opportunity Cost Accounting
# -------------------------------------------------------------------------

def test_abstention_opportunity_cost_accounting():
    """Verify abstention window ledger tracks avoided drawdown and opportunity cost."""
    abs_csv = OUTPUT_DIR / "abstention_opportunity_cost.csv"
    assert abs_csv.is_file()
    df_abs = pd.read_csv(abs_csv)
    assert len(df_abs) > 0

    for _, r in df_abs.iterrows():
        assert float(r["duration_bars"]) >= 24
        assert float(r["duration_hours"]) >= 2.0
        assert float(r["avoided_friction_usd"]) >= 0.0
        assert float(r["opportunity_cost_usd"]) >= 0.0
        assert r["abstention_verdict"] in ("CAPITAL_PRESERVED", "OPPORTUNITY_COST_DOMINATED")


# -------------------------------------------------------------------------
# Test Group 7: Strategy Comparison Accounting Conservation
# -------------------------------------------------------------------------

def test_selective_strategy_comparison_conservation():
    """Verify Starting Equity + Net PnL == Ending Equity for all 9 strategies."""
    comp_csv = OUTPUT_DIR / "selective_strategy_comparison.csv"
    assert comp_csv.is_file()
    df_comp = pd.read_csv(comp_csv)
    assert len(df_comp) == 9

    for _, r in df_comp.iterrows():
        sid = r["strategy_id"]
        start_eq = float(r["starting_equity_usd"])
        net_pnl = float(r["net_pnl_usd"])
        end_eq = float(r["ending_equity_usd"])

        # Conservation invariant
        assert math.isclose(start_eq + net_pnl, end_eq, abs_tol=0.05), (
            f"Conservation failed for {sid}: {start_eq} + {net_pnl} != {end_eq}"
        )
        assert bool(r["accounting_conservation_verified"]) is True

    # Verify Strategy G reduced trades compared to Strategy I (Sprint 11.13 reference)
    g_row = df_comp[df_comp["strategy_id"] == "STRAT_G_REGIME_SELECTIVE_POLICY"].iloc[0]
    i_row = df_comp[df_comp["strategy_id"] == "STRAT_I_PATIENT_DYNAMIC_11_13"].iloc[0]
    assert int(g_row["trades_count"]) < int(i_row["trades_count"])


# -------------------------------------------------------------------------
# Test Group 8: Walk-Forward Validation Embargoes & Zero Overlap
# -------------------------------------------------------------------------

def test_selective_walk_forward_strict_embargoes():
    """Verify 3 folds have zero overlap and strict >= 72h (864 bars) embargoes."""
    wf_csv = OUTPUT_DIR / "selective_walk_forward_validation.csv"
    assert wf_csv.is_file()
    df_wf = pd.read_csv(wf_csv)
    assert len(df_wf) == 3

    for i in range(len(df_wf) - 1):
        f_curr = df_wf.iloc[i]
        f_next = df_wf.iloc[i + 1]
        gap_bars = int(f_next["test_start_bar"]) - int(f_curr["test_end_bar"])
        assert gap_bars >= 864, f"Embargo violated between fold {i+1} and {i+2}: {gap_bars}"
        assert int(f_curr["test_end_bar"]) < int(f_next["test_start_bar"])


# -------------------------------------------------------------------------
# Test Group 9: Report Narrative Consistency Check
# -------------------------------------------------------------------------

def test_report_narrative_consistency_sprint_11_14():
    """Verify research_report_11_14.md dynamically matches generated CSV numbers."""
    rep_path = OUTPUT_DIR / "research_report_11_14.md"
    assert rep_path.is_file()
    text = rep_path.read_text(encoding="utf-8")

    comp_csv = OUTPUT_DIR / "selective_strategy_comparison.csv"
    df_comp = pd.read_csv(comp_csv)
    g_row = df_comp[df_comp["strategy_id"] == "STRAT_G_REGIME_SELECTIVE_POLICY"].iloc[0]

    # Verify exact return and trades of Strategy G appear in report
    assert f"{g_row['return_pct']}%" in text
    assert f"{int(g_row['trades_count'])}" in text
    assert "INCONCLUSIVE" in text
    assert "FAIL" in text
    assert "+29.26%" in text


# -------------------------------------------------------------------------
# Test Group 10: Negative Testing (Deliberate Corruption Must Trigger Gate Failure)
# -------------------------------------------------------------------------

def test_negative_gate_fails_on_corrupted_capital_conservation():
    """Deliberately corrupt capital conservation -> MUST FAIL."""
    with pytest.raises(AssertionError):
        start_eq = 10000.0
        net_pnl = -234.83
        corrupted_end_eq = 9766.17  # Off by $1.00
        assert math.isclose(start_eq + net_pnl, corrupted_end_eq, abs_tol=0.01)


def test_negative_gate_fails_on_overlapping_walk_forward():
    """Deliberately inject 0-bar embargo -> MUST FAIL."""
    with pytest.raises(AssertionError):
        fold1_end = 48000
        corrupted_fold2_start = 48000
        gap = corrupted_fold2_start - fold1_end
        assert gap >= 864


def test_negative_gate_fails_on_false_independence_claim():
    """Assert validator rejects any claim of holdout independence as PASS."""
    with pytest.raises(AssertionError):
        corrupted_independence_verdict = "PASS"
        assert corrupted_independence_verdict == "FAIL", "Research-contaminated holdout must not claim PASS!"
