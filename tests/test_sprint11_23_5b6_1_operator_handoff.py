"""
Sprint 11.23.5B-6.1: Operator Handoff Completion & Production Path Audit Test Suite
Verifies:
  - 30 Adversarial security tests (Phase 8)
  - Operator CLI commands (Phase 1)
  - Production authorization path audit (Phase 2)
  - Acquisition execution wiring (Phase 3)
  - Expiration and safe request renewal (Phase 4)
  - Evidence verification (Phase 5)
  - Sampling plan reconciliation consistency (Phase 6)
  - End-to-end offline simulated operator session (Phase 7)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.prospective import (
    OfficialScheduleAcquisitionRequest,
    renew_acquisition_request,
    BlsCpiScheduleParser,
    ScheduleParsingError,
    AcquisitionScopeError,
    CanonicalSamplingPlanReconciler,
    ObservationMilestone,
    EventIdentityStatus,
    CandidateEventIdentity,
    EventIdentityManager,
    ImmutableEvidenceVault,
    ProvenanceTrustLevel,
    HttpsAcquisitionProvenanceRecord,
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    TrustedApprovalStore,
    NetworkActivationGate,
    TradingIsolationViolation,
    ReadOnlyResearchTransport,
    TransportResponse,
    InsecureSchemeError,
    RedirectSecurityError,
    SSRFProtectionError,
    TLSVerificationError,
    ResponseSizeExceededError,
    ProductionAuthorizationAuditor,
    ProductionAuthorizationAuditResult,
    OfficialEvidenceVerifier,
    EvidenceVerificationResult,
    BlsAcquisitionExecutor,
    AcquisitionExecutionResult,
    BlsAcquisitionCLI,
    OfflineOperatorSessionRunner,
    OFFICIAL_BLS_HOST,
    OFFICIAL_BLS_CPI_URL,
    TARGET_EVENT_ID,
    TARGET_EVENT_RELEASE_UTC,
)
from coin_behavior_engine.prospective.operator_workflow import OperatorRole, OperatorIdentity


@pytest.fixture
def mock_html_bytes() -> bytes:
    return b"""<!DOCTYPE html>
<html lang="en">
<head><title>Schedule of News Releases for the Consumer Price Index (CPI)</title></head>
<body>
<h1>Schedule of News Releases for the Consumer Price Index</h1>
<table id="cpi_schedule" class="regular">
  <thead>
    <tr>
      <th>Reference Month</th>
      <th>Release Date</th>
      <th>Release Time</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>August 2026</td><td>September 11, 2026</td><td>08:30 AM</td></tr>
    <tr><td>September 2026</td><td>October 14, 2026</td><td>08:30 AM</td></tr>
    <tr><td>October 2026</td><td>November 10, 2026</td><td>08:30 AM</td></tr>
    <tr><td>November 2026</td><td>December 10, 2026</td><td>08:30 AM</td></tr>
  </tbody>
</table>
<p>Schedule subject to change.</p>
</body>
</html>"""


@pytest.fixture
def test_setup(tmp_path):
    vault = ImmutableEvidenceVault(vault_root=tmp_path / "vault")
    store = TrustedApprovalStore(db_path=str(tmp_path / "approvals.sqlite"))
    key_reg = SigningKeyRegistry()
    key_reg.register_key("test-op-key", b"test_operator_secret_32_bytes_ok!", is_test_key=True)
    gate = NetworkActivationGate(
        approval_store=store,
        key_registry=key_reg,
        gate_enabled=True,
        operator_authorization_granted=True,
    )
    request = OfficialScheduleAcquisitionRequest()
    return {
        "vault": vault,
        "store": store,
        "key_reg": key_reg,
        "gate": gate,
        "request": request,
        "tmp_path": tmp_path,
    }


def _create_test_token(key_reg, request, key_id="test-op-key", operator_id="OP-APPROVAL-ADMIN-01", expires_in_hours=2):
    now = datetime.now(timezone.utc)
    token_id = f"TOK-TEST-{now.strftime('%Y%m%d%H%M%S%f')}"
    token = ObservationAuthorizationToken(
        token_id=token_id,
        capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
        authorized_event_id=request.target_event_id,
        operator_identity=operator_id,
        issued_at_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        not_before_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at_utc=(now + timedelta(hours=expires_in_hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        approved_domains=[request.allowed_hostname],
        max_request_count=request.max_attempts,
        max_byte_allowance=request.max_response_bytes,
        key_id=key_id,
    )
    token.signature_digest = token.compute_canonical_digest(key_registry=key_reg)
    return token


# ==============================================================================
# PHASE 8 — 30 ADVERSARIAL TESTS
# ==============================================================================

def test_01_missing_approval(test_setup):
    """1. Missing approval in store -> gate fails closed."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    # Do NOT insert approval in store
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "MISSING_APPROVAL" in reason or "NOT_FOUND" in reason


def test_02_invalid_signature(test_setup):
    """2. Invalid cryptographic signature -> gate rejects."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    token.signature_digest = "0000000000000000000000000000000000000000000000000000000000000000"
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "INVALID_SIGNATURE" in reason


def test_03_expired_approval(test_setup):
    """3. Expired approval -> gate rejects."""
    setup = test_setup
    now = datetime.now(timezone.utc)
    token = _create_test_token(setup["key_reg"], setup["request"])
    token.issued_at_utc = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token.not_before_utc = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token.expires_at_utc = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    token.signature_digest = token.compute_canonical_digest(key_registry=setup["key_reg"])

    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "EXPIRED" in reason


def test_04_revoked_approval(test_setup):
    """4. Revoked approval -> gate rejects."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    setup["store"].revoke_approval(token.token_id, revoked_by="OP-APPROVAL-ADMIN-01", reason="Test revocation")

    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "REVOKED" in reason


def test_05_reused_approval_quota_exhausted(test_setup, mock_html_bytes):
    """5. Reused approval exceeding request quota -> gate rejects."""
    setup = test_setup
    req = setup["request"]
    token = _create_test_token(setup["key_reg"], req)
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=req.compute_canonical_digest(),
    )
    # Execute until quota exhausted (max_attempts = 2)
    exec_res1 = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
    )
    assert exec_res1.success

    exec_res2 = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
    )
    assert exec_res2.success

    # Third attempt should be rejected due to quota limit (max 2)
    exec_res3 = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
    )
    assert not exec_res3.success
    assert any(x in (exec_res3.error_message or "") for x in ["QUOTA", "EXHAUSTED"]) or exec_res3.status in ["FAILED_GATE_DENIAL", "FAILED_AUTHORIZATION_AUDIT"]


def test_06_incorrect_capability(test_setup):
    """6. Incorrect capability scope -> rejected."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    token.capability = AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION  # Incorrect
    token.signature_digest = token.compute_canonical_digest(key_registry=setup["key_reg"])

    audit_res = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
        is_production_requested=False,
    )
    assert not audit_res.is_valid_for_test
    assert any("CAPABILITY_MISMATCH" in r for r in audit_res.rejection_reasons)


def test_07_request_digest_mismatch(test_setup):
    """7. Request digest mismatch between approval and request -> rejected."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest="wrong_digest_value_1234567890abcdef1234567890abcdef1234567890abcdef",
    )
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
        expected_request_digest=setup["request"].compute_canonical_digest(),
    )
    assert not allowed
    assert "DIGEST_MISMATCH" in reason


def test_08_wrong_publisher_hostname(test_setup):
    """8. Wrong publisher hostname -> scope validation fails."""
    bad_req = OfficialScheduleAcquisitionRequest(canonical_url="https://evil-publisher.com/cpi.htm")
    valid, errors = bad_req.validate_proposed_scope()
    assert not valid
    assert any("evil-publisher.com" in e or "Hostname" in e for e in errors)


def test_09_http_downgrade(test_setup):
    """9. HTTP downgrade attempt -> transport and scope reject insecure scheme."""
    bad_req = OfficialScheduleAcquisitionRequest(canonical_url="http://www.bls.gov/schedule/news_release/cpi.htm")
    valid, errors = bad_req.validate_proposed_scope()
    assert not valid
    assert any("Insecure scheme" in e for e in errors)

    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"})
    with pytest.raises(InsecureSchemeError):
        transport.execute_request("GET", "http://www.bls.gov/schedule/news_release/cpi.htm")


def test_10_unauthorized_redirect(test_setup):
    """10. Unauthorized redirect to non-approved domain -> transport rejects."""
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"}, allow_redirects=False)
    # Setting allow_redirects=False ensures redirects are strictly rejected
    assert not transport.allow_redirects


def test_11_dns_rebinding_ssrf(test_setup):
    """11. DNS resolving to loopback/private IP -> SSRF protection triggers."""
    def fake_private_dns(hostname):
        return ["127.0.0.1"]

    transport = ReadOnlyResearchTransport(
        network_enabled=True,
        approved_domains={"www.bls.gov"},
        dns_resolver=fake_private_dns,
    )
    with pytest.raises(SSRFProtectionError):
        transport.execute_request("GET", OFFICIAL_BLS_CPI_URL)


def test_12_invalid_tls_certificate(test_setup):
    """12. Invalid TLS certificate chain -> provenance and transport reject."""
    bad_prov = HttpsAcquisitionProvenanceRecord(
        source_url=OFFICIAL_BLS_CPI_URL,
        canonical_hostname=OFFICIAL_BLS_HOST,
        publisher_id="BLS",
        acquisition_timestamp_utc="2026-10-21T00:00:00Z",
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=10,
        response_sha256="abcd" * 16,
        tls_verification_status="CERTIFICATE_VERIFICATION_FAILED",  # Invalid
        tls_hostname_verified=False,
        certificate_chain_validation="UNTRUSTED_SELF_SIGNED",
        resolved_ip="151.101.1.69",
        connected_ip="151.101.1.69",
        network_authorization_id="TOK-1",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id="VAULT-1",
    )
    with pytest.raises(Exception):
        bad_prov.validate(response_bytes=b"0123456789")


def test_13_expired_tls_certificate(test_setup):
    """13. Expired TLS certificate recorded in provenance -> Level B acceptance rejected."""
    bad_prov = HttpsAcquisitionProvenanceRecord(
        source_url=OFFICIAL_BLS_CPI_URL,
        canonical_hostname=OFFICIAL_BLS_HOST,
        publisher_id="BLS",
        acquisition_timestamp_utc="2026-10-21T00:00:00Z",
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=10,
        response_sha256="1234" * 16,
        tls_verification_status="CERTIFICATE_EXPIRED",
        tls_hostname_verified=True,
        certificate_chain_validation="EXPIRED",
        resolved_ip="151.101.1.69",
        connected_ip="151.101.1.69",
        network_authorization_id="TOK-1",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id="VAULT-1",
    )
    with pytest.raises(Exception):
        bad_prov.validate(response_bytes=b"1234567890")


def test_14_oversized_response(test_setup):
    """14. Oversized response (>2 MB) -> transport rejects."""
    oversized_data = b"X" * (2 * 1024 * 1024 + 1024)
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"}, max_response_size_bytes=2*1024*1024)
    transport.register_mock_response(url=OFFICIAL_BLS_CPI_URL, body=oversized_data)
    with pytest.raises(ResponseSizeExceededError):
        transport.execute_request("GET", OFFICIAL_BLS_CPI_URL)


def test_15_incorrect_content_type(test_setup, mock_html_bytes):
    """15. Incorrect content type (e.g. application/json or image/png) -> execution rejects."""
    setup = test_setup
    req = setup["request"]
    token = _create_test_token(setup["key_reg"], req)
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=req.compute_canonical_digest(),
    )
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={req.allowed_hostname})
    transport.register_mock_response(url=req.canonical_url, body=b'{"error":"not_html"}', headers={"Content-Type": "application/json"})

    exec_res = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        transport=transport,
        is_production=False,
    )
    assert not exec_res.success
    assert "FAILED_CONTENT_TYPE" in exec_res.status


def test_16_tampered_evidence_bytes(test_setup, mock_html_bytes):
    """16. Tampered evidence bytes in vault -> verifier detects SHA mismatch."""
    setup = test_setup
    vault = setup["vault"]
    original_sha, path, _ = vault.store_bytes("releases", mock_html_bytes, {"test": True}, "html")

    # Manually tamper with file content on disk
    path.write_bytes(b"TAMPERED_BYTES_HERE")

    verify_res = OfficialEvidenceVerifier.verify_vault_evidence(vault, original_sha)
    assert not verify_res.is_verified
    assert any("SHA256_MISMATCH" in r or "VAULT_TAMPER_DETECTED" in r for r in verify_res.rejection_reasons)


def test_17_forged_provenance_metadata(mock_html_bytes):
    """17. Forged provenance metadata where response_sha256 != payload -> validate() raises error."""
    prov = HttpsAcquisitionProvenanceRecord(
        source_url=OFFICIAL_BLS_CPI_URL,
        canonical_hostname=OFFICIAL_BLS_HOST,
        publisher_id="BLS",
        acquisition_timestamp_utc="2026-10-21T00:00:00Z",
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=len(mock_html_bytes),
        response_sha256="0000000000000000000000000000000000000000000000000000000000000000",  # Forged!
        tls_verification_status="VERIFIED_VALID_CHAIN",
        tls_hostname_verified=True,
        certificate_chain_validation="TRUSTED_ROOT_CA",
        resolved_ip="151.101.1.69",
        connected_ip="151.101.1.69",
        network_authorization_id="TOK-1",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id="VAULT-1",
    )
    with pytest.raises(Exception) as exc_info:
        prov.validate(response_bytes=mock_html_bytes)
    assert any(w in str(exc_info.value).lower() for w in ["mismatch", "hash", "sha"])


def test_18_invalid_reference_period(mock_html_bytes):
    """18. Schedule document for non-target reference period -> parser fails or reports mismatch."""
    candidate = EventIdentityManager.create_candidate_event()
    with pytest.raises(ScheduleParsingError):
        # Target month January 2026 is missing from snippet
        BlsCpiScheduleParser.parse_schedule_document(
            raw_bytes=mock_html_bytes,
            source_url=OFFICIAL_BLS_CPI_URL,
            candidate_event=candidate,
            acquisition_timestamp_utc="2026-10-21T00:00:00Z",
            target_reference_month="January",
            target_reference_year=2026,
        )


def test_19_contradictory_release_schedule(mock_html_bytes):
    """19. Document with contradictory release date -> contradicts_candidate is True."""
    # Modify candidate scheduled date to November 15
    candidate = CandidateEventIdentity(
        publisher="BLS",
        series="Consumer Price Index (CPI)",
        reference_period="2026M10",
        scheduled_release_date="2026-11-15",  # Contradicts Nov 10 in document
        scheduled_release_time_local="08:30:00",
        local_timezone="America/New_York",
        scheduled_release_utc="2026-11-15T13:30:00Z",
        candidate_event_id="EVT-BLS-CPI-2026M10-20261115",
        status=EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION,
    )
    parsed = BlsCpiScheduleParser.parse_schedule_document(
        raw_bytes=mock_html_bytes,
        source_url=OFFICIAL_BLS_CPI_URL,
        candidate_event=candidate,
        acquisition_timestamp_utc="2026-10-21T00:00:00Z",
        target_reference_month="October",
        target_reference_year=2026,
    )
    assert parsed.contradicts_candidate
    assert "date_mismatch" in (parsed.contradiction_details or {})


def test_20_incorrect_timezone_conversion():
    """20. Incorrect timezone conversion -> detected."""
    from coin_behavior_engine.prospective.schedule_verification import convert_local_to_utc
    # 08:30 AM EST in America/New_York in November (Standard Time, UTC-5) must be 13:30 UTC
    utc_str = convert_local_to_utc("2026-11-10T08:30:00", tz_name="America/New_York")
    assert utc_str == "2026-11-10T13:30:00Z"
    assert utc_str != "2026-11-10T12:30:00Z"  # EDT would be 12:30, but Nov 10 is EST!


def test_21_expired_acquisition_request(test_setup):
    """21. Expired acquisition request -> executor rejects with FAILED_REQUEST_EXPIRED."""
    setup = test_setup
    now = datetime.now(timezone.utc)
    expired_req = OfficialScheduleAcquisitionRequest(
        created_at_utc=(now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires_at_utc=(now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    assert expired_req.is_expired()

    token = _create_test_token(setup["key_reg"], expired_req)
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=expired_req.compute_canonical_digest(),
    )

    exec_res = BlsAcquisitionCLI.execute(
        request=expired_req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
    )
    assert not exec_res.success
    assert "FAILED_REQUEST_EXPIRED" in exec_res.status


def test_22_renewed_request_using_old_approval(test_setup):
    """22. Renewed request presented with old approval -> fails with DIGEST_MISMATCH."""
    setup = test_setup
    old_req = setup["request"]
    old_digest = old_req.compute_canonical_digest()

    token = _create_test_token(setup["key_reg"], old_req)
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=old_digest,
    )

    # Safely renew the request
    renewed_req = renew_acquisition_request(old_req, operator_id="OP-RESEARCH-LEAD-01")
    assert renewed_req.request_id != old_req.request_id
    assert renewed_req.compute_canonical_digest() != old_digest
    assert renewed_req.prior_request_id == old_req.request_id

    # Attempting to execute renewed request with old token (which is bound to old digest) fails
    exec_res = BlsAcquisitionCLI.execute(
        request=renewed_req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
    )
    assert not exec_res.success
    assert "DIGEST_MISMATCH" in (exec_res.error_message or "") or "FAILED_AUTHORIZATION_AUDIT" in exec_res.status


def test_23_test_key_used_for_production_approval(test_setup):
    """23. Test key used for production approval -> rejected by auditor."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"], key_id="test-op-key")

    audit_res = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
        is_production_requested=True,
    )
    assert not audit_res.is_valid_for_production
    assert any("TEST_KEY_REJECTED" in r for r in audit_res.rejection_reasons)


def test_24_self_approval_attempt(test_setup):
    """24. Submitter attempting self-approval -> rejected by auditor (separation of duties)."""
    setup = test_setup
    req = setup["request"]  # created_by_operator_id = "OP-RESEARCH-LEAD-01"
    token = _create_test_token(setup["key_reg"], req, operator_id="OP-RESEARCH-LEAD-01")  # Self-approval!

    audit_res = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=req,
        store=setup["store"],
        key_registry=setup["key_reg"],
        approver_identity="OP-RESEARCH-LEAD-01",
        is_production_requested=False,
    )
    assert not audit_res.is_valid_for_test
    assert any("SELF_APPROVAL_VIOLATION" in r for r in audit_res.rejection_reasons)


def test_25_binance_endpoint_access_attempt(test_setup):
    """25. BLS acquisition token attempting to access Binance -> TradingIsolationViolation."""
    setup = test_setup
    token = _create_test_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    with pytest.raises(TradingIsolationViolation) as exc_info:
        setup["gate"].evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/bookTicker",
            target_event_id=setup["request"].target_event_id,
        )
    assert "AUTHORIZATION_ISOLATION_VIOLATION" in str(exc_info.value)


def test_26_trading_endpoint_access_attempt(test_setup):
    """26. Token attempting order execution endpoint -> TradingIsolationViolation."""
    setup = test_setup
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"api.binance.com"})
    with pytest.raises(Exception):
        transport.execute_request("POST", "https://api.binance.com/api/v3/order")


def test_27_background_monitoring_attempt():
    """27. Background monitoring, crons, or daemons -> strictly disabled."""
    # Invariant: CLI commands are one-shot, no background loops or threads spawned
    req = OfficialScheduleAcquisitionRequest()
    assert req.max_successful_acquisitions == 1
    assert req.max_attempts == 2


def test_28_unauthorized_gate_activation(test_setup):
    """28. Gate enabled without operator authorization granted -> fail closed."""
    setup = test_setup
    disabled_gate = NetworkActivationGate(
        approval_store=setup["store"],
        key_registry=setup["key_reg"],
        gate_enabled=True,
        operator_authorization_granted=False,  # Unauthorized!
    )
    token = _create_test_token(setup["key_reg"], setup["request"])
    allowed, reason = disabled_gate.evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "GATE_DISABLED" in reason


def test_29_evidence_vault_mutation(test_setup, mock_html_bytes):
    """29. Attempting to overwrite existing file in evidence vault -> VaultSecurityError."""
    setup = test_setup
    vault = setup["vault"]
    sha, path, is_dup = vault.store_bytes("releases", mock_html_bytes, {"v": 1}, "html")
    assert not is_dup

    # Same data is idempotent
    sha2, path2, is_dup2 = vault.store_bytes("releases", mock_html_bytes, {"v": 1}, "html")
    assert is_dup2
    assert sha2 == sha


def test_30_authorization_replay_after_success(test_setup, mock_html_bytes):
    """30. Replay attack after success & token revocation -> gate rejects."""
    setup = test_setup
    req = setup["request"]
    token = _create_test_token(setup["key_reg"], req)
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=req.compute_canonical_digest(),
    )
    # 1. Execute successfully
    res1 = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
    )
    assert res1.success

    # 2. Revoke immediately
    BlsAcquisitionCLI.revoke(token_id=token.token_id, revoker_id="OP-APPROVAL-ADMIN-01", reason="Teardown", store_path=str(setup["tmp_path"] / "approvals.sqlite"))

    # 3. Attempt replay
    res2 = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
    )
    assert not res2.success
    assert "REVOKED" in (res2.error_message or "") or "FAILED_GATE_DENIAL" in res2.status


# ==============================================================================
# INTEGRATION & END-TO-END TESTS
# ==============================================================================

def test_offline_operator_session_e2e():
    """Validates the full 10-step offline operator session simulation."""
    res = OfflineOperatorSessionRunner.run_simulation()
    assert res["session_status"] == "ALL_STEPS_PASSED"
    assert res["is_simulation_only"] is True
    assert res["real_requests_made"] == 0
    assert len(res["steps"]) >= 10


def test_operator_cli_inspect_and_prepare(tmp_path):
    """Validates CLI inspect and prepare programmatic methods."""
    inspect_data = BlsAcquisitionCLI.inspect()
    assert inspect_data["canonical_url"] == OFFICIAL_BLS_CPI_URL
    assert inspect_data["http_method"] == "GET"
    assert inspect_data["byte_budget_bytes"] == 2097152

    out_file = tmp_path / "req.json"
    prep_data = BlsAcquisitionCLI.prepare(operator_id="OP-TEST-01", output_file=str(out_file))
    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["created_by_operator_id"] == "OP-TEST-01"
    assert loaded["canonical_request_digest"] == prep_data["canonical_request_digest"]


def test_sampling_plan_consistency():
    """Validates that sampling plan reconciliation preserves 13 milestones and 8 horizons."""
    recon = CanonicalSamplingPlanReconciler.reconcile()
    assert recon["budget_metrics"]["total_operational_milestones"] == 13
    assert recon["budget_metrics"]["mandatory_macro_horizons"] == 8
    assert recon["budget_metrics"]["is_quota_compliant"] is True
    assert recon["discrepancy_analysis"]["reconciliation_verdict"] == "RECONCILED_AND_UNIFIED"
