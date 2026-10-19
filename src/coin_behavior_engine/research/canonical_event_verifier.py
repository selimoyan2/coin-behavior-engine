"""
Sprint 11.23.1: Canonical Event Verification Engine
Provides a single, unified source of truth for historical event classification,
point-in-time causality, and safe execution candle determination.
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

class CanonicalVerificationStatus(str, Enum):
    VERIFIED_POINT_IN_TIME = "VERIFIED_POINT_IN_TIME"
    VERIFIED_EVENT_UNCERTAIN_LATENCY = "VERIFIED_EVENT_UNCERTAIN_LATENCY"
    OFFICIAL_SCHEDULE_ONLY = "OFFICIAL_SCHEDULE_ONLY"
    SECONDARY_TIMESTAMP_ONLY = "SECONDARY_TIMESTAMP_ONLY"
    ASSUMED_LATENCY = "ASSUMED_LATENCY"
    CONSENSUS_UNVERIFIED = "CONSENSUS_UNVERIFIED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"

class CanonicalEventVerifier:
    """Unified classification and causal validation engine."""

    BTC_HALVING_BLOCK_HASH = "0000000000000000000320283a032748cef8227873ff4872689bf23f1cda83a5"

    @classmethod
    def classify_record(cls, record: Dict[str, Any]) -> Tuple[CanonicalVerificationStatus, Optional[str]]:
        """
        Classifies an event record based on verifiable provenance rules:
        1. Causal order violations -> REJECTED
        2. Bitcoin Blockchain Block Hash -> VERIFIED_POINT_IN_TIME
        3. Local physical document bytes verified -> VERIFIED_POINT_IN_TIME / VERIFIED_EVENT_UNCERTAIN_LATENCY
        4. Official agency schedule without local document bytes -> OFFICIAL_SCHEDULE_ONLY
        5. Secondary media reports -> SECONDARY_TIMESTAMP_ONLY
        """
        t_pub_str = record.get("official_published_at_utc")
        t_avail_str = record.get("first_verified_public_at_utc")
        cat = record.get("event_category")
        doc_verified = record.get("source_document_verified", False)
        uncertainty = float(record.get("timestamp_uncertainty_seconds", 300.0))

        if t_pub_str and t_avail_str:
            t_pub = pd.to_datetime(t_pub_str)
            t_avail = pd.to_datetime(t_avail_str)
            if t_avail < t_pub:
                return (CanonicalVerificationStatus.REJECTED, "CAUSAL_ORDER_VIOLATION_PUBLIC_PRECEDES_PUBLISHED")

        # Bitcoin on-chain consensus
        if cat == "BITCOIN_PROTOCOL":
            doc_hash = str(record.get("source_document_sha256", ""))
            if cls.BTC_HALVING_BLOCK_HASH in doc_hash or doc_hash == cls.BTC_HALVING_BLOCK_HASH:
                return (CanonicalVerificationStatus.VERIFIED_POINT_IN_TIME, None)
            return (CanonicalVerificationStatus.QUARANTINED, "BITCOIN_BLOCK_HASH_MISMATCH")

        # Document byte verification
        if doc_verified:
            if uncertainty <= 60.0:
                return (CanonicalVerificationStatus.VERIFIED_POINT_IN_TIME, None)
            elif uncertainty <= 300.0:
                return (CanonicalVerificationStatus.VERIFIED_EVENT_UNCERTAIN_LATENCY, None)
            else:
                return (CanonicalVerificationStatus.ASSUMED_LATENCY, "EXCESSIVE_TIMESTAMP_UNCERTAINTY")

        # When document bytes are not locally verified
        if cat in ["US_INFLATION", "US_LABOR", "US_MONETARY_POLICY", "US_GROWTH"]:
            return (CanonicalVerificationStatus.OFFICIAL_SCHEDULE_ONLY, "PRIMARY_DOCUMENT_BYTES_NOT_ARCHIVED_LOCALLY")

        # Secondary qualitative news / announcements
        return (CanonicalVerificationStatus.SECONDARY_TIMESTAMP_ONLY, "UNARCHIVED_SECONDARY_WIRE_TIMESTAMP")

    @classmethod
    def compute_safe_execution_time(cls, t_pub_utc: datetime.datetime, uncertainty_seconds: float) -> datetime.datetime:
        """
        Computes the earliest defensible execution timestamp using the upper bound
        of the publication uncertainty interval:
        t_safe = t_pub + uncertainty_seconds
        """
        return t_pub_utc + datetime.timedelta(seconds=uncertainty_seconds)
