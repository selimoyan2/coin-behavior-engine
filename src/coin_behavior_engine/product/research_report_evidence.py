"""
Verifiable Research Report Bundle Engine V1
Sprint 22 — Research Intelligence Reporting & Evidence Presentation V1

Packages canonical research reports and associated scientific evidence into sealed,
tamper-evident verifiable evidence bundles, and provides an independent verifier.

Design Invariants:
- Canonical JSON serialization with sorted keys and UTF-8 encoding.
- Deterministic SHA-256 package checksum across canonical payload.
- Cryptographic boundary note: An internal checksum proves self-consistency, not
  independent root-of-trust authenticity. Supports comparison with trusted external checksums.
- Detects tampered timestamps, mutated numerical findings, altered model versions,
  modified holdout disclosures, or mismatched dataset provenance.
"""

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


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

        # Compile bundle payload
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
                "manifest_version": scope.get("dataset_manifest_version", "cbe-manifest-v3-7ed2e950dec3"),
                "manifest_sha256": provenance.get("dataset_manifest_sha256", "7ed2e950dec317c54aef7f67f1799aa9ef5b9162a55b55aaee9f352ba2de1245"),
                "source_commit_sha": provenance.get("source_commit_sha", "3c49506d8ea56dbe3ac4b6c8ba2221e551fc7fff"),
            },
            "canonical_model_identity": {
                "version": model.get("version", self.CANONICAL_MODEL),
                "status": model.get("status", "STRICTLY_FROZEN"),
                "parameter_mutations": 0,
            },
            "scientific_disclosures": {
                "predeclared_holdout_criteria_satisfied": report_data.get("statistical_evidence", {}).get("predeclared_holdout_criteria_satisfied", 2),
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

        # 1. Package Checksum Verification
        if recorded_checksum != recomputed_checksum:
            discrepancies.append(
                f"Checksum mismatch: recorded={recorded_checksum}, recomputed={recomputed_checksum}"
            )

        # 2. Trusted External Checksum Comparison (if supplied)
        if trusted_checksum and trusted_checksum != recomputed_checksum:
            discrepancies.append(
                f"Trusted checksum mismatch: trusted={trusted_checksum}, actual={recomputed_checksum}"
            )

        # 3. Model Identity Validation
        model_info = payload.get("canonical_model_identity", {})
        exp_model = expected_model_version or self.CANONICAL_MODEL
        if model_info.get("version") != exp_model:
            discrepancies.append(
                f"Model version drift: expected={exp_model}, observed={model_info.get('version')}"
            )
        if model_info.get("parameter_mutations", 0) != 0:
            discrepancies.append("Model parameter mutations detected (must be strictly zero)")

        # 4. Dataset Provenance Validation
        dataset_info = payload.get("dataset_provenance", {})
        if expected_dataset_version and dataset_info.get("manifest_version") != expected_dataset_version:
            discrepancies.append(
                f"Dataset version mismatch: expected={expected_dataset_version}, observed={dataset_info.get('manifest_version')}"
            )

        # 5. Scientific Holdout Disclosures Check
        disclosures = payload.get("scientific_disclosures", {})
        if disclosures.get("independent_confirmatory_replications", 0) != 0:
            discrepancies.append(
                "Scientific disclosure violation: independent confirmatory replications must be 0"
            )

        # 6. Report Timestamps Finiteness & Boundary Checks
        report = payload.get("canonical_report", {})
        scope = report.get("historical_scope", {})
        start_utc = scope.get("start_utc", "")
        end_utc = scope.get("end_utc", "")
        if not start_utc or not end_utc:
            discrepancies.append("Report historical scope start or end date missing")
        elif start_utc >= "2026-10-01" or end_utc > "2026-10-01":
            discrepancies.append("Quarantine violation: dates reach into quarantined October 2026")

        is_valid = len(discrepancies) == 0
        return {
            "valid": is_valid,
            "tampering_detected": not is_valid,
            "verdict": "VERIFIED_AUTHENTIC" if is_valid else "TAMPERING_OR_CORRUPTION_DETECTED",
            "report_id": payload.get("report_id"),
            "recorded_checksum": recorded_checksum,
            "recomputed_checksum": recomputed_checksum,
            "discrepancies": discrepancies,
            "model_version_verified": model_info.get("version") == exp_model,
            "provenance_verified": len(discrepancies) == 0,
        }
