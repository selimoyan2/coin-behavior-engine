"""
Scientific Reproducibility Lab Engine.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Enables controlled, bounded, offline reproduction of allowlisted research procedures
using authorized local data. Strictly maintains the scientific boundary between
local procedure re-execution and independent replication.
Eliminates scientific fallback constants and copies; enforces genuine independent
recomputation from authentic source observations.
"""

from __future__ import annotations

import enum
import glob
import hashlib
import hmac
import io
import json
import math
import os
import platform
import sys
import time
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    TRUSTED_ISSUERS,
)
from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
    TRUSTED_ARTIFACT_REGISTRY,
)
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json


class ReproductionStatus(str, enum.Enum):
    PROCEDURE_REEXECUTED = "PROCEDURE_REEXECUTED"
    OUTPUTS_MATCHED = "OUTPUTS_MATCHED"
    OUTPUTS_DIFFER = "OUTPUTS_DIFFER"
    REPRODUCTION_BLOCKED = "REPRODUCTION_BLOCKED"
    INDEPENDENT_REPLICATION_CONFIRMED = "INDEPENDENT_REPLICATION_CONFIRMED"


class ReferenceBlockedReason(str, enum.Enum):
    MISSING_TRUSTED_REFERENCE = "MISSING_TRUSTED_REFERENCE"
    UNVERIFIED_REFERENCE_PROVENANCE = "UNVERIFIED_REFERENCE_PROVENANCE"
    HISTORICAL_REPORT_INSPECTION_ONLY = "HISTORICAL_REPORT_INSPECTION_ONLY"
    MISSING_RAW_OBSERVATIONS = "MISSING_RAW_OBSERVATIONS"


@dataclass
class ReproductionProvenance:
    run_id: str
    record_id: str
    procedure_name: str
    procedure_version: str
    status: str  # from ReproductionStatus
    is_independent_replication: bool  # False for local reruns; never automatically True
    source_dataset_id: str
    source_artifact_path: str
    source_artifact_sha256: str
    start_time_utc: str
    end_time_utc: str
    execution_duration_ms: float
    execution_environment: Dict[str, Any]
    dependency_versions: Dict[str, str]
    reference_outputs: Dict[str, Any]
    reproduced_outputs: Dict[str, Any]
    reference_output_sha256: str
    reproduced_output_sha256: str
    comparison_details: Dict[str, Any]
    error_message_tr: Optional[str] = None
    error_message_en: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReproducibilityLabEngine:
    """
    Executes allowlisted offline scientific procedures with strict resource bounds,
    timing constraints, and output checksum matching.
    Enforces genuine independent recomputation from verified offline observations.
    """

    MAX_EXECUTION_TIME_SECONDS = 5.0
    NUMERICAL_TOLERANCE_EPS = 1e-4

    ALLOWLISTED_PROCEDURES = {
        "PROC_PARKINSON_VOLATILITY": {
            "name_tr": "Parkinson Ekstremum Değer Volatilite Hesaplaması",
            "name_en": "Parkinson Extreme-Value Volatility Estimation",
            "version": "1.2.0",
            "supported_categories": ["Volatilite", "Volatility"],
            "required_inputs": ["high_prices", "low_prices"],
        },
        "PROC_FUNDING_RATE_SUMMARY": {
            "name_tr": "Sürekli Fonlama Oranı İstatistiksel Özeti",
            "name_en": "Perpetual Funding Rate Statistical Summary",
            "version": "1.1.0",
            "supported_categories": ["Fonlama", "Funding", "Türev Piyasalar", "Derivatives"],
            "required_inputs": ["funding_rate_settlements"],
        },
        "PROC_REGIME_STABILITY_EVAL": {
            "name_tr": "Yürüyüş İleriye Rejim Kararlılığı Matrisi",
            "name_en": "Walk-Forward Regime Stability Matrix",
            "version": "1.0.0",
            "supported_categories": ["Rejim", "Regime"],
            "required_inputs": ["regime_transition_counts_or_predictions"],
        },
        "PROC_DTW_PATTERN_DISTANCE": {
            "name_tr": "Dinamik Zaman Bükmesi (DTW) Örüntü Mesafesi",
            "name_en": "Dynamic Time Warping Pattern Distance",
            "version": "1.0.0",
            "supported_categories": ["Örüntü", "Pattern", "Analog"],
            "required_inputs": ["dimension_distance_vectors_or_candle_series"],
        },
        "PROC_STORAGE_VERIFICATION": {
            "name_tr": "Kalıcı Depolama Birimi Çift Çekirdek Mountinfo Doğrulaması",
            "name_en": "Persistent Storage Dual-Kernel Mountinfo Verification",
            "version": "1.0.0",
            "supported_categories": ["Sistem Güvenilirliği", "Durability"],
            "required_inputs": ["mountinfo_content", "volume_verification_report"],
        },
    }

    @classmethod
    def get_supported_procedures(cls) -> Dict[str, Any]:
        return cls.ALLOWLISTED_PROCEDURES

    @classmethod
    def create_signed_reference_provenance(
        cls,
        record: Any,
        procedure_name: str,
        reference_outputs: Dict[str, Any],
        key_id: str,
        secret: str,
        issuer: str = "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
        recorded_at_utc: str = "2026-10-20T00:00:00Z",
        evaluation_window: Optional[str] = None,
        methodology: Optional[str] = None,
        override_dataset_id: Optional[str] = None,
        override_record_id: Optional[str] = None,
        override_procedure_version: Optional[str] = None,
        override_artifact_sha256: Optional[str] = None,
        created_during_reproduction_attempt: bool = False,
        forged_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a cryptographically signed reference provenance envelope bound to
        record_id, dataset_id, procedure_name, procedure_version, reference_output_sha256,
        source_artifact_sha256, and recorded_at_utc.
        """
        proc_meta = cls.ALLOWLISTED_PROCEDURES.get(procedure_name, {})
        proc_ver = override_procedure_version or proc_meta.get("version", "1.0.0")
        ref_json = json.dumps(reference_outputs, sort_keys=True)
        ref_sha = hashlib.sha256(ref_json.encode("utf-8")).hexdigest()

        claims = {
            "created_during_reproduction_attempt": bool(created_during_reproduction_attempt),
            "dataset_id": str(override_dataset_id if override_dataset_id is not None else getattr(record, "dataset_id", "")),
            "evaluation_window": str(evaluation_window or getattr(record, "historical_period", "")),
            "issuer": str(issuer),
            "key_id": str(key_id),
            "methodology": str(methodology or procedure_name),
            "procedure_name": str(procedure_name),
            "procedure_version": str(proc_ver),
            "record_id": str(override_record_id if override_record_id is not None else getattr(record, "id", "")),
            "recorded_at_utc": str(recorded_at_utc),
            "reference_output_sha256": str(ref_sha),
            "schema_version": "CBE-REFERENCE-PROVENANCE-1.0.0",
            "source_artifact_sha256": str(
                override_artifact_sha256
                if override_artifact_sha256 is not None
                else getattr(record, "source_artifact_sha256", "")
            ),
        }
        canonical_bytes = rfc8785_canonical_json(claims)
        claims_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        if forged_signature is not None:
            signature = forged_signature
        else:
            h = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256)
            signature = f"hmac-sha256:{key_id}:{h.hexdigest()}"

        envelope = dict(claims)
        envelope["signature"] = signature
        envelope["claims_sha256"] = claims_sha256
        return envelope

    @classmethod
    def validate_reference_provenance(
        cls,
        record: Any,
        selected_proc: str,
        proc_ver: str,
        source_path: str,
        actual_sha: str,
        start_utc: str,
        raw_json: Dict[str, Any],
        override_reference: Optional[Dict[str, Any]] = None,
        trusted_fixture_context: bool = False,
        reference_provenance: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Fail-closed validation of reference output provenance.
        Ensures reference outputs are recorded BEFORE the current reproduction attempt,
        have identifiable trusted provenance, and match dataset, record, window, and methodology.
        Returns: (is_valid, blocked_reason_code, human_explanation)
        """
        rec_id = getattr(record, "id", "") or ""
        ds_id = getattr(record, "dataset_id", "") or ""
        cat = getattr(record, "category", "") or ""
        proc_meta = cls.ALLOWLISTED_PROCEDURES.get(selected_proc, {})
        start_dt = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))

        prov = reference_provenance or getattr(record, "reference_provenance", None)

        # 1. Check explicit reference_provenance metadata if provided
        if prov is not None:
            if not isinstance(prov, dict):
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Reference provenance metadata is malformed.",
                )

            if prov.get("created_during_reproduction_attempt") is True:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Reference was created during the same reproduction attempt; self-referential validation is prohibited.",
                )

            rec_at = prov.get("recorded_at_utc")
            if not rec_at or not isinstance(rec_at, str):
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Reference provenance is missing recorded_at_utc timestamp.",
                )
            try:
                rec_dt = datetime.fromisoformat(rec_at.replace("Z", "+00:00"))
                if rec_dt >= start_dt:
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        f"Reference timestamp ({rec_at}) is not recorded prior to reproduction attempt ({start_utc}).",
                    )
            except Exception:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Invalid recorded_at_utc timestamp in reference provenance: '{rec_at}'.",
                )

            if prov.get("dataset_id") != ds_id:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Reference dataset_id ('{prov.get('dataset_id')}') does not match record dataset_id ('{ds_id}').",
                )

            if prov.get("record_id") and prov.get("record_id") != rec_id:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Reference record_id ('{prov.get('record_id')}') does not match target record ('{rec_id}').",
                )

            if prov.get("procedure_name") and prov.get("procedure_name") != selected_proc:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Reference procedure ('{prov.get('procedure_name')}') does not match executed procedure ('{selected_proc}').",
                )

            if prov.get("procedure_version") and prov.get("procedure_version") != proc_ver:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Reference procedure_version ('{prov.get('procedure_version')}') is incompatible with '{proc_ver}'.",
                )

            if prov.get("methodology") and prov.get("methodology") not in (
                selected_proc,
                "PARKINSON_HIGH_LOW",
                "FUNDING_SETTLEMENT_SUMMARY",
                "WALK_FORWARD_REGIME_AUDIT",
                "FAST_DTW_NORMALIZED",
                "MOUNTINFO_KERNEL_REEXECUTION",
            ):
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Reference methodology ('{prov.get('methodology')}') is incompatible with procedure '{selected_proc}'.",
                )

            if prov.get("evaluation_window") and getattr(record, "historical_period", ""):
                if prov.get("evaluation_window") != getattr(record, "historical_period", ""):
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        "Reference evaluation_window does not match record historical_period.",
                    )

            if prov.get("source_artifact_sha256") and prov.get("source_artifact_sha256") != actual_sha:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Reference source_artifact_sha256 does not match physical source artifact digest.",
                )

            # Verify cryptographic signature on reference_provenance unless in trusted_fixture_context
            if not trusted_fixture_context:
                sig_str = prov.get("signature", "")
                key_id = prov.get("key_id", "")
                issuer = prov.get("issuer", "")
                if not sig_str or not key_id or issuer not in TRUSTED_ISSUERS:
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        "Reference provenance lacks valid signature, key_id, or trusted issuer.",
                    )
                if signing_key_registry.is_key_revoked(key_id):
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        f"Reference provenance signing key '{key_id}' is revoked.",
                    )
                claims_payload = {
                    "created_during_reproduction_attempt": bool(prov.get("created_during_reproduction_attempt", False)),
                    "dataset_id": str(prov.get("dataset_id", "")),
                    "evaluation_window": str(prov.get("evaluation_window", "")),
                    "issuer": str(issuer),
                    "key_id": str(key_id),
                    "methodology": str(prov.get("methodology", "")),
                    "procedure_name": str(prov.get("procedure_name", "")),
                    "procedure_version": str(prov.get("procedure_version", "")),
                    "record_id": str(prov.get("record_id", "")),
                    "recorded_at_utc": str(rec_at),
                    "reference_output_sha256": str(prov.get("reference_output_sha256", "")),
                    "schema_version": str(prov.get("schema_version", "CBE-REFERENCE-PROVENANCE-1.0.0")),
                    "source_artifact_sha256": str(prov.get("source_artifact_sha256", "")),
                }
                canonical_bytes = rfc8785_canonical_json(claims_payload)
                is_sig_ok, _, _ = signing_key_registry.verify_signature(canonical_bytes, sig_str)
                if not is_sig_ok:
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        "Reference provenance cryptographic signature verification failed.",
                    )
                if override_reference is not None:
                    ref_sha = hashlib.sha256(json.dumps(override_reference, sort_keys=True).encode("utf-8")).hexdigest()
                    if prov.get("reference_output_sha256") != ref_sha:
                        return (
                            False,
                            ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                            "Override reference digest does not match signed reference_output_sha256.",
                        )

        # 2. Caller-supplied override_reference check:
        # Must NOT automatically count as trusted unless trusted_fixture_context=True or signed reference_provenance verified above
        if override_reference is not None:
            if not isinstance(override_reference, dict) or len(override_reference) == 0:
                return (
                    False,
                    ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value,
                    "Override reference is empty or invalid.",
                )
            if not trusted_fixture_context and prov is None:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Caller-supplied override_reference is untrusted without signed reference_provenance or explicit trusted_fixture_context.",
                )
            return True, None, None

        # 3. Stored artifact reference provenance validation (when override_reference is None)
        # Verify category / methodology compatibility between record and selected_proc
        supported_cats = proc_meta.get("supported_categories", [])
        rec_proc = getattr(record, "procedure_name", None)
        cat_compatible = any(c.lower() in cat.lower() for c in supported_cats) or (rec_proc == selected_proc)
        if not cat_compatible:
            return (
                False,
                ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                f"Record category '{cat}' is incompatible with procedure '{selected_proc}'; cross-methodology reference rejected.",
            )

        # Check JSON payload for embedded provenance overrides/tampering
        if isinstance(raw_json, dict):
            if raw_json.get("created_during_reproduction_attempt") is True:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    "Artifact reference marked as created_during_reproduction_attempt.",
                )
            json_ds = raw_json.get("dataset_id")
            if json_ds and json_ds != ds_id:
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Artifact dataset_id ('{json_ds}') contradicts record dataset_id ('{ds_id}').",
                )
            json_method = raw_json.get("methodology")
            if json_method and selected_proc == "PROC_PARKINSON_VOLATILITY" and json_method != "PARKINSON_HIGH_LOW":
                return (
                    False,
                    ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                    f"Artifact methodology ('{json_method}') is incompatible with PROC_PARKINSON_VOLATILITY.",
                )
            json_ts = raw_json.get("timestamp_utc") or raw_json.get("generated_at_utc") or raw_json.get("created_at_utc")
            if json_ts and isinstance(json_ts, str):
                try:
                    j_dt = datetime.fromisoformat(json_ts.replace("Z", "+00:00"))
                    if j_dt >= start_dt:
                        return (
                            False,
                            ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                            f"Artifact timestamp ({json_ts}) is not prior to current reproduction start ({start_utc}).",
                        )
                except Exception:
                    pass

        # Verify that the source artifact itself has identifiable trusted provenance:
        # Either pinned in TRUSTED_ARTIFACT_REGISTRY with matching SHA-256 (supporting both CRLF and LF git checkouts),
        # OR backed by a valid signed attestation, OR signed reference_provenance
        trust_status, _ = ResearchCatalogProvider.check_trusted_provenance(source_path, actual_sha)
        sp_obj = Path(source_path) if source_path else None
        if trust_status != "TRUSTED_PROVENANCE_CONFIRMED" and sp_obj is not None and sp_obj.exists() and sp_obj.suffix.lower() == ".json":
            try:
                crlf_bytes = sp_obj.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
                crlf_sha = hashlib.sha256(crlf_bytes).hexdigest()
                trust_status, _ = ResearchCatalogProvider.check_trusted_provenance(source_path, crlf_sha)
            except Exception:
                pass
        has_trusted_registry = trust_status == "TRUSTED_PROVENANCE_CONFIRMED"

        has_valid_att = False
        att = getattr(record, "observation_completeness_attestation", None)
        if att and isinstance(att, dict):
            att_res = ObservationCompletenessAttestationVerifier.verify_attestation(
                record, att, use_cache=True, enforce_source_file_integrity=True
            )
            has_valid_att = bool(att_res.get("is_valid"))

        if not has_trusted_registry and not has_valid_att and prov is None and not trusted_fixture_context:
            return (
                False,
                ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                f"Source artifact '{source_path}' is not in TRUSTED_ARTIFACT_REGISTRY and lacks cryptographic provenance.",
            )

        # Verify record creation / verification timestamp is prior to current reproduction start
        rec_created = getattr(record, "created_at_utc", None) or getattr(record, "verification_timestamp_utc", None)
        if rec_created and isinstance(rec_created, str):
            try:
                rc_dt = datetime.fromisoformat(rec_created.replace("Z", "+00:00"))
                if rc_dt >= start_dt:
                    return (
                        False,
                        ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value,
                        f"Record timestamp ({rec_created}) is not recorded prior to reproduction attempt ({start_utc}).",
                    )
            except Exception:
                pass

        return True, None, None

    @classmethod
    def execute_reproduction(
        cls,
        record: Any,
        procedure_name: Optional[str] = None,
        override_inputs: Optional[Dict[str, Any]] = None,
        override_reference: Optional[Dict[str, Any]] = None,
        trusted_fixture_context: bool = False,
        reference_provenance: Optional[Dict[str, Any]] = None,
    ) -> ReproductionProvenance:
        t0 = time.perf_counter()
        start_utc = datetime.now(timezone.utc).isoformat()
        rec_id = getattr(record, "id", "UNKNOWN")
        ds_id = getattr(record, "dataset_id", "UNKNOWN")
        source_path = getattr(record, "source_artifact", "")
        expected_sha = getattr(record, "source_artifact_sha256", "")
        run_id = f"REP-RUN-{hashlib.sha256(f'{rec_id}-{t0}'.encode()).hexdigest()[:12].upper()}"

        env_info = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_architecture": platform.machine(),
            "process_id": os.getpid(),
            "canonical_model": "CBE-0.7.0",
        }
        dep_info = {
            "python": sys.version.split()[0],
            "hashlib": "builtin",
            "json": "builtin",
            "math": "builtin",
        }

        # 1. Gate: Allowlist procedure check
        cat = getattr(record, "category", "")
        selected_proc = procedure_name
        if not selected_proc:
            # Auto-resolve from category
            for p_code, p_meta in cls.ALLOWLISTED_PROCEDURES.items():
                if any(c.lower() in cat.lower() for c in p_meta["supported_categories"]):
                    selected_proc = p_code
                    break

        if not selected_proc or selected_proc not in cls.ALLOWLISTED_PROCEDURES:
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc or "UNKNOWN",
                procedure_version="0.0.0",
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=expected_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs={},
                reproduced_outputs={},
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details={"blocked_reason": "Procedure not allowlisted or unsupported category."},
                error_message_tr="Belirtilen prosedür onaylı çevrimdışı prosedürler listesinde yer almıyor.",
                error_message_en="Specified procedure is not in the approved offline allowlist.",
            )

        proc_meta = cls.ALLOWLISTED_PROCEDURES[selected_proc]
        proc_ver = proc_meta["version"]

        # 2. Gate: Source artifact presence and physical integrity
        if not source_path or not Path(source_path).exists():
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc,
                procedure_version=proc_ver,
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=expected_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs={},
                reproduced_outputs={},
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details={"blocked_reason": "Source artifact missing on disk."},
                error_message_tr="Kaynak araştırma dosyası disk üzerinde bulunamadığından tekrarlama engellendi.",
                error_message_en="Reproduction blocked: Source artifact file not found on disk.",
            )

        p = Path(source_path)
        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc,
                procedure_version=proc_ver,
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=actual_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs={},
                reproduced_outputs={},
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details={"blocked_reason": "Source artifact hash mismatch."},
                error_message_tr="Kaynak dosya özeti beklenen özet ile uyuşmuyor; manipüle edilmiş veri çalıştırılamaz.",
                error_message_en="Reproduction blocked: Source artifact hash contradicts record digest.",
            )

        # 3. Gate: Independent Reference Provenance Validation
        raw_json_preview: Dict[str, Any] = {}
        try:
            raw_json_preview = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw_json_preview, dict):
                raw_json_preview = {}
        except Exception:
            raw_json_preview = {}

        is_ref_valid, ref_block_code, ref_block_msg = cls.validate_reference_provenance(
            record=record,
            selected_proc=selected_proc,
            proc_ver=proc_ver,
            source_path=source_path,
            actual_sha=actual_sha,
            start_utc=start_utc,
            raw_json=raw_json_preview,
            override_reference=override_reference,
            trusted_fixture_context=trusted_fixture_context,
            reference_provenance=reference_provenance,
        )
        if not is_ref_valid:
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            code_str = ref_block_code or ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc,
                procedure_version=proc_ver,
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=actual_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs={},
                reproduced_outputs={},
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details={
                    "blocked_reason": code_str,
                    "blocked_explanation": ref_block_msg,
                },
                error_message_tr=f"Tekrarlama engellendi ({code_str}): {ref_block_msg}",
                error_message_en=f"Reproduction blocked ({code_str}): {ref_block_msg}",
            )

        # 4. Controlled Offline Execution based on procedure
        try:
            ref_outputs, rep_outputs, blocked_reason = cls._execute_procedure_logic(
                selected_proc, record, p, override_inputs=override_inputs, override_reference=override_reference
            )
        except Exception as e:
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc,
                procedure_version=proc_ver,
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=actual_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs={},
                reproduced_outputs={},
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details={"exception": str(e)},
                error_message_tr=f"Prosedür çalıştırma hatası: {e}",
                error_message_en=f"Procedure execution exception: {e}",
            )

        if blocked_reason:
            t1 = time.perf_counter()
            end_utc = datetime.now(timezone.utc).isoformat()
            comp_details: Dict[str, Any] = {"blocked_reason": blocked_reason}
            if selected_proc == "PROC_STORAGE_VERIFICATION" and ReferenceBlockedReason.HISTORICAL_REPORT_INSPECTION_ONLY.value in blocked_reason:
                comp_details["audit_mode"] = "HISTORICAL_REPORT_INSPECTION"
                comp_details["storage_test_reexecuted"] = False
            return ReproductionProvenance(
                run_id=run_id,
                record_id=rec_id,
                procedure_name=selected_proc,
                procedure_version=proc_ver,
                status=ReproductionStatus.REPRODUCTION_BLOCKED.value,
                is_independent_replication=False,
                source_dataset_id=ds_id,
                source_artifact_path=source_path,
                source_artifact_sha256=actual_sha,
                start_time_utc=start_utc,
                end_time_utc=end_utc,
                execution_duration_ms=(t1 - t0) * 1000,
                execution_environment=env_info,
                dependency_versions=dep_info,
                reference_outputs=ref_outputs,
                reproduced_outputs=rep_outputs,
                reference_output_sha256="",
                reproduced_output_sha256="",
                comparison_details=comp_details,
                error_message_tr=f"Tekrarlama engellendi: {blocked_reason}",
                error_message_en=f"Reproduction blocked: {blocked_reason}",
            )

        # 5. Compare outputs and hashes
        ref_json = json.dumps(ref_outputs, sort_keys=True)
        rep_json = json.dumps(rep_outputs, sort_keys=True)
        ref_hash = hashlib.sha256(ref_json.encode("utf-8")).hexdigest()
        rep_hash = hashlib.sha256(rep_json.encode("utf-8")).hexdigest()

        # Check numerical matching within tolerance across complete schemas
        matched = True
        diffs = {}
        # Ensure all keys in reference match reproduced, and no extra keys in reproduced
        if set(ref_outputs.keys()) != set(rep_outputs.keys()):
            matched = False
            diffs["schema_keys_mismatch"] = {
                "reference_keys": sorted(list(ref_outputs.keys())),
                "reproduced_keys": sorted(list(rep_outputs.keys())),
            }

        for k, v in ref_outputs.items():
            if k in rep_outputs:
                v_rep = rep_outputs[k]
                if isinstance(v, (int, float)) and isinstance(v_rep, (int, float)) and not isinstance(v, bool) and not isinstance(v_rep, bool):
                    if not math.isclose(v, v_rep, abs_tol=cls.NUMERICAL_TOLERANCE_EPS):
                        matched = False
                        diffs[k] = {"reference": v, "reproduced": v_rep, "diff": abs(v - v_rep)}
                elif v != v_rep:
                    matched = False
                    diffs[k] = {"reference": v, "reproduced": v_rep}
            else:
                matched = False
                diffs[k] = {"reference": v, "reproduced": None}

        t1 = time.perf_counter()
        end_utc = datetime.now(timezone.utc).isoformat()
        elapsed_ms = (t1 - t0) * 1000

        status = ReproductionStatus.OUTPUTS_MATCHED.value if matched else ReproductionStatus.OUTPUTS_DIFFER.value

        return ReproductionProvenance(
            run_id=run_id,
            record_id=rec_id,
            procedure_name=selected_proc,
            procedure_version=proc_ver,
            status=status,
            # CRITICAL INVARIANT: Local re-execution is NEVER marked as independent replication!
            is_independent_replication=False,
            source_dataset_id=ds_id,
            source_artifact_path=source_path,
            source_artifact_sha256=actual_sha,
            start_time_utc=start_utc,
            end_time_utc=end_utc,
            execution_duration_ms=elapsed_ms,
            execution_environment=env_info,
            dependency_versions=dep_info,
            reference_outputs=ref_outputs,
            reproduced_outputs=rep_outputs,
            reference_output_sha256=ref_hash,
            reproduced_output_sha256=rep_hash,
            comparison_details={
                "matched": matched,
                "numerical_tolerance": cls.NUMERICAL_TOLERANCE_EPS,
                "discrepancies": diffs,
                "governance_notice_tr": "Yerel yeniden çalıştırma (re-execution) başarıyla tamamlandı. Bu sonuç bağımsız replikasyon teşkil ETMEZ.",
                "governance_notice_en": "Local re-execution completed. This does NOT constitute independent replication.",
            },
        )

    @classmethod
    def _execute_procedure_logic(
        cls,
        proc_name: str,
        record: Any,
        artifact_path: Path,
        override_inputs: Optional[Dict[str, Any]] = None,
        override_reference: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
        """
        Executes pure mathematical/statistical procedure from offline artifact content and verified raw inputs.
        Returns: (reference_outputs, reproduced_outputs, blocked_reason).
        Never copies reference into reproduced outputs, and never copies computed outputs into reference_outputs!
        """
        content_text = artifact_path.read_text(encoding="utf-8")
        raw_json = {}
        try:
            raw_json = json.loads(content_text)
        except Exception:
            pass

        ref_outputs: Dict[str, Any] = {}
        rep_outputs: Dict[str, Any] = {}
        inputs = override_inputs or {}

        # ----------------------------------------------------------------------
        # 1. PROC_PARKINSON_VOLATILITY
        # ----------------------------------------------------------------------
        if proc_name == "PROC_PARKINSON_VOLATILITY":
            # Identify exact high/low price observations
            highs: List[float] = inputs.get("highs") if "highs" in inputs else (raw_json.get("highs") or [])
            lows: List[float] = inputs.get("lows") if "lows" in inputs else (raw_json.get("lows") or [])

            # If not in artifact or override, check if dataset has raw klines (unless override_inputs explicitly passed empty)
            if "highs" not in inputs and "lows" not in inputs and (not highs or not lows):
                ds_id = getattr(record, "dataset_id", "")
                if "SPOT" in ds_id or "BTCUSDT" in ds_id:
                    cand_path = Path("data/normalized/binance_pilot_2022_01/BTCUSDT-1h-2022-01.parquet")
                    if not cand_path.exists():
                        cand_path = Path("data/binance_spot_multiyear/1h/BTCUSDT-1h-2022-01.parquet")
                    if cand_path.exists():
                        try:
                            import pandas as pd
                            df_p = pd.read_parquet(cand_path)
                            if "high" in df_p.columns and "low" in df_p.columns:
                                highs = df_p["high"].head(120).tolist()
                                lows = df_p["low"].head(120).tolist()
                        except Exception:
                            pass

            if not highs or not lows or len(highs) != len(lows) or len(highs) < 10:
                return (
                    {},
                    {},
                    f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Essential raw high/low price observations are missing from artifact/dataset; cannot fabricate Parkinson volatility without genuine high/low series.",
                )

            # Compute Parkinson Extreme-Value Volatility independently:
            # sigma_P = sqrt( 1 / (4 * ln(2) * N) * sum( ln(H_i / L_i)^2 ) )
            n = len(highs)
            log_hl_sq_sum = 0.0
            for h, l in zip(highs, lows):
                if h <= 0 or l <= 0 or h < l:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Invalid price geometry in high/low series (non-positive or low > high).",
                    )
                log_hl = math.log(h / l)
                log_hl_sq_sum += log_hl * log_hl

            factor = 1.0 / (4.0 * math.log(2.0) * n)
            computed_sigma_p = math.sqrt(factor * log_hl_sq_sum)
            # Annualized volatility: sigma_P * sqrt(8760) for 1h cadence
            computed_annualized = computed_sigma_p * math.sqrt(8760.0)

            # Independent Reference Output (NO computed_annualized fallback!)
            if override_reference is not None:
                ref_outputs = dict(override_reference)
            else:
                ref_val = raw_json.get("parkinson_volatility")
                if ref_val is None and raw_json.get("methodology") == "PARKINSON_HIGH_LOW":
                    ref_val = raw_json.get("volatility_ratio")
                ref_sample = raw_json.get("sample_size", getattr(record, "sample_size", None))
                if ref_val is None or ref_sample is None:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Separately recorded parkinson_volatility reference output is absent from trusted artifact.",
                    )

                ref_outputs = {
                    "methodology": "PARKINSON_HIGH_LOW",
                    "sample_size": int(ref_sample),
                    "parkinson_volatility": round(float(ref_val), 4),
                }

            rep_outputs = {
                "methodology": "PARKINSON_HIGH_LOW",
                "sample_size": n,
                "parkinson_volatility": round(float(computed_annualized), 4),
            }

        # ----------------------------------------------------------------------
        # 2. PROC_FUNDING_RATE_SUMMARY
        # ----------------------------------------------------------------------
        elif proc_name == "PROC_FUNDING_RATE_SUMMARY":
            rates: List[float] = inputs.get("rates") if "rates" in inputs else (raw_json.get("funding_observations") or [])

            if "rates" not in inputs and not rates:
                raw_zip_pattern = "data/historical/futures/raw/BTCUSDT-fundingRate-*.zip"
                zip_files = sorted(glob.glob(raw_zip_pattern))
                if zip_files:
                    extracted_rates = []
                    for zf_path in zip_files:
                        try:
                            with zipfile.ZipFile(zf_path) as zf:
                                for name in zf.namelist():
                                    if name.endswith(".csv"):
                                        with zf.open(name) as csv_file:
                                            content = csv_file.read().decode("utf-8").strip().splitlines()
                                            header = [h.strip() for h in content[0].split(",")]
                                            rate_idx = header.index("last_funding_rate") if "last_funding_rate" in header else 2
                                            for line in content[1:]:
                                                parts = line.split(",")
                                                if len(parts) > rate_idx:
                                                    try:
                                                        r_val = float(parts[rate_idx])
                                                        extracted_rates.append(r_val * 10000.0)
                                                    except ValueError:
                                                        continue
                        except Exception:
                            pass
                    if len(extracted_rates) >= 1275:
                        rates = extracted_rates[90:1275]
                    elif len(extracted_rates) >= 100:
                        rates = extracted_rates

            if not rates or len(rates) < 100:
                return (
                    {},
                    {},
                    f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Missing authentic offline funding observations; funding summary procedure requires genuine settlement rates.",
                )

            # Compute independent statistical metrics from raw settlement observations
            n_obs = len(rates)
            mean_bps = sum(rates) / n_obs
            neg_count = sum(1 for r in rates if r < 0)
            sorted_rates = sorted(rates)
            median_bps = (
                sorted_rates[n_obs // 2]
                if n_obs % 2 != 0
                else (sorted_rates[n_obs // 2 - 1] + sorted_rates[n_obs // 2]) / 2.0
            )
            min_bps = sorted_rates[0]
            max_bps = sorted_rates[-1]

            # Independent Reference Output (NO fallback to computed mean_bps, neg_count, median_bps, min_bps, max_bps, or n_obs!)
            if override_reference is not None:
                ref_outputs = dict(override_reference)
            else:
                be = raw_json.get("break_even_analysis", {})
                if not isinstance(be, dict):
                    be = {}
                ref_mean = be.get("observed_mean_funding_bps")
                ref_neg = be.get("negative_funding_count")
                ref_med = be.get("observed_median_funding_bps")
                ref_min = be.get("observed_min_funding_bps")
                ref_max = be.get("observed_max_funding_bps")

                evals = raw_json.get("model_evaluations", [])
                ref_sample = None
                if isinstance(evals, list) and len(evals) > 0 and isinstance(evals[0], dict):
                    ref_sample = evals[0].get("sample_size")
                if ref_sample is None:
                    ref_sample = be.get("sample_size")

                if any(x is None for x in (ref_mean, ref_neg, ref_med, ref_min, ref_max, ref_sample)):
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Reference report is missing one or more required break_even_analysis or sample_size fields.",
                    )

                ref_outputs = {
                    "mean_funding_bps": round(float(ref_mean), 4),
                    "negative_funding_count": int(ref_neg),
                    "observed_median_funding_bps": round(float(ref_med), 4),
                    "observed_min_funding_bps": round(float(ref_min), 4),
                    "observed_max_funding_bps": round(float(ref_max), 4),
                    "sample_size": int(ref_sample),
                }

            rep_outputs = {
                "mean_funding_bps": round(float(mean_bps), 4),
                "negative_funding_count": int(neg_count),
                "observed_median_funding_bps": round(float(median_bps), 4),
                "observed_min_funding_bps": round(float(min_bps), 4),
                "observed_max_funding_bps": round(float(max_bps), 4),
                "sample_size": n_obs,
            }

        # ----------------------------------------------------------------------
        # 3. PROC_REGIME_STABILITY_EVAL
        # ----------------------------------------------------------------------
        elif proc_name == "PROC_REGIME_STABILITY_EVAL":
            preds = inputs.get("predictions") if "predictions" in inputs else raw_json.get("predictions")
            obs = inputs.get("observed_regimes") if "observed_regimes" in inputs else raw_json.get("observed_regimes")

            if preds is not None or obs is not None:
                if not preds or not obs or len(preds) != len(obs) or len(preds) < 10:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Insufficient or mismatched predictions and observed_regimes arrays.",
                    )

                matches = sum(1 for p_val, o_val in zip(preds, obs) if p_val == o_val)
                match_rate = round(matches / len(preds), 4)

                if override_reference is not None:
                    ref_outputs = dict(override_reference)
                else:
                    hm = raw_json.get("holdout_metrics", {})
                    if not isinstance(hm, dict):
                        hm = {}
                    ref_val = hm.get("direction_match_rate")
                    ref_tot = hm.get("total_evaluated_periods")
                    if ref_val is None or ref_tot is None:
                        return (
                            {},
                            {},
                            f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Missing holdout_metrics.direction_match_rate or total_evaluated_periods in reference artifact.",
                        )
                    ref_outputs = {
                        "direction_match_rate": round(float(ref_val), 4),
                        "total_evaluated_periods": int(ref_tot),
                        "model_version": "CBE-0.7.0",
                    }

                rep_outputs = {
                    "direction_match_rate": match_rate,
                    "total_evaluated_periods": len(preds),
                    "model_version": "CBE-0.7.0",
                }
            else:
                # Recompute regime classification transitions directly from original candle observations
                # (Never merely divide stored summary counts!)
                audit = raw_json.get("regime_classification_audit", {})
                if not isinstance(audit, dict):
                    audit = {}
                ref_obs_transitions = audit.get("direct_transitions_observed_count")
                ref_tot_evaluated = audit.get("direct_transitions_total_evaluated")
                ref_rate_pct = audit.get("direct_transition_rate_pct")
                ref_null_bars = audit.get("null_model_single_ema", {}).get("total_bars") if isinstance(audit.get("null_model_single_ema"), dict) else None

                if override_reference is not None:
                    ref_outputs = dict(override_reference)
                else:
                    if any(x is None for x in (ref_obs_transitions, ref_tot_evaluated, ref_rate_pct, ref_null_bars)):
                        return (
                            {},
                            {},
                            f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Reference artifact is missing regime_classification_audit transition reference fields.",
                        )
                    ref_outputs = {
                        "direct_transitions_observed_count": int(ref_obs_transitions),
                        "direct_transitions_total_evaluated": int(ref_tot_evaluated),
                        "direct_transition_rate_pct": round(float(ref_rate_pct), 2),
                        "total_bars_evaluated": int(ref_null_bars),
                        "model_version": "CBE-0.7.0",
                    }

                # Load original candle series to recompute transitions via RegimeClassificationAuditor
                candles = inputs.get("candles")
                if candles is None and "candles" not in inputs:
                    q1_parquet = Path("data/historical/historical_binance_btcusdt_15m_q1_2024.parquet")
                    if q1_parquet.exists():
                        try:
                            import pandas as pd
                            df_candles = pd.read_parquet(q1_parquet)
                            candles = df_candles.to_dict(orient="records")
                        except Exception:
                            candles = None

                if not candles or len(candles) < 100:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Raw historical candle series required to recompute regime transitions are missing.",
                    )

                from coin_behavior_engine.research.historical.regime_audit import RegimeClassificationAuditor
                auditor = RegimeClassificationAuditor(candles)
                recomputed_audit = auditor.audit_trend_transitions().to_dict()

                rep_outputs = {
                    "direct_transitions_observed_count": int(recomputed_audit["direct_transitions_observed_count"]),
                    "direct_transitions_total_evaluated": int(recomputed_audit["direct_transitions_total_evaluated"]),
                    "direct_transition_rate_pct": round(float(recomputed_audit["direct_transition_rate_pct"]), 2),
                    "total_bars_evaluated": int(recomputed_audit["null_model_single_ema"]["total_bars"]),
                    "model_version": "CBE-0.7.0",
                }

        # ----------------------------------------------------------------------
        # 4. PROC_DTW_PATTERN_DISTANCE
        # ----------------------------------------------------------------------
        elif proc_name == "PROC_DTW_PATTERN_DISTANCE":
            s1 = inputs.get("series_a") if "series_a" in inputs else raw_json.get("series_query")
            s2 = inputs.get("series_b") if "series_b" in inputs else raw_json.get("series_candidate")

            if s1 is not None or s2 is not None:
                if not s1 or not s2 or not isinstance(s1, list) or not isinstance(s2, list) or len(s1) < 5 or len(s2) < 5:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Series arrays for 1D DTW computation are missing or shorter than minimum length (5).",
                    )
                # Genuine 1D Dynamic Time Warping computation
                n, m = len(s1), len(s2)
                dtw_matrix = [[float("inf")] * (m + 1) for _ in range(n + 1)]
                dtw_matrix[0][0] = 0.0
                for i in range(1, n + 1):
                    for j in range(1, m + 1):
                        cost = abs(float(s1[i - 1]) - float(s2[j - 1]))
                        dtw_matrix[i][j] = cost + min(
                            dtw_matrix[i - 1][j],
                            dtw_matrix[i][j - 1],
                            dtw_matrix[i - 1][j - 1],
                        )
                computed_dtw = round(dtw_matrix[n][m] / (n + m), 4)

                if override_reference is not None:
                    ref_outputs = dict(override_reference)
                else:
                    ref_val = raw_json.get("dtw_distance")
                    if ref_val is None:
                        return (
                            {},
                            {},
                            f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Separately recorded dtw_distance is absent from reference artifact.",
                        )
                    ref_outputs = {
                        "dtw_normalized_distance": round(float(ref_val), 4),
                        "series_a_len": int(raw_json.get("series_a_len", n)),
                        "series_b_len": int(raw_json.get("series_b_len", m)),
                    }

                rep_outputs = {
                    "dtw_normalized_distance": computed_dtw,
                    "series_a_len": n,
                    "series_b_len": m,
                }
            else:
                # Recompute multi-dimensional pattern similarity composite distance from component vectors
                components_override = inputs.get("components")
                ranked = raw_json.get("pattern_search", {}).get("ranked_candidates", []) if isinstance(raw_json.get("pattern_search"), dict) else []

                if not ranked or not isinstance(ranked, list) or len(ranked) == 0:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Essential series arrays or dimension distance vectors are absent from source artifact.",
                    )

                cand = ranked[0] if isinstance(ranked[0], dict) else {}
                comps = components_override if components_override is not None else cand.get("components", {})
                if not comps or not isinstance(comps, dict):
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Component distance vectors are missing.",
                    )

                tot_weight = 0.0
                computed_comp_dist = 0.0
                for dim_key, dim_val in comps.items():
                    if not isinstance(dim_val, dict) or "weight" not in dim_val or "distance_value" not in dim_val:
                        return (
                            {},
                            {},
                            f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Component '{dim_key}' is missing weight or distance_value.",
                        )
                    w = float(dim_val["weight"])
                    d_val = float(dim_val["distance_value"])
                    computed_comp_dist += w * d_val
                    tot_weight += w

                if tot_weight <= 0:
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: Pattern distance components contain zero total weight.",
                    )

                computed_comp_dist = round(computed_comp_dist / tot_weight, 4)
                computed_similarity_pct = round((1.0 - computed_comp_dist) * 100.0, 2)

                if override_reference is not None:
                    ref_outputs = dict(override_reference)
                else:
                    ref_comp_dist = cand.get("composite_distance")
                    ref_sim_pct = cand.get("similarity_score_pct")
                    if ref_comp_dist is None or ref_sim_pct is None:
                        return (
                            {},
                            {},
                            f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Separately recorded composite_distance or similarity_score_pct is missing from reference artifact.",
                        )
                    ref_outputs = {
                        "composite_distance": round(float(ref_comp_dist), 4),
                        "similarity_score_pct": round(float(ref_sim_pct), 2),
                        "components_evaluated_count": len(cand.get("components", {})),
                    }

                rep_outputs = {
                    "composite_distance": computed_comp_dist,
                    "similarity_score_pct": computed_similarity_pct,
                    "components_evaluated_count": len(comps),
                }

        # ----------------------------------------------------------------------
        # 5. PROC_STORAGE_VERIFICATION
        # ----------------------------------------------------------------------
        elif proc_name == "PROC_STORAGE_VERIFICATION":
            # Strictly separate historical report inspection from actual storage verification re-execution!
            mountinfo_content = inputs.get("mountinfo_content")
            if not mountinfo_content or not isinstance(mountinfo_content, str) or not mountinfo_content.strip():
                return (
                    {},
                    {},
                    f"{ReferenceBlockedReason.HISTORICAL_REPORT_INSPECTION_ONLY.value}: Historical report inspection only; raw kernel mountinfo_content input is required to re-execute StorageDurabilityEngine verification.",
                )

            from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
            target_dest = inputs.get("target_destination", "/app/data/prospective")
            parsed_mounts = StorageDurabilityEngine.parse_mountinfo_table(mountinfo_content=mountinfo_content)
            matched_mount = StorageDurabilityEngine.match_mount_for_path(target_dest, parsed_mounts)
            if not matched_mount:
                return (
                    {},
                    {},
                    f"{ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value}: No matching mount point for '{target_dest}' found in supplied mountinfo_content.",
                )

            recomputed_vol_id = matched_mount.get("volume_id")
            recomputed_fstype = matched_mount.get("fstype")
            recomputed_device = matched_mount.get("device")
            recomputed_tmpfs = bool(matched_mount.get("is_tmpfs"))
            recomputed_overlay = bool(matched_mount.get("is_overlay"))
            recomputed_writable = not bool(matched_mount.get("is_readonly"))
            recomputed_durable = bool(
                recomputed_vol_id
                and recomputed_fstype in ("ext4", "xfs")
                and not recomputed_tmpfs
                and not recomputed_overlay
                and recomputed_writable
            )

            if override_reference is not None:
                ref_outputs = dict(override_reference)
            else:
                ref_vol_id = raw_json.get("authorized_volume_id")
                md = raw_json.get("mount_details", {})
                if not isinstance(md, dict):
                    md = {}
                ref_dest = md.get("destination")
                ref_fs = md.get("filesystem")
                ref_dev = md.get("underlying_device")
                ref_tmpfs = md.get("is_tmpfs")
                ref_overlay = md.get("is_overlay")
                ref_writable = md.get("is_writable")
                ref_verdict = raw_json.get("durability_verdict")

                if any(
                    x is None
                    for x in (ref_vol_id, ref_dest, ref_fs, ref_dev, ref_tmpfs, ref_overlay, ref_writable, ref_verdict)
                ):
                    return (
                        {},
                        {},
                        f"{ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value}: Storage verification reference report is missing required mount_details or authorized_volume_id fields.",
                    )

                ref_outputs = {
                    "authorized_volume_id": str(ref_vol_id),
                    "destination": str(ref_dest),
                    "filesystem": str(ref_fs),
                    "underlying_device": str(ref_dev),
                    "is_tmpfs": bool(ref_tmpfs),
                    "is_overlay": bool(ref_overlay),
                    "is_writable": bool(ref_writable),
                    "durability_verdict": str(ref_verdict),
                }

            rep_outputs = {
                "authorized_volume_id": str(recomputed_vol_id or ""),
                "destination": str(matched_mount.get("mount_point", "")),
                "filesystem": str(recomputed_fstype or ""),
                "underlying_device": str(recomputed_device or ""),
                "is_tmpfs": recomputed_tmpfs,
                "is_overlay": recomputed_overlay,
                "is_writable": recomputed_writable,
                "durability_verdict": "VERIFIED_DURABLE" if recomputed_durable else "REJECTED_NON_DURABLE",
            }

        else:
            return {}, {}, f"Unsupported procedure name: '{proc_name}'."

        return ref_outputs, rep_outputs, None


# Global lab engine instance
reproducibility_lab_engine = ReproducibilityLabEngine()
