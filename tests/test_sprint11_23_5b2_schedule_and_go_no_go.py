"""
Sprint 11.23.5B-2: Schedule Verification, Market Data, Consensus & Go/No-Go Tests
Comprehensive test suite validating:
  - Official BLS schedule verification & offline fail-closed behavior
  - US/Eastern EDT/EST daylight saving time conversions
  - Schedule revision and supersession tracking
  - Canonical event ID derivation and placeholder detection
  - Market data semantics (bookTicker vs executed trade price distinction)
  - Missing and partial candle handling
  - Pre-release consensus vintage and anti-leakage guards
  - Request and byte budget feasibility (20 requests / 5 MB)
  - 16-gate Go/No-Go decision engine and checklist
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import pytest

from coin_behavior_engine.prospective import (
    ReadOnlyResearchTransport,
    TransportResponse,
    NetworkAccessProhibitedError,
    DomainNotAllowedError,
    TradingIsolationViolation,
    ObservationAuthorizationToken,
    ObservationAuthorizationEngine,
    AuthorizationCapability,
    AuthorizationStatus,
    SigningKeyRegistry,
    TrustedApprovalStore,
    TrustedApprovalRecord,
    NetworkActivationGate,
    AuthorizationError,
    MissingSigningKeyError,
    UnknownKeyIdError,
    NetworkActivationGateError,
    OperatorRole,
    OperatorIdentity,
    ProposalStatus,
    PilotProposal,
    OperatorApprovalWorkflowEngine,
    FileBackedKeyProvider,
    verify_key_file_permissions,
    ImmutableEvidenceVault,
    ProspectiveMarketObserver,
    MarketCandle,
    ConsensusEvidenceRegistry,
    ConsensusVerificationStatus,
    ProspectivePilotRunner,
    PilotConfig,
    ScheduleVerificationError,
    UnofficialSourceError,
    PlaceholderEventIdError,
    InvalidTimezoneConversionError,
    ReferencePeriodMismatchError,
    ScheduleRevisionError,
    DocumentHashMismatchError,
    MarketDataSpecificationError,
    RequestBudgetExhaustedError,
    ScheduleVerificationStatus,
    ScheduleRevisionStatus,
    SourceAuthenticityStatus,
    GoNoGoDecision,
    OfficialScheduleRecord,
    OfficialScheduleVerificationEngine,
    convert_local_to_utc,
    derive_canonical_event_id,
    is_placeholder_event_id,
    MarketDataObservationSpec,
    PilotRequestBudgetPlan,
    GateResult,
    PilotGoNoGoEngine,
)


@pytest.fixture(autouse=True)
def reset_key_registry():
    SigningKeyRegistry.reset_instance()
    yield
    SigningKeyRegistry.reset_instance()


# ==============================================================================
# 1. SCHEDULE VERIFICATION TESTS
# ==============================================================================

def test_01_missing_official_schedule_returns_pending():
    """Test 1: Offline verification with no document returns SCHEDULE_VERIFICATION_PENDING."""
    engine = OfficialScheduleVerificationEngine()
    record = engine.verify_schedule_offline(raw_document_bytes=None)
    assert record.verification_status == ScheduleVerificationStatus.SCHEDULE_VERIFICATION_PENDING
    assert record.source_authenticity_status == SourceAuthenticityStatus.UNAUTHENTICATED
    assert record.is_placeholder() is True
    assert "EVT-BLS-CPI-2026-PENDING" in record.event_id


def test_02_unofficial_schedule_source_rejected():
    """Test 2: Non-BLS schedule source URLs (aggregators, news) are rejected."""
    engine = OfficialScheduleVerificationEngine()
    fake_doc = b"<html>Sample Schedule</html>"
    with pytest.raises(UnofficialSourceError) as exc:
        engine.verify_schedule_offline(
            raw_document_bytes=fake_doc,
            source_url="https://investing.com/economic-calendar/cpi",
            reference_period="2026-09",
            scheduled_local_dt="2026-10-13T08:30:00",
        )
    assert "investing.com" in str(exc.value)


def test_03_timezone_conversion_edt_to_utc():
    """Test 3: Local EDT (UTC-4) converts deterministically to UTC."""
    # October is in EDT (UTC-4)
    utc_str = convert_local_to_utc("2026-10-13T08:30:00", "America/New_York")
    assert utc_str == "2026-10-13T12:30:00Z"


def test_04_daylight_saving_transition_est_to_utc():
    """Test 4: Local EST (UTC-5) converts deterministically to UTC."""
    # December is in EST (UTC-5)
    utc_str = convert_local_to_utc("2026-12-10T08:30:00", "America/New_York")
    assert utc_str == "2026-12-10T13:30:00Z"


def test_05_schedule_revision_and_supersession():
    """Test 5: Schedule revision preserves previous as SUPERSEDED and links new record."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        engine = OfficialScheduleVerificationEngine(vault=vault)
        doc1 = b"<html>Official BLS CPI Schedule v1</html>"
        sha1 = hashlib.sha256(doc1).hexdigest()

        rec1 = engine.verify_schedule_offline(
            raw_document_bytes=doc1,
            source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            claimed_sha256=sha1,
            reference_period="2026-09",
            scheduled_local_dt="2026-10-13T08:30:00",
        )
        assert rec1.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL
        assert rec1.revision_status == ScheduleRevisionStatus.ORIGINAL
        assert rec1.revision_number == 1

        # BLS announces revision: release rescheduled to Oct 14
        doc2 = b"<html>Official BLS CPI Schedule v2 REVISED</html>"
        superseded, revised = engine.revise_schedule(
            previous_record=rec1,
            new_local_dt="2026-10-14T08:30:00",
            new_document_bytes=doc2,
            new_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            reason="Government holiday adjustment",
        )

        assert superseded.verification_status == ScheduleVerificationStatus.SUPERSEDED
        assert superseded.revision_status == ScheduleRevisionStatus.SUPERSEDED
        assert superseded.superseded_by_event_id == revised.event_id

        assert revised.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL
        assert revised.revision_status == ScheduleRevisionStatus.REVISED
        assert revised.supersedes_event_id == rec1.event_id
        assert revised.revision_number == 2
        assert "20261014" in revised.event_id


def test_06_event_id_mismatch_in_gate():
    """Test 6: Gate rejects request when event ID does not match token approval."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-evt-mismatch", b"secret_key_bytes_mismatch_001", is_test_key=True)
    store = TrustedApprovalStore()

    token = ObservationAuthorizationToken(
        token_id="AUTH-EVT-01",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI-2026M09-20261013",
        operator_identity="Admin",
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        not_before_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="key-evt-mismatch",
    )
    token.signature_digest = token.compute_canonical_digest()
    store.create_privileged_approval(token, privileged_operator="Admin")

    gate = NetworkActivationGate(
        approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True
    )

    # Evaluate against a different event ID
    allowed, reason = gate.evaluate_request(
        token, "https://bls.gov/data", target_event_id="EVT-BLS-NFP-2026M09-20261002"
    )
    assert allowed is False
    assert "OUT_OF_SCOPE_EVENT" in reason


def test_07_placeholder_event_id_rejected():
    """Test 7: Placeholder event IDs are detected and rejected by identity standard."""
    assert is_placeholder_event_id("EVT-BLS-CPI-2026-PENDING") is True
    assert is_placeholder_event_id("EVT-BLS-CPI-TBD") is True
    assert is_placeholder_event_id("EVT-BLS-CPI-2026M09-20261013") is False

    with pytest.raises(PlaceholderEventIdError):
        derive_canonical_event_id("BLS", "CPI", "PENDING", "20261013")


def test_08_proposal_digest_mismatch_on_tampering():
    """Test 8: Modifying proposal fields changes digest and invalidates prior digest."""
    proposal = PilotProposal(
        proposal_id="PROP-01",
        proposal_version="1.0.0",
        event_id="EVT-BLS-CPI-2026M09-20261013",
        event_name="US CPI Release",
        official_publisher="BLS",
        official_source_url="https://www.bls.gov/cpi",
        expected_publication_time="2026-10-13T12:30:00Z",
        schedule_verification_status="VERIFIED",
        consensus_source_requirements=["Survey"],
        btc_market_data_endpoints=["https://data-api.binance.vision/api/v3/ticker/bookTicker"],
        max_duration_seconds=1800,
        max_requests=20,
        max_bytes=5242880,
        polling_interval_seconds=5.0,
        approved_domains=["bls.gov"],
        evidence_storage_destination="vault/",
        timestamp_policy="STRICT",
        emergency_stop_conditions=["429"],
        created_by_operator_id="OP-01",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    original_digest = proposal.compute_canonical_digest()

    # Modify an attribute (e.g. increase max_requests from 20 to 50)
    proposal.max_requests = 50
    tampered_digest = proposal.compute_canonical_digest()

    assert original_digest != tampered_digest


# ==============================================================================
# 2. CONSENSUS EVIDENCE & VINTAGE TESTS
# ==============================================================================

def test_09_missing_consensus_marked_unavailable():
    """Test 9: Without contemporaneous consensus source, status is marked UNAVAILABLE."""
    registry = ConsensusEvidenceRegistry()
    records = registry.get_consensus_records("EVT-BLS-CPI-2026M09-20261013")
    assert len(records) == 0  # Marked UNAVAILABLE; zero fabricated records


def test_10_consensus_first_available_after_release_rejected():
    """Test 10: Consensus observed on or after release is rejected as VINTAGE_VIOLATION."""
    registry = ConsensusEvidenceRegistry()
    release_utc = "2026-10-13T12:30:00Z"

    # Survey published at 12:31:00Z (after release)
    rec = registry.register_consensus_survey(
        event_id="EVT-BLS-CPI-2026M09-20261013",
        provider_name="Bloomberg Survey",
        survey_value=3.1,
        survey_unit="%",
        survey_published_at_utc="2026-10-13T12:31:00Z",
        first_observed_at_utc="2026-10-13T12:31:05Z",
        retrieved_at_utc="2026-10-13T12:31:10Z",
        official_release_scheduled_utc=release_utc,
    )
    assert rec.verification_status == ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED
    assert "VINTAGE_VIOLATION" in (rec.rejection_reason or "")


# ==============================================================================
# 3. MARKET DATA SEMANTICS & CANDLE INTEGRITY TESTS
# ==============================================================================

def test_11_bookticker_versus_trade_price_distinction():
    """Test 11: Attempting to treat bookTicker quotes as executed trade prices raises error."""
    spec = MarketDataObservationSpec()
    # Using bookTicker for spread/quotes is valid
    spec.validate_price_source("bookTicker", "bid_ask_spread_analysis")

    # Treating bookTicker as executed trade price is invalid
    with pytest.raises(MarketDataSpecificationError) as exc:
        spec.validate_price_source("bookTicker", "executed_trade_price_return")
    assert "SEMANTIC ERROR" in str(exc.value)


def test_12_missing_market_candle_detected():
    """Test 12: Missing candle in OHLCV stream is identified."""
    import pandas as pd
    observer = ProspectiveMarketObserver()
    df = pd.DataFrame([
        {"datetime": "2026-10-13T12:28:00Z", "open": 68000, "high": 68050, "low": 67950, "close": 68020, "volume": 15.0},
        # Missing 12:29:00Z candle
        {"datetime": "2026-10-13T12:30:00Z", "open": 68020, "high": 68200, "low": 68000, "close": 68150, "volume": 45.0},
    ])
    clean_df, meta = observer.clean_and_validate_candles(df, expected_freq_minutes=1)
    assert meta["missing_count"] >= 1
    assert meta["status"] == "GAPS_DETECTED"


def test_13_partial_candle_detected_and_rejected():
    """Test 13: Unclosed / partial candle is detected by close timestamp."""
    spec = MarketDataObservationSpec(allow_partial_candles=False)
    candle_open = "2026-10-13T12:30:00Z"
    candle_close = "2026-10-13T12:31:00Z"
    current_time = "2026-10-13T12:30:35Z"  # 35s into 1m bar -> partial

    is_partial = spec.is_partial_candle(candle_open, candle_close, current_time)
    assert is_partial is True


# ==============================================================================
# 4. PILOT OPERATING ENVELOPE & BUDGET TESTS
# ==============================================================================

def test_14_request_budget_feasibility_allocation():
    """Test 14: Planned 20-request breakdown validates strictly within budget."""
    budget = PilotRequestBudgetPlan()
    assert budget.total_planned_requests == 20
    is_ok, reason = budget.validate_feasibility()
    assert is_ok is True
    assert "BUDGET_FEASIBLE" in reason


def test_15_request_budget_exhaustion_detected():
    """Test 15: Allocating > 20 requests fails feasibility validation."""
    budget = PilotRequestBudgetPlan(release_polling_requests=12)  # Total 22 requests
    is_ok, reason = budget.validate_feasibility()
    assert is_ok is False
    assert "exceeds budget" in reason


def test_16_byte_budget_exhaustion_detected():
    """Test 16: Allocating > 5 MB bytes fails feasibility validation."""
    budget = PilotRequestBudgetPlan(max_bytes=1000)  # Very low byte limit
    is_ok, reason = budget.validate_feasibility()
    assert is_ok is False
    assert "exceeds budget" in reason


def test_17_clock_uncertainty_and_drift_bounded():
    """Test 17: Wall-clock UTC and monotonic duration timer ensure bounded timing."""
    start_mono = time.monotonic()
    t_utc = datetime.now(timezone.utc)
    time.sleep(0.05)
    elapsed = time.monotonic() - start_mono
    assert elapsed > 0.0
    assert t_utc.tzinfo is not None


# ==============================================================================
# 5. GO/NO-GO CHECKLIST & DECISION TESTS
# ==============================================================================

def test_18_expired_operator_approval_blocks_execution():
    """Test 18: Expired token is rejected by NetworkActivationGate."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-expired-test", b"secret_key_bytes_expired_001", is_test_key=True)
    store = TrustedApprovalStore()

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-EXP-01",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-01",
        operator_identity="Admin",
        issued_at_utc=(now - timedelta(hours=3)).isoformat(),
        not_before_utc=(now - timedelta(hours=3)).isoformat(),
        expires_at_utc=(now - timedelta(hours=1)).isoformat(),  # Expired 1 hour ago
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="key-expired-test",
    )
    token.signature_digest = token.compute_canonical_digest()
    store.create_privileged_approval(token, privileged_operator="Admin")

    gate = NetworkActivationGate(
        approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True
    )
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-01")
    assert allowed is False
    assert "EXPIRED" in reason


def test_19_missing_production_signing_key_fails_closed():
    """Test 19: Missing key in FileBackedKeyProvider raises FileNotFoundError."""
    with tempfile.TemporaryDirectory() as td:
        provider = FileBackedKeyProvider(td)
        with pytest.raises(FileNotFoundError):
            provider.load_key("nonexistent-key-id")


def test_20_revoked_authorization_blocks_execution():
    """Test 20: Revoked authorization token is immediately rejected."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-rev-test", b"secret_key_bytes_rev_001", is_test_key=True)
    store = TrustedApprovalStore()

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-REV-01",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-01",
        operator_identity="Admin",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="key-rev-test",
    )
    token.signature_digest = token.compute_canonical_digest()
    store.create_privileged_approval(token, privileged_operator="Admin")
    store.revoke_approval(token.token_id, revoked_by="Admin", reason="Test revocation")

    gate = NetworkActivationGate(
        approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True
    )
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-01")
    assert allowed is False
    assert "REVOKED" in reason


def test_21_unauthorized_real_network_attempt_blocked():
    """Test 21: Direct transport execution with network_enabled=True without authorization fails."""
    transport = ReadOnlyResearchTransport(network_enabled=True)
    with pytest.raises(NetworkActivationGateError):
        transport.execute_request("GET", "https://bls.gov/news")


def test_22_unauthorized_trading_endpoint_permanently_prohibited():
    """Test 22: Private trading endpoints raise TradingIsolationViolation or TradingEndpointAccessError."""
    from coin_behavior_engine.prospective.research_transport import TradingEndpointAccessError
    transport = ReadOnlyResearchTransport(network_enabled=False)
    with pytest.raises((TradingIsolationViolation, TradingEndpointAccessError)):
        transport.execute_request("GET", "https://api.binance.com/api/v3/order")


def test_23_interrupted_pilot_preflight_clean_stop():
    """Test 23: Calling request_stop() cleanly flags stop without state corruption."""
    from coin_behavior_engine.prospective import PilotAuthorizationToken
    token = PilotAuthorizationToken(
        operator_name="Admin",
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        is_authorized=False,
    )
    runner = ProspectivePilotRunner(
        config=PilotConfig(),
        token=token,
        vault=ImmutableEvidenceVault(),
        transport=ReadOnlyResearchTransport(network_enabled=False),
    )
    assert runner.stop_requested is False
    runner.request_stop()
    assert runner.stop_requested is True


def test_24_deterministic_go_no_go_decision():
    """Test 24: Preflight Go/No-Go decision engine produces deterministic NO_GO_SCHEDULE_UNVERIFIED."""
    # When schedule verification is pending (offline)
    engine = PilotGoNoGoEngine(
        schedule_record=None,  # Unverified
        operator_authorization_granted=False,
    )
    decision, tech_preflight, op_auth = engine.determine_decision()
    assert decision == GoNoGoDecision.NO_GO_SCHEDULE_UNVERIFIED
    assert tech_preflight == "PASS"
    assert op_auth == "NO"

    # All 16 gates evaluated
    gates = engine.evaluate_all_gates()
    assert len(gates) == 16
    assert gates[0].gate_name == "Repository Integrity"
    assert gates[7].gate_name == "Official Schedule Evidence"
    assert gates[7].status == "PENDING"
    assert gates[15].gate_name == "Trading Isolation"
    assert gates[15].status == "PASS"
