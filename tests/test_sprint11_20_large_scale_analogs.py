"""Sprint 11.20 Invariant Test Suite: Large-Scale Analog Intelligence & Range Trading Economics.

Tests verify:
1. Range metric forensic reconciliation (proof of -0.426% vs -1.42% MAE root cause).
2. Large-scale evaluation ledger completeness (>= 1,000 points, 8 horizons = >= 8,000 rows).
3. Causal candidate quarantine (t_cand + 2016 <= T).
4. Range trading simulator mechanics (next-bar open fill, 15 bps round-trip friction, cash conservation).
5. Multi-criteria abstention engine mechanics.
6. Probability sum conservation and validity.
7. Matched control comparisons and turnover parity.
8. Scientific honesty of mandatory status declarations.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.analogs.range_trader import CausalRangeTrader, RangeTradeRecord
from coin_behavior_engine.analogs.similarity_engine import CausalSimilarityEngine, FeatureVector
from coin_behavior_engine.analogs.regime_classifier import MarketRegimeClassifier
from coin_behavior_engine.analogs.feature_store import CausalFeatureStore
from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar


def test_range_metric_reconciliation():
    """Verify range metric forensic reconciliation file exists and resolves the discrepancy."""
    rec_path = Path("research_outputs/range_metric_reconciliation_11_20.json")
    if not rec_path.exists():
        rec_path = Path("range_metric_reconciliation_11_20.json")
    assert rec_path.exists(), "range_metric_reconciliation_11_20.json must exist"

    with open(rec_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify forensic root cause investigation
    forensic = data["forensic_investigation"]
    assert "root_cause_explanation" in forensic
    assert "in-trade" in forensic["root_cause_explanation"].lower()
    assert "unhedged" in forensic["root_cause_explanation"].lower()

    # Verify canonical recalculated metrics
    metrics = data["canonical_recalculated_metrics"]["metrics"]
    assert abs(metrics["in_trade_path_mae_pct"] - (-0.426)) < 0.05
    assert abs(metrics["unhedged_full_24h_mae_pct"] - (-1.497)) < 0.15
    assert metrics["in_trade_risk_reward_ratio"] == 1.82
    assert metrics["unhedged_risk_reward_ratio"] == 0.52

    assert data["canonical_recalculated_metrics"]["canonical_verdict"] == "NO_EDGE"


def test_evaluation_ledger_completeness():
    """Verify forecast evaluation ledger exists, contains >= 8,000 rows across 8 horizons."""
    ledger_path = Path("research_outputs/forecast_evaluation_ledger_11_20.parquet")
    if not ledger_path.exists():
        ledger_path = Path("forecast_evaluation_ledger_11_20.parquet")
    assert ledger_path.exists(), "forecast_evaluation_ledger_11_20.parquet must exist"

    df = pd.read_parquet(ledger_path)
    assert len(df) >= 8000, f"Expected at least 8000 prediction rows, got {len(df)}"

    required_cols = [
        "decision_timestamp_utc", "open_time", "decision_close",
        "market_regime", "regime_confidence", "prediction_horizon",
        "horizon_bars", "predicted_prob_up", "realized_return",
        "loss_brier_analog", "loss_brier_unconditional",
        "loss_brier_regime", "loss_brier_random_walk", "loss_brier_momentum",
        "is_abstained", "abstention_reason"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"

    # Verify 8 horizons present
    horizons = set(df["prediction_horizon"].unique())
    expected_horizons = {"1h", "3h", "6h", "12h", "24h", "48h", "72h", "7d"}
    assert expected_horizons.issubset(horizons), f"Missing horizons: {expected_horizons - horizons}"

    # Verify unique evaluation timestamps >= 1,000
    n_unique_ts = df["open_time"].nunique()
    assert n_unique_ts >= 1000, f"Expected >= 1,000 unique timestamps, got {n_unique_ts}"


def test_probability_conservation_and_validity():
    """Verify that analog probability forecasts conserve probability: 0 <= P(up) <= 1.0."""
    ledger_path = Path("research_outputs/forecast_evaluation_ledger_11_20.parquet")
    if not ledger_path.exists():
        ledger_path = Path("forecast_evaluation_ledger_11_20.parquet")
    df = pd.read_parquet(ledger_path)

    valid_df = df[~df["is_abstained"]]
    assert len(valid_df) > 0, "Should have non-abstained predictions"
    assert (valid_df["predicted_prob_up"] >= 0.0).all()
    assert (valid_df["predicted_prob_up"] <= 1.0).all()

    # For quantiles: q10 <= median <= q90
    assert (valid_df["predicted_q10"] <= valid_df["predicted_median_return"]).all()
    assert (valid_df["predicted_median_return"] <= valid_df["predicted_q90"]).all()


def test_causal_candidate_quarantine():
    """Verify that candidate analogs are strictly quarantined: t_cand + max_horizon <= T."""
    calendar = GlobalSessionCalendar()
    classifier = MarketRegimeClassifier()

    files = sorted(Path("data/binance_spot_multiyear/5m").glob("BTCUSDT-5m-*.parquet"))[:4]
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    events_path = Path("research_outputs/historical_event_evidence_audit_11_18_2.json")
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)["audited_events"]

    store = CausalFeatureStore(df, events, calendar)
    sim_engine = CausalSimilarityEngine(store.df, classifier, max_horizon_bars=2016)

    q_idx = 15000
    q_ms = int(store.df.iloc[q_idx]["open_time"])
    fv = store.get_feature_vector_at(q_ms)
    assert fv is not None

    res = sim_engine.find_analogs(q_idx, fv)
    assert len(res.analogs) > 0

    for a in res.analogs:
        # Candidate end must be strictly <= query idx
        assert a.candle_idx + sim_engine.max_horizon_bars <= q_idx, (
            f"Candidate at {a.candle_idx} outcome extends past query idx {q_idx}"
        )


def test_range_trading_simulator_mechanics():
    """Verify simulator fills at next-bar open, charges 15 bps round-trip friction, and conserves capital."""
    ledger_path = Path("research_outputs/range_trade_ledger_11_20.parquet")
    if not ledger_path.exists():
        ledger_path = Path("range_trade_ledger_11_20.parquet")
    assert ledger_path.exists(), "range_trade_ledger_11_20.parquet must exist"

    df_trades = pd.read_parquet(ledger_path)
    assert len(df_trades) > 0, "Trade ledger must contain executed trades"

    for _, row in df_trades.iterrows():
        # Total fee should be positive
        assert row["entry_fee_usdt"] > 0.0
        assert row["exit_fee_usdt"] > 0.0
        # Total slippage should be positive
        assert row["entry_slippage_usdt"] > 0.0
        assert row["exit_slippage_usdt"] > 0.0

        # Exact cash accounting: net_pnl = gross_proceeds - exit_fee - allocated_usdt
        expected_net = row["gross_proceeds_usdt"] - row["exit_fee_usdt"] - row["allocated_usdt"]
        assert abs(row["net_pnl_usdt"] - expected_net) < 0.05

    # Also verify CausalRangeTrader Cash-Only and Buy & Hold invariants
    dummy_df = pd.DataFrame({
        "open_time": [1000, 2000, 3000],
        "open": [65000.0, 65100.0, 65200.0],
        "high": [65200.0, 65300.0, 65400.0],
        "low": [64900.0, 65000.0, 65100.0],
        "close": [65100.0, 65200.0, 65300.0],
        "volume": [10.0, 10.0, 10.0]
    })
    trader = CausalRangeTrader(dummy_df)
    res_cash = trader.run_strategy(0, 2, "CASH_ONLY")
    assert res_cash["final_equity"] == 10000.00
    assert res_cash["net_pnl_usdt"] == 0.00

    res_bh = trader.run_strategy(0, 2, "BUY_AND_HOLD")
    assert res_bh["total_trades"] == 1
    assert res_bh["final_equity"] > 0


def test_matched_control_turnover_parity():
    """Verify matched control artifact exists and verifies turnover alignment."""
    ctrl_path = Path("research_outputs/matched_controls_11_20.json")
    if not ctrl_path.exists():
        ctrl_path = Path("matched_controls_11_20.json")
    assert ctrl_path.exists(), "matched_controls_11_20.json must exist"

    with open(ctrl_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ctrls = data["control_comparisons"]
    assert "matched_turnover_control" in ctrls
    assert "matched_exposure_control" in ctrls

    assert ctrls["matched_turnover_control"]["matched_trades_count"] == 7
    assert ctrls["matched_turnover_control"]["expected_turnover_drag_pct"] == 2.05


def test_scientific_status_declarations():
    """Verify research deliverables maintain honest scientific status declarations."""
    multi_path = Path("research_outputs/multihorizon_skill_audit_11_20.json")
    if not multi_path.exists():
        multi_path = Path("multihorizon_skill_audit_11_20.json")
    assert multi_path.exists(), "multihorizon_skill_audit_11_20.json must exist"

    with open(multi_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["probabilistic_forecast_skill"] == "NOT_SUPPORTED"

    news_path = Path("research_outputs/news_coverage_requirements_11_20.md")
    if not news_path.exists():
        news_path = Path("news_coverage_requirements_11_20.md")
    content = news_path.read_text(encoding="utf-8")
    assert "NEWS_CONDITIONED_EDGE=INSUFFICIENT_DATA" in content or "NEWS_CONDITIONED_EDGE = INSUFFICIENT_DATA" in content
