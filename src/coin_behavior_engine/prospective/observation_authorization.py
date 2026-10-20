"""
Sprint 11.23.5A: Real-World Observation Authorization Framework
Defines cryptographic, capability-separated, revocable authorization tokens
for future prospective external observation pilots without activating them.
Enforces:
  1. Complete separation of OFFLINE_SIMULATION, READ_ONLY_EXTERNAL_OBSERVATION,
     and LIVE_ORDER_EXECUTION (permanently prohibited).
  2. Multi-parameter scope bounding (domains, event ID, time window, request count, byte volume).
  3. Cryptographic signature and revocation checking.
  4. Mandatory fail-closed validation: in Sprint 11.23.5A, all external collection is NOT_AUTHORIZED.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from .governance import TradingIsolationViolation


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


@dataclass
class ObservationAuthorizationToken:
    token_id: str
    capability: AuthorizationCapability
    operator_name: str
    issued_at_utc: str
    not_before_utc: str
    expires_at_utc: str
    authorized_event_id: str
    approved_domains: List[str]
    max_requests_allowed: int
    max_bytes_allowed: int
    signature_digest: str
    is_authorized: bool = False  # Strictly False in Sprint 11.23.5A
    is_revoked: bool = False
    revocation_id: Optional[str] = None
    revocation_reason: Optional[str] = None

    def compute_canonical_digest(self, secret_salt: str = "CBE_PROSPECTIVE_AUTH_SALT_V1") -> str:
        """Computes deterministic HMAC SHA-256 over canonical token payload."""
        payload = {
            "token_id": self.token_id,
            "capability": self.capability.value,
            "operator_name": self.operator_name,
            "issued_at_utc": self.issued_at_utc,
            "not_before_utc": self.not_before_utc,
            "expires_at_utc": self.expires_at_utc,
            "authorized_event_id": self.authorized_event_id,
            "approved_domains": sorted(self.approved_domains),
            "max_requests_allowed": self.max_requests_allowed,
            "max_bytes_allowed": self.max_bytes_allowed,
        }
        canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(secret_salt.encode("utf-8"), canonical_str.encode("utf-8"), hashlib.sha256).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["capability"] = self.capability.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ObservationAuthorizationToken:
        d = dict(data)
        d["capability"] = AuthorizationCapability(d["capability"])
        return cls(**d)


class ObservationAuthorizationEngine:
    """
    Evaluates and audits authorization tokens for prospective research.
    Guarantees that no external collection token can become active in Sprint 11.23.5A.
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
        secret_salt: str = "CBE_PROSPECTIVE_AUTH_SALT_V1",
    ) -> Tuple[bool, AuthorizationStatus, str]:
        """
        Validates token invariants fail-closed.
        Returns: (is_valid, status_code, message)
        """
        now = current_time_utc or datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

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

        # 4. Check explicit authorization flag (Fail closed in Sprint 11.23.5A)
        if not token.is_authorized:
            return False, AuthorizationStatus.NOT_AUTHORIZED, (
                f"Token {token.token_id} is marked NOT_AUTHORIZED (Operator authorization NOT granted in this sprint)"
            )

        # 5. Check cryptographic signature digest
        expected_digest = token.compute_canonical_digest(secret_salt=secret_salt)
        if token.signature_digest != expected_digest:
            return False, AuthorizationStatus.SIGNATURE_INVALID, "Cryptographic token signature digest mismatch."

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
        if requests_spent >= token.max_requests_allowed:
            return False, AuthorizationStatus.QUOTA_EXCEEDED, (
                f"Request quota exceeded: {requests_spent}/{token.max_requests_allowed}"
            )

        if bytes_spent >= token.max_bytes_allowed:
            return False, AuthorizationStatus.QUOTA_EXCEEDED, (
                f"Byte volume quota exceeded: {bytes_spent}/{token.max_bytes_allowed}"
            )

        return True, AuthorizationStatus.VALID, "Authorization validated successfully."
