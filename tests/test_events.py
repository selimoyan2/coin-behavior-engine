"""Tests for event discovery and multi-timeframe linkage."""

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.events.detector import EventDetector
from coin_behavior_engine.events.multitimeframe import MultiTimeframeLinker
from coin_behavior_engine.features.pipeline import FeaturePipeline


def test_event_detection_on_synthetic_anomaly():
    np.random.seed(42)
    n = 200
    prices = [100.0] * n
    volumes = [10.0] * n

    # Introduce extreme upward spike at candle 150
    prices[150] = 115.0
    volumes[150] = 500.0

    df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(n)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(n)],
        "open": prices,
        "high": [p + 0.1 for p in prices],
        "low": [p - 0.1 for p in prices],
        "close": prices,
        "volume": volumes,
        "trade_count": [50] * n,
        "symbol": ["BTCUSDT"] * n,
    })

    pipeline = FeaturePipeline()
    feat_df = pipeline.compute_all_features(df)

    detector = EventDetector()
    scored_df, events_df = detector.detect_events(feat_df)

    # Spike at 150 must have extreme event score
    spike_score = scored_df.loc[150, "event_score"]
    assert spike_score >= 0.95

    # Events dataframe should capture the spike
    spike_ts = df.loc[150, "timestamp_open"]
    assert any(ev["timestamp_open"] == spike_ts for _, ev in events_df.iterrows())


def test_multitimeframe_linkage():
    # Synthetic events from 5m and 15m covering the same episode
    ev_5m = pd.DataFrame([{
        "event_id": "5m_1",
        "timestamp_open": 1767225600000,
        "timestamp_close": 1767225899999,
        "event_score": 0.98,
        "event_type": "UPWARD_EXPANSION",
        "return_simple": 0.03,
        "regime_during": "HIGH_VOLATILITY",
    }])

    ev_15m = pd.DataFrame([{
        "event_id": "15m_1",
        "timestamp_open": 1767225600000,
        "timestamp_close": 1767226499999,
        "event_score": 0.99,
        "event_type": "UPWARD_EXPANSION",
        "return_simple": 0.04,
        "regime_during": "HIGH_VOLATILITY",
    }])

    linker = MultiTimeframeLinker(tolerance_minutes=30)
    global_df, updated_dict = linker.link_events({"5m": ev_5m, "15m": ev_15m})

    assert len(global_df) == 1
    gev = global_df.iloc[0]
    assert gev["timeframe_count"] == 2
    assert "5m" in gev["participating_timeframes"]
    assert "15m" in gev["participating_timeframes"]
    assert updated_dict["5m"].iloc[0]["global_event_id"] == gev["global_event_id"]
    assert updated_dict["15m"].iloc[0]["global_event_id"] == gev["global_event_id"]
