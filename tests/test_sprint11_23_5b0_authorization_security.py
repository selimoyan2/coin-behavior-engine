"""
Sprint 11.23.5B-0: Authorization Security Remediation & Offline Attack Simulation Suite
Tests and validates:
  1. Hardcoded Secret Fallback Rejection (Phase 1)
  2. Missing Signing Key Rejection (Phase 1)
  3. Modified Authorization Boolean Ineffectiveness (Phase 2)
  4. Modified Event ID Tampering Detection (Phase 2)
  5. Modified Domain Tampering Detection (Phase 2)
  6. Extended Expiration Tampering Detection (Phase 2)
  7. Increased Request Quota Tampering Detection (Phase 2)
  8. Increased Byte Quota Tampering Detection (Phase 2)
  9. Invalid Signature Rejection (Phase 2)
  10. Unknown Signing Key ID Rejection (Phase 2)
  11. Revoked Authorization Rejection (Phase 3)
  12. Expired Authorization Rejection (Phase 3)
  13. Missing Approval Record Rejection (Phase 3 & 4)
  14. Forged Approval Configuration Rejection (Phase 3)
  15. Concurrent Quota Exhaustion & No Overspending (Phase 6)
  16. Redirect to Unapproved Domain Blocked (Phase 4 & 6)
  17. Direct Transport Authorization Bypass Blocked (Phase 4)
  18. Unauthorized Trading Endpoint Permanently Blocked (Phase 5)
  19. Restart After Authorization Revocation (Durable SQLite) (Phase 3)
  20. Key Rotation and Old-Key Rejection (Phase 1 & 2)
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import time
import urllib.parse
import pytest

from coin_behavior_engine.prospective import (
    ReadOnlyResearchTransport,
    TransportResponse,
    NetworkAccessProhibitedError,
    DomainNotAllowedError,
    TradingEndpointAccessError,
    TradingIsolationViolation,
    RedirectSecurityError,
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
    RevokedKeyError,
    SignatureVerificationError,
    AuthorizationRevokedError,
    AuthorizationExpiredError,
    ApprovalRecordMissingError,
    QuotaExceededError,
    OutOfScopeError,
    NetworkActivationGateError,
)


@pytest.fixture(autouse=True)
def clean_key_registry():
    """Ensures each test starts with a clean, isolated key registry."""
    SigningKeyRegistry.reset_instance()
    yield
    SigningKeyRegistry.reset_instance()


# ==============================================================================
# PHASE 7: 20 MANDATORY OFFLINE ATTACK SIMULATIONS
# ==============================================================================

def test_01_attack_hardcoded_secret_fallback():
    """Attack 1: Verify token computation fails closed without any hardcoded secret fallback."""
    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-01",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="unregistered-key-id",
    )
    # Registry has no keys; no secret fallback permitted
    with pytest.raises(UnknownKeyIdError):
        token.compute_canonical_digest()


def test_02_attack_missing_signing_key():
    """Attack 2: Attempting to sign or verify with empty or missing key fails closed."""
    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-02",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="missing-key",
    )
    with pytest.raises(UnknownKeyIdError):
        token.compute_canonical_digest(key_registry=SigningKeyRegistry.get_instance())

    assert token.verify_signature() is False


def test_03_attack_modified_authorization_boolean():
    """Attack 3: Setting is_authorized=True on untrusted token cannot grant external authorization."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-03", b"super_secret_test_key_bytes_03", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-03",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="UntrustedUser",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-03",
        is_authorized=True,  # Attacker attempts to bypass approval by setting is_authorized=True
    )
    token.signature_digest = token.compute_canonical_digest()

    # Trusted approval store has NO record for this token
    store = TrustedApprovalStore()
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    allowed, reason = gate.evaluate_request(
        token=token,
        target_url="https://bls.gov/news",
        target_event_id="EVT-BLS-CPI",
    )
    assert allowed is False
    assert "MISSING_APPROVAL_RECORD" in reason


def test_04_attack_modified_event_id():
    """Attack 4: Tampering with authorized_event_id invalidates cryptographic signature."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-04", b"super_secret_test_key_bytes_04", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-04",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-04",
    )
    token.signature_digest = token.compute_canonical_digest()
    assert token.verify_signature() is True

    # Tampering: attacker changes event_id to FOMC
    token.authorized_event_id = "EVT-FED-FOMC"
    assert token.verify_signature() is False


def test_05_attack_modified_domain():
    """Attack 5: Tampering with approved_domains invalidates cryptographic signature."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-05", b"super_secret_test_key_bytes_05", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-05",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-05",
    )
    token.signature_digest = token.compute_canonical_digest()

    # Tampering: attacker adds unauthorized domain
    token.approved_domains.append("malicious-target.com")
    assert token.verify_signature() is False


def test_06_attack_extended_expiration():
    """Attack 6: Tampering with expires_at_utc invalidates cryptographic signature."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-06", b"super_secret_test_key_bytes_06", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-06",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-06",
    )
    token.signature_digest = token.compute_canonical_digest()

    # Tampering: attacker extends expiration by 30 days
    token.expires_at_utc = (now + timedelta(days=30)).isoformat()
    assert token.verify_signature() is False


def test_07_attack_increased_request_quota():
    """Attack 7: Tampering with max_request_count invalidates cryptographic signature."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-07", b"super_secret_test_key_bytes_07", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-07",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=5,
        max_byte_allowance=1048576,
        key_id="test-key-07",
    )
    token.signature_digest = token.compute_canonical_digest()

    # Tampering: attacker increases request count to 500
    token.max_request_count = 500
    assert token.verify_signature() is False


def test_08_attack_increased_byte_quota():
    """Attack 8: Tampering with max_byte_allowance invalidates cryptographic signature."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-08", b"super_secret_test_key_bytes_08", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-08",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1024,
        key_id="test-key-08",
    )
    token.signature_digest = token.compute_canonical_digest()

    # Tampering: attacker increases allowance to 100 MB
    token.max_byte_allowance = 104857600
    assert token.verify_signature() is False


def test_09_attack_invalid_signature():
    """Attack 9: Corrupted or forged signature digests are rejected via constant-time comparison."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-09", b"super_secret_test_key_bytes_09", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-09",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-09",
        signature_digest="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    assert token.verify_signature() is False


def test_10_attack_unknown_signing_key_id():
    """Attack 10: Tokens referencing unknown or unregistered key IDs fail verification closed."""
    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-10",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="forged-or-unknown-key-id",
        signature_digest="abcdef0123456789",
    )
    assert token.verify_signature() is False


def test_11_attack_revoked_authorization():
    """Attack 11: Tokens revoked in the trusted store are denied immediately."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-11", b"super_secret_test_key_bytes_11", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-11",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-11",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()
    store.create_privileged_approval(token, privileged_operator="SecurityLead", is_production=False)

    # Revoke authorization
    store.revoke_approval(token.token_id, revoked_by="SecurityLead", reason="Compromised credentials")

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
    assert allowed is False
    assert "REVOKED" in reason


def test_12_attack_expired_authorization():
    """Attack 12: Tokens whose expiration has elapsed are rejected as EXPIRED."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-12", b"super_secret_test_key_bytes_12", is_test_key=True)

    past = datetime.now(timezone.utc) - timedelta(hours=2)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-12",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=(past - timedelta(hours=1)).isoformat(),
        not_before_utc=(past - timedelta(hours=1)).isoformat(),
        expires_at_utc=past.isoformat(),  # Already expired
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-12",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()
    store.create_privileged_approval(token, privileged_operator="SecurityLead", is_production=False)

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
    assert allowed is False
    assert "EXPIRED" in reason


def test_13_attack_missing_approval_record():
    """Attack 13: Cryptographically valid token without a trusted approval record is denied."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-13", b"super_secret_test_key_bytes_13", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-13",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-13",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()  # Empty store
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
    assert allowed is False
    assert "MISSING_APPROVAL_RECORD" in reason


def test_14_attack_forged_approval_configuration():
    """Attack 14: Untrusted callers cannot create production approval records."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-14", b"super_secret_test_key_bytes_14", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-14",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-14",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()
    # Attempting to create production approval fails closed
    with pytest.raises(AuthorizationError) as exc_info:
        store.create_privileged_approval(token, privileged_operator="Lead", is_production=True)
    assert "GOVERNANCE VIOLATION" in str(exc_info.value)


def test_15_attack_concurrent_quota_exhaustion():
    """Attack 15: Concurrent workers cannot overspend request quota under race conditions."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-15", b"super_secret_test_key_bytes_15", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-15",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="ConcurrentTester",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=3,  # Strict quota of 3
        max_byte_allowance=1048576,
        key_id="test-key-15",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()
    store.create_privileged_approval(token, privileged_operator="Lead", is_production=False)
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    results = []
    def attempt_request(worker_id: int):
        allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
        return allowed, reason

    # 10 concurrent requests competing for 3 quota slots
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_request, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r[0] is True]
    denials = [r for r in results if r[0] is False]

    # Exactly 3 allowed, exactly 7 denied
    assert len(successes) == 3
    assert len(denials) == 7
    for d in denials:
        assert "QUOTA" in d[1] or "EXHAUSTED" in d[1]


def test_16_attack_redirect_to_unapproved_domain():
    """Attack 16: Redirect target to an unapproved domain is blocked by domain security."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-16", b"super_secret_test_key_bytes_16", is_test_key=True)

    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=True)
    transport.register_mock_response(
        "https://bls.gov/redirect",
        status_code=301,
        headers={"location": "https://evil-unapproved.com/exfiltrate"},
    )

    # When following redirect to unapproved domain, DomainNotAllowedError must be raised
    with pytest.raises(DomainNotAllowedError):
        transport.execute_request("GET", "https://bls.gov/redirect")


def test_17_attack_direct_transport_authorization_bypass():
    """Attack 17: Direct call to transport.execute_request with network_enabled=True is blocked by gate."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-17", b"super_secret_test_key_bytes_17", is_test_key=True)

    transport = ReadOnlyResearchTransport(network_enabled=True)
    # Gate is default disabled (fail-closed); direct call must raise NetworkActivationGateError
    with pytest.raises(NetworkActivationGateError) as exc_info:
        transport.execute_request("GET", "https://bls.gov/news")
    assert "GATE_DISABLED" in str(exc_info.value)


def test_18_attack_unauthorized_trading_endpoint():
    """Attack 18: Trading endpoint access is permanently blocked even with valid observation tokens."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-18", b"super_secret_test_key_bytes_18", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-18",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BINANCE-MARKET",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["api.binance.com"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-18",
    )
    token.signature_digest = token.compute_canonical_digest()

    store = TrustedApprovalStore()
    store.create_privileged_approval(token, privileged_operator="Lead", is_production=False)
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    # Attempting order endpoint raises TradingIsolationViolation
    with pytest.raises(TradingIsolationViolation):
        gate.evaluate_request(token, "https://api.binance.com/api/v3/order", "EVT-BINANCE-MARKET")


def test_19_attack_restart_after_revocation():
    """Attack 19: Durable SQLite store retains revoked state across store re-instantiations."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-19", b"super_secret_test_key_bytes_19", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-19",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="test-key-19",
    )
    token.signature_digest = token.compute_canonical_digest()

    with tempfile.TemporaryDirectory() as td:
        db_file = Path(td) / "durable_approvals.sqlite"
        store1 = TrustedApprovalStore(db_path=db_file)
        store1.create_privileged_approval(token, privileged_operator="Lead", is_production=False)
        store1.revoke_approval(token.token_id, revoked_by="Lead", reason="Key compromised")

        # Reopen store from disk in separate instance (simulating system restart)
        store2 = TrustedApprovalStore(db_path=db_file)
        reloaded = store2.get_approval(token.token_id)
        assert reloaded is not None
        assert reloaded.status == "REVOKED"

        gate2 = NetworkActivationGate(approval_store=store2, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
        allowed, reason = gate2.evaluate_request(token, "https://bls.gov/news", "EVT-BLS-CPI")
        assert allowed is False
        assert "REVOKED" in reason


def test_20_attack_key_rotation_and_old_key_rejection():
    """Attack 20: Rotated or revoked keys in SigningKeyRegistry immediately reject previously valid tokens."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("old-key-v1", b"old_signing_key_bytes_v1_secure", is_test_key=True)

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-ATTACK-20",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI",
        operator_identity="SecurityAuditor",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="old-key-v1",
    )
    token.signature_digest = token.compute_canonical_digest()
    assert token.verify_signature() is True

    # Rotate / revoke old key
    reg.revoke_key("old-key-v1", reason="Scheduled 90-day rotation")

    # Token signed with revoked key now fails verification
    assert token.verify_signature() is False
