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

from contextlib import contextmanager
from contextvars import ContextVar
import hmac
import hashlib
import json
import os
import re
import secrets
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple


KEY_PURPOSE_EVIDENCE_BUNDLE = "EVIDENCE_BUNDLE_SIGNING"
KEY_PURPOSE_OBSERVATION_ATTESTATION = "OBSERVATION_ATTESTATION_SIGNING"
KEY_PURPOSE_INTAKE_MANIFEST = "INTAKE_MANIFEST_SIGNING"
KEY_PURPOSE_REFERENCE_PROVENANCE = "REFERENCE_PROVENANCE_SIGNING"
KEY_PURPOSE_REPLICATION_ATTESTATION = "REPLICATION_ATTESTATION_SIGNING"

DEFAULT_LEGACY_KEY_PURPOSES: Tuple[str, ...] = (
    KEY_PURPOSE_EVIDENCE_BUNDLE,
    KEY_PURPOSE_OBSERVATION_ATTESTATION,
    KEY_PURPOSE_INTAKE_MANIFEST,
    KEY_PURPOSE_REFERENCE_PROVENANCE,
)

ALL_SIGNING_PURPOSES: Tuple[str, ...] = (
    KEY_PURPOSE_EVIDENCE_BUNDLE,
    KEY_PURPOSE_OBSERVATION_ATTESTATION,
    KEY_PURPOSE_INTAKE_MANIFEST,
    KEY_PURPOSE_REFERENCE_PROVENANCE,
    KEY_PURPOSE_REPLICATION_ATTESTATION,
)

# Per-process cryptographic capability MAC secret (never exposed outside module)
_PROCESS_AUTHORITY_MAC_SECRET: bytes = secrets.token_bytes(32)
_ACTIVE_AUTHORITY_SESSIONS: Set[str] = set()
_PUBLIC_API_REQUEST_ACTIVE: ContextVar[bool] = ContextVar("_PUBLIC_API_REQUEST_ACTIVE", default=False)


@contextmanager
def public_api_request_guard() -> Iterator[None]:
    """Marks the current execution context as an ordinary public/research API request (verification-only)."""
    token = _PUBLIC_API_REQUEST_ACTIVE.set(True)
    try:
        yield
    finally:
        _PUBLIC_API_REQUEST_ACTIVE.reset(token)


def is_public_api_request_active() -> bool:
    """Returns True if executing inside a public/research API request context."""
    return bool(_PUBLIC_API_REQUEST_ACTIVE.get())


class CredentialSeparationViolationError(RuntimeError):
    """Raised when credential reuse across distinct security boundaries is detected."""
    pass


class InvalidCredentialError(ValueError):
    """Raised when a credential is malformed or invalid."""
    pass


class SigningAuthorityError(PermissionError, RuntimeError):
    """
    Fail-closed exception raised when a cryptographic signing operation violates
    key-registry presence, lifecycle/revocation rules, key purpose permissions,
    caller signing authority, or runtime environment restrictions.
    Never exposes raw key material or signing secrets.
    """

    def __init__(self, rejection_code: str, message: str) -> None:
        self.rejection_code = str(rejection_code)
        self.message = str(message)
        super().__init__(f"{self.rejection_code}: {self.message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_authorized": False,
            "rejection_code": self.rejection_code,
            "message": self.message,
        }


class SigningAuthorityContext:
    """
    Unforgeable server-side signing authority token bound to a process-private HMAC seal,
    explicit signing purposes, allowed key IDs, and runtime environment scope.
    Boolean flags (is_admin=True, authorized=True) or caller-constructed dicts are never accepted.
    """

    def __init__(
        self,
        *,
        context_id: str,
        authority_principal: str,
        allowed_purposes: Set[str],
        allowed_key_ids: Optional[Set[str]],
        environment_scope: str,
        is_test_authority: bool,
        capability_seal: str,
    ) -> None:
        self._context_id = str(context_id)
        self._authority_principal = str(authority_principal)
        self._allowed_purposes = frozenset(str(p) for p in allowed_purposes)
        self._allowed_key_ids = (
            frozenset(str(k) for k in allowed_key_ids) if allowed_key_ids is not None else None
        )
        self._environment_scope = str(environment_scope)
        self._is_test_authority = bool(is_test_authority)
        self._capability_seal = str(capability_seal)

    @property
    def context_id(self) -> str:
        return self._context_id

    @property
    def authority_principal(self) -> str:
        return self._authority_principal

    @property
    def allowed_purposes(self) -> frozenset[str]:
        return self._allowed_purposes

    @property
    def allowed_key_ids(self) -> Optional[frozenset[str]]:
        return self._allowed_key_ids

    @property
    def is_test_authority(self) -> bool:
        return self._is_test_authority

    @staticmethod
    def _compute_seal(
        context_id: str,
        authority_principal: str,
        allowed_purposes: Set[str],
        allowed_key_ids: Optional[Set[str]],
        environment_scope: str,
        is_test_authority: bool,
    ) -> str:
        payload = json.dumps(
            {
                "cid": context_id,
                "principal": authority_principal,
                "purposes": sorted(allowed_purposes),
                "keys": sorted(allowed_key_ids) if allowed_key_ids is not None else ["*"],
                "env": environment_scope,
                "test": bool(is_test_authority),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(_PROCESS_AUTHORITY_MAC_SECRET, payload, hashlib.sha256).hexdigest()

    def verify_integrity(self) -> bool:
        """Verifies the process-private HMAC seal on this authority context."""
        if not self._context_id or not self._capability_seal:
            return False
        expected = self._compute_seal(
            context_id=self._context_id,
            authority_principal=self._authority_principal,
            allowed_purposes=set(self._allowed_purposes),
            allowed_key_ids=set(self._allowed_key_ids) if self._allowed_key_ids is not None else None,
            environment_scope=self._environment_scope,
            is_test_authority=self._is_test_authority,
        )
        return hmac.compare_digest(self._capability_seal.encode("utf-8"), expected.encode("utf-8"))

    def is_session_open(self) -> bool:
        """Checks whether this signing authority session is currently active and unrevoked."""
        return self._context_id in _ACTIVE_AUTHORITY_SESSIONS

    def close(self) -> None:
        """Revokes/closes this signing authority session immediately."""
        _ACTIVE_AUTHORITY_SESSIONS.discard(self._context_id)

    @classmethod
    def authorize_operator_signing(
        cls,
        operator_token: Optional[str],
        purposes: Optional[Sequence[str]] = None,
        allowed_key_ids: Optional[Sequence[str]] = None,
    ) -> "SigningAuthorityContext":
        """
        Establishes an operator signing authority context after constant-time verification
        of the server-side operator token and environment signing policy.
        """
        if is_public_api_request_active():
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                "Signing authority cannot be granted inside ordinary research API request contexts.",
            )
        runtime_mode = CredentialManager.get_runtime_signing_mode()
        if runtime_mode != "SIGNING_AUTHORITY_ENABLED":
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                f"Runtime signing mode is '{runtime_mode}'; operator signing requires SIGNING_AUTHORITY_ENABLED.",
            )
        is_valid, reason = CredentialManager.verify_operator_token(operator_token)
        if not is_valid or reason != "AUTHORIZED_OPERATOR":
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "Caller failed server-side operator authentication for signing authority.",
            )
        p_set = set(purposes) if purposes else {KEY_PURPOSE_REPLICATION_ATTESTATION}
        k_set = set(allowed_key_ids) if allowed_key_ids is not None else None
        cid = f"op-sign-{secrets.token_hex(12)}"
        env_scope = CredentialManager.get_environment()
        seal = cls._compute_seal(
            context_id=cid,
            authority_principal="CBE_AUTHORIZED_OPERATOR_SIGNING_AUTHORITY",
            allowed_purposes=p_set,
            allowed_key_ids=k_set,
            environment_scope=env_scope,
            is_test_authority=False,
        )
        _ACTIVE_AUTHORITY_SESSIONS.add(cid)
        return cls(
            context_id=cid,
            authority_principal="CBE_AUTHORIZED_OPERATOR_SIGNING_AUTHORITY",
            allowed_purposes=p_set,
            allowed_key_ids=k_set,
            environment_scope=env_scope,
            is_test_authority=False,
            capability_seal=seal,
        )

    @classmethod
    def authorize_isolated_test_signing(
        cls,
        allowed_key_ids: Optional[Sequence[str]] = None,
        purposes: Optional[Sequence[str]] = None,
    ) -> "SigningAuthorityContext":
        """
        Creates a strictly isolated test signing authority context for unit/integration tests.
        Blocked in production, blocked inside public API request handlers, and blocked when
        runtime mode is locked to verification-only.
        """
        if CredentialManager.is_production():
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                "Isolated test signing authority is strictly prohibited in production.",
            )
        if is_public_api_request_active():
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                "Test signing authority cannot be invoked from public API request contexts.",
            )
        if os.environ.get("CBE_DISALLOW_TEST_SIGNING_AUTHORITY", "").strip().lower() in ("1", "true", "yes"):
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                "Test signing authority is disabled in the current runtime configuration.",
            )
        explicit_mode = os.environ.get("CBE_RUNTIME_SIGNING_MODE", "").strip().upper()
        if explicit_mode in ("VERIFICATION_ONLY", "VERIFICATION_ONLY_LOCKED", "DISABLED"):
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                f"Runtime is explicitly locked to '{explicit_mode}'; signing operations are not permitted.",
            )
        k_set: Optional[Set[str]] = None
        if allowed_key_ids is not None:
            k_set = {str(k).strip() for k in allowed_key_ids if str(k).strip()}
            if not k_set:
                raise SigningAuthorityError(
                    "SIGNING_KEY_NOT_FOUND",
                    "Isolated test signing authority requires at least one explicit test key ID.",
                )
        p_set = set(purposes) if purposes else {KEY_PURPOSE_REPLICATION_ATTESTATION}
        cid = f"test-sign-{secrets.token_hex(12)}"
        seal = cls._compute_seal(
            context_id=cid,
            authority_principal="CBE_ISOLATED_TEST_SIGNING_CONTEXT",
            allowed_purposes=p_set,
            allowed_key_ids=k_set,
            environment_scope="test_isolated",
            is_test_authority=True,
        )
        _ACTIVE_AUTHORITY_SESSIONS.add(cid)
        return cls(
            context_id=cid,
            authority_principal="CBE_ISOLATED_TEST_SIGNING_CONTEXT",
            allowed_purposes=p_set,
            allowed_key_ids=k_set,
            environment_scope="test_isolated",
            is_test_authority=True,
            capability_seal=seal,
        )


class CredentialManager:
    """Manages system secrets and enforces credential separation across security domains."""

    @classmethod
    def get_environment(cls) -> str:
        """Returns the canonical current environment string (staging, development, production)."""
        return os.environ.get("CBE_ENV", "staging").strip().lower()

    @classmethod
    def get_runtime_signing_mode(cls) -> str:
        """
        Returns the runtime signing mode.
        Defaults to VERIFICATION_ONLY in ordinary staging/production research runtimes
        so that verification is available without granting signing capability.
        """
        return os.environ.get("CBE_RUNTIME_SIGNING_MODE", "VERIFICATION_ONLY").strip().upper()

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
    Registry for HMAC-SHA256 evidence signing keys with rotation, purpose separation,
    lifecycle management, and revocation support.
    Ensures verifiable backward compatibility for historical keys while signing only
    with active, purpose-authorized keys under verified server-side authority.
    """

    DEFAULT_KEY_ID = "k2026-v1"
    # Key IDs permanently revoked due to historical retirement or prior source-code exposure
    DEFAULT_REVOKED_KEY_IDS: Tuple[str, ...] = (
        "cbe-attestation-2025-revoked",
        "cbe-attestation-2026-v1",
        "cbe-data-authority-2026-v1",
    )

    def __init__(self):
        self._active_key_id: str = os.environ.get("CBE_EVIDENCE_SIGNING_KEY_ID", self.DEFAULT_KEY_ID)
        self._keys: Dict[str, str] = {}
        self._key_metadata: Dict[str, Dict[str, Any]] = {}
        self._revoked_key_ids: Set[str] = set(self.DEFAULT_REVOKED_KEY_IDS)

        # Initialize active key
        active_secret = CredentialManager.get_evidence_signing_key()
        if active_secret:
            clean_id = self._active_key_id.strip()
            self._keys[clean_id] = active_secret.strip()
            self._key_metadata[clean_id] = {
                "key_id": clean_id,
                "is_active_for_signing": True,
                "lifecycle_state": "ACTIVE",
                "allowed_purposes": set(ALL_SIGNING_PURPOSES),
                "is_test_key": False,
            }

        # Initialize revoked key IDs from environment
        rev_env = os.environ.get("CBE_REVOKED_SIGNING_KEYS", "")
        if rev_env:
            for r_id in rev_env.split(","):
                clean = r_id.strip()
                if clean:
                    self._revoked_key_ids.add(clean)

        # Initialize historical verification keys (format: JSON {"key_id": "secret"} or comma separated id:secret)
        # Historical keys are strictly HISTORICAL_VERIFY_ONLY and cannot issue new signatures.
        hist_env = os.environ.get("CBE_HISTORICAL_SIGNING_KEYS", "")
        if hist_env:
            try:
                data = json.loads(hist_env)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, str):
                            ck = k.strip()
                            self._keys[ck] = v.strip()
                            self._key_metadata[ck] = {
                                "key_id": ck,
                                "is_active_for_signing": False,
                                "lifecycle_state": "HISTORICAL_VERIFY_ONLY",
                                "allowed_purposes": set(),
                                "is_test_key": False,
                            }
            except Exception:
                for item in hist_env.split(","):
                    if ":" in item:
                        k_id, k_sec = item.split(":", 1)
                        ck = k_id.strip()
                        self._keys[ck] = k_sec.strip()
                        self._key_metadata[ck] = {
                            "key_id": ck,
                            "is_active_for_signing": False,
                            "lifecycle_state": "HISTORICAL_VERIFY_ONLY",
                            "allowed_purposes": set(),
                            "is_test_key": False,
                        }

    def register_key(
        self,
        key_id: str,
        secret: str,
        is_active: bool = False,
        allowed_purposes: Optional[Sequence[str]] = None,
        is_test_key: bool = False,
        lifecycle_state: Optional[str] = None,
    ) -> None:
        """
        Registers a signing or verification key with explicit lifecycle state and purpose permissions.
        By default, legacy registrations without explicit allowed_purposes do NOT receive
        REPLICATION_ATTESTATION_SIGNING permission.
        """
        if not key_id or not secret or not isinstance(key_id, str) or not isinstance(secret, str):
            raise InvalidCredentialError("Key ID and secret must be non-empty strings")
        clean_id = key_id.strip()
        clean_secret = secret.strip()
        if not clean_id or not clean_secret:
            raise InvalidCredentialError("Key ID and secret must be non-empty strings")

        self._keys[clean_id] = clean_secret
        # If an explicitly registered key was in DEFAULT_REVOKED_KEY_IDS only by default and not revoked again,
        # keep revocation if it was explicitly revoked.
        effective_purposes = (
            {str(p).strip() for p in allowed_purposes if str(p).strip()}
            if allowed_purposes is not None
            else set(DEFAULT_LEGACY_KEY_PURPOSES)
        )
        eff_state = lifecycle_state or ("ACTIVE" if is_active else "HISTORICAL_VERIFY_ONLY")
        if self.is_key_revoked(clean_id):
            eff_state = "REVOKED"
        self._key_metadata[clean_id] = {
            "key_id": clean_id,
            "is_active_for_signing": bool(is_active) and eff_state == "ACTIVE",
            "lifecycle_state": eff_state,
            "allowed_purposes": effective_purposes,
            "is_test_key": bool(is_test_key),
        }
        if is_active:
            self._active_key_id = clean_id

    def get_runtime_signing_mode(self) -> str:
        """Returns the current runtime signing mode (defaults to VERIFICATION_ONLY)."""
        return CredentialManager.get_runtime_signing_mode()

    def rotate_key(
        self,
        old_key_id: str,
        new_key_id: str,
        new_secret: str,
        allowed_purposes: Optional[Sequence[str]] = None,
        is_test_key: bool = False,
        keep_old_for_verification: bool = True,
    ) -> None:
        """
        Rotates signing authority from old_key_id to new_key_id.
        Demotes old_key_id to HISTORICAL_VERIFY_ONLY so existing evidence signed by old_key_id
        remains verifiable while preventing old_key_id from issuing new signatures.
        """
        clean_old = (old_key_id or "").strip()
        if clean_old in self._key_metadata:
            self._key_metadata[clean_old]["is_active_for_signing"] = False
            if not keep_old_for_verification:
                self.revoke_key(clean_old)
            elif not self.is_key_revoked(clean_old):
                self._key_metadata[clean_old]["lifecycle_state"] = "HISTORICAL_VERIFY_ONLY"
        self.register_key(
            key_id=new_key_id,
            secret=new_secret,
            is_active=True,
            allowed_purposes=allowed_purposes,
            is_test_key=is_test_key,
            lifecycle_state="ACTIVE",
        )

    def revoke_key(self, key_id: str) -> None:
        """Revokes a key ID from both signing and verification, and invalidates verification cache."""
        clean_id = (key_id or "").strip()
        if not clean_id:
            return
        self._revoked_key_ids.add(clean_id)
        if clean_id in self._key_metadata:
            self._key_metadata[clean_id]["is_active_for_signing"] = False
            self._key_metadata[clean_id]["lifecycle_state"] = "REVOKED"
        try:
            from coin_behavior_engine.product.attestation_verifier import attestation_cache
            attestation_cache.invalidate_key(clean_id)
        except Exception:
            pass

    def remove_key(self, key_id: str) -> None:
        """Removes a key (such as an ephemeral isolated test key) from the registry."""
        clean_id = (key_id or "").strip()
        self._keys.pop(clean_id, None)
        self._key_metadata.pop(clean_id, None)

    def has_key(self, key_id: str) -> bool:
        """Checks whether a key ID exists in the registry without exposing its secret."""
        if not key_id or not isinstance(key_id, str):
            return False
        return key_id.strip() in self._keys

    def get_key_metadata(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Returns non-sensitive metadata for a registered key (never exposes raw secret)."""
        if not key_id or not isinstance(key_id, str):
            return None
        clean_id = key_id.strip()
        meta = self._key_metadata.get(clean_id)
        if not meta:
            if clean_id in self._keys:
                return {
                    "key_id": clean_id,
                    "is_active_for_signing": clean_id == self._active_key_id and not self.is_key_revoked(clean_id),
                    "lifecycle_state": "REVOKED" if self.is_key_revoked(clean_id) else "REGISTERED",
                    "allowed_purposes": sorted(DEFAULT_LEGACY_KEY_PURPOSES),
                    "is_test_key": False,
                    "is_revoked": self.is_key_revoked(clean_id),
                }
            return None
        return {
            "key_id": clean_id,
            "is_active_for_signing": bool(meta.get("is_active_for_signing", False)) and not self.is_key_revoked(clean_id),
            "lifecycle_state": "REVOKED" if self.is_key_revoked(clean_id) else str(meta.get("lifecycle_state", "INACTIVE")),
            "allowed_purposes": sorted(meta.get("allowed_purposes", set())),
            "is_test_key": bool(meta.get("is_test_key", False)),
            "is_revoked": self.is_key_revoked(clean_id),
        }

    def is_key_revoked(self, key_id: str) -> bool:
        """Checks if a key ID has been explicitly revoked."""
        if not key_id or not isinstance(key_id, str):
            return False
        return key_id.strip() in self._revoked_key_ids

    @contextmanager
    def isolated_test_signing_context(
        self,
        key_id: str,
        secret: str,
        purposes: Optional[Sequence[str]] = None,
        remove_key_on_exit: bool = True,
    ) -> Iterator[SigningAuthorityContext]:
        """
        Context manager for isolated test signing.
        Registers an ephemeral test key with explicit purposes, yields an authorized
        test SigningAuthorityContext, and revokes the session on exit so test signing
        authority never leaks into application runtime.
        """
        eff_purposes = list(purposes) if purposes is not None else [KEY_PURPOSE_REPLICATION_ATTESTATION]
        prev_active = self._active_key_id
        self.register_key(
            key_id=key_id,
            secret=secret,
            is_active=True,
            allowed_purposes=eff_purposes,
            is_test_key=True,
            lifecycle_state="ACTIVE",
        )
        auth_ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            allowed_key_ids=[key_id],
            purposes=eff_purposes,
        )
        try:
            yield auth_ctx
        finally:
            auth_ctx.close()
            if remove_key_on_exit:
                self.remove_key(key_id)
            else:
                meta = self._key_metadata.get(key_id.strip())
                if meta:
                    meta["is_active_for_signing"] = False
                    if not self.is_key_revoked(key_id):
                        meta["lifecycle_state"] = "HISTORICAL_VERIFY_ONLY"
            self._active_key_id = prev_active

    def sign_with_authority(
        self,
        canonical_bytes: bytes,
        key_id: Optional[str],
        required_purpose: str,
        authority_context: Any,
        runtime_mode_override: Optional[str] = None,
    ) -> str:
        """
        Narrowly scoped cryptographic signing interface enforcing all 6 P0 requirements:
        1. Requested key_id exists in the authorized signing-key registry (SIGNING_KEY_NOT_FOUND).
        2. Key is active for signing (SIGNING_KEY_NOT_AUTHORIZED).
        3. Key has not been revoked (SIGNING_KEY_REVOKED).
        4. Key is authorized for the required signing purpose (SIGNING_KEY_NOT_AUTHORIZED).
        5. Caller holds a verified server-side SigningAuthorityContext (SIGNING_AUTHORITY_NOT_GRANTED).
        6. Signing operation is permitted in the current runtime environment (SIGNING_OPERATION_NOT_PERMITTED).
        """
        # Condition 6: Environment & Runtime Mode Verification
        if is_public_api_request_active():
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                "Trusted signing operations are prohibited inside public/research API request contexts.",
            )

        explicit_env_mode = (
            (runtime_mode_override or os.environ.get("CBE_RUNTIME_SIGNING_MODE", "")).strip().upper()
        )
        if explicit_env_mode in (
            "VERIFICATION_ONLY",
            "VERIFICATION_ONLY_LOCKED",
            "DISABLED",
            "READ_ONLY",
            "APPLICATION_RUNTIME",
        ):
            raise SigningAuthorityError(
                "SIGNING_OPERATION_NOT_PERMITTED",
                f"Signing operation is not permitted in runtime mode '{explicit_env_mode}'.",
            )

        # Condition 5: Caller Signing Authority Verification
        if (
            authority_context is None
            or isinstance(authority_context, (bool, dict, str, int, float, list, tuple, set))
            or not isinstance(authority_context, SigningAuthorityContext)
        ):
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "Caller lacks a valid server-side SigningAuthorityContext; boolean flags or unauthenticated objects are rejected.",
            )

        if not authority_context.verify_integrity():
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "SigningAuthorityContext cryptographic capability seal is invalid or tampered.",
            )

        if not authority_context.is_session_open():
            if authority_context.is_test_authority:
                raise SigningAuthorityError(
                    "SIGNING_OPERATION_NOT_PERMITTED",
                    "Isolated test signing authority session has closed and cannot leak into runtime.",
                )
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "SigningAuthorityContext session is closed or revoked.",
            )

        if authority_context.is_test_authority:
            if (
                CredentialManager.is_production()
                or explicit_env_mode in ("AUTHORIZED_OPERATOR_SIGNING", "OPERATOR_SIGNING_ONLY")
                or os.environ.get("CBE_DISALLOW_TEST_SIGNING_AUTHORITY", "").strip().lower() in ("1", "true", "yes")
                or os.environ.get("CBE_APP_RUNTIME_ACTIVE", "").strip().lower() in ("1", "true", "yes")
            ):
                raise SigningAuthorityError(
                    "SIGNING_OPERATION_NOT_PERMITTED",
                    "Test signing authority is strictly barred from application or production runtime.",
                )
        else:
            # Non-test operator signing requires SIGNING_AUTHORITY_ENABLED runtime mode
            if CredentialManager.get_runtime_signing_mode() != "SIGNING_AUTHORITY_ENABLED":
                raise SigningAuthorityError(
                    "SIGNING_OPERATION_NOT_PERMITTED",
                    "Application runtime defaults to VERIFICATION_ONLY; operator signing is not enabled in this runtime.",
                )

        if required_purpose not in authority_context.allowed_purposes:
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                f"Caller SigningAuthorityContext does not grant permission for '{required_purpose}'.",
            )

        # Condition 1 & 3: Key Existence and Revocation Checks
        if not key_id or not isinstance(key_id, str) or not key_id.strip():
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_FOUND",
                "Signing key ID is missing or empty.",
            )
        clean_key_id = key_id.strip()

        if self.is_key_revoked(clean_key_id):
            raise SigningAuthorityError(
                "SIGNING_KEY_REVOKED",
                f"Signing key '{clean_key_id}' has been revoked and cannot issue signatures.",
            )

        secret = self._keys.get(clean_key_id)
        if not secret or not isinstance(secret, str):
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_FOUND",
                f"Signing key '{clean_key_id}' does not exist in the authorized signing-key registry.",
            )

        # Condition 2 & 4: Key Active Lifecycle, Test-Key Isolation & Purpose Permission Checks
        meta = self._key_metadata.get(clean_key_id)
        if not meta:
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_AUTHORIZED",
                f"Signing key '{clean_key_id}' lacks authorized signing metadata.",
            )

        if meta.get("is_test_key", False):
            if (
                not authority_context.is_test_authority
                or CredentialManager.is_production()
                or os.environ.get("CBE_APP_RUNTIME_ACTIVE", "").strip().lower() in ("1", "true", "yes")
            ):
                raise SigningAuthorityError(
                    "SIGNING_OPERATION_NOT_PERMITTED",
                    f"Isolated test key '{clean_key_id}' cannot be used outside an isolated test context.",
                )

        if not meta.get("is_active_for_signing", False) or meta.get("lifecycle_state") != "ACTIVE":
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_AUTHORIZED",
                f"Signing key '{clean_key_id}' is not active for signing (state={meta.get('lifecycle_state')}).",
            )

        key_purposes = meta.get("allowed_purposes", set())
        if required_purpose not in key_purposes:
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_AUTHORIZED",
                f"Signing key '{clean_key_id}' is not authorized for purpose '{required_purpose}'.",
            )

        if authority_context.allowed_key_ids is not None and clean_key_id not in authority_context.allowed_key_ids:
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_AUTHORIZED",
                f"Caller authority context is not permitted to sign with key '{clean_key_id}'.",
            )

        h = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256)
        return f"hmac-sha256:{clean_key_id}:{h.hexdigest()}"

    def sign_for_purpose(
        self,
        canonical_bytes: bytes,
        key_id: str,
        required_purpose: str,
    ) -> str:
        """
        Signs canonical bytes using a registered, active, non-revoked key authorized for required_purpose
        without exposing internal _keys storage to callers.
        """
        if not key_id or not isinstance(key_id, str) or not key_id.strip():
            raise SigningAuthorityError("SIGNING_KEY_NOT_FOUND", "Signing key ID is missing.")
        clean_key_id = key_id.strip()
        if self.is_key_revoked(clean_key_id):
            raise SigningAuthorityError(
                "SIGNING_KEY_REVOKED",
                f"Signing key '{clean_key_id}' is revoked.",
            )
        secret = self._keys.get(clean_key_id)
        if not secret:
            raise SigningAuthorityError(
                "SIGNING_KEY_NOT_FOUND",
                f"Signing key '{clean_key_id}' is not registered in SigningKeyRegistry.",
            )
        meta = self._key_metadata.get(clean_key_id)
        if meta:
            if not meta.get("is_active_for_signing", False):
                raise SigningAuthorityError(
                    "SIGNING_KEY_NOT_AUTHORIZED",
                    f"Signing key '{clean_key_id}' is not active for signing.",
                )
            if required_purpose not in meta.get("allowed_purposes", set()):
                raise SigningAuthorityError(
                    "SIGNING_KEY_NOT_AUTHORIZED",
                    f"Signing key '{clean_key_id}' is not authorized for purpose '{required_purpose}'.",
                )
        h = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256)
        return f"hmac-sha256:{clean_key_id}:{h.hexdigest()}"

    def get_active_key(self) -> Tuple[Optional[str], Optional[str]]:
        """Returns (active_key_id, active_secret)."""
        if self.is_key_revoked(self._active_key_id):
            return None, None
        meta = self._key_metadata.get(self._active_key_id)
        if meta and not meta.get("is_active_for_signing", False):
            return None, None
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
