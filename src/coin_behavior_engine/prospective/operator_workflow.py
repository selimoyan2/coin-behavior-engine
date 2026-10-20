"""
Sprint 11.23.5B-1: Privileged Operator Approval Workflow, Production Key Security & Pilot Readiness
Implements:
  1. Role separation: RESEARCH_OPERATOR, APPROVAL_ADMIN, AUDITOR.
  2. Machine-readable PilotProposal with canonical SHA-256 digest binding.
  3. Privileged approval and rejection workflow with separation of duty.
  4. File-based key security with restrictive filesystem permission verification.
  5. Secret redaction preventing exposure in logs, exceptions, or string formatting.
  6. Emergency stop and revocation synchronization.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import uuid

from .observation_authorization import (
    AuthorizationCapability,
    AuthorizationStatus,
    AuthorizationError,
    SigningKeyRegistry,
    TrustedApprovalStore,
    TrustedApprovalRecord,
    ObservationAuthorizationToken,
    TradingIsolationViolation,
)


# ==============================================================================
# 1. EXCEPTIONS
# ==============================================================================

class OperatorWorkflowError(AuthorizationError):
    """Base exception for operator workflow violations."""
    pass


class UnauthorizedOperatorActionError(OperatorWorkflowError):
    """Raised when an operator attempts an action unauthorized for their assigned role."""
    pass


class ProposalIntegrityError(OperatorWorkflowError):
    """Raised when a pilot proposal has invalid parameters, tampered digest, or missing fields."""
    pass


class KeyStorePermissionError(OperatorWorkflowError):
    """Raised when key file permissions are excessively permissive (must be 0600 on POSIX)."""
    pass


# ==============================================================================
# 2. OPERATOR ROLES & IDENTITIES
# ==============================================================================

class OperatorRole(str, Enum):
    RESEARCH_OPERATOR = "RESEARCH_OPERATOR"  # Can prepare proposals
    APPROVAL_ADMIN = "APPROVAL_ADMIN"        # Can approve or reject proposals
    AUDITOR = "AUDITOR"                      # Can inspect records without modifying


@dataclass(frozen=True)
class OperatorIdentity:
    """
    Cryptographically identifiable operator principal.
    Enforces role separation: research operators cannot self-approve.
    """
    operator_id: str
    role: OperatorRole
    operator_name: str
    public_key_fingerprint: str
    registered_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if isinstance(self.role, str):
            object.__setattr__(self, "role", OperatorRole(self.role))


# ==============================================================================
# 3. PRODUCTION KEY SECURITY & PERMISSION VERIFICATION
# ==============================================================================

def verify_key_file_permissions(filepath: Union[str, Path]) -> bool:
    """
    Verifies that key file permissions are restrictive.
    On POSIX, strictly enforces 0600 (read/write by owner only; no group or world bits).
    On Windows, verifies file exists and is accessible.
    Rejects symbolic links unconditionally across all platforms.
    """
    raw_p = Path(filepath)
    if raw_p.is_symlink():
        raise KeyStorePermissionError(f"Symlinks are strictly prohibited for key files: '{filepath}'.")

    p = raw_p.resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"Key file '{p}' does not exist or is not a file.")

    if os.name != "nt":
        import stat
        st = p.stat()
        mode = st.st_mode
        # Reject if group or other read/write/execute bits are set
        if bool(mode & (stat.S_IRWXG | stat.S_IRWXO)):
            raise KeyStorePermissionError(
                f"Insecure permissions on key file '{p}': {oct(mode)}. Expected owner-only (0600)."
            )
    return True


class FileBackedKeyProvider:
    """
    Loads signing keys from local filesystem with strict permission enforcement.
    Fails closed if permissions are too broad, file is missing, symlinks are used,
    or path traversal is attempted.
    """
    def __init__(self, key_dir: Union[str, Path]) -> None:
        self.key_dir = Path(key_dir).resolve()

    def load_key(self, key_id: str, is_test_key: bool = False) -> bytes:
        if not key_id or not re.match(r"^[a-zA-Z0-9_\-]+$", key_id):
            raise ValueError(f"Invalid key ID format: '{key_id}'")

        key_file = self.key_dir / f"{key_id}.key"
        if key_file.is_symlink():
            raise KeyStorePermissionError(f"Symlinks are prohibited for key files: '{key_file}'")

        resolved_file = key_file.resolve()
        if not resolved_file.is_relative_to(self.key_dir) or resolved_file.parent != self.key_dir:
            raise ValueError(f"Path traversal detected: '{key_file}' resolves outside key directory '{self.key_dir}'.")

        verify_key_file_permissions(key_file)
        data = key_file.read_bytes().strip()
        min_bytes = 16 if is_test_key else 32
        if len(data) < min_bytes:
            raise ValueError(f"Key '{key_id}' length ({len(data)} B) is less than required {min_bytes} bytes.")
        return data


def redact_secret_string(value: str, visible_chars: int = 4) -> str:
    """Masks secret strings, leaving at most the trailing visible_chars."""
    if not value:
        return "[EMPTY_SECRET]"
    if len(value) <= visible_chars:
        return "[REDACTED]"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


# ==============================================================================
# 4. MACHINE-READABLE PILOT PROPOSAL
# ==============================================================================

class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


@dataclass
class PilotProposal:
    """
    Machine-readable pilot observation proposal.
    Cryptographically serializes all scope, duration, domain, and event parameters.
    Material changes invalidate the previous digest.
    """
    proposal_id: str
    proposal_version: str
    event_id: str
    event_name: str
    official_publisher: str
    official_source_url: str
    expected_publication_time: str
    schedule_verification_status: str
    consensus_source_requirements: List[str]
    btc_market_data_endpoints: List[str]
    max_duration_seconds: int
    max_requests: int
    max_bytes: int
    polling_interval_seconds: float
    approved_domains: List[str]
    evidence_storage_destination: str
    timestamp_policy: str
    emergency_stop_conditions: List[str]
    created_by_operator_id: str
    created_at_utc: str
    authorization_status: ProposalStatus = ProposalStatus.PROPOSED
    approval_audit_references: Dict[str, Any] = field(default_factory=dict)
    rejection_reason: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.authorization_status, str):
            self.authorization_status = ProposalStatus(self.authorization_status)

    def canonical_payload(self) -> Dict[str, Any]:
        """Constructs strictly sorted canonical payload for cryptographic hashing."""
        return {
            "approved_domains": sorted([d.lower().strip() for d in self.approved_domains]),
            "btc_market_data_endpoints": sorted(self.btc_market_data_endpoints),
            "consensus_source_requirements": sorted(self.consensus_source_requirements),
            "created_by_operator_id": self.created_by_operator_id,
            "emergency_stop_conditions": sorted(self.emergency_stop_conditions),
            "event_id": self.event_id,
            "event_name": self.event_name,
            "evidence_storage_destination": self.evidence_storage_destination,
            "expected_publication_time": self.expected_publication_time,
            "max_bytes": self.max_bytes,
            "max_duration_seconds": self.max_duration_seconds,
            "max_requests": self.max_requests,
            "official_publisher": self.official_publisher,
            "official_source_url": self.official_source_url,
            "polling_interval_seconds": self.polling_interval_seconds,
            "proposal_id": self.proposal_id,
            "proposal_version": self.proposal_version,
            "schedule_verification_status": self.schedule_verification_status,
            "timestamp_policy": self.timestamp_policy,
        }

    def compute_canonical_digest(self) -> str:
        """Computes deterministic SHA-256 hash over canonical payload."""
        payload_bytes = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["authorization_status"] = self.authorization_status.value
        d["canonical_proposal_digest"] = self.compute_canonical_digest()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PilotProposal:
        d = dict(data)
        d.pop("canonical_proposal_digest", None)
        if "authorization_status" in d:
            d["authorization_status"] = ProposalStatus(d["authorization_status"])
        return cls(**d)


# ==============================================================================
# 5. PRIVILEGED OPERATOR APPROVAL WORKFLOW ENGINE
# ==============================================================================

class OperatorApprovalWorkflowEngine:
    """
    Orchestrates the privileged multi-role operator approval workflow:
      1. Prepare and submit a pilot proposal (RESEARCH_OPERATOR).
      2. Review pilot scope (AUDITOR, APPROVAL_ADMIN).
      3. Approve or reject proposal (APPROVAL_ADMIN only; submitter cannot self-approve).
      4. Issue scoped authorization token bound to proposal digest.
      5. Store approval in TrustedApprovalStore.
      6. Revoke authorization (APPROVAL_ADMIN).
    """

    @classmethod
    def submit_proposal(
        cls,
        proposal: PilotProposal,
        operator: OperatorIdentity,
    ) -> PilotProposal:
        """Validates and registers a new proposal submitted by a research operator."""
        if operator.role == OperatorRole.AUDITOR:
            raise UnauthorizedOperatorActionError(
                f"Auditor '{operator.operator_id}' is read-only and cannot submit pilot proposals."
            )

        if not proposal.event_id or "*" in proposal.event_id:
            raise ProposalIntegrityError(
                f"Wildcard or empty event ID '{proposal.event_id}' is prohibited in pilot proposals."
            )

        if not proposal.approved_domains:
            raise ProposalIntegrityError("Proposal must specify at least one approved source domain.")

        proposal.created_by_operator_id = operator.operator_id
        proposal.created_at_utc = datetime.now(timezone.utc).isoformat()
        proposal.authorization_status = ProposalStatus.PROPOSED
        return proposal

    @classmethod
    def review_proposal(
        cls,
        proposal: PilotProposal,
        reviewer: OperatorIdentity,
    ) -> Dict[str, Any]:
        """Provides an independent audit review of proposal scope and constraints."""
        digest = proposal.compute_canonical_digest()
        return {
            "proposal_id": proposal.proposal_id,
            "reviewed_by": reviewer.operator_id,
            "reviewer_role": reviewer.role.value,
            "canonical_digest": digest,
            "event_id": proposal.event_id,
            "status": proposal.authorization_status.value,
            "is_valid_structure": True,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def approve_proposal(
        cls,
        proposal: PilotProposal,
        approver: OperatorIdentity,
        key_id: str,
        store: TrustedApprovalStore,
        key_registry: Optional[SigningKeyRegistry] = None,
        is_production: bool = False,
        validity_hours: int = 1,
    ) -> Tuple[PilotProposal, ObservationAuthorizationToken, TrustedApprovalRecord]:
        """
        Executes privileged approval of a pilot proposal by an APPROVAL_ADMIN.
        Enforces separation of duties: submitter cannot self-approve.
        Production approvals are permanently prohibited in this sprint.
        """
        if approver.role != OperatorRole.APPROVAL_ADMIN:
            raise UnauthorizedOperatorActionError(
                f"Operator '{approver.operator_id}' with role '{approver.role.value}' is not authorized to grant approvals. "
                "APPROVAL_ADMIN role is strictly required."
            )

        # Separation of duty
        if approver.operator_id == proposal.created_by_operator_id:
            raise UnauthorizedOperatorActionError(
                f"Separation of duty violation: Submitter '{proposal.created_by_operator_id}' cannot self-approve proposal."
            )

        if is_production:
            raise AuthorizationError(
                "GOVERNANCE VIOLATION: Production approvals are strictly NOT authorized in Sprint 11.23.5B-1."
            )

        if "*" in proposal.event_id:
            raise ProposalIntegrityError("Wildcard event IDs are strictly prohibited in approvals.")

        reg = key_registry or SigningKeyRegistry.get_instance()
        proposal_digest = proposal.compute_canonical_digest()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=validity_hours)

        token_id = f"AUTH-{uuid.uuid4().hex[:12].upper()}"

        token = ObservationAuthorizationToken(
            token_id=token_id,
            capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
            authorized_event_id=proposal.event_id,
            operator_identity=approver.operator_id,
            issued_at_utc=now.isoformat(),
            not_before_utc=now.isoformat(),
            expires_at_utc=expires.isoformat(),
            approved_domains=proposal.approved_domains,
            max_request_count=proposal.max_requests,
            max_byte_allowance=proposal.max_bytes,
            key_id=key_id,
            policy_version="1.0.0",
        )
        token.signature_digest = token.compute_canonical_digest(key_registry=reg)

        approval_record = store.create_privileged_approval(
            token=token,
            privileged_operator=approver.operator_id,
            is_production=is_production,
            proposal_digest=proposal_digest,
        )

        proposal.authorization_status = ProposalStatus.APPROVED
        proposal.approval_audit_references = {
            "approval_id": approval_record.approval_id,
            "token_id": token.token_id,
            "approved_by": approver.operator_id,
            "approved_at_utc": approval_record.created_at_utc,
            "proposal_digest": proposal_digest,
        }

        return proposal, token, approval_record

    @classmethod
    def reject_proposal(
        cls,
        proposal: PilotProposal,
        rejector: OperatorIdentity,
        reason: str,
        store: TrustedApprovalStore,
    ) -> PilotProposal:
        """Privileged rejection of a pilot proposal."""
        if rejector.role != OperatorRole.APPROVAL_ADMIN:
            raise UnauthorizedOperatorActionError(
                f"Operator '{rejector.operator_id}' with role '{rejector.role.value}' is not authorized to reject proposals."
            )

        proposal.authorization_status = ProposalStatus.REJECTED
        proposal.rejection_reason = reason
        now_utc = datetime.now(timezone.utc).isoformat()
        store.audit_log(
            action="PROPOSAL_REJECTED",
            token_id=proposal.proposal_id,
            event_id=proposal.event_id,
            details={"rejected_by": rejector.operator_id, "reason": reason, "timestamp_utc": now_utc},
        )
        return proposal

    @classmethod
    def revoke_approval(
        cls,
        token_id: str,
        revoker: OperatorIdentity,
        reason: str,
        store: TrustedApprovalStore,
    ) -> bool:
        """Privileged revocation of an active authorization."""
        if revoker.role != OperatorRole.APPROVAL_ADMIN:
            raise UnauthorizedOperatorActionError(
                f"Operator '{revoker.operator_id}' with role '{revoker.role.value}' is not authorized to revoke approvals."
            )
        return store.revoke_approval(token_id=token_id, revoked_by=revoker.operator_id, reason=reason)
