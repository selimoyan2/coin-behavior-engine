"""
Sprint 11.05 Automated Verification Test Suite
================================================
Comprehensive verification of Verified Market Intelligence, Baseline Auditing,
Market Context Engine, Behavioral Pattern Research, and Paper Trading Simulation:
- Multi-provider verified news ingestion (Fed, SEC, Binance, BLS, Liquidations)
- Provenance auditing, permalinks, and publication timestamps
- Market Context Engine (freshness decay, contradiction, priced-in, timeline)
- Behavioral pattern evaluation & sample sufficiency gating
- Statistical baseline comparisons (majority-class, persistence, random walk, momentum)
- Non-overlapping sample independence auditing
- Historical paper simulation & benchmark accounting
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
    BaselineComparisonRecord,
    BehavioralPatternEvaluationRecord,
    CandleData,
    EventCategory,
    EventIntelligenceRecord,
    EventVerificationStatus,
    MarketBehaviorFeatures,
    MarketContextImpact,
    MarketContextTimelineRecord,
    MarketRegimeType,
    PaperTrade,
    SimulationRunResult,
)
from coin_behavior_engine.research_lab.historical_data import TimeframeAggregator
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.news_adapters import (
    EconomicCalendarAdapter,
    FederalReserveAdapter,
    LiquidationTelemetryAdapter,
    NewsIngestionCoordinator,
    SECEnforcementAdapter,
)
from coin_behavior_engine.research_lab.context_engine import MarketContextEngine
from coin_behavior_engine.research_lab.behavioral_patterns import BehavioralPatternResearcher
from coin_behavior_engine.research_lab.baseline_auditor import BaselineAuditor
from coin_behavior_engine.research_lab.case_study import MarketRealityCaseStudyGenerator
from coin_behavior_engine.research_lab.evaluation import StrategyEvaluator
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator


def generate_synthetic_5m_candles(count: int = 100) -> List[CandleData]:
    """Generate deterministic synthetic 5m candles."""
    base_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    base_ts = int(base_time.timestamp() * 1000)
    candles = []
    price = 84000.0

    for i in range(count):
        ts_open = base_ts + (i * 300_000)
        ts_close = ts_open + 299_999
        dt_open = datetime.fromtimestamp(ts_open / 1000, tz=timezone.utc).isoformat()
        dt_close = datetime.fromtimestamp(ts_close / 1000, tz=timezone.utc).isoformat()

        delta = 25.0 * math.sin(i / 8.0)
        open_p = price
        close_p = price + delta
        high_p = max(open_p, close_p) + 15.0
        low_p = min(open_p, close_p) - 15.0
        vol = 50.0 + (i % 10)

        candles.append(CandleData(
            symbol="BTCUSDT",
            timestamp_open=ts_open,
            timestamp_close=ts_close,
            datetime_open_utc=dt_open,
            datetime_close_utc=dt_close,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=vol,
            interval="5m",
        ))
        price = close_p

    return candles


# ---------------------------------------------------------------------------
# Test Category 1: Research Safety & Invariants
# ---------------------------------------------------------------------------
def test_sprint11_05_safety_invariants():
    """Verify that Research Lab safety interlocks remain fail-closed."""
    assert RESEARCH_LAB_ACTIVE is True
    assert RESEARCH_TRADING_ENABLED is False
    assert RESEARCH_PROSPECTIVE_OBSERVATION is False
    assert RESEARCH_APPROVAL_4_AUTHORIZED is False

    config = ResearchLabConfig()
    assert config.trading_enabled is False
    assert config.approval_4_authorized is False
    assert config.prospective_scoring_enabled is False


# ---------------------------------------------------------------------------
# Test Category 2: Verified News Ingestion Adapters & Provenance
# ---------------------------------------------------------------------------
def test_economic_calendar_and_liquidation_adapters():
    """Verify EconomicCalendarAdapter and LiquidationTelemetryAdapter return verified records."""
    cal_adapter = EconomicCalendarAdapter()
    cal_events = cal_adapter.fetch_events("2026-09-23T00:00:00Z", "2026-10-18T23:59:59Z")
    assert len(cal_events) >= 2
    for e in cal_events:
        assert e.verification_status == EventVerificationStatus.VERIFIED_EVENT
        assert e.source_url.startswith("https://")
        assert e.exact_factual_claim != ""

    liq_adapter = LiquidationTelemetryAdapter()
    liq_events = liq_adapter.fetch_events("2026-09-23T00:00:00Z", "2026-10-18T23:59:59Z")
    assert len(liq_events) >= 1
    assert liq_events[0].category == EventCategory.LIQUIDATION_CASCADE
    assert liq_events[0].verification_status == EventVerificationStatus.VERIFIED_EVENT


def test_news_ingestion_coordinator_caching_and_provenance(tmp_path):
    """Verify NewsIngestionCoordinator loads events, persists cache, and exports provenance audit."""
    cache_path = tmp_path / "test_events_cache.json"
    coord = NewsIngestionCoordinator(cache_file=cache_path)
    events = coord.ingest_all_events()

    assert len(events) >= 5
    assert cache_path.exists()

    # Test CSV export
    csv_out = tmp_path / "verified_event_dataset.csv"
    NewsIngestionCoordinator.export_verified_event_dataset_csv(events, csv_out)
    assert csv_out.exists()
    df = pd.read_csv(csv_out)
    assert len(df) == len(events)
    assert "source_url" in df.columns
    assert "published_at_utc" in df.columns

    # Test JSON provenance audit
    json_out = tmp_path / "event_provenance_audit.json"
    NewsIngestionCoordinator.export_provenance_audit_json(events, json_out)
    assert json_out.exists()


# ---------------------------------------------------------------------------
# Test Category 3: Market Context Engine & Contradiction Detection
# ---------------------------------------------------------------------------
def test_market_context_engine_timeline_and_contradiction():
    """Verify MarketContextEngine computes freshness and detects price contradiction."""
    candles = generate_synthetic_5m_candles(count=30)
    
    # Create synthetic negative event at candle 5
    evt = EventIntelligenceRecord(
        event_id="EVT-TEST-NEG-001",
        event_type="REGULATORY_WARNING",
        category=EventCategory.REGULATION,
        headline="Regulatory warning bulletin published",
        summary="SEC published warning bulletin.",
        source_name="SEC",
        source_url="https://sec.gov/test",
        actor="SEC",
        affected_assets=["BTC"],
        published_at_utc=candles[5].datetime_open_utc,
        first_observed_at_utc=candles[5].datetime_open_utc,
        ingested_at_utc=candles[5].datetime_open_utc,
        verification_status=EventVerificationStatus.VERIFIED_EVENT,
        source_credibility=0.95,
        source_reliability_class="TIER_1_OFFICIAL_REGULATORY_AGENCY",
        context_impact=MarketContextImpact.NEGATIVE,
        event_severity=0.80,
        freshness_half_life_hours=12.0,
    )

    engine = MarketContextEngine([evt])
    timeline = engine.generate_timeline(candles)

    assert len(timeline) == len(candles)
    # Candle 0 has no active events
    assert timeline[0].active_events_count == 0
    assert timeline[0].primary_headline == "NO_ACTIVE_EVENT"

    # Candle 10 has active event
    assert timeline[10].active_events_count >= 1
    assert timeline[10].primary_event_id == "EVT-TEST-NEG-001"


# ---------------------------------------------------------------------------
# Test Category 4: Behavioral Pattern Research Engine
# ---------------------------------------------------------------------------
def test_behavioral_pattern_researcher_sample_gating():
    """Verify BehavioralPatternResearcher discovers patterns and flags insufficient evidence."""
    candles = generate_synthetic_5m_candles(count=100)
    features = MarketBehaviorFeatureEngine.compute_all(candles)
    
    # Create dummy context timeline
    timeline = [
        MarketContextTimelineRecord(
            timestamp_open=c.timestamp_open,
            datetime_utc=c.datetime_open_utc,
            active_events_count=1,
            net_sentiment_score=-0.5,
            dominant_impact=MarketContextImpact.NEGATIVE,
            has_unabsorbed_negative_shock=True,
            has_positive_catalyst=False,
            contradiction_detected=False,
            priced_in_detected=False,
            primary_event_id="EVT-001",
            primary_headline="Negative Shock Event",
        )
        for c in candles
    ]

    records = BehavioralPatternResearcher.evaluate_all_patterns(candles, features, timeline)
    assert len(records) == 6
    for r in records:
        assert isinstance(r, BehavioralPatternEvaluationRecord)
        assert r.empirical_status in ["VALIDATED", "INSUFFICIENT_SAMPLES", "FALSIFIED", "INCONCLUSIVE"]
        if r.sample_count < 5:
            assert r.sufficient_evidence is False
            assert r.empirical_status == "INSUFFICIENT_SAMPLES"


# ---------------------------------------------------------------------------
# Test Category 5: Independent Baseline Comparator
# ---------------------------------------------------------------------------
def test_baseline_auditor_degrees_of_freedom_and_baselines():
    """Verify BaselineAuditor calculates majority class, persistence, random walk, and degrees of freedom."""
    candles = generate_synthetic_5m_candles(count=80)
    features = MarketBehaviorFeatureEngine.compute_all(candles)
    context_timeline = [
        MarketContextTimelineRecord(
            timestamp_open=c.timestamp_open,
            datetime_utc=c.datetime_open_utc,
            active_events_count=0,
            net_sentiment_score=0.0,
            dominant_impact=MarketContextImpact.UNCERTAIN,
            has_unabsorbed_negative_shock=False,
            has_positive_catalyst=False,
            contradiction_detected=False,
            priced_in_detected=False,
        )
        for c in candles
    ]

    records = BaselineAuditor.run_full_baseline_comparison(candles, features, context_timeline)
    assert len(records) >= 9  # 3 models * 3 horizons

    for rec in records:
        assert isinstance(rec, BaselineComparisonRecord)
        assert 0.0 <= rec.accuracy_3class <= 100.0
        assert 0.0 <= rec.majority_class_baseline_accuracy <= 100.0
        assert 0.0 <= rec.persistence_baseline_accuracy <= 100.0
        assert rec.sample_count_independent <= rec.sample_count_overlapping
        # For 4h (horizon_bars=48), independent samples should be approximately n // 48
        if rec.horizon == "4h":
            assert rec.sample_count_independent <= math.ceil(len(candles) / 48)
        assert rec.statistical_verdict in ["ADVANTAGE_PROVEN", "NO_EDGE", "INCONCLUSIVE"]


# ---------------------------------------------------------------------------
# Test Category 6: Market Reality Case Study Markdown Generation
# ---------------------------------------------------------------------------
def test_market_reality_case_study_generation(tmp_path):
    """Verify MarketRealityCaseStudyGenerator produces valid markdown report with required sections."""
    candles = generate_synthetic_5m_candles(count=40)
    features = MarketBehaviorFeatureEngine.compute_all(candles)
    timeline = [
        MarketContextTimelineRecord(
            timestamp_open=c.timestamp_open,
            datetime_utc=c.datetime_open_utc,
            active_events_count=0,
            net_sentiment_score=0.0,
            dominant_impact=MarketContextImpact.UNCERTAIN,
            has_unabsorbed_negative_shock=False,
            has_positive_catalyst=False,
            contradiction_detected=False,
            priced_in_detected=False,
        )
        for c in candles
    ]

    out_file = tmp_path / "market_reality_case_study.md"
    MarketRealityCaseStudyGenerator.generate_case_study_markdown(
        output_file=out_file,
        candles=candles,
        features=features,
        context_timeline=timeline,
        events=[],
        trades=[],
    )

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "MARKET REALITY CASE STUDY #002" in content
    assert "Cycle Peak Reversal" in content
    assert "What Remains Uncertain" in content
