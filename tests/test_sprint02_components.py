"""Automated unit and regression tests for Sprint 02 research engine."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.partitions.temporal import TemporalPartitionManager, compute_partition_hash
from coin_behavior_engine.outcomes.continuous import ContinuousOutcomeEngine, HORIZONS_5M
from coin_behavior_engine.snapshots.extractor import PreEventSnapshotExtractor
from coin_behavior_engine.snapshots.controls import MatchedControlEngine
from coin_behavior_engine.snapshots.comparison import compute_cohens_d, SnapshotStatisticalComparator
from coin_behavior_engine.hierarchy.macro_regime import MacroRegimeDetector
from coin_behavior_engine.compression.analyzer import CompressionEpisodeAnalyzer
from coin_behavior_engine.scoring.evt import ExtremeValueTailModel, EventScoreV2Engine
from coin_behavior_engine.similarity.engine import CausalSimilarityEngine, PatternFingerprint
from coin_behavior_engine.walkforward.evaluator import WalkForwardEvaluator, classify_replication_outcome


@pytest.fixture
def synthetic_5m_market():
    """Generates synthetic 5m OHLCV data spanning multiple years for testing."""
    np.random.seed(42)
    n = 2000
    dates = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    closes = 50000.0 + np.cumsum(np.random.randn(n) * 50.0)
    highs = closes + np.abs(np.random.randn(n) * 20.0)
    lows = closes - np.abs(np.random.randn(n) * 20.0)
    opens = closes + np.random.randn(n) * 5.0
    vol = np.random.exponential(10.0, n)
    t_open = [int(d.timestamp() * 1000) for d in dates]
    t_close = [t + 299999 for t in t_open]

    df = pd.DataFrame({
        "timestamp_open": t_open,
        "timestamp_close": t_close,
        "datetime_open": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vol,
        "trade_count": [100] * n,
        "symbol": ["BTCUSDT"] * n,
    })

    # Add synthetic features
    df["volatility_realized_24h"] = pd.Series(closes).pct_change().rolling(288, min_periods=10).std().fillna(0.01)
    df["volatility_compression_ratio"] = np.random.uniform(0.5, 1.5, n)
    df["volume_zscore_24h"] = np.random.randn(n)
    df["volume_buy_ratio"] = np.random.uniform(0.4, 0.6, n)
    df["return_log_1h"] = pd.Series(closes).pct_change(12).fillna(0.0)
    df["return_log_24h"] = pd.Series(closes).pct_change(288).fillna(0.0)
    df["trend_slope_24h"] = np.random.randn(n) * 0.0005
    df["event_score"] = np.random.uniform(0.1, 0.9, n)
    df["regime"] = np.random.choice(["TRANSITION", "COMPRESSION", "TRENDING_BULL"], n)

    return df


def test_continuous_outcomes(synthetic_5m_market):
    """Verify forward continuous outcomes across all horizons."""
    engine = ContinuousOutcomeEngine(horizons={"15m": 3, "1h": 12, "4h": 48})
    df_out = engine.compute_forward_outcomes(synthetic_5m_market)

    assert "fwd_ret_15m" in df_out.columns
    assert "fwd_abs_ret_15m" in df_out.columns
    assert "fwd_mfe_15m" in df_out.columns
    assert "fwd_mae_15m" in df_out.columns
    assert "fwd_vol_15m" in df_out.columns

    # Verify no lookahead in past rows
    assert not np.isnan(df_out.at[0, "fwd_ret_15m"])
    # Last rows should have NaN due to horizon shift
    assert np.isnan(df_out.at[len(df_out) - 1, "fwd_ret_15m"])

    summary = engine.summarize_outcome_distributions(df_out)
    assert len(summary) == 3
    assert "mean_signed_ret" in summary.columns


def test_snapshots_and_matched_controls(synthetic_5m_market):
    """Verify causal pre-event snapshots and deterministic matched control selection."""
    event_indices = [500, 1000, 1500]

    # Snapshots
    extractor = PreEventSnapshotExtractor(offsets={"T_minus_5m": 1, "T_minus_1h": 12})
    snaps = extractor.extract_snapshots_for_events(synthetic_5m_market, event_indices)
    assert "T_minus_5m" in snaps
    assert len(snaps["T_minus_5m"]) == 3

    # Controls
    ctrl_engine = MatchedControlEngine(event_exclusion_window_candles=50)
    controls_df = ctrl_engine.find_matched_controls(synthetic_5m_market, event_indices)
    assert len(controls_df) == 3
    for _, row in controls_df.iterrows():
        ev_idx = int(row["event_idx"])
        ctrl_idx = int(row["control_idx"])
        # Control cannot be within exclusion window of event
        assert abs(ev_idx - ctrl_idx) > 50


def test_macro_regimes(synthetic_5m_market):
    """Verify persistent Layer 2 macro-regime detector and hysteresis filter."""
    detector = MacroRegimeDetector(persistence_min_candles=6)
    out_df = detector.detect_macro_regimes(synthetic_5m_market)

    assert "macro_regime" in out_df.columns
    assert "macro_regime_duration" in out_df.columns

    metrics = detector.calculate_regime_transition_metrics(out_df)
    assert "switches_per_day" in metrics
    assert "median_duration_hours" in metrics


def test_compression_analyzer(synthetic_5m_market):
    """Verify compression episode identification and categorization."""
    analyzer = CompressionEpisodeAnalyzer(expansion_horizon_candles=50, expansion_threshold_pct=0.01)
    # Set a chunk to COMPRESSION
    synthetic_5m_market.loc[200:230, "regime"] = "COMPRESSION"
    episodes = analyzer.identify_compression_episodes(synthetic_5m_market)
    assert len(episodes) >= 1
    assert episodes[0]["outcome_category"] in [
        "CATEGORY_A_UPWARD_EXPANSION",
        "CATEGORY_B_DOWNWARD_EXPANSION",
        "CATEGORY_C_FALSE_OR_CHOP"
    ]


def test_evt_and_event_score_v2(synthetic_5m_market):
    """Verify EVT tail model fitting and Mahalanobis Event Score V2."""
    evt = ExtremeValueTailModel(threshold_quantile=0.90)
    tail_data = np.random.exponential(1.0, 1000)
    params = evt.fit(tail_data)
    assert "shape_xi" in params
    assert "scale_sigma" in params

    tail_probs = evt.compute_tail_probability(np.array([1.0, 2.0, 5.0]))
    assert len(tail_probs) == 3
    # Probability decreases with higher threshold
    assert tail_probs[0] >= tail_probs[1] >= tail_probs[2]

    # Event Score V2
    v2_engine = EventScoreV2Engine()
    v2_engine.fit_discovery(synthetic_5m_market.iloc[:1000])
    scores = v2_engine.compute_event_score_v2(synthetic_5m_market)
    assert len(scores) == len(synthetic_5m_market)
    # Scores should be in [0, 1] without saturation
    assert (scores >= 0.0).all() and (scores <= 1.0).all()


def test_causal_similarity_engine(synthetic_5m_market):
    """Verify strictly causal historical analog search."""
    engine = CausalSimilarityEngine(trajectory_len=48, buffer_candles=50)
    engine_df = synthetic_5m_market.copy()
    engine_df["fwd_ret_1h"] = engine_df["close"].pct_change(12).shift(-12)
    engine_df["fwd_ret_4h"] = engine_df["close"].pct_change(48).shift(-48)
    engine_df["fwd_ret_24h"] = engine_df["close"].pct_change(288).shift(-288)

    query_idx = 800
    candidate_indices = [100, 200, 300, 400, 780, 850, 900]
    analogs = engine.search_historical_analogs(engine_df, query_idx, candidate_indices, top_k=3)

    assert len(analogs) <= 3
    for a in analogs:
        # Strict causality: candidate must be strictly less than query_idx - buffer (800 - 50 = 750)
        assert a["candidate_idx"] <= 750


def test_walk_forward_replication_classification():
    """Verify out-of-sample replication outcome classification."""
    assert classify_replication_outcome(0.50, 0.48, 0.001) == "REPLICATE"
    assert classify_replication_outcome(0.50, 0.25, 0.01) == "WEAKEN"
    assert classify_replication_outcome(0.50, 0.05, 0.20) == "DISAPPEAR"
    assert classify_replication_outcome(0.50, -0.40, 0.01) == "REVERSE"
