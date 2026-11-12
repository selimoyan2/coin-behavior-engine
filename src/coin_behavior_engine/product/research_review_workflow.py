"""
Sprint 27 — Module 27.6: Research Review & Decision Workflow.
(CBE_SPRINT27_FINAL_RECORD_INTEGRITY_CLOSURE)

Provides a structured, authenticated, append-only scientific review workflow for
research records and experiments.

Key Scientific & Trust Invariants (P0-2 Review Provenance & Authenticity Closure):
1. Strict Separation of Automated Assessments vs. Authenticated Review Decisions:
   - Computed algorithmic recommendations are represented strictly as
     SYSTEM_GENERATED_ASSESSMENT (review_classification="AUTOMATED_ASSESSMENT",
     reviewer_identity="SYSTEM_GENERATED_ASSESSMENT", authoritative=False).
   - Algorithmic assessments are NEVER attributed to CBE_SCIENTIFIC_REVIEW_BOARD
     or CBE_DATA_GOVERNANCE_COUNCIL and NEVER stored as AUTHENTICATED_REVIEW_DECISION.
   - Startup initialization does NOT fabricate historical human review decisions or timestamps.
2. Authenticated Review Decision Requirements:
   - Requires server-verified operator/reviewer authentication (rejects unauthenticated requests
     and rejects client-supplied boolean flags such as is_admin=True, authorized=True).
   - Rejects fabricated or unverified reviewer identities.
   - Requires an auditable decision timestamp (rejects forged historical or future timestamps).
   - Requires non-empty authentic supporting_evidence_ids verified against canonical catalog,
     dataset, and experiment records.
   - Appends every verified decision to an append-only SHA-256 tamper-detection audit log
     with durable atomic persistence and legacy synthetic review quarantine.
3. Governance Boundary:
   - Neither SYSTEM_GENERATED_ASSESSMENT nor ACCEPT_FOR_RESEARCH_ARCHIVE changes
     scientific governance authorization (TECHNICAL_NO_GO remains strictly enforced).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from coin_behavior_engine.product.credential_manager import CredentialManager
from coin_behavior_engine.product.experiment_timeline_registry import (
    _parse_iso8601_utc,
    experiment_registry_service,
)
from coin_behavior_engine.product.process_locking import MultiProcessLock
from coin_behavior_engine.product.research_catalog_provider import ResearchCatalogProvider
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

GENESIS_REVIEW_DIGEST = "0" * 64
REVIEW_PERSISTENCE_SCHEMA_VERSION = "1.0"

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

VALID_REVIEW_CLASSIFICATIONS = (
    "AUTOMATED_ASSESSMENT",
    "AUTHENTICATED_REVIEW_DECISION",
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

PROHIBITED_SYNTHETIC_REVIEW_TIMESTAMPS = {
    f"2026-10-{15 + idx:02d}T12:00:00Z" for idx in range(15)
}


class ReviewWorkflowSecurityError(PermissionError, ValueError):
    """Raised when a review submission or audit log operation violates security or governance rules."""

    def __init__(self, rejection_code: str, message: str) -> None:
        self.rejection_code = str(rejection_code)
        self.message = str(message)
        super().__init__(f"{self.rejection_code}: {self.message}")


@dataclass
class SystemGeneratedAssessment:
    """
    Non-authoritative algorithmic readiness recommendation.
    Never represented as a human or board governance decision.
    """

    assessment_id: str
    research_id: str
    record_origin: str
    review_classification: str
    reviewer_identity: str
    authoritative: bool
    suggested_decision: str
    assessment_reason: str
    supporting_evidence_ids: List[str]
    recommended_review_state: str
    governance_effect: str = "NONE_NON_AUTHORITATIVE_AUTOMATED_ASSESSMENT"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewAuditRecord:
    """Append-only hash-chained authenticated scientific review decision record."""

    review_id: str
    research_id: str
    reviewer_identity: str
    decision: str
    decision_reason: str
    supporting_evidence_ids: List[str]
    decision_timestamp: str
    previous_review_digest: str
    resulting_review_state: str = "REVIEW_COMPLETED"
    review_classification: str = "AUTHENTICATED_REVIEW_DECISION"
    record_origin: str = "AUTHENTICATED_REVIEW_DECISION"
    authoritative: bool = True
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
        self._storage_path = Path(storage_path) if storage_path else None
        self._review_log: List[ReviewAuditRecord] = []
        self._automated_assessments: Dict[str, SystemGeneratedAssessment] = {}
        self._quarantined_synthetic_reviews: List[Dict[str, Any]] = []
        self._record_states: Dict[str, str] = {}

        self._compute_automated_assessments()
        if self._storage_path and self._storage_path.exists():
            self._load_persisted_reviews()

    def _get_lock_path(self) -> Union[str, Path]:
        if self._storage_path is not None:
            return self._storage_path.with_suffix(".lock")
        return Path(tempfile.gettempdir()) / "sprint27_review_workflow.lock"

    def _compute_automated_assessments(self) -> None:
        """
        Computes non-authoritative SYSTEM_GENERATED_ASSESSMENT recommendations from
        current scientific readiness evaluation.
        Never populates self._review_log with fabricated human/board decisions.
        """
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        for rec in catalog:
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

            if is_quarantined:
                suggested_dec = "BLOCK_DUE_TO_PROVENANCE"
                reason = (
                    "Automated readiness check: October 2026 dataset is quarantined due to synthetic contamination; "
                    "recommended state is BLOCKED."
                )
                ev_ids = [rec.id, f"DS-{rec.dataset_id}"]
                rec_state = "BLOCKED"
            elif is_prov_or_integrity_ok and scorecard.overall_verdict == "READY_FOR_CONFIRMATORY_REVIEW":
                suggested_dec = "REQUEST_REPRODUCTION"
                reason = (
                    "Automated readiness check: Source artifact integrity and statistical methodology checks passed; "
                    "awaiting authenticated human scientific review and independent reproduction verification."
                )
                ev_ids = [rec.id, f"DS-{rec.dataset_id}", f"STAT-{rec.id}"]
                rec_state = "EVIDENCE_CHECK_COMPLETED"
            elif is_prov_or_integrity_ok:
                suggested_dec = "REQUEST_ADDITIONAL_EVIDENCE"
                reason = (
                    "Automated readiness check: Source artifact integrity verified; independent out-of-sample "
                    "replication or inferential hypothesis evidence still pending."
                )
                ev_ids = [rec.id, f"DS-{rec.dataset_id}"]
                rec_state = "EVIDENCE_CHECK_COMPLETED"
            else:
                suggested_dec = "BLOCK_DUE_TO_PROVENANCE"
                reason = "Automated readiness check: Dataset provenance verification not satisfied."
                ev_ids = [rec.id]
                rec_state = "BLOCKED"

            assessment = SystemGeneratedAssessment(
                assessment_id=f"AUTO-ASSESS-{rec.id}",
                research_id=rec.id,
                record_origin="AUTOMATED_ASSESSMENT",
                review_classification="AUTOMATED_ASSESSMENT",
                reviewer_identity="SYSTEM_GENERATED_ASSESSMENT",
                authoritative=False,
                suggested_decision=suggested_dec,
                assessment_reason=reason,
                supporting_evidence_ids=ev_ids,
                recommended_review_state=rec_state,
            )
            self._automated_assessments[rec.id] = assessment
            # Until an authenticated human review is submitted, record state reflects initial check state (never REVIEW_COMPLETED)
            if rec.id not in self._record_states:
                self._record_states[rec.id] = rec_state

    def reclassify_or_quarantine_legacy_reviews(
        self,
        candidate_records: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Inspects candidate/legacy review records, quarantining and reclassifying any synthetic
        seeded reviews (e.g., invented 2026-10-15..21 timestamps or unauthenticated board attribution)
        as non-authoritative SYSTEM_GENERATED_ASSESSMENT entries while preserving genuine
        authenticated review decisions.
        """
        preserved: List[ReviewAuditRecord] = []
        quarantined: List[Dict[str, Any]] = []

        for r in candidate_records:
            ts = str(r.get("decision_timestamp") or "").strip()
            classification = str(r.get("review_classification") or "").strip()
            origin = str(r.get("record_origin") or "").strip()
            is_synthetic_seed = (
                ts in PROHIBITED_SYNTHETIC_REVIEW_TIMESTAMPS
                or origin in ("SYNTHETIC_SEED", "AUTOMATED_ASSESSMENT")
                or classification == "AUTOMATED_ASSESSMENT"
                or str(r.get("reviewer_identity") or "") == "SYSTEM_GENERATED_ASSESSMENT"
            )
            if is_synthetic_seed:
                reclassified = dict(r)
                reclassified["review_classification"] = "AUTOMATED_ASSESSMENT"
                reclassified["record_origin"] = "AUTOMATED_ASSESSMENT"
                reclassified["reviewer_identity"] = "SYSTEM_GENERATED_ASSESSMENT"
                reclassified["authoritative"] = False
                reclassified["quarantine_status"] = "QUARANTINED_SYNTHETIC_SEED_REVIEW"
                quarantined.append(reclassified)
                self._quarantined_synthetic_reviews.append(reclassified)
            else:
                rec_obj = ReviewAuditRecord(
                    review_id=str(r.get("review_id", "")),
                    research_id=str(r.get("research_id", "")),
                    reviewer_identity=str(r.get("reviewer_identity", "")),
                    decision=str(r.get("decision", "")),
                    decision_reason=str(r.get("decision_reason", "")),
                    supporting_evidence_ids=list(r.get("supporting_evidence_ids") or []),
                    decision_timestamp=ts,
                    previous_review_digest=str(r.get("previous_review_digest", "")),
                    resulting_review_state=str(r.get("resulting_review_state", "REVIEW_COMPLETED")),
                    review_classification="AUTHENTICATED_REVIEW_DECISION",
                    record_origin="AUTHENTICATED_REVIEW_DECISION",
                    authoritative=True,
                    review_digest=str(r.get("review_digest", "")),
                )
                preserved.append(rec_obj)

        return {
            "preserved_authenticated_count": len(preserved),
            "quarantined_synthetic_count": len(quarantined),
            "preserved_authenticated_reviews": [p.to_dict() for p in preserved],
            "quarantined_synthetic_reviews": quarantined,
        }

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
            review_classification="AUTHENTICATED_REVIEW_DECISION",
            record_origin="AUTHENTICATED_REVIEW_DECISION",
            authoritative=True,
        )
        rec.review_digest = rec.compute_review_digest()
        self._review_log.append(rec)
        self._record_states[research_id] = resulting_state
        return rec

    @staticmethod
    def _build_verifiable_evidence_reference_set(target_research_id: str) -> Set[str]:
        """
        Builds the set of authentic, verifiable evidence identifiers for a given research record.
        Rejects nonexistent or quarantined/unverified evidence IDs.
        """
        valid_ids: Set[str] = set()
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        for rec in catalog:
            is_quarantined = (
                getattr(rec, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
                or rec.id in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
            )
            prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
            scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
            is_verified = (
                bool(prov.get("is_verified"))
                or "SOURCE_ARTIFACT_INTEGRITY" in scorecard.passed_dimensions
            ) and not is_quarantined

            # The research record ID itself is a known catalog reference if it exists
            if rec.id == target_research_id or is_verified:
                valid_ids.add(rec.id)
            if is_verified:
                valid_ids.add(rec.dataset_id)
                valid_ids.add(f"DS-{rec.dataset_id}")
                if "BTCUSDT-SPOT-1H" in rec.dataset_id:
                    valid_ids.add("BTCUSDT-SPOT-1H")
                    valid_ids.add("DS-BTCUSDT-SPOT-1H")
                if "BTCUSDT-SPOT-5M" in rec.dataset_id:
                    valid_ids.add("BTCUSDT-SPOT-5M")
                    valid_ids.add("DS-BTCUSDT-SPOT-5M")
                if "BTCUSDT-PERP-FUNDING" in rec.dataset_id:
                    valid_ids.add("BTCUSDT-PERP-FUNDING-8H")
                    valid_ids.add("DS-BTCUSDT-PERP-FUNDING-8H")
                valid_ids.add(f"STAT-{rec.id}")
                valid_ids.add(f"METH-{rec.id}")
                valid_ids.add(f"HYP-{rec.id}")
                if getattr(rec, "specification_id", None):
                    valid_ids.add(str(rec.specification_id))
                if getattr(rec, "source_artifact", None):
                    valid_ids.add(str(rec.source_artifact))

        for exp in experiment_registry_service.list_experiments().get("experiments", []):
            if exp.get("execution_status") != "BLOCKED":
                valid_ids.add(str(exp["experiment_id"]))
                if exp.get("hypothesis_id"):
                    valid_ids.add(str(exp["hypothesis_id"]))
                if exp.get("methodology_id"):
                    valid_ids.add(str(exp["methodology_id"]))

        return valid_ids

    @staticmethod
    def _verify_reviewer_authentication(
        operator_token: Optional[str],
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Verifies server-side authentication for a review decision submission.
        Rejects automated assessment impersonation, boolean flags, missing tokens,
        invalid tokens, and fabricated reviewer identities.
        """
        body = payload or {}
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}

        # 0. Reject automated assessment impersonation as an authenticated review decision
        if (
            str(body.get("review_classification") or "").strip().upper() == "AUTOMATED_ASSESSMENT"
            or str(body.get("record_origin") or "").strip().upper() == "AUTOMATED_ASSESSMENT"
            or str(body.get("reviewer_identity") or "").strip().upper() == "SYSTEM_GENERATED_ASSESSMENT"
            or bool(body.get("is_automated_assessment"))
        ):
            raise ReviewWorkflowSecurityError(
                "AUTOMATED_ASSESSMENT_IMPERSONATION_REJECTED",
                "Automated recommendation (SYSTEM_GENERATED_ASSESSMENT) cannot be stored as an AUTHENTICATED_REVIEW_DECISION.",
            )

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

    @staticmethod
    def _validate_decision_timestamp(requested_ts: Optional[str]) -> str:
        now_dt = datetime.now(timezone.utc)
        if requested_ts is None:
            return now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        ts_clean = str(requested_ts).strip()
        if ts_clean in PROHIBITED_SYNTHETIC_REVIEW_TIMESTAMPS:
            raise ReviewWorkflowSecurityError(
                "FORGED_REVIEW_TIMESTAMP_REJECTED",
                f"Timestamp '{ts_clean}' matches a prohibited synthetic seed timestamp.",
            )

        parsed_dt = _parse_iso8601_utc(ts_clean)
        if parsed_dt is None:
            raise ReviewWorkflowSecurityError(
                "FORGED_REVIEW_TIMESTAMP_REJECTED",
                f"Review decision timestamp '{ts_clean}' is malformed or missing UTC timezone.",
            )

        # Reject future timestamps (> 60s skew) or backdated historical forgery (> 10 minutes old)
        if parsed_dt > now_dt + timedelta(seconds=60):
            raise ReviewWorkflowSecurityError(
                "FORGED_REVIEW_TIMESTAMP_REJECTED",
                f"Review decision timestamp '{ts_clean}' is in the future.",
            )
        if parsed_dt < now_dt - timedelta(minutes=10):
            raise ReviewWorkflowSecurityError(
                "FORGED_REVIEW_TIMESTAMP_REJECTED",
                f"Review decision timestamp '{ts_clean}' is backdated and cannot be verified as a live authenticated decision.",
            )

        return parsed_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def submit_review_decision(
        self,
        research_id: str,
        decision: str,
        decision_reason: str,
        supporting_evidence_ids: Optional[List[str]] = None,
        operator_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        decision_timestamp: Optional[str] = None,
        review_classification: str = "AUTHENTICATED_REVIEW_DECISION",
    ) -> Dict[str, Any]:
        """
        Submits an authenticated scientific review decision and appends it to the
        hash-chained review audit log.
        """
        combined_payload = dict(payload or {})
        if review_classification and review_classification != "AUTHENTICATED_REVIEW_DECISION":
            combined_payload["review_classification"] = review_classification

        verified_principal = self._verify_reviewer_authentication(
            operator_token=operator_token,
            headers=headers,
            payload=combined_payload,
        )

        # Validate decision timestamp (reject forged past/future timestamps)
        req_ts = decision_timestamp or combined_payload.get("decision_timestamp")
        verified_ts = self._validate_decision_timestamp(req_ts)

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

        # Validate supporting_evidence_ids against authentic verifiable evidence
        ev_list = (
            supporting_evidence_ids
            if supporting_evidence_ids is not None
            else combined_payload.get("supporting_evidence_ids")
        )
        if ev_list is None:
            # Default to [target_id] only if target_id itself has verified provenance/integrity or non-accept decision
            ev_list = [target_id]
        if not isinstance(ev_list, list) or len(ev_list) == 0:
            raise ReviewWorkflowSecurityError(
                "UNVERIFIED_EVIDENCE_REFERENCE_REJECTED",
                "Authenticated review decisions require at least one verifiable supporting_evidence_id.",
            )

        valid_ev_set = self._build_verifiable_evidence_reference_set(target_id)
        for ev_ref in ev_list:
            ev_str = str(ev_ref or "").strip()
            if not ev_str or ev_str not in valid_ev_set:
                raise ReviewWorkflowSecurityError(
                    "UNVERIFIED_EVIDENCE_REFERENCE_REJECTED",
                    f"Supporting evidence reference '{ev_str}' does not exist or is unverified/quarantined.",
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

        with MultiProcessLock(self._get_lock_path(), timeout=5.0):
            if self._storage_path and self._storage_path.exists():
                self._load_persisted_reviews_unlocked()
            audit_rec = self._append_review_record(
                research_id=target_id,
                reviewer_identity=verified_principal,
                decision=dec,
                decision_reason=reason_clean,
                supporting_evidence_ids=[str(x).strip() for x in ev_list],
                resulting_state=resulting_state,
                timestamp_utc=verified_ts,
            )
            self._persist_reviews_unlocked()

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
        Verifies the internal SHA-256 tamper-detection hash chain across all review audit records.
        Detects any tampering with reviewer_identity, decision, reason, timestamp, or previous_review_digest.
        Explicitly labels the chain as an internal tamper-detection mechanism (not externally anchored).
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
                    review_classification=str(r.get("review_classification", "AUTHENTICATED_REVIEW_DECISION")),
                    record_origin=str(r.get("record_origin", "AUTHENTICATED_REVIEW_DECISION")),
                    authoritative=bool(r.get("authoritative", True)),
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
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Review audit hash chain broken at '{item.review_id}' (index {idx}): previous_review_digest mismatch.",
                }
            computed = item.compute_review_digest()
            if item.review_digest and item.review_digest != computed:
                return {
                    "chain_valid": False,
                    "rejection_code": "REVIEW_AUDIT_RECORD_TAMPERED",
                    "failed_index": idx,
                    "failed_review_id": item.review_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Review audit record '{item.review_id}' content does not match review_digest.",
                }
            expected_prev = computed

        return {
            "chain_valid": True,
            "rejection_code": None,
            "total_reviews_verified": len(target_list),
            "head_review_digest": expected_prev,
            "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
            "externally_anchored": False,
            "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
        }

    def list_reviews(self, research_id: Optional[str] = None) -> Dict[str, Any]:
        chain_status = self.verify_review_audit_chain()
        auth_items = [r.to_dict() for r in self._review_log]
        auto_items = [a.to_dict() for a in self._automated_assessments.values()]
        if research_id and str(research_id).upper() != "ALL":
            rq = str(research_id).strip().lower()
            auth_items = [r for r in auth_items if rq in r["research_id"].lower() or rq in r["review_id"].lower()]
            auto_items = [a for a in auto_items if rq in a["research_id"].lower() or rq in a["assessment_id"].lower()]

        return {
            "status": "success",
            "canonical_model": "CBE-0.7.0",
            "governance_decision": "TECHNICAL_NO_GO",
            "valid_review_states": list(VALID_REVIEW_STATES),
            "valid_review_decisions": list(VALID_REVIEW_DECISIONS),
            "audit_chain_integrity": chain_status,
            "record_review_states": dict(self._record_states),
            "total_reviews": len(auth_items),
            "reviews": auth_items,
            "authenticated_reviews": auth_items,
            "total_automated_assessments": len(auto_items),
            "automated_assessments": auto_items,
            "quarantined_synthetic_reviews": list(self._quarantined_synthetic_reviews),
        }

    def _persist_reviews_unlocked(self) -> None:
        if not self._storage_path:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._storage_path.with_suffix(".tmp")
        payload = {
            "schema_version": REVIEW_PERSISTENCE_SCHEMA_VERSION,
            "authenticated_reviews": [r.to_dict() for r in self._review_log],
            "quarantined_synthetic_reviews": list(self._quarantined_synthetic_reviews),
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(serialized)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(self._storage_path))

    def _load_persisted_reviews_unlocked(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return
        tmp_path = self._storage_path.with_suffix(".tmp")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ReviewWorkflowSecurityError(
                "CORRUPTED_REVIEW_AUDIT_LOG",
                f"Persisted review audit log is corrupted: {exc}",
            ) from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != REVIEW_PERSISTENCE_SCHEMA_VERSION:
            raise ReviewWorkflowSecurityError(
                "INVALID_REVIEW_PERSISTENCE_SCHEMA",
                "Persisted review audit log has invalid or missing schema_version.",
            )
        revs_raw = raw.get("authenticated_reviews", [])
        if not isinstance(revs_raw, list):
            raise ReviewWorkflowSecurityError(
                "CORRUPTED_REVIEW_AUDIT_LOG",
                "Persisted authenticated_reviews must be a list.",
            )
        reclassified = self.reclassify_or_quarantine_legacy_reviews(revs_raw)
        preserved_dicts = reclassified["preserved_authenticated_reviews"]
        check = self.verify_review_audit_chain(preserved_dicts)
        if not check.get("chain_valid"):
            raise ReviewWorkflowSecurityError(
                check.get("rejection_code") or "REVIEW_AUDIT_HASH_CHAIN_BROKEN",
                check.get("message") or "Persisted review audit log failed hash-chain verification.",
            )
        self._review_log = [
            ReviewAuditRecord(
                review_id=str(r["review_id"]),
                research_id=str(r["research_id"]),
                reviewer_identity=str(r["reviewer_identity"]),
                decision=str(r["decision"]),
                decision_reason=str(r["decision_reason"]),
                supporting_evidence_ids=list(r.get("supporting_evidence_ids") or []),
                decision_timestamp=str(r["decision_timestamp"]),
                previous_review_digest=str(r["previous_review_digest"]),
                resulting_review_state=str(r.get("resulting_review_state", "REVIEW_COMPLETED")),
                review_classification="AUTHENTICATED_REVIEW_DECISION",
                record_origin="AUTHENTICATED_REVIEW_DECISION",
                authoritative=True,
                review_digest=str(r["review_digest"]),
            )
            for r in preserved_dicts
        ]
        for r in self._review_log:
            self._record_states[r.research_id] = r.resulting_review_state

    def _load_persisted_reviews(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return
        with MultiProcessLock(self._get_lock_path(), timeout=5.0):
            self._load_persisted_reviews_unlocked()


def _default_review_storage_path() -> Optional[Path]:
    env_p = os.environ.get("CBE_REVIEW_WORKFLOW_PATH", "").strip()
    if env_p:
        return Path(env_p)
    staging_dir = Path("/app/data/prospective")
    if staging_dir.exists() and os.access(str(staging_dir), os.W_OK):
        return staging_dir / "sprint27_review_audit_log.json"
    return None


# Singleton workflow engine
research_review_workflow_engine = ResearchReviewWorkflowEngine(
    storage_path=_default_review_storage_path()
)
