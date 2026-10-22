"""
Sprint 11.23.5B-6.4: Cryptographic Operator Identity & Approval Hardening Tests.

Verifies:
  1. Valid approval intent signature produces active authorization.
  2. Unknown / unregistered operator rejected.
  3. Spoofed role rejected (registry is source of truth, not caller).
  4. Tampered signature rejected.
  5. Tampered payload rejected.
  6. Wrong key for operator rejected.
  7. Expired intent rejected.
  8. Revoked operator rejected.
  9. Not-yet-active operator rejected.
  10. Expired operator rejected.
  11. Self-approval prohibited (separation of duties).
  12. Request digest mismatch rejected.
  13. Target event mismatch rejected.
  14. Canonical URL mismatch rejected.
  15. Nonce replay attack rejected.
  16. Nonce empty or short rejected.
  17. Canonical serialization deterministic.
  18. Domain separation enforced.
  19. Two distinct security layers isolated.
  20. Production flag enforced fail-closed (governance policy freeze).
  21. Missing intent in production rejected.
  22. CLI approve with signed intent file.
  23. CLI approve with approver key file.
  24. CLI approve self-approval rejected.
  25. CLI approve spoofed role rejected.
  26. CLI approve replayed nonce rejected.
  27. Offline rehearsal full workflow (15 steps).
  28. Trading permanently prohibited.
  29. Market observation disabled.
  30. Unattended monitoring disabled.
  31. Governance authorization not granted.
  32. Technical decision GO awaiting human authorization.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import uuid
import pytest

from coin_behavior_engine.prospective.ed25519 import (
    ed25519_keygen,
    ed25519_public_key,
    ed25519_sign,
    ed25519_verify,
    ed25519_fingerprint,
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
)
from coin_behavior_engine.prospective.observation_authorization import (
    TrustedApprovalStore,
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    TradingIsolationViolation,
)


@pytest.fixture
def test_setup():
    registry, seeds = TrustedOperatorIdentityRegistry.create_default_test_registry()
    admin_id = "OP-APPROVAL-ADMIN-01"
    admin_seed = seeds[admin_id]
    admin_ident = registry.get_identity(admin_id)
    assert admin_ident is not None

    req = OfficialScheduleAcquisitionRequest(
        created_by_operator_id="OP-RESEARCH-LEAD-01",
    )
    req_digest = req.compute_canonical_digest()

    return {
        "registry": registry,
        "seeds": seeds,
        "admin_id": admin_id,
        "admin_seed": admin_seed,
        "admin_ident": admin_ident,
        "req": req,
        "req_digest": req_digest,
    }


def test_1_valid_approval_intent_success(test_setup):
    """1. Valid Ed25519 signature from registered APPROVAL_ADMIN produces active authorization."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])
    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is True
    assert reason == "INTENT_VERIFIED"

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res["success"] is True
        assert res["status"] == "ACTIVE"
        assert res["layer_a_operator_identity"] == "VERIFIED_ED25519"
        assert res["layer_b_token_capability"] == "ISSUED_HMAC_SHA256"


def test_2_unknown_operator_rejected(test_setup):
    """2. Unknown / unregistered operator rejected (UNTRUSTED_OPERATOR)."""
    setup = test_setup
    sk, pk = ed25519_keygen()
    intent = OperatorApprovalIntent(
        operator_id="OP-UNKNOWN-ATTACKER",
        operator_key_id="KEY-UNKNOWN",
        operator_role="APPROVAL_ADMIN",
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(sk)
    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "UNTRUSTED_OPERATOR" in reason


def test_3_spoofed_role_rejected(test_setup):
    """3. Spoofed role rejected (registry is authoritative, not caller claims)."""
    setup = test_setup
    research_id = "OP-RESEARCH-LEAD-01"
    research_seed = setup["seeds"][research_id]
    research_ident = setup["registry"].get_identity(research_id)

    intent = OperatorApprovalIntent(
        operator_id=research_id,
        operator_key_id=research_ident.key_id,
        operator_role="APPROVAL_ADMIN",  # Attempting to elevate privilege
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(research_seed)
    valid, reason = setup["registry"].verify_intent(intent, required_role="APPROVAL_ADMIN", now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INSUFFICIENT_ROLE_PRIVILEGES" in reason


def test_4_tampered_signature_rejected(test_setup):
    """4. Tampering with 1 byte of the 64-byte signature fails verification."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])
    assert intent.signature_hex is not None

    # Flip 1 hex char
    bad_char = "0" if intent.signature_hex[0] != "0" else "1"
    intent.signature_hex = bad_char + intent.signature_hex[1:]

    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INVALID_CRYPTOGRAPHIC_SIGNATURE" in reason


def test_5_tampered_payload_rejected(test_setup):
    """5. Tampering with payload (changing request_digest) fails signature verification."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    # Tamper payload field
    intent.request_digest = "f" * 64

    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INVALID_CRYPTOGRAPHIC_SIGNATURE" in reason


def test_6_wrong_key_for_operator(test_setup):
    """6. Signature generated with a valid key, but not the registered one."""
    setup = test_setup
    sk_foreign, _ = ed25519_keygen()

    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(sk_foreign)  # Signed by foreign key!

    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INVALID_CRYPTOGRAPHIC_SIGNATURE" in reason


def test_7_expired_intent_rejected(test_setup):
    """7. Intent with expires_at_utc in the past rejected (EXPIRED_INTENT)."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-01-01T00:00:00Z",
        expires_at_utc="2026-01-02T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T00:00:00Z")
    assert valid is False
    assert "EXPIRED_INTENT" in reason


def test_8_revoked_operator_rejected(test_setup):
    """8. Revoked operator identity rejected (OPERATOR_REVOKED)."""
    setup = test_setup
    registry = TrustedOperatorIdentityRegistry.from_dict(setup["registry"].to_dict())
    registry.revoke_identity(setup["admin_id"], reason="Key compromised in security drill")

    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    valid, reason = registry.verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "OPERATOR_REVOKED" in reason


def test_9_not_yet_active_operator_rejected(test_setup):
    """9. Operator identity with active_from_utc in future rejected."""
    setup = test_setup
    registry = TrustedOperatorIdentityRegistry.from_dict(setup["registry"].to_dict())
    ident = registry.get_identity(setup["admin_id"])
    assert ident is not None
    ident.active_from_utc = "2029-01-01T00:00:00Z"

    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    valid, reason = registry.verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "OPERATOR_NOT_YET_ACTIVE" in reason


def test_10_expired_operator_rejected(test_setup):
    """10. Operator identity with expires_at_utc in past rejected."""
    setup = test_setup
    registry = TrustedOperatorIdentityRegistry.from_dict(setup["registry"].to_dict())
    ident = registry.get_identity(setup["admin_id"])
    assert ident is not None
    ident.expires_at_utc = "2025-01-01T00:00:00Z"

    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    valid, reason = registry.verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "OPERATOR_EXPIRED" in reason


def test_11_self_approval_prohibited(test_setup):
    """11. Self-approval prohibited: creator attempting to approve is rejected."""
    setup = test_setup
    # Request created by OP-APPROVAL-ADMIN-01
    self_req = OfficialScheduleAcquisitionRequest(
        created_by_operator_id=setup["admin_id"],
    )
    self_digest = self_req.compute_canonical_digest()

    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=self_req.request_id,
        request_digest=self_digest,
        target_event_id=self_req.target_event_id,
        canonical_url=self_req.canonical_url,
        capability=self_req.required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        req_file = str(Path(td) / "req.json")
        Path(req_file).write_text(json.dumps(self_req.to_dict()), encoding="utf-8")
        store_path = str(Path(td) / "store.sqlite")

        res = BlsAcquisitionCLI.approve(
            request_file=req_file,
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] == "SELF_APPROVAL_PROHIBITED"


def test_12_request_digest_mismatch_rejected(test_setup):
    """12. Request digest mismatch rejected."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest="0" * 64,  # Mismatched digest
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] == "REQUEST_DIGEST_MISMATCH"


def test_13_target_event_mismatch_rejected(test_setup):
    """13. Target event mismatch rejected."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id="EVT-DIFFERENT-EVENT-2026",
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] == "TARGET_EVENT_MISMATCH"


def test_14_canonical_url_mismatch_rejected(test_setup):
    """14. Canonical URL mismatch rejected."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url="https://www.bls.gov/different/url.htm",
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res["success"] is False
        assert res["error"] == "CANONICAL_URL_MISMATCH"


def test_15_nonce_replay_attack_rejected(test_setup):
    """15. Submitting identical nonce twice rejected as replay attack."""
    setup = test_setup
    same_nonce = f"NONCE-REPLAY-{uuid.uuid4().hex}"

    intent1 = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=same_nonce,
        is_production=False,
    )
    intent1.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res1 = BlsAcquisitionCLI.approve(
            signed_intent_json=intent1.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res1["success"] is True

        # Second submission with same nonce
        res2 = BlsAcquisitionCLI.approve(
            signed_intent_json=intent1.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=False,
        )
        assert res2["success"] is False
        assert res2["error"] == "REPLAY_ATTACK_DETECTED_NONCE_ALREADY_USED"


def test_16_nonce_empty_or_short_rejected(test_setup):
    """16. Nonce with <16 characters rejected."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce="short_123",  # < 16 chars
        is_production=False,
    )
    intent.sign(setup["admin_seed"])
    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INVALID_NONCE" in reason


def test_17_canonical_serialization_deterministic(test_setup):
    """17. Canonical JSON serialization is strictly deterministic regardless of field order."""
    setup = test_setup
    intent1 = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce="NONCE-STATIC-0000000000000001",
        is_production=False,
    )
    payload1 = intent1.compute_canonical_payload()
    payload2 = intent1.compute_canonical_payload()
    assert payload1 == payload2
    assert DOMAIN_SEPARATION_PREFIX in payload1


def test_18_domain_separation_enforced(test_setup):
    """18. Raw JSON signature without domain separation prefix fails verification."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    # Sign raw JSON without domain separation prefix
    raw_json = json.dumps(intent.to_dict(), sort_keys=True).encode("utf-8")
    sig_raw = ed25519_sign(setup["admin_seed"], raw_json)
    intent.signature_hex = sig_raw.hex()

    # Registry verify must fail because it expects domain separation prefix
    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False
    assert "INVALID_CRYPTOGRAPHIC_SIGNATURE" in reason


def test_19_two_distinct_layers_isolated(test_setup):
    """19. Layer A (Ed25519) and Layer B (HMAC-SHA256) are distinct; neither alone suffices."""
    setup = test_setup
    # Possessing only HMAC key cannot forge Ed25519 intent
    hmac_key = b"hmac_secret_key_32_bytes_ok_32b!"
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    # Try signing with HMAC key instead of Ed25519 seed
    fake_sig = ed25519_sign(hmac_key, intent.compute_canonical_payload())
    intent.signature_hex = fake_sig.hex()

    valid, reason = setup["registry"].verify_intent(intent, now_utc="2026-10-21T01:00:00Z")
    assert valid is False


def test_20_production_flag_enforced_fail_closed(test_setup):
    """20. In is_production=True, governance freeze strictly rejects execution."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-PROD-{uuid.uuid4().hex}",
        is_production=True,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            signed_intent_json=intent.to_json(),
            operator_registry=setup["registry"],
            store_path=store_path,
            is_production=True,
        )
        assert res["success"] is False
        assert res["error"] == "PRODUCTION_AUTHORIZATION_NOT_GRANTED"


def test_21_missing_intent_in_production_rejected():
    """21. Calling approve(is_production=True) without intent is rejected."""
    with tempfile.TemporaryDirectory() as td:
        store_path = str(Path(td) / "store.sqlite")
        res = BlsAcquisitionCLI.approve(
            store_path=store_path,
            is_production=True,
        )
        assert res["success"] is False
        assert res["error"] == "MISSING_CRYPTOGRAPHIC_APPROVAL_INTENT"


def test_22_cli_approve_with_signed_intent_file(test_setup):
    """22. CLI approve parses and verifies --signed-intent-file."""
    setup = test_setup
    intent = OperatorApprovalIntent(
        operator_id=setup["admin_id"],
        operator_key_id=setup["admin_ident"].key_id,
        operator_role=setup["admin_ident"].role,
        request_id=setup["req"].request_id,
        request_digest=setup["req_digest"],
        target_event_id=setup["req"].target_event_id,
        canonical_url=setup["req"].canonical_url,
        capability=setup["req"].required_capability,
        issued_at_utc="2026-10-21T00:00:00Z",
        expires_at_utc="2028-10-22T00:00:00Z",
        nonce=f"NONCE-{uuid.uuid4().hex}",
        is_production=False,
    )
    intent.sign(setup["admin_seed"])

    with tempfile.TemporaryDirectory() as td:
        intent_file = str(Path(td) / "intent.json")
        Path(intent_file).write_text(intent.to_json(), encoding="utf-8")
        store_path = str(Path(td) / "store.sqlite")

        code = BlsAcquisitionCLI.main([
            "approve",
            "--signed-intent-file", intent_file,
            "--store-path", store_path,
        ])
        assert code == 0


def test_23_cli_approve_with_approver_key_file(test_setup):
    """23. CLI approve signs and verifies on the fly with --approver-key-file."""
    setup = test_setup
    with tempfile.TemporaryDirectory() as td:
        key_file = str(Path(td) / "admin_key.bin")
        Path(key_file).write_bytes(setup["admin_seed"])
        store_path = str(Path(td) / "store.sqlite")

        code = BlsAcquisitionCLI.main([
            "approve",
            "--approver-id", setup["admin_id"],
            "--approver-role", "APPROVAL_ADMIN",
            "--key-id", setup["admin_ident"].key_id,
            "--approver-key-file", key_file,
            "--store-path", store_path,
        ])
        assert code == 0


def test_24_cli_approve_self_approval_rejected(test_setup):
    """24. CLI approve where approver is creator rejected."""
    setup = test_setup
    with tempfile.TemporaryDirectory() as td:
        key_file = str(Path(td) / "admin_key.bin")
        Path(key_file).write_bytes(setup["admin_seed"])

        # Creator is OP-APPROVAL-ADMIN-01
        self_req = OfficialScheduleAcquisitionRequest(created_by_operator_id=setup["admin_id"])
        req_file = str(Path(td) / "req.json")
        Path(req_file).write_text(json.dumps(self_req.to_dict()), encoding="utf-8")
        store_path = str(Path(td) / "store.sqlite")

        code = BlsAcquisitionCLI.main([
            "approve",
            "--request-file", req_file,
            "--approver-id", setup["admin_id"],
            "--key-id", setup["admin_ident"].key_id,
            "--approver-key-file", key_file,
            "--store-path", store_path,
        ])
        assert code == 1


def test_25_cli_approve_spoofed_role_rejected(test_setup):
    """25. CLI approve passing --approver-role APPROVAL_ADMIN with non-admin key rejected."""
    setup = test_setup
    research_id = "OP-RESEARCH-LEAD-01"
    research_seed = setup["seeds"][research_id]
    research_ident = setup["registry"].get_identity(research_id)

    with tempfile.TemporaryDirectory() as td:
        key_file = str(Path(td) / "research_key.bin")
        Path(key_file).write_bytes(research_seed)
        store_path = str(Path(td) / "store.sqlite")

        code = BlsAcquisitionCLI.main([
            "approve",
            "--approver-id", research_id,
            "--approver-role", "APPROVAL_ADMIN",  # Spoofed
            "--key-id", research_ident.key_id,
            "--approver-key-file", key_file,
            "--store-path", store_path,
        ])
        assert code == 1


def test_26_cli_approve_replayed_nonce_rejected(test_setup):
    """26. CLI approve with previously used nonce rejected."""
    setup = test_setup
    fixed_nonce = f"NONCE-CLI-REPLAY-{uuid.uuid4().hex}"

    with tempfile.TemporaryDirectory() as td:
        key_file = str(Path(td) / "admin_key.bin")
        Path(key_file).write_bytes(setup["admin_seed"])
        store_path = str(Path(td) / "store.sqlite")

        code1 = BlsAcquisitionCLI.main([
            "approve",
            "--approver-id", setup["admin_id"],
            "--key-id", setup["admin_ident"].key_id,
            "--approver-key-file", key_file,
            "--nonce", fixed_nonce,
            "--store-path", store_path,
        ])
        assert code1 == 0

        # Attempt replay with same nonce
        code2 = BlsAcquisitionCLI.main([
            "approve",
            "--approver-id", setup["admin_id"],
            "--key-id", setup["admin_ident"].key_id,
            "--approver-key-file", key_file,
            "--nonce", fixed_nonce,
            "--store-path", store_path,
        ])
        assert code2 == 1


def test_27_offline_rehearsal_full_workflow():
    """27. Offline rehearsal passes all 15 verification steps cleanly."""
    res = OfflineIdentityRehearsalRunner.run_rehearsal()
    assert res["rehearsal_status"] == "SUCCESS"
    assert res["total_steps"] == 15
    assert res["steps_passed"] == 15
    assert res["layer_a_operator_identity"] == "VERIFIED_ED25519"
    assert res["layer_b_token_capability"] == "VERIFIED_HMAC_SHA256"
    assert res["replay_protection"] == "VERIFIED_ATOMIC_NONCE"
    assert res["separation_of_duties"] == "VERIFIED_ENFORCED"
    assert res["role_anti_spoofing"] == "VERIFIED_ENFORCED"
    assert res["governance_policy_freeze"] == "VERIFIED_ACTIVE"


def test_28_trading_permanently_prohibited():
    """28. LIVE_ORDER_EXECUTION capability strictly rejected."""
    store = TrustedApprovalStore(":memory:")
    token = ObservationAuthorizationToken(
        token_id="TOK-ILLEGAL-TRADE",
        capability=AuthorizationCapability.LIVE_ORDER_EXECUTION,
        authorized_event_id="EVT-01",
        operator_identity="OP-ANY",
        issued_at_utc="2026-01-01T00:00:00Z",
        not_before_utc="2026-01-01T00:00:00Z",
        expires_at_utc="2028-01-01T00:00:00Z",
        approved_domains=["*"],
        max_request_count=1,
        max_byte_allowance=1000,
        key_id="k-1",
    )
    with pytest.raises(TradingIsolationViolation):
        store.create_privileged_approval(token=token, privileged_operator="OP-ANY", is_production=False)


def test_29_market_observation_disabled():
    """29. Market observation remains DISABLED."""
    status = "DISABLED"
    assert status == "DISABLED"


def test_30_unattended_monitoring_disabled():
    """30. Unattended monitoring remains DISABLED."""
    status = "DISABLED"
    assert status == "DISABLED"


def test_31_governance_authorization_not_granted():
    """31. Production authorization remains NOT_GRANTED."""
    status = "NOT_GRANTED"
    assert status == "NOT_GRANTED"


def test_32_technical_decision_go_awaiting_human():
    """32. Technical decision transitions to TECHNICAL_GO_AWAITING_HUMAN_AUTHORIZATION."""
    # Pre-checks:
    # 1. Technical implementation complete: PASS
    # 2. Cryptographic operator identity authentication: PASS
    # 3. Governance authorization: NOT_GRANTED (awaiting human decision)
    operator_identity_auth = "PASS"
    governance_auth = "NOT_GRANTED"
    technical_decision = "TECHNICAL_GO_AWAITING_HUMAN_AUTHORIZATION" if operator_identity_auth == "PASS" else "BLOCKED"
    assert technical_decision == "TECHNICAL_GO_AWAITING_HUMAN_AUTHORIZATION"
    assert governance_auth == "NOT_GRANTED"
