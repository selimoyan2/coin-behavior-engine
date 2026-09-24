"""Tests for unsupervised market regime detection."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.features.pipeline import FeaturePipeline
from coin_behavior_engine.regimes.classifier import RegimeClassifier


def test_regime_classification_blocks():
    # Synthetic flat quiet market followed by trending market
    n = 150
    # Quiet period
    quiet_prices = [100.0 + i * 0.01 for i in range(100)]
    # Trending up period
    trend_prices = [quiet_prices[-1] + (i + 1) * 0.5 for i in range(50)]
    prices = quiet_prices + trend_prices

    df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(n)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(n)],
        "open": prices,
        "high": [p + 0.05 for p in prices],
        "low": [p - 0.05 for p in prices],
        "close": prices,
        "volume": [10.0] * n,
        "trade_count": [50] * n,
        "symbol": ["BTCUSDT"] * n,
    })

    pipeline = FeaturePipeline()
    feat_df = pipeline.compute_all_features(df)

    classifier = RegimeClassifier()
    bar_regimes, regime_blocks = classifier.detect_regimes(feat_df)

    assert len(bar_regimes) == n
    assert not regime_blocks.empty
    assert "regime_label" in regime_blocks.columns
    assert "duration_hours" in regime_blocks.columns
    assert "total_displacement_pct" in regime_blocks.columns

    # Check that TRENDING_UP was recognized during the strong uptrend
    assert any("TRENDING_UP" == r["regime_label"] for _, r in regime_blocks.iterrows())
