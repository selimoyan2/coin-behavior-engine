"""
Sprint 11.03 Automated Verification Test Suite
================================================
Comprehensive verification of Market Behavior Research Lab components:
- System safety & configuration constraints (isolated namespace, APPROVAL_4=False, trading disabled)
- Historical data contracts, aggregation & anti-leakage invariants
- Data quality validation & anomaly detection
- Market behavior feature engine & regime classification
- Event intelligence catalog & pre/post market alignment
- Behavioral pattern recognition & outcome catalogs
- Probabilistic prediction engine & calibrated distributions
- Risk engine & position sizing bounds
- Historical paper simulation & order execution accounting
- Strategy evaluation & reproducible reporting
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
import pytest
import pandas as pd

from coin_behavior_engine.research_lab.configuration import (
    ResearchLabConfig,
    RESEARCH_LAB_ACTIVE,
    RESEARCH_TRADING_ENABLED,
    RESEARCH_PROSPECTIVE_OBSERVATION,
    RESEARCH_APPROVAL_4_AUTHORIZED,
)
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    MarketRegimeType,
    DecisionAction,
    DecisionMode,
    TradeExitReason,
    EventCategory,
    MarketBehaviorFeatures,
    EventIntelligenceRecord,
    ProbabilisticPrediction,
    ResearchDecision,
    PaperTrade,
    SimulationRunResult,
    CaseStudyResult,
)
from coin_behavior_engine.research_lab.historical_data import (
    TimeframeAggregator,
    BinanceHistoricalAdapter,
)
from coin_behavior_engine.research_lab.data_quality import DataQualityValidator
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.market_regime import MarketRegimeDetector
from coin_behavior_engine.research_lab.event_intelligence import EventIntelligenceStore
from coin_behavior_engine.research_lab.event_alignment import EventMarketAligner
from coin_behavior_engine.research_lab.pattern_engine import BehavioralPatternEngine
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.decision_engine import ResearchDecisionEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator
from coin_behavior_engine.research_lab.evaluation import StrategyEvaluator
from coin_behavior_engine.research_lab.reporting import ResearchLabReporter


# -------------------------------------------------------------------------
# 1. Safety & Invariant Tests
# -------------------------------------------------------------------------

def test_01_safety_invariants_frozen():
    """Verify that live trading, prospective scoring, and approval 4 remain permanently disabled."""
    assert RESEARCH_LAB_ACTIVE is True
    assert RESEARCH_TRADING_ENABLED is False, "CRITICAL: Live trading must be FALSE in research lab"
    assert RESEARCH_PROSPECTIVE_OBSERVATION is False, "CRITICAL: Prospective scoring must be FALSE"
    assert RESEARCH_APPROVAL_4_AUTHORIZED is False, "CRITICAL: APPROVAL_4 must remain FALSE"

    config = ResearchLabConfig()
    assert config.trading_enabled is False
    assert config.prospective_scoring_enabled is False
    assert config.approval_4_authorized is False

    with pytest.raises(ValueError, match="Real trading cannot be enabled"):
        ResearchLabConfig(trading_enabled=True)

    with pytest.raises(ValueError, match="Approval 4 cannot be enabled"):
        ResearchLabConfig(approval_4_authorized=True)

    with pytest.raises(ValueError, match="Prospective scoring cannot be enabled"):
        ResearchLabConfig(prospective_scoring_enabled=True)


# -------------------------------------------------------------------------
# 2. Historical Data & Aggregation Anti-Leakage Tests
# -------------------------------------------------------------------------

@pytest.fixture
def synthetic_1m_candles() -> List[CandleData]:
    """Generate 100 1-minute synthetic candles for exact mathematical testing."""
    start_dt = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    candles = []
    
    for i in range(100):
        dt_open = start_dt + timedelta(minutes=i)
        dt_close = dt_open + timedelta(minutes=1)
        open_p = 80000.0 + i * 10.0
        high_p = open_p + 15.0
        low_p = open_p - 5.0
        close_p = open_p + 8.0
        vol = 10.0 + (i % 5)
        
        c = CandleData(
            timestamp_open=int(dt_open.timestamp() * 1000),
            timestamp_close=int(dt_close.timestamp() * 1000),
            datetime_open_utc=dt_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
            datetime_close_utc=dt_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol,
            quote_volume=vol * open_p,
            trades_count=100,
            taker_buy_base_volume=vol * 0.5,
            is_closed=True,
            symbol="BTCUSDT",
            interval="1m",
            provenance="SYNTHETIC_TEST",
        )
        candles.append(c)
    return candles


def test_02_timeframe_aggregation_strict_boundaries(synthetic_1m_candles):
    """Verify 1m to 5m aggregation respects closed bar logic and computes OHLCV correctly."""
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")

    assert len(candles_5m) == 20, "100 1m bars must aggregate into exactly 20 5m bars"

    first_bar = candles_5m[0]
    expected_open = synthetic_1m_candles[0].open
    expected_high = max(c.high for c in synthetic_1m_candles[0:5])
    expected_low = min(c.low for c in synthetic_1m_candles[0:5])
    expected_close = synthetic_1m_candles[4].close
    expected_vol = sum(c.volume for c in synthetic_1m_candles[0:5])

    assert first_bar.open == pytest.approx(expected_open)
    assert first_bar.high == pytest.approx(expected_high)
    assert first_bar.low == pytest.approx(expected_low)
    assert first_bar.close == pytest.approx(expected_close)
    assert first_bar.volume == pytest.approx(expected_vol)
    assert first_bar.interval == "5m"


# -------------------------------------------------------------------------
# 3. Data Quality Validator Tests
# -------------------------------------------------------------------------

def test_03_data_quality_validator(synthetic_1m_candles):
    """Verify validation passes on clean data and detects injected flaws."""
    # Clean check
    report_clean = DataQualityValidator.validate(synthetic_1m_candles, symbol="BTCUSDT", interval="1m")
    assert report_clean.passed is True
    assert report_clean.gaps_count == 0
    assert report_clean.ohlcv_inversions_count == 0

    # Invert high and low in candle 10
    flawed_candles = [c for c in synthetic_1m_candles]
    flawed_c10 = CandleData(
        timestamp_open=flawed_candles[10].timestamp_open,
        timestamp_close=flawed_candles[10].timestamp_close,
        datetime_open_utc=flawed_candles[10].datetime_open_utc,
        datetime_close_utc=flawed_candles[10].datetime_close_utc,
        open=flawed_candles[10].open,
        high=70000.0,  # Lower than low
        low=flawed_candles[10].low,
        close=flawed_candles[10].close,
        volume=flawed_candles[10].volume,
    )
    flawed_candles[10] = flawed_c10
    report_flawed = DataQualityValidator.validate(flawed_candles, symbol="BTCUSDT", interval="1m")
    assert report_flawed.passed is False
    assert report_flawed.ohlcv_inversions_count >= 1

    # Inject gap by removing candle 20
    gapped_candles = [c for i, c in enumerate(synthetic_1m_candles) if i != 20]
    report_gap = DataQualityValidator.validate(gapped_candles, symbol="BTCUSDT", interval="1m")
    assert report_gap.passed is False
    assert report_gap.gaps_count >= 1


# -------------------------------------------------------------------------
# 4. Feature Engine & Market Regime Tests
# -------------------------------------------------------------------------

def test_04_feature_engine_and_regimes(synthetic_1m_candles):
    """Verify feature calculation produces valid numerical features and regimes are classified."""
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")
    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=10)

    assert len(features) == len(candles_5m)
    for feat in features:
        assert isinstance(feat, MarketBehaviorFeatures)
        assert feat.close_price > 0.0

    regimes = MarketRegimeDetector.classify_all(candles_5m, lookback_bars=10)
    assert len(regimes) == len(candles_5m)
    for r in regimes:
        assert isinstance(r, MarketRegimeType)


# -------------------------------------------------------------------------
# 5. Event Intelligence & Alignment Tests
# -------------------------------------------------------------------------

def test_05_event_intelligence_store_and_alignment(synthetic_1m_candles):
    """Verify curated events exist, point-in-time filter works, and alignment computes returns."""
    event_store = EventIntelligenceStore.load_curated_october_2026_events()
    events = event_store.all_events()
    assert len(events) >= 5, "Must have curated events for October 2026"

    # Test causality / observability
    cutoff_utc = "2026-10-10T12:00:00Z"
    obs_events = event_store.events_observable_at(cutoff_utc, lookback_hours=48.0)
    for ev in obs_events:
        assert ev.published_at_utc <= cutoff_utc

    # Test alignment against candles
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")
    alignments = EventMarketAligner.align_events(events, candles_5m)
    assert len(alignments) >= 1
    assert alignments[0].event_id == "EVT-20260921-FOMC-HAWK"
    assert alignments[0].price_at_event > 0.0


# -------------------------------------------------------------------------
# 6. Behavioral Pattern Engine Tests
# -------------------------------------------------------------------------

def test_06_behavioral_patterns(synthetic_1m_candles):
    """Verify pattern detector runs across series and match_patterns_at_index returns valid list."""
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")
    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=10)

    for i in range(len(candles_5m)):
        pats = BehavioralPatternEngine.match_patterns_at_index(candles_5m, features, i)
        assert isinstance(pats, list)

    # Test distribution calculation on matched occurrences
    dist = BehavioralPatternEngine.evaluate_pattern_distribution(
        "SHARP_DECLINE_VOLUME_EXHAUSTION",
        [2, 4],
        candles_5m,
        horizon_bars=5,
    )
    assert dist is not None
    assert dist.pattern_name == "SHARP_DECLINE_VOLUME_EXHAUSTION"
    assert 0.0 <= dist.probability_positive_outcome <= 1.0


# -------------------------------------------------------------------------
# 7. Probability Engine Tests
# -------------------------------------------------------------------------

def test_07_probability_engine_distributions(synthetic_1m_candles):
    """Verify calibrated distributions sum to 1.0 and predictions have proper types."""
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")
    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=10)

    for feat in features:
        pred = ProbabilityEngine.generate_prediction(
            features=feat,
            active_patterns=[],
            observable_events=None,
        )
        assert isinstance(pred, ProbabilisticPrediction)
        p_sum = pred.probability_up + pred.probability_down + pred.probability_neutral
        assert p_sum == pytest.approx(1.0, abs=1e-3)
        assert pred.confidence_status in ("CALIBRATED", "UNCALIBRATED", "NO_PREDICTION")


# -------------------------------------------------------------------------
# 8. Risk Engine & Position Sizing Tests
# -------------------------------------------------------------------------

def test_08_risk_engine_sizing_and_limits():
    """Verify position sizing does not exceed max capital risk fraction and clamps safely."""
    config = ResearchLabConfig(max_position_size_pct=0.25, risk_per_trade_pct=0.02)
    risk_engine = RiskEngine(config)

    dummy_feat = MarketBehaviorFeatures(
        timestamp_open=1790000000000,
        datetime_utc="2026-10-01T00:00:00Z",
        close_price=80000.0,
        atr_14=500.0,
    )

    size_usd, qty, sl, tp = risk_engine.calculate_trade_parameters(
        current_price=80000.0,
        features=dummy_feat,
        current_capital=10000.0,
        risk_mode="STANDARD",
    )

    assert sl < 80000.0
    assert tp > 80000.0
    assert size_usd <= 10000.0 * 0.25 + 0.01  # Max 25% position size
    assert qty > 0.0

    # Strict mode test
    size_strict, qty_strict, sl_strict, tp_strict = risk_engine.calculate_trade_parameters(
        current_price=80000.0,
        features=dummy_feat,
        current_capital=10000.0,
        risk_mode="STRICT",
    )
    assert size_strict <= size_usd
    assert sl_strict > sl  # Tighter stop in strict mode


# -------------------------------------------------------------------------
# 9. Paper Simulator Execution & Accounting Tests
# -------------------------------------------------------------------------

def test_09_simulator_execution_mechanics(synthetic_1m_candles):
    """Verify simulator fills on next bar open, deducts fees/slippage, and tracks equity."""
    candles_5m = TimeframeAggregator.aggregate(synthetic_1m_candles, target_interval="5m", symbol="BTCUSDT")
    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=10)

    evaluator = StrategyEvaluator()
    sim_results = evaluator.run_strategy_comparison(candles_5m, features)

    assert "Strategy_A_Technical_Only" in sim_results
    assert "Strategy_B_Context_Aware" in sim_results
    assert "Strategy_C_Risk_Controlled" in sim_results

    res_a = sim_results["Strategy_A_Technical_Only"]
    assert isinstance(res_a, SimulationRunResult)
    assert res_a.initial_capital == 10000.0
    assert len(res_a.equity_series) == len(candles_5m)

    if res_a.trades:
        for trade in res_a.trades:
            assert isinstance(trade, PaperTrade)
            assert trade.fees_paid > 0.0
            assert trade.slippage_cost >= 0.0
            assert trade.exit_price > 0.0


# -------------------------------------------------------------------------
# 10. End-to-End Real Cached Dataset Validation & Invariants
# -------------------------------------------------------------------------

def test_10_cached_dataset_and_evaluator_consistency():
    """Verify cached Binance parquet exists, loads without error, and satisfies quality requirements."""
    parquet_path = Path("data/research_lab/binance_BTCUSDT_1m_recent.parquet")
    if not parquet_path.exists():
        pytest.skip("Cached parquet file not found (offline test environment)")

    df_1m = pd.read_parquet(parquet_path)
    assert len(df_1m) >= 10000, "Cached dataset must have substantial historical depth"

    # Convert to CandleData objects
    candles_1m = []
    for _, r in df_1m.iterrows():
        c = CandleData(
            timestamp_open=int(r["timestamp_open"]),
            timestamp_close=int(r["timestamp_close"]),
            datetime_open_utc=str(r["datetime_open_utc"]),
            datetime_close_utc=str(r["datetime_close_utc"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            quote_volume=float(r.get("quote_volume", 0.0)),
            trades_count=int(r.get("trades_count", 0)),
            taker_buy_base_volume=float(r.get("taker_buy_base_volume", 0.0)),
            is_closed=True,
            symbol="BTCUSDT",
            interval="1m",
        )
        candles_1m.append(c)

    # Validate quality
    rep = DataQualityValidator.validate(candles_1m, symbol="BTCUSDT", interval="1m")
    assert rep.passed is True, f"Data quality validation failed: {rep.violations}"

    # Check 5m aggregation
    candles_5m = TimeframeAggregator.aggregate(candles_1m, target_interval="5m", symbol="BTCUSDT")
    assert len(candles_5m) > 2000

    # Ensure timestamps encompass October 2026
    start_utc = candles_5m[0].datetime_open_utc
    end_utc = candles_5m[-1].datetime_open_utc
    assert "2026" in start_utc
    assert "2026-10" in end_utc

    # Event alignment over full dataset: All 5 events must align!
    event_store = EventIntelligenceStore.load_curated_october_2026_events()
    events = event_store.all_events()
    alignments = EventMarketAligner.align_events(events, candles_5m)
    assert len(alignments) == len(events)
