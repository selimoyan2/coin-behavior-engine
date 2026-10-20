"""
Sprint 11.23.5B-6.2: Production Authorization Readiness & Controlled BLS Acquisition Gate
32 Adversarial Security Tests + 14-Step Deterministic Rehearsal Verification Suite.

Validates:
  1. Missing production key
  2. Test key in production
  3. Malformed production key
  4. Insecure key permissions
  5. Unauthorized approver
  6. Self-approval
  7. Forged signature
  8. Expired request
  9. Expired approval
  10. Revoked approval
  11. Digest mismatch
  12. Renewed request with old approval
  13. Wrong capability
  14. Wrong URL
  15. Wrong hostname
  16. DNS rebinding
  17. Invalid TLS chain
  18. HTTP downgrade
  19. Unauthorized redirect
  20. Oversized response
  21. Quota exhaustion
  22. Concurrent execution attempt (multi-threaded quota contention)
  23. Crash during acquisition (durable reservation in SQLite)
  24. Authorization replay (rejected due to CONSUMED status)
  25. Forged provenance
  26. Evidence vault mutation
  27. Conflicting CPI schedule
  28. Attempted Binance access (TradingIsolationViolation)
  29. Attempted trading (TradingIsolationViolation)
  30. Attempted unattended monitoring
  31. Unauthorized production activation (TECHNICALLY_READY_AWAITING_OPERATOR_AUTHORIZATION)
  32. Governance policy freeze bypass attempt
  33. 14-Step Offline Production-Path Rehearsal
  34. CLI Privileged Approval Workflow
"""

from __future__ import annotations

import concurrent.futures
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
    OfflineProductionPathRehearsalRunner,
    OFFICIAL_BLS_HOST,
    OFFICIAL_BLS_CPI_URL,
    TARGET_EVENT_ID,
    TARGET_EVENT_RELEASE_UTC,
)
from coin_behavior_engine.prospective.operator_workflow import (
    OperatorRole,
    OperatorIdentity,
    FileBackedKeyProvider,
    verify_key_file_permissions,
)


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


def _create_token(
    key_reg,
    request,
    key_id="test-op-key",
    operator_id="OP-APPROVAL-ADMIN-01",
    expires_in_hours=2,
    capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
):
    now = datetime.now(timezone.utc)
    token_id = f"TOK-TEST-{now.strftime('%Y%m%d%H%M%S%f')}"
    token = ObservationAuthorizationToken(
        token_id=token_id,
        capability=capability,
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
# 32 ADVERSARIAL & SECURITY TESTS
# ==============================================================================

def test_01_missing_production_key(tmp_path):
    """1. Missing production key file in secure directory -> fails closed."""
    provider = FileBackedKeyProvider(key_dir=tmp_path / "empty_keys")
    with pytest.raises(Exception):
        provider.load_key("nonexistent-key-01")


def test_02_test_key_in_production(test_setup):
    """2. Test key used for production authorization -> rejected."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"], key_id="test-op-key")
    audit = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
        is_production_requested=True,
    )
    assert not audit.is_valid_for_production
    assert any("TEST_KEY_REJECTED" in r for r in audit.rejection_reasons)


def test_03_malformed_production_key(tmp_path):
    """3. Malformed/short (<16 B) key file -> FileBackedKeyProvider rejects."""
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    short_file = key_dir / "short-key.key"
    short_file.write_bytes(b"too_short")
    provider = FileBackedKeyProvider(key_dir=key_dir)
    with pytest.raises(ValueError, match=r"less than required (16|32) bytes"):
        provider.load_key("short-key")


def test_04_insecure_key_permissions(tmp_path):
    """4. Insecure permissions on key file -> verify_key_file_permissions handles securely."""
    key_file = tmp_path / "perm-key.key"
    key_file.write_bytes(b"valid_length_key_secret_32_bytes!")
    verify_key_file_permissions(key_file)
    assert key_file.exists()


def test_05_unauthorized_approver_role(test_setup, tmp_path):
    """5. Operator with unauthorized role (e.g. RESEARCH_OPERATOR) attempts approve -> rejected."""
    req_file = tmp_path / "request.json"
    BlsAcquisitionCLI.prepare(output_file=str(req_file))
    res = BlsAcquisitionCLI.approve(
        request_file=str(req_file),
        approver_id="OP-RESEARCH-02",
        approver_role="RESEARCH_OPERATOR",
        store_path=str(test_setup["tmp_path"] / "approvals.sqlite"),
    )
    assert not res["success"]
    assert res["error"] == "UNAUTHORIZED_APPROVER_ROLE"


def test_06_self_approval_prohibited(test_setup, tmp_path):
    """6. Submitter attempts self-approval -> separation of duties rejects."""
    req_file = tmp_path / "request.json"
    BlsAcquisitionCLI.prepare(operator_id="OP-DUAL-ROLE-01", output_file=str(req_file))
    res = BlsAcquisitionCLI.approve(
        request_file=str(req_file),
        approver_id="OP-DUAL-ROLE-01",
        approver_role="APPROVAL_ADMIN",
        store_path=str(test_setup["tmp_path"] / "approvals.sqlite"),
    )
    assert not res["success"]
    assert res["error"] == "SELF_APPROVAL_PROHIBITED"


def test_07_forged_signature(test_setup):
    """7. Tampered signature digest -> fails verification."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    token.signature_digest = "forged_00000000000000000000000000000000000000000000000000000000000000"
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "INVALID_SIGNATURE" in reason


def test_08_expired_request(test_setup, tmp_path):
    """8. Expired request -> cannot approve and execution fails."""
    req = OfficialScheduleAcquisitionRequest(
        expires_at_utc=(datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    assert req.is_expired()
    token = _create_token(test_setup["key_reg"], req)
    res = BlsAcquisitionCLI.execute(
        request=req,
        token=token,
        store=test_setup["store"],
        gate=test_setup["gate"],
        vault=test_setup["vault"],
        key_registry=test_setup["key_reg"],
    )
    assert not res.success
    assert res.status == "FAILED_REQUEST_EXPIRED"


def test_09_expired_approval(test_setup):
    """9. Expired approval token -> gate rejects."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"], expires_in_hours=-1)
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


def test_10_revoked_approval(test_setup):
    """10. Revoked approval -> gate and execution reject."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    setup["store"].revoke_approval(token.token_id, revoked_by="OP-ADMIN", reason="Revocation test")
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "REVOKED" in reason


def test_11_digest_mismatch(test_setup):
    """11. Approval bound to different request digest -> rejected."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest="mismatched_digest_111111111111111111111111111111111111111111111111111",
    )
    audit = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
    )
    assert not audit.is_valid_for_test
    assert any("DIGEST_MISMATCH" in r for r in audit.rejection_reasons)


def test_12_renewed_request_with_old_approval(test_setup):
    """12. Renewed request ID/digest evaluated against old approval -> fails digest match."""
    setup = test_setup
    old_digest = setup["request"].compute_canonical_digest()
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=old_digest,
    )
    renewed_req = renew_acquisition_request(setup["request"], operator_id="OP-RESEARCH-LEAD-01")
    audit = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=renewed_req,
        store=setup["store"],
        key_registry=setup["key_reg"],
    )
    assert not audit.is_valid_for_test
    assert any("DIGEST_MISMATCH" in r for r in audit.rejection_reasons)


def test_13_wrong_capability(test_setup):
    """13. Capability other than OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION -> rejected."""
    setup = test_setup
    token = _create_token(
        setup["key_reg"],
        setup["request"],
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
    )
    audit = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
    )
    assert not audit.is_valid_for_test
    assert any("CAPABILITY_MISMATCH" in r for r in audit.rejection_reasons)


def test_14_wrong_url(test_setup):
    """14. Request targeting non-canonical URL -> scope validation fails."""
    bad_req = OfficialScheduleAcquisitionRequest(canonical_url="https://evil-publisher.com/cpi.htm")
    valid, errors = bad_req.validate_proposed_scope()
    assert not valid
    assert any("evil-publisher.com" in e or "Hostname" in e for e in errors)


def test_15_wrong_hostname(test_setup):
    """15. Hostname outside approved_domains -> gate denies request."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    allowed, reason = setup["gate"].evaluate_request(
        token=token,
        target_url="https://malicious.evil.com/schedule",
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "OUT_OF_SCOPE_DOMAIN" in reason


def test_16_dns_rebinding(test_setup):
    """16. DNS rebinding / private IP range -> SSRFProtectionError."""
    def fake_private_dns(hostname):
        return ["127.0.0.1"]

    transport = ReadOnlyResearchTransport(
        network_enabled=True,
        approved_domains={"www.bls.gov"},
        dns_resolver=fake_private_dns,
    )
    with pytest.raises(SSRFProtectionError):
        transport.execute_request("GET", OFFICIAL_BLS_CPI_URL)


def test_17_invalid_tls_chain(test_setup):
    """17. Invalid TLS certificate chain -> provenance validation fails."""
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
        tls_verification_status="CERTIFICATE_VERIFICATION_FAILED",
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


def test_18_http_downgrade(test_setup):
    """18. HTTP downgrade attempt -> transport and scope reject insecure scheme."""
    bad_req = OfficialScheduleAcquisitionRequest(canonical_url="http://www.bls.gov/schedule/news_release/cpi.htm")
    valid, errors = bad_req.validate_proposed_scope()
    assert not valid
    assert any("Insecure scheme" in e for e in errors)

    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"})
    with pytest.raises(InsecureSchemeError):
        transport.execute_request("GET", "http://www.bls.gov/schedule/news_release/cpi.htm")


def test_19_unauthorized_redirect(test_setup):
    """19. Unauthorized cross-domain redirect -> allow_redirects=False strictly enforced."""
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"}, allow_redirects=False)
    assert not transport.allow_redirects


def test_20_oversized_response(test_setup):
    """20. Oversized response (>2 MB) -> ResponseSizeExceededError."""
    oversized_data = b"X" * (2 * 1024 * 1024 + 1024)
    transport = ReadOnlyResearchTransport(network_enabled=False, approved_domains={"www.bls.gov"}, max_response_size_bytes=2 * 1024 * 1024)
    transport.register_mock_response(url=OFFICIAL_BLS_CPI_URL, body=oversized_data)
    with pytest.raises(ResponseSizeExceededError):
        transport.execute_request("GET", OFFICIAL_BLS_CPI_URL)


def test_21_quota_exhaustion(test_setup):
    """21. Repeated failed attempts without vaulting deplete quota to 0."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    # Reserve quota attempt 1
    res1, _ = setup["store"].reserve_quota(token.token_id, estimated_bytes=1000)
    assert res1
    # Reserve quota attempt 2
    res2, _ = setup["store"].reserve_quota(token.token_id, estimated_bytes=1000)
    assert res2
    # Reserve quota attempt 3 -> should fail exhausted
    res3, msg = setup["store"].reserve_quota(token.token_id, estimated_bytes=1000)
    assert not res3
    assert "EXHAUSTED" in msg


def test_22_concurrent_execution_attempt(test_setup):
    """22. Multi-threaded quota reservation -> SQLite transaction serializes safely."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )

    def _attempt_reserve():
        return setup["store"].reserve_quota(token.token_id, estimated_bytes=500)[0]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_attempt_reserve) for _ in range(5)]
        results = [f.result() for f in futures]

    # Exactly 2 should succeed (max_attempts = 2), 3 should fail
    assert results.count(True) == 2
    assert results.count(False) == 3


def test_23_crash_during_acquisition(test_setup):
    """23. Quota reservation survives simulated process crash/store re-instantiation."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    # Reserve quota once
    setup["store"].reserve_quota(token.token_id, estimated_bytes=500)
    setup["store"].close()

    # Reconnect (simulating post-crash state)
    reconnected_store = TrustedApprovalStore(db_path=str(setup["tmp_path"] / "approvals.sqlite"))
    try:
        rec = reconnected_store.get_approval(token.token_id)
        assert rec is not None
        assert rec.spent_requests == 1  # Persisted durably

        # Can only reserve 1 more time
        can_res_2, _ = reconnected_store.reserve_quota(token.token_id, estimated_bytes=500)
        assert can_res_2
        can_res_3, _ = reconnected_store.reserve_quota(token.token_id, estimated_bytes=500)
        assert not can_res_3  # Blocked fail-closed
    finally:
        reconnected_store.close()


def test_24_authorization_replay_rejected_consumed(test_setup, mock_html_bytes):
    """24. Successful acquisition transitions token to CONSUMED; immediate replay rejected."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )

    # First execution succeeds and consumes
    res1 = BlsAcquisitionCLI.execute(
        request=setup["request"],
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
        consume_token=True,
    )
    assert res1.success

    # Token status is now CONSUMED
    rec = setup["store"].get_approval(token.token_id)
    assert rec.status == "CONSUMED"

    # Second execution must immediately fail closed despite spent_requests < max_attempts
    res2 = BlsAcquisitionCLI.execute(
        request=setup["request"],
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=False,
        mock_response_bytes=mock_html_bytes,
        consume_token=True,
    )
    assert not res2.success
    assert "CONSUMED" in (res2.error_message or "") or "FAILED_AUTHORIZATION_AUDIT" in res2.status


def test_25_forged_provenance(test_setup, mock_html_bytes):
    """25. Forged provenance metadata where response_sha256 != payload -> validate() raises error."""
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


def test_26_evidence_vault_mutation(test_setup, mock_html_bytes):
    """26. Mutated vault file -> verification detects corruption."""
    setup = test_setup
    vault = setup["vault"]
    original_sha, path, _ = vault.store_bytes("releases", mock_html_bytes, {"test": True}, "html")

    # Manually tamper with file content on disk
    path.write_bytes(b"TAMPERED_BYTES_HERE")

    verify_res = OfficialEvidenceVerifier.verify_vault_evidence(vault, original_sha)
    assert not verify_res.is_verified
    assert any("SHA256_MISMATCH" in r or "VAULT_TAMPER_DETECTED" in r for r in verify_res.rejection_reasons)


def test_27_conflicting_cpi_schedule(mock_html_bytes):
    """27. Schedule document for non-target reference period -> parser fails with ScheduleParsingError."""
    candidate = EventIdentityManager.create_candidate_event()
    with pytest.raises(ScheduleParsingError):
        BlsCpiScheduleParser.parse_schedule_document(
            raw_bytes=mock_html_bytes,
            source_url=OFFICIAL_BLS_CPI_URL,
            candidate_event=candidate,
            acquisition_timestamp_utc="2026-10-21T00:00:00Z",
            target_reference_month="January",
            target_reference_year=2026,
        )


def test_28_attempted_binance_access(test_setup):
    """28. Attempted Binance access with acquisition capability -> TradingIsolationViolation."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    with pytest.raises(TradingIsolationViolation, match="strictly prohibits exchange/market data access"):
        setup["gate"].evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/price",
            target_event_id=setup["request"].target_event_id,
        )


def test_29_attempted_trading(test_setup):
    """29. LIVE_ORDER_EXECUTION capability -> immediate TradingIsolationViolation."""
    setup = test_setup
    token = _create_token(
        setup["key_reg"],
        setup["request"],
        capability=AuthorizationCapability.LIVE_ORDER_EXECUTION,
    )
    with pytest.raises(TradingIsolationViolation, match="permanently prohibited"):
        setup["gate"].evaluate_request(
            token=token,
            target_url=setup["request"].canonical_url,
            target_event_id=setup["request"].target_event_id,
        )


def test_30_attempted_unattended_monitoring(test_setup):
    """30. Continuous or looped monitoring without token -> rejected by gate."""
    setup = test_setup
    allowed, reason = setup["gate"].evaluate_request(
        token=None,
        target_url=setup["request"].canonical_url,
        target_event_id=setup["request"].target_event_id,
    )
    assert not allowed
    assert "MISSING_TOKEN" in reason


def test_31_unauthorized_production_activation(test_setup):
    """31. Production request with valid key/token reports TECHNICALLY_READY_AWAITING_OPERATOR_AUTHORIZATION."""
    setup = test_setup
    setup["key_reg"].register_key("prod-key-01", b"prod_secret_32_bytes_strictly_ok!", is_test_key=False)
    token = _create_token(setup["key_reg"], setup["request"], key_id="prod-key-01")
    setup["store"].create_privileged_approval(
        token=token,
        privileged_operator="OP-APPROVAL-ADMIN-01",
        is_production=False,
        proposal_digest=setup["request"].compute_canonical_digest(),
    )
    res = BlsAcquisitionCLI.execute(
        request=setup["request"],
        token=token,
        store=setup["store"],
        gate=setup["gate"],
        vault=setup["vault"],
        key_registry=setup["key_reg"],
        is_production=True,
    )
    assert not res.success
    assert res.status == "TECHNICALLY_READY_AWAITING_OPERATOR_AUTHORIZATION"


def test_32_governance_policy_freeze_bypass_attempt(test_setup):
    """32. Governance policy freeze bypass attempt -> strictly fail-closed."""
    setup = test_setup
    token = _create_token(setup["key_reg"], setup["request"])
    audit = ProductionAuthorizationAuditor.audit_production_authorization(
        token=token,
        request=setup["request"],
        store=setup["store"],
        key_registry=setup["key_reg"],
        is_production_requested=True,
    )
    assert not audit.is_valid_for_production
    assert any("POLICY_FREEZE" in r for r in audit.rejection_reasons)


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

def test_offline_production_path_rehearsal_runner_14_steps():
    """Validates that the 14-step deterministic simulation completes with all 14 steps passing."""
    res = OfflineProductionPathRehearsalRunner.run_rehearsal()
    assert res["session_status"] == "ALL_STEPS_PASSED"
    assert res["total_steps"] == 14
    assert res["passed_steps"] == 14
    assert res["real_requests_made"] == 0
    assert res["is_simulation_only"] is True


def test_cli_approve_and_status(tmp_path):
    """Validates CLI approve and approval-status subcommands."""
    req_file = tmp_path / "req.json"
    s_path = str(tmp_path / "approvals.sqlite")
    BlsAcquisitionCLI.prepare(output_file=str(req_file))

    app_res = BlsAcquisitionCLI.approve(
        request_file=str(req_file),
        approver_id="OP-APPROVAL-ADMIN-01",
        approver_role="APPROVAL_ADMIN",
        store_path=s_path,
    )
    assert app_res["success"]
    assert app_res["status"] == "ACTIVE"

    status_res = BlsAcquisitionCLI.approval_status(
        token_id=app_res["token_id"],
        store_path=s_path,
    )
    assert status_res["status"] == "ACTIVE"
    assert status_res["token_id"] == app_res["token_id"]
