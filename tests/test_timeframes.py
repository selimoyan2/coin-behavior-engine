"""Tests for timeframe aggregation engine."""

import pandas as pd
import pytest

from coin_behavior_engine.timeframes.aggregator import TimeframeAggregator


def test_timeframe_aggregation_exact_math():
    # 3 consecutive 5-minute candles comprising exactly one 15m candle (00:00 to 00:15)
    df_5m = pd.DataFrame({
        "timestamp_open": [1767225600000, 1767225900000, 1767226200000],  # 00:00, 00:05, 00:10
        "timestamp_close": [1767225899999, 1767226199999, 1767226499999],
        "open": [100.0, 102.0, 101.0],
        "high": [105.0, 108.0, 103.0],
        "low": [98.0, 101.0, 99.0],
        "close": [102.0, 101.0, 106.0],
        "volume": [10.0, 20.0, 30.0],
        "quote_volume": [1000.0, 2000.0, 3100.0],
        "trade_count": [50, 75, 125],
        "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
    })

    aggregator = TimeframeAggregator()
    df_15m = aggregator.aggregate(df_5m, "15m")

    assert len(df_15m) == 1
    candle = df_15m.iloc[0]

    # Open = first
    assert candle["open"] == 100.0
    # High = max
    assert candle["high"] == 108.0
    # Low = min
    assert candle["low"] == 98.0
    # Close = last
    assert candle["close"] == 106.0
    # Volumes = sum
    assert candle["volume"] == 60.0
    assert candle["quote_volume"] == 6100.0
    # Trades = sum
    assert candle["trade_count"] == 250
    # Timestamps
    assert candle["timestamp_open"] == 1767225600000
    assert candle["timestamp_close"] == 1767226499999
