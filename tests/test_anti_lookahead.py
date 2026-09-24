"""Anti-lookahead test guaranteeing no future data leakage into historical features."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.events.detector import EventDetector
from coin_behavior_engine.features.pipeline import FeaturePipeline


def test_no_future_data_leakage():
    """
    CRITICAL ANTI-LOOKAHEAD TEST:
    Calculate features and event scores on history up to timestamp T.
    Then append future candles T+1 ... T+N.
    Recalculate.
    Assert that all feature values and event scores at timestamp T remain EXACTLY IDENTICAL.
    """
    np.random.seed(42)
    total_bars = 400
    t_split = 250  # Timestamp T is at index 249 (250 bars)

    prices = 100.0 + np.cumsum(np.random.randn(total_bars) * 0.5)
    full_df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(total_bars)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(total_bars)],
        "open": prices,
        "high": prices + np.abs(np.random.randn(total_bars) * 0.5),
        "low": prices - np.abs(np.random.randn(total_bars) * 0.5),
        "close": prices + np.random.randn(total_bars) * 0.2,
        "volume": np.random.uniform(10.0, 100.0, total_bars),
        "quote_volume": np.random.uniform(1000.0, 10000.0, total_bars),
        "trade_count": np.random.randint(50, 300, total_bars),
        "symbol": ["BTCUSDT"] * total_bars,
    })

    # Dataset 1: strictly history up to T
    history_up_to_t = full_df.iloc[:t_split].copy()

    pipeline = FeaturePipeline()
    detector = EventDetector()

    feat_t1 = pipeline.compute_all_features(history_up_to_t)
    scored_t1, _ = detector.detect_events(feat_t1)

    # Features and score at timestamp T (the last row of history_up_to_t)
    row_t_before = scored_t1.iloc[-1]

    # Dataset 2: history up to T PLUS future bars appended
    feat_t2 = pipeline.compute_all_features(full_df)
    scored_t2, _ = detector.detect_events(feat_t2)

    # Features and score at timestamp T in the extended dataset
    row_t_after = scored_t2.iloc[t_split - 1]

    # Verify identical timestamps
    assert row_t_before["timestamp_open"] == row_t_after["timestamp_open"]

    # Verify that all numeric feature columns at timestamp T are strictly identical
    numeric_cols = [
        col for col in scored_t1.columns
        if pd.api.types.is_numeric_dtype(scored_t1[col])
        and col not in ("timestamp_open", "timestamp_close")
    ]

    for col in numeric_cols:
        val_before = row_t_before[col]
        val_after = row_t_after[col]

        if np.isnan(val_before) and np.isnan(val_after):
            continue

        assert np.isclose(val_before, val_after, atol=1e-7), (
            f"Future leakage detected in feature '{col}' at timestamp T! "
            f"Before future appended: {val_before}, After future appended: {val_after}"
        )

    # Also assert that event_type at T is identical
    ev_before = row_t_before["event_type"]
    ev_after = row_t_after["event_type"]
    if pd.isna(ev_before) and pd.isna(ev_after):
        pass
    else:
        assert ev_before == ev_after, (
            f"Event classification at timestamp T changed after appending future data! "
            f"{ev_before} != {ev_after}"
        )
