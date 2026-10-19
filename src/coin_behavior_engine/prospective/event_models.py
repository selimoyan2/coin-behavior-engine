"""
Sprint 11.23.4: Prospective Event Data Models and Status Enums
Defines strongly typed, serialized models for prospective economic and crypto event collection,
consensus vintage tracking, source retrieval artifacts, point-in-time timestamp provenance,
and event lifecycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ProspectiveEventStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    SCHEDULE_VERIFIED = "SCHEDULE_VERIFIED"
    AWAITING_RELEASE = "AWAITING_RELEASE"
    RELEASE_OBSERVED = "RELEASE_OBSERVED"
    SOURCE_EVIDENCE_CAPTURED = "SOURCE_EVIDENCE_CAPTURED"
    MARKET_OBSERVATION_COMPLETE = "MARKET_OBSERVATION_COMPLETE"
    RESEARCH_ELIGIBILITY_REVIEW = "RESEARCH_ELIGIBILITY_REVIEW"

    # Exceptional / Quarantined States
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    TIMESTAMP_UNCERTAIN = "TIMESTAMP_UNCERTAIN"
    CONSENSUS_UNVERIFIED = "CONSENSUS_UNVERIFIED"
    OBSERVATION_INCOMPLETE = "OBSERVATION_INCOMPLETE"
    QUARANTINED = "QUARANTINED"


class ProspectiveEventCategory(str, Enum):
    US_INFLATION = "US_INFLATION"
    US_LABOR = "US_LABOR"
    US_MONETARY_POLICY = "US_MONETARY_POLICY"
    US_GROWTH = "US_GROWTH"
    CRYPTO_PROTOCOL = "CRYPTO_PROTOCOL"


class ConsensusVerificationStatus(str, Enum):
    CONSENSUS_VERIFIED = "CONSENSUS_VERIFIED"
    CONSENSUS_UNVERIFIED = "CONSENSUS_UNVERIFIED"
    VINTAGE_VIOLATION_REJECTED = "VINTAGE_VIOLATION_REJECTED"


class AdapterFailureReason(str, Enum):
    NONE = "NONE"
    HTTP_403_FORBIDDEN = "HTTP_403_FORBIDDEN"
    HTTP_429_RATE_LIMITED = "HTTP_429_RATE_LIMITED"
    HTTP_5XX_SERVER_ERROR = "HTTP_5XX_SERVER_ERROR"
    DNS_FAILURE = "DNS_FAILURE"
    TIMEOUT = "TIMEOUT"
    CONTENT_TYPE_MISMATCH = "CONTENT_TYPE_MISMATCH"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"


class TimestampProvenanceClassification(str, Enum):
    VERIFIED_PUBLICATION_TIME = "VERIFIED_PUBLICATION_TIME"
    OBSERVED_RETRIEVAL_TIME = "OBSERVED_RETRIEVAL_TIME"
    SCHEDULE_ONLY = "SCHEDULE_ONLY"
    TIMESTAMP_UNCERTAIN = "TIMESTAMP_UNCERTAIN"


@dataclass
class EventRevisionRecord:
    revision_id: str
    timestamp_utc: str
    field_changed: str
    old_value: Any
    new_value: Any
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProspectiveEventRecord:
    event_id: str
    event_category: ProspectiveEventCategory
    indicator: str
    issuing_organization: str
    official_source_url: str
    scheduled_publication_at_utc: str
    schedule_verification_at_utc: str
    original_timezone: str
    event_status: ProspectiveEventStatus
    timestamp_uncertainty_seconds: float
    source_evidence_ref: Optional[str] = None
    last_update_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revision_history: List[Dict[str, Any]] = field(default_factory=list)
    directional_trading_eligible: bool = False  # Always False
    actual_official_publication_at_utc: Optional[str] = None
    first_observed_at_utc: Optional[str] = None
    provenance_classification: TimestampProvenanceClassification = (
        TimestampProvenanceClassification.SCHEDULE_ONLY
    )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_category"] = self.event_category.value
        d["event_status"] = self.event_status.value
        d["provenance_classification"] = self.provenance_classification.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProspectiveEventRecord:
        d = dict(data)
        d["event_category"] = ProspectiveEventCategory(d["event_category"])
        d["event_status"] = ProspectiveEventStatus(d["event_status"])
        if "provenance_classification" in d:
            d["provenance_classification"] = TimestampProvenanceClassification(
                d["provenance_classification"]
            )
        else:
            d["provenance_classification"] = TimestampProvenanceClassification.SCHEDULE_ONLY
        return cls(**d)


@dataclass
class ConsensusRecord:
    event_id: str
    provider_name: str
    survey_value: float
    survey_unit: str
    survey_published_at_utc: str
    first_observed_at_utc: str
    retrieved_at_utc: str
    original_document_ref: Optional[str] = None
    raw_document_sha256: Optional[str] = None
    verification_status: ConsensusVerificationStatus = (
        ConsensusVerificationStatus.CONSENSUS_UNVERIFIED
    )
    rejection_reason: Optional[str] = None
    is_retrospective_match: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verification_status"] = self.verification_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConsensusRecord:
        d = dict(data)
        d["verification_status"] = ConsensusVerificationStatus(d["verification_status"])
        return cls(**d)


@dataclass
class ReleaseDocument:
    event_id: str
    source_url: str
    http_status: int
    content_type: str
    raw_bytes: bytes
    raw_sha256: str
    retrieved_at_utc: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    failure_reason: AdapterFailureReason = AdapterFailureReason.NONE
    scheduled_publication_at_utc: Optional[str] = None
    actual_official_publication_at_utc: Optional[str] = None
    retrieval_start_at_utc: Optional[str] = None
    retrieval_complete_at_utc: Optional[str] = None
    first_observed_at_utc: Optional[str] = None
    http_date_header_utc: Optional[str] = None
    http_last_modified_utc: Optional[str] = None
    timestamp_uncertainty_seconds: float = 0.0
    estimated_clock_skew_seconds: float = 0.0
    provenance_classification: TimestampProvenanceClassification = (
        TimestampProvenanceClassification.OBSERVED_RETRIEVAL_TIME
    )

    def to_dict(self, include_bytes: bool = False) -> Dict[str, Any]:
        d = {
            "event_id": self.event_id,
            "source_url": self.source_url,
            "http_status": self.http_status,
            "content_type": self.content_type,
            "raw_sha256": self.raw_sha256,
            "retrieved_at_utc": self.retrieved_at_utc,
            "metadata": self.metadata,
            "failure_reason": self.failure_reason.value,
            "byte_size": len(self.raw_bytes),
            "scheduled_publication_at_utc": self.scheduled_publication_at_utc,
            "actual_official_publication_at_utc": self.actual_official_publication_at_utc,
            "retrieval_start_at_utc": self.retrieval_start_at_utc,
            "retrieval_complete_at_utc": self.retrieval_complete_at_utc,
            "first_observed_at_utc": self.first_observed_at_utc,
            "http_date_header_utc": self.http_date_header_utc,
            "http_last_modified_utc": self.http_last_modified_utc,
            "timestamp_uncertainty_seconds": self.timestamp_uncertainty_seconds,
            "estimated_clock_skew_seconds": self.estimated_clock_skew_seconds,
            "provenance_classification": self.provenance_classification.value,
        }
        if include_bytes:
            d["raw_bytes_hex"] = self.raw_bytes.hex()
        return d
