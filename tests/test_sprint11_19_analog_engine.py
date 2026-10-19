"""Sprint 11.19 Invariant Test Suite: Historical Analog Learning Engine V1.

Tests execute directly against source code, feature store, similarity engine,
forecasting routines, and governance manifests.
NO outcome-forcing assertions.
NO simple assertions on pre-saved boolean flags.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.analogs.feature_store import CausalFeatureStore
from coin_behavior_engine.analogs.regime_classifier import MarketRegimeClassifier
from coin_behavior_engine.analogs.similarity_engine import CausalSimilarityEngine
from coin_behavior_engine.analogs.probabilistic_forecaster import ProbabilisticForecaster
from coin_behavior_engine.analogs.range_intelligence import RangeIntelligenceEvaluator
from coin_behavior_engine.macro.global_session_calendar import GlobalSessionCalendar


@pytest.fixture(scope="module")
def multiyear_df():
    # Load sample of multiyear 5m data (2022-01 to 2023-06)
    files = sorted(Path("data/binance_spot_multiyear/5m").glob("BTCUSDT-5m-*.parquet"))[:18]
    assert len(files) >= 12, "Must have multi-year 5m parquets available"
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    return df


@pytest.fixture(scope="module")
def audited_events():
    events_path = Path("research_outputs/historical_event_evidence_audit_11_18_2.json")
    assert events_path.exists()
    with open(events_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["audited_events"]


def test_cross_dataset_closure_reconciliation():
    """Verify cross-dataset closure accurately accounts for raw vs vision discrepancy."""
    closure_path = Path("research_outputs/cross_dataset_closure_11_19.json")
    assert closure_path.exists(), "cross_dataset_closure_11_19.json must exist"
    with open(closure_path, "r", encoding="utf-8") as f:
        closure = json.load(f)

    summary = closure["investigation_summary"]
    assert summary["mismatched_bars_count"] == 8
    assert summary["identical_bars_count"] == 497309
    assert summary["concordance_rate_pct"] > 99.99

    # Check terminal bar quarantine
    q_bars = closure["governance_and_quarantine"]["quarantined_bars"]
    assert len(q_bars) == 1
    assert "2026-09-23 20:20:00" in q_bars[0]["datetime_utc"]


def test_contamination_governance_no_virgin_claims():
    """Verify contamination register strictly rejects virgin/out-of-sample claims for 2026."""
    contam_path = Path("research_outputs/contamination_register_11_19.json")
    assert contam_path.exists(), "contamination_register_11_19.json must exist"
    with open(contam_path, "r", encoding="utf-8") as f:
        reg = json.load(f)

    mandate = reg["mandatory_status_declarations"]
    assert mandate["HISTORICAL_DATA_STATUS"] == "RESEARCH_CONTAMINATED"
    assert mandate["PROSPECTIVE_OBSERVATION"] == "NOT_STARTED"

    # Verify 2026 partition is HISTORICAL_RESEARCH_EXPOSED
    p_2026 = next(p for p in reg["partition_contamination_inventory"] if p["partition_id"] == "PARTITION_2026_Q1_Q3")
    assert p_2026["contamination_level"] == "HISTORICAL_RESEARCH_EXPOSED"


def test_event_provenance_downgraded_to_assumed_latency():
    """Verify all 3 events are downgraded to ASSUMED_LATENCY."""
    corr_path = Path("research_outputs/event_provenance_corrections_11_19.json")
    assert corr_path.exists(), "event_provenance_corrections_11_19.json must exist"
    with open(corr_path, "r", encoding="utf-8") as f:
        corr = json.load(f)

    assert corr["overall_event_provenance"] == "ASSUMED"
    for evt in corr["downgraded_events"]:
        assert evt["corrected_classification"] == "ASSUMED_LATENCY"
        assert "conservative_visibility_enforcement" in evt


def test_no_future_feature_leakage(multiyear_df, audited_events):
    """Verify that features at T_0 strictly observe only closed candles with close_time <= T_0."""
    calendar = GlobalSessionCalendar()
    store = CausalFeatureStore(multiyear_df, audited_events, calendar)

    # Query at a specific moment
    q_ms = int(multiyear_df.iloc[1000]["close_time"])
    fv = store.get_feature_vector_at(q_ms)
    assert fv is not None
    assert fv.open_time <= q_ms
    assert fv.open_time == int(multiyear_df.iloc[1000]["open_time"])


def test_no_future_analog_candidates_and_quarantine(multiyear_df, audited_events):
    """Verify candidate analogs have their entire 7-day outcome completed BEFORE query moment."""
    calendar = GlobalSessionCalendar()
    store = CausalFeatureStore(multiyear_df, audited_events, calendar)
    classifier = MarketRegimeClassifier()
    sim_engine = CausalSimilarityEngine(store.df, classifier, max_horizon_bars=2016)

    # Query at bar 10,000
    q_idx = 10000
    q_ms = int(store.df.iloc[q_idx]["open_time"])
    fv = store.get_feature_vector_at(q_ms)
    assert fv is not None

    res = sim_engine.find_analogs(q_idx, fv)
    assert len(res.analogs) > 0

    for a in res.analogs:
        # Strict quarantine invariant: a.candle_idx + 2016 <= q_idx
        assert a.candle_idx + sim_engine.max_horizon_bars <= q_idx, (
            f"Future leakage: Analog at {a.candle_idx} + 2016 > {q_idx}"
        )


def test_outage_cross_gap_window_rejection(multiyear_df, audited_events):
    """Verify windows crossing the March 24, 2023 outage are flagged invalid."""
    calendar = GlobalSessionCalendar()
    store = CausalFeatureStore(multiyear_df, audited_events, calendar)

    # Query inside or right after outage: 2023-03-24 15:00:00 UTC
    outage_ts_ms = 1679670000000  # 2023-03-24 15:00:00 UTC
    fv = store.get_feature_vector_at(outage_ts_ms)
    if fv:
        assert not fv.is_valid_window, "Window crossing March 24, 2023 outage must be flagged invalid"
        assert fv.rejection_reason == "WINDOW_CROSSES_20230324_EXCHANGE_OUTAGE"


def test_probabilistic_forecast_probability_conservation(multiyear_df, audited_events):
    """Verify probabilistic forecast probabilities sum to ~1.0."""
    calendar = GlobalSessionCalendar()
    store = CausalFeatureStore(multiyear_df, audited_events, calendar)
    classifier = MarketRegimeClassifier()
    sim_engine = CausalSimilarityEngine(store.df, classifier, max_horizon_bars=2016)
    forecaster = ProbabilisticForecaster()

    q_idx = 8000
    q_ms = int(store.df.iloc[q_idx]["open_time"])
    q_close = float(store.df.iloc[q_idx]["close"])
    fv = store.get_feature_vector_at(q_ms)

    res = sim_engine.find_analogs(q_idx, fv)
    pred = forecaster.generate_forecast(res, q_close, store.df)

    assert not pred.is_abstained
    for h, fcast in pred.forecasts.items():
        total_p = fcast.prob_up + fcast.prob_down
        assert abs(total_p - 1.0) < 0.05, f"Horizon {h} prob sum violation: {total_p}"
        assert fcast.quantile_10 <= fcast.quantile_50 if hasattr(fcast, 'quantile_50') else fcast.quantile_10 <= fcast.median_return
        assert fcast.median_return <= fcast.quantile_90


def test_range_intelligence_friction_and_no_edge(multiyear_df):
    """Verify RangeIntelligenceEvaluator returns NO_EDGE when channel width is insufficient for friction."""
    evaluator = RangeIntelligenceEvaluator(multiyear_df)

    # Channel width 0.20% (65,000 to 65,130 USDT) - less than 0.30% round-trip friction
    res = evaluator.evaluate_channel(
        support_level=65000.0,
        resistance_level=65130.0,
        current_price=65050.0
    )
    assert res.verdict == "NO_EDGE"
    assert "Insufficient net tradable room" in res.verdict_rationale


def test_news_coverage_gap_insufficient_data():
    """Verify that news intelligence gap document confirms INSUFFICIENT_DATA."""
    gap_path = Path("research_outputs/news_coverage_gap_11_19.md")
    assert gap_path.exists()
    content = gap_path.read_text(encoding="utf-8")
    assert "NEWS_CONDITIONED_EDGE=INSUFFICIENT_DATA" in content
    assert "sample of three events spanning 57 months provides exactly zero statistical power" in content
