"""Tests for event windows extraction and post-event outcome evaluation."""

import pandas as pd
import pytest

from coin_behavior_engine.events.windows import EventWindowExtractor


def test_event_windows_separation_and_classification():
    # 50 candles: event at candle 20
    n = 50
    prices = [100.0] * n
    # Make candle 20 an upward spike
    prices[20] = 105.0

    # Scenario A: Failure - price immediately drops back to 100.0 from candle 21 to 50
    df = pd.DataFrame({
        "timestamp_open": [1767225600000 + i * 300_000 for i in range(n)],
        "timestamp_close": [1767225899999 + i * 300_000 for i in range(n)],
        "open": prices,
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
        "volume": [10.0] * n,
    })

    event_record = pd.DataFrame([{
        "event_id": "5m_1",
        "timestamp_open": df.loc[20, "timestamp_open"],
        "timestamp_close": df.loc[20, "timestamp_close"],
        "event_type": "UPWARD_EXPANSION",
        "event_score": 0.98,
        "is_significant": True,
        "close_price": 105.0,
        "return_simple": 0.05,
    }])

    extractor = EventWindowExtractor(timeframe_minutes=5, failed_expansion_threshold_pct=0.003)
    evaluated = extractor.evaluate_event_outcomes(event_record, df)

    assert len(evaluated) == 1
    ev = evaluated.iloc[0]

    # Pre-return 1h should be positive (comparing 105 to earlier 100)
    assert "pre_return_1h" in ev
    assert "post_return_1h" in ev
    # Post-return 1h is negative (-0.0476 since price dropped back to 100 from 105)
    assert ev["post_return_1h"] < 0
    # Because followthrough is negative, outcome classification must be FAILED_EXPANSION
    assert ev["outcome_classification"] == "FAILED_EXPANSION"
