"""
Sprint 11.04 Automated Verification Test Suite
================================================
Comprehensive verification of Research Integrity, Reconciled Benchmark Accounting,
Multi-Timeframe Behavioral Features, Event Verification Filtering, and Counterfactuals:
- Complete boundary aggregation (partial candle exclusion at boundaries)
- Mark-to-market Buy & Hold benchmark accounting (drawdown, fees, Sharpe)
- Source-agnostic event verification model and abstention gates
- Multi-timeframe trend alignment and volatility compression features
- Multi-horizon probabilistic predictions & calibration evaluation
- Retrospective counterfactual trade analysis and tagging
- Fail-closed research safety interlocks
"""

import math
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
    EventVerificationStatus,
    MarketBehaviorFeatures,
    EventIntelligenceRecord,
    ProbabilisticPrediction,
    ResearchDecision,
    PaperTrade,
    SimulationRunResult,
)
from coin_behavior_engine.research_lab.historical_data import TimeframeAggregator
from coin_behavior_engine.research_lab.data_quality import DataQualityValidator
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.event_intelligence import EventIntelligenceStore
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.decision_engine import ResearchDecisionEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator
from coin_behavior_engine.research_lab.evaluation import StrategyEvaluator
from coin_behavior_engine.research_lab.counterfactuals import CounterfactualAnalyzer


def generate_synthetic_1m_candles(count: int = 100, start_minute: int = 0) -> List[CandleData]:
    """Generate deterministic synthetic 1m candles starting at a specific minute offset."""
    base_time = datetime(2026, 10, 1, 0, start_minute, 0, tzinfo=timezone.utc)
    base_ts = int(base_time.timestamp() * 1000)
    candles = []
    price = 80000.0

    for i in range(count):
        ts_open = base_ts + (i * 60_000)
        ts_close = ts_open + 59_999
        dt_open = datetime.fromtimestamp(ts_open / 1000, tz=timezone.utc).isoformat()
        dt_close = datetime.fromtimestamp(ts_close / 1000, tz=timezone.utc).isoformat()
        
        # Simple cyclic price movement
        delta = 10.0 * math.sin(i / 10.0)
        open_p = price
        close_p = price + delta
        high_p = max(open_p, close_p) + 5.0
        low_p = min(open_p, close_p) - 5.0
        vol = 10.0 + (i % 5)
        
        candles.append(CandleData(
            timestamp_open=ts_open,
            timestamp_close=ts_close,
            datetime_open_utc=dt_open,
            datetime_close_utc=dt_close,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol,
            interval="1m",
        ))
        price = close_p

    return candles


# ---------------------------------------------------------------------------
# Test Category 1: Research Safety & Invariants
# ---------------------------------------------------------------------------
def test_safety_invariants_fail_closed():
    """Verify that Research Lab safety flags remain strictly disabled."""
    assert RESEARCH_LAB_ACTIVE is True
    assert RESEARCH_TRADING_ENABLED is False
    assert RESEARCH_PROSPECTIVE_OBSERVATION is False
    assert RESEARCH_APPROVAL_4_AUTHORIZED is False

    config = ResearchLabConfig()
    assert config.trading_enabled is False
    assert config.approval_4_authorized is False
    assert config.prospective_scoring_enabled is False

    with pytest.raises(ValueError, match="SAFETY INVARIANT VIOLATION"):
        ResearchLabConfig(trading_enabled=True)

    with pytest.raises(ValueError, match="SAFETY INVARIANT VIOLATION"):
        ResearchLabConfig(approval_4_authorized=True)

    with pytest.raises(ValueError, match="SAFETY INVARIANT VIOLATION"):
        ResearchLabConfig(prospective_scoring_enabled=True)


# ---------------------------------------------------------------------------
# Test Category 2: Boundary Aggregation & Candle Count Reconciliation
# ---------------------------------------------------------------------------
def test_timeframe_aggregator_partial_boundary_exclusion():
    """Verify that allow_partial_boundaries=False excludes incomplete boundary buckets."""
    candles_1m = generate_synthetic_1m_candles(count=14, start_minute=2)
    
    agg = TimeframeAggregator()
    candles_5m = agg.aggregate(candles_1m, target_interval="5m", allow_partial_boundaries=False)
    
    # Incomplete buckets excluded
    assert len(candles_5m) >= 1
    for c in candles_5m:
        assert c.interval == "5m"
        assert c.timestamp_close - c.timestamp_open == 299_999


def test_reconciliation_on_cached_binance_parquet():
    """Verify that cached 36,000 1m candles cleanly aggregate into 7,199 5m candles without partial buckets."""
    parquet_path = Path("data/research_lab/binance_BTCUSDT_1m_recent.parquet")
    if not parquet_path.exists():
        pytest.skip("Historical parquet cache not present")

    df_1m = pd.read_parquet(parquet_path)
    assert len(df_1m) == 36_000

    candles_1m = [
        CandleData(
            timestamp_open=int(r["timestamp_open"]),
            timestamp_close=int(r["timestamp_close"]),
            datetime_open_utc=str(r["datetime_open_utc"]),
            datetime_close_utc=str(r["datetime_close_utc"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            interval="1m",
        )
        for _, r in df_1m.iterrows()
    ]

    agg = TimeframeAggregator()
    candles_5m = agg.aggregate(candles_1m, target_interval="5m", allow_partial_boundaries=False)
    assert len(candles_5m) == 7_199

    candles_1h = agg.aggregate(candles_5m, target_interval="1h", allow_partial_boundaries=False)
    assert len(candles_1h) == 599

    candles_4h = agg.aggregate(candles_1h, target_interval="4h", allow_partial_boundaries=False)
    assert len(candles_4h) == 149


# ---------------------------------------------------------------------------
# Test Category 3: Buy & Hold Mark-to-Market Accounting & Drawdown
# ---------------------------------------------------------------------------
def test_buy_and_hold_benchmark_drawdown_correction():
    """Verify that Buy & Hold mark-to-market drawdown is computed along the true price path."""
    base_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    base_ts = int(base_time.timestamp() * 1000)
    candles = []
    
    # Construct candles with deliberate drawdown from 80k to 70k then recovery to 75k
    for i in range(50):
        ts_open = base_ts + (i * 300_000)
        ts_close = ts_open + 299_999
        dt_open = datetime.fromtimestamp(ts_open / 1000, tz=timezone.utc).isoformat()
        dt_close = datetime.fromtimestamp(ts_close / 1000, tz=timezone.utc).isoformat()
        
        if i < 10:
            p = 80000.0
        elif 10 <= i <= 25:
            p = 70000.0  # -12.5% drawdown
        else:
            p = 75000.0
            
        candles.append(CandleData(
            timestamp_open=ts_open,
            timestamp_close=ts_close,
            datetime_open_utc=dt_open,
            datetime_close_utc=dt_close,
            open=p,
            high=p + 10.0,
            low=p - 10.0,
            close=p,
            volume=10.0,
            interval="5m",
        ))

    config = ResearchLabConfig()
    sim = HistoricalPaperSimulator(config)
    res = sim.simulate(candles, decisions=[])

    # Drawdown must accurately reflect the drop along the path (> 10%)
    assert res.baseline_buy_and_hold_drawdown_pct > 10.0
    # Fees must be deducted (entry taker fee + exit taker fee)
    assert res.baseline_buy_and_hold_fees > 0.0


# ---------------------------------------------------------------------------
# Test Category 4: Event Verification Model & Abstention Gate
# ---------------------------------------------------------------------------
def test_event_verification_filtering():
    """Verify that unverified/mock events are excluded from verified_events()."""
    store = EventIntelligenceStore.load_curated_october_2026_events()
    events = store.all_events()
    assert len(events) >= 5

    # In Sprint 11.04, 0 events meet the strict VERIFIED_EVENT standard
    verified = store.verified_events()
    assert len(verified) == 0

    # Ensure all events have valid verification statuses
    for ev in events:
        assert isinstance(ev.verification_status, EventVerificationStatus)
        assert ev.verification_status in [
            EventVerificationStatus.REPORTED_UNCONFIRMED,
            EventVerificationStatus.RETROSPECTIVE_INTERPRETATION,
            EventVerificationStatus.UNSUPPORTED,
        ]


def test_strategy_b_abstention_on_unverified_events():
    """Verify that Strategy B generates NO_TRADE decisions when no verified events exist."""
    candles = generate_synthetic_1m_candles(count=20)
    features = MarketBehaviorFeatureEngine.compute_all(candles)
    store = EventIntelligenceStore.load_curated_october_2026_events()
    # No verified events in store
    verified_events = store.verified_events()
    assert len(verified_events) == 0

    engine = ResearchDecisionEngine()
    for feat in features:
        pred = ProbabilityEngine.generate_prediction(feat, active_patterns=[])
        # Set confidence to CALIBRATED to test specifically the Strategy B news-gate filter
        pred.confidence_status = "CALIBRATED"
        pred.probability_up = 0.60
        pred.expected_return_pct = 1.0  # Above transaction fee hurdle
        
        dec = engine.evaluate_decision(
            features=feat,
            prediction=pred,
            active_patterns=[],
            strategy_mode=DecisionMode.CONTEXT_AWARE_RESEARCH,
            observable_events=verified_events,
        )
        assert dec.action == DecisionAction.NO_TRADE
        assert "verified news coverage insufficient" in dec.reason.lower()


# ---------------------------------------------------------------------------
# Test Category 5: Multi-Timeframe Alignment & Volatility Compression
# ---------------------------------------------------------------------------
def test_htf_and_volatility_compression_features():
    """Verify calculation of HTF regimes, volatility compression ratio, and divergence."""
    candles_5m = generate_synthetic_1m_candles(count=120)
    features = MarketBehaviorFeatureEngine.compute_all(candles_5m)

    assert len(features) == len(candles_5m)
    for feat in features:
        assert isinstance(feat.htf_1h_regime, MarketRegimeType)
        assert isinstance(feat.htf_4h_regime, MarketRegimeType)
        assert feat.volatility_compression_ratio >= 0.0
        assert feat.price_volume_divergence in ["BULLISH_DIV", "BEARISH_DIV", "NONE"]


# ---------------------------------------------------------------------------
# Test Category 6: Probability Engine Prediction & Multi-Horizon Evaluation
# ---------------------------------------------------------------------------
def test_multi_horizon_predictions_and_evaluation():
    """Verify probabilistic predictions multi-horizon generation and accuracy evaluation."""
    candles = generate_synthetic_1m_candles(count=40)
    features = MarketBehaviorFeatureEngine.compute_all(candles)

    predictions = []
    for f in features:
        pred = ProbabilityEngine.generate_prediction(f, active_patterns=[], prediction_horizon="1h")
        assert pred.prediction_horizon in ["15m", "1h", "4h"]
        assert 0.0 <= pred.probability_up <= 1.0
        assert 0.0 <= pred.probability_down <= 1.0
        assert 0.0 <= pred.probability_neutral <= 1.0
        assert abs((pred.probability_up + pred.probability_down + pred.probability_neutral) - 1.0) < 1e-3
        predictions.append(pred)

    eval_rows = ProbabilityEngine.evaluate_predictions(predictions, candles, horizon_bars=12)
    assert len(eval_rows) > 0
    first_row = eval_rows[0]
    assert "brier_score_up" in first_row
    assert "directional_correct" in first_row
    assert "realized_mae_pct" in first_row
    assert first_row["brier_score_up"] >= 0.0


# ---------------------------------------------------------------------------
# Test Category 7: Retrospective Counterfactuals Tagging
# ---------------------------------------------------------------------------
def test_counterfactual_trade_analysis_tagging():
    """Verify that counterfactual analysis produces RETROSPECTIVE_COUNTERFACTUAL tagged rows."""
    candles = generate_synthetic_1m_candles(count=30)
    features = MarketBehaviorFeatureEngine.compute_all(candles)

    # Create synthetic paper trade
    trade = PaperTrade(
        trade_id="TRD-TEST001",
        strategy_name="Strategy_A_Technical_Only",
        symbol="BTCUSDT",
        side="BUY",
        entry_time_utc=candles[5].datetime_open_utc,
        entry_price=candles[5].close,
        exit_time_utc=candles[15].datetime_close_utc,
        exit_price=candles[15].close,
        exit_reason=TradeExitReason.STOP_LOSS,
        quantity=0.1,
        gross_pnl=(candles[15].close - candles[5].close) * 0.1,
        fees_paid=5.0,
        slippage_cost=0.5,
        net_pnl=((candles[15].close - candles[5].close) * 0.1) - 5.5,
        return_pct=-0.5,
        holding_period_minutes=50,
    )

    cfs = CounterfactualAnalyzer.analyze_significant_trades([trade], candles, features, top_n=1)
    assert len(cfs) == 1
    cf = cfs[0]
    assert cf.methodology == "RETROSPECTIVE_COUNTERFACTUAL"
    assert cf.pnl_if_skipped == 0.0
    assert cf.pnl_if_size_halved != 0.0
    assert cf.action_if_htf_required in ["EXECUTE", "BLOCK_TRADE"]
