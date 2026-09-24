"""Automated regression test verifying that September 21 code does not contaminate the generic pipeline."""

import pandas as pd
import pytest

from coin_behavior_engine.config.loader import load_config
from coin_behavior_engine.normalization.canonical import CanonicalNormalizer
from coin_behavior_engine.research.behavior_map import BehaviorMapEngine
from coin_behavior_engine.timeframes.aggregator import TimeframeAggregator


def test_september21_pipeline_independence():
    """
    Assert that generic 2026 event outputs are 100% identical
    whether the September 21 audit module is executed or excluded.
    """
    config = load_config()
    normalizer = CanonicalNormalizer(config.paths.normalized_dir)
    aggregator = TimeframeAggregator(config.paths.derived_dir)

    canonical_5m = normalizer.load_canonical(config.asset.symbol, config.asset.primary_timeframe)
    canonical_5m = canonical_5m[canonical_5m["datetime_open"] >= "2026-09-01"].reset_index(drop=True)
    timeframes = {"5m": canonical_5m}
    for tf in config.asset.derived_timeframes:
        timeframes[tf] = aggregator.aggregate(canonical_5m, tf)

    engine = BehaviorMapEngine(config)

    # Run A: without September 21 audit
    res_a = engine.run(timeframes, include_september_audit=False)
    # Run B: with September 21 audit
    res_b = engine.run(timeframes, include_september_audit=True)

    # 1. Events 5m
    pd.testing.assert_frame_equal(res_a["events_5m"], res_b["events_5m"])

    # 2. Regimes 5m
    pd.testing.assert_frame_equal(res_a["regimes_5m"], res_b["regimes_5m"])

    # 3. Global event clusters
    pd.testing.assert_frame_equal(res_a["global_events"], res_b["global_events"])
