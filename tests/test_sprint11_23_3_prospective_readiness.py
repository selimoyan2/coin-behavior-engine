"""
Sprint 11.23.3: Prospective Evidence Collection & Observation Readiness Test Suite
Executes comprehensive tests covering:
1. Prospective event registry and timezone normalization.
2. Schedule revision tracking without silent overwrites.
3. Source adapter document retrieval, byte preservation, and failure classification.
4. Consensus vintage rule enforcement and anti-retrospective calendar guard.
5. Content-addressed immutable evidence vault, atomic writes, and corruption detection.
6. BTC/USDT market observation architecture and candle integrity checks.
7. Event lifecycle state machine and exceptional quarantine states.
8. Execution of all 15 deterministic failure and robustness simulation scenarios.
9. Performance safety guards: bounded queues, rate limiters, and checkpointing.
10. Governance and trading isolation enforcement.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import pandas as pd
import pytest

from coin_behavior_engine.prospective import (
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ReleaseDocument,
    AdapterFailureReason,
    ProspectiveEventRegistry,
    BLSSourceAdapter,
    BEASourceAdapter,
    FederalReserveSourceAdapter,
    CryptoProtocolAdapter,
    ConsensusEvidenceRegistry,
    ImmutableEvidenceVault,
    ProspectiveMarketObserver,
    MarketCandle,
    EventStateMachine,
    EventLifecycleTransitionError,
    ProspectiveSimulationRunner,
    BoundedEventQueue,
    RateLimiter,
    CheckpointManager,
    ProspectiveGovernanceGuard,
    TradingIsolationViolation,
)

ROOT_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# TEST 1: Prospective Event Registry & Timezone Normalization
# ---------------------------------------------------------------------------
def test_01_prospective_event_registry_and_timezone():
    reg = ProspectiveEventRegistry()
    # US CPI: 08:30 New York (Eastern) -> 13:30 UTC (standard time) or 12:30 UTC (daylight time)
    # 2026-11-12 is Standard Time (UTC-5) -> 13:30 UTC
    ev = reg.register_scheduled_event(
        event_id="PRSP-BLS-CPI-20261112",
        category=ProspectiveEventCategory.US_INFLATION,
        indicator="CPI_YOY",
        issuing_org="Bureau of Labor Statistics",
        official_url="https://www.bls.gov/cpi",
        scheduled_local_str="2026-11-12T08:30:00",
        local_tz_name="America/New_York",
        schedule_verification_utc="2026-11-01T12:00:00Z",
        timestamp_uncertainty_seconds=30.0
    )
    assert ev.event_id == "PRSP-BLS-CPI-20261112"
    assert ev.scheduled_publication_at_utc == "2026-11-12T13:30:00Z"
    assert ev.event_status == ProspectiveEventStatus.SCHEDULE_VERIFIED
    assert ev.directional_trading_eligible is False
    assert len(ev.revision_history) == 1

# ---------------------------------------------------------------------------
# TEST 2: Schedule Revision Tracking Without Silent Overwrites
# ---------------------------------------------------------------------------
def test_02_schedule_revision_tracking():
    reg = ProspectiveEventRegistry()
    reg.register_scheduled_event(
        event_id="PRSP-FED-FOMC-20261104",
        category=ProspectiveEventCategory.US_MONETARY_POLICY,
        indicator="FOMC_RATE_DECISION",
        issuing_org="Federal Reserve Board",
        official_url="https://federalreserve.gov",
        scheduled_local_str="2026-11-04T14:00:00",
        local_tz_name="America/New_York",
        schedule_verification_utc="2026-10-15T00:00:00Z"
    )

    # Agency reschedules release
    updated = reg.update_schedule(
        event_id="PRSP-FED-FOMC-20261104",
        new_scheduled_local_str="2026-11-04T14:30:00",
        verification_utc="2026-10-25T12:00:00Z",
        reason="Fed announced 30-minute delay for special briefing"
    )

    assert updated.scheduled_publication_at_utc == "2026-11-04T19:30:00Z" # 14:30 EST = 19:30 UTC
    assert len(updated.revision_history) == 2
    rev = updated.revision_history[1]
    assert rev["old_value"] == "2026-11-04T19:00:00Z"
    assert rev["new_value"] == "2026-11-04T19:30:00Z"
    assert "30-minute delay" in rev["reason"]

# ---------------------------------------------------------------------------
# TEST 3: Source Adapters Retrieval & Byte-Level SHA-256 Calculation
# ---------------------------------------------------------------------------
def test_03_source_adapters_retrieval_and_hashing():
    adapter = BLSSourceAdapter()
    sample_bytes = b"Official Bureau of Labor Statistics PDF Report bytes"
    expected_sha = hashlib.sha256(sample_bytes).hexdigest()

    doc = adapter.fetch_release_document(
        event_id="PRSP-BLS-CPI-TEST",
        target_url="https://www.bls.gov/news.release/cpi.nr0.htm",
        mock_transport=lambda url: {
            "status_code": 200,
            "content_type": "text/html; charset=utf-8",
            "content": sample_bytes
        }
    )

    assert doc.http_status == 200
    assert doc.raw_bytes == sample_bytes
    assert doc.raw_sha256 == expected_sha
    assert doc.failure_reason == AdapterFailureReason.NONE

# ---------------------------------------------------------------------------
# TEST 4: Transparent Classification of HTTP 403, 429, and Gaps
# ---------------------------------------------------------------------------
def test_04_adapter_failure_classification():
    adapter = BEASourceAdapter()

    # Test 403
    doc_403 = adapter.fetch_release_document(
        event_id="TEST-403",
        target_url="https://www.bea.gov/secret",
        mock_transport=lambda u: {"status_code": 403, "content": b"Forbidden"}
    )
    assert doc_403.failure_reason == AdapterFailureReason.HTTP_403_FORBIDDEN

    # Test 429 Rate Limit
    doc_429 = adapter.fetch_release_document(
        event_id="TEST-429",
        target_url="https://www.bea.gov/data",
        mock_transport=lambda u: {"status_code": 429, "content": b"Rate Limited", "headers": {"Retry-After": "120"}}
    )
    assert doc_429.failure_reason == AdapterFailureReason.HTTP_429_RATE_LIMITED
    assert doc_429.metadata["headers"]["Retry-After"] == "120"

# ---------------------------------------------------------------------------
# TEST 5: Consensus Vintage Rule & Rejection of Late Surveys
# ---------------------------------------------------------------------------
def test_05_consensus_vintage_rule_enforcement():
    c_reg = ConsensusEvidenceRegistry()

    # Valid vintage: survey published before event
    valid_rec = c_reg.register_consensus_survey(
        event_id="EVT-01",
        provider_name="Reuters Polling",
        survey_value=3.1,
        survey_unit="percent",
        survey_published_at_utc="2026-11-12T12:00:00Z",
        first_observed_at_utc="2026-11-12T12:05:00Z",
        retrieved_at_utc="2026-11-12T12:05:10Z",
        official_release_scheduled_utc="2026-11-12T13:30:00Z",
        original_document_ref="vault://consensus/cpi_poll.json",
        raw_document_sha256="a" * 64
    )
    assert valid_rec.verification_status == ConsensusVerificationStatus.CONSENSUS_VERIFIED

    # Late vintage: survey published after event
    late_rec = c_reg.register_consensus_survey(
        event_id="EVT-02",
        provider_name="Late Survey",
        survey_value=3.1,
        survey_unit="percent",
        survey_published_at_utc="2026-11-12T13:35:00Z", # Late!
        first_observed_at_utc="2026-11-12T13:35:00Z",
        retrieved_at_utc="2026-11-12T13:35:10Z",
        official_release_scheduled_utc="2026-11-12T13:30:00Z",
        original_document_ref="vault://consensus/late.json",
        raw_document_sha256="b" * 64
    )
    assert late_rec.verification_status == ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED

# ---------------------------------------------------------------------------
# TEST 6: Anti-Retrospective Calendar Matching Guard
# ---------------------------------------------------------------------------
def test_06_anti_retrospective_calendar_matching_guard():
    c_reg = ConsensusEvidenceRegistry()
    # Attempting to verify consensus based on retrospective calendar number without contemporaneous bytes
    retro_rec = c_reg.register_consensus_survey(
        event_id="EVT-03",
        provider_name="Retrospective Calendar",
        survey_value=2.9,
        survey_unit="percent",
        survey_published_at_utc="2026-11-12T10:00:00Z",
        first_observed_at_utc="2026-11-12T10:00:00Z",
        retrieved_at_utc="2026-11-12T10:00:00Z",
        official_release_scheduled_utc="2026-11-12T13:30:00Z",
        original_document_ref=None,
        raw_document_sha256=None,
        is_retrospective_calendar_match=True
    )
    assert retro_rec.verification_status == ConsensusVerificationStatus.CONSENSUS_UNVERIFIED
    assert "RETROSPECTIVE_NUMERICAL_MATCH" in retro_rec.rejection_reason

# ---------------------------------------------------------------------------
# TEST 7: Immutable Evidence Vault: Atomic Write, Dedup, and Journal
# ---------------------------------------------------------------------------
def test_07_immutable_evidence_vault_operations(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    data = b"Federal Open Market Committee Meeting Minutes Statement"
    sha = hashlib.sha256(data).hexdigest()

    # First write
    sha_out, fpath, is_dup = vault.store_bytes("releases", data, {"event_id": "FOMC-01"})
    assert sha_out == sha
    assert fpath.exists()
    assert is_dup is False

    # Second write: Duplicate detection must avoid rewrite
    sha_dup, fpath_dup, is_dup_2 = vault.store_bytes("releases", data, {"event_id": "FOMC-01-RETRY"})
    assert sha_dup == sha
    assert fpath_dup == fpath
    assert is_dup_2 is True

    # Audit journal check
    assert vault.journal_path.exists()
    with open(vault.journal_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1 # Only one original write logged

# ---------------------------------------------------------------------------
# TEST 8: Vault Corruption Detection
# ---------------------------------------------------------------------------
def test_08_vault_corruption_detection(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    data = b"Original Authentic Release Document Bytes"
    sha, fpath, _ = vault.store_bytes("releases", data, {"event_id": "EVT-TEST"})

    # Tamper with file
    with open(fpath, "wb") as f:
        f.write(b"Tampered and corrupted content")

    audit = vault.verify_vault_integrity()
    assert audit["status"] == "CORRUPTION_DETECTED"
    assert audit["total_corrupt"] == 1
    assert audit["corrupt_files"][0]["expected_sha"] == sha

# ---------------------------------------------------------------------------
# TEST 9: Market Observer: OHLCV Validation & Missing Gaps
# ---------------------------------------------------------------------------
def test_09_market_observer_ohlcv_validation_and_gaps():
    observer = ProspectiveMarketObserver()
    
    # Valid candle
    c_valid = MarketCandle(
        timestamp_utc="2026-11-12T13:30:00Z",
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=50.0
    )
    ok, err = c_valid.validate_ohlcv()
    assert ok is True

    # Invalid candle: High < Open
    c_invalid = MarketCandle(
        timestamp_utc="2026-11-12T13:30:00Z",
        open=100.0,
        high=95.0,
        low=90.0,
        close=92.0,
        volume=50.0
    )
    ok, err = c_invalid.validate_ohlcv()
    assert ok is False
    assert err == "HIGH_VIOLATION"

    # Test Gap Detection in DataFrame
    times = [
        datetime(2026, 11, 12, 13, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 12, 13, 5, tzinfo=timezone.utc),
        datetime(2026, 11, 12, 13, 20, tzinfo=timezone.utc) # 15 min gap!
    ]
    df = pd.DataFrame({
        "datetime": times,
        "open": [100.0, 101.0, 102.0],
        "high": [102.0, 103.0, 104.0],
        "low": [99.0, 100.0, 101.0],
        "close": [101.0, 102.0, 103.0],
        "volume": [10.0, 12.0, 15.0]
    })
    _, meta = observer.clean_and_validate_candles(df, expected_freq_minutes=5)
    assert meta["status"] == "GAPS_DETECTED"
    assert meta["missing_count"] == 2

# ---------------------------------------------------------------------------
# TEST 10: Multi-Horizon Event Reaction Observation & Zero Trading Signal
# ---------------------------------------------------------------------------
def test_10_market_observation_metrics_and_zero_trade_signal():
    observer = ProspectiveMarketObserver()
    # 350 bars of 5m data covering pre and post windows
    times = [datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=5*i) for i in range(350)]
    df = pd.DataFrame({
        "datetime": times,
        "open": [100.0 + i*0.1 for i in range(350)],
        "high": [101.0 + i*0.1 for i in range(350)],
        "low": [99.0 + i*0.1 for i in range(350)],
        "close": [100.5 + i*0.1 for i in range(350)],
        "volume": [100.0 for _ in range(350)]
    })

    rep = observer.observe_event_window(
        event_id="EVT-OBS-01",
        t_pub_utc_str="2026-11-12T13:30:00Z",
        uncertainty_seconds=30.0,
        market_df=df,
        timeframe_minutes=5
    )

    assert rep.data_continuity_status == "VALID"
    assert rep.post_15m_abs_ret_pct > 0.0
    assert rep.directional_trading_signal == "NONE_PROHIBITED"
    assert rep.portfolio_allocation_authorized is False

# ---------------------------------------------------------------------------
# TEST 11: Event Lifecycle State Machine Gates
# ---------------------------------------------------------------------------
def test_11_event_lifecycle_state_machine():
    ev = ProspectiveEventRecord(
        event_id="EVT-SM-01",
        event_category=ProspectiveEventCategory.US_INFLATION,
        indicator="CPI_YOY",
        issuing_organization="BLS",
        official_source_url="https://bls.gov",
        scheduled_publication_at_utc="2026-11-12T13:30:00Z",
        schedule_verification_at_utc="2026-11-01T00:00:00Z",
        original_timezone="America/New_York",
        event_status=ProspectiveEventStatus.DISCOVERED,
        timestamp_uncertainty_seconds=30.0
    )

    # 1. DISCOVERED -> SCHEDULE_VERIFIED
    ev = EventStateMachine.transition_to_schedule_verified(ev, "2026-11-01T00:00:00Z")
    assert ev.event_status == ProspectiveEventStatus.SCHEDULE_VERIFIED

    # 2. SCHEDULE_VERIFIED -> AWAITING_RELEASE
    ev = EventStateMachine.transition_to_awaiting_release(ev)
    assert ev.event_status == ProspectiveEventStatus.AWAITING_RELEASE

    # 3. AWAITING_RELEASE -> RELEASE_OBSERVED
    ev = EventStateMachine.transition_to_release_observed(ev, "2026-11-12T13:30:15Z", 30.0)
    assert ev.event_status == ProspectiveEventStatus.RELEASE_OBSERVED

    # 4. RELEASE_OBSERVED -> SOURCE_EVIDENCE_CAPTURED
    doc = ReleaseDocument(
        event_id="EVT-SM-01",
        source_url="https://bls.gov",
        http_status=200,
        content_type="text/html",
        raw_bytes=b"sample release content",
        raw_sha256="c" * 64,
        retrieved_at_utc="2026-11-12T13:30:20Z"
    )
    ev = EventStateMachine.transition_to_evidence_captured(ev, doc)
    assert ev.event_status == ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED

    # 5. SOURCE_EVIDENCE_CAPTURED -> MARKET_OBSERVATION_COMPLETE
    ev = EventStateMachine.transition_to_observation_complete(ev, missing_candles_count=0)
    assert ev.event_status == ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE

    # 6. MARKET_OBSERVATION_COMPLETE -> RESEARCH_ELIGIBILITY_REVIEW
    st, audit = EventStateMachine.evaluate_research_eligibility(ev)
    assert st == ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW
    assert ev.directional_trading_eligible is False
    assert audit["directional_trading_permitted"] is False

# ---------------------------------------------------------------------------
# TEST 12: Deterministic Simulation Suite: All 15 Scenarios Pass
# ---------------------------------------------------------------------------
def test_12_simulation_scenarios_all_pass(tmp_path):
    sim_results = ProspectiveSimulationRunner.run_all_scenarios(tmp_path)
    assert sim_results["simulation_run_status"] == "PASS"
    assert sim_results["scenarios_passed_count"] == 15
    assert sim_results["scenarios_tested_count"] == 15

# ---------------------------------------------------------------------------
# TEST 13: Performance Guards: Bounded Queue & Rate Limiting
# ---------------------------------------------------------------------------
def test_13_performance_safety_guards():
    # Bounded queue
    q = BoundedEventQueue(max_capacity=3)
    assert q.push("item1") is True
    assert q.push("item2") is True
    assert q.push("item3") is True
    # 4th item rejected due to bound
    assert q.push("item4") is False
    assert q.overflow_rejections == 1
    assert len(q) == 3

    # Rate limiter
    limiter = RateLimiter(requests_per_minute=60.0, burst_limit=2)
    # First 2 should succeed from burst
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    # 3rd immediate acquire should throttle
    assert limiter.acquire() is False
    assert limiter.throttled_count == 1

# ---------------------------------------------------------------------------
# TEST 14: Governance & Trading Isolation
# ---------------------------------------------------------------------------
def test_14_governance_and_trading_isolation():
    # 1. Clean environment
    env_audit = ProspectiveGovernanceGuard.verify_clean_environment()
    assert env_audit["trading_isolation_status"] == "PASS"
    assert env_audit["directional_trading_authorization"] == "STRICTLY_PROHIBITED"

    # 2. Assert evidence non-tradable
    clean_event = {"event_id": "TEST-01", "directional_trading_eligible": False}
    ProspectiveGovernanceGuard.assert_evidence_non_tradable(clean_event) # Should not raise

    # Attempting to set directional_trading_eligible to True raises TradingIsolationViolation
    violating_event = {"event_id": "TEST-02", "directional_trading_eligible": True}
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_evidence_non_tradable(violating_event)

    # 3. Audit loaded modules for forbidden order execution
    mod_audit = ProspectiveGovernanceGuard.audit_module_isolation()
    assert mod_audit["status"] == "PASS"
    assert mod_audit["isolation_verified"] is True
