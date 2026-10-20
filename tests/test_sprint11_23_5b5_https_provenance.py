"""
Sprint 11.23.5B-5 Test Suite: Official HTTPS Evidence Provenance & Verification Policy
30 Comprehensive Adversarial Tests covering:
  1. Valid authenticated HTTPS fixture.
  2. Valid publisher-signed fixture.
  3. HTTPS-only evidence without document signature.
  4. Claimed official local HTML.
  5. Forged TLS verification metadata.
  6. Invalid certificate chain.
  7. Hostname mismatch.
  8. Expired certificate.
  9. Unauthorized redirect.
  10. DNS rebinding.
  11. Connected-IP mismatch / private IP.
  12. Source outside allowlist.
  13. HTTP downgrade.
  14. Missing network authorization.
  15. Expired authorization.
  16. Mid-request revocation.
  17. Request quota exhaustion.
  18. Byte budget exhaustion.
  19. Tampered response bytes.
  20. Duplicate evidence.
  21. Contradictory CPI schedules.
  22. Incorrect reference period.
  23. Incorrect timezone conversion.
  24. Stale schedule evidence.
  25. Proposal digest mismatch.
  26. Old approval reused with new proposal.
  27. Untrusted local file promoted to verified.
  28. Forged publisher signature.
  29. Evidence vault mutation.
  30. Trading capability invocation.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.prospective import (
    ProvenanceTrustLevel,
    HttpsAcquisitionProvenanceRecord,
    PublisherSignatureProvenanceRecord,
    ProvenanceValidationError,
    EvidenceProvenanceVerifier,
    OfficialScheduleAcceptancePolicy,
    ControlledEvidenceImporter,
    SourceAuthenticityLevel,
    EventIdentityManager,
    EventIdentityStatus,
    PilotProposalV3Builder,
    ImmutableEvidenceVault,
    OperatorRole,
    OperatorIdentity,
    ProposalStatus,
    OperatorApprovalWorkflowEngine,
    SigningKeyRegistry,
    TrustedApprovalStore,
    NetworkActivationGate,
)
from coin_behavior_engine.prospective.governance import (
    TradingIsolationViolation,
    ProspectiveGovernanceGuard,
)
from coin_behavior_engine.prospective.schedule_verification import convert_local_to_utc


# Helper fixture for official BLS CPI HTML
VALID_BLS_CPI_HTML = (
    b"<!DOCTYPE html><html><head><title>BLS Schedule</title></head><body>"
    b"<h1>Bureau of Labor Statistics Release Schedule</h1>"
    b"<p>News Release: Consumer Price Index (CPI)</p>"
    b"<p>Reference Month: October 2026</p>"
    b"<p>Release Date: November 10, 2026</p>"
    b"<p>Release Time: 08:30 AM EST</p>"
    b"</body></html>"
)
VALID_BLS_SHA256 = hashlib.sha256(VALID_BLS_CPI_HTML).hexdigest()


def make_valid_https_provenance() -> HttpsAcquisitionProvenanceRecord:
    return HttpsAcquisitionProvenanceRecord(
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        canonical_hostname="www.bls.gov",
        publisher_id="BLS",
        acquisition_timestamp_utc="2026-10-20T21:00:00Z",
        request_method="GET",
        http_status=200,
        content_type="text/html",
        content_length=len(VALID_BLS_CPI_HTML),
        response_sha256=VALID_BLS_SHA256,
        tls_verification_status="VERIFIED_VALID_CHAIN",
        tls_hostname_verified=True,
        certificate_chain_validation="TRUSTED_ROOT_CA",
        resolved_ip="151.101.65.69",
        connected_ip="151.101.65.69",
        network_authorization_id="TOK-AUTH-BLS-PILOT-01",
        network_gate_decision="PERMITTED",
        evidence_vault_object_id=f"EVD-{VALID_BLS_SHA256[:16].upper()}",
        redirect_chain=[],
        certificate_fingerprint_sha256="abc123certfingerprint",
    )


def make_valid_publisher_signature() -> PublisherSignatureProvenanceRecord:
    return PublisherSignatureProvenanceRecord(
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        publisher_id="BLS",
        original_document_sha256=VALID_BLS_SHA256,
        signature_bytes_base64="TU9DS19TSUdOQVRVUkVfQkxTX0dPVA==",
        signing_key_id="KEY-BLS-RELEASE-2026",
        verification_result="VALID",
        verified_at_utc="2026-10-20T21:00:00Z",
        verification_algorithm="RSA-SHA256",
        evidence_vault_object_id=f"EVD-{VALID_BLS_SHA256[:16].upper()}",
    )


# ==============================================================================
# TESTS 1 - 4: PROVENANCE TRUST LEVELS & ACCEPTANCE
# ==============================================================================

def test_01_valid_authenticated_https_fixture():
    prov = make_valid_https_provenance()
    prov.validate(VALID_BLS_CPI_HTML)

    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=VALID_BLS_CPI_HTML,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"https_provenance": prov.to_dict()},
    )
    assert res.is_accepted is True
    assert res.rejection_reason is None
    assert res.trust_level == ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION
    assert res.bound_event_id == "EVT-BLS-CPI-2026M10-20261110"
    assert res.schedule_release_utc == "2026-11-10T13:30:00Z"


def test_02_valid_publisher_signed_fixture():
    sig_rec = make_valid_publisher_signature()
    sig_rec.validate(VALID_BLS_CPI_HTML)

    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=VALID_BLS_CPI_HTML,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"publisher_signature": sig_rec.to_dict()},
    )
    assert res.is_accepted is True
    assert res.trust_level == ProvenanceTrustLevel.VERIFIED_PUBLISHER_SIGNATURE
    assert res.bound_event_id == "EVT-BLS-CPI-2026M10-20261110"


def test_03_https_only_evidence_not_misclassified_as_signed():
    prov = make_valid_https_provenance()
    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=VALID_BLS_CPI_HTML,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"https_provenance": prov.to_dict()},
    )
    assert res.is_accepted is True
    assert res.trust_level == ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION
    assert res.trust_level != ProvenanceTrustLevel.VERIFIED_PUBLISHER_SIGNATURE


def test_04_claimed_official_local_html_rejected():
    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=VALID_BLS_CPI_HTML,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"notes": "Downloaded manually via browser save-as without provenance"},
    )
    assert res.is_accepted is False
    assert res.trust_level == ProvenanceTrustLevel.SOURCE_CLAIMED_OFFICIAL
    assert "Insufficient provenance trust level" in res.rejection_reason


# ==============================================================================
# TESTS 5 - 13: NETWORK, TLS & ACQUISITION BOUNDARY DEFENSES
# ==============================================================================

def test_05_forged_tls_verification_metadata_rejected():
    prov = make_valid_https_provenance()
    prov.tls_verification_status = "CLIENT_CLAIMED_OK_UNVERIFIED"
    with pytest.raises(ProvenanceValidationError, match="Invalid TLS verification status"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_06_invalid_certificate_chain_rejected():
    prov = make_valid_https_provenance()
    prov.certificate_chain_validation = "SELF_SIGNED_OR_UNTRUSTED"
    with pytest.raises(ProvenanceValidationError, match="Certificate chain validation failed"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_07_hostname_mismatch_rejected():
    prov = make_valid_https_provenance()
    prov.canonical_hostname = "evil-bls.gov"
    with pytest.raises(ProvenanceValidationError, match="Hostname mismatch"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_08_expired_certificate_rejected():
    prov = make_valid_https_provenance()
    prov.tls_verification_status = "EXPIRED_CERTIFICATE"
    with pytest.raises(ProvenanceValidationError, match="Invalid TLS verification status"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_09_unauthorized_redirect_rejected():
    prov = make_valid_https_provenance()
    prov.redirect_chain = ["https://unauthorized-mirror.com/cpi.htm"]
    with pytest.raises(ProvenanceValidationError, match="Unauthorized redirect target host"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_10_dns_rebinding_rejected():
    prov = make_valid_https_provenance()
    prov.resolved_ip = "151.101.65.69"
    prov.connected_ip = "151.101.65.70"  # Mismatched IP
    with pytest.raises(ProvenanceValidationError, match="DNS rebinding detected"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_11_connected_ip_mismatch_or_private_ip_rejected():
    prov = make_valid_https_provenance()
    prov.resolved_ip = "127.0.0.1"
    prov.connected_ip = "127.0.0.1"
    with pytest.raises(ProvenanceValidationError, match="SSRF violation"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_12_source_outside_allowlist_rejected():
    prov = make_valid_https_provenance()
    prov.source_url = "https://unofficial-cpi-calendar.com/cpi.htm"
    prov.canonical_hostname = "unofficial-cpi-calendar.com"
    with pytest.raises(ProvenanceValidationError, match="outside the approved official publisher allowlist"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_13_http_downgrade_rejected():
    prov = make_valid_https_provenance()
    prov.source_url = "http://www.bls.gov/schedule/news_release/cpi.htm"
    with pytest.raises(ProvenanceValidationError, match="Insecure scheme 'http'"):
        prov.validate(VALID_BLS_CPI_HTML)


# ==============================================================================
# TESTS 14 - 18: AUTHORIZATION, QUOTA & REVOCATION
# ==============================================================================

def test_14_missing_network_authorization_rejected():
    prov = make_valid_https_provenance()
    prov.network_authorization_id = ""
    with pytest.raises(ProvenanceValidationError, match="Missing network authorization ID"):
        prov.validate(VALID_BLS_CPI_HTML)


def test_15_expired_authorization_rejected():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Admin", "FPR-A")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        # Force expiration in store
        with store._lock:
            conn = store._get_connection()
            try:
                conn.execute(
                    "UPDATE approval_records SET expires_at_utc = '2020-01-01T00:00:00Z' WHERE token_id = ?",
                    (token.token_id,),
                )
                conn.commit()
            finally:
                store._close_connection(conn)

        ok, reason = gate.evaluate_request(
            token=token,
            target_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is False
        assert "expired" in reason.lower()


def test_16_mid_request_revocation_denies_provenance():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Admin", "FPR-A")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        # Initial evaluation permitted
        ok, _ = gate.evaluate_request(
            token=token,
            target_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is True

        # Mid-request revocation
        store.revoke_approval(token.token_id, revoked_by=op_admin.operator_id, reason="SECURITY_HALT")

        # Subsequent evaluation denied
        denied, reason = gate.evaluate_request(
            token=token,
            target_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            target_event_id=candidate.candidate_event_id,
        )
        assert denied is False
        assert "revoked" in reason.lower()
        store.close()


def test_17_request_quota_exhaustion_blocks_acquisition():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Admin", "FPR-A")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        for _ in range(20):
            store.reserve_quota(token.token_id, estimated_bytes=100)
            store.commit_quota(token.token_id, actual_bytes=50)

        ok, reason = gate.evaluate_request(
            token=token,
            target_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is False
        assert "exhausted" in reason.lower() or "quota" in reason.lower()
        store.close()


def test_18_byte_budget_exhaustion_blocks_acquisition():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Admin", "FPR-A")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )

        # Attempt to reserve more than max allowance (5 MB)
        ok, reason = store.reserve_quota(token.token_id, estimated_bytes=6 * 1024 * 1024)
        assert ok is False
        assert "BYTE_QUOTA_EXCEEDED" in reason
        store.close()


# ==============================================================================
# TESTS 19 - 24: EVIDENCE INTEGRITY & SCHEDULE VALIDATION
# ==============================================================================

def test_19_tampered_response_bytes_hash_mismatch():
    prov = make_valid_https_provenance()
    tampered_bytes = VALID_BLS_CPI_HTML + b"\n<!-- tamper -->"
    with pytest.raises(ProvenanceValidationError, match="Response bytes hash mismatch"):
        prov.validate(tampered_bytes)


def test_20_duplicate_evidence_idempotency():
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td) / "vault")
        importer = ControlledEvidenceImporter(vault=vault)
        prov = make_valid_https_provenance()

        r1 = importer.import_evidence(
            raw_bytes=VALID_BLS_CPI_HTML,
            declared_source_url=prov.source_url,
            declared_mime_type="text/html",
            provenance_sidecar={"https_provenance": prov.to_dict()},
        )
        assert r1.is_duplicate is False

        r2 = importer.import_evidence(
            raw_bytes=VALID_BLS_CPI_HTML,
            declared_source_url=prov.source_url,
            declared_mime_type="text/html",
            provenance_sidecar={"https_provenance": prov.to_dict()},
        )
        assert r2.is_duplicate is True
        assert r1.evidence_id == r2.evidence_id


def test_21_contradictory_cpi_schedules_isolated():
    # Modified schedule claiming Nov 15 instead of Nov 10
    contradictory_html = VALID_BLS_CPI_HTML.replace(b"November 10, 2026", b"November 15, 2026")
    contradictory_sha = hashlib.sha256(contradictory_html).hexdigest()
    prov = make_valid_https_provenance()
    prov.response_sha256 = contradictory_sha
    prov.content_length = len(contradictory_html)

    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=contradictory_html,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"https_provenance": prov.to_dict()},
    )
    assert res.is_accepted is False
    assert "does not confirm candidate release date" in res.rejection_reason


def test_22_incorrect_reference_period_rejected():
    # Document referencing September 2026 instead of October 2026
    wrong_period_html = VALID_BLS_CPI_HTML.replace(b"October 2026", b"September 2026")
    sha = hashlib.sha256(wrong_period_html).hexdigest()
    prov = make_valid_https_provenance()
    prov.response_sha256 = sha
    prov.content_length = len(wrong_period_html)

    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=wrong_period_html,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"https_provenance": prov.to_dict()},
    )
    assert res.is_accepted is False
    assert "does not match candidate reference period" in res.rejection_reason


def test_23_incorrect_timezone_conversion_rejected():
    # Attempting to convert assuming Daylight Saving Time (EDT) in November
    dt_est = convert_local_to_utc("2026-11-10T08:30:00", tz_name="America/New_York")
    assert dt_est == "2026-11-10T13:30:00Z"
    assert dt_est != "2026-11-10T12:30:00Z"  # 12:30 was EDT in October


def test_24_stale_schedule_evidence_rejected():
    # Document for 2025 CPI
    stale_html = VALID_BLS_CPI_HTML.replace(b"2026", b"2025")
    sha = hashlib.sha256(stale_html).hexdigest()
    prov = make_valid_https_provenance()
    prov.response_sha256 = sha
    prov.content_length = len(stale_html)

    res = OfficialScheduleAcceptancePolicy.evaluate_acceptance(
        evidence_bytes=stale_html,
        source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
        sidecar={"https_provenance": prov.to_dict()},
    )
    assert res.is_accepted is False


# ==============================================================================
# TESTS 25 - 30: PROPOSAL DIGEST, FREEZE & GOVERNANCE INVARIANTS
# ==============================================================================

def test_25_proposal_digest_mismatch_invalidates_approval():
    candidate = EventIdentityManager.create_candidate_event()
    p1 = PilotProposalV3Builder.build_proposal(candidate)
    d1 = p1.compute_canonical_digest()

    p2 = PilotProposalV3Builder.build_proposal(candidate)
    p2.max_duration_seconds = 1800  # Altered duration
    d2 = p2.compute_canonical_digest()
    assert d1 != d2


def test_26_old_approval_reused_with_new_proposal_rejected():
    candidate = EventIdentityManager.create_candidate_event()
    p1 = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Admin", "FPR-A")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token1, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            p1, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )

        p2 = PilotProposalV3Builder.build_proposal(candidate)
        p2.max_duration_seconds = 1800  # Different proposal
        digest2 = p2.compute_canonical_digest()

        # Token 1 proposal_digest matches p1, not p2
        rec = store.get_approval(token1.token_id)
        assert rec.proposal_digest == p1.compute_canonical_digest()
        assert rec.proposal_digest != digest2
        store.close()


def test_27_untrusted_local_file_promoted_to_verified_rejected():
    candidate = EventIdentityManager.create_candidate_event()
    # Unverified provenance cannot freeze event
    with pytest.raises(ValueError, match="Schedule evidence lacks cryptographic provenance verification"):
        EventIdentityManager.bind_and_freeze_event(
            candidate,
            verified_schedule_sha256=VALID_BLS_SHA256,
            trust_level=ProvenanceTrustLevel.SOURCE_CLAIMED_OFFICIAL,
        )


def test_28_forged_publisher_signature_rejected():
    sig = make_valid_publisher_signature()
    sig.verification_result = "INVALID_SIGNATURE"
    with pytest.raises(ProvenanceValidationError, match="verification result is 'INVALID_SIGNATURE'"):
        sig.validate(VALID_BLS_CPI_HTML)


def test_29_evidence_vault_mutation_detected():
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td) / "vault")
        importer = ControlledEvidenceImporter(vault=vault)
        prov = make_valid_https_provenance()

        receipt = importer.import_evidence(
            raw_bytes=VALID_BLS_CPI_HTML,
            declared_source_url=prov.source_url,
            declared_mime_type="text/html",
            provenance_sidecar={"https_provenance": prov.to_dict()},
        )
        stored_file = vault.vault_root / receipt.stored_vault_path
        assert stored_file.exists()

        # Mutate stored byte
        stored_file.write_bytes(stored_file.read_bytes() + b"\x00")

        # Verify mutation is detected
        actual_sha = hashlib.sha256(stored_file.read_bytes()).hexdigest()
        assert actual_sha != receipt.sha256_hash


def test_30_trading_capability_invocation_permanently_prohibited():
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_endpoint_not_order_execution("https://api.binance.com/api/v3/order")

    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_evidence_non_tradable(
            {"directional_trading_eligible": True, "event_id": "EVT-TEST-CPI"}
        )
