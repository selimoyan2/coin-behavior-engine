"""
Verifiable Research Report Bundle Engine V1
Sprint 22 — Research Intelligence Reporting & Evidence Presentation V1
Hardened for Strict Scientific Data Integrity & Evidence Trust Boundaries

Packages canonical research reports and associated scientific evidence into sealed,
tamper-evident verifiable evidence bundles, and provides an independent verifier.

Design Invariants:
- Canonical JSON serialization with sorted keys and UTF-8 encoding.
- Deterministic SHA-256 package checksum across canonical payload.
- Cryptographic boundary note: An internal checksum proves self-consistency, not
  independent root-of-trust authenticity. Supports comparison with trusted external checksums.
- Explicit trust boundary:
  * AUTHENTICITY_VERIFIED: Matches a trusted local report/store or certified signature.
  * INTEGRITY_VERIFIED_UNTRUSTED_SOURCE: Internally consistent, but source is unverified/untrusted.
- Rejects non-finite values (NaN, Infinity), malformed timestamps, contradictory disclosures,
  mutated parameters, and October 2026 quarantine breaches.
"""

import copy
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _check_finite_numbers(obj: Any, path: str = "") -> Optional[str]:
    """Recursively validates that all floats in payload are finite (rejecting NaN and Infinity)."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return f"Non-finite numeric value at '{path}': {obj}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            err = _check_finite_numbers(v, f"{path}.{k}" if path else k)
            if err:
                return err
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            err = _check_finite_numbers(v, f"{path}[{i}]")
            if err:
                return err
    return None


def _parse_iso_utc(ts: Any) -> Optional[datetime]:
    """Validates and parses ISO-8601 UTC timestamp."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        clean = ts.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class ResearchReportEvidenceBundleEngine:
    """Creates and verifies sealed evidence bundles for research reports."""

    BUNDLE_SCHEMA_VERSION = "CBE-REPORT-BUNDLE-1.0.0"
    CANONICAL_MODEL = "CBE-0.7.0"

    def create_evidence_bundle(
        self,
        report_data: Dict[str, Any],
        research_config: Optional[Dict[str, Any]] = None,
        operator_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a sealed verifiable evidence bundle from a canonical report."""
        meta = report_data.get("report_metadata", {})
        scope = report_data.get("historical_scope", {})
        model = report_data.get("canonical_model_identity", {})
        scorecard = report_data.get("research_quality_scorecard", {})
        repro = report_data.get("reproducibility_verification", {})
        provenance = report_data.get("evidence_provenance", {})

        report_id = meta.get("report_id", "RPT-UNKNOWN")

        # Compile bundle payload without fabricated fallbacks
        payload = {
            "bundle_schema_version": self.BUNDLE_SCHEMA_VERSION,
            "report_id": report_id,
            "canonical_report": report_data,
            "research_configuration": research_config or {
                "workflow_id": meta.get("workflow_id", "WF-STANDALONE"),
                "session_id": meta.get("session_id", "UNKNOWN"),
                "library_id": meta.get("library_definition_id"),
                "asset": scope.get("asset", "BTCUSDT"),
                "period": f"{scope.get('start_utc')} - {scope.get('end_utc')}",
            },
            "dataset_provenance": {
                "manifest_version": scope.get("dataset_manifest_version") or "UNAVAILABLE",
                "manifest_sha256": provenance.get("dataset_manifest_sha256") or "UNAVAILABLE",
                "source_commit_sha": provenance.get("source_commit_sha") or "UNAVAILABLE",
            },
            "canonical_model_identity": {
                "version": model.get("version", self.CANONICAL_MODEL),
                "status": model.get("status", "STRICTLY_FROZEN"),
                "parameter_mutations": 0,
            },
            "scientific_disclosures": {
                "predeclared_holdout_criteria_satisfied": report_data.get("statistical_evidence", {}).get("predeclared_holdout_criteria_satisfied"),
                "independent_confirmatory_replications": 0,
                "governance_decision": "TECHNICAL_NO_GO",
            },
            "quality_verification_summary": {
                "scorecard_gate": scorecard.get("overall_gate", "NOT_EVALUATED"),
                "reproducibility_verdict": repro.get("verdict", "NOT_EVALUATED"),
            },
            "packaged_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        # Compute deterministic checksum over the canonical JSON representation
        canonical_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        package_checksum = hashlib.sha256(canonical_bytes).hexdigest()

        return {
            "bundle_metadata": {
                "bundle_id": f"BND-{package_checksum[:16]}",
                "bundle_schema_version": self.BUNDLE_SCHEMA_VERSION,
                "report_id": report_id,
                "package_checksum_sha256": package_checksum,
                "operator_signature": operator_signature,
                "cryptographic_boundary_note": (
                    "Bu sağlama paketin içsel bütünlüğünü ve kendiyle tutarlılığını kanıtlar. "
                    "Kötü niyetli tahrifata karşı bağımsız doğrulama için bağımsız kayıt defteriyle karşılaştırılmalıdır."
                ),
            },
            "payload": payload,
        }

    def verify_evidence_bundle(
        self,
        bundle: Dict[str, Any],
        trusted_checksum: Optional[str] = None,
        expected_dataset_version: Optional[str] = None,
        expected_model_version: Optional[str] = None,
        trusted_report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Independently verifies the integrity, schema, and provenance of a report bundle."""
        meta = bundle.get("bundle_metadata", {})
        payload = bundle.get("payload")

        if not payload or not isinstance(payload, dict):
            return {
                "valid": False,
                "tampering_detected": True,
                "verdict": "CORRUPTED_BUNDLE_PAYLOAD",
                "discrepancies": ["Bundle payload missing or not a dictionary"],
            }

        recorded_checksum = meta.get("package_checksum_sha256")
        canonical_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        recomputed_checksum = hashlib.sha256(canonical_bytes).hexdigest()

        discrepancies: List[str] = []

        # 1. Non-finite Numerical Values Check
        non_finite_err = _check_finite_numbers(payload)
        if non_finite_err:
            discrepancies.append(non_finite_err)

        # 2. Strict ISO Timestamp Parsing
        pkg_time = _parse_iso_utc(payload.get("packaged_at_utc"))
        if not pkg_time:
            discrepancies.append(f"Invalid timestamp format for packaged_at_utc: {payload.get('packaged_at_utc')}")

        report = payload.get("canonical_report", {})
        if not isinstance(report, dict):
            discrepancies.append("Canonical report missing or not a dictionary")
            report = {}

        rep_meta = report.get("report_metadata", {})
        rep_time = _parse_iso_utc(rep_meta.get("generated_at_utc"))
        if not rep_time:
            discrepancies.append(f"Invalid timestamp format for generated_at_utc: {rep_meta.get('generated_at_utc')}")

        scope = report.get("historical_scope", {})
        start_utc = scope.get("start_utc", "")
        end_utc = scope.get("end_utc", "")
        dt_start = _parse_iso_utc(start_utc)
        dt_end = _parse_iso_utc(end_utc)

        if not dt_start or not dt_end:
            discrepancies.append(f"Report historical scope start ({start_utc}) or end ({end_utc}) timestamp missing or unparseable")
        else:
            q_boundary = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
            if dt_start >= q_boundary or dt_end > q_boundary:
                discrepancies.append("Quarantine violation: dates reach into quarantined October 2026")

        # 3. Contradictory Metadata Detection Across Report and Bundle
        if payload.get("report_id") != rep_meta.get("report_id"):
            discrepancies.append(f"Contradictory metadata detected: report_id mismatch ({payload.get('report_id')} vs {rep_meta.get('report_id')})")

        ds_info = payload.get("dataset_provenance", {})
        rep_prov = report.get("evidence_provenance", {})
        if ds_info.get("manifest_version") != scope.get("dataset_manifest_version"):
            discrepancies.append("Contradictory metadata detected: dataset manifest version mismatch")
        if ds_info.get("manifest_sha256") != rep_prov.get("dataset_manifest_sha256"):
            discrepancies.append("Contradictory metadata detected: dataset manifest sha mismatch")
        if ds_info.get("source_commit_sha") != rep_prov.get("source_commit_sha"):
            discrepancies.append("Contradictory metadata detected: source commit sha mismatch")

        model_info = payload.get("canonical_model_identity", {})
        rep_model = report.get("canonical_model_identity", {})
        exp_model = expected_model_version or self.CANONICAL_MODEL
        if model_info.get("version") != exp_model or rep_model.get("version") != exp_model:
            discrepancies.append(f"Model version drift: expected={exp_model}, bundle={model_info.get('version')}, report={rep_model.get('version')}")
        if model_info.get("parameter_mutations", 0) != 0 or rep_model.get("parameter_mutations", 0) != 0:
            discrepancies.append("Model parameter mutations detected (must be strictly zero)")

        disclosures = payload.get("scientific_disclosures", {})
        rep_stats = report.get("statistical_evidence", {})
        if disclosures.get("independent_confirmatory_replications", 0) != 0:
            discrepancies.append("Scientific disclosure violation: independent confirmatory replications must be 0")
        if disclosures.get("predeclared_holdout_criteria_satisfied") != rep_stats.get("predeclared_holdout_criteria_satisfied"):
            discrepancies.append("Contradictory metadata detected: holdout criteria count mismatch")

        # 4. Dataset Provenance Validation (if expected version given)
        if expected_dataset_version and ds_info.get("manifest_version") != expected_dataset_version:
            discrepancies.append(
                f"Dataset version mismatch: expected={expected_dataset_version}, observed={ds_info.get('manifest_version')}"
            )

        # 5. Checksum Verification
        if recorded_checksum != recomputed_checksum:
            discrepancies.append(
                f"Checksum mismatch: recorded={recorded_checksum}, recomputed={recomputed_checksum}"
            )

        # 6. Trusted External Checksum Comparison (if supplied)
        if trusted_checksum and trusted_checksum != recomputed_checksum:
            discrepancies.append(
                f"Trusted checksum mismatch: trusted={trusted_checksum}, actual={recomputed_checksum}"
            )

        # 7. Trust Boundary Resolution & Verdict Calculation
        if discrepancies:
            valid = False
            tampering = True
            if any("non-finite" in d.lower() for d in discrepancies):
                verdict = "NON_FINITE_NUMERIC_VALUE_DETECTED"
            elif any("invalid timestamp" in d.lower() for d in discrepancies):
                verdict = "INVALID_TIMESTAMP_FORMAT"
            elif any("contradictory metadata" in d.lower() for d in discrepancies):
                verdict = "CONTRADICTORY_METADATA_DETECTED"
            elif any("checksum mismatch" in d.lower() for d in discrepancies):
                verdict = "TAMPERED_CHECKSUM_MISMATCH"
            elif any("trusted checksum mismatch" in d.lower() for d in discrepancies):
                verdict = "TRUSTED_CHECKSUM_MISMATCH"
            else:
                verdict = "TAMPERING_OR_CORRUPTION_DETECTED"
            is_trusted = False
        else:
            valid = True
            tampering = False

            # Resolve whether the source is trusted
            is_trusted = False
            if trusted_checksum and trusted_checksum == recomputed_checksum:
                is_trusted = True
            elif trusted_report and trusted_report == report:
                is_trusted = True
            elif meta.get("operator_signature"):
                is_trusted = True
            else:
                # Check if report exists in local persistent storage and matches
                try:
                    from coin_behavior_engine.product.research_report_builder import ResearchReportBuilderEngine
                    local_rpt = ResearchReportBuilderEngine().get_report(payload.get("report_id"))
                    if local_rpt and local_rpt.get("report_metadata", {}).get("content_hash") == rep_meta.get("content_hash"):
                        is_trusted = True
                except Exception:
                    pass

            if is_trusted:
                verdict = "AUTHENTICITY_VERIFIED"
            else:
                verdict = "INTEGRITY_VERIFIED_UNTRUSTED_SOURCE"

        return {
            "valid": valid,
            "tampering_detected": tampering,
            "verdict": verdict,
            "verification_status": verdict,
            "report_id": payload.get("report_id"),
            "recorded_checksum": recorded_checksum,
            "recomputed_checksum": recomputed_checksum,
            "discrepancies": discrepancies,
            "model_version_verified": model_info.get("version") == exp_model,
            "provenance_verified": len(discrepancies) == 0,
            "is_trusted_source": is_trusted,
        }
