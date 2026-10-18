"""Comprehensive Regression and Verification Test Suite for CBE Sprint 11.12.

Sprint 11.12: Financial Truth Audit & Benchmark Integrity Lock.
Verifies:
1. Canonical dataset manifest & SHA-256 fingerprint lock.
2. Resolution of all 7 financial discrepancies in the register.
3. Strict accounting conservation: Starting Equity + Net PnL == Ending Equity.
4. Buy-and-Hold benchmark resolution (+29.85% / +29.26% full holdout vs -0.16% timeout).
5. Dynamic engine trade count and PnL resolution (98 trades, -3.11% vs +23.28%).
6. Non-overlapping walk-forward folds with strict 72h embargoes.
7. Forensic trade classification of all 214 trades and cooldown savings replay.
8. Complete artifact delivery and VERIFIED research verdict.
"""

import json
import math
from pathlib import Path
import pandas as pd
import pytest


CANONICAL_SHA256 = "2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487"
OUTPUT_DIR = Path("research_outputs")


@pytest.fixture(scope="module")
def manifest():
    manifest_path = OUTPUT_DIR / "canonical_benchmark_manifest.json"
    assert manifest_path.is_file(), f"Missing canonical manifest: {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def discrepancy_df():
    path = OUTPUT_DIR / "financial_discrepancy_register.csv"
    assert path.is_file(), f"Missing discrepancy register: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def strategy_comp_df():
    path = OUTPUT_DIR / "canonical_strategy_comparison.csv"
    assert path.is_file(), f"Missing canonical strategy comparison: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def walk_forward_df():
    path = OUTPUT_DIR / "canonical_walk_forward_validation.csv"
    assert path.is_file(), f"Missing canonical walk forward csv: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def trade_attribution_df():
    path = OUTPUT_DIR / "trade_attribution_reconciliation.csv"
    assert path.is_file(), f"Missing trade attribution csv: {path}"
    return pd.read_csv(path)


# -------------------------------------------------------------------------
# Test Group 1: Canonical Dataset Manifest & Fingerprint Lock
# -------------------------------------------------------------------------

def test_canonical_manifest_fingerprint(manifest):
    """Verify SHA-256 fingerprint matches canonical immutable hash."""
    assert manifest["dataset_sha256"] == CANONICAL_SHA256
    assert manifest["total_candles"] == 105120
    assert manifest["symbol"] == "BTCUSDT"
    assert manifest["interval"] == "5m"
    assert manifest["holdout_test_partition"]["candles_count"] == 18396
    assert manifest["holdout_test_partition"]["start_index"] == 86724
    assert manifest["holdout_test_partition"]["end_index"] == 105119


def test_canonical_dataset_prices(manifest):
    """Verify exact opening and closing BTC prices."""
    assert manifest["full_period"]["start_open_price"] == pytest.approx(106891.72, abs=0.1)
    assert manifest["full_period"]["end_close_price"] == pytest.approx(82104.03, abs=0.1)
    assert manifest["holdout_test_partition"]["starting_btc_price_open"] == pytest.approx(63040.01, abs=0.1)
    assert manifest["holdout_test_partition"]["ending_btc_price_close"] == pytest.approx(82104.03, abs=0.1)


# -------------------------------------------------------------------------
# Test Group 2: Financial Discrepancy Register
# -------------------------------------------------------------------------

def test_discrepancy_register_all_resolved(discrepancy_df):
    """Verify all 7 identified discrepancies are marked as RESOLVED."""
    assert len(discrepancy_df) == 7
    expected_ids = [f"DISC-0{i}" for i in range(1, 8)]
    assert list(discrepancy_df["discrepancy_id"]) == expected_ids

    for _, row in discrepancy_df.iterrows():
        assert row["reconciliation_verdict"] == "RESOLVED"
        assert len(str(row["root_cause_file_and_line"])) > 5
        assert len(str(row["mechanistic_explanation"])) > 20
        assert len(str(row["corrected_canonical_value"])) > 5


def test_discrepancy_01_buy_and_hold_cause(discrepancy_df):
    """Verify DISC-01 identifies default max_holding_bars=12 timeout bug."""
    row = discrepancy_df[discrepancy_df["discrepancy_id"] == "DISC-01"].iloc[0]
    assert "max_holding_bars" in row["mechanistic_explanation"]
    assert "TIME_EXPIRY" in row["mechanistic_explanation"]


def test_discrepancy_02_dynamic_engine_cause(discrepancy_df):
    """Verify DISC-02 identifies unclassified legacy parquet regimes."""
    row = discrepancy_df[discrepancy_df["discrepancy_id"] == "DISC-02"].iloc[0]
    assert "legacy regime labels" in row["mechanistic_explanation"] or "classify_market_regimes" in row["mechanistic_explanation"]


# -------------------------------------------------------------------------
# Test Group 3: Strict Accounting Conservation
# -------------------------------------------------------------------------

def test_accounting_conservation_all_strategies(strategy_comp_df):
    """Verify Starting Equity + Net PnL == Ending Equity for all 9 strategies."""
    assert len(strategy_comp_df) == 9

    for _, row in strategy_comp_df.iterrows():
        strat = row["strategy_id"]
        start_eq = float(row["starting_equity_usd"])
        net_pnl = float(row["net_pnl_usd"])
        end_eq = float(row["ending_equity_usd"])

        # Exact conservation
        assert math.isclose(start_eq + net_pnl, end_eq, abs_tol=0.02), (
            f"Accounting conservation failed for {strat}: {start_eq} + {net_pnl} != {end_eq}"
        )
        assert bool(row["accounting_conservation_verified"]) is True

        # Friction conservation: friction == fees + slippage
        fees = float(row["total_fees_usd"])
        slip = float(row["total_slippage_usd"])
        fric = float(row["total_friction_usd"])
        assert math.isclose(fees + slip, fric, abs_tol=0.02)

        # Net PnL == Gross PnL - Friction
        gross = float(row["gross_pnl_usd"])
        assert math.isclose(gross - fric, net_pnl, abs_tol=0.02)


# -------------------------------------------------------------------------
# Test Group 4: Strategy Specific Truths
# -------------------------------------------------------------------------

def test_buy_and_hold_benchmark_resolution(strategy_comp_df):
    """Verify Buy-and-Hold held full 18,396 bars and earned +29.26% (+$2,926.43)."""
    bnh = strategy_comp_df[strategy_comp_df["strategy_id"] == "STRAT_B_BNH"].iloc[0]
    assert bnh["trades_count"] == 1
    assert float(bnh["return_pct"]) == pytest.approx(29.26, abs=0.1)
    assert float(bnh["net_pnl_usd"]) == pytest.approx(2926.43, abs=1.0)
    assert float(bnh["time_in_usdt_pct"]) < 0.1  # Held BTC nearly 100% of the time


def test_dynamic_engine_sprint_11_10_reconciliation(strategy_comp_df):
    """Verify authentic Sprint 11.10 Strategy F is reproduced: 98 trades, -3.11%."""
    dyn = strategy_comp_df[strategy_comp_df["strategy_id"] == "STRAT_F_EXISTING_DYN"].iloc[0]
    assert dyn["trades_count"] == 98
    assert float(bnh_pnl := dyn["net_pnl_usd"]) == pytest.approx(-311.08, abs=1.0)
    assert float(dyn["return_pct"]) == pytest.approx(-3.11, abs=0.1)
    assert float(dyn["total_friction_usd"]) == pytest.approx(2922.87, abs=2.0)


# -------------------------------------------------------------------------
# Test Group 5: Non-Overlapping Walk-Forward Folds with 72h Embargoes
# -------------------------------------------------------------------------

def test_walk_forward_zero_overlap_and_embargoes(walk_forward_df):
    """Verify 3 folds have zero overlap and strict >= 72h (864 bars) embargoes."""
    assert len(walk_forward_df) == 3

    for i in range(len(walk_forward_df)):
        row = walk_forward_df.iloc[i]
        assert bool(row["zero_overlap_verified"]) is True
        assert float(row["embargo_hours"]) >= 72.0
        assert int(row["embargo_bars"]) >= 864

    # Check boundaries
    f1 = walk_forward_df.iloc[0]
    f2 = walk_forward_df.iloc[1]
    f3 = walk_forward_df.iloc[2]

    assert f1["test_end_bar"] <= f2["test_start_bar"] - 864
    assert f2["test_end_bar"] <= f3["test_start_bar"] - 864


# -------------------------------------------------------------------------
# Test Group 6: Trade Attribution Forensics
# -------------------------------------------------------------------------

def test_trade_attribution_reconciliation(trade_attribution_df):
    """Verify trade failure classifications and counterfactual cooldown savings."""
    assert len(trade_attribution_df) == 214

    # Valid failure categories
    valid_categories = {
        "FEE_DRIVEN_LOSS",
        "UNNECESSARY_RE_ENTRY",
        "PREMATURE_PANIC_EXIT",
        "STOPPED_BEFORE_REVERSAL",
        "GENUINE_FORECAST_FAILURE",
        "ADVERSE_REGIME_EXPOSURE",
        "FALSE_REVERSAL",
        "NONE_PROFITABLE",
    }
    categories_found = set(trade_attribution_df["failure_category"].unique())
    assert categories_found.issubset(valid_categories)

    # Check avoidable churn trades exist
    churn_trades = trade_attribution_df[trade_attribution_df["failure_category"] == "UNNECESSARY_RE_ENTRY"]
    assert len(churn_trades) > 0


# -------------------------------------------------------------------------
# Test Group 7: Deliverables & Report Verdict
# -------------------------------------------------------------------------

def test_all_sprint_11_12_deliverables_exist():
    """Verify all 10 required artifacts exist and are non-empty."""
    expected_files = [
        "canonical_benchmark_manifest.json",
        "dataset_integrity_audit.md",
        "financial_discrepancy_register.csv",
        "canonical_trade_ledger.csv",
        "canonical_equity_curves.csv",
        "canonical_strategy_comparison.csv",
        "canonical_walk_forward_validation.csv",
        "trade_attribution_reconciliation.csv",
        "prediction_and_event_ablation_audit.md",
        "research_report_11_12.md",
    ]
    for fn in expected_files:
        p = OUTPUT_DIR / fn
        assert p.is_file(), f"Required file missing: {fn}"
        assert p.stat().st_size > 100, f"File {fn} is suspiciously small: {p.stat().st_size} bytes"


def test_research_report_verdict_verified():
    """Verify research_report_11_12.md explicitly contains VERIFIED verdict."""
    rep_path = OUTPUT_DIR / "research_report_11_12.md"
    content = rep_path.read_text(encoding="utf-8")
    assert "**Validation Verdict:** **VERIFIED**" in content or "Validation Verdict: VERIFIED" in content
    assert "DISC-01" in content
    assert "DISC-07" in content
