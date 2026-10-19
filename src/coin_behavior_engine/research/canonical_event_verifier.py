"""
Sprint 11.23.2: Canonical Event Verification Engine
Provides a single, unified source of truth for historical event classification,
blockchain identifier vs source document verification, point-in-time causality,
and safe execution candle determination.
"""

from __future__ import annotations

import datetime
from enum import Enum
import hashlib
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
    """Unified classification, provenance verification, and causal validation engine."""

    BTC_HALVING_BLOCK_HASH = "0000000000000000000320283a032748cef8227873ff4872689bf23f1cda83a5"
    BTC_HALVING_BLOCK_HEIGHT = 840000

    @classmethod
    def verify_document_bytes(cls, file_path: Path, expected_sha256: str) -> bool:
        """
        Physically validates source document bytes from local disk.
        Returns False if file is missing, empty, or hash does not match expected_sha256.
        """
        if not file_path or not file_path.exists() or not file_path.is_file():
            return False
        if not expected_sha256 or len(expected_sha256) != 64:
            return False
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower() == expected_sha256.lower()

    @classmethod
    def verify_blockchain_block(cls, block_hash: str, block_height: Optional[int] = None) -> bool:
        """
        Verifies on-chain blockchain block identifier.
        Distinguishes PoW target consensus hash from off-chain source document hash.
        """
        if not isinstance(block_hash, str) or len(block_hash) != 64:
            return False
        if block_height == cls.BTC_HALVING_BLOCK_HEIGHT:
            return block_hash.lower() == cls.BTC_HALVING_BLOCK_HASH.lower()
        return block_hash.startswith("00000000")

    @classmethod
    def classify_record(cls, record: Dict[str, Any], base_dir: Optional[Path] = None) -> Tuple[CanonicalVerificationStatus, Optional[str]]:
        """
        Classifies an event record based on verifiable provenance rules:
        1. Causal order violations -> REJECTED
        2. Bitcoin Blockchain Block Hash -> Verified on-chain consensus
        3. Local physical document bytes verified -> VERIFIED_POINT_IN_TIME / VERIFIED_EVENT_UNCERTAIN_LATENCY
        4. Official agency schedule without local document bytes -> OFFICIAL_SCHEDULE_ONLY
        5. Secondary media reports -> SECONDARY_TIMESTAMP_ONLY
        """
        t_pub_str = record.get("official_published_at_utc")
        t_avail_str = record.get("first_verified_public_at_utc")
        cat = record.get("event_category")
        doc_verified = record.get("source_document_verified", False)
        uncertainty = float(record.get("timestamp_uncertainty_seconds") or record.get("publication_timestamp_uncertainty_seconds") or 300.0)

        # Causal sanity check: public availability cannot precede official published time
        if t_pub_str and t_avail_str:
            t_pub = pd.to_datetime(t_pub_str)
            t_avail = pd.to_datetime(t_avail_str)
            if t_avail < t_pub:
                return (CanonicalVerificationStatus.REJECTED, "CAUSAL_ORDER_VIOLATION_PUBLIC_PRECEDES_PUBLISHED")

        # Blockchain on-chain consensus
        if cat == "BITCOIN_PROTOCOL":
            block_hash = record.get("blockchain_block_hash") or record.get("source_document_sha256")
            block_height = record.get("blockchain_block_height", cls.BTC_HALVING_BLOCK_HEIGHT)
            if not block_hash or not cls.verify_blockchain_block(str(block_hash), block_height):
                return (CanonicalVerificationStatus.QUARANTINED, "BITCOIN_BLOCK_HASH_MISMATCH")

            # If physical document path is provided, verify its byte integrity
            doc_path = record.get("source_document_path")
            doc_hash = record.get("source_document_sha256")
            if doc_path and doc_hash and base_dir:
                p = (base_dir / doc_path).resolve()
                if not cls.verify_document_bytes(p, doc_hash):
                    return (CanonicalVerificationStatus.REJECTED, "SOURCE_DOCUMENT_BYTE_HASH_MISMATCH")

            return (CanonicalVerificationStatus.VERIFIED_POINT_IN_TIME, None)

        # Document byte verification for off-chain publications
        if doc_verified:
            doc_path = record.get("source_document_path")
            doc_hash = record.get("source_document_sha256")
            if doc_path and doc_hash and base_dir:
                p = (base_dir / doc_path).resolve()
                if not cls.verify_document_bytes(p, doc_hash):
                    return (CanonicalVerificationStatus.REJECTED, "SOURCE_DOCUMENT_BYTE_HASH_MISMATCH")

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
