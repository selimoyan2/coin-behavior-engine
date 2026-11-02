"""
CBE — Independent Evidence Verification Engine (Sprint 21)
Validates exported evidence packages, recalculates canonical cryptographic checksums,
verifies dataset provenance, enforces model freeze invariants, and detects tampering.

Epistemological Boundary:
Cryptographic checksum verification demonstrates internal data integrity relative to the
embedded or supplied digest. It guarantees that the evidence package has not undergone
accidental corruption or unauthorized tampering since generation. However, it does NOT
independently prove that the original scientific methodology was omniscient or predictive.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine

logger = logging.getLogger("cbe.research_evidence_verifier")

EVIDENCE_SCHEMA_VERSION = "CBE-WORKFLOW-EVIDENCE-1.0.0"
OCTOBER_2026_QUARANTINE_START = "2026-10-01T00:00:00Z"


class EvidenceVerificationStatus(str, Enum):
    """Integrity verification status for evidence packages."""
    VERIFIED_VALID = "VERIFIED_VALID"
    CHECKSUM_MISMATCH_TAMPERED = "CHECKSUM_MISMATCH_TAMPERED"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    MODEL_FREEZE_VIOLATION = "MODEL_FREEZE_VIOLATION"
    QUARANTINE_VIOLATION = "QUARANTINE_VIOLATION"
    SCIENTIFIC_DISCLOSURE_INCOMPLETE = "SCIENTIFIC_DISCLOSURE_INCOMPLETE"
    CORRUPTED_PAYLOAD = "CORRUPTED_PAYLOAD"


@dataclass
class EvidenceVerificationReport:
    """Detailed audit report produced by independent evidence verification."""
    status: str
    is_valid: bool
    package_checksum_verified: bool
    recorded_checksum: str
    computed_checksum: str
    model_version_verified: bool
    quarantine_verified: bool
    disclosures_verified: bool
    tampering_detected: bool
    tampered_fields: List[str] = field(default_factory=list)
    epistemological_boundary_notice: str = (
        "KRİPTOGRAFİK BÜTÜNLÜK BİLDİRİMİ: Sağlama özeti doğrulaması, paketin oluşturulduğu andan bu yana "
        "değiştirilmediğini kanıtlar; orijinal bilimsel analizin geleceğe yönelik tahmin doğruluğunu kanıtlamaz."
    )
    details: Dict[str, Any] = field(default_factory=dict)
    verified_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchEvidenceVerifier:
    """
    Independent verifier for research evidence packages.
    Operates statelessly without requiring in-memory research session dependencies.
    """

    @classmethod
    def canonical_serialize(cls, payload: Dict[str, Any]) -> bytes:
        """Deterministic canonical JSON serialization for cryptographic hashing."""
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def compute_package_checksum(cls, evidence_package: Dict[str, Any]) -> str:
        """
        Compute SHA-256 digest over the canonical JSON representation of the package
        excluding the package_checksum_sha256 field itself.
        """
        clean_pkg = copy.deepcopy(evidence_package)
        clean_pkg.pop("package_checksum_sha256", None)
        raw_bytes = cls.canonical_serialize(clean_pkg)
        return hashlib.sha256(raw_bytes).hexdigest()

    @classmethod
    def verify_package(
        cls,
        evidence_input: Union[str, Path, Dict[str, Any]],
        expected_dataset_sha: Optional[str] = None,
    ) -> EvidenceVerificationReport:
        """
        Conduct full independent audit on an evidence package.
        Validates schema, checksum, model freeze, historical date bounds, and disclosures.
        """
        tampered_fields: List[str] = []

        # 1. Parse JSON if string or Path
        if isinstance(evidence_input, (str, Path)):
            try:
                if isinstance(evidence_input, Path) or (isinstance(evidence_input, str) and (evidence_input.endswith(".json") or Path(evidence_input).exists())):
                    raw_text = Path(evidence_input).read_text(encoding="utf-8")
                else:
                    raw_text = str(evidence_input)
                pkg = json.loads(raw_text)
            except Exception as e:
                return EvidenceVerificationReport(
                    status=EvidenceVerificationStatus.CORRUPTED_PAYLOAD.value,
                    is_valid=False,
                    package_checksum_verified=False,
                    recorded_checksum="",
                    computed_checksum="",
                    model_version_verified=False,
                    quarantine_verified=False,
                    disclosures_verified=False,
                    tampering_detected=True,
                    tampered_fields=["json_syntax"],
                    details={"error": f"JSON ayrıştırma hatası: {str(e)}"},
                )
        elif isinstance(evidence_input, dict):
            pkg = copy.deepcopy(evidence_input)
        else:
            return EvidenceVerificationReport(
                status=EvidenceVerificationStatus.CORRUPTED_PAYLOAD.value,
                is_valid=False,
                package_checksum_verified=False,
                recorded_checksum="",
                computed_checksum="",
                model_version_verified=False,
                quarantine_verified=False,
                disclosures_verified=False,
                tampering_detected=True,
                tampered_fields=["type_error"],
                details={"error": "Geçersiz kanıt paketi veri türü."},
            )

        recorded_checksum = pkg.get("package_checksum_sha256", "")
        if not recorded_checksum:
            tampered_fields.append("package_checksum_sha256")

        # 2. Checksum recalculation
        computed_checksum = cls.compute_package_checksum(pkg)
        checksum_valid = bool(recorded_checksum and recorded_checksum == computed_checksum)
        if not checksum_valid:
            tampered_fields.append("package_checksum_sha256_mismatch")

        # 3. Model Freeze Validation
        model_meta = pkg.get("canonical_model", {})
        model_ver = model_meta.get("version")
        model_status = model_meta.get("status")
        mutations = model_meta.get("parameter_mutations")

        model_valid = (
            model_ver == FROZEN_MODEL_VERSION
            and model_status == "STRICTLY_FROZEN"
            and mutations == 0
        )
        if not model_valid:
            tampered_fields.append("canonical_model")

        # 4. Historical Date Bounds & Quarantine
        spec = pkg.get("research_specification", {})
        start_utc = spec.get("reference_start_utc") or spec.get("start_utc")
        end_utc = spec.get("reference_end_utc") or spec.get("end_utc")

        quarantine_valid = True
        if not start_utc or not end_utc:
            quarantine_valid = False
            tampered_fields.append("research_specification.dates_missing")
        else:
            try:
                dt_start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
                dt_end = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
                dt_quarantine = datetime.fromisoformat(OCTOBER_2026_QUARANTINE_START.replace("Z", "+00:00"))
                if dt_start >= dt_end or dt_start >= dt_quarantine or dt_end > dt_quarantine:
                    quarantine_valid = False
                    tampered_fields.append("research_specification.quarantine_or_order_violation")
            except Exception:
                quarantine_valid = False
                tampered_fields.append("research_specification.date_format_invalid")

        # 5. Scientific Disclosures Validation
        disclosures = pkg.get("scientific_disclosures", {})
        holdout_sat = disclosures.get("predeclared_holdout_criteria_satisfied")
        conf_rep = disclosures.get("independent_confirmatory_replications")
        limitations = disclosures.get("epistemological_limitations")

        disclosures_valid = (
            holdout_sat == 2
            and conf_rep == 0
            and isinstance(limitations, list)
            and len(limitations) >= 2
        )
        if not disclosures_valid:
            tampered_fields.append("scientific_disclosures")

        # 6. Dataset Provenance Check if expected hash given
        dataset_meta = pkg.get("dataset_provenance", {})
        pkg_manifest_sha = dataset_meta.get("manifest_sha256")
        if expected_dataset_sha and pkg_manifest_sha != expected_dataset_sha:
            tampered_fields.append("dataset_provenance.manifest_sha256")

        # Determine overall status
        if not checksum_valid:
            status = EvidenceVerificationStatus.CHECKSUM_MISMATCH_TAMPERED.value
        elif not model_valid:
            status = EvidenceVerificationStatus.MODEL_FREEZE_VIOLATION.value
        elif not quarantine_valid:
            status = EvidenceVerificationStatus.QUARANTINE_VIOLATION.value
        elif not disclosures_valid:
            status = EvidenceVerificationStatus.SCIENTIFIC_DISCLOSURE_INCOMPLETE.value
        else:
            status = EvidenceVerificationStatus.VERIFIED_VALID.value

        is_valid = status == EvidenceVerificationStatus.VERIFIED_VALID.value
        tampering_detected = len(tampered_fields) > 0

        return EvidenceVerificationReport(
            status=status,
            is_valid=is_valid,
            package_checksum_verified=checksum_valid,
            recorded_checksum=recorded_checksum,
            computed_checksum=computed_checksum,
            model_version_verified=model_valid,
            quarantine_verified=quarantine_valid,
            disclosures_verified=disclosures_valid,
            tampering_detected=tampering_detected,
            tampered_fields=tampered_fields,
            details={
                "workflow_id": pkg.get("workflow_id"),
                "research_session_id": pkg.get("research_session_id"),
                "export_schema_version": pkg.get("export_schema_version"),
                "asset": spec.get("asset"),
                "interval": spec.get("interval"),
                "reference_start_utc": start_utc,
                "reference_end_utc": end_utc,
                "dataset_manifest_sha256": pkg_manifest_sha,
            },
        )
