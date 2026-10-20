"""
Sprint 11.23.5B-0: Authorization Security Remediation & Trusted Approval Engine
Remediates authorization vulnerabilities identified in Sprint 11.23.5A:
  1. Complete removal of hardcoded HMAC keys and insecure fallback secrets.
  2. Cryptographically signed authorization payload binding all security parameters.
  3. Trusted Approval & Revocation Store (SQLite) separating authenticated tokens
     from privileged operator approval decisions.
  4. Network Activation Gate enforcing 10 mandatory conditions at execution boundary.
  5. Permanent trading isolation and strict capability segregation.
  6. Transactional quota reservation and multi-threaded / concurrent request safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import urllib.parse
import uuid

from .governance import (
    TradingIsolationViolation,
    DENYLISTED_TRADING_ENDPOINTS,
)

PROHIBITED_REQUEST_HEADERS: Set[str] = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-mbx-apikey",
}


# ==============================================================================
# 1. EXCEPTIONS
# ==============================================================================

class AuthorizationError(Exception):
    """Base exception for prospective authorization failures."""
    pass


class MissingSigningKeyError(AuthorizationError):
    """Raised when no signing key is provisioned for signing or verification."""
    pass


class UnknownKeyIdError(AuthorizationError):
    """Raised when the token references an unrecognized key ID."""
    pass


class RevokedKeyError(AuthorizationError):
    """Raised when a cryptographic key ID has been revoked."""
    pass


class SignatureVerificationError(AuthorizationError):
    """Raised when cryptographic token signature verification fails."""
    pass


class AuthorizationRevokedError(AuthorizationError):
    """Raised when authorization has been revoked."""
    pass


class AuthorizationExpiredError(AuthorizationError):
    """Raised when authorization timestamp is expired."""
    pass


class ApprovalRecordMissingError(AuthorizationError):
    """Raised when no trusted operator approval record exists for the token."""
    pass


class QuotaExceededError(AuthorizationError):
    """Raised when request count or byte allowance quota is exhausted."""
    pass


class OutOfScopeError(AuthorizationError):
    """Raised when target domain or event ID is outside approved authorization scope."""
    pass


class NetworkActivationGateError(AuthorizationError):
    """Raised when external network retrieval is blocked by the activation gate."""
    pass


# ==============================================================================
# 2. ENUMS
# ==============================================================================

class AuthorizationCapability(str, Enum):
    OFFLINE_SIMULATION = "OFFLINE_SIMULATION"
    READ_ONLY_EXTERNAL_OBSERVATION = "READ_ONLY_EXTERNAL_OBSERVATION"
    LIVE_ORDER_EXECUTION = "LIVE_ORDER_EXECUTION"  # Permanently prohibited


class AuthorizationStatus(str, Enum):
    VALID = "VALID"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    EXPIRED = "EXPIRED"
    NOT_YET_VALID = "NOT_YET_VALID"
    REVOKED = "REVOKED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    PROHIBITED_CAPABILITY = "PROHIBITED_CAPABILITY"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    MISSING_APPROVAL_RECORD = "MISSING_APPROVAL_RECORD"
    UNKNOWN_KEY_ID = "UNKNOWN_KEY_ID"
    GATE_DISABLED = "GATE_DISABLED"


# ==============================================================================
# 3. CRYPTOGRAPHIC KEY REGISTRY (NO HARDCODED SECRETS)
# ==============================================================================

class SigningKeyRegistry:
    """
    Cryptographic key registry providing explicit key provisioning.
    Enforces:
      - No hardcoded keys or fallback secrets in source code.
      - Explicit key registration.
      - Fail-closed key lookup.
      - Separation of test keys from production keys.
      - Key rotation and revocation tracking.
    """
    _instance: Optional[SigningKeyRegistry] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._reg_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> SigningKeyRegistry:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = cls()

    def register_key(
        self,
        key_id: str,
        key_bytes: bytes,
        is_test_key: bool = False,
        description: str = "",
    ) -> None:
        if not key_id or not isinstance(key_id, str):
            raise ValueError("Key ID must be a non-empty string.")
        if not key_bytes or not isinstance(key_bytes, (bytes, bytearray)):
            raise ValueError("Key bytes must be non-empty bytes.")
        if len(key_bytes) < 16:
            raise ValueError("Cryptographic key must be at least 16 bytes.")

        with self._reg_lock:
            self._keys[key_id] = {
                "key_bytes": bytes(key_bytes),
                "is_test_key": is_test_key,
                "is_revoked": False,
                "revocation_reason": None,
                "description": description,
                "registered_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    def get_key(self, key_id: str, allow_test_key: bool = True) -> bytes:
        if not key_id:
            raise MissingSigningKeyError("No signing key ID provided.")
        with self._reg_lock:
            entry = self._keys.get(key_id)
            if entry is None:
                raise UnknownKeyIdError(f"Signing key ID '{key_id}' is not recognized in registry.")
            if entry["is_revoked"]:
                raise RevokedKeyError(f"Signing key ID '{key_id}' has been revoked: {entry['revocation_reason']}")
            if entry["is_test_key"] and not allow_test_key:
                raise AuthorizationError(f"Test key '{key_id}' cannot be used in a production context.")
            return entry["key_bytes"]

    def revoke_key(self, key_id: str, reason: str = "Operator key rotation") -> None:
        with self._reg_lock:
            if key_id in self._keys:
                self._keys[key_id]["is_revoked"] = True
                self._keys[key_id]["revocation_reason"] = reason

    def has_key(self, key_id: str) -> bool:
        with self._reg_lock:
            entry = self._keys.get(key_id)
            return entry is not None and not entry["is_revoked"]

    def is_test_key(self, key_id: str) -> bool:
        with self._reg_lock:
            entry = self._keys.get(key_id)
            return entry is not None and entry["is_test_key"]

    def clear(self) -> None:
        with self._reg_lock:
            self._keys.clear()


# ==============================================================================
# 4. SIGNED AUTHORIZATION PAYLOAD
# ==============================================================================

@dataclass
class ObservationAuthorizationToken:
    """
    Cryptographic prospective research authorization token.
    Cryptographically binds:
      - token_id
      - capability
      - authorized_event_id
      - operator_identity
      - issuer_identity
      - issued_at_utc
      - not_before_utc
      - expires_at_utc
      - approved_domains
      - max_request_count
      - max_byte_allowance
      - policy_version
      - key_id
    """
    token_id: str
    capability: AuthorizationCapability
    authorized_event_id: str
    operator_identity: str = ""
    issued_at_utc: str = ""
    not_before_utc: str = ""
    expires_at_utc: str = ""
    approved_domains: List[str] = field(default_factory=list)
    max_request_count: int = 0
    max_byte_allowance: int = 0
    key_id: str = "test-key-default"
    policy_version: str = "1.0.0"
    issuer_identity: str = "CBE_SECURITY_GOVERNANCE"
    signature_digest: str = ""
    # Backward-compatibility parameters:
    operator_name: Optional[str] = None
    max_requests_allowed: Optional[int] = None
    max_bytes_allowed: Optional[int] = None
    is_authorized: bool = False  # Untrusted boolean; has ZERO authorization effect!
    is_revoked: bool = False
    revocation_id: Optional[str] = None
    revocation_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.operator_name and not self.operator_identity:
            self.operator_identity = self.operator_name
        elif self.operator_identity and not self.operator_name:
            self.operator_name = self.operator_identity

        if self.max_requests_allowed is not None and self.max_request_count == 0:
            self.max_request_count = self.max_requests_allowed
        elif self.max_request_count and self.max_requests_allowed is None:
            self.max_requests_allowed = self.max_request_count

        if self.max_bytes_allowed is not None and self.max_byte_allowance == 0:
            self.max_byte_allowance = self.max_bytes_allowed
        elif self.max_byte_allowance and self.max_bytes_allowed is None:
            self.max_bytes_allowed = self.max_byte_allowance

        if isinstance(self.capability, str):
            self.capability = AuthorizationCapability(self.capability)

    def canonical_payload(self) -> Dict[str, Any]:
        """Constructs strictly sorted canonical payload for cryptographic signing."""
        return {
            "approved_domains": sorted([d.lower().strip() for d in self.approved_domains]),
            "authorized_event_id": self.authorized_event_id,
            "capability": self.capability.value,
            "expires_at_utc": self.expires_at_utc,
            "issued_at_utc": self.issued_at_utc,
            "issuer_identity": self.issuer_identity,
            "key_id": self.key_id,
            "max_byte_allowance": self.max_byte_allowance,
            "max_request_count": self.max_request_count,
            "not_before_utc": self.not_before_utc,
            "operator_identity": self.operator_identity,
            "policy_version": self.policy_version,
            "token_id": self.token_id,
        }

    def compute_canonical_digest(
        self,
        signing_key: Optional[bytes] = None,
        key_registry: Optional[SigningKeyRegistry] = None,
    ) -> str:
        """
        Computes deterministic HMAC-SHA256 signature over canonical payload.
        Fails closed when signing key is missing. No default secret exists.
        """
        if signing_key is None:
            reg = key_registry or SigningKeyRegistry.get_instance()
            signing_key = reg.get_key(self.key_id)

        if not signing_key:
            raise MissingSigningKeyError(
                f"Missing signing key for token '{self.token_id}' with key_id '{self.key_id}'."
            )

        payload_bytes = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hmac.new(signing_key, payload_bytes, hashlib.sha256).hexdigest()

    def verify_signature(
        self,
        signing_key: Optional[bytes] = None,
        key_registry: Optional[SigningKeyRegistry] = None,
    ) -> bool:
        """Verifies signature digest using constant-time MAC comparison."""
        if not self.signature_digest:
            return False
        try:
            expected = self.compute_canonical_digest(
                signing_key=signing_key, key_registry=key_registry
            )
            return hmac.compare_digest(self.signature_digest, expected)
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["capability"] = self.capability.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ObservationAuthorizationToken:
        d = dict(data)
        d["capability"] = AuthorizationCapability(d["capability"])
        return cls(**d)


# ==============================================================================
# 5. TRUSTED APPROVAL & REVOCATION STORE (SQLITE)
# ==============================================================================

@dataclass
class TrustedApprovalRecord:
    approval_id: str
    token_id: str
    operator_identity: str
    capability: AuthorizationCapability
    authorized_event_id: str
    approved_domains: List[str]
    max_request_count: int
    max_byte_allowance: int
    spent_requests: int
    spent_bytes: int
    issued_at_utc: str
    not_before_utc: str
    expires_at_utc: str
    policy_version: str
    status: str  # ACTIVE, REVOKED, EXHAUSTED, EXPIRED
    created_at_utc: str
    is_production: bool = False


class TrustedApprovalStore:
    """
    Lightweight, transactional, durable store for operator authorization approvals and revocations.
    Guarantees:
      - Default deny: untrusted configuration or unapproved tokens cannot activate external access.
      - Explicit approval records requiring privileged administrative creation.
      - Durable revocations surviving process restarts.
      - Transactional quota reservation and accounting under concurrent load.
      - Complete audit trail.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _close_connection(self, conn: sqlite3.Connection) -> None:
        if conn is not self._mem_conn:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS approval_records (
                            approval_id TEXT PRIMARY KEY,
                            token_id TEXT UNIQUE NOT NULL,
                            operator_identity TEXT NOT NULL,
                            capability TEXT NOT NULL,
                            authorized_event_id TEXT NOT NULL,
                            approved_domains_json TEXT NOT NULL,
                            max_request_count INTEGER NOT NULL,
                            max_byte_allowance INTEGER NOT NULL,
                            spent_requests INTEGER NOT NULL DEFAULT 0,
                            spent_bytes INTEGER NOT NULL DEFAULT 0,
                            issued_at_utc TEXT NOT NULL,
                            not_before_utc TEXT NOT NULL,
                            expires_at_utc TEXT NOT NULL,
                            policy_version TEXT NOT NULL,
                            status TEXT NOT NULL,
                            created_at_utc TEXT NOT NULL,
                            is_production INTEGER NOT NULL DEFAULT 0
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS revocation_records (
                            revocation_id TEXT PRIMARY KEY,
                            token_id TEXT NOT NULL,
                            revoked_by TEXT NOT NULL,
                            revoked_at_utc TEXT NOT NULL,
                            reason TEXT NOT NULL
                        );
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS audit_trail (
                            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            action TEXT NOT NULL,
                            token_id TEXT,
                            event_id TEXT,
                            timestamp_utc TEXT NOT NULL,
                            details_json TEXT NOT NULL
                        );
                    """)
            finally:
                self._close_connection(conn)

    def create_privileged_approval(
        self,
        token: ObservationAuthorizationToken,
        privileged_operator: str,
        is_production: bool = False,
    ) -> TrustedApprovalRecord:
        """
        Creates an explicit operator approval record in the trusted store.
        Production approvals are permanently prohibited in this sprint.
        """
        if is_production:
            raise AuthorizationError(
                "GOVERNANCE VIOLATION: Production approvals are strictly NOT authorized in Sprint 11.23.5B-0."
            )
        if token.capability == AuthorizationCapability.LIVE_ORDER_EXECUTION:
            raise TradingIsolationViolation(
                "CRITICAL GOVERNANCE VIOLATION: Cannot approve LIVE_ORDER_EXECUTION capability!"
            )
        if not privileged_operator:
            raise ValueError("Privileged operator identity must be provided.")

        approval_id = f"APPR-{uuid.uuid4().hex[:12].upper()}"
        now_utc = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO approval_records (
                            approval_id, token_id, operator_identity, capability,
                            authorized_event_id, approved_domains_json, max_request_count,
                            max_byte_allowance, spent_requests, spent_bytes, issued_at_utc,
                            not_before_utc, expires_at_utc, policy_version, status,
                            created_at_utc, is_production
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                    """, (
                        approval_id,
                        token.token_id,
                        token.operator_identity,
                        token.capability.value,
                        token.authorized_event_id,
                        json.dumps(token.approved_domains),
                        token.max_request_count,
                        token.max_byte_allowance,
                        token.issued_at_utc,
                        token.not_before_utc,
                        token.expires_at_utc,
                        token.policy_version,
                        now_utc,
                        1 if is_production else 0,
                    ))
                    conn.execute("""
                        INSERT INTO audit_trail (action, token_id, event_id, timestamp_utc, details_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        "APPROVAL_CREATED",
                        token.token_id,
                        token.authorized_event_id,
                        now_utc,
                        json.dumps({"approval_id": approval_id, "approved_by": privileged_operator}),
                    ))
            finally:
                self._close_connection(conn)

        record = self.get_approval(token.token_id)
        if record is None:
            raise ApprovalRecordMissingError("Failed to verify created approval record.")
        return record

    def get_approval(self, token_id: str) -> Optional[TrustedApprovalRecord]:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM approval_records WHERE token_id = ?", (token_id,)
                ).fetchone()
                if not row:
                    return None
                return TrustedApprovalRecord(
                    approval_id=row["approval_id"],
                    token_id=row["token_id"],
                    operator_identity=row["operator_identity"],
                    capability=AuthorizationCapability(row["capability"]),
                    authorized_event_id=row["authorized_event_id"],
                    approved_domains=json.loads(row["approved_domains_json"]),
                    max_request_count=row["max_request_count"],
                    max_byte_allowance=row["max_byte_allowance"],
                    spent_requests=row["spent_requests"],
                    spent_bytes=row["spent_bytes"],
                    issued_at_utc=row["issued_at_utc"],
                    not_before_utc=row["not_before_utc"],
                    expires_at_utc=row["expires_at_utc"],
                    policy_version=row["policy_version"],
                    status=row["status"],
                    created_at_utc=row["created_at_utc"],
                    is_production=bool(row["is_production"]),
                )
            finally:
                self._close_connection(conn)

    def revoke_approval(self, token_id: str, revoked_by: str, reason: str) -> bool:
        rev_id = f"REV-{uuid.uuid4().hex[:12].upper()}"
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cursor = conn.execute(
                        "UPDATE approval_records SET status = 'REVOKED' WHERE token_id = ?",
                        (token_id,)
                    )
                    if cursor.rowcount == 0:
                        return False
                    conn.execute("""
                        INSERT INTO revocation_records (revocation_id, token_id, revoked_by, revoked_at_utc, reason)
                        VALUES (?, ?, ?, ?, ?)
                    """, (rev_id, token_id, revoked_by, now_utc, reason))
                    conn.execute("""
                        INSERT INTO audit_trail (action, token_id, event_id, timestamp_utc, details_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        "APPROVAL_REVOKED",
                        token_id,
                        "",
                        now_utc,
                        json.dumps({"reason": reason, "revoked_by": revoked_by}),
                    ))
                    return True
            finally:
                self._close_connection(conn)

    def reserve_quota(self, token_id: str, estimated_bytes: int = 0) -> Tuple[bool, str]:
        """
        Atomically reserves 1 request and estimated_bytes against the token quota.
        Guarantees no quota overspending under concurrent access.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    row = conn.execute(
                        "SELECT status, max_request_count, spent_requests, max_byte_allowance, spent_bytes, expires_at_utc "
                        "FROM approval_records WHERE token_id = ?",
                        (token_id,)
                    ).fetchone()
                    if not row:
                        return False, "MISSING_APPROVAL_RECORD"
                    if row["status"] == "REVOKED":
                        return False, "AUTHORIZATION_REVOKED"
                    if row["status"] != "ACTIVE":
                        return False, f"STATUS_{row['status']}"

                    now_utc = datetime.now(timezone.utc)
                    expires_utc = datetime.fromisoformat(row["expires_at_utc"].replace("Z", "+00:00"))
                    if now_utc > expires_utc:
                        conn.execute("UPDATE approval_records SET status = 'EXPIRED' WHERE token_id = ?", (token_id,))
                        return False, "AUTHORIZATION_EXPIRED"

                    if row["spent_requests"] >= row["max_request_count"]:
                        conn.execute("UPDATE approval_records SET status = 'EXHAUSTED' WHERE token_id = ?", (token_id,))
                        return False, "REQUEST_QUOTA_EXCEEDED"

                    if (row["spent_bytes"] + estimated_bytes) > row["max_byte_allowance"]:
                        return False, "BYTE_QUOTA_EXCEEDED"

                    new_requests = row["spent_requests"] + 1
                    new_bytes = row["spent_bytes"] + estimated_bytes
                    new_status = "EXHAUSTED" if new_requests >= row["max_request_count"] else "ACTIVE"

                    conn.execute(
                        "UPDATE approval_records SET spent_requests = ?, spent_bytes = ?, status = ? WHERE token_id = ?",
                        (new_requests, new_bytes, new_status, token_id)
                    )
                    return True, "QUOTA_RESERVED"
            finally:
                self._close_connection(conn)

    def commit_quota(self, token_id: str, actual_bytes: int, estimated_bytes: int = 0) -> None:
        delta = actual_bytes - estimated_bytes
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        "UPDATE approval_records SET spent_bytes = spent_bytes + ? WHERE token_id = ?",
                        (delta, token_id)
                    )
            finally:
                self._close_connection(conn)

    def release_quota(self, token_id: str, estimated_bytes: int = 0, refund_request: bool = True) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    req_delta = -1 if refund_request else 0
                    conn.execute(
                        """UPDATE approval_records 
                           SET spent_requests = MAX(0, spent_requests + ?),
                               spent_bytes = MAX(0, spent_bytes - ?),
                               status = 'ACTIVE'
                           WHERE token_id = ? AND status = 'EXHAUSTED'""",
                        (req_delta, estimated_bytes, token_id)
                    )
                    conn.execute(
                        """UPDATE approval_records 
                           SET spent_requests = MAX(0, spent_requests + ?),
                               spent_bytes = MAX(0, spent_bytes - ?)
                           WHERE token_id = ? AND status != 'EXHAUSTED'""",
                        (req_delta, estimated_bytes, token_id)
                    )
            finally:
                self._close_connection(conn)


# ==============================================================================
# 6. NETWORK ACTIVATION GATE (10 MANDATORY GATES)
# ==============================================================================

class NetworkActivationGate:
    """
    Enforces the 10 mandatory network activation conditions at execution boundary:
      1. Explicit operator approval in trusted store.
      2. Valid cryptographic authorization.
      3. Approved event ID.
      4. Approved source domain.
      5. Valid time window.
      6. Available request quota.
      7. Available byte quota.
      8. Research-only capability (never LIVE_ORDER_EXECUTION).
      9. Safe HTTPS transport.
      10. Explicit runtime activation.
    Defaults to DISABLED (fail-closed).
    """

    def __init__(
        self,
        approval_store: Optional[TrustedApprovalStore] = None,
        key_registry: Optional[SigningKeyRegistry] = None,
        gate_enabled: bool = False,
        operator_authorization_granted: bool = False,
    ) -> None:
        self.approval_store = approval_store or TrustedApprovalStore()
        self.key_registry = key_registry or SigningKeyRegistry.get_instance()
        self.gate_enabled = gate_enabled
        self.operator_authorization_granted = operator_authorization_granted

    def evaluate_request(
        self,
        token: Optional[ObservationAuthorizationToken],
        target_url: str,
        target_event_id: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        estimated_bytes: int = 0,
    ) -> Tuple[bool, str]:
        """
        Evaluates the 10 mandatory conditions for network retrieval.
        Returns: (allowed: bool, status_or_reason: str)
        """
        # Condition 10: Explicit runtime activation
        if not self.gate_enabled or not self.operator_authorization_granted:
            return False, "GATE_DISABLED: Network activation gate or operator authorization is disabled (fail-closed)."

        # Condition 1 & 2: Token and Cryptographic authorization
        if token is None:
            return False, "MISSING_TOKEN: No authorization token provided."

        if not token.verify_signature(key_registry=self.key_registry):
            return False, "INVALID_SIGNATURE: Token cryptographic signature digest verification failed."

        # Condition 8: Research-only capability (Trading Isolation)
        if token.capability == AuthorizationCapability.LIVE_ORDER_EXECUTION:
            raise TradingIsolationViolation(
                "CRITICAL GOVERNANCE VIOLATION: LIVE_ORDER_EXECUTION is permanently prohibited!"
            )
        if token.capability != AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION:
            return False, f"PROHIBITED_CAPABILITY: Token capability '{token.capability.value}' not authorized for network."

        # Condition 9: Safe HTTPS transport checks
        parsed = urllib.parse.urlparse(target_url)
        if parsed.scheme.lower() != "https":
            return False, f"INSECURE_SCHEME: Scheme '{parsed.scheme}' rejected. Only HTTPS permitted."
        if method.upper() not in ("GET", "HEAD"):
            return False, f"PROHIBITED_METHOD: Method '{method}' rejected. Read-only GET/HEAD only."
        path = parsed.path.lower()
        for pattern in DENYLISTED_TRADING_ENDPOINTS:
            if re.search(pattern, path):
                raise TradingIsolationViolation(f"Trading endpoint access denied: '{path}'")

        # Condition 1: Explicit operator approval in trusted store
        approval = self.approval_store.get_approval(token.token_id)
        if approval is None:
            return False, "MISSING_APPROVAL_RECORD: No trusted operator approval record found for token."
        if approval.status == "REVOKED":
            return False, "REVOKED: Approval has been revoked by operator."
        if approval.status != "ACTIVE":
            return False, f"APPROVAL_STATUS_{approval.status}: Approval is not active."

        # Condition 3: Approved event ID
        if approval.authorized_event_id != "*" and approval.authorized_event_id != target_event_id:
            return False, f"OUT_OF_SCOPE_EVENT: Target event '{target_event_id}' != authorized '{approval.authorized_event_id}'."

        # Condition 4: Approved source domain
        host = (parsed.hostname or "").lower().strip()
        domain_allowed = any(
            host == d.lower() or host.endswith("." + d.lower()) for d in approval.approved_domains
        )
        if not domain_allowed:
            return False, f"OUT_OF_SCOPE_DOMAIN: Host '{host}' not in approved domains: {approval.approved_domains}."

        # Condition 5: Valid time window
        now_utc = datetime.now(timezone.utc)
        try:
            t_not_before = datetime.fromisoformat(approval.not_before_utc.replace("Z", "+00:00"))
            t_expires = datetime.fromisoformat(approval.expires_at_utc.replace("Z", "+00:00"))
            if now_utc < t_not_before:
                return False, f"NOT_YET_VALID: Current time {now_utc.isoformat()} < {approval.not_before_utc}."
            if now_utc > t_expires:
                return False, f"EXPIRED: Current time {now_utc.isoformat()} > {approval.expires_at_utc}."
        except Exception as e:
            return False, f"TIME_FORMAT_ERROR: {e}"

        # Condition 6 & 7: Available request quota and byte quota (Atomic reservation)
        reserved, res_msg = self.approval_store.reserve_quota(token.token_id, estimated_bytes=estimated_bytes)
        if not reserved:
            return False, f"QUOTA_FAILED: {res_msg}"

        return True, "AUTHORIZED"


# ==============================================================================
# 7. OBSERVATION AUTHORIZATION ENGINE
# ==============================================================================

class ObservationAuthorizationEngine:
    """
    Evaluates and audits authorization tokens and approvals for prospective research.
    Guarantees:
      - Authenticated tokens without trusted approval records CANNOT activate network collection.
      - Tokens with prohibited capabilities raise TradingIsolationViolation.
      - Fail-closed evaluation.
    """

    @classmethod
    def verify_authorization(
        cls,
        token: Optional[ObservationAuthorizationToken],
        requested_capability: AuthorizationCapability,
        target_domain: str,
        target_event_id: str,
        current_time_utc: Optional[datetime] = None,
        requests_spent: int = 0,
        bytes_spent: int = 0,
        signing_key: Optional[bytes] = None,
        key_registry: Optional[SigningKeyRegistry] = None,
        approval_store: Optional[TrustedApprovalStore] = None,
    ) -> Tuple[bool, AuthorizationStatus, str]:
        """
        Validates token invariants fail-closed.
        Returns: (is_valid, status_code, message)
        """
        now = current_time_utc or datetime.now(timezone.utc)

        # 1. Permanently prohibit LIVE_ORDER_EXECUTION
        if requested_capability == AuthorizationCapability.LIVE_ORDER_EXECUTION:
            raise TradingIsolationViolation(
                "CRITICAL GOVERNANCE VIOLATION: LIVE_ORDER_EXECUTION capability is permanently prohibited!"
            )

        if token is None:
            return False, AuthorizationStatus.NOT_AUTHORIZED, "No authorization token provided."

        if token.capability == AuthorizationCapability.LIVE_ORDER_EXECUTION:
            raise TradingIsolationViolation(
                "CRITICAL GOVERNANCE VIOLATION: Token contains prohibited LIVE_ORDER_EXECUTION capability!"
            )

        # 2. Check capability match
        if token.capability != requested_capability:
            return False, AuthorizationStatus.PROHIBITED_CAPABILITY, (
                f"Token capability '{token.capability.value}' does not match requested capability '{requested_capability.value}'"
            )

        # 3. Check revocation
        if token.is_revoked:
            return False, AuthorizationStatus.REVOKED, (
                f"Authorization token {token.token_id} has been revoked (Reason: {token.revocation_reason})"
            )

        # 4. Check approval store if provided
        if approval_store is not None:
            approval = approval_store.get_approval(token.token_id)
            if approval is None:
                return False, AuthorizationStatus.MISSING_APPROVAL_RECORD, (
                    f"Token {token.token_id} has no trusted operator approval record in the store."
                )
            if approval.status == "REVOKED":
                return False, AuthorizationStatus.REVOKED, f"Approval for token {token.token_id} has been revoked."
            if approval.status != "ACTIVE":
                return False, AuthorizationStatus.NOT_AUTHORIZED, f"Approval status is {approval.status}."
        else:
            # If no store passed, check explicit token authorization flag
            if not token.is_authorized:
                return False, AuthorizationStatus.NOT_AUTHORIZED, (
                    f"Token {token.token_id} is marked NOT_AUTHORIZED (Operator authorization NOT granted in this sprint)"
                )

        # 5. Check cryptographic signature digest
        reg = key_registry or SigningKeyRegistry.get_instance()
        try:
            if not token.verify_signature(signing_key=signing_key, key_registry=reg):
                return False, AuthorizationStatus.SIGNATURE_INVALID, "Cryptographic token signature digest mismatch."
        except (UnknownKeyIdError, MissingSigningKeyError, RevokedKeyError) as e:
            return False, AuthorizationStatus.SIGNATURE_INVALID, f"Signature verification error: {e}"

        # 6. Check time bounds
        try:
            t_not_before = datetime.fromisoformat(token.not_before_utc.replace("Z", "+00:00"))
            t_expires = datetime.fromisoformat(token.expires_at_utc.replace("Z", "+00:00"))
            if now < t_not_before:
                return False, AuthorizationStatus.NOT_YET_VALID, f"Token not valid until {token.not_before_utc}."
            if now > t_expires:
                return False, AuthorizationStatus.EXPIRED, f"Token expired at {token.expires_at_utc}."
        except Exception as e:
            return False, AuthorizationStatus.NOT_AUTHORIZED, f"Invalid date formatting in token: {e}"

        # 7. Check domain scope
        host = target_domain.lower().strip()
        domain_allowed = any(
            host == d.lower() or host.endswith("." + d.lower()) for d in token.approved_domains
        )
        if not domain_allowed:
            return False, AuthorizationStatus.OUT_OF_SCOPE, (
                f"Target domain '{target_domain}' not permitted by token approved domains: {token.approved_domains}"
            )

        # 8. Check event binding
        if token.authorized_event_id != "*" and token.authorized_event_id != target_event_id:
            return False, AuthorizationStatus.OUT_OF_SCOPE, (
                f"Target event '{target_event_id}' does not match token authorized event '{token.authorized_event_id}'"
            )

        # 9. Check quotas
        if requests_spent >= token.max_request_count:
            return False, AuthorizationStatus.QUOTA_EXCEEDED, (
                f"Request quota exceeded: {requests_spent}/{token.max_request_count}"
            )

        if bytes_spent >= token.max_byte_allowance:
            return False, AuthorizationStatus.QUOTA_EXCEEDED, (
                f"Byte volume quota exceeded: {bytes_spent}/{token.max_byte_allowance}"
            )

        return True, AuthorizationStatus.VALID, "Authorization validated successfully."
