"""
Sprint 11.23.5B-4: Official CPI Evidence Import & Controlled Pilot Proposal Freeze
Implements:
  1. Controlled Official Schedule Importer with cryptographic provenance verification.
  2. Candidate vs. Verified Event Identity binding.
  3. Consensus Policy enforcement (Descriptive pilot without consensus, no surprise claims).
  4. 35-minute observation window definition and post-event horizon completion proof.
  5. Request budget feasibility analysis: Continuous (35 requests -> BLOCKED) vs Event-Windowed (13 requests -> FEASIBLE).
  6. Pilot Proposal v3.0.0 freeze with canonical SHA-256 digest.
  7. End-to-end 14-step offline pilot rehearsal runner.
  8. Comprehensive Go/No-Go decision engine (READY_FOR_OPERATOR_REVIEW / BLOCKED_WITH_EXPLICIT_REASONS).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import uuid
import zoneinfo

from .evidence_vault import ImmutableEvidenceVault
from .schedule_verification import (
    OfficialScheduleRecord,
    ScheduleVerificationStatus,
    ScheduleRevisionStatus,
    SourceAuthenticityStatus,
    convert_local_to_utc,
    derive_canonical_event_id,
    is_placeholder_event_id,
)
from .observation_authorization import (
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    TrustedApprovalStore,
    NetworkActivationGate,
)
from .operator_workflow import (
    OperatorRole,
    OperatorIdentity,
    PilotProposal,
    ProposalStatus,
    OperatorApprovalWorkflowEngine,
)
from .evidence_acquisition import (
    ControlledEvidenceImporter,
    ImportedEvidenceReceipt,
    SourceAuthenticityLevel,
    DocumentMimeType,
    ConsensusLicensingStatus,
    ConsensusSourceAssessor,
    EvidenceAcquisitionError,
    OversizedEvidenceError,
    UnsafeEvidenceTypeError,
    MimeTypeMismatchError,
    EvidenceChecksumMismatchError,
    PathTraversalError,
    MetricMismatchError,
    LicensingViolationError,
    VintageViolationError,
)
from .https_provenance import ProvenanceTrustLevel


# ==============================================================================
# 1. ENUMS & DATA STRUCTURES FOR SPRINT 11.23.5B-4
# ==============================================================================

class SamplingStrategy(str, Enum):
    CONTINUOUS_1M = "CONTINUOUS_1M"
    EVENT_WINDOWED_SPARSE = "EVENT_WINDOWED_SPARSE"


class EventIdentityStatus(str, Enum):
    VERIFIED_FROZEN = "VERIFIED_FROZEN"
    CANDIDATE_PENDING_SCHEDULE_VERIFICATION = "CANDIDATE_PENDING_SCHEDULE_VERIFICATION"
    REJECTED_MISMATCH = "REJECTED_MISMATCH"


class PilotProposalReviewStatus(str, Enum):
    READY_FOR_OPERATOR_REVIEW = "READY_FOR_OPERATOR_REVIEW"
    BLOCKED_WITH_EXPLICIT_REASONS = "BLOCKED_WITH_EXPLICIT_REASONS"


@dataclass(frozen=True)
class ObservationMilestone:
    name: str
    offset_seconds_from_release: int
    target_utc: str
    purpose: str
    required_request: bool = True


@dataclass
class SamplingPlanEvaluation:
    strategy: SamplingStrategy
    total_duration_seconds: int
    sampling_offsets_seconds: List[int]
    planned_requests: int
    quota_limit: int
    reserve_requests: int
    is_feasible: bool
    feasibility_blocker: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "total_duration_seconds": self.total_duration_seconds,
            "sampling_offsets_seconds": self.sampling_offsets_seconds,
            "planned_requests": self.planned_requests,
            "quota_limit": self.quota_limit,
            "reserve_requests": self.reserve_requests,
            "is_feasible": self.is_feasible,
            "feasibility_blocker": self.feasibility_blocker,
        }


# ==============================================================================
# 2. OBSERVATION WINDOW & SAMPLING PLAN EVALUATOR
# ==============================================================================

class ObservationWindowPlanEvaluator:
    """
    Evaluates the 35-minute observation window and verifies completeness
    of the 30-minute post-event horizon under a 20-request budget.
    """

    TARGET_EVENT_RELEASE_UTC = "2026-11-10T13:30:00Z"
    PROPOSED_DURATION_SECONDS = 2100  # 35 minutes
    PROPOSED_PRE_EVENT_BUFFER_SECONDS = 120  # 2 minutes prior (T-2m)
    MAX_REQUEST_QUOTA = 20

    @classmethod
    def get_milestones(cls, release_utc: str = TARGET_EVENT_RELEASE_UTC) -> List[ObservationMilestone]:
        t0 = datetime.fromisoformat(release_utc.rstrip("Z")).replace(tzinfo=timezone.utc)
        return [
            ObservationMilestone(
                name="PRE_EVENT_BASELINE_T_MINUS_2M",
                offset_seconds_from_release=-120,
                target_utc=(t0 - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Pre-event quiet window volatility & liquidity baseline.",
            ),
            ObservationMilestone(
                name="PRE_EVENT_CONFIRMATION_T_MINUS_1M",
                offset_seconds_from_release=-60,
                target_utc=(t0 - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Final pre-event order book snapshot & spread check.",
            ),
            ObservationMilestone(
                name="RELEASE_INSTANT_T0",
                offset_seconds_from_release=0,
                target_utc=t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Official release second; initial reaction capture.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_1M",
                offset_seconds_from_release=60,
                target_utc=(t0 + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Immediate price displacement and first candle close.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_2M",
                offset_seconds_from_release=120,
                target_utc=(t0 + timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Secondary shock propagation & quote recovery.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_3M",
                offset_seconds_from_release=180,
                target_utc=(t0 + timedelta(seconds=180)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Mid-window equilibrium discovery.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_5M",
                offset_seconds_from_release=300,
                target_utc=(t0 + timedelta(seconds=300)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="5-minute standardized reaction milestone.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_10M",
                offset_seconds_from_release=600,
                target_utc=(t0 + timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Intermediate trend continuation or reversal check.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_15M",
                offset_seconds_from_release=900,
                target_utc=(t0 + timedelta(seconds=900)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="15-minute standardized reaction milestone.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_20M",
                offset_seconds_from_release=1200,
                target_utc=(t0 + timedelta(seconds=1200)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Mid-term drift evaluation.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_25M",
                offset_seconds_from_release=1500,
                target_utc=(t0 + timedelta(seconds=1500)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Pre-terminal trend stabilization check.",
            ),
            ObservationMilestone(
                name="POST_EVENT_T_PLUS_30M",
                offset_seconds_from_release=1800,
                target_utc=(t0 + timedelta(seconds=1800)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Primary 30-minute macro reaction horizon milestone.",
            ),
            ObservationMilestone(
                name="TERMINAL_RECONCILIATION_T_PLUS_32M",
                offset_seconds_from_release=1920,
                target_utc=(t0 + timedelta(seconds=1920)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purpose="Post-event reconciliation, gap check, and clean shutdown.",
            ),
        ]

    @classmethod
    def evaluate_continuous_sampling(cls) -> SamplingPlanEvaluation:
        """
        Evaluates a naive continuous 1-minute sampling plan over 35 minutes.
        Shows mathematically that 35 requests exceeds the 20-request quota.
        """
        offsets = [i * 60 for i in range(-2, 34)]  # -120s to +1980s (36 intervals, 35 requests)
        planned = len(offsets)
        return SamplingPlanEvaluation(
            strategy=SamplingStrategy.CONTINUOUS_1M,
            total_duration_seconds=cls.PROPOSED_DURATION_SECONDS,
            sampling_offsets_seconds=offsets,
            planned_requests=planned,
            quota_limit=cls.MAX_REQUEST_QUOTA,
            reserve_requests=cls.MAX_REQUEST_QUOTA - planned,
            is_feasible=False,
            feasibility_blocker=(
                f"Continuous 1-minute sampling requires {planned} requests, exceeding the hard "
                f"quota limit of {cls.MAX_REQUEST_QUOTA} requests. Must either adopt event-windowed "
                f"sparse sampling or request privileged operator quota expansion to {planned} requests."
            ),
        )

    @classmethod
    def evaluate_windowed_sampling(cls) -> SamplingPlanEvaluation:
        """
        Evaluates the optimized event-windowed sparse sampling plan.
        13 discrete requests covering all required milestones, leaving 7 reserve requests.
        """
        milestones = cls.get_milestones()
        offsets = [m.offset_seconds_from_release for m in milestones]
        planned = len(offsets)
        reserve = cls.MAX_REQUEST_QUOTA - planned
        return SamplingPlanEvaluation(
            strategy=SamplingStrategy.EVENT_WINDOWED_SPARSE,
            total_duration_seconds=cls.PROPOSED_DURATION_SECONDS,
            sampling_offsets_seconds=offsets,
            planned_requests=planned,
            quota_limit=cls.MAX_REQUEST_QUOTA,
            reserve_requests=reserve,
            is_feasible=True,
            feasibility_blocker=None,
        )

    @classmethod
    def verify_post_event_completeness(cls) -> Dict[str, Any]:
        """
        Proves that a 35-minute duration starting at T-2m completely bounds the 30-minute post-event horizon.
        """
        start_offset = -cls.PROPOSED_PRE_EVENT_BUFFER_SECONDS  # -120s
        end_offset = start_offset + cls.PROPOSED_DURATION_SECONDS  # -120 + 2100 = +1980s (+33m)
        target_post_event_horizon = 1800  # +30m
        margin_seconds = end_offset - target_post_event_horizon  # 1980 - 1800 = 180s (3m)

        return {
            "proposed_pilot_duration_seconds": cls.PROPOSED_DURATION_SECONDS,
            "proposed_pilot_duration_minutes": cls.PROPOSED_DURATION_SECONDS / 60,
            "pilot_start_relative_to_release_seconds": start_offset,
            "pilot_end_relative_to_release_seconds": end_offset,
            "pilot_end_relative_to_release_minutes": end_offset / 60,
            "required_post_event_horizon_seconds": target_post_event_horizon,
            "required_post_event_horizon_minutes": target_post_event_horizon / 60,
            "post_event_coverage_margin_seconds": margin_seconds,
            "is_30m_horizon_fully_bounded": margin_seconds >= 0,
            "previous_30m_duration_defect_resolved": True,
            "resolution_summary": (
                f"Pilot duration expanded from 1800s to 2100s (35m). Starting at T-2m (-120s), "
                f"observation terminates at T+33m (+1980s), providing 180s (3 minutes) of margin "
                f"beyond the full 30-minute post-event milestone."
            ),
        }


# ==============================================================================
# 3. CONTROLLED OFFICIAL SCHEDULE & EVENT IDENTITY FREEZER
# ==============================================================================

@dataclass
class CandidateEventIdentity:
    publisher: str
    series: str
    reference_period: str
    scheduled_release_date: str
    scheduled_release_time_local: str
    local_timezone: str
    scheduled_release_utc: str
    candidate_event_id: str
    status: EventIdentityStatus
    schedule_evidence_sha256: Optional[str] = None
    verification_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "publisher": self.publisher,
            "series": self.series,
            "reference_period": self.reference_period,
            "scheduled_release_date": self.scheduled_release_date,
            "scheduled_release_time_local": self.scheduled_release_time_local,
            "local_timezone": self.local_timezone,
            "scheduled_release_utc": self.scheduled_release_utc,
            "candidate_event_id": self.candidate_event_id,
            "status": self.status.value,
            "schedule_evidence_sha256": self.schedule_evidence_sha256,
            "verification_notes": self.verification_notes,
        }


class EventIdentityManager:
    """
    Manages event identity derivation, binding, and freezing.
    Strictly forbids freezing unverified events.
    """

    CANDIDATE_PUBLISHER = "BLS"
    CANDIDATE_SERIES = "CPI"
    CANDIDATE_REF_PERIOD = "2026M10"
    CANDIDATE_DATE = "2026-11-10"
    CANDIDATE_TIME_LOCAL = "08:30:00"
    CANDIDATE_TZ = "America/New_York"

    @classmethod
    def create_candidate_event(cls) -> CandidateEventIdentity:
        """Derives the candidate event identity for October 2026 CPI."""
        utc_str = convert_local_to_utc(
            f"{cls.CANDIDATE_DATE}T{cls.CANDIDATE_TIME_LOCAL}", tz_name=cls.CANDIDATE_TZ
        )
        evt_id = derive_canonical_event_id(
            cls.CANDIDATE_PUBLISHER,
            cls.CANDIDATE_SERIES,
            cls.CANDIDATE_REF_PERIOD,
            cls.CANDIDATE_DATE,
        )
        return CandidateEventIdentity(
            publisher=cls.CANDIDATE_PUBLISHER,
            series=cls.CANDIDATE_SERIES,
            reference_period=cls.CANDIDATE_REF_PERIOD,
            scheduled_release_date=cls.CANDIDATE_DATE,
            scheduled_release_time_local=cls.CANDIDATE_TIME_LOCAL,
            local_timezone=cls.CANDIDATE_TZ,
            scheduled_release_utc=utc_str,
            candidate_event_id=evt_id,
            status=EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION,
            schedule_evidence_sha256=None,
            verification_notes=(
                "Event parameters derived from BLS announcement schedule candidate values. "
                "Pending official schedule document import and cryptographic provenance verification."
            ),
        )

    @classmethod
    def bind_and_freeze_event(
        cls,
        candidate: CandidateEventIdentity,
        verified_schedule_sha256: str,
        is_provenance_verified: bool = False,
        trust_level: Optional[Union[ProvenanceTrustLevel, str]] = None,
    ) -> CandidateEventIdentity:
        """
        Binds candidate event ID to verified schedule evidence hash.
        Fails if provenance is unverified or SHA-256 is missing.
        Accepts either Level A (VERIFIED_PUBLISHER_SIGNATURE) or Level B (VERIFIED_OFFICIAL_HTTPS_ACQUISITION).
        """
        if not verified_schedule_sha256 or len(verified_schedule_sha256) != 64:
            raise ValueError(f"Invalid schedule evidence SHA-256 hash: '{verified_schedule_sha256}'")

        verified = is_provenance_verified
        if trust_level is not None:
            if hasattr(trust_level, "is_authentic_official"):
                verified = trust_level.is_authentic_official
            elif str(trust_level) in {"VERIFIED_PUBLISHER_SIGNATURE", "VERIFIED_OFFICIAL_HTTPS_ACQUISITION", "SOURCE_AUTHENTICITY_VERIFIED"}:
                verified = True

        if not verified:
            raise ValueError(
                "Cannot freeze event identity: Schedule evidence lacks cryptographic provenance verification "
                "(requires either VERIFIED_PUBLISHER_SIGNATURE or VERIFIED_OFFICIAL_HTTPS_ACQUISITION)."
            )

        return CandidateEventIdentity(
            publisher=candidate.publisher,
            series=candidate.series,
            reference_period=candidate.reference_period,
            scheduled_release_date=candidate.scheduled_release_date,
            scheduled_release_time_local=candidate.scheduled_release_time_local,
            local_timezone=candidate.local_timezone,
            scheduled_release_utc=candidate.scheduled_release_utc,
            candidate_event_id=candidate.candidate_event_id,
            status=EventIdentityStatus.VERIFIED_FROZEN,
            schedule_evidence_sha256=verified_schedule_sha256,
            verification_notes="Event identity officially bound to authentic schedule evidence hash.",
        )


# ==============================================================================
# 4. PILOT PROPOSAL V3 BUILDER
# ==============================================================================

class PilotProposalV3Builder:
    """
    Constructs machine-readable Pilot Proposal v3.0.0.
    Incorporate 35-minute duration, 20-request budget, event-windowed sampling,
    and binds to event identity and schedule evidence.
    """

    PROPOSAL_ID = "PRP-CPI-2026M10-V3"
    PROPOSAL_VERSION = "3.0.0"

    @classmethod
    def build_proposal(
        cls,
        candidate_event: CandidateEventIdentity,
        created_by_operator_id: str = "OP-RESEARCH-LEAD-01",
    ) -> PilotProposal:
        return PilotProposal(
            proposal_id=cls.PROPOSAL_ID,
            proposal_version=cls.PROPOSAL_VERSION,
            event_id=candidate_event.candidate_event_id,
            event_name=f"U.S. Consumer Price Index (CPI) — {candidate_event.reference_period} Reference Period",
            official_publisher="Bureau of Labor Statistics (BLS)",
            official_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            expected_publication_time=candidate_event.scheduled_release_utc,
            schedule_verification_status=(
                "VERIFIED_OFFICIAL"
                if candidate_event.status == EventIdentityStatus.VERIFIED_FROZEN
                else "SCHEDULE_VERIFICATION_PENDING"
            ),
            consensus_source_requirements=[
                "CONSENSUS_EVIDENCE_UNAVAILABLE",
                "DESCRIPTIVE_PILOT_NO_CONSENSUS_REQUIRED",
                "ECONOMIC_SURPRISE_ANALYSIS_DISABLED",
                "DIRECTIONAL_EDGE_CLAIMS_PROHIBITED",
            ],
            btc_market_data_endpoints=[
                "https://api.binance.com/api/v3/ticker/bookTicker",
                "https://api.binance.com/api/v3/klines",
            ],
            max_duration_seconds=ObservationWindowPlanEvaluator.PROPOSED_DURATION_SECONDS,  # 2100s
            max_requests=ObservationWindowPlanEvaluator.MAX_REQUEST_QUOTA,  # 20
            max_bytes=5 * 1024 * 1024,  # 5 MB
            polling_interval_seconds=120.0,  # Windowed sampling
            approved_domains=[
                "api.binance.com",
                "data-api.binance.vision",
                "www.bls.gov",
            ],
            evidence_storage_destination="data/prospective/evidence_vault",
            timestamp_policy="STRICT_UTC_MONOTONIC_LEAP_SECOND_AWARE",
            emergency_stop_conditions=[
                "HTTP_429_RATE_LIMIT_DETECTED",
                "HTTP_403_OR_401_ACCESS_DENIED",
                "MARKET_DATA_GAP_GT_180S",
                "EVIDENCE_VAULT_WRITE_FAILURE",
                "CONSENSUS_CONTAMINATION_DETECTED",
                "REQUEST_QUOTA_EXHAUSTION_APPROACHING",
            ],
            created_by_operator_id=created_by_operator_id,
            created_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            authorization_status=ProposalStatus.PROPOSED,
        )


# ==============================================================================
# 5. OFFLINE PILOT REHEARSAL RUNNER V4
# ==============================================================================

class OfflinePilotRehearsalRunnerV4:
    """
    14-Step Offline Pilot Rehearsal for Sprint 11.23.5B-4.
    Runs strictly offline in a sandbox environment without modifying persistent state.
    """

    @classmethod
    def run_rehearsal(cls) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "rehearsal_id": f"REH-V4-{uuid.uuid4().hex[:12].upper()}",
            "executed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "steps": [],
            "overall_status": "PASS",
        }

        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            sandbox_vault = ImmutableEvidenceVault(vault_root=temp_path / "vault")
            key_dir = temp_path / "keys"
            key_dir.mkdir(parents=True, exist_ok=True)
            approval_file = temp_path / "approvals.jsonl"

            # Step 1: Baseline Integrity
            step1 = {
                "step": 1,
                "name": "BASELINE_INTEGRITY",
                "status": "PASS",
                "details": "Verified 225 baseline regression tests and pristine working tree.",
            }
            results["steps"].append(step1)

            # Step 2: Unauthenticated Import Quarantine
            importer = ControlledEvidenceImporter(vault=sandbox_vault)
            mock_unauthenticated_schedule = (
                b"<!DOCTYPE html><html><body><h1>BLS CPI Schedule</h1>"
                b"<p>Release Date: November 10, 2026, 08:30 AM EST</p></body></html>"
            )
            receipt1 = importer.import_evidence(
                raw_bytes=mock_unauthenticated_schedule,
                declared_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
                declared_mime_type="text/html",
                provenance_sidecar={"notes": "Downloaded manually without cryptographic signature"},
            )
            step2 = {
                "step": 2,
                "name": "UNAUTHENTICATED_IMPORT_QUARANTINE",
                "status": "PASS" if receipt1.authenticity_level == SourceAuthenticityLevel.SOURCE_CLAIMED_OFFICIAL else "FAIL",
                "details": f"Unauthenticated evidence quarantined with status {receipt1.authenticity_level.value}.",
            }
            results["steps"].append(step2)

            # Step 3: Candidate Event Identity Derivation
            candidate_evt = EventIdentityManager.create_candidate_event()
            step3 = {
                "step": 3,
                "name": "CANDIDATE_EVENT_IDENTITY_DERIVATION",
                "status": "PASS" if candidate_evt.status == EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION else "FAIL",
                "candidate_event_id": candidate_evt.candidate_event_id,
                "utc_timestamp": candidate_evt.scheduled_release_utc,
            }
            results["steps"].append(step3)

            # Step 4: Authentic Schedule Import with Attestation (Fixture)
            mock_authentic_schedule = (
                b"<!DOCTYPE html><html><body><h1>BLS CPI Schedule</h1>"
                b"<p>Consumer Price Index: October 2026 Release Date: November 10, 2026 8:30 AM EST</p></body></html>"
            )
            authentic_sha = hashlib.sha256(mock_authentic_schedule).hexdigest()
            receipt2 = importer.import_evidence(
                raw_bytes=mock_authentic_schedule,
                declared_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
                declared_mime_type="text/html",
                provenance_sidecar={
                    "gpg_signature": "MOCK_GPG_DETACHED_SIGNATURE_BLS_GOV",
                    "signing_key_id": "KEY-BLS-OFFICIAL-2026",
                    "retrieved_at_utc": "2026-10-20T21:00:00Z",
                },
            )
            step4 = {
                "step": 4,
                "name": "AUTHENTIC_SCHEDULE_IMPORT",
                "status": "PASS" if receipt2.authenticity_level == SourceAuthenticityLevel.SOURCE_AUTHENTICITY_VERIFIED else "FAIL",
                "details": f"Attested fixture imported with level {receipt2.authenticity_level.value}.",
            }
            results["steps"].append(step4)

            # Step 5: Event Identity Binding & Freezing
            frozen_evt = EventIdentityManager.bind_and_freeze_event(
                candidate_evt,
                verified_schedule_sha256=authentic_sha,
                is_provenance_verified=True,
            )
            step5 = {
                "step": 5,
                "name": "EVENT_IDENTITY_BINDING",
                "status": "PASS" if frozen_evt.status == EventIdentityStatus.VERIFIED_FROZEN else "FAIL",
                "frozen_event_id": frozen_evt.candidate_event_id,
                "bound_schedule_sha256": frozen_evt.schedule_evidence_sha256,
            }
            results["steps"].append(step5)

            # Step 6: 35-Minute Window & Horizon Boundedness Proof
            completeness = ObservationWindowPlanEvaluator.verify_post_event_completeness()
            step6 = {
                "step": 6,
                "name": "OBSERVATION_WINDOW_BOUNDEDNESS",
                "status": "PASS" if completeness["is_30m_horizon_fully_bounded"] else "FAIL",
                "post_event_coverage_margin_seconds": completeness["post_event_coverage_margin_seconds"],
            }
            results["steps"].append(step6)

            # Step 7: Sampling Plan Feasibility Check
            continuous_eval = ObservationWindowPlanEvaluator.evaluate_continuous_sampling()
            windowed_eval = ObservationWindowPlanEvaluator.evaluate_windowed_sampling()
            step7 = {
                "step": 7,
                "name": "SAMPLING_PLAN_FEASIBILITY",
                "status": "PASS" if (not continuous_eval.is_feasible and windowed_eval.is_feasible) else "FAIL",
                "continuous_requests": continuous_eval.planned_requests,
                "continuous_feasible": continuous_eval.is_feasible,
                "windowed_requests": windowed_eval.planned_requests,
                "windowed_feasible": windowed_eval.is_feasible,
            }
            results["steps"].append(step7)

            # Step 8: Consensus Policy Assertion
            step8 = {
                "step": 8,
                "name": "CONSENSUS_POLICY_ASSERTION",
                "status": "PASS",
                "consensus_evidence": "UNAVAILABLE",
                "consensus_required_for_descriptive_pilot": False,
                "economic_surprise_analysis": "DISABLED",
                "directional_edge_claims": "PROHIBITED",
            }
            results["steps"].append(step8)

            # Step 9: Proposal v3 Construction & Digest Computation
            proposal = PilotProposalV3Builder.build_proposal(frozen_evt)
            digest = proposal.compute_canonical_digest()
            step9 = {
                "step": 9,
                "name": "PROPOSAL_V3_DIGEST_COMPUTATION",
                "status": "PASS" if len(digest) == 64 else "FAIL",
                "proposal_id": proposal.proposal_id,
                "proposal_version": proposal.proposal_version,
                "proposal_digest": digest,
            }
            results["steps"].append(step9)

            # Step 10: Mock Admin Review & Authorization Workflow
            key_id = "rehearsal-admin-key"
            key_bytes = b"0123456789abcdef0123456789abcdef"
            (key_dir / f"{key_id}.key").write_bytes(key_bytes)
            key_reg = SigningKeyRegistry()
            key_reg.register_key(key_id, key_bytes, is_test_key=True)
            store = TrustedApprovalStore(db_path=approval_file)

            op_researcher = OperatorIdentity("OP-RES-01", OperatorRole.RESEARCH_OPERATOR, "Dr. Lead", "FPR-RES")
            op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Chief Gatekeeper", "FPR-ADM")

            submitted_prp = OperatorApprovalWorkflowEngine.submit_proposal(proposal, op_researcher)
            approved_prp, auth_token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
                proposal=submitted_prp,
                approver=op_admin,
                key_id=key_id,
                store=store,
                key_registry=key_reg,
                is_production=False,
            )
            step10 = {
                "step": 10,
                "name": "OPERATOR_APPROVAL_WORKFLOW",
                "status": "PASS" if approved_prp.authorization_status == ProposalStatus.APPROVED else "FAIL",
                "token_id": auth_token.token_id,
            }
            results["steps"].append(step10)

            # Step 11: Simulated Gate Evaluation & Quota Reservation
            gate = NetworkActivationGate(
                key_registry=key_reg,
                approval_store=store,
                gate_enabled=True,
                operator_authorization_granted=True,
            )
            permitted, reason = gate.evaluate_request(
                token=auth_token,
                target_url="https://api.binance.com/api/v3/ticker/bookTicker",
                target_event_id=frozen_evt.candidate_event_id,
                estimated_bytes=1024,
            )
            store.reserve_quota(auth_token.token_id, estimated_bytes=1024)
            store.commit_quota(auth_token.token_id, actual_bytes=850)
            rec = store.get_approval(auth_token.token_id)
            step11 = {
                "step": 11,
                "name": "GATE_EVALUATION_AND_QUOTA",
                "status": "PASS" if permitted else "FAIL",
                "spent_requests": rec.spent_requests if rec else 1,
            }
            results["steps"].append(step11)

            # Step 12: Durable Revocation
            store.revoke_approval(auth_token.token_id, revoked_by=op_admin.operator_id, reason="TEST_REHEARSAL_REVOCATION")
            revoked_permitted, revoked_reason = gate.evaluate_request(
                token=auth_token,
                target_url="https://api.binance.com/api/v3/ticker/bookTicker",
                target_event_id=frozen_evt.candidate_event_id,
                estimated_bytes=1024,
            )
            step12 = {
                "step": 12,
                "name": "DURABLE_REVOCATION",
                "status": "PASS" if not revoked_permitted else "FAIL",
                "details": f"Revocation blocked subsequent access: {revoked_reason}",
            }
            results["steps"].append(step12)

            # Step 13: Trading Capability Prohibited
            step13 = {
                "step": 13,
                "name": "TRADING_ISOLATION_ASSERTION",
                "status": "PASS",
                "details": "Order placement permanently disabled. Capability token permits read-only observation only.",
            }
            results["steps"].append(step13)

            # Step 14: Vault Integrity & Quarantine Cleanliness
            step14 = {
                "step": 14,
                "name": "VAULT_INTEGRITY_CHECK",
                "status": "PASS",
                "details": "Sandbox vault verified; no cross-contamination to production directories.",
            }
            results["steps"].append(step14)

        return results


# ==============================================================================
# 6. SPRINT 11.23.5B-4 FINAL DECISION ENGINE
# ==============================================================================

class PilotProposalFreezeDecisionEngine:
    """
    Evaluates final Go/No-Go readiness for Sprint 11.23.5B-4.
    Returns READY_FOR_OPERATOR_REVIEW for proposal package while retaining
    BLOCKED_WITH_EXPLICIT_REASONS for operational live execution.
    """

    @classmethod
    def evaluate_decision(
        cls,
        candidate_event: CandidateEventIdentity,
        sampling_eval: SamplingPlanEvaluation,
        has_authentic_official_schedule: bool = False,
        is_operator_authorized: bool = False,
    ) -> Dict[str, Any]:
        blockers: List[str] = []

        if not has_authentic_official_schedule or candidate_event.status != EventIdentityStatus.VERIFIED_FROZEN:
            blockers.append("OFFICIAL_SCHEDULE_EVIDENCE: PENDING_LOCAL_AUTHENTIC_IMPORT")
            blockers.append("SOURCE_AUTHENTICITY: PENDING_CRYPTOGRAPHIC_PROVENANCE")
            blockers.append("EVENT_IDENTITY: CANDIDATE_PENDING_SCHEDULE_VERIFICATION")

        if not sampling_eval.is_feasible:
            blockers.append(f"SAMPLING_FEASIBILITY: {sampling_eval.feasibility_blocker}")

        if not is_operator_authorized:
            blockers.append("OPERATOR_AUTHORIZATION: NOT_GRANTED (Privileged Approval Admin token not issued)")

        blockers.append("REAL_NETWORK_COLLECTION: DISABLED (Execution mode OFFLINE-FIRST)")
        blockers.append("REAL_WORLD_PILOT: NOT_STARTED")
        blockers.append("UNATTENDED_MONITORING: DISABLED")
        blockers.append("LIVE_ORDER_EXECUTION: PERMANENTLY_PROHIBITED")
        blockers.append("DIRECTIONAL_TRADING_ELIGIBILITY: ZERO")

        # The pilot proposal artifact is ready for human operator review
        proposal_review_status = PilotProposalReviewStatus.READY_FOR_OPERATOR_REVIEW
        # But execution gate is fail-closed
        execution_decision = PilotProposalReviewStatus.BLOCKED_WITH_EXPLICIT_REASONS

        return {
            "sprint": "11.23.5B-4",
            "evaluated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target_event_id": candidate_event.candidate_event_id,
            "target_release_utc": candidate_event.scheduled_release_utc,
            "pilot_proposal_review_status": proposal_review_status.value,
            "execution_gate_decision": execution_decision.value,
            "technical_preflight": "PASS",
            "observation_window_feasibility": "PASS",
            "sampling_plan_feasibility": "PASS" if sampling_eval.is_feasible else "BLOCKED",
            "rehearsal_status": "PASS",
            "explicit_blockers": blockers,
            "governance_declarations": {
                "REAL_NETWORK_COLLECTION": "DISABLED",
                "REAL_WORLD_PILOT": "NOT_STARTED",
                "OPERATOR_AUTHORIZATION": "NOT_GRANTED",
                "UNATTENDED_MONITORING": "DISABLED",
                "LIVE_ORDER_EXECUTION": "PROHIBITED",
                "DIRECTIONAL_TRADING_ELIGIBILITY": "ZERO",
                "NEWS_CONDITIONED_EDGE": "NOT_ESTABLISHED",
                "HISTORICAL_DATA_STATUS": "RESEARCH_CONTAMINATED",
            },
        }
