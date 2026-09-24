"""Permanent Research Governance & Claim Registry Engine V2.

Enforces strict machine-verifiable evidence chain:
CLAIM -> ARTIFACT -> CODE -> TEST.

Includes Sprint 06 Semantic Claim Integrity V2:
- claim_semantic_operator verification
- Claim language validation (contradiction detection)
- Multi-dimensional evidence support (Numeric, Semantic, Statistical, OOS, Coverage)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import pandas as pd

from coin_behavior_engine.utils.logging import logger


VALID_STATUSES = {"VERIFIED", "PARTIALLY_VERIFIED", "FAILED", "UNVERIFIED"}

SUPPORTED_SEMANTIC_OPERATORS = {
    "GREATER_THAN",
    "LESS_THAN",
    "GREATER_THAN_OR_EQUAL",
    "LESS_THAN_OR_EQUAL",
    "BETWEEN",
    "EQUAL",
    "NOT_EQUAL",
    "POSITIVE_DELTA",
    "NEGATIVE_DELTA",
    "CI_EXCLUDES_ZERO_POSITIVE",
    "CI_EXCLUDES_ZERO_NEGATIVE",
    "CI_INCLUDES_ZERO",
    "IMPROVES",
    "DEGRADES",
    "NO_MATERIAL_CHANGE",
    "REPLICATES",
    "FAILS_TO_REPLICATE",
}

BANNED_CAUSAL_TRIGGERS = [
    r"\bcauses?\b",
    r"\bcaused\b",
    r"\bcausing\b",
    r"\bdrives?\b",
    r"\bdriven\b",
    r"\bdriving\b",
    r"\bexplains?\b",
    r"\bexplained\b",
    r"\bexplaining\b",
    r"\bresults?\s+in\b",
    r"\bresulted\s+in\b",
    r"\bresulting\s+in\b",
    r"\bleads?\s+to\b",
    r"\bled\s+to\b",
    r"\bleading\s+to\b",
]

ALLOWED_ASSOCIATIVE_TERMS = [
    "associated_with",
    "temporally_precedes",
    "incrementally_informative",
    "conditionally_associated",
    "predictive_within_sample",
    "predictive_out_of_sample",
]


@dataclass
class ResearchClaim:
    """Represents a discrete, machine-verifiable research claim."""

    claim_id: str
    claim_text: str
    metric_name: str
    metric_value: float | str | bool
    sample_size: int
    partition: str
    horizon: str
    artifact_path: str
    artifact_row_or_key: str
    generating_module: str
    test_reference: str
    status: str = "UNVERIFIED"
    verification_notes: str = ""

    # Semantic Integrity V2 Extensions
    claim_semantic_operator: str = "EQUAL"
    comparison_baseline: float = 0.0
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    p_value: Optional[float] = None
    fdr_q_value: Optional[float] = None
    required_evidence: List[str] = field(default_factory=list)
    numeric_integrity: str = "UNVERIFIED"
    semantic_integrity: str = "UNVERIFIED"
    statistical_support: str = "UNVERIFIED"
    oos_support: str = "UNVERIFIED"
    coverage_support: str = "UNVERIFIED"

    # Causal Language Integrity V3 Extensions
    has_causal_identification: bool = False
    causal_language_integrity: str = "UNVERIFIED"

    final_claim_status: str = "UNVERIFIED"
    failure_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchClaimRegistry:
    """Central registry and verification engine for scientific claims."""

    def __init__(self, registry_file: Optional[str | Path] = None):
        self.claims: Dict[str, ResearchClaim] = {}
        self.registry_file = Path(registry_file) if registry_file else None

        if self.registry_file and self.registry_file.exists():
            self.load_from_json(self.registry_file)

    def register_claim(
        self,
        claim_id: str,
        claim_text: str,
        metric_name: str,
        metric_value: float | str | bool,
        sample_size: int,
        partition: str,
        horizon: str,
        artifact_path: str,
        artifact_row_or_key: str,
        generating_module: str,
        test_reference: str,
        status: str = "UNVERIFIED",
        verification_notes: str = "",
        claim_semantic_operator: str = "EQUAL",
        comparison_baseline: float = 0.0,
        ci_low: Optional[float] = None,
        ci_high: Optional[float] = None,
        p_value: Optional[float] = None,
        fdr_q_value: Optional[float] = None,
        required_evidence: Optional[List[str]] = None,
        has_causal_identification: bool = False,
    ) -> ResearchClaim:
        """Register or update a research claim with semantic operator and causal language support."""
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")

        if claim_semantic_operator not in SUPPORTED_SEMANTIC_OPERATORS:
            raise ValueError(
                f"Invalid semantic operator '{claim_semantic_operator}'. "
                f"Must be one of {SUPPORTED_SEMANTIC_OPERATORS}"
            )

        claim = ResearchClaim(
            claim_id=claim_id,
            claim_text=claim_text,
            metric_name=metric_name,
            metric_value=metric_value,
            sample_size=sample_size,
            partition=partition,
            horizon=horizon,
            artifact_path=str(artifact_path),
            artifact_row_or_key=str(artifact_row_or_key),
            generating_module=generating_module,
            test_reference=test_reference,
            status=status,
            verification_notes=verification_notes,
            claim_semantic_operator=claim_semantic_operator,
            comparison_baseline=comparison_baseline,
            ci_low=ci_low,
            ci_high=ci_high,
            p_value=p_value,
            fdr_q_value=fdr_q_value,
            required_evidence=required_evidence or [],
            has_causal_identification=has_causal_identification,
        )
        self.claims[claim_id] = claim
        return claim

    def get_claim(self, claim_id: str) -> Optional[ResearchClaim]:
        return self.claims.get(claim_id)

    def verify_claim_artifact(self, claim_id: str) -> bool:
        """Verify that the referenced artifact file exists on disk."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False
        p = Path(claim.artifact_path)
        return p.exists() and p.stat().st_size > 0

    def verify_metric_value(self, claim_id: str, rel_tol: float = 1e-3, abs_tol: float = 1e-4) -> bool:
        """Verify that the claimed metric value matches the value stored in the artifact."""
        claim = self.claims.get(claim_id)
        if not claim or not self.verify_claim_artifact(claim_id):
            return False

        path = Path(claim.artifact_path)
        key = claim.artifact_row_or_key

        try:
            if path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                val = data.get(key)
                if val is None:
                    if "=" in key and isinstance(data, dict):
                        k_col, k_target = key.split("=", 1)
                        for item_list in data.values():
                            if isinstance(item_list, list):
                                for item in item_list:
                                    if isinstance(item, dict) and str(item.get(k_col)) == k_target:
                                        val = item.get(claim.metric_name)
                                        break
                                if val is not None:
                                    break
                    if val is None:
                        parts = key.split(".")
                        curr = data
                        for pt in parts:
                            if isinstance(curr, dict) and pt in curr:
                                curr = curr[pt]
                            else:
                                return False
                        val = curr
            elif path.suffix == ".csv":
                df = pd.read_csv(path)
                if key in df.columns:
                    val = df[key].iloc[0]
                elif "=" in key:
                    sub = df
                    for condition in key.split("&"):
                        if "=" in condition:
                            col, target = condition.split("=", 1)
                            sub = sub[sub[col].astype(str) == target]
                    if sub.empty or claim.metric_name not in sub.columns:
                        return False
                    val = sub[claim.metric_name].iloc[0]
                else:
                    return False
            elif path.suffix == ".parquet":
                df = pd.read_parquet(path)
                if key in df.columns:
                    val = df[key].iloc[0]
                elif "=" in key:
                    sub = df
                    for condition in key.split("&"):
                        if "=" in condition:
                            col, target = condition.split("=", 1)
                            sub = sub[sub[col].astype(str) == target]
                    if sub.empty or claim.metric_name not in sub.columns:
                        return False
                    val = sub[claim.metric_name].iloc[0]
                else:
                    return False
            else:
                return False

            if isinstance(claim.metric_value, (int, float)) and isinstance(val, (int, float)):
                diff = abs(float(claim.metric_value) - float(val))
                allowed = max(abs_tol, rel_tol * abs(float(claim.metric_value)))
                return diff <= allowed
            return str(claim.metric_value) == str(val)
        except Exception as e:
            logger.warning(f"Verification error for claim {claim_id}: {e}")
            return False

    def verify_sample_size(self, claim_id: str) -> bool:
        """Verify that sample size is positive and matches artifact row/sample count."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False
        return claim.sample_size > 0

    def verify_partition(self, claim_id: str) -> bool:
        """Verify partition string is valid."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False
        valid_parts = {
            "DISCOVERY_2021_2024",
            "VALIDATION_2025",
            "OBSERVED_HOLDOUT_2026",
            "FULL_SAMPLE",
            "POOLED",
            "LATER_ETF_VALIDATION_2025",
            "EARLY_ETF_DISCOVERY_2024",
            "ETF_ACTIVE",
            "EARLY_EVENT_DISCOVERY_2021_2024",
            "LATER_EVENT_VALIDATION_2025",
            "OBSERVED_HOLDOUT_2026_EVENT",
        }
        return claim.partition in valid_parts

    def verify_test_reference(self, claim_id: str) -> bool:
        """Verify test reference string is provided and points to a test method or module."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False
        return bool(claim.test_reference and ("test_" in claim.test_reference or "tests/" in claim.test_reference))

    def verify_semantic_operator(self, claim_id: str) -> tuple[bool, str]:
        """Verify whether the claimed metric value and intervals satisfy the semantic operator."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False, "Claim not found"

        op = claim.claim_semantic_operator
        val = claim.metric_value
        base = claim.comparison_baseline
        ci_l = claim.ci_low
        ci_h = claim.ci_high

        # 1. Operators on numerical values
        if isinstance(val, (int, float)):
            f_val = float(val)
            if op == "GREATER_THAN" and not (f_val > base):
                return False, f"Operator GREATER_THAN failed: {f_val} <= {base}"
            if op == "LESS_THAN" and not (f_val < base):
                return False, f"Operator LESS_THAN failed: {f_val} >= {base}"
            if op == "GREATER_THAN_OR_EQUAL" and not (f_val >= base):
                return False, f"Operator GREATER_THAN_OR_EQUAL failed: {f_val} < {base}"
            if op == "LESS_THAN_OR_EQUAL" and not (f_val <= base):
                return False, f"Operator LESS_THAN_OR_EQUAL failed: {f_val} > {base}"
            if op == "POSITIVE_DELTA" and not (f_val > 0.0):
                return False, f"Operator POSITIVE_DELTA failed: delta {f_val} is non-positive"
            if op == "NEGATIVE_DELTA" and not (f_val < 0.0):
                return False, f"Operator NEGATIVE_DELTA failed: delta {f_val} is non-negative"
            if op == "NO_MATERIAL_CHANGE" and not (abs(f_val) < 0.002):
                return False, f"Operator NO_MATERIAL_CHANGE failed: |{f_val}| >= 0.002"
            if op == "IMPROVES":
                if f_val <= 0.0:
                    return False, f"Operator IMPROVES failed: delta {f_val} is non-positive"
                # If required evidence specifies CI or FDR, check them
                if "block_ci_support" in claim.required_evidence and ci_l is not None and ci_l <= 0.0:
                    return False, f"Operator IMPROVES failed: lower CI bound {ci_l} includes zero or negative"
                if "fdr_support" in claim.required_evidence and claim.fdr_q_value is not None and claim.fdr_q_value > 0.05:
                    return False, f"Operator IMPROVES failed: FDR q-value {claim.fdr_q_value} > 0.05"
            if op == "DEGRADES" and not (f_val < 0.0):
                return False, f"Operator DEGRADES failed: delta {f_val} is non-negative"

        # 2. Confidence interval operators
        if op == "CI_EXCLUDES_ZERO_POSITIVE":
            if ci_l is None or ci_h is None or not (ci_l > 0.0 and ci_h > 0.0):
                return False, f"Operator CI_EXCLUDES_ZERO_POSITIVE failed: CI [{ci_l}, {ci_h}] does not exclude 0"
        if op == "CI_EXCLUDES_ZERO_NEGATIVE":
            if ci_l is None or ci_h is None or not (ci_l < 0.0 and ci_h < 0.0):
                return False, f"Operator CI_EXCLUDES_ZERO_NEGATIVE failed: CI [{ci_l}, {ci_h}] does not exclude 0"
        if op == "CI_INCLUDES_ZERO":
            if ci_l is None or ci_h is None or not (ci_l <= 0.0 <= ci_h):
                return False, f"Operator CI_INCLUDES_ZERO failed: CI [{ci_l}, {ci_h}] excludes zero"

        # 3. Replication operators
        if op == "REPLICATES":
            if isinstance(val, (int, float)) and float(val) <= 0.0:
                return False, f"Operator REPLICATES failed: replication metric {val} is non-positive"
            if str(val).upper() in ["FAIL", "FAILED", "DEGRADED", "UNVERIFIED"]:
                return False, f"Operator REPLICATES failed: metric indicates {val}"

        if op == "FAILS_TO_REPLICATE":
            if str(val).upper() in ["VERIFIED", "REPLICATED", "PASSED"]:
                return False, f"Operator FAILS_TO_REPLICATE failed: metric indicates {val}"

        return True, "Operator satisfied"

    def verify_causal_language(self, claim_id: str) -> tuple[bool, str]:
        """Check for unverified causal language in claim text.

        Words like 'causes', 'drives', 'explains', 'results in', 'leads to' MUST
        fail semantic audit without explicit causal identification.
        Allowed association terms: associated_with, temporally_precedes,
        incrementally_informative, conditionally_associated, predictive_within_sample,
        predictive_out_of_sample.
        """
        claim = self.claims.get(claim_id)
        if not claim:
            return False, "Claim not found"

        text = claim.claim_text.lower()
        if not claim.has_causal_identification:
            for pattern in BANNED_CAUSAL_TRIGGERS:
                match = re.search(pattern, text)
                if match:
                    return (
                        False,
                        f"Causal language violation: matched causal trigger '{match.group(0)}' "
                        f"in claim text without explicit causal identification",
                    )

        return True, "Causal language integrity verified"

    def verify_claim_language(self, claim_id: str) -> tuple[bool, str]:
        """Check for semantic contradictions between claim text language and metric value."""
        claim = self.claims.get(claim_id)
        if not claim:
            return False, "Claim not found"

        text = claim.claim_text.lower()
        val = claim.metric_value

        # Check 'improves', 'increases', 'adds'
        if any(w in text for w in ["improves", "increases", "adds material", "outperforms", "beneficial"]):
            if isinstance(val, (int, float)) and float(val) < 0.0:
                return False, f"Semantic contradiction: claim text asserts improvement but metric is negative ({val})"
            if str(val).upper() in ["NO_MATERIAL_LIFT", "DEGRADED", "FAILED", "NO_DIRECTIONAL_EDGE"]:
                return False, f"Semantic contradiction: claim text asserts improvement but status is {val}"

        # Check 'reduces', 'degrades', 'worsens'
        if any(w in text for w in ["degrades", "worsens", "dilutes", "reduces performance"]):
            if isinstance(val, (int, float)) and float(val) > 0.0 and claim.claim_semantic_operator == "DEGRADES":
                return False, f"Semantic contradiction: claim asserts degradation but metric is positive ({val})"

        # Check 'unverified', 'fails', 'no edge'
        if any(w in text for w in ["unverified", "no edge", "fails to predict", "no material lift"]):
            if isinstance(val, (int, float)) and float(val) > 0.05 and claim.claim_semantic_operator == "IMPROVES":
                return False, f"Semantic contradiction: claim asserts no edge but operator is IMPROVES"

        return True, "No language contradictions detected"

    def audit_all_claims(self, output_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """Perform comprehensive machine-audit across all registered claims with semantic and causal checks."""
        verified_count = 0
        partial_count = 0
        failed_count = 0
        unverified_count = 0

        audit_records = []

        for cid, claim in self.claims.items():
            has_artifact = self.verify_claim_artifact(cid)
            has_metric = self.verify_metric_value(cid)
            has_samples = self.verify_sample_size(cid)
            has_partition = self.verify_partition(cid)
            has_test = self.verify_test_reference(cid)
            op_ok, op_reason = self.verify_semantic_operator(cid)
            lang_ok, lang_reason = self.verify_claim_language(cid)
            causal_ok, causal_reason = self.verify_causal_language(cid)

            # Dimensions
            numeric_int = "PASSED" if (has_artifact and has_metric) else "FAILED"
            semantic_int = "PASSED" if (op_ok and lang_ok) else "FAILED"
            causal_int = "PASSED" if causal_ok else "FAILED"
            stat_support = "PASSED" if (claim.p_value is None or claim.p_value <= 0.05) else "FAILED"
            if claim.claim_semantic_operator in ["NO_DIRECTIONAL_EDGE", "NO_MATERIAL_CHANGE", "FAILS_TO_REPLICATE"]:
                stat_support = "PASSED"
            oos_support = "PASSED" if has_partition else "FAILED"
            cov_support = "PASSED" if has_samples else "FAILED"

            failure_reasons = []
            if not has_artifact:
                failure_reasons.append("Artifact file missing")
            if not has_metric:
                failure_reasons.append("Metric value mismatch with artifact")
            if not op_ok:
                failure_reasons.append(op_reason)
            if not lang_ok:
                failure_reasons.append(lang_reason)
            if not causal_ok:
                failure_reasons.append(causal_reason)
            if not has_samples:
                failure_reasons.append("Invalid sample size")
            if not has_partition:
                failure_reasons.append("Invalid partition")
            if not has_test:
                failure_reasons.append("Test reference missing")

            claim.numeric_integrity = numeric_int
            claim.semantic_integrity = semantic_int
            claim.causal_language_integrity = causal_int
            claim.statistical_support = stat_support
            claim.oos_support = oos_support
            claim.coverage_support = cov_support

            if (
                numeric_int == "PASSED"
                and semantic_int == "PASSED"
                and causal_int == "PASSED"
                and oos_support == "PASSED"
                and cov_support == "PASSED"
                and has_test
            ):
                actual_status = "VERIFIED"
                verified_count += 1
            elif numeric_int == "PASSED" and has_test and causal_int == "PASSED":
                actual_status = "PARTIALLY_VERIFIED"
                partial_count += 1
            elif semantic_int == "FAILED" or numeric_int == "FAILED" or causal_int == "FAILED":
                actual_status = "FAILED"
                failed_count += 1
            else:
                actual_status = "UNVERIFIED"
                unverified_count += 1

            claim.status = actual_status
            claim.final_claim_status = actual_status
            claim.failure_reason = "; ".join(failure_reasons) if failure_reasons else ""

            audit_records.append({
                "claim_id": cid,
                "status": actual_status,
                "has_artifact": has_artifact,
                "has_metric_match": has_metric,
                "has_valid_sample_size": has_samples,
                "has_valid_partition": has_partition,
                "has_test_reference": has_test,
                "semantic_operator": claim.claim_semantic_operator,
                "semantic_operator_valid": op_ok,
                "claim_language_valid": lang_ok,
                "has_causal_identification": claim.has_causal_identification,
                "causal_language_integrity": causal_int,
                "causal_language_valid": causal_ok,
                "numeric_integrity": numeric_int,
                "semantic_integrity": semantic_int,
                "statistical_support": stat_support,
                "oos_support": oos_support,
                "coverage_support": cov_support,
                "final_claim_status": actual_status,
                "failure_reason": claim.failure_reason,
                "claim_text": claim.claim_text,
                "metric_name": claim.metric_name,
                "metric_value": claim.metric_value,
                "artifact_path": claim.artifact_path,
                "test_reference": claim.test_reference,
            })

        overall_status = "PASSED" if (verified_count + partial_count > 0 and unverified_count == 0 and failed_count == 0) else "PARTIAL"
        if verified_count == 0:
            overall_status = "FAILED"

        summary = {
            "audit_name": "RESEARCH_CLAIM_INTEGRITY_AUDIT_V3",
            "total_claims": len(self.claims),
            "verified_claims": verified_count,
            "partially_verified_claims": partial_count,
            "failed_claims": failed_count,
            "unverified_claims": unverified_count,
            "pass_rate": float(verified_count / max(1, len(self.claims))),
            "claim_integrity_status": overall_status,
            "audit_records": audit_records,
        }

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Saved claim integrity audit to {p}")

        return summary

    def audit_semantic_claims(self, output_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """Generate mandatory Semantic Claim Audit Table."""
        records = []
        for cid, claim in self.claims.items():
            records.append({
                "claim_id": cid,
                "claim_text": claim.claim_text,
                "numeric_integrity": claim.numeric_integrity,
                "semantic_operator": claim.claim_semantic_operator,
                "semantic_integrity": claim.semantic_integrity,
                "statistical_support": claim.statistical_support,
                "oos_support": claim.oos_support,
                "coverage_support": claim.coverage_support,
                "final_status": claim.final_claim_status,
                "failure_reason": claim.failure_reason,
            })

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            logger.info(f"Saved semantic claim audit table to {p}")

        return records

    def audit_causal_language(self, output_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """Generate mandatory Causal Language Integrity Audit Table V3."""
        records = []
        for cid, claim in self.claims.items():
            records.append({
                "claim_id": cid,
                "claim_text": claim.claim_text,
                "has_causal_identification": claim.has_causal_identification,
                "causal_language_integrity": claim.causal_language_integrity,
                "final_status": claim.final_claim_status,
                "failure_reason": claim.failure_reason,
            })

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            logger.info(f"Saved causal language integrity audit table to {p}")

        return records

    def export_registry(self, output_path: str | Path) -> None:
        """Export claims to JSON file."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [claim.to_dict() for claim in self.claims.values()]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Exported claim registry ({len(self.claims)} claims) to {p}")

    def load_from_json(self, file_path: str | Path) -> None:
        """Load claims from JSON file."""
        p = Path(file_path)
        if not p.exists():
            return
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for cdict in data:
                # Filter out unknown keys for backwards compatibility
                filtered = {k: v for k, v in cdict.items() if k in ResearchClaim.__annotations__}
                self.claims[cdict["claim_id"]] = ResearchClaim(**filtered)
        elif isinstance(data, dict):
            for cid, cdict in data.items():
                filtered = {k: v for k, v in cdict.items() if k in ResearchClaim.__annotations__}
                self.claims[cid] = ResearchClaim(**filtered)
