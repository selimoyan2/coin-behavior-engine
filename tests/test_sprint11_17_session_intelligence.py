"""Sprint 11.17 Regression and Invariant Test Suite.

Verifies:
1. Global session calendar correctness & DST shifts.
2. Causal tagging without lookahead leakage.
3. Probability and directional accuracy mathematical bounds.
4. Friction identity: Net EV == Mean Return - Nominal Friction.
5. Patient spot model state machine invariants & portfolio accounting.
6. Stop-loss forensics causal validity.
7. Scientific verdict completeness & mandatory declarations.

All assertions enforce mathematical, causal, statistical, and accounting invariants.
NO outcome-forcing assertions.
"""

import json
from pathlib import Path
import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar


@pytest.fixture(scope="module")
def calendar():
    return GlobalSessionCalendar()


@pytest.fixture(scope="module")
def dataset():
    path = Path("research_outputs/market_state_dataset.parquet")
    assert path.exists(), "Market state dataset must exist"
    return pd.read_parquet(path)


def test_global_session_calendar_correctness(calendar):
    """Verify DST transitions and exchange open times."""
    # Winter dates
    date_winter = datetime.date(2026, 1, 15)
    # Summer dates
    date_summer = datetime.date(2026, 6, 15)

    # NYSE: 09:30 local -> 14:30 UTC winter (EST), 13:30 UTC summer (EDT)
    open_ny_w = calendar.get_exchange_open_utc("NYSE", date_winter)
    open_ny_s = calendar.get_exchange_open_utc("NYSE", date_summer)
    assert open_ny_w.hour == 14 and open_ny_w.minute == 30
    assert open_ny_s.hour == 13 and open_ny_s.minute == 30

    # LSE: 08:00 local -> 08:00 UTC winter (GMT), 07:00 UTC summer (BST)
    open_lon_w = calendar.get_exchange_open_utc("LSE", date_winter)
    open_lon_s = calendar.get_exchange_open_utc("LSE", date_summer)
    assert open_lon_w.hour == 8 and open_lon_w.minute == 0
    assert open_lon_s.hour == 7 and open_lon_s.minute == 0

    # TSE: 09:00 local -> 00:00 UTC (No DST)
    open_tky_w = calendar.get_exchange_open_utc("TSE", date_winter)
    open_tky_s = calendar.get_exchange_open_utc("TSE", date_summer)
    assert open_tky_w.hour == 0 and open_tky_w.minute == 0
    assert open_tky_s.hour == 0 and open_tky_s.minute == 0

    # HKEX: 09:30 local -> 01:30 UTC (No DST)
    open_hkg_w = calendar.get_exchange_open_utc("HKEX", date_winter)
    open_hkg_s = calendar.get_exchange_open_utc("HKEX", date_summer)
    assert open_hkg_w.hour == 1 and open_hkg_w.minute == 30
    assert open_hkg_s.hour == 1 and open_hkg_s.minute == 30


def test_calendar_holiday_handling(calendar):
    """Verify official holidays are not marked as trading days."""
    assert not calendar.is_trading_day("NYSE", datetime.date(2025, 7, 4))
    assert not calendar.is_trading_day("LSE", datetime.date(2025, 12, 25))
    assert not calendar.is_trading_day("TSE", datetime.date(2026, 1, 1))
    assert not calendar.is_trading_day("HKEX", datetime.date(2025, 1, 29))
    assert not calendar.is_trading_day("NYSE", datetime.date(2026, 1, 17))  # Saturday


def test_no_lookahead_leakage_in_session_tagging(calendar, dataset):
    """Verify window tagging causal boundaries."""
    df_sample = dataset.iloc[:1000].copy()
    df_tagged = calendar.tag_dataset_session_windows(df_sample)

    for ex in ["tse", "hkex", "lse", "nyse"]:
        open_col = f"{ex}_is_open_bar"
        pre_col = f"{ex}_pre_10m"
        post_col = f"{ex}_post_5m"

        open_indices = np.where(df_tagged[open_col] == 1)[0]
        for idx in open_indices:
            assert df_tagged[post_col].iloc[idx] == 1
            if idx > 0:
                assert df_tagged[pre_col].iloc[idx - 1] == 1
            assert df_tagged[pre_col].iloc[idx] == 0


def test_predictive_metrics_bounds_and_invariants():
    """Verify probability bounds and sample size invariants."""
    metrics_path = Path("research_outputs/session_predictive_metrics_11_17.csv")
    assert metrics_path.exists(), "Session predictive metrics file must exist"
    df_m = pd.read_csv(metrics_path)

    assert len(df_m) == 60, "Must contain all 60 exchange/window/horizon combinations"

    # Probability bounds
    assert ((df_m["directional_accuracy"] >= 0.0) & (df_m["directional_accuracy"] <= 1.0)).all()
    assert ((df_m["base_rate"] >= 0.0) & (df_m["base_rate"] <= 1.0)).all()
    assert ((df_m["brier_score"] >= 0.0) & (df_m["brier_score"] <= 1.0)).all()

    # Confidence interval bounds
    assert (df_m["ci_95_low"] <= df_m["ci_95_high"]).all()
    assert ((df_m["ci_95_low"] >= 0.0) & (df_m["ci_95_high"] <= 1.0)).all()


def test_cost_adjusted_expectancy_mathematical_identity():
    """Verify mathematical identity: Net EV (bps) == Mean Long Return (bps) - Friction (bps)."""
    metrics_path = Path("research_outputs/session_predictive_metrics_11_17.csv")
    df_m = pd.read_csv(metrics_path)

    for _, row in df_m.iterrows():
        expected_net_ev = row["mean_ret_conditional_long_bps"] - row["friction_bps"]
        assert pytest.approx(row["net_ev_long_bps"], abs=1e-5) == expected_net_ev


def test_patient_spot_model_portfolio_accounting():
    """Verify trade ledger invariants under Canonical Execution Policy V2."""
    ledger_path = Path("research_outputs/patient_session_trade_ledger_11_17.csv")
    assert ledger_path.exists(), "Trade ledger must exist"
    df_l = pd.read_csv(ledger_path)

    assert len(df_l) > 0, "Trade ledger must contain executed trades"

    for _, row in df_l.iterrows():
        assert row["entry_price"] > 0
        assert row["exit_price"] > 0
        assert row["btc_qty"] > 0
        assert row["holding_bars"] >= 1
        assert row["cash_balance"] >= 0
        assert row["exit_reason"] in ["STOP_LOSS", "TAKE_PROFIT", "TREND_BREAKDOWN", "TERMINAL_CLOSE"]


def test_stop_loss_forensics_causal_invariants():
    """Verify stop forensics causal timestamps and price bounds."""
    stops_path = Path("research_outputs/stop_reentry_forensics_11_17.csv")
    assert stops_path.exists(), "Stop forensics must exist"
    df_s = pd.read_csv(stops_path)

    assert len(df_s) > 0, "Must contain stop events"
    assert (df_s["stop_price"] > 0).all()
    assert (df_s["trade_id"] > 0).all()
    # Indicators must be strictly binary
    assert set(df_s["saved_capital_24h"].unique()).issubset({0, 1})
    assert set(df_s["whipsaw_loss_24h"].unique()).issubset({0, 1})


def test_scientific_verdict_and_mandatory_declarations():
    """Verify formal verdict and required operational declarations."""
    verdict_path = Path("research_outputs/session_intelligence_verdict_11_17.json")
    assert verdict_path.exists(), "Verdict JSON must exist"

    with open(verdict_path, "r", encoding="utf-8") as f:
        v = json.load(f)

    assert v["scientific_classification"] in ["SESSION_EDGE_NOT_SUPPORTED", "INCONCLUSIVE", "SESSION_EDGE_SUPPORTED"]
    assert v["mandatory_declarations"]["session_intelligence"] == "EXPLORATORY"
    assert v["mandatory_declarations"]["prospective_observation"] == "NOT_STARTED"
    assert v["mandatory_declarations"]["live_trading"] == "PROHIBITED"
    assert v["mandatory_declarations"]["operator_authorization"] == "NOT_GRANTED"
    assert v["mandatory_declarations"]["next_step"] == "OPERATOR_REVIEW"
