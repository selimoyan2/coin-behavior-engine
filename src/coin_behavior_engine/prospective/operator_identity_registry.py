"""
Sprint 11.23.5B-6.4: Cryptographic Operator Identity & Approval Hardening.

Provides:
  1. Pure Ed25519-based operator identity verification.
  2. TrustedOperatorIdentity dataclass with public keys, assigned roles, and validity windows.
  3. TrustedOperatorIdentityRegistry enforcing strict role assignment (anti-self-declaration).
  4. OperatorApprovalIntent with domain separation and canonical payload serialization.
  5. Cryptographic signature generation and verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .ed25519 import (
    ed25519_keygen,
    ed25519_public_key,
    ed25519_sign,
    ed25519_verify,
    ed25519_fingerprint,
)


DOMAIN_SEPARATION_PREFIX = b"CBE-ED25519-APPROVAL-INTENT-V1:"
DEFAULT_INTENT_SCHEMA_VERSION = "v1"
DEFAULT_APPROVAL_ACTION = "BLS_ACQUISITION_APPROVAL"


@dataclass
class TrustedOperatorIdentity:
    """
    Cryptographically authenticated operator identity with trusted public key and assigned role.
    Roles are immutable and strictly enforced from the registry.
    """
    operator_id: str
    role: str
    operator_name: str
    public_key_hex: str
    key_id: str
    fingerprint: str = ""
    active_from_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    expires_at_utc: str = field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    is_revoked: bool = False
    revocation_reason: Optional[str] = None
    allowed_capabilities: List[str] = field(default_factory=lambda: ["*"])

    def __post_init__(self) -> None:
        if not self.public_key_hex or len(self.public_key_hex) != 64:
            raise ValueError(f"Invalid public key hex for operator {self.operator_id}: must be 64 hex characters (32 bytes)")
        computed_fp = ed25519_fingerprint(bytes.fromhex(self.public_key_hex))
        if not self.fingerprint:
            self.fingerprint = computed_fp
        elif self.fingerprint.lower() != computed_fp.lower():
            raise ValueError(f"Public key fingerprint mismatch for operator {self.operator_id}")

    def is_active(self, now_utc: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validates whether the operator identity is currently active, unrevoked, and within validity window.
        """
        if self.is_revoked:
            return False, f"OPERATOR_REVOKED: Identity '{self.operator_id}' revoked ({self.revocation_reason or 'No reason provided'})"

        now_dt = datetime.fromisoformat(now_utc.replace("Z", "+00:00")) if now_utc else datetime.now(timezone.utc)
        active_from_dt = datetime.fromisoformat(self.active_from_utc.replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))

        if now_dt < active_from_dt:
            return False, f"OPERATOR_NOT_YET_ACTIVE: Identity '{self.operator_id}' active from {self.active_from_utc}"
        if now_dt > expires_dt:
            return False, f"OPERATOR_EXPIRED: Identity '{self.operator_id}' expired at {self.expires_at_utc}"

        return True, "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrustedOperatorIdentity:
        return cls(
            operator_id=data["operator_id"],
            role=data["role"],
            operator_name=data["operator_name"],
            public_key_hex=data["public_key_hex"],
            key_id=data["key_id"],
            fingerprint=data.get("fingerprint", ""),
            active_from_utc=data.get("active_from_utc", ""),
            expires_at_utc=data.get("expires_at_utc", ""),
            is_revoked=data.get("is_revoked", False),
            revocation_reason=data.get("revocation_reason"),
            allowed_capabilities=data.get("allowed_capabilities", ["*"]),
        )


@dataclass
class OperatorApprovalIntent:
    """
    Digitally signed approval intent payload.
    Binds the approval action to an operator ID, key ID, request digest, target event,
    canonical URL, and single-use nonce.
    """
    operator_id: str
    operator_key_id: str
    operator_role: str
    request_id: str
    request_digest: str
    target_event_id: str
    canonical_url: str
    capability: str
    issued_at_utc: str
    expires_at_utc: str
    nonce: str
    is_production: bool = False
    action: str = DEFAULT_APPROVAL_ACTION
    schema_version: str = DEFAULT_INTENT_SCHEMA_VERSION
    signature_hex: Optional[str] = None

    def compute_canonical_payload(self) -> bytes:
        """
        Computes deterministic, canonical byte representation of the intent for signing/verification.
        Enforces domain separation prefix and sorts keys.
        Excludes signature_hex from the signed payload.
        """
        raw_dict = {
            "action": self.action,
            "capability": self.capability,
            "canonical_url": self.canonical_url,
            "expires_at_utc": self.expires_at_utc,
            "is_production": self.is_production,
            "issued_at_utc": self.issued_at_utc,
            "nonce": self.nonce,
            "operator_id": self.operator_id,
            "operator_key_id": self.operator_key_id,
            "operator_role": self.operator_role,
            "request_digest": self.request_digest,
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "target_event_id": self.target_event_id,
        }
        canonical_json = json.dumps(raw_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return DOMAIN_SEPARATION_PREFIX + canonical_json

    def compute_intent_digest(self) -> str:
        """
        Computes SHA-256 hex digest of the canonical intent payload.
        """
        return hashlib.sha256(self.compute_canonical_payload()).hexdigest()

    def sign(self, private_seed: bytes) -> str:
        """
        Signs the canonical payload using the provided 32-byte Ed25519 private seed.
        Stores and returns the 64-byte signature formatted as 128 hex characters.
        """
        payload = self.compute_canonical_payload()
        sig_bytes = ed25519_sign(private_seed, payload)
        self.signature_hex = sig_bytes.hex()
        return self.signature_hex

    def verify_cryptographic_signature(self, public_key_hex: str) -> bool:
        """
        Verifies the Ed25519 signature against the given public key hex.
        """
        if not self.signature_hex or len(self.signature_hex) != 128:
            return False
        try:
            pk_bytes = bytes.fromhex(public_key_hex)
            sig_bytes = bytes.fromhex(self.signature_hex)
            payload = self.compute_canonical_payload()
            return ed25519_verify(pk_bytes, payload, sig_bytes)
        except Exception:
            return False

    def is_expired(self, now_utc: Optional[str] = None) -> bool:
        """
        Checks whether the intent has expired.
        """
        now_dt = datetime.fromisoformat(now_utc.replace("Z", "+00:00")) if now_utc else datetime.now(timezone.utc)
        expires_dt = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
        return now_dt > expires_dt

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OperatorApprovalIntent:
        return cls(
            operator_id=data["operator_id"],
            operator_key_id=data["operator_key_id"],
            operator_role=data["operator_role"],
            request_id=data["request_id"],
            request_digest=data["request_digest"],
            target_event_id=data["target_event_id"],
            canonical_url=data["canonical_url"],
            capability=data["capability"],
            issued_at_utc=data["issued_at_utc"],
            expires_at_utc=data["expires_at_utc"],
            nonce=data["nonce"],
            is_production=data.get("is_production", False),
            action=data.get("action", DEFAULT_APPROVAL_ACTION),
            schema_version=data.get("schema_version", DEFAULT_INTENT_SCHEMA_VERSION),
            signature_hex=data.get("signature_hex"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> OperatorApprovalIntent:
        return cls.from_dict(json.loads(json_str))


class TrustedOperatorIdentityRegistry:
    """
    Registry of verified operator identities, public keys, and roles.
    Enforces that roles are strictly derived from registry configuration and cannot be
    self-declared or spoofed by callers.
    """

    def __init__(self, identities: Optional[List[TrustedOperatorIdentity]] = None) -> None:
        self._identities: Dict[str, TrustedOperatorIdentity] = {}
        self._identities_by_key_id: Dict[str, TrustedOperatorIdentity] = {}
        if identities:
            for ident in identities:
                self.register_identity(ident)

    def register_identity(self, identity: TrustedOperatorIdentity) -> None:
        """
        Registers or updates an operator identity.
        """
        self._identities[identity.operator_id] = identity
        self._identities_by_key_id[identity.key_id] = identity

    def get_identity(self, operator_id: str) -> Optional[TrustedOperatorIdentity]:
        """
        Retrieves identity by operator ID.
        """
        return self._identities.get(operator_id)

    def get_identity_by_key_id(self, key_id: str) -> Optional[TrustedOperatorIdentity]:
        """
        Retrieves identity by key ID.
        """
        return self._identities_by_key_id.get(key_id)

    def get_operator_role(self, operator_id: str) -> Optional[str]:
        """
        Retrieves authoritative assigned role for operator ID from registry.
        """
        identity = self._identities.get(operator_id)
        return identity.role if identity else None

    def revoke_identity(self, operator_id: str, reason: str = "Administrative revocation") -> bool:
        """
        Revokes an operator identity.
        """
        identity = self._identities.get(operator_id)
        if identity:
            identity.is_revoked = True
            identity.revocation_reason = reason
            return True
        return False

    def verify_intent(
        self,
        intent: OperatorApprovalIntent,
        required_role: str = "APPROVAL_ADMIN",
        now_utc: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Performs comprehensive verification of an OperatorApprovalIntent:
          1. Operator registered in registry.
          2. Operator identity is active, within validity window, and unrevoked.
          3. Operator's registered role matches required_role (anti-spoofing).
          4. Intent's operator_key_id matches registered key_id.
          5. Intent has not expired.
          6. Nonce is non-empty and minimum 16 bytes (32 hex characters) or UUID format.
          7. Ed25519 signature is cryptographically valid under registered public key.
        """
        # 1. Existence
        identity = self.get_identity(intent.operator_id)
        if not identity:
            return False, f"UNTRUSTED_OPERATOR: Operator '{intent.operator_id}' not found in trusted registry"

        # 2. Key ID binding
        if identity.key_id != intent.operator_key_id:
            return False, (
                f"KEY_ID_MISMATCH: Operator '{intent.operator_id}' registered with key_id "
                f"'{identity.key_id}', but intent specifies '{intent.operator_key_id}'"
            )

        # 3. Active & unrevoked
        is_active, active_reason = identity.is_active(now_utc=now_utc)
        if not is_active:
            return False, active_reason

        # 4. Strict role enforcement (Registry role, NEVER self-declared role)
        if identity.role != required_role:
            return False, (
                f"INSUFFICIENT_ROLE_PRIVILEGES: Operator '{intent.operator_id}' has registry role "
                f"'{identity.role}', but action requires authoritative role '{required_role}'"
            )

        if intent.operator_role != identity.role:
            return False, (
                f"ROLE_DECLARATION_MISMATCH: Intent claims role '{intent.operator_role}', "
                f"but registry assigns '{identity.role}'"
            )

        # 5. Intent expiration
        if intent.is_expired(now_utc=now_utc):
            return False, f"EXPIRED_INTENT: Approval intent expired at {intent.expires_at_utc}"

        # 6. Nonce sanity
        if not intent.nonce or len(intent.nonce.strip()) < 16:
            return False, "INVALID_NONCE: Nonce must be at least 16 characters for cryptographic entropy"

        # 7. Signature verification
        if not intent.signature_hex:
            return False, "MISSING_SIGNATURE: Approval intent contains no cryptographic signature"

        sig_valid = intent.verify_cryptographic_signature(identity.public_key_hex)
        if not sig_valid:
            return False, "INVALID_CRYPTOGRAPHIC_SIGNATURE: Ed25519 signature verification failed against registered public key"

        return True, "INTENT_VERIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry_version": "v1",
            "identities": [ident.to_dict() for ident in self._identities.values()],
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TrustedOperatorIdentityRegistry:
        identities = [TrustedOperatorIdentity.from_dict(d) for d in data.get("identities", [])]
        return cls(identities=identities)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> TrustedOperatorIdentityRegistry:
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save_to_file(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def create_default_test_registry(cls) -> Tuple[TrustedOperatorIdentityRegistry, Dict[str, bytes]]:
        """
        Creates a reproducible test registry with predefined operators and returns their private seeds.
        Used for unit tests, offline rehearsals, and controlled validation.
        """
        # Deterministic seeds derived via SHA-256
        seeds = {
            "OP-APPROVAL-ADMIN-01": hashlib.sha256(b"CBE-TEST-SEED-APPROVAL-ADMIN-01").digest(),
            "OP-RESEARCH-LEAD-01": hashlib.sha256(b"CBE-TEST-SEED-RESEARCH-LEAD-01").digest(),
            "OP-AUDITOR-01": hashlib.sha256(b"CBE-TEST-SEED-AUDITOR-01").digest(),
            "OP-OPERATOR-02": hashlib.sha256(b"CBE-TEST-SEED-OPERATOR-02").digest(),
        }

        now_utc = "2026-01-01T00:00:00Z"
        exp_utc = "2028-01-01T00:00:00Z"

        admin_pub = ed25519_public_key(seeds["OP-APPROVAL-ADMIN-01"]).hex()
        research_pub = ed25519_public_key(seeds["OP-RESEARCH-LEAD-01"]).hex()
        auditor_pub = ed25519_public_key(seeds["OP-AUDITOR-01"]).hex()
        operator_pub = ed25519_public_key(seeds["OP-OPERATOR-02"]).hex()

        identities = [
            TrustedOperatorIdentity(
                operator_id="OP-APPROVAL-ADMIN-01",
                role="APPROVAL_ADMIN",
                operator_name="Primary Approval Administrator",
                public_key_hex=admin_pub,
                key_id="KEY-ADMIN-01",
                active_from_utc=now_utc,
                expires_at_utc=exp_utc,
                allowed_capabilities=["ACQUISITION_EXECUTE", "SCHEDULE_VERIFY", "*"],
            ),
            TrustedOperatorIdentity(
                operator_id="OP-RESEARCH-LEAD-01",
                role="RESEARCH_OPERATOR",
                operator_name="Lead Research Analyst",
                public_key_hex=research_pub,
                key_id="KEY-RESEARCH-01",
                active_from_utc=now_utc,
                expires_at_utc=exp_utc,
                allowed_capabilities=["SCHEDULE_PROPOSE", "SCHEDULE_VERIFY"],
            ),
            TrustedOperatorIdentity(
                operator_id="OP-AUDITOR-01",
                role="AUDITOR",
                operator_name="Independent Security Auditor",
                public_key_hex=auditor_pub,
                key_id="KEY-AUDITOR-01",
                active_from_utc=now_utc,
                expires_at_utc=exp_utc,
                allowed_capabilities=["AUDIT_INSPECT", "READ_ONLY"],
            ),
            TrustedOperatorIdentity(
                operator_id="OP-OPERATOR-02",
                role="RESEARCH_OPERATOR",
                operator_name="Secondary Operations Engineer",
                public_key_hex=operator_pub,
                key_id="KEY-OPERATOR-02",
                active_from_utc=now_utc,
                expires_at_utc=exp_utc,
                allowed_capabilities=["SCHEDULE_PROPOSE"],
            ),
        ]
        registry = cls(identities=identities)
        return registry, seeds
