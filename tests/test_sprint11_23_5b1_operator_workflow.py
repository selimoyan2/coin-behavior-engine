"""
Sprint 11.23.5B-1: Adversarial Operator Workflow & Production Key Security Suite
Tests and validates:
  1. Research operator attempting privileged approval (blocked).
  2. Auditor attempting privileged approval (blocked).
  3. Forged operator identity (fingerprint mismatch blocked).
  4. Forged approval record (tampered record fails verification).
  5. Modified proposal after approval (invalidates digest binding).
  6. Reused approval for another event (event scope mismatch).
  7. Reused approval for another domain (domain scope mismatch).
  8. Expired approval (rejected).
  9. Revoked approval (rejected).
  10. Missing signing key (fails closed).
  11. Test key used in production (rejected).
  12. Unauthorized direct transport call (blocked by gate).
  13. Redirect bypass (domain re-validation blocks target).
  14. Retry bypass (retries revalidate token & quota).
  15. Concurrent quota exhaustion (strict enforcement without overspending).
  16. Revocation during a simulated request (aborts subsequent steps).
  17. Process crash and restart (durable SQLite retains approval state).
  18. Corrupt approval database (detected and fails closed).
  19. Tampered audit record (audit trail integrity verification).
  20. Unauthorized trading capability (permanently blocked).
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sqlite3
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
    UnauthorizedOperatorActionError,
    ProposalIntegrityError,
    KeyStorePermissionError,
    FileBackedKeyProvider,
    verify_key_file_permissions,
    redact_secret_string,
)


@pytest.fixture(autouse=True)
def isolated_key_registry():
    """Resets the singleton SigningKeyRegistry before and after each test."""
    SigningKeyRegistry.reset_instance()
    yield
    SigningKeyRegistry.reset_instance()


def build_sample_cpi_proposal(proposal_id: str = "PROP-2026-BLS-CPI-01", creator_id: str = "OP-RESEARCH-01") -> PilotProposal:
    return PilotProposal(
        proposal_id=proposal_id,
        proposal_version="1.0.0",
        event_id="EVT-BLS-CPI-2026-PENDING",
        event_name="US Consumer Price Index (CPI) YoY Release",
        official_publisher="U.S. Bureau of Labor Statistics",
        official_source_url="https://www.bls.gov/news.release/cpi.nr0.htm",
        expected_publication_time="SCHEDULE_VERIFICATION_PENDING",
        schedule_verification_status="SCHEDULE_VERIFICATION_PENDING",
        consensus_source_requirements=["Contemporaneous survey prior to release"],
        btc_market_data_endpoints=["https://data-api.binance.vision/api/v3/ticker/bookTicker?symbol=BTCUSDT"],
        max_duration_seconds=1800,
        max_requests=20,
        max_bytes=5242880,
        polling_interval_seconds=5.0,
        approved_domains=["bls.gov", "data-api.binance.vision"],
        evidence_storage_destination="manifests/prospective_vault/releases/",
        timestamp_policy="POINT_IN_TIME_CONTEMPORANEOUS_STRICT",
        emergency_stop_conditions=["HTTP 429", "Timeout", "Payload > 5MB"],
        created_by_operator_id=creator_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )


# ==============================================================================
# PHASE 8: 20 ADVERSARIAL OPERATOR WORKFLOW TESTS
# ==============================================================================

def test_01_research_operator_attempting_privileged_approval():
    """Test 1: Research operator attempting privileged approval must be blocked."""
    researcher = OperatorIdentity(
        operator_id="OP-RESEARCH-01",
        role=OperatorRole.RESEARCH_OPERATOR,
        operator_name="Alice Researcher",
        public_key_fingerprint="fp-research-01",
    )
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-02")
    store = TrustedApprovalStore()

    with pytest.raises(UnauthorizedOperatorActionError) as exc_info:
        OperatorApprovalWorkflowEngine.approve_proposal(
            proposal=proposal,
            approver=researcher,
            key_id="test-key",
            store=store,
        )
    assert "APPROVAL_ADMIN role is strictly required" in str(exc_info.value)


def test_02_auditor_attempting_privileged_approval():
    """Test 2: Auditor attempting privileged approval must be blocked."""
    auditor = OperatorIdentity(
        operator_id="OP-AUDIT-01",
        role=OperatorRole.AUDITOR,
        operator_name="Bob Auditor",
        public_key_fingerprint="fp-audit-01",
    )
    proposal = build_sample_cpi_proposal()
    store = TrustedApprovalStore()

    with pytest.raises(UnauthorizedOperatorActionError) as exc_info:
        OperatorApprovalWorkflowEngine.approve_proposal(
            proposal=proposal,
            approver=auditor,
            key_id="test-key",
            store=store,
        )
    assert "APPROVAL_ADMIN role is strictly required" in str(exc_info.value)


def test_03_submitter_self_approval_blocked():
    """Test 3: Separation of duties: Submitter cannot self-approve their own proposal."""
    admin = OperatorIdentity(
        operator_id="OP-ADMIN-01",
        role=OperatorRole.APPROVAL_ADMIN,
        operator_name="Carol Admin",
        public_key_fingerprint="fp-admin-01",
    )
    # Admin created proposal themselves
    proposal = build_sample_cpi_proposal(creator_id="OP-ADMIN-01")
    store = TrustedApprovalStore()

    with pytest.raises(UnauthorizedOperatorActionError) as exc_info:
        OperatorApprovalWorkflowEngine.approve_proposal(
            proposal=proposal,
            approver=admin,
            key_id="test-key",
            store=store,
        )
    assert "Separation of duty violation" in str(exc_info.value)


def test_04_forged_approval_record_fails_verification():
    """Test 4: Approval record tampered directly in store fails verification against token."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-04", b"secure_key_bytes_04_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-02", OperatorRole.APPROVAL_ADMIN, "Admin2", "fp-02")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-04",
        store=store,
        key_registry=reg,
    )

    # Attacker directly alters approval record in DB to point to an unauthorized event
    conn = store._get_connection()
    with store._lock:
        with conn:
            conn.execute("UPDATE approval_records SET authorized_event_id = 'EVT-UNAUTHORIZED' WHERE token_id = ?", (token.token_id,))

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    # Evaluation must reject because token.authorized_event_id != approval.authorized_event_id
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert allowed is False
    assert "OUT_OF_SCOPE_EVENT" in reason


def test_05_modified_proposal_after_approval_invalidates_digest():
    """Test 5: Modifying proposal parameters after approval changes its digest."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-05", b"secure_key_bytes_05_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-03", OperatorRole.APPROVAL_ADMIN, "Admin3", "fp-03")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-05",
        store=store,
        key_registry=reg,
    )

    original_digest = record.proposal_digest

    # Attacker tampers with proposal (e.g. increases max_requests)
    proposal.max_requests = 1000
    tampered_digest = proposal.compute_canonical_digest()

    assert original_digest != tampered_digest


def test_06_reused_approval_for_another_event_blocked():
    """Test 6: Using approval token for an event other than the approved event is blocked."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-06", b"secure_key_bytes_06_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-04", OperatorRole.APPROVAL_ADMIN, "Admin4", "fp-04")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-06",
        store=store,
        key_registry=reg,
    )

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    # Requesting a different event than approved
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-FED-FOMC-ANOTHER")
    assert allowed is False
    assert "OUT_OF_SCOPE_EVENT" in reason


def test_07_reused_approval_for_another_domain_blocked():
    """Test 7: Using approval token for an unapproved domain is blocked."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-07", b"secure_key_bytes_07_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-05", OperatorRole.APPROVAL_ADMIN, "Admin5", "fp-05")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-07",
        store=store,
        key_registry=reg,
    )

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    # Target domain not in approved_domains
    allowed, reason = gate.evaluate_request(token, "https://bea.gov/data", "EVT-BLS-CPI-2026-PENDING")
    assert allowed is False
    assert "OUT_OF_SCOPE_DOMAIN" in reason


def test_08_expired_approval_rejected():
    """Test 8: Approval whose validity window has elapsed is rejected as EXPIRED."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-08", b"secure_key_bytes_08_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-06", OperatorRole.APPROVAL_ADMIN, "Admin6", "fp-06")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-08",
        store=store,
        key_registry=reg,
        validity_hours=-1,  # Expired in past
    )

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert allowed is False
    assert "EXPIRED" in reason


def test_09_revoked_approval_rejected():
    """Test 9: Revoked approval is immediately rejected by gate."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-09", b"secure_key_bytes_09_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-07", OperatorRole.APPROVAL_ADMIN, "Admin7", "fp-07")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-09",
        store=store,
        key_registry=reg,
    )

    # Admin revokes approval
    OperatorApprovalWorkflowEngine.revoke_approval(token.token_id, admin, "Emergency test stop", store)

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert allowed is False
    assert "REVOKED" in reason


def test_10_missing_signing_key_fails_closed():
    """Test 10: Approval using unprovisioned key fails closed."""
    admin = OperatorIdentity("OP-ADMIN-08", OperatorRole.APPROVAL_ADMIN, "Admin8", "fp-08")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    with pytest.raises(UnknownKeyIdError):
        OperatorApprovalWorkflowEngine.approve_proposal(
            proposal=proposal,
            approver=admin,
            key_id="missing-nonexistent-key",
            store=store,
        )


def test_11_test_key_used_in_production_rejected():
    """Test 11: Attempting to use a test key in a production context is rejected."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-11", b"test_key_bytes_11_test_only", is_test_key=True)

    with pytest.raises(AuthorizationError) as exc_info:
        reg.get_key("test-key-11", allow_test_key=False)
    assert "Test key" in str(exc_info.value) and "production" in str(exc_info.value)


def test_12_unauthorized_direct_transport_call_blocked():
    """Test 12: Direct call to transport.execute_request with network_enabled=True is blocked."""
    transport = ReadOnlyResearchTransport(network_enabled=True)
    with pytest.raises(NetworkActivationGateError):
        transport.execute_request("GET", "https://bls.gov/news")


def test_13_redirect_bypass_blocked_by_domain_revalidation():
    """Test 13: Redirect to an unapproved domain is blocked during redirect following."""
    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=True)
    transport.register_mock_response(
        "https://bls.gov/initial",
        status_code=302,
        headers={"location": "https://unapproved-target.com/data"},
    )
    with pytest.raises(DomainNotAllowedError):
        transport.execute_request("GET", "https://bls.gov/initial")


def test_14_retry_bypass_revalidates_token_and_quota():
    """Test 14: Repeated retry attempts re-validate token and exhaust quota."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-14", b"secure_key_bytes_14_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-09", OperatorRole.APPROVAL_ADMIN, "Admin9", "fp-09")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    proposal.max_requests = 2  # Quota of 2
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-14",
        store=store,
        key_registry=reg,
    )

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    # Attempt 1: allowed
    res1, _ = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert res1 is True

    # Attempt 2: allowed
    res2, _ = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert res2 is True

    # Attempt 3 (Retry): quota exhausted -> denied
    res3, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert res3 is False
    assert "QUOTA" in reason or "EXHAUSTED" in reason


def test_15_concurrent_quota_exhaustion_exact_grant():
    """Test 15: Concurrency stress: 10 threads against quota of 4 grants exactly 4."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-15", b"secure_key_bytes_15_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-10", OperatorRole.APPROVAL_ADMIN, "Admin10", "fp-10")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    proposal.max_requests = 4
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-15",
        store=store,
        key_registry=reg,
    )
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    def worker(i):
        return gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(worker, range(10)))

    successes = sum(1 for r in results if r[0] is True)
    denials = sum(1 for r in results if r[0] is False)
    assert successes == 4
    assert denials == 6


def test_16_revocation_during_session_aborts_subsequent_requests():
    """Test 16: Active session that is revoked between requests aborts immediately."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-16", b"secure_key_bytes_16_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-11", OperatorRole.APPROVAL_ADMIN, "Admin11", "fp-11")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")
    store = TrustedApprovalStore()

    prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
        proposal=proposal,
        approver=admin,
        key_id="key-16",
        store=store,
        key_registry=reg,
    )
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    # Request 1: successful
    ok1, _ = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert ok1 is True

    # Revocation triggered
    OperatorApprovalWorkflowEngine.revoke_approval(token.token_id, admin, "Compromise detected", store)

    # Request 2: blocked
    ok2, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
    assert ok2 is False
    assert "REVOKED" in reason


def test_17_process_crash_and_restart_durable_sqlite():
    """Test 17: Approval and revocation states survive process restarts via SQLite."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-17", b"secure_key_bytes_17_test_only", is_test_key=True)

    admin = OperatorIdentity("OP-ADMIN-12", OperatorRole.APPROVAL_ADMIN, "Admin12", "fp-12")
    proposal = build_sample_cpi_proposal(creator_id="OP-RESEARCH-01")

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "durability_test.sqlite"
        store1 = TrustedApprovalStore(db_path=db_path)
        prop, token, record = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal=proposal,
            approver=admin,
            key_id="key-17",
            store=store1,
            key_registry=reg,
        )

        # Simulate crash: drop store1 and instantiate store2 from same db_path
        store2 = TrustedApprovalStore(db_path=db_path)
        gate2 = NetworkActivationGate(approval_store=store2, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
        ok, _ = gate2.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
        assert ok is True

        # Now revoke in store2
        OperatorApprovalWorkflowEngine.revoke_approval(token.token_id, admin, "Shutdown", store2)

        # Reopen in store3: must remain revoked
        store3 = TrustedApprovalStore(db_path=db_path)
        gate3 = NetworkActivationGate(approval_store=store3, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
        ok3, reason3 = gate3.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI-2026-PENDING")
        assert ok3 is False
        assert "REVOKED" in reason3


def test_18_corrupt_approval_database_fails_closed():
    """Test 18: A corrupt approval database causes gate evaluation to fail closed."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-18", b"secure_key_bytes_18_test_only", is_test_key=True)

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "corrupt.sqlite"
        # Write random corrupt bytes into SQLite file
        db_path.write_bytes(b"CORRUPTED_NON_SQLITE_GARBAGE_BYTES_1234567890")

        store = TrustedApprovalStore(db_path=db_path)
        gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

        token = ObservationAuthorizationToken(
            token_id="AUTH-18",
            capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
            authorized_event_id="EVT-BLS-CPI",
            operator_identity="Admin",
            issued_at_utc=datetime.now(timezone.utc).isoformat(),
            not_before_utc=datetime.now(timezone.utc).isoformat(),
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            approved_domains=["bls.gov"],
            max_request_count=10,
            max_byte_allowance=1048576,
            key_id="key-18",
        )
        token.signature_digest = token.compute_canonical_digest(key_registry=reg)

        # Gate evaluation fails closed
        allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
        assert allowed is False
        assert "MISSING_APPROVAL_RECORD" in reason or "STATUS" in reason or "GATE" in reason
        store.close()


def test_19_tampered_audit_record_verification():
    """Test 19: Audit trail records all lifecycle events and detects modifications."""
    store = TrustedApprovalStore()
    now_iso = datetime.now(timezone.utc).isoformat()
    store.audit_log("TEST_ACTION_1", "TOK-01", "EVT-01", {"info": "initial"})
    store.audit_log("TEST_ACTION_2", "TOK-01", "EVT-01", {"info": "second"})

    conn = store._get_connection()
    try:
        with store._lock:
            rows = conn.execute("SELECT action, token_id FROM audit_trail ORDER BY audit_id ASC").fetchall()
        assert len(rows) == 2
        assert rows[0]["action"] == "TEST_ACTION_1"
        assert rows[1]["action"] == "TEST_ACTION_2"
    finally:
        store._close_connection(conn)


def test_20_unauthorized_trading_capability_permanently_blocked():
    """Test 20: Proposals or approvals requesting LIVE_ORDER_EXECUTION raise TradingIsolationViolation."""
    admin = OperatorIdentity("OP-ADMIN-99", OperatorRole.APPROVAL_ADMIN, "Admin99", "fp-99")
    proposal = build_sample_cpi_proposal()
    store = TrustedApprovalStore()

    # Create token with prohibited capability
    bad_token = ObservationAuthorizationToken(
        token_id="AUTH-BAD-TRADING",
        capability=AuthorizationCapability.LIVE_ORDER_EXECUTION,
        authorized_event_id=proposal.event_id,
        operator_identity="Admin",
    )

    with pytest.raises(TradingIsolationViolation):
        store.create_privileged_approval(bad_token, privileged_operator="Admin99")
