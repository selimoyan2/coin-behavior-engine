"""Claim Integrity V4: Temporal Claim Integrity & Prospective Claim Registry.

Enforces:
- Temporal Claim Integrity: prediction_created_at < outcome_available_at.
- Strict rejection of hindsight language ("model predicted" requires immutable prospective record).
- Separate prospective claim registry.
- Prohibits premature commercial/trading claim statuses.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.claims.registry import (
    BANNED_CAUSAL_TRIGGERS,
    ALLOWED_ASSOCIATIVE_TERMS,
    SUPPORTED_SEMANTIC_OPERATORS,
)

logger = logging.getLogger(__name__)

def check_causal_language(claim_text: str, has_causal_identification: bool = False) -> Tuple[bool, str]:
    """Check for unverified causal language in prospective claim text."""
    if not has_causal_identification:
        text = claim_text.lower()
        for pattern in BANNED_CAUSAL_TRIGGERS:
            match = re.search(pattern, text)
            if match:
                return (
                    False,
                    f"Causal language violation: matched causal trigger '{match.group(0)}' "
                    f"without explicit causal identification",
                )
    return True, "Causal language integrity verified"

VALID_PROSPECTIVE_STATUSES = {
    "INSUFFICIENT_DATA",
    "EARLY_SUPPORT",
    "EARLY_CONTRADICTION",
    "STABLE_SO_FAR",
    "DEGRADING_SO_FAR",
    "MATURE_FOR_REVIEW",
}

BANNED_PROSPECTIVE_STATUSES = {
    "PROVEN",
    "PROFITABLE",
    "READY_TO_TRADE",
    "READY_FOR_LIVE_TRADING",
}


class TemporalClaimIntegrityViolation(Exception):
    """Raised when a prospective claim violates temporal causality."""
    pass


def parse_utc(dt_str: str) -> datetime:
    dt_str = dt_str.replace("Z", "+00:00").replace(" UTC", "+00:00")
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class ProspectiveClaim:
    claim_id: str
    claim_text: str
    metric_name: str
    metric_value: Any
    prediction_id: str
    prediction_created_at: str
    outcome_available_at: str
    prediction_hash: str
    sample_size: int
    horizon: str = "1h"
    artifact_path: str = ""
    artifact_row_or_key: str = ""
    status: str = "INSUFFICIENT_DATA"
    verification_notes: str = ""
    claim_semantic_operator: str = "LESS_THAN"
    comparison_baseline: float = 0.0
    has_causal_identification: bool = False
    evidence_status: str = "PENDING"
    temporal_valid: bool = False
    language_valid: bool = False


class ProspectiveClaimRegistry:
    """Manages prospective claims under Claim Integrity V4."""

    def __init__(self):
        self.claims: Dict[str, ProspectiveClaim] = {}

    def register_prospective_claim(
        self,
        claim_id: str,
        claim_text: str,
        metric_name: str,
        metric_value: Any,
        prediction_id: str,
        prediction_created_at: str,
        outcome_available_at: str,
        prediction_hash: str,
        sample_size: int,
        horizon: str = "1h",
        artifact_path: str = "",
        artifact_row_or_key: str = "",
        status: str = "INSUFFICIENT_DATA",
        verification_notes: str = "",
        claim_semantic_operator: str = "LESS_THAN",
        comparison_baseline: float = 0.0,
        has_causal_identification: bool = False,
    ) -> ProspectiveClaim:
        if status in BANNED_PROSPECTIVE_STATUSES:
            raise ValueError(
                f"Status '{status}' is prohibited during prospective observation. "
                f"Must be one of {VALID_PROSPECTIVE_STATUSES}"
            )

        if status not in VALID_PROSPECTIVE_STATUSES and status != "VERIFIED":
            status = "INSUFFICIENT_DATA"

        claim = ProspectiveClaim(
            claim_id=claim_id,
            claim_text=claim_text,
            metric_name=metric_name,
            metric_value=metric_value,
            prediction_id=prediction_id,
            prediction_created_at=prediction_created_at,
            outcome_available_at=outcome_available_at,
            prediction_hash=prediction_hash,
            sample_size=sample_size,
            horizon=horizon,
            artifact_path=artifact_path,
            artifact_row_or_key=artifact_row_or_key,
            status=status,
            verification_notes=verification_notes,
            claim_semantic_operator=claim_semantic_operator,
            comparison_baseline=comparison_baseline,
            has_causal_identification=has_causal_identification,
        )
        self.claims[claim_id] = claim
        return claim

    def verify_temporal_integrity(self, claim_id: str) -> Tuple[bool, str]:
        """Verify that prediction_created_at < outcome_available_at."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False, f"Claim {claim_id} not found"

        if not claim.prediction_created_at or not claim.outcome_available_at:
            return False, "Missing prediction_created_at or outcome_available_at"

        pred_dt = parse_utc(claim.prediction_created_at)
        outcome_dt = parse_utc(claim.outcome_available_at)

        if pred_dt >= outcome_dt:
            return False, (
                f"TEMPORAL LEAKAGE: prediction created at {claim.prediction_created_at} "
                f"is not strictly prior to outcome available at {claim.outcome_available_at}"
            )

        claim.temporal_valid = True
        return True, "PASSED"

    def verify_claim_language(self, claim_id: str) -> Tuple[bool, str]:
        """Verify absence of hindsight phrases and check causal language integrity."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False, f"Claim {claim_id} not found"

        # Check causal language
        causal_ok, reason = check_causal_language(claim.claim_text, claim.has_causal_identification)
        if not causal_ok:
            return False, reason

        # Check hindsight language: "the model predicted" requires verified prediction record
        if "the model predicted" in claim.claim_text.lower():
            if not claim.prediction_id or not claim.prediction_hash:
                return False, "Phrase 'the model predicted' used without immutable prediction proof."

        claim.language_valid = True
        return True, "PASSED"

    def audit_all_prospective_claims(self, out_file: Path) -> Dict[str, Any]:
        """Run complete Claim Integrity V4 audit."""
        records = []
        total = len(self.claims)
        verified = 0

        for c_id, c in self.claims.items():
            temp_ok, temp_msg = self.verify_temporal_integrity(c_id)
            lang_ok, lang_msg = self.verify_claim_language(c_id)

            passed = temp_ok and lang_ok
            if passed:
                verified += 1

            records.append({
                "claim_id": c_id,
                "status": c.status,
                "temporal_integrity": "PASSED" if temp_ok else "FAILED",
                "temporal_reason": temp_msg,
                "causal_and_hindsight_language": "PASSED" if lang_ok else "FAILED",
                "language_reason": lang_msg,
                "prediction_id": c.prediction_id,
                "prediction_created_at": c.prediction_created_at,
                "outcome_available_at": c.outcome_available_at,
                "prediction_hash": c.prediction_hash,
                "claim_text": c.claim_text,
            })

        out_data = {
            "audit_name": "PROSPECTIVE_CLAIM_INTEGRITY_V4",
            "total_claims": total,
            "verified_claims": verified,
            "failed_claims": total - verified,
            "audit_status": "PASSED" if (verified == total and total > 0) else ("NO_CLAIMS" if total == 0 else "FAILED"),
            "audit_records": records,
        }

        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2)

        return out_data

    def export_registry(self, out_file: Path) -> None:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        data = {c_id: asdict(c) for c_id, c in self.claims.items()}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
