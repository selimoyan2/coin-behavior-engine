"""
Credential Isolation and Evidence Signing Key Management Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Enforces strict separation of credentials by purpose:
1. Operator Authentication: CBE_OPERATOR_TOKEN
2. Evidence Signing: CBE_EVIDENCE_SIGNING_KEY (with key_id and rotation registry)
3. Staging Test Automation: CBE_TEST_OPERATOR_TOKEN (strictly barred from production)
4. Administrative Diagnostics: CBE_ADMIN_DIAGNOSTICS_TOKEN

Guarantees:
- Credential reuse between operator token and signing key is strictly prohibited.
- Constant-time verification against timing attacks.
- Fail-closed behavior on missing or invalid secrets.
- Secrets never exposed in logs, API payloads, or exception messages.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class CredentialSeparationViolationError(RuntimeError):
    """Raised when credential reuse across distinct security boundaries is detected."""
    pass


class InvalidCredentialError(ValueError):
    """Raised when a credential is malformed or invalid."""
    pass


class CredentialManager:
    """Manages system secrets and enforces credential separation across security domains."""

    @classmethod
    def get_environment(cls) -> str:
        """Returns the canonical current environment string (staging, development, production)."""
        return os.environ.get("CBE_ENV", "staging").strip().lower()

    @classmethod
    def is_production(cls) -> bool:
        """Checks if current execution context is marked as production."""
        return cls.get_environment() == "production"

    @classmethod
    def get_operator_token(cls) -> Optional[str]:
        """Returns configured operator authentication token."""
        return (
            os.environ.get("CBE_OPERATOR_TOKEN")
            or os.environ.get("OPERATOR_TOKEN")
        )

    @classmethod
    def get_evidence_signing_key(cls) -> Optional[str]:
        """Returns configured evidence signing secret key."""
        return (
            os.environ.get("CBE_EVIDENCE_SIGNING_KEY")
            or os.environ.get("CBE_OPERATOR_SIGNATURE_KEY")
        )

    @classmethod
    def get_test_operator_token(cls) -> Optional[str]:
        """
        Returns staging test automation token.
        STRICT FAIL-CLOSED: Test operator token is NEVER accepted in production.
        """
        if cls.is_production():
            return None
        return os.environ.get("CBE_TEST_OPERATOR_TOKEN")

    @classmethod
    def get_admin_diagnostics_token(cls) -> Optional[str]:
        """Returns administrative token for privileged diagnostic inspection."""
        return os.environ.get("CBE_ADMIN_DIAGNOSTICS_TOKEN")

    @classmethod
    def validate_credential_separation(cls) -> None:
        """
        Validates that operator authentication and evidence signing keys are distinct.
        Raises CredentialSeparationViolationError if cross-purpose credential reuse is detected.
        """
        op_tok = cls.get_operator_token()
        sig_key = cls.get_evidence_signing_key()

        if op_tok and sig_key:
            if hmac.compare_digest(op_tok.strip().encode("utf-8"), sig_key.strip().encode("utf-8")):
                raise CredentialSeparationViolationError(
                    "CREDENTIAL_REUSE_PROHIBITED: Operator authentication token must not serve "
                    "as HMAC evidence signing key. Use distinct credentials for authentication and signing."
                )

        # In production, test operator token must not be configured or accepted
        if cls.is_production():
            test_tok = os.environ.get("CBE_TEST_OPERATOR_TOKEN")
            if test_tok and test_tok.strip():
                raise CredentialSeparationViolationError(
                    "PRODUCTION_SECRET_VIOLATION: CBE_TEST_OPERATOR_TOKEN is strictly prohibited in production."
                )

    @classmethod
    def verify_operator_token(cls, candidate: Optional[str]) -> Tuple[bool, str]:
        """
        Validates operator token in constant time.
        Rejects empty, revoked, malformed, or mismatched tokens.
        """
        if not candidate or not isinstance(candidate, str):
            return False, "TOKEN_EMPTY_OR_INVALID"

        token = candidate.strip()
        if len(token) < 8:
            return False, "TOKEN_MALFORMED"

        from coin_behavior_engine.product.operations_console import is_token_revoked
        if is_token_revoked(token):
            return False, "TOKEN_REVOKED"

        # Check configured operator token
        op_tok = cls.get_operator_token()
        if op_tok and hmac.compare_digest(token.encode("utf-8"), op_tok.strip().encode("utf-8")):
            return True, "AUTHORIZED_OPERATOR"

        # Check staging test operator token (only non-production)
        if not cls.is_production():
            test_tok = cls.get_test_operator_token()
            if test_tok and hmac.compare_digest(token.encode("utf-8"), test_tok.strip().encode("utf-8")):
                return True, "AUTHORIZED_TEST_OPERATOR"

        return False, "TOKEN_MISMATCH"

    @classmethod
    def verify_admin_diagnostics_token(cls, candidate: Optional[str]) -> Tuple[bool, str]:
        """Validates administrative diagnostics token."""
        if not candidate or not isinstance(candidate, str):
            return False, "TOKEN_EMPTY"

        token = candidate.strip()
        from coin_behavior_engine.product.operations_console import is_token_revoked
        if is_token_revoked(token):
            return False, "TOKEN_REVOKED"

        admin_tok = cls.get_admin_diagnostics_token()
        if admin_tok and hmac.compare_digest(token.encode("utf-8"), admin_tok.strip().encode("utf-8")):
            return True, "AUTHORIZED_ADMIN"

        # Operator token can also access diagnostics if admin token not configured
        if not admin_tok:
            valid, reason = cls.verify_operator_token(token)
            if valid:
                return True, "AUTHORIZED_OPERATOR_FALLBACK"

        return False, "TOKEN_MISMATCH"


class SigningKeyRegistry:
    """
    Registry for HMAC-SHA256 evidence signing keys with rotation and revocation support.
    Ensures verifiable backward compatibility for historical keys while signing with active key.
    """

    DEFAULT_KEY_ID = "k2026-v1"

    def __init__(self):
        self._active_key_id: str = os.environ.get("CBE_EVIDENCE_SIGNING_KEY_ID", self.DEFAULT_KEY_ID)
        self._keys: Dict[str, str] = {}
        self._revoked_key_ids: Set[str] = set()

        # Initialize active key
        active_secret = CredentialManager.get_evidence_signing_key()
        if active_secret:
            self._keys[self._active_key_id] = active_secret.strip()

        # Initialize revoked key IDs from environment
        rev_env = os.environ.get("CBE_REVOKED_SIGNING_KEYS", "")
        if rev_env:
            for r_id in rev_env.split(","):
                clean = r_id.strip()
                if clean:
                    self._revoked_key_ids.add(clean)

        # Initialize historical verification keys (format: JSON {"key_id": "secret"} or comma separated id:secret)
        hist_env = os.environ.get("CBE_HISTORICAL_SIGNING_KEYS", "")
        if hist_env:
            try:
                data = json.loads(hist_env)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, str):
                            self._keys[k.strip()] = v.strip()
            except Exception:
                for item in hist_env.split(","):
                    if ":" in item:
                        k_id, k_sec = item.split(":", 1)
                        self._keys[k_id.strip()] = k_sec.strip()

    def register_key(self, key_id: str, secret: str, is_active: bool = False) -> None:
        """Registers a signing or verification key."""
        if not key_id or not secret:
            raise InvalidCredentialError("Key ID and secret must be non-empty strings")
        self._keys[key_id] = secret
        if is_active:
            self._active_key_id = key_id

    def revoke_key(self, key_id: str) -> None:
        """Revokes a key ID from valid verification."""
        self._revoked_key_ids.add(key_id)

    def is_key_revoked(self, key_id: str) -> bool:
        """Checks if a key ID has been explicitly revoked."""
        return key_id in self._revoked_key_ids

    def get_active_key(self) -> Tuple[Optional[str], Optional[str]]:
        """Returns (active_key_id, active_secret)."""
        secret = self._keys.get(self._active_key_id)
        if not secret:
            return None, None
        return self._active_key_id, secret

    def sign_canonical_payload(self, canonical_bytes: bytes) -> str:
        """
        Signs canonical bytes with the active key.
        Returns format: hmac-sha256:<key_id>:<hex_signature>
        """
        key_id, secret = self.get_active_key()
        if not secret or not key_id:
            raise RuntimeError("NO_ACTIVE_SIGNING_KEY_CONFIGURED: Cannot sign evidence payload.")
        if self.is_key_revoked(key_id):
            raise RuntimeError(f"ACTIVE_KEY_REVOKED: Active signing key '{key_id}' is revoked.")

        h = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256)
        return f"hmac-sha256:{key_id}:{h.hexdigest()}"

    def verify_signature(
        self,
        canonical_bytes: bytes,
        signature_str: str,
        trusted_keys_override: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verifies an evidence signature.
        Supports structured format: hmac-sha256:<key_id>:<hex>
        Supports legacy format: hmac-sha256:<hex> or raw hex.
        Returns: (is_valid, reason, key_id)
        """
        if not signature_str or not isinstance(signature_str, str):
            return False, "SIGNATURE_EMPTY_OR_INVALID", None

        sig_clean = signature_str.strip()

        # Format 1: Structured hmac-sha256:<key_id>:<hex>
        match_structured = re.match(r"^hmac-sha256:([a-zA-Z0-9_-]+):([a-fA-F0-9]{64})$", sig_clean)
        if match_structured:
            key_id, sig_hex = match_structured.group(1), match_structured.group(2)
            if self.is_key_revoked(key_id):
                return False, "REVOKED_SIGNING_KEY", key_id

            # Look up in registered keys
            secret = self._keys.get(key_id)
            if not secret and trusted_keys_override:
                for k in trusted_keys_override:
                    if k:
                        expected = hmac.new(k.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
                        if hmac.compare_digest(sig_hex, expected):
                            return True, "HMAC_SHA256_VERIFIED", key_id
                return False, "UNKNOWN_SIGNING_KEY", key_id

            if not secret:
                return False, "UNKNOWN_SIGNING_KEY", key_id

            expected_hex = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig_hex, expected_hex):
                return True, "HMAC_SHA256_VERIFIED", key_id
            return False, "HMAC_SIGNATURE_MISMATCH", key_id

        # Format 2: Legacy hmac-sha256:<hex>
        sig_hex = sig_clean
        if sig_clean.startswith("hmac-sha256:"):
            sig_hex = sig_clean[len("hmac-sha256:"):]

        candidate_keys = list(self._keys.values())
        if trusted_keys_override:
            for k in trusted_keys_override:
                if k and k not in candidate_keys:
                    candidate_keys.append(k)

        for k in candidate_keys:
            expected = hmac.new(k.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig_hex, expected):
                # Check if this key corresponds to a revoked key_id
                matching_ids = [kid for kid, sec in self._keys.items() if sec == k]
                revoked_ids = [kid for kid in matching_ids if self.is_key_revoked(kid)]
                if revoked_ids:
                    return False, "REVOKED_SIGNING_KEY", revoked_ids[0]
                matched_id = matching_ids[0] if matching_ids else "legacy"
                return True, "HMAC_SHA256_VERIFIED", matched_id

        return False, "HMAC_SIGNATURE_MISMATCH", None


# Global singleton instance
signing_key_registry = SigningKeyRegistry()
