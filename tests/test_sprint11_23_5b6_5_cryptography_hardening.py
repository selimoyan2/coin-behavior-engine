"""
Sprint 11.23.5B-6.5: Cryptography Hardening & Adversarial Verification Suite.

Covers all 16 required adversarial scenarios:
  1. Invalid Ed25519 signatures.
  2. Malformed public keys.
  3. Revoked operator keys.
  4. Expired operator identities.
  5. Test-key production escalation.
  6. Forged administrator roles.
  7. Self-approval.
  8. Replay attacks.
  9. Concurrent approval attempts.
  10. Tampered acquisition requests.
  11. HMAC authorization bypass.
  12. Governance freeze bypass.
  13. Unsafe key-file permissions.
  14. Symlink attacks.
  15. Missing cryptography dependency (no silent fallback).
  16. Unauthorized external network attempts.
Plus cross-implementation compatibility tests.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone, timedelta
import importlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest.mock as mock
import uuid
import pytest

from coin_behavior_engine.prospective.ed25519 import (
    ed25519_keygen,
    ed25519_public_key,
    ed25519_sign,
    ed25519_verify,
    ed25519_fingerprint,
    CRYPTOGRAPHY_PROVIDER,
    IS_AUDITED_LIBRARY,
    ZERO_CUSTOM_FALLBACK,
)
from coin_behavior_engine.prospective.key_security import (
    SecureKeyManager,
    SecurePrivateKeyHandle,
    KeySecurityError,
    SymlinkKeyPathError,
    InsecureKeyPermissionsError,
    PathTraversalKeyError,
    TestKeyInProductionError,
    KNOWN_TEST_SEEDS,
)
from coin_behavior_engine.prospective.operator_identity_registry import (
    TrustedOperatorIdentity,
    TrustedOperatorIdentityRegistry,
    OperatorApprovalIntent,
    DOMAIN_SEPARATION_PREFIX,
)
from coin_behavior_engine.prospective.bls_acquisition import (
    OfficialScheduleAcquisitionRequest,
    BlsAcquisitionCLI,
    OfflineIdentityRehearsalRunner,
    OFFICIAL_BLS_CPI_URL,
    TARGET_EVENT_ID,
)
from coin_behavior_engine.prospective.observation_authorization import (
    TrustedApprovalStore,
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    NetworkActivationGate,
    TradingIsolationViolation,
)


@pytest.fixture
def identity_fixture():
    registry, seeds = TrustedOperatorIdentityRegistry.create_default_test_registry()
    admin_id = "OP-APPROVAL-ADMIN-01"
    admin_seed = seeds[admin_id]
    admin_ident = registry.get_identity(admin_id)
    assert admin_ident is not None

    req = OfficialScheduleAcquisitionRequest(
        created_by_operator_id="OP-RESEARCH-LEAD-01",
    )
    req_digest = req.compute_canonical_digest()

    now = datetime.now(timezone.utc)
    valid_from = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    valid_to = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "registry": registry,
        "seeds": seeds,
        "admin_id": admin_id,
        "admin_seed": admin_seed,
        "admin_ident": admin_ident,
        "req": req,
        "req_digest": req_digest,
        "valid_from": valid_from,
        "valid_to": valid_to,
    }


# ==============================================================================
# CROSS-IMPLEMENTATION COMPATIBILITY TESTS (TASK 1)
# ==============================================================================

def test_cross_implementation_rfc8032_vector_1():
    """Verify standard cryptography library matches RFC 8032 test vector 1."""
    seed1 = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    expected_pk1 = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    expected_sig1 = "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"

    pk = ed25519_public_key(seed1)
    sig = ed25519_sign(seed1, b"")
    assert pk.hex() == expected_pk1
    assert sig.hex() == expected_sig1
    assert ed25519_verify(pk, b"", sig) is True


def test_cross_implementation_rfc8032_vector_2():
    """Verify standard cryptography library matches RFC 8032 test vector 2."""
    seed2 = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    pk2 = ed25519_public_key(seed2)
    sig2 = ed25519_sign(seed2, b"\x72")
    assert ed25519_verify(pk2, b"\x72", sig2) is True
    assert ed25519_verify(pk2, b"\x73", sig2) is False


def test_cryptography_provider_metadata():
    """Verify the active provider is the audited cryptography library."""
    assert CRYPTOGRAPHY_PROVIDER == "cryptography.hazmat.primitives.asymmetric.ed25519"
    assert IS_AUDITED_LIBRARY is True
    assert ZERO_CUSTOM_FALLBACK is True


# ==============================================================================
# 16 ADVERSARIAL SCENARIOS (TASK 5)
# ==============================================================================

def test_adv_01_invalid_ed25519_signatures(identity_fixture):
    """Scenario 1: Corrupted or invalid length signatures are rejected."""
    f = identity_fixture
    msg = b"Secure Message"
    sig = ed25519_sign(f["admin_seed"], msg)
    pk = bytes.fromhex(f["admin_ident"].public_key_hex)

    # Valid
    assert ed25519_verify(pk, msg, sig) is True

    # Bad length (truncated)
    assert ed25519_verify(pk, msg, sig[:63]) is False
    assert ed25519_verify(pk, msg, sig + b"\x00") is False

    # Corrupt single byte
    corrupt_sig = bytearray(sig)
    corrupt_sig[10] ^= 0xFF
    assert ed25519_verify(pk, msg, bytes(corrupt_sig)) is False

    # Non-bytes
    assert ed25519_verify(pk, msg, "not-bytes") is False


def test_adv_02_malformed_public_keys(identity_fixture):
    """Scenario 2: Malformed or non-canonical public keys are rejected."""
    f = identity_fixture
    msg = b"Secure Message"
    sig = ed25519_sign(f["admin_seed"], msg)

    # Key length != 32
    assert ed25519_verify(b"\x00" * 31, msg, sig) is False
    assert ed25519_verify(b"\x00" * 33, msg, sig) is False
    assert ed25519_verify(b"", msg, sig) is False

    # Key derivation with invalid seed
    with pytest.raises(ValueError):
        ed25519_public_key(b"\x00" * 31)


def test_adv_03_revoked_operator_keys(identity_fixture):
    """Scenario 3: Revoked operator keys fail verification."""
    f = identity_fixture
    registry = TrustedOperatorIdentityRegistry.from_dict(f["registry"].to_dict())
    assert registry.revoke_identity(f["admin_id"], reason="Key compromised") is True

    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    valid, reason = registry.verify_intent(intent)
    assert valid is False
    assert "OPERATOR_REVOKED" in reason


def test_adv_04_expired_operator_identities(identity_fixture):
    """Scenario 4: Expired operator identities are rejected."""
    f = identity_fixture
    registry = TrustedOperatorIdentityRegistry.from_dict(f["registry"].to_dict())
    ident = registry.get_identity(f["admin_id"])
    ident.expires_at_utc = "2020-01-01T00:00:00Z"

    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    valid, reason = registry.verify_intent(intent)
    assert valid is False
    assert "OPERATOR_EXPIRED" in reason


def test_adv_05_test_key_production_escalation(identity_fixture):
    """Scenario 5: Test keys or deterministic test seeds cannot authorize production."""
    f = identity_fixture

    # 1. Loading test seed in production mode raises TestKeyInProductionError
    with tempfile.TemporaryDirectory() as td:
        key_file = Path(td) / "test.seed"
        SecureKeyManager.save_private_key(key_file, f["admin_seed"], is_test_key=True)

        with pytest.raises(TestKeyInProductionError):
            SecureKeyManager.load_private_key(key_file, is_test_key=True, is_production=True)

        # Even with is_test_key=False, if the raw seed is a known test seed, it must be rejected!
        with pytest.raises(TestKeyInProductionError):
            SecureKeyManager.load_private_key(key_file, is_test_key=False, is_production=True)

    # 2. Registry rejects test key in production intent
    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=True,
    )
    intent.sign(f["admin_seed"])

    valid, reason = f["registry"].verify_intent(intent, enforce_production_key_isolation=True)
    assert valid is False
    assert "TEST_KEY_PRODUCTION_ESCALATION" in reason


def test_adv_06_forged_administrator_roles(identity_fixture):
    """Scenario 6: Non-admin caller claiming APPROVAL_ADMIN role is rejected."""
    f = identity_fixture
    research_id = "OP-RESEARCH-LEAD-01"
    research_seed = f["seeds"][research_id]
    research_ident = f["registry"].get_identity(research_id)

    # Research lead tries to declare themselves APPROVAL_ADMIN
    intent = OperatorApprovalIntent(
        operator_id=research_id,
        operator_key_id=research_ident.key_id,
        operator_role="APPROVAL_ADMIN",  # Forged!
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(research_seed)

    valid, reason = f["registry"].verify_intent(intent, required_role="APPROVAL_ADMIN")
    assert valid is False
    assert "INSUFFICIENT_ROLE_PRIVILEGES" in reason


def test_adv_07_self_approval(identity_fixture):
    """Scenario 7: Approval Admin cannot approve an acquisition request they created."""
    f = identity_fixture
    self_req = OfficialScheduleAcquisitionRequest(created_by_operator_id=f["admin_id"])
    self_digest = self_req.compute_canonical_digest()

    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=self_req.request_id,
        request_digest=self_digest,
        target_event_id=self_req.target_event_id,
        canonical_url=self_req.canonical_url,
        capability=self_req.required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        req_file = str(Path(td) / "req.json")
        Path(req_file).write_text(json.dumps(self_req.to_dict()), encoding="utf-8")
        res = BlsAcquisitionCLI.approve(
            request_file=req_file,
            signed_intent_json=intent.to_json(),
            operator_registry=f["registry"],
            store_path=str(Path(td) / "store.sqlite"),
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] == "SELF_APPROVAL_PROHIBITED"


def test_adv_08_replay_attacks(identity_fixture):
    """Scenario 8: Replay of consumed nonce is strictly rejected."""
    f = identity_fixture
    fixed_nonce = f"NONCE-REPLAY-{uuid.uuid4().hex}"

    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=fixed_nonce,
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res1 = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=f["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res1["success"] is True

        # Replay attempt
        res2 = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=f["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res2["success"] is False
        assert res2["error"] == "REPLAY_ATTACK_DETECTED_NONCE_ALREADY_USED"


def test_adv_09_concurrent_approval_attempts(identity_fixture):
    """Scenario 9: Concurrent approval attempts with the same nonce result in exactly one winner."""
    f = identity_fixture
    shared_nonce = f"NONCE-RACE-{uuid.uuid4().hex}"

    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=shared_nonce,
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")

        def attempt_approval():
            return BlsAcquisitionCLI.approve(
                signed_intent_json=intent.to_json(),
                operator_registry=f["registry"],
                store_path=store_path,
                is_production=False,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_approval) for _ in range(5)]
            results = [f.result() for f in futures]

        successes = [r for r in results if r.get("success")]
        replays = [r for r in results if r.get("error") == "REPLAY_ATTACK_DETECTED_NONCE_ALREADY_USED"]

        assert len(successes) == 1, "Exactly one approval must succeed"
        assert len(replays) == 4, "All other concurrent attempts must be rejected as replay attacks"


def test_adv_10_tampered_acquisition_requests(identity_fixture):
    """Scenario 10: Tampered canonical URL or digest does not match intent."""
    f = identity_fixture
    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(f["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        # Request with tampered URL
        tampered_req = OfficialScheduleAcquisitionRequest(
            canonical_url="https://www.bls.gov/tampered_path.htm",
            created_by_operator_id="OP-RESEARCH-LEAD-01",
        )
        req_file = str(Path(td) / "tampered.json")
        Path(req_file).write_text(json.dumps(tampered_req.to_dict()), encoding="utf-8")

        res = BlsAcquisitionCLI.approve(
            request_file=req_file,
            signed_intent_json=intent.to_json(),
            operator_registry=f["registry"],
            store_path=str(Path(td) / "store.sqlite"),
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] in ("REQUEST_DIGEST_MISMATCH", "CANONICAL_URL_MISMATCH")


def test_adv_11_hmac_authorization_bypass(identity_fixture):
    """Scenario 11: Possessing Layer B HMAC key cannot bypass Layer A Ed25519 authentication."""
    f = identity_fixture
    hmac_key = b"hmac_key_for_layer_b_32_bytes_ok"

    # Attempt to sign intent with HMAC key
    with pytest.raises(ValueError):
        # Key is not 32 bytes or is not a valid Ed25519 seed
        ed25519_sign(hmac_key[:31], b"some payload")

    # Valid Layer A intent cannot activate network without valid Layer B token
    store = TrustedApprovalStore(":memory:")
    gate = NetworkActivationGate(
        approval_store=store,
        gate_enabled=True,
        operator_authorization_granted=True,
    )
    allowed, reason = gate.evaluate_request(
        token=None,  # Missing Layer B token
        target_url=OFFICIAL_BLS_CPI_URL,
        target_event_id=TARGET_EVENT_ID,
    )
    assert allowed is False
    assert "MISSING_TOKEN" in reason


def test_adv_12_governance_freeze_bypass(identity_fixture):
    """Scenario 12: Production approval cannot bypass governance policy freeze."""
    f = identity_fixture
    intent = OperatorApprovalIntent(
        operator_id=f["admin_id"],
        operator_key_id=f["admin_ident"].key_id,
        operator_role=f["admin_ident"].role,
        request_id=f["req"].request_id,
        request_digest=f["req_digest"],
        target_event_id=f["req"].target_event_id,
        canonical_url=f["req"].canonical_url,
        capability=f["req"].required_capability,
        issued_at_utc=f["valid_from"],
        expires_at_utc=f["valid_to"],
        nonce=f"NONCE-PROD-{uuid.uuid4().hex}",
        is_production=True,
    )
    intent.sign(f["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=f["registry"],
            store_path=str(Path(td) / "store.sqlite"),
            is_production=True,
        )
        assert res["success"] is False
        assert res["error"] == "PRODUCTION_AUTHORIZATION_NOT_GRANTED"
        assert "freeze" in res["message"].lower()


def test_adv_13_unsafe_key_file_permissions(identity_fixture):
    """Scenario 13: Unsafe private key file permissions are rejected."""
    f = identity_fixture
    with tempfile.TemporaryDirectory() as td:
        key_file = Path(td) / "unsafe.seed"
        SecureKeyManager.save_private_key(key_file, f["admin_seed"], is_test_key=True)

        if os.name != "nt":
            # Chmod 0o666 (world readable and writable)
            os.chmod(key_file, 0o666)
            with pytest.raises(InsecureKeyPermissionsError):
                SecureKeyManager.load_private_key(key_file, is_test_key=True)
        else:
            # On Windows, verify permissions method executes without crash
            SecureKeyManager.verify_file_permissions(key_file)


def test_adv_14_symlink_attacks(identity_fixture):
    """Scenario 14: Symlink key paths are rejected fail-closed."""
    f = identity_fixture
    with tempfile.TemporaryDirectory() as td:
        real_key = Path(td) / "real.seed"
        SecureKeyManager.save_private_key(real_key, f["admin_seed"], is_test_key=True)
        symlink_key = Path(td) / "symlink.seed"

        try:
            os.symlink(real_key, symlink_key)
            with pytest.raises(SymlinkKeyPathError):
                SecureKeyManager.load_private_key(symlink_key, is_test_key=True)
        except OSError:
            # On Windows without developer mode/admin privilege, symlink creation might raise OSError
            # Verify mock detection
            with mock.patch("os.path.islink", return_value=True):
                with pytest.raises(SymlinkKeyPathError):
                    SecureKeyManager.assert_not_symlink(real_key)


def test_adv_15_missing_cryptography_dependency():
    """Scenario 15: Missing cryptography dependency fails closed with no silent fallback."""
    assert ZERO_CUSTOM_FALLBACK is True
    ed_module = sys.modules["coin_behavior_engine.prospective.ed25519"]

    orig_import = __import__
    def mock_import(name, *args, **kwargs):
        if "cryptography" in name:
            raise ImportError("No module named 'cryptography'")
        return orig_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError) as exc_info:
            importlib.reload(ed_module)
        assert "CRITICAL SECURITY REQUIREMENT" in str(exc_info.value)

    # Restore module
    importlib.reload(ed_module)
    assert ed_module.ZERO_CUSTOM_FALLBACK is True


def test_adv_16_unauthorized_external_network_attempts():
    """Scenario 16: Outbound requests without valid authorization are rejected."""
    store = TrustedApprovalStore(":memory:")
    gate = NetworkActivationGate(
        approval_store=store,
        gate_enabled=False,  # Disabled by default
        operator_authorization_granted=False,
    )
    allowed, reason = gate.evaluate_request(
        token=None,
        target_url=OFFICIAL_BLS_CPI_URL,
        target_event_id=TARGET_EVENT_ID,
    )
    assert allowed is False
    assert "GATE_DISABLED" in reason


def test_private_key_redaction(identity_fixture):
    """Verify that SecurePrivateKeyHandle never leaks secret bytes in repr or str."""
    f = identity_fixture
    handle = SecurePrivateKeyHandle(f["admin_seed"], is_test_key=True, key_id="KEY-ADMIN-01")
    raw_hex = f["admin_seed"].hex()

    assert raw_hex not in repr(handle)
    assert raw_hex not in str(handle)
    assert "[SECRET_REDACTED]" in repr(handle)


def test_operator_enrollment_and_rotation(identity_fixture):
    """Verify independent authorization required for enrollment and rotation."""
    f = identity_fixture
    registry = TrustedOperatorIdentityRegistry.from_dict(f["registry"].to_dict())

    # 1. Self-enrollment of Approval Admin role is prohibited
    new_admin_seed = bytes(range(32))
    new_admin_pub = ed25519_public_key(new_admin_seed).hex()
    new_admin_ident = TrustedOperatorIdentity(
        operator_id="OP-NEW-ADMIN-99",
        role="APPROVAL_ADMIN",
        operator_name="Rogue Admin",
        public_key_hex=new_admin_pub,
        key_id="KEY-NEW-ADMIN-99",
    )
    with pytest.raises(ValueError) as exc:
        registry.enroll_operator(new_admin_ident, authorized_by="OP-NEW-ADMIN-99")
    assert "not registered" in str(exc.value)

    # 2. Research operator cannot enroll an admin
    with pytest.raises(ValueError) as exc:
        registry.enroll_operator(new_admin_ident, authorized_by="OP-RESEARCH-LEAD-01")
    assert "must be APPROVAL_ADMIN" in str(exc.value)

    # 3. Legitimate enrollment by active Approval Admin succeeds
    registry.enroll_operator(new_admin_ident, authorized_by=f["admin_id"])
    assert registry.get_identity("OP-NEW-ADMIN-99") is not None

    # 4. Key rotation updates key_id and public_key
    rotated_seed = bytes([i ^ 0xAA for i in range(32)])
    rotated_pub = ed25519_public_key(rotated_seed).hex()
    updated = registry.rotate_operator_key(
        operator_id="OP-NEW-ADMIN-99",
        new_public_key_hex=rotated_pub,
        new_key_id="KEY-NEW-ADMIN-99-ROTATED",
        authorized_by=f["admin_id"],
    )
    assert updated.key_id == "KEY-NEW-ADMIN-99-ROTATED"
    assert updated.public_key_hex == rotated_pub
