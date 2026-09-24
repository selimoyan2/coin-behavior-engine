"""Tests for statistical feature calculations."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.features.pipeline import FeaturePipeline
from coin_behavior_engine.features.returns import compute_returns
from coin_behavior_engine.features.volatility import compute_true_range


def test_compute_returns():
    df = pd.DataFrame({
        "close": [100.0, 110.0, 104.5]
    })
    res = compute_returns(df)
    # Simple returns: 0, 0.10, -0.05
    assert np.isclose(res.loc[0, "return_simple"], 0.0)
    assert np.isclose(res.loc[1, "return_simple"], 0.10)
    assert np.isclose(res.loc[2, "return_simple"], -0.05)
    # Log returns: 0, ln(1.1), ln(104.5/110)
    assert np.isclose(res.loc[1, "return_log"], np.log(1.1))


def test_compute_true_range():
    df = pd.DataFrame({
        "open": [100.0, 105.0],
        "high": [105.0, 115.0],
        "low": [95.0, 102.0],
        "close": [100.0, 110.0],
    })
    res = compute_true_range(df)
    # First candle TR = 105 - 95 = 10
    assert np.isclose(res.loc[0, "true_range"], 10.0)
    # Second candle TR = max(115-102, |115-100|, |102-100|) = max(13, 15, 2) = 15
    assert np.isclose(res.loc[1, "true_range"], 15.0)


def test_feature_pipeline_execution():
    # Synthetic dataset of 300 candles
    n = 300
    np.random.seed(42)
    prices = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(n)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(n)],
        "open": prices,
        "high": prices + 0.5,
        "low": prices - 0.5,
        "close": prices + np.random.randn(n) * 0.1,
        "volume": np.random.uniform(5.0, 50.0, n),
        "quote_volume": np.random.uniform(500.0, 5000.0, n),
        "trade_count": np.random.randint(50, 200, n),
        "symbol": ["BTCUSDT"] * n,
    })

    pipeline = FeaturePipeline()
    feat_df = pipeline.compute_all_features(df)

    assert len(feat_df) == n
    assert "return_simple" in feat_df.columns
    assert "return_log" in feat_df.columns
    assert "rank_abs_return" in feat_df.columns
    assert "rank_volatility" in feat_df.columns
    assert "rank_volume" in feat_df.columns

    # Check that percentile ranks are bounded in [0.0, 1.0]
    ranks = feat_df["rank_abs_return"].dropna()
    assert (ranks >= 0.0).all() and (ranks <= 1.0).all()
