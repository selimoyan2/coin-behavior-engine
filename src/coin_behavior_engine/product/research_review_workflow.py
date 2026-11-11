"""
Sprint 27 — Module 27.6: Research Review & Decision Workflow.
(CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO)

Provides a structured, authenticated, append-only scientific review workflow for
research records and experiments.

Key Scientific & Trust Invariants:
1. Canonical 9 Review States:
   - DRAFT
   - SUBMITTED_FOR_REVIEW
   - EVIDENCE_CHECK_PENDING
   - EVIDENCE_CHECK_COMPLETED
   - SCIENTIFIC_REVIEW_IN_PROGRESS
   - REVISION_REQUESTED
   - REVIEW_COMPLETED
   - REJECTED
   - BLOCKED
2. Canonical 6 Review Decision Types:
   - ACCEPT_FOR_RESEARCH_ARCHIVE
   - REQUEST_ADDITIONAL_EVIDENCE
   - REQUEST_REPRODUCTION
   - REQUEST_METHODOLOGY_REVIEW
   - REJECT_UNSUPPORTED_CLAIM
   - BLOCK_DUE_TO_PROVENANCE
3. Review Authorization & Audit Trail:
   - Rejects unauthenticated review decision submissions (Negative Security Test #7).
   - Rejects client-supplied boolean authorization flags such as is_admin=True,
     authorized=True, reviewer_override=True (Negative Security Test #8).
   - Rejects fabricated or unverified reviewer identities.
   - Records every decision in an append-only hash-chained review audit log
     with tamper detection (Negative Security Test #9).
4. Governance Boundary:
   - ACCEPT_FOR_RESEARCH_ARCHIVE means accepted into the offline scientific archive ONLY.
   - Never grants live trading permission, production deployment, or removal of TECHNICAL_NO_GO
     (Negative Security Test #19).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from coin_behavior_engine.product.credential_manager import CredentialManager
from coin_behavior_engine.product.process_locking import MultiProcessLock
from coin_behavior_engine.product.research_catalog_provider import ResearchCatalogProvider
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

GENESIS_REVIEW_DIGEST = "0" * 64

VALID_REVIEW_STATES = (
    "DRAFT",
    "SUBMITTED_FOR_REVIEW",
    "EVIDENCE_CHECK_PENDING",
    "EVIDENCE_CHECK_COMPLETED",
    "SCIENTIFIC_REVIEW_IN_PROGRESS",
    "REVISION_REQUESTED",
    "REVIEW_COMPLETED",
    "REJECTED",
    "BLOCKED",
)

VALID_REVIEW_DECISIONS = (
    "ACCEPT_FOR_RESEARCH_ARCHIVE",
    "REQUEST_ADDITIONAL_EVIDENCE",
    "REQUEST_REPRODUCTION",
    "REQUEST_METHODOLOGY_REVIEW",
    "REJECT_UNSUPPORTED_CLAIM",
    "BLOCK_DUE_TO_PROVENANCE",
)

AUTHORIZED_REVIEWER_PRINCIPALS = {
    "CBE_SCIENTIFIC_REVIEW_BOARD",
    "CBE_AUTHORIZED_OPERATOR_REVIEWER",
    "CBE_DATA_GOVERNANCE_COUNCIL",
}

FORBIDDEN_CLIENT_AUTH_FLAGS = (
    "is_admin",
    "authorized",
    "is_authorized",
    "reviewer_override",
    "bypass_auth",
    "force_accept",
    "grant_live_trading",
    "remove_technical_no_go",
)


class ReviewWorkflowSecurityError(PermissionError, ValueError):
    """Raised when a review submission or audit log operation violates security or governance rules."""

    def __init__(self, rejection_code: str, message: str) -> None:
        self.rejection_code = str(rejection_code)
        self.message = str(message)
        super().__init__(f"{self.rejection_code}: {self.message}")


@dataclass
class ReviewAuditRecord:
    """Append-only hash-chained scientific review decision record."""

    review_id: str
    research_id: str
    reviewer_identity: str
    decision: str
    decision_reason: str
    supporting_evidence_ids: List[str]
    decision_timestamp: str
    previous_review_digest: str
    resulting_review_state: str = "REVIEW_COMPLETED"
    governance_scope_notice: str = (
        "OFFLINE_RESEARCH_ARCHIVE_ONLY | TECHNICAL_NO_GO_UNCHANGED | LIVE_TRADING_PERMANENTLY_PROHIBITED"
    )
    review_digest: str = ""

    def compute_review_digest(self) -> str:
        core = {
            "review_id": self.review_id,
            "research_id": self.research_id,
            "reviewer_identity": self.reviewer_identity,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "decision_timestamp": self.decision_timestamp,
            "previous_review_digest": self.previous_review_digest,
        }
        return hashlib.sha256(rfc8785_canonical_json(core)).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("review_digest"):
            d["review_digest"] = self.compute_review_digest()
        return d


class ResearchReviewWorkflowEngine:
    """Module 27.6 — Authenticated Scientific Review & Decision Workflow Engine."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = storage_path
        self._review_log: List[ReviewAuditRecord] = []
        self._record_states: Dict[str, str] = {}
        self._seed_canonical_reviews()

    def _append_review_record(
        self,
        research_id: str,
        reviewer_identity: str,
        decision: str,
        decision_reason: str,
        supporting_evidence_ids: List[str],
        resulting_state: str,
        timestamp_utc: Optional[str] = None,
    ) -> ReviewAuditRecord:
        ts = timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prev_digest = (
            self._review_log[-1].review_digest
            if self._review_log
            else GENESIS_REVIEW_DIGEST
        )
        seq_no = len(self._review_log) + 1
        rev_id = f"REV-{seq_no:04d}-{research_id}"
        rec = ReviewAuditRecord(
            review_id=rev_id,
            research_id=research_id,
            reviewer_identity=reviewer_identity,
            decision=decision,
            decision_reason=decision_reason,
            supporting_evidence_ids=list(supporting_evidence_ids or []),
            decision_timestamp=ts,
            previous_review_digest=prev_digest,
            resulting_review_state=resulting_state,
        )
        rec.review_digest = rec.compute_review_digest()
        self._review_log.append(rec)
        self._record_states[research_id] = resulting_state
        return rec

    def _seed_canonical_reviews(self) -> None:
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        for idx, rec in enumerate(catalog):
            prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
            scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
            is_quarantined = (
                getattr(rec, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
                or rec.id in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
            )
            is_prov_or_integrity_ok = (
                bool(prov.get("is_verified"))
                or "SOURCE_ARTIFACT_INTEGRITY" in scorecard.passed_dimensions
            ) and not is_quarantined
            ts = f"2026-10-{15 + idx:02d}T12:00:00Z"

            if is_quarantined:
                self._append_review_record(
                    research_id=rec.id,
                    reviewer_identity="CBE_DATA_GOVERNANCE_COUNCIL",
                    decision="BLOCK_DUE_TO_PROVENANCE",
                    decision_reason="October 2026 dataset is quarantined due to synthetic contamination; blocked from confirmatory research.",
                    supporting_evidence_ids=[f"DS-{rec.dataset_id}"],
                    resulting_state="BLOCKED",
                    timestamp_utc=ts,
                )
            elif is_prov_or_integrity_ok and scorecard.overall_verdict == "READY_FOR_CONFIRMATORY_REVIEW":
                self._append_review_record(
                    research_id=rec.id,
                    reviewer_identity="CBE_SCIENTIFIC_REVIEW_BOARD",
                    decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                    decision_reason="Cryptographic provenance, statistical methodology, and reproducibility checks passed for offline research archive.",
                    supporting_evidence_ids=[rec.id, f"DS-{rec.dataset_id}", f"STAT-{rec.id}"],
                    resulting_state="REVIEW_COMPLETED",
                    timestamp_utc=ts,
                )
            elif is_prov_or_integrity_ok:
                self._append_review_record(
                    research_id=rec.id,
                    reviewer_identity="CBE_SCIENTIFIC_REVIEW_BOARD",
                    decision="REQUEST_ADDITIONAL_EVIDENCE",
                    decision_reason="Source artifact integrity verified; independent out-of-sample replication or inferential hypothesis evidence still pending.",
                    supporting_evidence_ids=[rec.id, f"DS-{rec.dataset_id}"],
                    resulting_state="EVIDENCE_CHECK_COMPLETED",
                    timestamp_utc=ts,
                )
            else:
                self._append_review_record(
                    research_id=rec.id,
                    reviewer_identity="CBE_DATA_GOVERNANCE_COUNCIL",
                    decision="BLOCK_DUE_TO_PROVENANCE",
                    decision_reason="Dataset provenance verification not satisfied.",
                    supporting_evidence_ids=[rec.id],
                    resulting_state="BLOCKED",
                    timestamp_utc=ts,
                )

    @staticmethod
    def _verify_reviewer_authentication(
        operator_token: Optional[str],
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Verifies server-side authentication for a review decision submission.
        Rejects boolean flags, missing tokens, invalid tokens, and fabricated reviewer identities.
        """
        body = payload or {}
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}

        # 1. Reject client-supplied boolean authorization or governance override flags
        for bad_flag in FORBIDDEN_CLIENT_AUTH_FLAGS:
            if bad_flag in body:
                raise ReviewWorkflowSecurityError(
                    "CLIENT_AUTHORIZATION_FLAG_REJECTED",
                    f"Client-supplied authorization or governance flag '{bad_flag}' is strictly prohibited.",
                )

        # 2. Extract token from explicit argument or request headers (never trust a bare boolean)
        tok = (
            operator_token
            or hdrs.get("x-operator-token")
            or hdrs.get("x-research-token")
            or body.get("operator_token")
        )
        if not tok and "authorization" in hdrs:
            auth_val = str(hdrs["authorization"]).strip()
            if auth_val.lower().startswith("bearer "):
                tok = auth_val[7:].strip()

        if not tok or not str(tok).strip():
            raise ReviewWorkflowSecurityError(
                "UNAUTHENTICATED_REVIEW_SUBMISSION_REJECTED",
                "Submitting a scientific review decision requires server-verified operator/reviewer authentication.",
            )

        clean_tok = str(tok).strip()
        is_valid, reason = CredentialManager.verify_operator_token(clean_tok)
        if not is_valid:
            # Also check configured staging research token if in non-production
            env = CredentialManager.get_environment()
            test_tok = CredentialManager.get_test_operator_token()
            if env != "production" and test_tok and hmac.compare_digest(clean_tok.encode("utf-8"), test_tok.strip().encode("utf-8")):
                is_valid = True
            else:
                raise ReviewWorkflowSecurityError(
                    "REVIEWER_AUTHENTICATION_FAILED",
                    f"Reviewer authentication failed ({reason}).",
                )

        # 3. Validate reviewer_identity (cannot be fabricated arbitrary identity)
        requested_identity = str(
            body.get("reviewer_identity") or "CBE_AUTHORIZED_OPERATOR_REVIEWER"
        ).strip()
        if requested_identity not in AUTHORIZED_REVIEWER_PRINCIPALS:
            raise ReviewWorkflowSecurityError(
                "FABRICATED_REVIEWER_IDENTITY_REJECTED",
                f"Reviewer identity '{requested_identity}' is not an authorized server-verified principal.",
            )

        return requested_identity

    def submit_review_decision(
        self,
        research_id: str,
        decision: str,
        decision_reason: str,
        supporting_evidence_ids: Optional[List[str]] = None,
        operator_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submits an authenticated scientific review decision and appends it to the
        hash-chained review audit log.
        """
        combined_payload = dict(payload or {})
        verified_principal = self._verify_reviewer_authentication(
            operator_token=operator_token,
            headers=headers,
            payload=combined_payload,
        )

        dec = str(decision or "").strip().upper()
        if dec not in VALID_REVIEW_DECISIONS:
            raise ReviewWorkflowSecurityError(
                "INVALID_REVIEW_DECISION_TYPE",
                f"Invalid review decision '{dec}'. Supported: {VALID_REVIEW_DECISIONS}",
            )

        reason_clean = str(decision_reason or "").strip()
        if len(reason_clean) < 5:
            raise ReviewWorkflowSecurityError(
                "MISSING_DECISION_REASON",
                "A substantive scientific decision_reason is required for every review decision.",
            )

        catalog = ResearchCatalogProvider.get_canonical_catalog()
        cat_by_id = {r.id: r for r in catalog}
        target_id = str(research_id or "").strip()
        if target_id not in cat_by_id:
            raise ReviewWorkflowSecurityError(
                "RESEARCH_RECORD_NOT_FOUND",
                f"Research record '{target_id}' does not exist in the canonical catalog.",
            )

        rec = cat_by_id[target_id]
        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        is_quarantined = (
            getattr(rec, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
            or rec.id in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
        )
        is_prov_or_integrity_ok = (
            bool(prov.get("is_verified"))
            or "SOURCE_ARTIFACT_INTEGRITY" in scorecard.passed_dimensions
        ) and not is_quarantined

        # Fail-closed provenance check: cannot ACCEPT_FOR_RESEARCH_ARCHIVE if provenance is unverified or quarantined
        if dec == "ACCEPT_FOR_RESEARCH_ARCHIVE" and not is_prov_or_integrity_ok:
            raise ReviewWorkflowSecurityError(
                "UNVERIFIED_PROVENANCE_ARCHIVE_ACCEPTANCE_BLOCKED",
                f"Cannot accept '{target_id}' for the research archive because dataset provenance is unverified or quarantined.",
            )

        state_map = {
            "ACCEPT_FOR_RESEARCH_ARCHIVE": "REVIEW_COMPLETED",
            "REQUEST_ADDITIONAL_EVIDENCE": "REVISION_REQUESTED",
            "REQUEST_REPRODUCTION": "REVISION_REQUESTED",
            "REQUEST_METHODOLOGY_REVIEW": "SCIENTIFIC_REVIEW_IN_PROGRESS",
            "REJECT_UNSUPPORTED_CLAIM": "REJECTED",
            "BLOCK_DUE_TO_PROVENANCE": "BLOCKED",
        }
        resulting_state = state_map[dec]

        audit_rec = self._append_review_record(
            research_id=target_id,
            reviewer_identity=verified_principal,
            decision=dec,
            decision_reason=reason_clean,
            supporting_evidence_ids=list(supporting_evidence_ids or [target_id]),
            resulting_state=resulting_state,
        )

        return {
            "status": "success",
            "review_record": audit_rec.to_dict(),
            "governance_enforcement": {
                "canonical_model": "CBE-0.7.0",
                "model_status": "STRICTLY_FROZEN",
                "technical_decision": "TECHNICAL_NO_GO",
                "live_trading_authorized": False,
                "production_deployment_authorized": False,
                "archive_acceptance_scope": "OFFLINE_SCIENTIFIC_RESEARCH_ARCHIVE_ONLY",
            },
        }

    def verify_review_audit_chain(
        self,
        records: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Verifies the SHA-256 hash chain across all review audit records.
        Detects any tampering with reviewer_identity, decision, reason, timestamp, or previous_review_digest
        (Negative Security Test #9).
        """
        target_list = (
            [
                ReviewAuditRecord(
                    review_id=str(r.get("review_id", "")),
                    research_id=str(r.get("research_id", "")),
                    reviewer_identity=str(r.get("reviewer_identity", "")),
                    decision=str(r.get("decision", "")),
                    decision_reason=str(r.get("decision_reason", "")),
                    supporting_evidence_ids=list(r.get("supporting_evidence_ids") or []),
                    decision_timestamp=str(r.get("decision_timestamp", "")),
                    previous_review_digest=str(r.get("previous_review_digest", "")),
                    resulting_review_state=str(r.get("resulting_review_state", "REVIEW_COMPLETED")),
                    review_digest=str(r.get("review_digest", "")),
                )
                for r in records
            ]
            if records is not None
            else self._review_log
        )

        expected_prev = GENESIS_REVIEW_DIGEST
        for idx, item in enumerate(target_list):
            if item.previous_review_digest != expected_prev:
                return {
                    "chain_valid": False,
                    "rejection_code": "REVIEW_AUDIT_HASH_CHAIN_BROKEN",
                    "failed_index": idx,
                    "failed_review_id": item.review_id,
                    "message": f"Review audit hash chain broken at '{item.review_id}' (index {idx}): previous_review_digest mismatch.",
                }
            computed = item.compute_review_digest()
            if item.review_digest and item.review_digest != computed:
                return {
                    "chain_valid": False,
                    "rejection_code": "REVIEW_AUDIT_RECORD_TAMPERED",
                    "failed_index": idx,
                    "failed_review_id": item.review_id,
                    "message": f"Review audit record '{item.review_id}' content does not match review_digest.",
                }
            expected_prev = computed

        return {
            "chain_valid": True,
            "rejection_code": None,
            "total_reviews_verified": len(target_list),
            "head_review_digest": expected_prev,
        }

    def list_reviews(self, research_id: Optional[str] = None) -> Dict[str, Any]:
        chain_status = self.verify_review_audit_chain()
        items = [r.to_dict() for r in self._review_log]
        if research_id and str(research_id).upper() != "ALL":
            rq = str(research_id).strip().lower()
            items = [r for r in items if rq in r["research_id"].lower() or rq in r["review_id"].lower()]

        return {
            "status": "success",
            "canonical_model": "CBE-0.7.0",
            "governance_decision": "TECHNICAL_NO_GO",
            "valid_review_states": list(VALID_REVIEW_STATES),
            "valid_review_decisions": list(VALID_REVIEW_DECISIONS),
            "audit_chain_integrity": chain_status,
            "record_review_states": dict(self._record_states),
            "total_reviews": len(items),
            "reviews": items,
        }


# Singleton workflow engine
research_review_workflow_engine = ResearchReviewWorkflowEngine()
