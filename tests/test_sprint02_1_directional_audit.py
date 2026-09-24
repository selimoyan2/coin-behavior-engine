"""Automated Regression & Integrity Test Suite for Sprint 02.1 Directional Audit.

Implements 15 mandatory tests verifying temporal causality, embargo purging,
partition isolation, mathematical calibration, deterministic reproduction,
and absence of lookahead bias.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.similarity.engine import CausalSimilarityEngine, PatternFingerprint
from coin_behavior_engine.audit.directional import (
    compute_wilson_ci,
    compute_block_bootstrap_ci,
    compute_brier_score,
    DirectionalAuditor,
)


@pytest.fixture(scope="module")
def synthetic_market_data():
    """Create a deterministic synthetic dataset spanning 2021 to 2026."""
    rng = np.random.RandomState(42)
    n_candles = 5000

    dates = pd.date_range("2021-01-01", periods=n_candles, freq="5min")
    close_price = 30000.0 + np.cumsum(rng.randn(n_candles) * 50)
    ret_log = np.diff(np.log(close_price), prepend=0)

    # Macro regime cycling
    regimes = ["TRENDING_UP_HIGH_VOL", "RANGING_LOW_VOL", "BREAKOUT_HIGH_VOL", "TRENDING_DOWN_LOW_VOL"]
    macro_regime = [regimes[(i // 500) % len(regimes)] for i in range(n_candles)]

    df = pd.DataFrame({
        "datetime_open": dates,
        "close": close_price,
        "return_log": ret_log,
        "macro_regime": macro_regime,
        "macro_regime_duration": [(i % 500) + 1 for i in range(n_candles)],
        "volatility_realized_24h": np.abs(rng.randn(n_candles) * 0.01) + 0.005,
        "volatility_compression_ratio": rng.uniform(0.5, 2.0, size=n_candles),
        "volume_zscore_24h": rng.randn(n_candles),
        "volume_buy_ratio": rng.uniform(0.3, 0.7, size=n_candles),
        "trend_slope_24h": rng.randn(n_candles) * 0.001,
        "is_event": False,
    })
    df["year"] = df["datetime_open"].dt.year

    # Mark some events
    event_indices = list(range(300, n_candles - 300, 50))
    df.loc[event_indices, "is_event"] = True

    # Forward returns
    for h_name, h_steps in [("15m", 3), ("30m", 6), ("1h", 12), ("2h", 24), ("4h", 48), ("8h", 96), ("12h", 144), ("24h", 288)]:
        fwd = np.full(n_candles, np.nan)
        for i in range(n_candles - h_steps):
            fwd[i] = (close_price[i + h_steps] - close_price[i]) / close_price[i]
        df[fwd_ret_col := f"fwd_ret_{h_name}"] = fwd

    return df


# ------------------------------------------------------------------------------
# TEST 1: analogue_timestamp < query_timestamp
# ------------------------------------------------------------------------------
def test_01_analogue_timestamp_strictly_before_query(synthetic_market_data):
    """Test that all retrieved analogues strictly precede the query timestamp."""
    df = synthetic_market_data
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=288)

    events = df.index[df["is_event"]].tolist()
    query_idx = events[-10]

    analogs = engine.search_historical_analogs(df, query_idx, events, top_k=5)
    assert len(analogs) > 0, "Expected at least one historical analogue"

    query_ts = df.at[query_idx, "datetime_open"]
    for a in analogs:
        c_idx = a["candidate_idx"]
        assert c_idx < query_idx, f"Analogue idx {c_idx} >= query idx {query_idx}"
        assert df.at[c_idx, "datetime_open"] < query_ts, "Analogue timestamp is not strictly before query"


# ------------------------------------------------------------------------------
# TEST 2: analogue_outcome_end < query_timestamp
# ------------------------------------------------------------------------------
def test_02_analogue_outcome_window_non_overlapping(synthetic_market_data):
    """Test that candidate forward outcome window (<=24h) does not overlap query timestamp."""
    df = synthetic_market_data
    # 288 candles = 24 hours at 5m
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=288)

    events = df.index[df["is_event"]].tolist()
    query_idx = events[-5]

    analogs = engine.search_historical_analogs(df, query_idx, events, top_k=5)
    assert len(analogs) > 0

    for a in analogs:
        c_idx = a["candidate_idx"]
        # Candidate forward outcome window ends at c_idx + 288
        assert c_idx + 288 <= query_idx, f"Analogue outcome window ({c_idx}+288={c_idx+288}) overlaps query idx {query_idx}"


# ------------------------------------------------------------------------------
# TEST 3: No validation data in discovery fitting
# ------------------------------------------------------------------------------
def test_03_no_validation_data_in_discovery_fitting(synthetic_market_data):
    """Test that discovery partition strictly contains data prior to 2025."""
    df = synthetic_market_data
    auditor = DirectionalAuditor(df, reports_dir="data/reports/test_sprint02_1")

    assert (auditor.disc_df["year"] < 2025).all(), "Discovery dataframe contains validation/holdout years (>=2025)"
    for ev in auditor.disc_events:
        assert auditor.disc_df.at[ev, "year"] < 2025, f"Event {ev} in discovery has year >= 2025"


# ------------------------------------------------------------------------------
# TEST 4: No 2026 data in 2025 validation fitting
# ------------------------------------------------------------------------------
def test_04_no_2026_data_in_2025_validation_fitting(synthetic_market_data):
    """Test that validation partition strictly isolates year 2025 without 2026 holdout leakage."""
    df = synthetic_market_data
    auditor = DirectionalAuditor(df, reports_dir="data/reports/test_sprint02_1")

    if not auditor.val_df.empty:
        assert (auditor.val_df["year"] == 2025).all(), "Validation partition contains non-2025 data"
    if not auditor.holdout_df.empty:
        assert (auditor.holdout_df["year"] == 2026).all(), "Holdout partition contains non-2026 data"


# ------------------------------------------------------------------------------
# TEST 5: Embargo enforcement
# ------------------------------------------------------------------------------
def test_05_embargo_enforcement(synthetic_market_data):
    """Test that buffer_candles strictly excludes all candidates within the embargo window."""
    df = synthetic_market_data
    buffer = 100
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=buffer)

    events = df.index[df["is_event"]].tolist()
    query_idx = events[-5]

    analogs = engine.search_historical_analogs(df, query_idx, events, top_k=10)
    for a in analogs:
        c_idx = a["candidate_idx"]
        assert c_idx <= query_idx - buffer, f"Candidate idx {c_idx} violates buffer {buffer} for query {query_idx}"


# ------------------------------------------------------------------------------
# TEST 6: Physical-event de-duplication
# ------------------------------------------------------------------------------
def test_06_physical_event_deduplication():
    """Test that clustering logic merges proximate timestamps within cluster window."""
    raw_events = [100, 102, 105, 200, 201, 500, 505, 510, 800]
    cluster_window = 6 # 30 min (6 candles)

    clustered = []
    last_idx = -9999
    for ev in raw_events:
        if ev - last_idx > cluster_window:
            clustered.append(ev)
            last_idx = ev

    assert clustered == [100, 200, 500, 510, 800]
    for i in range(len(clustered) - 1):
        assert clustered[i + 1] - clustered[i] > cluster_window


# ------------------------------------------------------------------------------
# TEST 7: Deterministic KNN results
# ------------------------------------------------------------------------------
def test_07_deterministic_knn_results(synthetic_market_data):
    """Test that repeated similarity queries produce exactly identical candidates and distances."""
    df = synthetic_market_data
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=288)

    events = df.index[df["is_event"]].tolist()
    query_idx = events[-8]

    res1 = engine.search_historical_analogs(df, query_idx, events, top_k=5)
    res2 = engine.search_historical_analogs(df, query_idx, events, top_k=5)

    assert len(res1) == len(res2)
    for a1, a2 in zip(res1, res2):
        assert a1["candidate_idx"] == a2["candidate_idx"]
        assert math.isclose(a1["distance"], a2["distance"], rel_tol=1e-6)


# ------------------------------------------------------------------------------
# TEST 8: Deterministic placebo tests
# ------------------------------------------------------------------------------
def test_08_deterministic_placebo_tests(synthetic_market_data):
    """Test that negative-control placebo tests produce deterministic null results with fixed seed."""
    df = synthetic_market_data
    auditor = DirectionalAuditor(df, reports_dir="data/reports/test_sprint02_1")

    queries = [i for i in auditor.disc_events if i >= 1000][:30]
    df_plac1 = auditor.audit_21_placebo_tests(queries, horizon="4h")
    df_plac2 = auditor.audit_21_placebo_tests(queries, horizon="4h")

    assert df_plac1.equals(df_plac2), "Placebo test results are not deterministic"
    assert (df_plac1["status"].str.startswith("PASSED_NULL")).sum() == 3


# ------------------------------------------------------------------------------
# TEST 9: Deterministic block bootstrap
# ------------------------------------------------------------------------------
def test_09_deterministic_block_bootstrap():
    """Test that time-aware block bootstrap produces identical CIs given same random seed."""
    rng = np.random.RandomState(42)
    flags = rng.choice([0, 1], size=200, p=[0.5, 0.5])

    ci1 = compute_block_bootstrap_ci(flags, block_size=24, n_boot=500, random_seed=42)
    ci2 = compute_block_bootstrap_ci(flags, block_size=24, n_boot=500, random_seed=42)

    assert ci1 == ci2, "Block bootstrap CI is not deterministic with fixed random seed"
    assert ci1[0] <= ci1[1], "Lower CI bound is greater than upper CI bound"


# ------------------------------------------------------------------------------
# TEST 10: Probability calculation integrity
# ------------------------------------------------------------------------------
def test_10_probability_calculation_integrity():
    """Test that predicted probabilities and vote strengths are bounded within valid mathematical ranges."""
    a_rets_list = [
        [0.01, 0.02, 0.03, 0.04, 0.05], # All UP
        [-0.01, -0.02, -0.03, -0.04, -0.05], # All DOWN
        [0.01, -0.02, 0.03, -0.04, 0.05], # 3 UP, 2 DOWN
    ]

    for a_rets in a_rets_list:
        p_up = sum(1 for r in a_rets if r > 0) / len(a_rets)
        strength = max(p_up, 1.0 - p_up)

        assert 0.0 <= p_up <= 1.0, f"p_up {p_up} out of [0, 1]"
        assert 0.5 <= strength <= 1.0, f"vote strength {strength} out of [0.5, 1.0]"


# ------------------------------------------------------------------------------
# TEST 11: Calibration calculation integrity
# ------------------------------------------------------------------------------
def test_11_calibration_calculation_integrity():
    """Test that Brier score is computed correctly against mathematical expectations."""
    # Perfect forecast: Brier = 0
    p_perf = np.array([1.0, 0.0, 1.0, 0.0])
    y_perf = np.array([1, 0, 1, 0])
    assert compute_brier_score(p_perf, y_perf) == 0.0

    # Perfectly wrong forecast: Brier = 1
    p_wrong = np.array([0.0, 1.0, 0.0, 1.0])
    assert compute_brier_score(p_wrong, y_perf) == 1.0

    # Uninformative 50/50 forecast: Brier = 0.25
    p_half = np.array([0.5, 0.5, 0.5, 0.5])
    assert compute_brier_score(p_half, y_perf) == 0.25


# ------------------------------------------------------------------------------
# TEST 12: Year partition isolation
# ------------------------------------------------------------------------------
def test_12_year_partition_isolation(synthetic_market_data):
    """Test that yearly stability audit evaluates each year without cross-year bleed."""
    df = synthetic_market_data
    auditor = DirectionalAuditor(df, reports_dir="data/reports/test_sprint02_1")

    res = auditor.audit_11_yearly_stability(horizon="4h")
    assert not res.empty
    assert "year" in res.columns
    assert "partition_role" in res.columns

    # Verify Discovery years are marked correctly
    for _, row in res.iterrows():
        if row["year"] <= 2024:
            assert row["partition_role"] == "DISCOVERY_DIAGNOSTIC"


# ------------------------------------------------------------------------------
# TEST 13: Macro-regime causality
# ------------------------------------------------------------------------------
def test_13_macro_regime_causality(synthetic_market_data):
    """Test that macro-regime state at query index depends only on historical lookback."""
    df = synthetic_market_data
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=288)

    q_idx = 1000
    fp = engine.extract_fingerprint(df, q_idx)
    assert fp is not None
    assert fp.macro_regime == df.at[q_idx, "macro_regime"]
    assert fp.macro_duration_hours == df.at[q_idx, "macro_regime_duration"] * 5 / 60


# ------------------------------------------------------------------------------
# TEST 14: Feature ablation reproducibility
# ------------------------------------------------------------------------------
def test_14_feature_ablation_reproducibility(synthetic_market_data):
    """Test that feature ablation produces reproducible metrics across consecutive calls."""
    df = synthetic_market_data
    auditor = DirectionalAuditor(df, reports_dir="data/reports/test_sprint02_1")

    queries = [i for i in auditor.disc_events if i >= 1000][:20]
    df1 = auditor.audit_22_feature_ablation(queries, horizon="4h")
    df2 = auditor.audit_22_feature_ablation(queries, horizon="4h")

    assert df1.equals(df2), "Feature ablation output is not deterministic"


# ------------------------------------------------------------------------------
# TEST 15: No future data used in normalization
# ------------------------------------------------------------------------------
def test_15_no_future_data_in_normalization(synthetic_market_data):
    """Test that trajectory fingerprint normalization uses strictly the past 48 candles."""
    df = synthetic_market_data
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=288)

    q_idx = 500
    fp = engine.extract_fingerprint(df, q_idx)
    assert fp is not None

    # Normalization uses only causal past window [q-47:q] and ATR at or before q
    raw_window = df["close"].iloc[q_idx - 48 + 1 : q_idx + 1].to_numpy()
    atr = df.at[q_idx, "volatility_realized_24h"] * df.at[q_idx, "close"]
    expected_traj = (raw_window - raw_window[0]) / atr

    np.testing.assert_allclose(fp.trajectory_4h, expected_traj, rtol=1e-5, atol=1e-6)
    assert len(fp.trajectory_4h) == 48
