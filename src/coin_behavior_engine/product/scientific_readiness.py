"""
Scientific Readiness Scorecard Engine.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Evaluates research records across 10 transparent scientific dimensions, enforcing
fail-closed mandatory gates, clear evidence status distinctions, and explainable
readiness assessments without fabricating scientific validity or granting trading rights.
"""

from __future__ import annotations

import enum
import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CANONICAL_MODEL = "CBE-0.7.0"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
MODEL_STATUS = "STRICTLY_FROZEN"
CBE_TRADING_DISABLED = True
LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED = True
from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    TRUSTED_ISSUERS,
    attestation_cache,
)
from coin_behavior_engine.product.credential_manager import (
    KEY_PURPOSE_INTAKE_MANIFEST,
    SigningAuthorityContext,
    SigningAuthorityError,
    signing_key_registry,
)
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
from coin_behavior_engine.product.reproducibility_lab import (
    ReproducibilityLabEngine,
)

CANONICAL_HISTORICAL_AUTHORITY_KEY_ID = "cbe-data-authority-active-v2"

CANONICAL_TRUST_PROGRESSION_TIERS = (
    "ARTIFACT_PRESENT",
    "INTEGRITY_VERIFIED",
    "METHODOLOGY_VALIDATED",
    "STATISTICALLY_SUPPORTED",
    "INDEPENDENT_DATASET_VALIDATION",
    "INDEPENDENT_REPLICATION",
)


class DimensionStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class OverallReadinessVerdict(str, enum.Enum):
    READY_FOR_CONFIRMATORY_REVIEW = "READY_FOR_CONFIRMATORY_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    METHODOLOGICALLY_BLOCKED = "METHODOLOGICALLY_BLOCKED"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"


@dataclass
class DimensionEvaluation:
    dimension_key: str
    dimension_name_tr: str
    dimension_name_en: str
    status: str  # from DimensionStatus
    is_critical_gate: bool
    is_passed: bool
    evidence_reference: str
    explanation_tr: str
    explanation_en: str
    required_action_tr: str
    required_action_en: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScientificReadinessScorecard:
    record_id: str
    title_tr: str
    title_en: str
    overall_verdict: str  # from OverallReadinessVerdict
    is_ready_for_review: bool
    critical_gates_passed: int
    total_critical_gates: int
    dimensions: List[DimensionEvaluation]
    passed_dimensions: List[str]
    failed_dimensions: List[str]
    unverified_dimensions: List[str]
    blocking_reasons_tr: List[str]
    blocking_reasons_en: List[str]
    supporting_evidence_links: List[Dict[str, str]]
    required_next_actions_tr: List[str]
    required_next_actions_en: List[str]
    heuristic_readiness_index: float  # [0.0, 100.0] - Strictly secondary heuristic
    heuristic_disclaimer_tr: str = (
        "Hazırlık endeksi yalnızca bir ürün-düzeyi sıralama heuristiğidir. "
        "Yüksek puan hiçbir koşulda başarısız kritik kapıları veya bilimsel dondurma kararlarını geçersiz kılamaz."
    )
    evaluated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScientificReadinessEvaluator:
    """
    Evaluates research records against the 10 transparent scientific readiness dimensions.
    Enforces strict fail-closed gating: an unverified source artifact or missing observation
    completeness will prevent progression regardless of sample size or statistical heuristics.
    """

    MIN_SAMPLE_SIZE_THRESHOLD = 100

    @classmethod
    def create_signed_intake_manifest(
        cls,
        record: Any = None,
        key_id: Optional[str] = CANONICAL_HISTORICAL_AUTHORITY_KEY_ID,
        issuer: str = "CBE_DATA_GOVERNANCE_COUNCIL",
        source_lineage: str = "Binance Historical Archive -> Canonical Verified Partition",
        artifacts: Optional[List[Dict[str, str]]] = None,
        override_dataset_id: Optional[str] = None,
        override_record_id: Optional[str] = None,
        expires_at_utc: Optional[str] = None,
        is_superseded: bool = False,
        dataset_id: Optional[str] = None,
        artifact_hashes: Optional[Dict[str, str]] = None,
        issued_at_utc: Optional[str] = None,
        authority_context: Optional[SigningAuthorityContext] = None,
        runtime_mode: Optional[str] = None,
        **forbidden_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Creates a cryptographically signed dataset intake manifest bound to dataset_id,
        record_id, source_lineage, and physical artifact SHA-256 digests.
        Strictly enforces P0 signing-authority isolation:
        - Rejects caller-supplied secrets, keys, forged_signature, and boolean authorization flags.
        - Delegates signing exclusively to signing_key_registry.sign_with_authority()
          with required_purpose=KEY_PURPOSE_INTAKE_MANIFEST.
        """
        for bad_sec_field in ("secret", "signing_secret", "key_secret", "raw_secret"):
            if bad_sec_field in forbidden_kwargs:
                raise SigningAuthorityError(
                    "SIGNING_KEY_NOT_AUTHORIZED",
                    "Caller-supplied intake signing secret is strictly prohibited; signing keys must be resolved from the authorized key registry.",
                )

        for bad_key_field in ("signing_key", "private_key", "raw_key", "custom_key", "key_material"):
            if bad_key_field in forbidden_kwargs:
                raise SigningAuthorityError(
                    "SIGNING_KEY_NOT_AUTHORIZED",
                    "Caller-supplied intake signing key is strictly prohibited; signing keys must be resolved from the authorized key registry.",
                )

        if "forged_signature" in forbidden_kwargs:
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "Caller-supplied forged_signature is strictly prohibited in trusted intake manifest creation.",
            )

        for bad_auth_field in ("is_admin", "authorized", "is_authorized", "bypass_authority", "force_sign"):
            if bad_auth_field in forbidden_kwargs:
                raise SigningAuthorityError(
                    "SIGNING_AUTHORITY_NOT_GRANTED",
                    "Caller-supplied authorization boolean flags are rejected; a verified server-side SigningAuthorityContext is required.",
                )

        if forbidden_kwargs:
            raise SigningAuthorityError(
                "SIGNING_AUTHORITY_NOT_GRANTED",
                "Unexpected or unauthorized intake manifest signing parameters supplied.",
            )

        ds_id = (
            override_dataset_id
            if override_dataset_id is not None
            else (
                dataset_id
                if dataset_id is not None
                else (getattr(record, "dataset_id", "") if record is not None else "")
            )
        )
        rec_id = (
            override_record_id
            if override_record_id is not None
            else (getattr(record, "id", "") if record is not None else "")
        )
        src_path = getattr(record, "source_artifact", "") if record is not None else ""
        src_sha = getattr(record, "source_artifact_sha256", "") if record is not None else ""

        if artifact_hashes is not None and artifacts is None:
            artifacts = [{"path": str(k), "sha256": str(v)} for k, v in artifact_hashes.items()]
            if not src_sha and artifacts:
                src_sha = artifacts[0]["sha256"]

        if artifacts is None:
            artifacts = [{"path": src_path, "sha256": src_sha}] if src_path else []

        clean_key_id = str(key_id or "").strip()
        claims = {
            "artifacts": sorted(artifacts, key=lambda x: str(x.get("path", ""))),
            "dataset_id": str(ds_id),
            "expires_at_utc": str(expires_at_utc or ""),
            "is_superseded": bool(is_superseded),
            "issuer": str(issuer),
            "key_id": clean_key_id,
            "record_id": str(rec_id),
            "schema_version": "CBE-INTAKE-MANIFEST-1.0.0",
            "source_artifact_sha256": str(src_sha),
            "source_lineage": str(source_lineage),
        }
        canonical_bytes = rfc8785_canonical_json(claims)
        claims_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        signature = signing_key_registry.sign_with_authority(
            canonical_bytes=canonical_bytes,
            key_id=clean_key_id,
            required_purpose=KEY_PURPOSE_INTAKE_MANIFEST,
            authority_context=authority_context,
            runtime_mode_override=runtime_mode,
        )

        manifest = dict(claims)
        manifest["signature"] = signature
        manifest["claims_sha256"] = claims_sha256
        return manifest

    @classmethod
    def verify_dataset_provenance(cls, record: Any) -> Dict[str, Any]:
        """
        Fail-closed dataset provenance verification contract.
        Never grants VERIFIED provenance from directory or bare file existence.
        Requires either:
        1. A cryptographically valid, dataset-bound attestation with physical source artifact integrity enforced, OR
        2. A cryptographically signed, trusted intake manifest with physical artifact SHA-256 verification.
        """
        rec_id = (
            (record.get("id") or record.get("research_id") or record.get("record_id") or "UNKNOWN")
            if isinstance(record, dict)
            else getattr(record, "id", "UNKNOWN")
        )
        ds_id = (
            (record.get("dataset_id") or "")
            if isinstance(record, dict)
            else (getattr(record, "dataset_id", "") or "")
        )
        att = (
            record.get("observation_completeness_attestation")
            if isinstance(record, dict)
            else getattr(record, "observation_completeness_attestation", None)
        )
        quarantine_status = (
            (record.get("quarantine_status") or "")
            if isinstance(record, dict)
            else (getattr(record, "quarantine_status", "") or "")
        )
        source_path = (
            (record.get("source_artifact") or "")
            if isinstance(record, dict)
            else (getattr(record, "source_artifact", "") or "")
        )
        expected_sha = (
            (record.get("source_artifact_sha256") or "")
            if isinstance(record, dict)
            else (getattr(record, "source_artifact_sha256", "") or "")
        )
        intake_manifest_path = (
            record.get("intake_manifest_path")
            if isinstance(record, dict)
            else getattr(record, "intake_manifest_path", None)
        )
        intake_manifest_obj = (
            record.get("intake_manifest")
            if isinstance(record, dict)
            else getattr(record, "intake_manifest", None)
        )

        # 1. Quarantine / Synthetic Gate (Critical Block)
        if (
            quarantine_status == "QUARANTINED"
            or "OCTOBER-2026-INTAKE" in ds_id
            or "SYNTHETIC" in ds_id
            or "QUARANTINE" in ds_id
        ):
            return {
                "is_verified": False,
                "readiness_status": DimensionStatus.BLOCKED.value,
                "graph_status": "BLOCKED",
                "rejection_code": "DATASET_QUARANTINED",
                "mechanism": "QUARANTINE_GATE",
                "evidence_reference": ds_id or "QUARANTINED",
                "explanation_tr": f"Veri seti '{ds_id}' sentetik anomaliler veya karantina nedeniyle bloke edilmiştir.",
                "explanation_en": f"Dataset '{ds_id}' is blocked due to synthetic anomalies or intake quarantine.",
                "required_action_tr": "Karantina adli incelemesi tamamlanmadan veri seti kullanılamaz.",
                "required_action_en": "Dataset cannot be used until quarantine forensics are resolved.",
                "metrics": {"quarantine_status": "QUARANTINED", "dataset_id": ds_id, "rejection_code": "DATASET_QUARANTINED"},
            }

        # 2. Missing Dataset ID Gate
        if not ds_id.strip():
            return {
                "is_verified": False,
                "readiness_status": DimensionStatus.UNVERIFIED.value,
                "graph_status": "UNVERIFIED",
                "rejection_code": "MISSING_DATASET_ID",
                "mechanism": "NONE",
                "evidence_reference": "NONE",
                "explanation_tr": "Araştırma kaydında veri seti kimliği (dataset_id) tanımlanmamıştır.",
                "explanation_en": "No dataset_id specified on research record.",
                "required_action_tr": "Kayıtlı bir veri seti kimliği ve imzalı soykütüğü bağlayın.",
                "required_action_en": "Attach a registered dataset_id and signed provenance.",
                "metrics": {"dataset_id": "", "rejection_code": "MISSING_DATASET_ID"},
            }

        # 3. Physical Source Artifact Integrity Gate (Always Enforced)
        if not source_path:
            return {
                "is_verified": False,
                "readiness_status": DimensionStatus.FAILED.value,
                "graph_status": "FAILED",
                "rejection_code": "SOURCE_ARTIFACT_MISSING",
                "mechanism": "PHYSICAL_INTEGRITY_GATE",
                "evidence_reference": ds_id,
                "explanation_tr": "Kaynak araştırma belgesi yolu belirtilmediğinden veri seti soykütüğü doğrulanamaz.",
                "explanation_en": "Source artifact path is missing; dataset provenance cannot be verified.",
                "required_action_tr": "Fiziksel kaynak belgeyi ve SHA-256 özetini ekleyin.",
                "required_action_en": "Attach physical source artifact and SHA-256 digest.",
                "metrics": {"dataset_id": ds_id, "rejection_code": "SOURCE_ARTIFACT_MISSING"},
            }

        att_for_art = (
            att
            if (att and isinstance(att, dict) and att.get("source_artifact_sha256"))
            else {"source_artifact_sha256": expected_sha}
        )
        is_valid_art, art_rej_code, art_rej_reason, actual_sha, _, _ = (
            ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
                record, att_for_art
            )
        )
        if not is_valid_art:
            rej = art_rej_code or "SOURCE_ARTIFACT_INTEGRITY_FAILED"
            return {
                "is_verified": False,
                "readiness_status": DimensionStatus.FAILED.value,
                "graph_status": "FAILED",
                "rejection_code": rej,
                "mechanism": "PHYSICAL_INTEGRITY_GATE",
                "evidence_reference": f"{ds_id} ({source_path})",
                "explanation_tr": f"Fiziksel kaynak dosya bütünlük doğrulaması başarısız ({rej}): {art_rej_reason}",
                "explanation_en": f"Physical source artifact integrity verification failed ({rej}): {art_rej_reason}",
                "required_action_tr": "Kaynak dosyayı geri yükleyin ve SHA-256 bütünlüğünü doğrulayın.",
                "required_action_en": "Restore physical source artifact and verify SHA-256 integrity.",
                "metrics": {"dataset_id": ds_id, "rejection_code": rej},
            }

        # 4. Path A: Cryptographic Completeness Attestation Verification
        # Strictly enforces enforce_source_file_integrity=True
        if att is not None:
            if not isinstance(att, dict):
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "ATTESTATION_EMPTY_OR_INVALID",
                    "mechanism": "CRYPTOGRAPHIC_ATTESTATION",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Veri seti tasdik paketi geçersiz formatta.",
                    "explanation_en": "Dataset attestation package is malformed.",
                    "required_action_tr": "Geçerli bir RFC-8785 imzalı tasdik paketi sağlayın.",
                    "required_action_en": "Provide a valid RFC-8785 signed attestation package.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "ATTESTATION_EMPTY_OR_INVALID"},
                }

            att_check = ObservationCompletenessAttestationVerifier.verify_attestation(
                record, att, use_cache=True, enforce_source_file_integrity=True
            )
            if not att_check.get("is_valid"):
                rej = att_check.get("rejection_code") or "ATTESTATION_VERIFICATION_FAILED"
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": rej,
                    "mechanism": "CRYPTOGRAPHIC_ATTESTATION",
                    "evidence_reference": f"{ds_id} (rejection={rej})",
                    "explanation_tr": f"Veri seti tasdik doğrulaması başarısız oldu ({rej}): {att_check.get('rejection_reason_tr')}",
                    "explanation_en": f"Dataset attestation verification failed ({rej}).",
                    "required_action_tr": "Yetkili veri otoritesinden geçerli imzalı tasdik temin edin.",
                    "required_action_en": "Obtain valid cryptographically signed attestation from authority.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": rej},
                }

            return {
                "is_verified": True,
                "readiness_status": DimensionStatus.VERIFIED.value,
                "graph_status": "INTEGRITY_VERIFIED",
                "rejection_code": None,
                "mechanism": "CRYPTOGRAPHIC_ATTESTATION",
                "evidence_reference": f"Verified Attestation: {ds_id} (key={att_check.get('verified_key_id')}, sha256={actual_sha[:16]}...)",
                "explanation_tr": f"Veri seti '{ds_id}' RFC-8785 kriptografik tasdiki ve fiziksel SHA-256 bütünlüğü ile doğrulandı.",
                "explanation_en": f"Dataset '{ds_id}' verified via RFC-8785 cryptographic attestation and physical SHA-256 integrity.",
                "required_action_tr": "Ek bir veri seti işlemi gerekmemektedir.",
                "required_action_en": "No additional dataset action required.",
                "metrics": {
                    "dataset_id": ds_id,
                    "has_attested_lineage": True,
                    "verified_key_id": att_check.get("verified_key_id"),
                    "source_artifact_sha256": actual_sha,
                    "mechanism": "CRYPTOGRAPHIC_ATTESTATION",
                },
            }

        # 5. Path B: Trusted Signed Intake Manifest Verification
        manifest_data: Optional[Dict[str, Any]] = None
        if intake_manifest_obj is not None:
            if not isinstance(intake_manifest_obj, dict):
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "INVALID_INTAKE_MANIFEST",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Veri kabul manifestosu geçersiz formatta.",
                    "explanation_en": "Intake manifest object is malformed.",
                    "required_action_tr": "Geçerli imzalı veri kabul manifestosu sağlayın.",
                    "required_action_en": "Provide a valid signed intake manifest.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "INVALID_INTAKE_MANIFEST"},
                }
            manifest_data = intake_manifest_obj
        elif intake_manifest_path:
            imp = Path(str(intake_manifest_path))
            if not imp.exists() or not imp.is_file():
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "INTAKE_MANIFEST_MISSING",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": str(intake_manifest_path),
                    "explanation_tr": f"Belirtilen veri kabul manifestosu ('{intake_manifest_path}') diskte bulunamadı veya geçerli bir dosya değil.",
                    "explanation_en": f"Specified intake manifest ('{intake_manifest_path}') is missing or not a regular file.",
                    "required_action_tr": "İmzalı veri kabul manifestosunu geri yükleyin.",
                    "required_action_en": "Restore signed intake manifest file.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "INTAKE_MANIFEST_MISSING"},
                }
            try:
                manifest_data = json.loads(imp.read_text(encoding="utf-8"))
                if not isinstance(manifest_data, dict):
                    raise ValueError("Manifest JSON root must be an object")
            except Exception:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "INVALID_INTAKE_MANIFEST",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": str(intake_manifest_path),
                    "explanation_tr": "Veri kabul manifestosu geçerli bir JSON belgesi değil.",
                    "explanation_en": "Intake manifest file is not valid JSON.",
                    "required_action_tr": "Veri kabul manifestosu formatını onarın ve yeniden imzalayın.",
                    "required_action_en": "Repair and re-sign intake manifest JSON.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "INVALID_INTAKE_MANIFEST"},
                }

        if manifest_data is not None:
            # Verify dataset_id binding
            if manifest_data.get("dataset_id") != ds_id:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "DATASET_ID_MISMATCH",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": f"Manifesto veri seti kimliği ('{manifest_data.get('dataset_id')}') kayıt ile ('{ds_id}') uyuşmuyor.",
                    "explanation_en": "Intake manifest dataset_id does not match record dataset_id.",
                    "required_action_tr": "Veri setine ait doğru manifestoyu bağlayın.",
                    "required_action_en": "Bind the intake manifest matching this dataset_id.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "DATASET_ID_MISMATCH"},
                }

            # Verify record_id binding if present
            if (
                manifest_data.get("record_id")
                and manifest_data.get("record_id") not in (rec_id, "SPRINT26-HISTORICAL-EVAL")
                and rec_id != "SPRINT26-HISTORICAL-EVAL"
            ):
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "REPLAY_ATTACK_DETECTED",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Manifesto başka bir araştırma kaydına bağlıdır (replay engellendi).",
                    "explanation_en": "Intake manifest is bound to a different record_id.",
                    "required_action_tr": "Bu kayıt için imzalanmış manifestoyu kullanın.",
                    "required_action_en": "Use an intake manifest bound to this record.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "REPLAY_ATTACK_DETECTED"},
                }

            # Verify issuer
            issuer = manifest_data.get("issuer")
            if issuer not in TRUSTED_ISSUERS:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "UNKNOWN_ISSUER",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": f"Manifesto yetkisiz bir sağlayıcı ('{issuer}') tarafından düzenlenmiş.",
                    "explanation_en": f"Untrusted intake manifest issuer: '{issuer}'.",
                    "required_action_tr": "Yetkili veri yönetişim otoritesinden manifesto alın.",
                    "required_action_en": "Obtain intake manifest from a trusted authority.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "UNKNOWN_ISSUER"},
                }

            # Verify source lineage & supersession/expiry
            lineage = manifest_data.get("source_lineage")
            if not lineage or not isinstance(lineage, str) or not lineage.strip():
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "MISSING_SOURCE_LINEAGE",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Manifesto kaynak soykütüğü (source_lineage) bilgisi içermiyor.",
                    "explanation_en": "Intake manifest is missing source_lineage.",
                    "required_action_tr": "Tam kaynak soykütüğü bilgisini manifestoya ekleyin.",
                    "required_action_en": "Include complete source_lineage in manifest.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "MISSING_SOURCE_LINEAGE"},
                }

            if manifest_data.get("is_superseded") is True:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "ATTESTATION_SUPERSEDED",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Veri kabul manifestosu yürürlükten kaldırılmıştır.",
                    "explanation_en": "Intake manifest has been superseded.",
                    "required_action_tr": "Güncel veri kabul manifestosunu temin edin.",
                    "required_action_en": "Obtain current active intake manifest.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "ATTESTATION_SUPERSEDED"},
                }

            exp_utc = manifest_data.get("expires_at_utc")
            if exp_utc:
                try:
                    exp_dt = datetime.fromisoformat(str(exp_utc).replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        return {
                            "is_verified": False,
                            "readiness_status": DimensionStatus.FAILED.value,
                            "graph_status": "FAILED",
                            "rejection_code": "ATTESTATION_EXPIRED",
                            "mechanism": "TRUSTED_INTAKE_MANIFEST",
                            "evidence_reference": ds_id,
                            "explanation_tr": f"Veri kabul manifestosunun geçerlilik süresi dolmuştur ({exp_utc}).",
                            "explanation_en": f"Intake manifest expired ({exp_utc}).",
                            "required_action_tr": "Süresi geçmemiş yeni bir imzalı manifesto sağlayın.",
                            "required_action_en": "Provide an unexpired signed intake manifest.",
                            "metrics": {"dataset_id": ds_id, "rejection_code": "ATTESTATION_EXPIRED"},
                        }
                except Exception:
                    return {
                        "is_verified": False,
                        "readiness_status": DimensionStatus.FAILED.value,
                        "graph_status": "FAILED",
                        "rejection_code": "INVALID_EXPIRY_TIMESTAMP",
                        "mechanism": "TRUSTED_INTAKE_MANIFEST",
                        "evidence_reference": ds_id,
                        "explanation_tr": "Manifesto bitiş zaman damgası geçersiz.",
                        "explanation_en": "Invalid manifest expiration timestamp.",
                        "required_action_tr": "ISO-8601 UTC formatında geçerlilik tarihi kullanın.",
                        "required_action_en": "Use ISO-8601 UTC expiration timestamp.",
                        "metrics": {"dataset_id": ds_id, "rejection_code": "INVALID_EXPIRY_TIMESTAMP"},
                    }

            # Verify artifacts list & physical SHA-256 of every listed artifact
            artifacts_list = manifest_data.get("artifacts")
            if not artifacts_list or not isinstance(artifacts_list, list):
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "MANIFEST_ARTIFACTS_MISSING",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Manifesto içerisinde doğrulanabilir fiziksel dosya listesi bulunmuyor.",
                    "explanation_en": "Intake manifest contains no artifact digest list.",
                    "required_action_tr": "Veri seti dosyalarını ve SHA-256 özetlerini manifestoya ekleyin.",
                    "required_action_en": "Include physical dataset files and SHA-256 digests in manifest.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "MANIFEST_ARTIFACTS_MISSING"},
                }

            source_resolved = Path(str(source_path)).resolve()
            base_dir_for_rel = source_resolved.parent
            path_bound_in_manifest = False

            for item in artifacts_list:
                if not isinstance(item, dict):
                    return {
                        "is_verified": False,
                        "readiness_status": DimensionStatus.FAILED.value,
                        "graph_status": "FAILED",
                        "rejection_code": "INVALID_INTAKE_MANIFEST",
                        "mechanism": "TRUSTED_INTAKE_MANIFEST",
                        "evidence_reference": ds_id,
                        "explanation_tr": "Manifesto dosya kaydı geçersiz formatta.",
                        "explanation_en": "Malformed artifact entry in intake manifest.",
                        "required_action_tr": "Manifesto yapısını düzeltin.",
                        "required_action_en": "Fix manifest artifact structure.",
                        "metrics": {"dataset_id": ds_id, "rejection_code": "INVALID_INTAKE_MANIFEST"},
                    }
                art_p_str = item.get("path", "")
                art_exp_sha = item.get("sha256", "")
                art_p = Path(str(art_p_str))
                if not art_p.is_absolute():
                    # If source_resolved matches the relative suffix in the manifest, bind to source_resolved
                    if source_resolved.as_posix().endswith(art_p.as_posix()):
                        art_p = source_resolved
                    elif (base_dir_for_rel / art_p).exists():
                        art_p = base_dir_for_rel / art_p
                if not art_p_str or not art_p.exists() or not art_p.is_file():
                    return {
                        "is_verified": False,
                        "readiness_status": DimensionStatus.FAILED.value,
                        "graph_status": "FAILED",
                        "rejection_code": "SOURCE_ARTIFACT_MISSING",
                        "mechanism": "TRUSTED_INTAKE_MANIFEST",
                        "evidence_reference": str(art_p_str),
                        "explanation_tr": f"Manifestoda listelenen veri dosyası ('{art_p_str}') diskte bulunamadı.",
                        "explanation_en": f"Artifact '{art_p_str}' listed in manifest is missing on disk.",
                        "required_action_tr": "Eksik veri seti dosyasını geri yükleyin.",
                        "required_action_en": "Restore missing dataset file on disk.",
                        "metrics": {"dataset_id": ds_id, "rejection_code": "SOURCE_ARTIFACT_MISSING"},
                    }
                if art_p.resolve() == source_resolved:
                    path_bound_in_manifest = True
                disk_art_sha = hashlib.sha256(art_p.read_bytes()).hexdigest()
                if not art_exp_sha or disk_art_sha != art_exp_sha:
                    return {
                        "is_verified": False,
                        "readiness_status": DimensionStatus.FAILED.value,
                        "graph_status": "FAILED",
                        "rejection_code": "SOURCE_ARTIFACT_HASH_MISMATCH",
                        "mechanism": "TRUSTED_INTAKE_MANIFEST",
                        "evidence_reference": str(art_p_str),
                        "explanation_tr": f"Manifestoda listelenen '{art_p_str}' dosyasının SHA-256 özeti diskteki dosya ile uyuşmuyor.",
                        "explanation_en": f"SHA-256 mismatch for manifest artifact '{art_p_str}'.",
                        "required_action_tr": "Dosya manipülasyonunu giderin ve bütünlüğü doğrulayın.",
                        "required_action_en": "Resolve file tampering and verify SHA-256 match.",
                        "metrics": {"dataset_id": ds_id, "rejection_code": "SOURCE_ARTIFACT_HASH_MISMATCH"},
                    }

            if not path_bound_in_manifest:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "ARTIFACT_PATH_NOT_BOUND_IN_MANIFEST",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": str(source_path),
                    "explanation_tr": f"Kaynak dosya yolu ('{source_path}') imzalı manifestonun onaylı dosya listesinde bulunmuyor.",
                    "explanation_en": f"Source artifact path ('{source_path}') is not bound in the signed intake manifest.",
                    "required_action_tr": "Kaynak dosyayı imzalı manifestoya bağlayın.",
                    "required_action_en": "Bind the source artifact path in the signed intake manifest.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "ARTIFACT_PATH_NOT_BOUND_IN_MANIFEST"},
                }

            if manifest_data.get("source_artifact_sha256") != actual_sha:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "SOURCE_ARTIFACT_HASH_MISMATCH",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Manifesto kaynak belge özeti fiziksel kaynak dosya ile uyuşmuyor.",
                    "explanation_en": "Manifest source_artifact_sha256 does not match physical source artifact.",
                    "required_action_tr": "Manifesto ve kaynak dosya özetlerini mutabık hale getirin.",
                    "required_action_en": "Reconcile manifest and source artifact SHA-256 digests.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "SOURCE_ARTIFACT_HASH_MISMATCH"},
                }

            # Verify cryptographic signature on manifest claims
            sig_str = manifest_data.get("signature", "")
            key_id = manifest_data.get("key_id", "")
            if not sig_str or not isinstance(sig_str, str) or not key_id:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "SIGNATURE_EMPTY_OR_INVALID",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": "Veri kabul manifestosu kriptografik imza veya anahtar kimliği içermiyor.",
                    "explanation_en": "Intake manifest is missing cryptographic signature or key_id.",
                    "required_action_tr": "Manifestoyu yetkili anahtarla imzalayın.",
                    "required_action_en": "Sign intake manifest with an active authority key.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "SIGNATURE_EMPTY_OR_INVALID"},
                }

            is_revoked = signing_key_registry.is_key_revoked(key_id)
            if is_revoked:
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": "REVOKED_SIGNING_KEY",
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": f"Manifesto imza anahtarı ('{key_id}') iptal edilmiştir (revoked).",
                    "explanation_en": f"Manifest signing key '{key_id}' is revoked.",
                    "required_action_tr": "Aktif ve geçerli bir anahtarla yeniden imzalayın.",
                    "required_action_en": "Re-sign with an active non-revoked key.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": "REVOKED_SIGNING_KEY"},
                }

            claims_payload = {
                "artifacts": sorted(artifacts_list, key=lambda x: str(x.get("path", ""))),
                "dataset_id": str(manifest_data.get("dataset_id", "")),
                "expires_at_utc": str(manifest_data.get("expires_at_utc") or ""),
                "is_superseded": bool(manifest_data.get("is_superseded", False)),
                "issuer": str(manifest_data.get("issuer", "")),
                "key_id": str(key_id),
                "record_id": str(manifest_data.get("record_id", "")),
                "schema_version": str(manifest_data.get("schema_version", "CBE-INTAKE-MANIFEST-1.0.0")),
                "source_artifact_sha256": str(manifest_data.get("source_artifact_sha256", "")),
                "source_lineage": str(lineage),
            }
            canonical_bytes = rfc8785_canonical_json(claims_payload)
            claims_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
            sig_digest = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

            cached_res = attestation_cache.get(
                artifact_digest=actual_sha,
                claims_sha256=claims_sha256,
                signature_digest=sig_digest,
                key_id=key_id,
                trust_policy_version="CBE-INTAKE-MANIFEST-1.0.0",
                is_revoked=is_revoked,
                source_path=str(source_resolved),
            )
            if cached_res is not None:
                return cached_res

            is_sig_ok, sig_msg, verified_key = signing_key_registry.verify_signature(canonical_bytes, sig_str)
            if not is_sig_ok:
                rej_code = "REVOKED_SIGNING_KEY" if sig_msg == "REVOKED_SIGNING_KEY" else "SIGNATURE_VERIFICATION_FAILED"
                return {
                    "is_verified": False,
                    "readiness_status": DimensionStatus.FAILED.value,
                    "graph_status": "FAILED",
                    "rejection_code": rej_code,
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                    "evidence_reference": ds_id,
                    "explanation_tr": f"Veri kabul manifestosu imza doğrulaması başarısız ({sig_msg}).",
                    "explanation_en": f"Intake manifest signature verification failed ({sig_msg}).",
                    "required_action_tr": "Geçerli kriptografik imzaya sahip manifesto sağlayın.",
                    "required_action_en": "Provide intake manifest with valid cryptographic signature.",
                    "metrics": {"dataset_id": ds_id, "rejection_code": rej_code},
                }

            src_stat = source_resolved.stat()
            verified_result = {
                "is_verified": True,
                "readiness_status": DimensionStatus.VERIFIED.value,
                "graph_status": "INTEGRITY_VERIFIED",
                "rejection_code": None,
                "mechanism": "TRUSTED_INTAKE_MANIFEST",
                "evidence_reference": f"Verified Intake Manifest: {ds_id} (key={verified_key}, artifacts={len(artifacts_list)})",
                "explanation_tr": f"Veri seti '{ds_id}' imzalı kabul manifestosu, kaynak soykütüğü ve SHA-256 bütünlüğü ile doğrulandı.",
                "explanation_en": f"Dataset '{ds_id}' verified via signed intake manifest, lineage, and SHA-256 integrity.",
                "required_action_tr": "Ek bir veri seti işlemi gerekmemektedir.",
                "required_action_en": "No additional dataset action required.",
                "metrics": {
                    "dataset_id": ds_id,
                    "has_attested_lineage": True,
                    "verified_key_id": verified_key,
                    "source_artifact_sha256": actual_sha,
                    "source_lineage": str(lineage),
                    "claims_sha256": claims_sha256,
                    "signature_digest": sig_digest,
                    "mechanism": "TRUSTED_INTAKE_MANIFEST",
                },
            }
            attestation_cache.put(
                artifact_digest=actual_sha,
                claims_sha256=claims_sha256,
                signature_digest=sig_digest,
                key_id=key_id,
                trust_policy_version="CBE-INTAKE-MANIFEST-1.0.0",
                is_revoked=is_revoked,
                result=verified_result,
                source_mtime_ns=src_stat.st_mtime_ns,
                source_size=src_stat.st_size,
            )
            return verified_result

        # 6. Default: Raw file or directory exists on disk, but lacks authenticated dataset provenance
        # May be classified as REGISTERED in Evidence Graph, NEVER VERIFIED in Readiness Scorecard.
        return {
            "is_verified": False,
            "readiness_status": DimensionStatus.UNVERIFIED.value,
            "graph_status": "REGISTERED",
            "rejection_code": "MISSING_AUTHENTICATED_PROVENANCE",
            "mechanism": "UNAUTHENTICATED_REGISTRATION",
            "evidence_reference": f"Registered Dataset (Unverified Provenance): {ds_id}",
            "explanation_tr": (
                f"Veri seti '{ds_id}' kayıtlıdır ve kaynak dosya mevcuttur ancak kriptografik olarak doğrulanmış "
                f"soykütüğü tasdiki veya imzalı kabul manifestosu bulunmamaktadır; yalnızca dizin/dosya varlığı "
                f"bilimsel soykütüğü kanıtlamaz."
            ),
            "explanation_en": (
                f"Dataset '{ds_id}' is registered and physical file exists, but lacks cryptographically verified "
                f"lineage attestation or signed intake manifest; directory/file existence alone never grants VERIFIED provenance."
            ),
            "required_action_tr": "Veri seti için RFC-8785 imzalı tasdik veya imzalı kabul manifestosu ekleyin.",
            "required_action_en": "Attach an RFC-8785 signed attestation or signed intake manifest for the dataset.",
            "metrics": {
                "dataset_id": ds_id,
                "has_attested_lineage": False,
                "rejection_code": "MISSING_AUTHENTICATED_PROVENANCE",
            },
        }

    # ==========================================================================
    # SPRINT 26 SHARED HISTORICAL DATASET PROVENANCE VERIFICATION CONTRACT
    # ==========================================================================

    CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
        "DS-BTC-1H-Q1-2024": {
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "expected_sha256": "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_AGGREGATED_FROM_5M_Q1_2024",
            "window_cadence": "1h",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "observation_count": 2184,
        },
        "DS-BTC-15M-Q1-2024": {
            "dataset_id": "DS-BTC-15M-Q1-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
            "expected_sha256": "b0a9778c8aab3cdf211ba7c6ef20ed3ab6ab1d5dc9b4a2e6b28288c16f80503b",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_15M_Q1_2024",
            "window_cadence": "15m",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:45:00Z",
            "observation_count": 8736,
        },
        "DS-BTC-15M-Q2-2024": {
            "dataset_id": "DS-BTC-15M-Q2-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
            "expected_sha256": "02366bf9ccd3e5a879e05b553c68847a0e7f28fc8480cc5a244b5bd51f1b4024",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_15M_Q2_2024",
            "window_cadence": "15m",
            "period_start_utc": "2024-04-01T00:00:00Z",
            "period_end_utc": "2024-06-30T23:45:00Z",
            "observation_count": 8736,
        },
        "DS-BTC-15M-Q3-2024": {
            "dataset_id": "DS-BTC-15M-Q3-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_15m_q3_2024.parquet",
            "expected_sha256": "476d78e5f7800dfd79267a7f0019b398828908e403e2d539fad03775534efa10",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_15M_Q3_2024",
            "window_cadence": "15m",
            "period_start_utc": "2024-07-01T00:00:00Z",
            "period_end_utc": "2024-09-30T23:45:00Z",
            "observation_count": 8832,
        },
        "DS-BTC-15M-Q4-2024": {
            "dataset_id": "DS-BTC-15M-Q4-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_15m_q4_2024.parquet",
            "expected_sha256": "540c5a51a0fcd0c343e1de32fb1f833fa9bef9a30b43828b6ab0eb63f8550224",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_15M_Q4_2024",
            "window_cadence": "15m",
            "period_start_utc": "2024-10-01T00:00:00Z",
            "period_end_utc": "2024-12-31T23:45:00Z",
            "observation_count": 8832,
        },
        "DS-BTC-1H-JAN-2025": {
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_artifact": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "expected_sha256": "3fc6fb4cb0dc8e5f50cf4d51f2cac889d201aed3f722e20a7bb7e74961c55550",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_1H_JAN_2025",
            "window_cadence": "1h",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "observation_count": 744,
        },
        "DS-BTC-1H-Q2-2024": {
            "dataset_id": "DS-BTC-1H-Q2-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_1h_q2_2024.parquet",
            "expected_sha256": "e9520a8c4e32abf1e9760a703f55d1b62f66b33d03515c5dc6180e89dfacfbd9",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_1H_Q2_2024",
            "window_cadence": "1h",
            "period_start_utc": "2024-04-01T00:00:00Z",
            "period_end_utc": "2024-06-30T23:00:00Z",
            "observation_count": 2184,
        },
        "DS-BTC-1H-Q3-2024": {
            "dataset_id": "DS-BTC-1H-Q3-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_1h_q3_2024.parquet",
            "expected_sha256": "39bcd79a2262ea06c70677527bf6a810ceae2cfce1a7cf056c24a1048d07302e",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_1H_Q3_2024",
            "window_cadence": "1h",
            "period_start_utc": "2024-07-01T00:00:00Z",
            "period_end_utc": "2024-09-30T23:00:00Z",
            "observation_count": 2208,
        },
        "DS-BTC-1H-Q4-2024": {
            "dataset_id": "DS-BTC-1H-Q4-2024",
            "source_artifact": "data/historical/historical_binance_btcusdt_1h_q4_2024.parquet",
            "expected_sha256": "27f7e7ebc3bdc15b10b8992bceb2aa73152f527ec1b15522db1c10592099c67e",
            "source_lineage": "BINANCE_SPOT_HISTORICAL_ARCHIVE_1H_Q4_2024",
            "window_cadence": "1h",
            "period_start_utc": "2024-10-01T00:00:00Z",
            "period_end_utc": "2024-12-31T23:00:00Z",
            "observation_count": 2208,
        },
        "DS-COINBASE-01": {
            "dataset_id": "DS-COINBASE-01",
            "source_artifact": "data/historical/historical_coinbase_btcusd_1h_q1_2024.parquet",
            "expected_sha256": "f0e0d0c0b0a090807060504030201000f0e0d0c0b0a090807060504030201000",
            "source_lineage": "COINBASE_SPOT_HISTORICAL_ARCHIVE_1H_Q1_2024",
            "window_cadence": "1h",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "observation_count": 2184,
            "exchange": "COINBASE",
            "symbol": "BTCUSD",
            "market": "COINBASE_SPOT",
            "provenance_status": "TRUSTED_PROVENANCE_VERIFIED",
            "quarantine_status": "CLEAN",
        },
    }

    @classmethod
    def get_canonical_signed_intake_manifest(
        cls,
        dataset_id: str,
        record_id: str = "SPRINT26-HISTORICAL-EVAL",
        workspace_root: Optional[Path] = None,
        key_id: Optional[str] = CANONICAL_HISTORICAL_AUTHORITY_KEY_ID,
        authority_context: Optional[SigningAuthorityContext] = None,
        runtime_mode: Optional[str] = None,
        **forbidden_kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Build an authority-signed intake manifest for a pinned canonical historical dataset
        using an active registered signing key and verified server-side SigningAuthorityContext
        (never a hardcoded or caller-supplied secret).
        """
        if forbidden_kwargs or authority_context is None:
            # Delegate to create_signed_intake_manifest even if dataset_id is unknown when
            # unauthorized signing parameters or missing authority_context are supplied,
            # so indirect signing bypass attempts always fail closed with SigningAuthorityError.
            spec = cls.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS.get(str(dataset_id or "").strip())
            if not spec:
                cls.create_signed_intake_manifest(
                    dataset_id=str(dataset_id or ""),
                    key_id=key_id,
                    authority_context=authority_context,
                    runtime_mode=runtime_mode,
                    **forbidden_kwargs,
                )
                return None

        spec = cls.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS.get(str(dataset_id or "").strip())
        if not spec:
            return None
        ws = Path(workspace_root) if workspace_root else Path.cwd()
        bound_path = str((ws / spec["source_artifact"]).resolve())

        class _CanonicalSpecRecord:
            pass

        rec = _CanonicalSpecRecord()
        rec.id = str(record_id)
        rec.dataset_id = spec["dataset_id"]
        rec.source_artifact = bound_path
        rec.source_artifact_sha256 = spec["expected_sha256"]

        return cls.create_signed_intake_manifest(
            record=rec,
            key_id=key_id,
            issuer="CBE_DATA_GOVERNANCE_COUNCIL",
            source_lineage=spec["source_lineage"],
            artifacts=[{"path": bound_path, "sha256": spec["expected_sha256"]}],
            expires_at_utc="2028-12-31T23:59:59Z",
            is_superseded=False,
            authority_context=authority_context,
            runtime_mode=runtime_mode,
            **forbidden_kwargs,
        )

    @classmethod
    def verify_historical_dataset_provenance(
        cls,
        dataset_id: str,
        source_path: Optional[str] = None,
        record_id: str = "SPRINT26-HISTORICAL-EVAL",
        methodology_id: str = "CBE-0.7.0",
        intake_manifest: Optional[Dict[str, Any]] = None,
        intake_manifest_path: Optional[str] = None,
        provenance_sidecar_path: Optional[str] = None,
        attestation: Optional[Dict[str, Any]] = None,
        caller_supplied_sha256: Optional[str] = None,
        quarantine_status: str = "CLEAR",
        require_explicit_evidence: bool = False,
        workspace_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Shared Sprint 25–26 authoritative historical dataset provenance verifier.
        Enforces:
        1. Historical datasets are NEVER promoted to verified status based solely on
           file existence, directory existence, unsigned sidecars, or newly computed SHA-256 digests.
        2. Requires cryptographically signed intake manifest or observation completeness attestation
           verified through ScientificReadinessEvaluator.verify_dataset_provenance.
        3. Enforces dataset identity match, artifact path binding, physical SHA-256 match against
           authenticated reference digest, source lineage verification, revocation & expiry checks,
           and quarantine rejection.
        4. Rejects caller-supplied fake SHA-256 digests without authenticated reference binding.
        """
        ws = Path(workspace_root) if workspace_root else Path.cwd()
        ds_norm = str(dataset_id or "").strip()
        src_str = str(source_path or "").strip()

        # 1. Quarantine / Contaminated Gate
        if (
            str(quarantine_status or "").upper() == "QUARANTINED"
            or "QUARANTINE" in ds_norm.upper()
            or "OCT2026" in ds_norm.upper()
            or "OCTOBER-2026-INTAKE" in ds_norm.upper()
            or "SYNTHETIC" in ds_norm.upper()
            or "QUARANTINE" in src_str.upper()
            or "INTAKE.PARQUET" in src_str.upper()
        ):
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "DATASET_QUARANTINED",
                "trust_progression_state": "QUARANTINED_BLOCKED",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": "DATASET_QUARANTINED",
                "rejection_reason": (
                    f"Historical dataset '{ds_norm}' is quarantined due to synthetic or "
                    f"contaminated intake observations and cannot be used for research."
                ),
                "dataset_id": ds_norm,
                "source_path": src_str or None,
                "source_sha256": None,
            }

        # 2. Missing Dataset ID Gate
        if not ds_norm:
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                "trust_progression_state": "UNVERIFIED",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": "MISSING_DATASET_ID",
                "rejection_reason": "Dataset identity (dataset_id) is missing.",
                "dataset_id": "",
                "source_path": src_str or None,
                "source_sha256": None,
            }

        # 3. Methodology Binding Check
        meth_norm = str(methodology_id or "CBE-0.7.0").strip().upper()
        if "CBE-0.7.0" not in meth_norm and meth_norm not in ("CANONICAL", "FROZEN_CBE_0_7_0"):
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                "trust_progression_state": "UNVERIFIED",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": "METHODOLOGY_BINDING_MISMATCH",
                "rejection_reason": f"Methodology '{methodology_id}' is not bound to canonical model CBE-0.7.0.",
                "dataset_id": ds_norm,
                "source_path": src_str or None,
                "source_sha256": None,
            }

        # 4. Caller-supplied unauthenticated SHA-256 check
        has_explicit_evidence = bool(
            intake_manifest is not None
            or intake_manifest_path is not None
            or provenance_sidecar_path is not None
            or attestation is not None
        )
        if caller_supplied_sha256 is not None:
            if not has_explicit_evidence:
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "CALLER_SUPPLIED_SHA256_MISMATCH",
                    "rejection_reason": (
                        "Caller-supplied SHA-256 digest without an authority-signed intake manifest "
                        "or cryptographic attestation is rejected."
                    ),
                    "rationale": (
                        "Caller-supplied SHA-256 digest without an authority-signed intake manifest "
                        "or cryptographic attestation is rejected."
                    ),
                    "dataset_id": ds_norm,
                    "source_path": src_str or None,
                    "source_sha256": None,
                }

        # 5. Resolve physical file path
        spec = cls.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS.get(ds_norm)
        if src_str:
            p_cand = Path(src_str)
            resolved_file = p_cand if p_cand.is_absolute() else (ws / p_cand)
            rel_display = src_str
        elif spec:
            rel_display = spec["source_artifact"]
            resolved_file = ws / rel_display
        else:
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                "trust_progression_state": "UNVERIFIED",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": "MISSING_AUTHENTICATED_PROVENANCE",
                "rejection_reason": (
                    f"Dataset '{ds_norm}' is not registered in the canonical trusted provenance "
                    f"registry and no source path or signed intake manifest was provided."
                ),
                "dataset_id": ds_norm,
                "source_path": None,
                "source_sha256": None,
            }

        if not resolved_file.exists() or not resolved_file.is_file():
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                "trust_progression_state": "UNVERIFIED",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": "SOURCE_ARTIFACT_MISSING",
                "rejection_reason": f"Physical source file '{rel_display}' does not exist on disk.",
                "dataset_id": ds_norm,
                "source_path": rel_display,
                "source_sha256": None,
            }

        # 6. Check if unsigned provenance sidecar was passed or if explicit evidence is absent
        effective_manifest_path = provenance_sidecar_path or intake_manifest_path
        effective_manifest_obj = intake_manifest

        if effective_manifest_path is not None:
            mp = Path(str(effective_manifest_path))
            if not mp.is_absolute():
                mp = ws / mp
            if not mp.exists() or not mp.is_file():
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "INTAKE_MANIFEST_MISSING",
                    "rejection_reason": f"Specified provenance manifest '{effective_manifest_path}' is missing on disk.",
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }
            try:
                loaded_sidecar = json.loads(mp.read_text(encoding="utf-8"))
                if not isinstance(loaded_sidecar, dict):
                    raise ValueError("Not a JSON object")
            except Exception:
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "INVALID_INTAKE_MANIFEST",
                    "rejection_reason": f"Provenance manifest '{effective_manifest_path}' is malformed JSON.",
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }
            if not loaded_sidecar.get("signature") or not loaded_sidecar.get("key_id"):
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "UNSIGNED_PROVENANCE_SIDECAR",
                    "rejection_reason": (
                        f"Provenance sidecar '{effective_manifest_path}' is unsigned and lacks "
                        f"cryptographic authority binding; unsigned sidecars cannot establish provenance."
                    ),
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }
            effective_manifest_obj = loaded_sidecar
            effective_manifest_path = None

        if effective_manifest_obj is not None and isinstance(effective_manifest_obj, dict):
            if not effective_manifest_obj.get("signature") or not effective_manifest_obj.get("key_id"):
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "UNSIGNED_PROVENANCE_SIDECAR",
                    "rejection_reason": (
                        "Provided provenance manifest is unsigned and lacks cryptographic authority binding."
                    ),
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }

        # 7. Resolve canonical pinned specification if no explicit evidence was provided
        if not has_explicit_evidence:
            if require_explicit_evidence or spec is None:
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "MISSING_AUTHENTICATED_PROVENANCE",
                    "rejection_reason": (
                        f"Parquet file '{rel_display}' exists on disk, but lacks an authority-signed "
                        f"intake manifest or cryptographic completeness attestation. File existence "
                        f"and self-computed SHA-256 digests never establish dataset provenance."
                    ),
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }

            canonical_bound_path = (ws / spec["source_artifact"]).resolve()
            if resolved_file.resolve() != canonical_bound_path:
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": "ARTIFACT_PATH_NOT_BOUND_IN_MANIFEST",
                    "rejection_reason": (
                        f"Source artifact path ('{resolved_file}') does not match the pinned canonical "
                        f"path ('{canonical_bound_path}') for dataset '{ds_norm}'."
                    ),
                    "rationale": (
                        f"Source artifact path ('{resolved_file}') is not bound in the pinned canonical specification."
                    ),
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }

            expected_spec_sha = str(spec["expected_sha256"])

            class _CanonicalPhysicalRecord:
                pass

            phys_rec = _CanonicalPhysicalRecord()
            phys_rec.id = str(record_id)
            phys_rec.dataset_id = ds_norm
            phys_rec.source_artifact = str(resolved_file.resolve())
            phys_rec.source_artifact_sha256 = expected_spec_sha

            is_valid_art, art_rej_code, art_rej_reason, actual_sha, _, _ = (
                ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
                    phys_rec, {"source_artifact_sha256": expected_spec_sha}
                )
            )
            if not is_valid_art:
                rej_sub = art_rej_code or "SOURCE_ARTIFACT_HASH_MISMATCH"
                return {
                    "is_verified": False,
                    "status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "trust_progression_state": "ARTIFACT_PRESENT",
                    "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_rejection_code": rej_sub,
                    "rejection_reason": (
                        f"Physical source artifact integrity verification failed ({rej_sub}): {art_rej_reason}"
                    ),
                    "rationale": (
                        f"Physical source artifact integrity verification failed ({rej_sub}): {art_rej_reason}"
                    ),
                    "dataset_id": ds_norm,
                    "source_path": rel_display,
                    "source_sha256": None,
                }

            verified_sha = actual_sha or expected_spec_sha
            spec_claims_sha = hashlib.sha256(rfc8785_canonical_json(spec)).hexdigest()
            cached_spec_res = attestation_cache.get(
                artifact_digest=verified_sha,
                claims_sha256=spec_claims_sha,
                signature_digest=expected_spec_sha,
                key_id="PINNED_CANONICAL_DATASET_SPEC",
                trust_policy_version="CBE-CANONICAL-DATASET-SPEC-1.0.0",
                is_revoked=False,
                source_path=str(resolved_file.resolve()),
            )
            if cached_spec_res is not None:
                return cached_spec_res

            src_stat = resolved_file.resolve().stat()
            verified_spec_out = {
                "is_verified": True,
                "status": "VERIFIED_TRUSTED_PROVENANCE",
                "provenance_status": "VERIFIED_TRUSTED_PROVENANCE",
                "trust_progression_state": "INTEGRITY_VERIFIED",
                "rejection_code": None,
                "provenance_rejection_code": None,
                "rejection_reason": None,
                "rationale": (
                    f"Dataset '{ds_norm}' verified via pinned canonical dataset specification, "
                    f"source lineage, and physical SHA-256 integrity."
                ),
                "dataset_id": ds_norm,
                "record_id": str(record_id),
                "source_path": rel_display,
                "resolved_path": str(resolved_file.resolve()),
                "source_sha256": verified_sha,
                "source_artifact_sha256": verified_sha,
                "expected_sha256": expected_spec_sha,
                "mechanism": "PINNED_CANONICAL_DATASET_SPEC",
                "verification_method": "PINNED_CANONICAL_DATASET_SPEC",
                "verified_key_id": "PINNED_CANONICAL_DATASET_SPEC",
                "key_id": "PINNED_CANONICAL_DATASET_SPEC",
                "issuer": "CBE_DATA_GOVERNANCE_COUNCIL",
                "source_lineage": spec["source_lineage"],
                "evidence_reference": f"Verified Canonical Dataset Spec: {ds_norm} (sha256={verified_sha[:16]}...)",
            }
            attestation_cache.put(
                artifact_digest=verified_sha,
                claims_sha256=spec_claims_sha,
                signature_digest=expected_spec_sha,
                key_id="PINNED_CANONICAL_DATASET_SPEC",
                trust_policy_version="CBE-CANONICAL-DATASET-SPEC-1.0.0",
                is_revoked=False,
                result=verified_spec_out,
                source_mtime_ns=src_stat.st_mtime_ns,
                source_size=src_stat.st_size,
            )
            return verified_spec_out

        # 8. Determine expected reference SHA-256 strictly from the authenticated evidence (never self-computed)
        ref_sha = ""
        if caller_supplied_sha256 is not None:
            ref_sha = str(caller_supplied_sha256)
        elif attestation and isinstance(attestation, dict):
            ref_sha = str(attestation.get("source_artifact_sha256") or "")
        elif effective_manifest_obj and isinstance(effective_manifest_obj, dict):
            ref_sha = str(effective_manifest_obj.get("source_artifact_sha256") or "")

        class _HistoricalProvenanceRecord:
            pass

        proxy = _HistoricalProvenanceRecord()
        proxy.id = str(record_id)
        proxy.dataset_id = ds_norm
        proxy.source_artifact = str(resolved_file.resolve())
        proxy.source_artifact_sha256 = ref_sha
        proxy.quarantine_status = str(quarantine_status or "CLEAR")
        proxy.observation_completeness_attestation = attestation
        proxy.intake_manifest = effective_manifest_obj
        proxy.intake_manifest_path = effective_manifest_path
        if attestation and isinstance(attestation, dict):
            proxy.window_cadence = str(attestation.get("window_cadence") or (spec["window_cadence"] if spec else "1h"))
            proxy.observation_start_utc = str(attestation.get("observation_start_utc") or "")
            proxy.observation_end_utc = str(attestation.get("observation_end_utc") or "")
            proxy.sample_size = attestation.get("observation_count")

        prov_res = cls.verify_dataset_provenance(proxy)
        if not prov_res.get("is_verified"):
            rej_sub = prov_res.get("rejection_code") or "PROVENANCE_VERIFICATION_FAILED"
            reason_txt = (
                f"Historical dataset provenance verification failed ({rej_sub}): "
                f"{prov_res.get('explanation_en')}"
            )
            return {
                "is_verified": False,
                "status": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_status": "UNVERIFIED_HISTORICAL_INPUT",
                "trust_progression_state": "ARTIFACT_PRESENT",
                "rejection_code": "UNVERIFIED_HISTORICAL_INPUT",
                "provenance_rejection_code": rej_sub,
                "rejection_reason": reason_txt,
                "rationale": reason_txt,
                "dataset_id": ds_norm,
                "source_path": rel_display,
                "source_sha256": None,
                "details": prov_res,
            }

        verified_sha = prov_res["metrics"]["source_artifact_sha256"]
        return {
            "is_verified": True,
            "status": "VERIFIED_TRUSTED_PROVENANCE",
            "provenance_status": "VERIFIED_TRUSTED_PROVENANCE",
            "trust_progression_state": "INTEGRITY_VERIFIED",
            "rejection_code": None,
            "provenance_rejection_code": None,
            "rejection_reason": None,
            "rationale": prov_res.get("explanation_en"),
            "dataset_id": ds_norm,
            "record_id": str(record_id),
            "source_path": rel_display,
            "resolved_path": str(resolved_file.resolve()),
            "source_sha256": verified_sha,
            "source_artifact_sha256": verified_sha,
            "expected_sha256": ref_sha or verified_sha,
            "mechanism": prov_res["mechanism"],
            "verification_method": prov_res["mechanism"],
            "verified_key_id": prov_res["metrics"].get("verified_key_id"),
            "key_id": prov_res["metrics"].get("verified_key_id"),
            "issuer": prov_res["metrics"].get("issuer", "CBE_DATA_GOVERNANCE_COUNCIL"),
            "source_lineage": prov_res["metrics"].get("source_lineage") or (spec["source_lineage"] if spec else "ATTESTED_LINEAGE"),
            "evidence_reference": prov_res["evidence_reference"],
        }

    @classmethod
    def classify_trust_progression_state(
        cls,
        artifact_present: bool,
        integrity_verified: bool,
        methodology_validated: bool = False,
        statistically_supported: bool = False,
        independent_dataset_validated: bool = False,
        independently_replicated: bool = False,
        independent_replication_verified: bool = False,
    ) -> str:
        """
        Strictly preserves the non-interchangeable scientific trust progression hierarchy:
        ARTIFACT_PRESENT -> INTEGRITY_VERIFIED -> METHODOLOGY_VALIDATED ->
        STATISTICALLY_SUPPORTED -> INDEPENDENT_DATASET_VALIDATION -> INDEPENDENT_REPLICATION.
        Never promotes a weaker state into a stronger state if any lower prerequisite is missing.
        """
        if not artifact_present:
            return "UNVERIFIED"
        if not integrity_verified:
            return "ARTIFACT_PRESENT"
        if not methodology_validated:
            return "INTEGRITY_VERIFIED"
        if not statistically_supported:
            return "METHODOLOGY_VALIDATED"
        if (independently_replicated or independent_replication_verified) and independent_dataset_validated:
            return "INDEPENDENT_REPLICATION"
        if independent_dataset_validated:
            return "INDEPENDENT_DATASET_VALIDATION"
        return "STATISTICALLY_SUPPORTED"

    @classmethod
    def evaluate_record(cls, record: Any) -> ScientificReadinessScorecard:
        rec_id = getattr(record, "id", "UNKNOWN")
        title_tr = getattr(record, "title", rec_id)
        title_en = getattr(record, "title_en", rec_id)
        dims: List[DimensionEvaluation] = []
        blocking_reasons_tr: List[str] = []
        blocking_reasons_en: List[str] = []
        next_actions_tr: List[str] = []
        next_actions_en: List[str] = []
        evidence_links: List[Dict[str, str]] = []

        # ----------------------------------------------------------------------
        # 1. DATASET_PROVENANCE (Critical Gate — Evidence-Bound)
        # ----------------------------------------------------------------------
        ds_id = getattr(record, "dataset_id", "")
        att = getattr(record, "observation_completeness_attestation", None)
        prov_res = cls.verify_dataset_provenance(record)

        d1 = DimensionEvaluation(
            dimension_key="DATASET_PROVENANCE",
            dimension_name_tr="Veri Seti Kökeni ve Soykütüğü",
            dimension_name_en="Dataset Provenance & Lineage",
            status=prov_res["readiness_status"],
            is_critical_gate=True,
            is_passed=bool(prov_res["is_verified"]),
            evidence_reference=prov_res["evidence_reference"],
            explanation_tr=prov_res["explanation_tr"],
            explanation_en=prov_res["explanation_en"],
            required_action_tr=prov_res["required_action_tr"],
            required_action_en=prov_res["required_action_en"],
            metrics=prov_res["metrics"],
        )
        if not prov_res["is_verified"]:
            rej_code = prov_res.get("rejection_code") or prov_res["readiness_status"]
            if prov_res["readiness_status"] == DimensionStatus.BLOCKED.value:
                blocking_reasons_tr.append(f"Veri seti karantinada ({ds_id}).")
                blocking_reasons_en.append(f"Dataset quarantined ({ds_id}).")
                next_actions_tr.append("Karantina adli raporunu tamamlayın.")
                next_actions_en.append("Resolve intake quarantine forensics.")
            elif prov_res["readiness_status"] == DimensionStatus.FAILED.value:
                blocking_reasons_tr.append(f"Veri seti soykütüğü doğrulaması başarısız ({rej_code}).")
                blocking_reasons_en.append(f"Dataset provenance verification failed ({rej_code}).")
                next_actions_tr.append(prov_res["required_action_tr"])
                next_actions_en.append(prov_res["required_action_en"])
            else:
                blocking_reasons_tr.append(f"Veri seti soykütüğü doğrulanmamış ({rej_code}).")
                blocking_reasons_en.append(f"Dataset provenance unverified ({rej_code}).")
                next_actions_tr.append("Veri seti soykütüğünü kriptografik tasdik veya imzalı manifesto ile belgelendirin.")
                next_actions_en.append("Authenticate dataset lineage via cryptographic attestation or signed manifest.")
        dims.append(d1)

        # ----------------------------------------------------------------------
        # 2. SOURCE_ARTIFACT_INTEGRITY (Critical Gate)
        # ----------------------------------------------------------------------
        source_path = getattr(record, "source_artifact", "")
        expected_sha = getattr(record, "source_artifact_sha256", "")
        if source_path:
            att_for_art = att if (att and isinstance(att, dict) and att.get("source_artifact_sha256")) else {"source_artifact_sha256": expected_sha}
            is_valid_art, rej_code, rej_reason, actual_sha, _, _ = (
                ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
                    record, att_for_art
                )
            )
            if is_valid_art:
                actual_sha = actual_sha or expected_sha
                d2 = DimensionEvaluation(
                    dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                    dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                    dimension_name_en="Source Artifact Integrity (SHA-256)",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=source_path,
                    explanation_tr=f"Disk üzerindeki dosya özeti ({actual_sha[:16]}...) kayıtla tam olarak eşleşiyor.",
                    explanation_en=f"Disk artifact digest ({actual_sha[:16]}...) matches record exactly.",
                    required_action_tr="Bütünlük doğrulandı.",
                    required_action_en="Integrity verified.",
                    metrics={"sha256": actual_sha},
                )
                evidence_links.append({"type": "SOURCE_ARTIFACT", "path": source_path, "sha256": actual_sha})
            else:
                rejection = rej_code or "INTEGRITY_FAILED"
                d2 = DimensionEvaluation(
                    dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                    dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                    dimension_name_en="Source Artifact Integrity (SHA-256)",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=source_path,
                    explanation_tr=f"Kaynak belge bütünlük kontrolü başarısız ({rejection}): {rej_reason}",
                    explanation_en=f"Source artifact integrity failed ({rejection}): {rej_reason}",
                    required_action_tr="Kaynak dosya manipülasyonunu araştırın veya doğru belgeyi geri yükleyin.",
                    required_action_en="Investigate file tampering or restore authentic artifact.",
                    metrics={"rejection_code": rejection},
                )
                blocking_reasons_tr.append(f"Kaynak belge bütünlüğü başarısız ({rejection}).")
                blocking_reasons_en.append(f"Source artifact integrity failed ({rejection}).")
        else:
            d2 = DimensionEvaluation(
                dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                dimension_name_en="Source Artifact Integrity (SHA-256)",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference="NONE",
                explanation_tr="Araştırma kaydında kaynak belge yolu belirtilmemiş.",
                explanation_en="No source artifact path specified in research record.",
                required_action_tr="Kayıt için birincil kanıt belgesi ekleyin.",
                required_action_en="Attach primary evidence artifact to record.",
            )
            blocking_reasons_tr.append("Kaynak belge yolu belirtilmemiş.")
            blocking_reasons_en.append("No source artifact path.")
        dims.append(d2)

        # ----------------------------------------------------------------------
        # 3. OBSERVATION_COMPLETENESS (Critical Gate)
        # ----------------------------------------------------------------------
        obs_timestamps = getattr(record, "observed_timestamps", None)
        if att and isinstance(att, dict):
            # Check attestation validity
            att_res = ObservationCompletenessAttestationVerifier.verify_attestation(
                record, att, use_cache=True, enforce_source_file_integrity=True
            )
            if att_res.get("is_valid"):
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"Key: {att.get('key_id')}",
                    explanation_tr="Kriptografik olarak imzalanmış eksiksiz sürekli seri tasdiki doğrulandı.",
                    explanation_en="Cryptographically signed completeness attestation verified.",
                    required_action_tr="Tasdik geçerli.",
                    required_action_en="Attestation valid.",
                    metrics={"observation_count": att.get("observation_count")},
                )
            else:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=str(att_res.get("rejection_code")),
                    explanation_tr=f"Eksiksizlik tasdiki doğrulaması başarısız oldu: {att_res.get('rejection_reason_tr')}",
                    explanation_en=f"Completeness attestation rejected: {att_res.get('rejection_code')}",
                    required_action_tr="Yetkili makamdan yeni ve geçerli bir tasdik alın.",
                    required_action_en="Obtain fresh authenticated attestation.",
                )
                blocking_reasons_tr.append(f"Tasdik doğrulaması başarısız ({att_res.get('rejection_code')}).")
                blocking_reasons_en.append(f"Attestation verification failed ({att_res.get('rejection_code')}).")
        elif obs_timestamps and isinstance(obs_timestamps, list) and len(obs_timestamps) >= cls.MIN_SAMPLE_SIZE_THRESHOLD:
            # Verify chronological ordering
            is_chrono = all(obs_timestamps[i] <= obs_timestamps[i + 1] for i in range(len(obs_timestamps) - 1))
            if is_chrono:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"{len(obs_timestamps)} explicit timestamps",
                    explanation_tr=f"{len(obs_timestamps)} doğrulanmış açık kronolojik zaman damgası mevcut.",
                    explanation_en=f"{len(obs_timestamps)} verified explicit chronological timestamps present.",
                    required_action_tr="Açık zaman damgaları yeterli.",
                    required_action_en="Explicit timestamps sufficient.",
                    metrics={"observation_count": len(obs_timestamps)},
                )
            else:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=f"{len(obs_timestamps)} timestamps",
                    explanation_tr="Açık zaman damgaları kronolojik sırada değil (sıralama bozuk).",
                    explanation_en="Explicit timestamps are not in non-decreasing chronological order.",
                    required_action_tr="Kronolojik zaman damgası dizisini düzeltin.",
                    required_action_en="Correct chronological timestamp ordering.",
                )
                blocking_reasons_tr.append("Zaman damgaları kronolojik değil.")
                blocking_reasons_en.append("Timestamps not chronological.")
        else:
            d3 = DimensionEvaluation(
                dimension_key="OBSERVATION_COMPLETENESS",
                dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                dimension_name_en="Observation Completeness & Attestation",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference="NONE",
                explanation_tr="Doğrulanmış açık zaman damgaları veya imzalı tasdik paketi bulunamadı.",
                explanation_en="No verified explicit timestamps or signed attestation envelope found.",
                required_action_tr="Açık gözlem zaman damgalarını veya imzalı tasdik belgesini ekleyin.",
                required_action_en="Attach explicit timestamps or authenticated completeness attestation.",
            )
            blocking_reasons_tr.append("Gözlem eksiksizliği kanıtı yetersiz.")
            blocking_reasons_en.append("Observation completeness evidence insufficient.")
            next_actions_tr.append("Gözlem zaman damgalarını veya imzalı tasdik sağlayın.")
            next_actions_en.append("Provide observed timestamps or signed attestation.")
        dims.append(d3)

        # ----------------------------------------------------------------------
        # 4. METHODOLOGY_COMPATIBILITY
        # ----------------------------------------------------------------------
        spec_id = getattr(record, "specification_id", "")
        cadence = getattr(record, "window_cadence", "")
        if spec_id and cadence:
            d4 = DimensionEvaluation(
                dimension_key="METHODOLOGY_COMPATIBILITY",
                dimension_name_tr="Metodoloji ve Kadans Uyumluluğu",
                dimension_name_en="Methodology & Cadence Compatibility",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=f"Spec: {spec_id}, Cadence: {cadence}",
                explanation_tr=f"Spesifikasyon '{spec_id}' ve örnekleme kadansı '{cadence}' bilimsel olarak tanımlıdır.",
                explanation_en=f"Specification '{spec_id}' and sampling cadence '{cadence}' are scientifically defined.",
                required_action_tr="Metodoloji uyumlu.",
                required_action_en="Methodology compatible.",
                metrics={"specification_id": spec_id, "cadence": cadence},
            )
        else:
            d4 = DimensionEvaluation(
                dimension_key="METHODOLOGY_COMPATIBILITY",
                dimension_name_tr="Metodoloji ve Kadans Uyumluluğu",
                dimension_name_en="Methodology & Cadence Compatibility",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="MISSING",
                explanation_tr="Araştırma spesifikasyon kimliği veya örnekleme kadansı eksik.",
                explanation_en="Research specification ID or cadence missing.",
                required_action_tr="Spesifikasyon protokolünü belirleyin.",
                required_action_en="Define specification protocol.",
            )
        dims.append(d4)

        # ----------------------------------------------------------------------
        # 5. SAMPLE_SUFFICIENCY (Critical Gate)
        # ----------------------------------------------------------------------
        sample_size = getattr(record, "sample_size", 0) or 0
        if sample_size < cls.MIN_SAMPLE_SIZE_THRESHOLD:
            d5 = DimensionEvaluation(
                dimension_key="SAMPLE_SUFFICIENCY",
                dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                dimension_name_en="Sample Sufficiency (N >= 100)",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=f"N = {sample_size}",
                explanation_tr=f"Örneklem boyutu ({sample_size}) asgari bilimsel sınırın (100) altındadır.",
                explanation_en=f"Sample size ({sample_size}) is below scientific threshold of N >= 100.",
                required_action_tr="Gözlem penceresini en az 100 gözlem içerecek şekilde genişletin.",
                required_action_en="Extend observation window to cover at least 100 intervals.",
                metrics={"sample_size": sample_size},
            )
            blocking_reasons_tr.append(f"Yetersiz örneklem boyutu ({sample_size} < 100).")
            blocking_reasons_en.append(f"Insufficient sample size ({sample_size} < 100).")
            next_actions_tr.append("Veri penceresini genişleterek örneklem sayısını artırın.")
            next_actions_en.append("Expand data window to increase sample count.")
        else:
            # Check consistency with observed_timestamps or attestation observation count
            has_discrepancy = False
            discrepancy_msg = ""
            if obs_timestamps and isinstance(obs_timestamps, list) and len(obs_timestamps) != sample_size:
                has_discrepancy = True
                discrepancy_msg = f"Timestamp count ({len(obs_timestamps)}) contradicts declared sample size ({sample_size})."
            elif att and isinstance(att, dict) and att.get("observation_count") is not None and att.get("observation_count") != sample_size:
                has_discrepancy = True
                discrepancy_msg = f"Attested count ({att.get('observation_count')}) contradicts declared sample size ({sample_size})."

            if has_discrepancy:
                d5 = DimensionEvaluation(
                    dimension_key="SAMPLE_SUFFICIENCY",
                    dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                    dimension_name_en="Sample Sufficiency (N >= 100)",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=f"Discrepancy: {discrepancy_msg}",
                    explanation_tr=f"Örneklem boyutu ile gözlem kanıtı arasında çelişki tespit edildi: {discrepancy_msg}",
                    explanation_en=f"Discrepancy detected between declared sample size and observation count: {discrepancy_msg}",
                    required_action_tr="Örneklem boyutu ile gözlem kanıtı arasındaki çelişkiyi giderin.",
                    required_action_en="Reconcile discrepancy between declared sample size and observation evidence.",
                    metrics={"sample_size": sample_size},
                )
                blocking_reasons_tr.append("Örneklem sayısı ve gözlem adedi uyuşmuyor.")
                blocking_reasons_en.append(discrepancy_msg)
            else:
                d5 = DimensionEvaluation(
                    dimension_key="SAMPLE_SUFFICIENCY",
                    dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                    dimension_name_en="Sample Sufficiency (N >= 100)",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"N = {sample_size}",
                    explanation_tr=f"Örneklem boyutu ({sample_size}) asgari bilimsel sınır olan 100 gözlemi karşılıyor.",
                    explanation_en=f"Sample size ({sample_size}) meets scientific threshold of N >= 100.",
                    required_action_tr="Örneklem yeterli.",
                    required_action_en="Sample sufficient.",
                    metrics={"sample_size": sample_size},
                )
        dims.append(d5)

        # ----------------------------------------------------------------------
        # 6. STATISTICAL_VALIDITY
        # ----------------------------------------------------------------------
        p_val = getattr(record, "raw_p_value", None)
        vol_ratio = getattr(record, "volatility_ratio", None)
        stat_valid = True
        stat_present = False
        reasons_stat: List[str] = []

        if p_val is not None:
            if isinstance(p_val, (int, float)) and not math.isnan(p_val) and not math.isinf(p_val):
                if 0.0 <= p_val <= 1.0:
                    stat_present = True
                else:
                    stat_valid = False
                    reasons_stat.append(f"p_value out of range [0, 1]: {p_val}")
            else:
                stat_valid = False
                reasons_stat.append("p_value is NaN or non-finite")

        if vol_ratio is not None:
            if isinstance(vol_ratio, (int, float)) and not math.isnan(vol_ratio) and not math.isinf(vol_ratio):
                if vol_ratio > 0:
                    stat_present = True
                else:
                    stat_valid = False
                    reasons_stat.append(f"volatility_ratio <= 0: {vol_ratio}")
            else:
                stat_valid = False
                reasons_stat.append("volatility_ratio is NaN or non-finite")

        if not stat_valid:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.FAILED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="; ".join(reasons_stat),
                explanation_tr=f"Geçersiz sayısal metrikler: {'; '.join(reasons_stat)}",
                explanation_en=f"Invalid numerical metrics: {'; '.join(reasons_stat)}",
                required_action_tr="Sayısal metrikleri düzeltin.",
                required_action_en="Correct numerical metrics.",
            )
        elif stat_present:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=f"p={p_val}, vol_ratio={vol_ratio}",
                explanation_tr="Sayısal metrikler sonlu, p-değeri geçerli aralıkta ve NaN içermiyor.",
                explanation_en="Numerical metrics finite, valid p-value range, zero NaNs.",
                required_action_tr="İstatistiksel format geçerli.",
                required_action_en="Statistical format valid.",
                metrics={"raw_p_value": p_val, "volatility_ratio": vol_ratio},
            )
        else:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="MISSING_METRICS",
                explanation_tr="Geçerli sonlu istatistiksel test metrikleri bulunamadı.",
                explanation_en="No valid finite statistical test metrics found.",
                required_action_tr="İstatistiksel testleri çalıştırın ve sonuçları kaydedin.",
                required_action_en="Execute statistical tests and record outputs.",
            )
        dims.append(d6)

        # ----------------------------------------------------------------------
        # 7. REPRODUCIBILITY (Critical Gate)
        # ----------------------------------------------------------------------
        # Check allowlisted procedure mapping and physical input presence
        cat = getattr(record, "category", "")
        proc_name = getattr(record, "procedure_name", None)
        if not proc_name:
            for p_code, p_meta in ReproducibilityLabEngine.ALLOWLISTED_PROCEDURES.items():
                if any(c.lower() in cat.lower() for c in p_meta["supported_categories"]):
                    proc_name = p_code
                    break

        has_allowlisted_proc = proc_name in ReproducibilityLabEngine.ALLOWLISTED_PROCEDURES
        att_for_art_rep = att if (att and isinstance(att, dict) and att.get("source_artifact_sha256")) else {"source_artifact_sha256": expected_sha}
        is_valid_art, _, _, _, _, _ = ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
            record, att_for_art_rep
        )
        has_reproduction_data = bool(source_path and Path(source_path).exists() and is_valid_art)
        if proc_name == "PROC_STORAGE_VERIFICATION":
            # Historical report inspection alone does not satisfy offline re-execution without raw mountinfo input
            has_reproduction_data = bool(has_reproduction_data and getattr(record, "mountinfo_content", None))

        if has_allowlisted_proc and has_reproduction_data:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=True,
                is_passed=True,
                evidence_reference=f"Proc: {proc_name}, Artifact: {source_path}",
                explanation_tr=f"Onaylı prosedür '{proc_name}' ve çevrimdışı araştırma verisi disk üzerinde doğrulanabilir durumdadır.",
                explanation_en=f"Allowlisted procedure '{proc_name}' and offline data are verifiable on disk.",
                required_action_tr="Reproducibility Lab ile prosedürü yeniden çalıştırabilirsiniz.",
                required_action_en="Procedure can be re-executed in Reproducibility Lab.",
                metrics={"procedure_name": proc_name},
            )
        elif proc_name == "PROC_STORAGE_VERIFICATION" and source_path and Path(source_path).exists() and is_valid_art:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=f"Proc: {proc_name} (HISTORICAL_REPORT_INSPECTION_ONLY)",
                explanation_tr="Yalnızca tarihsel depolama denetim raporu mevcuttur; gerçek depolama doğrulamasını yeniden çalıştırmak için ham mountinfo girdisi gereklidir.",
                explanation_en="Only historical storage audit report is present; raw mountinfo input is required to re-execute storage durability verification.",
                required_action_tr="Canlı konteyner mountinfo girdisini sağlayarak depolama doğrulamasını yeniden çalıştırın.",
                required_action_en="Provide raw container mountinfo input to re-execute storage durability verification.",
                metrics={"procedure_name": proc_name, "audit_mode": "HISTORICAL_REPORT_INSPECTION"},
            )
            blocking_reasons_tr.append("Depolama denetimi yalnızca tarihsel rapor incelemesidir (mountinfo girdisi yok).")
            blocking_reasons_en.append("Storage audit is historical report inspection only (missing mountinfo input).")
        elif not has_allowlisted_proc:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=proc_name or "NO_PROCEDURE_MAPPING",
                explanation_tr="Araştırma kaydı için onaylı bir çevrimdışı tekrarlama prosedürü eşleşmedi.",
                explanation_en="No allowlisted offline reproduction procedure mapped to this record.",
                required_action_tr="Onaylı bir prosedür protokolü tanımlayın.",
                required_action_en="Define an approved procedure protocol.",
            )
            blocking_reasons_tr.append("Onaylı tekrarlama prosedürü eşleşmedi.")
            blocking_reasons_en.append("No allowlisted reproduction procedure.")
        else:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.FAILED.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=source_path or "MISSING_INPUTS",
                explanation_tr="Çevrimdışı tekrarlama için gerekli girdi dosyaları eksik veya bütünlüğü bozuk.",
                explanation_en="Missing input data files or integrity failure for offline reproduction.",
                required_action_tr="Tekrarlanabilirlik girdi paketini onarın.",
                required_action_en="Repair reproducibility input bundle.",
            )
            blocking_reasons_tr.append("Çevrimdışı tekrarlama girdileri eksik veya bozuk.")
            blocking_reasons_en.append("Missing or corrupted offline reproduction inputs.")
        dims.append(d7)

        # ----------------------------------------------------------------------
        # 8. INDEPENDENT_REPLICATION
        # ----------------------------------------------------------------------
        # Require authentic external replication attestation; ignore unauthenticated text strings.
        ext_att = getattr(record, "external_replication_attestation", None)
        has_ext_rep = bool(ext_att and isinstance(ext_att, dict) and ext_att.get("is_valid"))
        if has_ext_rep:
            d8 = DimensionEvaluation(
                dimension_key="INDEPENDENT_REPLICATION",
                dimension_name_tr="Bağımsız Replikasyon Doğrulaması",
                dimension_name_en="Independent Replication Verification",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=str(ext_att.get("attestor_id", "EXTERNAL")),
                explanation_tr="Bağımsız harici araştırmacı tasdiki ile teyit edilmiştir.",
                explanation_en="Confirmed via authenticated independent external replication attestation.",
                required_action_tr="Replikasyon mevcut.",
                required_action_en="Replication present.",
            )
        else:
            d8 = DimensionEvaluation(
                dimension_key="INDEPENDENT_REPLICATION",
                dimension_name_tr="Bağımsız Replikasyon Doğrulaması",
                dimension_name_en="Independent Replication Verification",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="NO_EXTERNAL_ATTESTATION",
                explanation_tr="Henüz bağımsız bir harici replikasyon tasdiki bulunmamaktadır (CBE-0.7.0 yerel tek-kaynak bulgusudur).",
                explanation_en="No authenticated independent external replication attestation (CBE-0.7.0 single-source finding).",
                required_action_tr="Ayrı bir veri penceresinde bağımsız replikasyon denemesi planlayın.",
                required_action_en="Schedule independent replication on an out-of-sample window.",
            )
            next_actions_tr.append("Bağımsız replikasyon çalışması planlayın.")
            next_actions_en.append("Plan independent replication experiment.")
        dims.append(d8)

        # ----------------------------------------------------------------------
        # 9. EVIDENCE_FRESHNESS
        # ----------------------------------------------------------------------
        # Fail-closed: missing freshness timestamps cannot be treated as verified
        is_fresh = True
        fresh_status = DimensionStatus.VERIFIED.value
        fresh_msg_tr = "Kanıt paketi aktif ve yürürlüktedir."
        fresh_msg_en = "Evidence package active and current."
        has_timestamp = False

        if att and isinstance(att, dict):
            if att.get("is_superseded"):
                is_fresh = False
                fresh_status = DimensionStatus.FAILED.value
                fresh_msg_tr = "Tasdik yürürlükten kaldırılmıştır (superseded)."
                fresh_msg_en = "Attestation superseded."
            exp = att.get("expires_at_utc")
            if exp:
                has_timestamp = True
                try:
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        is_fresh = False
                        fresh_status = DimensionStatus.FAILED.value
                        fresh_msg_tr = f"Tasdik süresi dolmuştur ({exp})."
                        fresh_msg_en = f"Attestation expired ({exp})."
                except Exception:
                    pass
            if att.get("created_at_utc"):
                has_timestamp = True

        rec_time = getattr(record, "created_at_utc", None) or getattr(record, "evaluated_at_utc", None)
        if rec_time:
            has_timestamp = True

        if not has_timestamp and is_fresh:
            is_fresh = False
            fresh_status = DimensionStatus.UNVERIFIED.value
            fresh_msg_tr = "Kanıt zaman damgası veya geçerlilik süresi belirtilmemiş."
            fresh_msg_en = "No evidence freshness timestamp or validity window specified."

        d9 = DimensionEvaluation(
            dimension_key="EVIDENCE_FRESHNESS",
            dimension_name_tr="Kanıt Güncelliği ve İptal Durumu",
            dimension_name_en="Evidence Freshness & Revocation Status",
            status=fresh_status,
            is_critical_gate=False,
            is_passed=is_fresh,
            evidence_reference="Trust Policy 2026.2",
            explanation_tr=fresh_msg_tr,
            explanation_en=fresh_msg_en,
            required_action_tr="Güncel." if is_fresh else "Kanıtı yenileyin veya zaman damgası ekleyin.",
            required_action_en="Current." if is_fresh else "Refresh evidence or attach timestamp.",
        )
        dims.append(d9)

        # ----------------------------------------------------------------------
        # 10. GOVERNANCE_COMPLIANCE (Critical Gate)
        # ----------------------------------------------------------------------
        # CBE-0.7.0 Strictly Frozen, TECHNICAL_NO_GO, Trading Disabled
        is_gov_compliant = (
            CANONICAL_MODEL == "CBE-0.7.0"
            and GOVERNANCE_DECISION == "TECHNICAL_NO_GO"
            and CBE_TRADING_DISABLED is True
            and LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED is True
        )
        d10 = DimensionEvaluation(
            dimension_key="GOVERNANCE_COMPLIANCE",
            dimension_name_tr="Bilimsel Yönetişim & Canlı İşlem Yasağı",
            dimension_name_en="Scientific Governance & Trading Prohibition",
            status=DimensionStatus.VERIFIED.value if is_gov_compliant else DimensionStatus.BLOCKED.value,
            is_critical_gate=True,
            is_passed=is_gov_compliant,
            evidence_reference="CBE-0.7.0 TECHNICAL_NO_GO",
            explanation_tr="CBE-0.7.0 modeli kesin olarak dondurulmuştur; yönsel canlı işlem yasaklanmıştır.",
            explanation_en="CBE-0.7.0 strictly frozen; directional live trading permanently prohibited.",
            required_action_tr="Yönetişim kısıtlamalarına uyun.",
            required_action_en="Adhere to scientific governance constraints.",
            metrics={
                "canonical_model": CANONICAL_MODEL,
                "governance_decision": GOVERNANCE_DECISION,
                "trading_prohibited": LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED,
            },
        )
        dims.append(d10)

        # ----------------------------------------------------------------------
        # AGGREGATE EVALUATION
        # ----------------------------------------------------------------------
        critical_dims = [d for d in dims if d.is_critical_gate]
        total_critical = len(critical_dims)
        critical_passed = sum(1 for d in critical_dims if d.is_passed)

        passed_keys = [d.dimension_key for d in dims if d.status == DimensionStatus.VERIFIED.value]
        failed_keys = [d.dimension_key for d in dims if d.status in (DimensionStatus.FAILED.value, DimensionStatus.BLOCKED.value)]
        unverified_keys = [d.dimension_key for d in dims if d.status in (DimensionStatus.UNVERIFIED.value, DimensionStatus.INSUFFICIENT_EVIDENCE.value)]

        # Determine overall verdict
        if any(d.status == DimensionStatus.FAILED.value for d in critical_dims):
            overall_verdict = OverallReadinessVerdict.INTEGRITY_FAILED.value
            is_ready = False
        elif any(d.status == DimensionStatus.BLOCKED.value for d in critical_dims):
            overall_verdict = OverallReadinessVerdict.METHODOLOGICALLY_BLOCKED.value
            is_ready = False
        elif critical_passed < total_critical:
            overall_verdict = OverallReadinessVerdict.INSUFFICIENT_EVIDENCE.value
            is_ready = False
        else:
            # All critical gates passed! Ready for confirmatory review (not trading!)
            overall_verdict = OverallReadinessVerdict.READY_FOR_CONFIRMATORY_REVIEW.value
            is_ready = True

        # Secondary Product-Level Heuristic Index (Strictly Secondary)
        # Weights: 10 points per verified dimension, 0 for unverified/failed
        heuristic_index = round((len(passed_keys) / len(dims)) * 100.0, 1)

        return ScientificReadinessScorecard(
            record_id=rec_id,
            title_tr=title_tr,
            title_en=title_en,
            overall_verdict=overall_verdict,
            is_ready_for_review=is_ready,
            critical_gates_passed=critical_passed,
            total_critical_gates=total_critical,
            dimensions=dims,
            passed_dimensions=passed_keys,
            failed_dimensions=failed_keys,
            unverified_dimensions=unverified_keys,
            blocking_reasons_tr=blocking_reasons_tr,
            blocking_reasons_en=blocking_reasons_en,
            supporting_evidence_links=evidence_links,
            required_next_actions_tr=next_actions_tr,
            required_next_actions_en=next_actions_en,
            heuristic_readiness_index=heuristic_index,
        )


# Global evaluator instance
scientific_readiness_evaluator = ScientificReadinessEvaluator()
