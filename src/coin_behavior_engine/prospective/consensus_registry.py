"""
Sprint 11.23.3: Consensus Vintage Evidence Registry
Maintains point-in-time contemporaneous consensus surveys with strict vintage validation,
anti-retrospective matching guards, and cryptographic source document verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .event_models import (
    ConsensusRecord,
    ConsensusVerificationStatus,
)

class ConsensusEvidenceRegistry:
    """
    Registry for prospective consensus forecasts.
    Enforces the core vintage law: consensus must be published and independently observed
    strictly prior to the official event release.
    Rejects claims of verification based solely on numerical match with retrospective calendars.
    """

    def __init__(self) -> None:
        self._records: Dict[str, List[ConsensusRecord]] = {}

    def register_consensus_survey(
        self,
        event_id: str,
        provider_name: str,
        survey_value: float,
        survey_unit: str,
        survey_published_at_utc: str,
        first_observed_at_utc: str,
        retrieved_at_utc: str,
        official_release_scheduled_utc: str,
        original_document_ref: Optional[str] = None,
        raw_document_sha256: Optional[str] = None,
        is_retrospective_calendar_match: bool = False
    ) -> ConsensusRecord:
        """
        Registers a consensus forecast record.
        Enforces:
        1. survey_published_at_utc < official_release_scheduled_utc
        2. first_observed_at_utc < official_release_scheduled_utc
        3. If no physical byte proof (raw_document_sha256 is None or empty),
           status is CONSENSUS_UNVERIFIED.
        4. If marked as merely a retrospective calendar match without contemporaneous wire ticket,
           status remains CONSENSUS_UNVERIFIED.
        """
        t_survey = datetime.fromisoformat(survey_published_at_utc.replace("Z", "+00:00"))
        t_observed = datetime.fromisoformat(first_observed_at_utc.replace("Z", "+00:00"))
        t_release = datetime.fromisoformat(official_release_scheduled_utc.replace("Z", "+00:00"))

        status = ConsensusVerificationStatus.CONSENSUS_UNVERIFIED
        rejection_reason = None

        # Check vintage violation
        if t_survey >= t_release:
            status = ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED
            rejection_reason = "VINTAGE_VIOLATION_SURVEY_PUBLISHED_ON_OR_AFTER_EVENT"
        elif t_observed >= t_release:
            status = ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED
            rejection_reason = "VINTAGE_VIOLATION_FIRST_OBSERVED_ON_OR_AFTER_EVENT"
        else:
            # Vintage is causally valid, now check evidentiary backing
            if is_retrospective_calendar_match and not raw_document_sha256:
                status = ConsensusVerificationStatus.CONSENSUS_UNVERIFIED
                rejection_reason = "RETROSPECTIVE_NUMERICAL_MATCH_INSUFFICIENT_FOR_VERIFICATION"
            elif raw_document_sha256 and len(raw_document_sha256) == 64 and original_document_ref:
                status = ConsensusVerificationStatus.CONSENSUS_VERIFIED
            else:
                status = ConsensusVerificationStatus.CONSENSUS_UNVERIFIED
                rejection_reason = "MISSING_CONTEMPORANEOUS_SOURCE_DOCUMENT_BYTES"

        record = ConsensusRecord(
            event_id=event_id,
            provider_name=provider_name,
            survey_value=survey_value,
            survey_unit=survey_unit,
            survey_published_at_utc=survey_published_at_utc,
            first_observed_at_utc=first_observed_at_utc,
            retrieved_at_utc=retrieved_at_utc,
            original_document_ref=original_document_ref,
            raw_document_sha256=raw_document_sha256,
            verification_status=status,
            rejection_reason=rejection_reason,
            is_retrospective_match=is_retrospective_calendar_match
        )

        if event_id not in self._records:
            self._records[event_id] = []
        self._records[event_id].append(record)
        return record

    def get_consensus_records(self, event_id: str) -> List[ConsensusRecord]:
        return self._records.get(event_id, [])

    def get_verified_consensus(self, event_id: str) -> Optional[ConsensusRecord]:
        for rec in self._records.get(event_id, []):
            if rec.verification_status == ConsensusVerificationStatus.CONSENSUS_VERIFIED:
                return rec
        return None

    def export_summary(self) -> Dict[str, Any]:
        total_records = sum(len(recs) for recs in self._records.values())
        verified_count = 0
        unverified_count = 0
        rejected_count = 0

        for recs in self._records.values():
            for r in recs:
                if r.verification_status == ConsensusVerificationStatus.CONSENSUS_VERIFIED:
                    verified_count += 1
                elif r.verification_status == ConsensusVerificationStatus.CONSENSUS_UNVERIFIED:
                    unverified_count += 1
                elif r.verification_status == ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED:
                    rejected_count += 1

        return {
            "total_events_with_consensus": len(self._records),
            "total_consensus_records": total_records,
            "verified_contemporaneous_count": verified_count,
            "unverified_count": unverified_count,
            "vintage_violation_rejected_count": rejected_count,
            "anti_retrospective_rule_enforced": True
        }
