"""Comprehensive unit and integration test suite for Sprint 09.20.

Covers:
1. Binance Spot BTCUSDT genesis boundary invariant (2017-08-17T04:00:00Z / 1502942400000 ms).
2. Historical candle validation (monotonicity, 5m interval, gap detection, OHLC invariants).
3. Chunked dataset reading and safe isolated storage (with live volume protection).
4. Price action feature extraction with zero-lookahead verification.
5. Market session detection and Opening Range (5/10/15/30/60m) with DST awareness.
6. Market context (trend/range, volatility regimes, RVOL, OHLCV liquidity proxies).
7. Non-OHLCV extensibility interfaces and strict availability timestamp lookahead guard.
8. Purged and embargoed walk-forward time-series splitting.
9. Investment evaluation engine (TP/SL execution, trade cost model, risk metrics, independent trades).
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from datetime import datetime, timezone

from coin_behavior_engine.research.historical import (
    BINANCE_SPOT_BTCUSDT_GENESIS_MS,
    BINANCE_SPOT_BTCUSDT_GENESIS_UTC,
    HistoricalCandleValidator,
    HistoricalDatasetContract,
    HistoricalDatasetProvenance,
    HistoricalDatasetReader,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    HistoricalValidationReport,
    MarketContextExtractor,
    MarketContextFeatures,
    MarketSession,
    MarketSessionConfig,
    MarketSessionDetector,
    OpeningRangeWindow,
    PriceActionFeatureExtractor,
    PriceActionSignals,
    TimestampedNewsItem,
    EconomicAnnouncementItem,
    DerivativesContextItem,
    EtfFlowItem,
    ExternalDataAvailabilityError,
    PurgedEmbargoTimeSeriesSplitter,
    PurgedFold,
    TradeDirection,
    InvestmentOpportunity,
    TradeCostModel,
    SimulatedTradeResult,
    PortfolioEvaluationReport,
    InvestmentEvaluator,
)
from coin_behavior_engine.research.historical.extensibility_interfaces import get_available_signals


def make_synthetic_candle(
    index: int,
    start_ts_ms: int = BINANCE_SPOT_BTCUSDT_GENESIS_MS,
    interval_ms: int = 300_000,
    open_price: float = 20000.0,
    high_price: float = 20100.0,
    low_price: float = 19950.0,
    close_price: float = 20050.0,
    volume: float = 10.0,
) -> dict:
    """Helper to construct a valid synthetic 5m candle."""
    ts = start_ts_ms + index * interval_ms
    return {
        "open_time": ts,
        "timestamp_ms": ts,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "close_time": ts + interval_ms - 1,
    }


# =========================================================================
# 1. Genesis Boundary and Market Specification
# =========================================================================
def test_genesis_boundary_constants():
    assert BINANCE_SPOT_BTCUSDT_GENESIS_MS == 1502942400000
    assert BINANCE_SPOT_BTCUSDT_GENESIS_UTC == "2017-08-17T04:00:00Z"


def test_historical_market_spec_valid():
    spec = HistoricalMarketSpec(
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        timeframe="5m",
        start_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS + 3600_000,
        end_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS + 7200_000,
    )
    assert spec.start_timestamp_ms > BINANCE_SPOT_BTCUSDT_GENESIS_MS


def test_historical_market_spec_pre_genesis_fails():
    with pytest.raises(ValueError, match="precedes Binance Spot BTCUSDT launch"):
        HistoricalMarketSpec(
            exchange="binance",
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            start_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS - 300_000,
            end_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS + 300_000,
        )


def test_historical_market_spec_invalid_range():
    with pytest.raises(ValueError, match="end_timestamp_ms.*must be > start_timestamp_ms"):
        HistoricalMarketSpec(
            exchange="binance",
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            start_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS + 600_000,
            end_timestamp_ms=BINANCE_SPOT_BTCUSDT_GENESIS_MS + 300_000,
        )


# =========================================================================
# 2. Historical Candle Validation
# =========================================================================
def test_candle_validator_valid_sequence():
    candles = [
        make_synthetic_candle(i, open_price=20000 + i * 10, high_price=20050 + i * 10, low_price=19980 + i * 10, close_price=20020 + i * 10)
        for i in range(20)
    ]
    validator = HistoricalCandleValidator()
    report = validator.validate(candles)

    assert report.is_valid is True
    assert report.total_candles == 20
    assert report.valid_candles == 20
    assert report.gap_count == 0
    assert report.duplicate_count == 0
    assert report.boundary_violation_count == 0


def test_candle_validator_detects_gap():
    candles = [make_synthetic_candle(0), make_synthetic_candle(1), make_synthetic_candle(4)]
    validator = HistoricalCandleValidator()
    report = validator.validate(candles)

    assert report.is_valid is False
    assert report.gap_count == 1
    assert report.missing_candle_count == 2
    assert report.gaps[0]["missing_bars"] == 2


def test_candle_validator_detects_duplicate_and_monotonicity():
    c0 = make_synthetic_candle(0)
    c1 = make_synthetic_candle(1)
    c1_dup = make_synthetic_candle(1)
    validator = HistoricalCandleValidator()
    report = validator.validate([c0, c1, c1_dup])

    assert report.is_valid is False
    assert report.duplicate_count == 1


def test_candle_validator_detects_ohlc_invariants():
    # High < Close violation
    bad_c1 = make_synthetic_candle(0, open_price=20000, high_price=19900, low_price=19800, close_price=20000)
    # Low > Open violation
    bad_c2 = make_synthetic_candle(1, open_price=20000, high_price=20200, low_price=20100, close_price=20150)
    # Negative volume
    bad_c3 = make_synthetic_candle(2, volume=-5.0)

    validator = HistoricalCandleValidator()
    report = validator.validate([bad_c1, bad_c2, bad_c3])
    assert report.is_valid is False
    assert report.boundary_violation_count >= 3


# =========================================================================
# 3. Safe Isolated Storage and Chunked Reader
# =========================================================================
def test_dataset_store_forbids_live_volume_access(tmp_path: Path):
    safe_dir = tmp_path / "data" / "historical"
    store = HistoricalDatasetStore(base_dir=safe_dir)

    # Attempting to point to live capture must raise ValueError
    with pytest.raises(ValueError, match="cannot point to live capture directory"):
        HistoricalDatasetStore(base_dir=tmp_path / "live_capture")


def test_dataset_store_and_chunked_reader(tmp_path: Path):
    safe_dir = tmp_path / "data" / "historical"
    store = HistoricalDatasetStore(base_dir=safe_dir)

    candles = [make_synthetic_candle(i) for i in range(25)]
    spec = HistoricalMarketSpec(
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        timeframe="5m",
        start_timestamp_ms=candles[0]["open_time"],
        end_timestamp_ms=candles[-1]["open_time"],
    )

    data_path, prov_path = store.save_dataset(candles, spec, file_format="jsonl")
    assert data_path.exists()
    assert prov_path.exists()

    # Read back in chunks of 10
    reader = HistoricalDatasetReader(data_path)
    chunks = list(reader.iter_chunks(chunk_size=10))

    assert len(chunks) == 3
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5
    assert sum(len(c) for c in chunks) == 25


# =========================================================================
# 4. Price Action Feature Extraction & Zero Lookahead
# =========================================================================
def test_price_action_feature_extraction_and_zero_lookahead():
    # Create 30 candles with a swing high at index 10 and swing low at index 20
    candles = []
    base_price = 20000.0
    for i in range(35):
        if i == 10:
            hi = 21000.0
            lo = 20500.0
            cl = 20800.0
            op = 20500.0
        elif i == 20:
            hi = 19500.0
            lo = 19000.0
            cl = 19200.0
            op = 19400.0
        else:
            hi = base_price + 50
            lo = base_price - 50
            cl = base_price + 10
            op = base_price - 10
        candles.append(make_synthetic_candle(i, open_price=op, high_price=hi, low_price=lo, close_price=cl))

    extractor = PriceActionFeatureExtractor(swing_left_bars=5, swing_right_bars=5)
    signals = extractor.extract_features(candles)

    assert len(signals) == 35

    # Check zero lookahead: swing high at 10 requires 5 right bars, so it is confirmed at bar 15 (10 + 5)
    # At bar 14, nearest_resistance should NOT be 21000.0
    # At bar 15+, nearest_resistance should be 21000.0
    sig_14 = signals[14]
    sig_15 = signals[15]
    assert sig_14.nearest_resistance != 21000.0
    assert sig_15.nearest_resistance == 21000.0

    # Strict lookahead invariance test: modify future bar (e.g. index 30) and verify signals up to index 25 are identical
    modified_candles = [dict(c) for c in candles]
    modified_candles[30]["high"] = 99999.0
    modified_candles[30]["close"] = 99990.0
    mod_signals = extractor.extract_features(modified_candles)

    for k in range(26):
        assert signals[k].to_dict() == mod_signals[k].to_dict()


def test_price_action_patterns():
    # Test pinbar detection
    # Bullish pinbar (Hammer): Open 20000, Close 20050, High 20060, Low 19800 (Lower wick = 200, Range = 260 -> 76% wick)
    c_hammer = make_synthetic_candle(0, open_price=20000, high_price=20060, low_price=19800, close_price=20050)
    extractor = PriceActionFeatureExtractor()
    sigs = extractor.extract_features([c_hammer])
    assert sigs[0].is_pinbar_bullish is True
    assert sigs[0].is_pinbar_bearish is False


# =========================================================================
# 5. Market Session Detection and Opening Range
# =========================================================================
def test_market_session_detector_dst_and_zones():
    detector = MarketSessionDetector()

    # Summer: 2024-07-15 14:00:00 UTC
    # London is in BST (UTC+1) -> 15:00 BST (London active: 08:00-16:30)
    # NY is in EDT (UTC-4) -> 10:00 EDT (NY active: 09:30-16:00)
    # London and NY are both active -> LONDON_NY_OVERLAP
    dt_summer = datetime(2024, 7, 15, 14, 0, tzinfo=timezone.utc)
    ts_summer = int(dt_summer.timestamp() * 1000)
    cfg_summer = detector.detect_session(ts_summer)

    assert MarketSession.LONDON_NY_OVERLAP.value in cfg_summer.active_sessions
    assert cfg_summer.is_overlap is True
    assert cfg_summer.is_london_active is True
    assert cfg_summer.is_ny_active is True

    # Asian session: 04:00 UTC
    dt_asian = datetime(2024, 7, 15, 4, 0, tzinfo=timezone.utc)
    cfg_asian = detector.detect_session(int(dt_asian.timestamp() * 1000))
    assert MarketSession.ASIAN.value in cfg_asian.active_sessions
    assert cfg_asian.is_asian_active is True
    assert cfg_asian.is_london_active is False


def test_opening_range_computation():
    detector = MarketSessionDetector()

    # Generate 20 bars spanning NY session start (13:30 UTC in Summer EDT = 09:30 EDT)
    start_dt = datetime(2024, 7, 15, 13, 15, tzinfo=timezone.utc)
    start_ts = int(start_dt.timestamp() * 1000)

    candles = []
    for i in range(25):
        # High varies during first 15 mins (bars at 13:30, 13:35, 13:40)
        hi = 30500.0 if i == 4 else 30100.0
        lo = 29500.0 if i == 5 else 29900.0
        candles.append(make_synthetic_candle(i, start_ts_ms=start_ts, high_price=hi, low_price=lo))

    ranges = detector.compute_opening_ranges(candles, window_minutes=15, target_session=MarketSession.NEW_YORK.value)

    assert len(ranges) >= 1
    ny_or = ranges[0]
    assert ny_or.window_minutes == 15
    assert ny_or.high == 30500.0
    assert ny_or.low == 29500.0
    assert ny_or.is_finalized is True


# =========================================================================
# 6. Market Context and OHLCV Liquidity Proxies
# =========================================================================
def test_market_context_and_liquidity_proxies():
    # Strong upward trend
    candles = [
        make_synthetic_candle(i, open_price=20000 + i * 50, high_price=20080 + i * 50, low_price=19990 + i * 50, close_price=20060 + i * 50, volume=15.0)
        for i in range(30)
    ]
    extractor = MarketContextExtractor(efficiency_window=10, volatility_window=20)
    contexts = extractor.extract_context(candles)

    assert len(contexts) == 30
    last_ctx = contexts[-1]

    # In a clean uptrend, efficiency ratio should be close to 1.0
    assert last_ctx.efficiency_ratio > 0.8
    assert last_ctx.is_trending is True
    assert last_ctx.trend_direction == 1
    assert last_ctx.is_ohlcv_liquidity_proxy is True
    assert "statistical proxy" in last_ctx.liquidity_proxy_disclaimer.lower()
    assert last_ctx.amihud_illiquidity_proxy >= 0.0
    assert last_ctx.corwin_schultz_spread_proxy >= 0.0


# =========================================================================
# 7. Extensibility Interfaces & Lookahead Guard
# =========================================================================
def test_extensibility_interfaces_and_lookahead_prevention():
    now_ms = 1700000000000

    news_past = TimestampedNewsItem(
        news_id="n1",
        headline="BTC ETF approved",
        source="SEC",
        published_timestamp_ms=now_ms - 10_000,
        available_timestamp_ms=now_ms - 5_000,
        sentiment_score=0.9,
        impact_tier="CRITICAL",
    )

    news_future = TimestampedNewsItem(
        news_id="n2",
        headline="Future event",
        source="Vendor",
        published_timestamp_ms=now_ms + 10_000,
        available_timestamp_ms=now_ms + 12_000,
        sentiment_score=0.1,
        impact_tier="LOW",
    )

    # Attempting to access future news at now_ms must raise ExternalDataAvailabilityError
    with pytest.raises(ExternalDataAvailabilityError, match="Lookahead bias detected"):
        get_available_signals([news_past, news_future], decision_timestamp_ms=now_ms, fail_on_future=True)

    # When filtered with fail_on_future=False, only past news is returned
    valid_signals = get_available_signals([news_past, news_future], decision_timestamp_ms=now_ms, fail_on_future=False)
    assert len(valid_signals) == 1
    assert valid_signals[0].news_id == "n1"


def test_extensibility_invalid_availability_timestamp():
    # available before published must be rejected
    with pytest.raises(ValueError, match="available_timestamp_ms.*cannot be before"):
        TimestampedNewsItem(
            news_id="err",
            headline="Invalid",
            source="Test",
            published_timestamp_ms=1000,
            available_timestamp_ms=500,
            sentiment_score=0.0,
            impact_tier="LOW",
        )


# =========================================================================
# 8. Purged and Embargoed Walk-Forward Time-Series Splitter
# =========================================================================
def test_purged_embargo_time_series_splitter():
    splitter = PurgedEmbargoTimeSeriesSplitter(
        n_splits=3,
        outcome_horizon_bars=10,
        embargo_bars=5,
        min_train_bars=50,
    )

    total_bars = 200
    folds = list(splitter.split(total_bars))
    assert len(folds) == 3

    for fold in folds:
        # Check purge: train_indices must stop exactly outcome_horizon_bars before val_indices start
        assert fold.train_end_idx == fold.val_start_idx - 10
        assert fold.purged_count == 10

        # No intersection between train and val
        assert set(fold.train_indices).isdisjoint(set(fold.val_indices))

        # Check embargo count
        assert fold.embargo_count <= 5


# =========================================================================
# 9. Investment Evaluator, Realistic Costs & Institutional Metrics
# =========================================================================
def test_investment_evaluator_long_trade():
    candles = [
        make_synthetic_candle(0, open_price=20000, high_price=20020, low_price=19980, close_price=20000),
        make_synthetic_candle(1, open_price=20000, high_price=20150, low_price=19990, close_price=20100),
        make_synthetic_candle(2, open_price=20100, high_price=20300, low_price=20050, close_price=20280),
    ]

    opp = InvestmentOpportunity(
        opportunity_id="opp_1",
        symbol="BTCUSDT",
        entry_bar_index=0,
        entry_timestamp_ms=candles[0]["open_time"],
        direction=TradeDirection.LONG,
        entry_price=20000.0,
        take_profit_price=20250.0,
        stop_loss_price=19800.0,
        max_holding_bars=10,
    )

    cost_model = TradeCostModel(taker_fee_bps=5.0, half_spread_bps=1.0, slippage_bps=2.0)
    evaluator = InvestmentEvaluator(cost_model)
    res = evaluator.simulate_trade(opp, candles)

    assert res is not None
    assert res.exit_reason == "TAKE_PROFIT"
    assert res.exit_bar_index == 2
    assert res.exit_price == 20250.0
    assert res.gross_return_pct == pytest.approx((20250 - 20000) / 20000)
    # Net return must deduct roundtrip costs (16 bps = 0.0016)
    assert res.net_return_pct < res.gross_return_pct
    assert res.is_win is True


def test_investment_evaluator_portfolio_metrics():
    # Construct 10 simulated trades
    candles = [make_synthetic_candle(i, open_price=20000 + i*10, high_price=20050 + i*10, low_price=19950 + i*10, close_price=20020 + i*10) for i in range(50)]
    opps = [
        InvestmentOpportunity(
            opportunity_id=f"opp_{i}",
            symbol="BTCUSDT",
            entry_bar_index=i * 4,
            entry_timestamp_ms=candles[i * 4]["open_time"],
            direction=TradeDirection.LONG,
            entry_price=candles[i * 4]["close"],
            take_profit_price=candles[i * 4]["close"] * 1.01,
            stop_loss_price=candles[i * 4]["close"] * 0.99,
            max_holding_bars=3,
        )
        for i in range(8)
    ]

    evaluator = InvestmentEvaluator()
    trades, report = evaluator.evaluate_opportunities(opps, candles)

    assert len(trades) == 8
    assert report.total_opportunities == 8
    assert report.executed_trades == 8
    assert report.independent_opportunities_count >= 1
    assert 0.0 <= report.win_rate <= 1.0
    assert report.max_drawdown_pct >= 0.0
    assert report.total_costs_paid_pct > 0.0
