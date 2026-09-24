"""Tests for deterministic execution and reproducibility."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.features.pipeline import FeaturePipeline
from coin_behavior_engine.regimes.classifier import RegimeClassifier


def test_reproducibility_deterministic_pipeline():
    np.random.seed(42)
    n = 100
    prices = 100.0 + np.cumsum(np.random.randn(n) * 0.2)
    df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(n)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(n)],
        "open": prices,
        "high": prices + 0.1,
        "low": prices - 0.1,
        "close": prices,
        "volume": [10.0] * n,
        "trade_count": [50] * n,
        "symbol": ["BTCUSDT"] * n,
    })

    # Run 1
    pipe1 = FeaturePipeline()
    feat1 = pipe1.compute_all_features(df)
    regime1_bars, regime1_blocks = RegimeClassifier().detect_regimes(feat1)

    # Run 2
    pipe2 = FeaturePipeline()
    feat2 = pipe2.compute_all_features(df)
    regime2_bars, regime2_blocks = RegimeClassifier().detect_regimes(feat2)

    # Assert exact numerical identity across runs
    pd.testing.assert_frame_equal(feat1, feat2)
    pd.testing.assert_series_equal(regime1_bars, regime2_bars)
    pd.testing.assert_frame_equal(regime1_blocks, regime2_blocks)
