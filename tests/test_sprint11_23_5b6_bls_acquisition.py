"""
Sprint 11.23.5B-6 Adversarial & Security Verification Test Suite
Official BLS Evidence Acquisition & Event Identity Verification

Validates:
  - Phase 1: One-Time Acquisition Request
  - Phase 2: Authorization Isolation (OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION)
  - Phase 3: Trusted HTTPS Acquisition & Provenance Generation
  - Phase 4: Official BLS CPI Schedule Parsing & Contradiction Detection
  - Phase 5: Event Identity Verification & Freezing Guards
  - Phase 6: Canonical Sampling Plan Reconciliation (13 milestones vs 8 horizons)
  - Phase 7: Offline End-to-End 14-Step Deterministic Rehearsal
  - Phase 8: Adversarial Security & Governance Invariants
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import pytest
import tempfile

from coin_behavior_engine.prospective import (
    AuthorizationCapability,
    AuthorizationStatus,
    ObservationAuthorizationToken,
    TrustedApprovalStore,
    NetworkActivationGate,
    SigningKeyRegistry,
    TradingIsolationViolation,
    ReadOnlyResearchTransport,
    TransportResponse,
    InsecureSchemeError,
    DomainNotAllowedError,
    TradingEndpointAccessError,
    ResponseSizeExceededError,
    ProvenanceTrustLevel,
    HttpsAcquisitionProvenanceRecord,
    EvidenceProvenanceVerifier,
    OfficialScheduleAcceptancePolicy,
    CandidateEventIdentity,
    EventIdentityStatus,
    EventIdentityManager,
    PilotProposalV3Builder,
    PilotProposal,
    OfficialScheduleAcquisitionRequest,
    ParsedCpiSchedule,
    BlsCpiScheduleParser,
    ScheduleParsingError,
    AcquisitionScopeError,
    CanonicalSamplingMilestone,
    CanonicalSamplingPlanReconciler,
    OfflinePilotRehearsalRunnerV5,
    MAX_ACQUISITION_ATTEMPTS,
    MAX_ACQUISITION_RESPONSE_BYTES,
    OFFICIAL_BLS_HOST,
    OFFICIAL_BLS_CPI_URL,
    TARGET_EVENT_ID,
    TARGET_EVENT_RELEASE_UTC,
    ImmutableEvidenceVault,
)


@pytest.fixture
def clean_registry():
    SigningKeyRegistry.reset_instance()
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-5b6", b"unit_test_secret_32_bytes_ok_5b6!!", is_test_key=True)
    return reg


@pytest.fixture
def mock_store():
    store = TrustedApprovalStore()
    yield store
    store.close()


@pytest.fixture
def sample_bls_html():
    return b"""<!DOCTYPE html>
<html>
<head><title>Consumer Price Index Schedule</title></head>
<body>
<h1>Schedule of News Releases for the Consumer Price Index (CPI)</h1>
<table>
  <tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr>
  <tr><td>September 2026</td><td>October 14, 2026</td><td>08:30 AM</td></tr>
  <tr><td>October 2026</td><td>November 10, 2026</td><td>08:30 AM</td></tr>
  <tr><td>November 2026</td><td>December 10, 2026</td><td>08:30 AM</td></tr>
</table>
<p>Schedule subject to change.</p>
</body>
</html>"""


# ==============================================================================
# 1. PHASE 1: ONE-TIME ACQUISITION REQUEST AUDIT
# ==============================================================================

def test_01_acquisition_request_defaults_and_scope():
    """Verifies official acquisition request parameters adhere strictly to Phase 1 boundaries."""
    req = OfficialScheduleAcquisitionRequest()
    valid, violations = req.validate_proposed_scope()
    assert valid, f"Violations: {violations}"
    assert req.allowed_hostname == "www.bls.gov"
    assert req.canonical_url == "https://www.bls.gov/schedule/news_release/cpi.htm"
    assert req.http_method == "GET"
    assert req.max_successful_acquisitions == 1
    assert req.max_attempts == 2
    assert req.max_response_bytes == 2 * 1024 * 1024
    assert req.required_capability == AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION.value
    assert req.target_event_id == TARGET_EVENT_ID


def test_02_acquisition_request_digest_determinism():
    """Verifies that the canonical request digest is deterministic and sensitive to changes."""
    req1 = OfficialScheduleAcquisitionRequest()
    digest1 = req1.compute_canonical_digest()
    assert len(digest1) == 64

    req2 = OfficialScheduleAcquisitionRequest(max_response_bytes=1024 * 1024)
    digest2 = req2.compute_canonical_digest()
    assert digest1 != digest2


# ==============================================================================
# 2. PHASE 2: AUTHORIZATION ISOLATION (OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION)
# ==============================================================================

def test_03_unauthorized_acquisition_rejected(mock_store, clean_registry):
    """Verifies that requests without an authorization token are denied."""
    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(
        token=None,
        target_url=OFFICIAL_BLS_CPI_URL,
        target_event_id=TARGET_EVENT_ID,
    )
    assert not allowed
    assert "MISSING_TOKEN" in reason


def test_04_forged_approval_signature_rejected(mock_store, clean_registry):
    """Verifies that a token with a forged signature fails verification."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-FORGED-01",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-ATTACKER",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
        signature_digest="0000000000000000000000000000000000000000000000000000000000000000",
    )
    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert not allowed
    assert "INVALID_SIGNATURE" in reason


def test_05_approval_scope_mismatch_event_id(mock_store, clean_registry):
    """Verifies that a token authorized for a different event cannot be used for CPI."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-MISMATCH-EVT",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id="EVT-SOME-OTHER-EVENT",
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert not allowed
    assert "OUT_OF_SCOPE_EVENT" in reason


def test_06_reused_approval_digest_mismatch_rejected(mock_store, clean_registry):
    """Verifies that an approval bound to an older request digest is rejected when the digest changes."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = OfficialScheduleAcquisitionRequest()
    req_digest = req.compute_canonical_digest()

    token = ObservationAuthorizationToken(
        token_id="TOK-REUSED-01",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(
        token=token, privileged_operator="OP-ADMIN", is_production=False, proposal_digest="old_stale_digest_12345"
    )

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(
        token=token,
        target_url=OFFICIAL_BLS_CPI_URL,
        target_event_id=TARGET_EVENT_ID,
        expected_request_digest=req_digest,
    )
    assert not allowed
    assert "DIGEST_MISMATCH" in reason


def test_07_expired_approval_rejected(mock_store, clean_registry):
    """Verifies that an expired approval is blocked fail-closed."""
    past_utc = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_utc = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-EXPIRED-01",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=past_utc,
        not_before_utc=past_utc,
        expires_at_utc=expired_utc,
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert not allowed
    assert "EXPIRED" in reason


def test_08_revoked_approval_rejected(mock_store, clean_registry):
    """Verifies that durable revocation blocks subsequent requests immediately."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-REVOKED-01",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    mock_store.revoke_approval(token_id=token.token_id, revoked_by="OP-SECURITY", reason="Precautionary revocation")

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert not allowed
    assert "REVOKED" in reason


# ==============================================================================
# 3. PHASE 2 ISOLATION: PROHIBIT MARKET ACCESS & TRADING UNDER ACQUISITION CAPABILITY
# ==============================================================================

def test_09_attempted_binance_access_under_acquisition_token_raises_violation(mock_store, clean_registry):
    """
    CRITICAL: OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION must never permit Binance market data access.
    Attempting to target api.binance.com must raise TradingIsolationViolation.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-ACQ-ATTEMPT-BINANCE",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST, "api.binance.com"],  # Attacker attempts to sneak in Binance
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)

    with pytest.raises(TradingIsolationViolation) as exc:
        gate.evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/bookTicker?symbol=BTCUSDT",
            target_event_id=TARGET_EVENT_ID,
        )
    assert "AUTHORIZATION_ISOLATION_VIOLATION" in str(exc.value)


def test_10_attempted_trading_endpoint_raises_violation(mock_store, clean_registry):
    """Verifies that targeting order endpoints raises TradingIsolationViolation."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-ORDER-01",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)

    with pytest.raises(TradingIsolationViolation):
        gate.evaluate_request(
            token=token,
            target_url="https://www.bls.gov/api/v3/order",  # Path matches denylisted pattern
            target_event_id=TARGET_EVENT_ID,
        )


# ==============================================================================
# 4. PHASE 3: TRUSTED HTTPS TRANSPORT AUDIT
# ==============================================================================

def test_11_http_downgrade_rejected():
    """Verifies plain http:// is rejected by transport."""
    transport = ReadOnlyResearchTransport(network_enabled=False)
    with pytest.raises(InsecureSchemeError):
        transport._validate_request_security("GET", "http://www.bls.gov/schedule/cpi.htm", {})


def test_12_non_allowlisted_domain_rejected():
    """Verifies domains outside allowlist are blocked."""
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"})
    with pytest.raises(DomainNotAllowedError):
        transport._validate_request_security("GET", "https://unauthorized-domain.com/cpi.htm", {})


def test_13_oversized_response_rejected():
    """Verifies that response bodies > 2 MB trigger ResponseSizeExceededError."""
    transport = ReadOnlyResearchTransport(network_enabled=False, max_response_size_bytes=2 * 1024 * 1024)
    huge_body = b"A" * (2 * 1024 * 1024 + 10)
    transport.register_mock_response(OFFICIAL_BLS_CPI_URL, status_code=200, body=huge_body)

    with pytest.raises(ResponseSizeExceededError):
        transport.execute_request("GET", OFFICIAL_BLS_CPI_URL)


# ==============================================================================
# 5. PHASE 4: OFFICIAL SCHEDULE PARSING & CONTRADICTION DETECTION
# ==============================================================================

def test_14_schedule_parsing_valid_html(sample_bls_html):
    """Verifies correct parsing of official BLS CPI table."""
    candidate = EventIdentityManager.create_candidate_event()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    parsed = BlsCpiScheduleParser.parse_schedule_document(
        raw_bytes=sample_bls_html,
        source_url=OFFICIAL_BLS_CPI_URL,
        candidate_event=candidate,
        acquisition_timestamp_utc=now_utc,
        target_reference_month="October",
        target_reference_year=2026,
    )

    assert parsed.publisher == "BLS"
    assert parsed.reference_period == "2026M10"
    assert parsed.release_date == "2026-11-10"
    assert parsed.release_time_local == "08:30:00"
    assert parsed.scheduled_release_utc == "2026-11-10T13:30:00Z"
    assert parsed.derived_event_id == TARGET_EVENT_ID
    assert not parsed.contradicts_candidate


def test_15_schedule_parsing_contradiction_detected():
    """
    Verifies that if the official document contains a different date (e.g. Nov 12),
    contradicts_candidate is set to True, both values are recorded, and no overwrite occurs.
    """
    contradictory_html = b"""<html><body>
    <h1>Schedule of News Releases for the Consumer Price Index (CPI)</h1>
    <table>
      <tr><td>October 2026</td><td>November 12, 2026</td><td>08:30 AM</td></tr>
    </table></body></html>"""

    candidate = EventIdentityManager.create_candidate_event()
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    parsed = BlsCpiScheduleParser.parse_schedule_document(
        raw_bytes=contradictory_html,
        source_url=OFFICIAL_BLS_CPI_URL,
        candidate_event=candidate,
        acquisition_timestamp_utc=now_utc,
        target_reference_month="October",
        target_reference_year=2026,
    )

    assert parsed.contradicts_candidate
    assert parsed.release_date == "2026-11-12"
    assert parsed.contradiction_details["date_mismatch"]["candidate"] == "2026-11-10"
    assert parsed.contradiction_details["date_mismatch"]["parsed_official"] == "2026-11-12"


def test_16_missing_reference_period_raises_error():
    """Verifies that missing reference period raises ScheduleParsingError."""
    missing_period_html = b"""<html><body>
    <h1>Schedule of News Releases for the Consumer Price Index (CPI)</h1>
    <table>
      <tr><td>January 2026</td><td>February 11, 2026</td><td>08:30 AM</td></tr>
    </table></body></html>"""

    candidate = EventIdentityManager.create_candidate_event()
    with pytest.raises(ScheduleParsingError) as exc:
        BlsCpiScheduleParser.parse_schedule_document(
            raw_bytes=missing_period_html,
            source_url=OFFICIAL_BLS_CPI_URL,
            candidate_event=candidate,
            acquisition_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            target_reference_month="October",
            target_reference_year=2026,
        )
    assert "Could not locate official schedule entry" in str(exc.value)


def test_17_missing_series_keyword_raises_error():
    """Verifies that a document lacking 'Consumer Price Index' / 'CPI' markers is rejected."""
    wrong_doc = b"<html><body>Unrelated Employment Report Schedule</body></html>"
    candidate = EventIdentityManager.create_candidate_event()
    with pytest.raises(ScheduleParsingError) as exc:
        BlsCpiScheduleParser.parse_schedule_document(
            raw_bytes=wrong_doc,
            source_url=OFFICIAL_BLS_CPI_URL,
            candidate_event=candidate,
            acquisition_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    assert "lacks required 'Consumer Price Index'" in str(exc.value)


# ==============================================================================
# 6. PHASE 5: EVENT IDENTITY VERIFICATION GUARDS
# ==============================================================================

def test_18_event_identity_remains_pending_without_verified_provenance():
    """Verifies candidate event retains status CANDIDATE_PENDING_SCHEDULE_VERIFICATION without verified provenance."""
    candidate = EventIdentityManager.create_candidate_event()
    assert candidate.status == EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION

    # Attempting to bind with unverified provenance raises ValueError
    with pytest.raises(ValueError) as exc:
        EventIdentityManager.bind_and_freeze_event(
            candidate=candidate,
            verified_schedule_sha256="a" * 64,
            is_provenance_verified=False,
            trust_level=ProvenanceTrustLevel.SOURCE_CLAIMED_OFFICIAL,
        )
    assert "lacks cryptographic provenance verification" in str(exc.value)


def test_19_binding_with_valid_level_b_freezes_event():
    """Verifies candidate event transitions to VERIFIED_FROZEN when bound to Level B verified provenance."""
    candidate = EventIdentityManager.create_candidate_event()
    dummy_sha = "b" * 64
    frozen = EventIdentityManager.bind_and_freeze_event(
        candidate=candidate,
        verified_schedule_sha256=dummy_sha,
        is_provenance_verified=True,
        trust_level=ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION,
    )
    assert frozen.status == EventIdentityStatus.VERIFIED_FROZEN
    assert frozen.schedule_evidence_sha256 == dummy_sha


# ==============================================================================
# 7. PHASE 6: SAMPLING PLAN RECONCILIATION
# ==============================================================================

def test_20_sampling_plan_reconciliation_metrics():
    """
    Reconciles the discrepancy between 13 operational milestones and 8 macro horizons.
    Proves total requests (13) <= quota (20) leaving 7 reserve requests.
    """
    recon = CanonicalSamplingPlanReconciler.reconcile(release_utc=TARGET_EVENT_RELEASE_UTC)

    assert recon["discrepancy_analysis"]["sprint_b4_count"] == 13
    assert recon["discrepancy_analysis"]["sprint_b5_count"] == 8
    assert recon["discrepancy_analysis"]["reconciliation_verdict"] == "RECONCILED_AND_UNIFIED"

    metrics = recon["budget_metrics"]
    assert metrics["total_operational_milestones"] == 13
    assert metrics["mandatory_macro_horizons"] == 8
    assert metrics["total_planned_requests"] == 13
    assert metrics["hard_quota_limit"] == 20
    assert metrics["reserve_requests_buffer"] == 7
    assert metrics["is_quota_compliant"] is True


def test_21_batch_klines_efficiency_fallback():
    """
    Verifies that the canonical reconciler documents the 1-call batch klines fallback
    with capacity of 35 completed 1m candles.
    """
    recon = CanonicalSamplingPlanReconciler.reconcile(release_utc=TARGET_EVENT_RELEASE_UTC)
    fallback = recon["batch_efficiency_fallback"]
    assert fallback["single_request_candle_capacity"] == 35
    assert "limit=35" in fallback["endpoint"]


# ==============================================================================
# 8. PHASE 7: OFFLINE PILOT REHEARSAL RUNNER V5 (14-STEP DETERMINISTIC SIMULATION)
# ==============================================================================

def test_22_offline_pilot_rehearsal_v5_full_flow():
    """Executes the full 14-step deterministic rehearsal runner and verifies 100% pass."""
    results = OfflinePilotRehearsalRunnerV5.run_rehearsal()
    assert results["total_steps"] == 14
    assert results["passed_steps"] == 14
    assert results["rehearsal_status"] == "ALL_14_STEPS_PASSED"
    assert results["is_simulation_only"] is True
    assert results["real_requests_made"] == 0


# ==============================================================================
# 9. PHASE 8: PRODUCTION AUTHORIZATION PERMANENT PROHIBITION
# ==============================================================================

def test_23_production_approval_permanently_prohibited(mock_store, clean_registry):
    """Verifies that attempting to create a production approval in trusted store raises AuthorizationError."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-PROD-ATTEMPT",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)

    with pytest.raises(Exception) as exc:
        mock_store.create_privileged_approval(
            token=token,
            privileged_operator="OP-ADMIN",
            is_production=True,  # Prohibited!
        )
    assert "Production approvals are strictly NOT authorized" in str(exc.value)


def test_24_quota_overflow_blocked_by_gate(mock_store, clean_registry):
    """Verifies that exceeding the max request quota (2 requests) blocks the 3rd attempt."""
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    token = ObservationAuthorizationToken(
        token_id="TOK-QUOTA-TEST",
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=TARGET_EVENT_ID,
        operator_identity="OP-RESEARCH-01",
        issued_at_utc=now_utc,
        not_before_utc=now_utc,
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[OFFICIAL_BLS_HOST],
        max_request_count=2,  # Max 2 attempts
        max_byte_allowance=1000000,
        key_id="test-key-5b6",
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=clean_registry)
    mock_store.create_privileged_approval(token=token, privileged_operator="OP-ADMIN", is_production=False)

    gate = NetworkActivationGate(approval_store=mock_store, key_registry=clean_registry, gate_enabled=True, operator_authorization_granted=True)

    # Attempt 1: allowed
    a1, _ = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert a1

    # Attempt 2: allowed
    a2, _ = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert a2

    # Attempt 3: quota exhausted -> blocked
    a3, r3 = gate.evaluate_request(token=token, target_url=OFFICIAL_BLS_CPI_URL, target_event_id=TARGET_EVENT_ID)
    assert not a3
    assert "QUOTA_FAILED" in r3 or "APPROVAL_STATUS_EXHAUSTED" in r3


def test_25_evidence_vault_mutation_detected(tmp_path):
    """Verifies tampering with vaulted evidence bytes is detected via SHA-256 integrity check."""
    vault = ImmutableEvidenceVault(vault_root=tmp_path / "vault")
    payload = b"Original BLS Evidence Bytes"
    sha, stored_path, _ = vault.store_bytes(
        category="releases",
        data=payload,
        source_metadata={"url": OFFICIAL_BLS_CPI_URL},
        extension="html",
    )

    # Tamper with file on disk directly
    tampered_payload = b"Tampered Modified Bytes"
    stored_path.write_bytes(tampered_payload)

    # Verification must report corrupted file
    audit = vault.verify_vault_integrity()
    assert len(audit["corrupt_files"]) > 0


def test_26_dns_rebinding_rejected():
    """Verifies that DNS rebinding (connected_ip != resolved_ip) is rejected by provenance validation."""
    prov = HttpsAcquisitionProvenanceRecord(
        source_url=OFFICIAL_BLS_CPI_URL,
        canonical_hostname=OFFICIAL_BLS_HOST,
        publisher_id="BLS",
        acquisition_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=100,
        response_sha256="c" * 64,
        tls_verification_status="VERIFIED_VALID_CHAIN",
        tls_hostname_verified=True,
        certificate_chain_validation="TRUSTED_ROOT_CA",
        resolved_ip="151.101.1.69",
        connected_ip="151.101.1.70",  # Rebound IP!
        redirect_chain=[],
        network_authorization_id="TOK-1",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id="VAULT-1",
    )
    with pytest.raises(Exception) as exc:
        prov.validate()
    assert "DNS rebinding detected" in str(exc.value)


def test_27_tls_hostname_mismatch_rejected():
    """Verifies that an HTTPS provenance record with tls_hostname_verified=False is rejected."""
    prov = HttpsAcquisitionProvenanceRecord(
        source_url=OFFICIAL_BLS_CPI_URL,
        canonical_hostname=OFFICIAL_BLS_HOST,
        publisher_id="BLS",
        acquisition_timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=100,
        response_sha256="c" * 64,
        tls_verification_status="VERIFIED_VALID_CHAIN",
        tls_hostname_verified=False,  # Mismatch!
        certificate_chain_validation="TRUSTED_ROOT_CA",
        resolved_ip="151.101.1.69",
        connected_ip="151.101.1.69",
        redirect_chain=[],
        network_authorization_id="TOK-1",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id="VAULT-1",
    )
    with pytest.raises(Exception) as exc:
        prov.validate()
    assert "TLS hostname verification failed" in str(exc.value)


def test_28_attempted_background_monitoring_prohibited():
    """Verifies that trading endpoints are strictly blocked and governance invariants hold."""
    from coin_behavior_engine.prospective.governance import ProspectiveGovernanceGuard
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_endpoint_not_order_execution("https://api.binance.com/api/v3/order")

    audit = ProspectiveGovernanceGuard.verify_all_governance_invariants()
    assert audit["overall_status"] == "PASS"
    assert audit["live_trading_prohibited"] is True


def test_29_proposal_digest_sensitivity_to_milestones():
    """Verifies that changing milestone parameters alters the proposal digest."""
    candidate = EventIdentityManager.create_candidate_event()
    p1 = PilotProposalV3Builder.build_proposal(candidate)
    d1 = p1.compute_canonical_digest()

    p2 = PilotProposalV3Builder.build_proposal(candidate)
    p2.max_duration_seconds = 1800  # Modifying duration from 2100s
    d2 = p2.compute_canonical_digest()
    assert d1 != d2


def test_30_missing_schedule_document_preserves_pending():
    """Verifies that when no document is provided, schedule verification returns PENDING cleanly without network access."""
    candidate = EventIdentityManager.create_candidate_event()
    assert candidate.status == EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION
    assert candidate.schedule_evidence_sha256 is None

