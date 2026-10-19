"""
Sprint 11.23.3: Event Lifecycle State Machine
Implements the rigorous prospective event state machine from discovery to research review.
Enforces explicit evidentiary gates and handles all exceptional quarantine states.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .event_models import (
    ProspectiveEventRecord,
    ProspectiveEventStatus,
    ReleaseDocument,
    ConsensusRecord,
    ConsensusVerificationStatus,
    AdapterFailureReason,
)

class EventLifecycleTransitionError(Exception):
    """Raised when an illegal or unverified state machine transition is attempted."""
    pass

class EventStateMachine:
    """
    Formal state machine for prospective event progression.
    Guarantees that an event cannot advance to research review without
    satisfying all intermediate cryptographic, causal, and observational criteria.
    """

    VALID_FORWARD_TRANSITIONS = {
        ProspectiveEventStatus.DISCOVERED: [
            ProspectiveEventStatus.SCHEDULE_VERIFIED,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.SCHEDULE_VERIFIED: [
            ProspectiveEventStatus.AWAITING_RELEASE,
            ProspectiveEventStatus.TIMESTAMP_UNCERTAIN,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.AWAITING_RELEASE: [
            ProspectiveEventStatus.RELEASE_OBSERVED,
            ProspectiveEventStatus.SOURCE_UNAVAILABLE,
            ProspectiveEventStatus.TIMESTAMP_UNCERTAIN,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.RELEASE_OBSERVED: [
            ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED,
            ProspectiveEventStatus.SOURCE_UNAVAILABLE,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED: [
            ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE,
            ProspectiveEventStatus.OBSERVATION_INCOMPLETE,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE: [
            ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW,
            ProspectiveEventStatus.CONSENSUS_UNVERIFIED,
            ProspectiveEventStatus.QUARANTINED
        ],
        ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW: [
            ProspectiveEventStatus.QUARANTINED
        ]
    }

    @classmethod
    def can_transition(cls, current_status: ProspectiveEventStatus, target_status: ProspectiveEventStatus) -> bool:
        allowed = cls.VALID_FORWARD_TRANSITIONS.get(current_status, [])
        return target_status in allowed

    @classmethod
    def transition(
        cls,
        event: ProspectiveEventRecord,
        target_status: ProspectiveEventStatus,
        reason: str = "",
    ) -> ProspectiveEventRecord:
        if not cls.can_transition(event.event_status, target_status):
            raise EventLifecycleTransitionError(
                f"Cannot transition from {event.event_status} to {target_status}: {reason}"
            )
        event.event_status = target_status
        return event

    @classmethod
    def transition_to_schedule_verified(
        cls,
        event: ProspectiveEventRecord,
        verified_utc: str
    ) -> ProspectiveEventRecord:
        if not cls.can_transition(event.event_status, ProspectiveEventStatus.SCHEDULE_VERIFIED):
            raise EventLifecycleTransitionError(f"Cannot transition from {event.event_status} to SCHEDULE_VERIFIED")
        
        event.event_status = ProspectiveEventStatus.SCHEDULE_VERIFIED
        event.schedule_verification_at_utc = verified_utc
        return event

    @classmethod
    def transition_to_awaiting_release(cls, event: ProspectiveEventRecord) -> ProspectiveEventRecord:
        if not cls.can_transition(event.event_status, ProspectiveEventStatus.AWAITING_RELEASE):
            raise EventLifecycleTransitionError(f"Cannot transition from {event.event_status} to AWAITING_RELEASE")
        
        event.event_status = ProspectiveEventStatus.AWAITING_RELEASE
        return event

    @classmethod
    def transition_to_release_observed(
        cls,
        event: ProspectiveEventRecord,
        observed_release_utc: str,
        uncertainty_seconds: float
    ) -> ProspectiveEventRecord:
        if uncertainty_seconds > 300.0:
            event.event_status = ProspectiveEventStatus.TIMESTAMP_UNCERTAIN
            return event

        if not cls.can_transition(event.event_status, ProspectiveEventStatus.RELEASE_OBSERVED):
            raise EventLifecycleTransitionError(f"Cannot transition from {event.event_status} to RELEASE_OBSERVED")
        
        event.event_status = ProspectiveEventStatus.RELEASE_OBSERVED
        event.timestamp_uncertainty_seconds = uncertainty_seconds
        return event

    @classmethod
    def transition_to_evidence_captured(
        cls,
        event: ProspectiveEventRecord,
        doc: ReleaseDocument
    ) -> ProspectiveEventRecord:
        if doc.http_status in [403, 429, 404] or doc.failure_reason != AdapterFailureReason.NONE:
            event.event_status = ProspectiveEventStatus.SOURCE_UNAVAILABLE
            event.source_evidence_ref = None
            return event

        if not doc.raw_sha256 or len(doc.raw_sha256) != 64:
            event.event_status = ProspectiveEventStatus.QUARANTINED
            return event

        if not cls.can_transition(event.event_status, ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED):
            raise EventLifecycleTransitionError(f"Cannot transition from {event.event_status} to SOURCE_EVIDENCE_CAPTURED")

        event.event_status = ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED
        event.source_evidence_ref = doc.raw_sha256
        return event

    @classmethod
    def transition_to_observation_complete(
        cls,
        event: ProspectiveEventRecord,
        missing_candles_count: int
    ) -> ProspectiveEventRecord:
        if missing_candles_count > 0:
            event.event_status = ProspectiveEventStatus.OBSERVATION_INCOMPLETE
            return event

        if not cls.can_transition(event.event_status, ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE):
            raise EventLifecycleTransitionError(f"Cannot transition from {event.event_status} to MARKET_OBSERVATION_COMPLETE")

        event.event_status = ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE
        return event

    @classmethod
    def evaluate_research_eligibility(
        cls,
        event: ProspectiveEventRecord,
        consensus_record: Optional[ConsensusRecord] = None
    ) -> Tuple[ProspectiveEventStatus, Dict[str, Any]]:
        """
        Final research eligibility evaluation.
        Requires:
        1. Event in MARKET_OBSERVATION_COMPLETE
        2. Valid source_evidence_ref present
        3. If consensus is required: must be CONSENSUS_VERIFIED
        Even if eligible for research, directional trading eligibility remains FALSE.
        """
        audit_results = {
            "schedule_verified": event.schedule_verification_at_utc is not None,
            "source_evidence_verified": bool(event.source_evidence_ref and len(event.source_evidence_ref) == 64),
            "timestamp_certainty_verified": event.timestamp_uncertainty_seconds <= 300.0,
            "consensus_verified": False,
            "directional_trading_permitted": False # Strictly False
        }

        if consensus_record:
            audit_results["consensus_verified"] = (consensus_record.verification_status == ConsensusVerificationStatus.CONSENSUS_VERIFIED)

        # Enforce gates
        if not audit_results["source_evidence_verified"]:
            event.event_status = ProspectiveEventStatus.SOURCE_UNAVAILABLE
            return event.event_status, audit_results

        if not audit_results["timestamp_certainty_verified"]:
            event.event_status = ProspectiveEventStatus.TIMESTAMP_UNCERTAIN
            return event.event_status, audit_results

        if consensus_record and not audit_results["consensus_verified"]:
            event.event_status = ProspectiveEventStatus.CONSENSUS_UNVERIFIED
            return event.event_status, audit_results

        if not cls.can_transition(event.event_status, ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW):
            event.event_status = ProspectiveEventStatus.QUARANTINED
            return event.event_status, audit_results

        event.event_status = ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW
        event.directional_trading_eligible = False # Never promote to trading
        return event.event_status, audit_results
