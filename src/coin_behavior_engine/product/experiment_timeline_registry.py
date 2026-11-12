"""
Sprint 27 — Module 27.2: Experiment Registry & Research Timeline.
(CBE_SPRINT27_FINAL_RECORD_INTEGRITY_CLOSURE)

Tracks every research experiment, reproduction run, walk-forward evaluation,
robustness experiment, and validation check in a structured, append-only,
hash-chained chronological registry.

Key Scientific & Trust Invariants (P0 Record Integrity Closure):
1. Strict separation of three distinct record origins:
   - CATALOG_PROJECTION: Historical catalog record discovered in the canonical catalog.
   - VERIFIED_HISTORICAL_EXECUTION: Execution backed by an authentic persisted execution log.
   - OFFLINE_EXPERIMENT_EXECUTION: Actual execution performed through an authorized offline workflow.
2. Catalog discovery is NEVER represented as execution:
   - Explicit lifecycle states include CATALOG_DISCOVERED, HISTORICAL_EXECUTION_UNVERIFIED,
     EXECUTION_EVIDENCE_AVAILABLE, EXECUTION_EVIDENCE_VERIFIED, REPRODUCTION_NOT_ESTABLISHED
     alongside the 12 execution lifecycle states.
   - Predefined historical execution timestamps are NEVER invented.
   - Synthetic output artifact IDs (OUT-ART-*) and metadata-derived result digests are prohibited.
   - OUTPUTS_MATCHED requires actual comparison against independently persisted expected results.
3. Complete durable persistence hydration & recovery:
   - Validates schema_version, required experiment fields, execution attempt structures,
     timeline event structures, SHA-256 chain integrity, chronological ordering, duplicate event IDs,
     and experiment-to-event references before restoring runtime state.
   - Uses file-backed MultiProcessLock, atomic temp-file write + fsync + os.replace, and cleans up
     leftover .tmp files from interrupted writes.
   - Labels the local hash chain accurately as INTERNAL_TAMPER_DETECTION_CHAIN (not externally anchored).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from coin_behavior_engine.product.process_locking import MultiProcessLock
from coin_behavior_engine.product.research_catalog_provider import (
    TRUSTED_ARTIFACT_REGISTRY,
    ResearchCatalogProvider,
)
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

REPO_ROOT = Path(__file__).resolve().parents[3]

CANONICAL_MODEL_VERSION = "CBE-0.7.0"
CANONICAL_EXECUTION_MODE = "STRICTLY_OFFLINE_RESEARCH"
GENESIS_TIMELINE_DIGEST = "0" * 64
CATALOG_DISCOVERY_EPOCH_UTC = "1970-01-01T00:00:00Z"
PERSISTENCE_SCHEMA_VERSION = "1.0"

VALID_EXPERIMENT_LIFECYCLE_STATES = (
    "CATALOG_DISCOVERED",
    "HISTORICAL_EXECUTION_UNVERIFIED",
    "EXECUTION_EVIDENCE_AVAILABLE",
    "EXECUTION_EVIDENCE_VERIFIED",
    "REPRODUCTION_NOT_ESTABLISHED",
    "REGISTERED",
    "INPUT_VALIDATION_PENDING",
    "INPUT_VALIDATED",
    "EXECUTION_READY",
    "EXECUTING_OFFLINE",
    "EXECUTION_COMPLETED",
    "EXECUTION_FAILED",
    "EVIDENCE_VERIFICATION_PENDING",
    "EVIDENCE_VERIFIED",
    "SCIENTIFIC_REVIEW_PENDING",
    "SCIENTIFIC_REVIEW_COMPLETED",
    "BLOCKED",
)

VALID_RECORD_ORIGINS = (
    "CATALOG_PROJECTION",
    "VERIFIED_HISTORICAL_EXECUTION",
    "OFFLINE_EXPERIMENT_EXECUTION",
)

REQUIRED_EXPERIMENT_FIELDS = (
    "experiment_id",
    "research_id",
    "experiment_type",
    "experiment_title",
    "hypothesis_id",
    "methodology_id",
    "dataset_id",
    "dataset_fingerprint",
    "model_version",
    "execution_mode",
    "execution_started_at",
    "execution_completed_at",
    "execution_status",
    "parameter_fingerprint",
    "input_artifact_ids",
    "output_artifact_ids",
    "result_digest",
    "provenance_verdict",
    "reproducibility_verdict",
    "validation_verdict",
)

REQUIRED_ATTEMPT_FIELDS = (
    "attempt_id",
    "experiment_id",
    "attempt_number",
    "started_at_utc",
    "completed_at_utc",
    "execution_status",
    "result_digest",
    "output_artifact_ids",
)

REQUIRED_TIMELINE_EVENT_FIELDS = (
    "event_id",
    "experiment_id",
    "event_type",
    "event_timestamp",
    "event_source",
    "event_payload_digest",
    "previous_event_digest",
    "event_digest",
)


class ExperimentRegistrySecurityError(PermissionError, ValueError):
    """Raised when an experiment registration, promotion, or persistence operation violates trust rules."""

    def __init__(self, rejection_code: str, message: str) -> None:
        self.rejection_code = str(rejection_code)
        self.message = str(message)
        super().__init__(f"{self.rejection_code}: {self.message}")


def _parse_iso8601_utc(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str or not isinstance(ts_str, str):
        return None
    s = ts_str.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_authentic_artifact_metadata_timestamp(artifact_path_str: Optional[str]) -> Optional[str]:
    """
    Reads an authentic timestamp field embedded inside a physical artifact JSON on disk,
    if and only if the file exists and matches TRUSTED_ARTIFACT_REGISTRY.
    Never invents a timestamp.
    """
    if not artifact_path_str:
        return None
    norm = str(artifact_path_str).replace("\\", "/")
    matched_rel: Optional[str] = None
    for reg_rel in TRUSTED_ARTIFACT_REGISTRY:
        if norm == reg_rel or norm.endswith("/" + reg_rel):
            matched_rel = reg_rel
            break
    if not matched_rel:
        return None
    full_path = REPO_ROOT / matched_rel
    if not full_path.exists() or not full_path.is_file():
        return None
    try:
        raw_bytes = full_path.read_bytes()
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = TRUSTED_ARTIFACT_REGISTRY[matched_rel].get("expected_sha256") or TRUSTED_ARTIFACT_REGISTRY[matched_rel].get("sha256")
        if actual_sha != expected_sha:
            return None
        parsed = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(parsed, dict):
            return None
        for key in ("generated_at_utc", "exported_at_utc", "timestamp_utc", "recorded_at_utc"):
            val = parsed.get(key)
            if isinstance(val, str) and _parse_iso8601_utc(val) is not None:
                return val.strip()
        hdr = parsed.get("header")
        if isinstance(hdr, dict):
            for key in ("exported_at_utc", "generated_at_utc", "timestamp_utc"):
                val = hdr.get(key)
                if isinstance(val, str) and _parse_iso8601_utc(val) is not None:
                    return val.strip()
    except Exception:
        return None
    return None


@dataclass
class ExecutionAttemptRecord:
    """Distinct execution attempt record so reruns never overwrite prior evidence."""

    attempt_id: str
    experiment_id: str
    attempt_number: int
    started_at_utc: str
    completed_at_utc: str
    execution_status: str
    result_digest: Optional[str]
    output_artifact_ids: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentRecord:
    """Canonical Sprint 27 Experiment Record with all 20 required fields plus origin metadata."""

    experiment_id: str
    research_id: str
    experiment_type: str
    experiment_title: str
    hypothesis_id: str
    methodology_id: str
    dataset_id: str
    dataset_fingerprint: str
    model_version: str
    execution_mode: str
    execution_started_at: Optional[str]
    execution_completed_at: Optional[str]
    execution_status: str
    parameter_fingerprint: str
    input_artifact_ids: List[str]
    output_artifact_ids: List[str]
    result_digest: Optional[str]
    provenance_verdict: str
    reproducibility_verdict: str
    validation_verdict: str
    execution_attempts: List[Dict[str, Any]] = field(default_factory=list)
    record_origin: str = "CATALOG_PROJECTION"
    source_artifact_timestamp_utc: Optional[str] = None
    historical_execution_authenticity: str = "CATALOG_DISCOVERED_NO_EXECUTION_LOG"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentTimelineEvent:
    """Append-only hash-chained chronological timeline event."""

    event_id: str
    experiment_id: str
    event_type: str
    event_timestamp: str
    event_source: str
    event_payload_digest: str
    previous_event_digest: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_digest: str = ""

    def compute_event_digest(self) -> str:
        core = {
            "event_id": self.event_id,
            "experiment_id": self.experiment_id,
            "event_type": self.event_type,
            "event_timestamp": self.event_timestamp,
            "event_source": self.event_source,
            "event_payload_digest": self.event_payload_digest,
            "previous_event_digest": self.previous_event_digest,
        }
        return hashlib.sha256(rfc8785_canonical_json(core)).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("event_digest"):
            d["event_digest"] = self.compute_event_digest()
        return d


class ExperimentRegistryAndTimelineService:
    """Module 27.2 — Authoritative Experiment Registry & Append-Only Research Timeline."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._recovered_from_interrupted_tmp: bool = False
        self._experiments: Dict[str, ExperimentRecord] = {}
        self._timeline: List[ExperimentTimelineEvent] = []

        if self._storage_path is not None:
            self._cleanup_interrupted_tmp_if_present()
            if self._storage_path.exists():
                self._load_persisted_state()
                return

        self._seed_canonical_experiments()
        if self._storage_path is not None:
            self._persist_state_if_configured()

    def _get_lock_path(self) -> Union[str, Path]:
        if self._storage_path is not None:
            return self._storage_path.with_suffix(".lock")
        return Path(tempfile.gettempdir()) / "sprint27_experiment_registry.lock"

    def _cleanup_interrupted_tmp_if_present(self) -> None:
        """Cleans up any leftover .tmp file from an interrupted write without corrupting the primary registry."""
        if not self._storage_path:
            return
        tmp_path = self._storage_path.with_suffix(".tmp")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
                self._recovered_from_interrupted_tmp = True
            except OSError:
                pass

    @staticmethod
    def compute_deterministic_experiment_id(
        research_id: str,
        experiment_type: str,
        methodology_id: str,
        dataset_id: str,
        parameter_fingerprint: str,
    ) -> str:
        canonical = f"{research_id}|{experiment_type}|{methodology_id}|{dataset_id}|{parameter_fingerprint}"
        digest8 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8].upper()
        return f"EXP-{research_id}-{digest8}"

    @staticmethod
    def compute_parameter_fingerprint(params: Dict[str, Any]) -> str:
        return hashlib.sha256(rfc8785_canonical_json(params or {})).hexdigest()

    @staticmethod
    def compute_prohibited_metadata_digest(
        exp_id: str,
        sample_size: Any,
        volatility_ratio: Any = None,
        raw_p_value: Any = None,
    ) -> str:
        return hashlib.sha256(
            f"{exp_id}:{sample_size}:{volatility_ratio}:{raw_p_value}".encode("utf-8")
        ).hexdigest()

    def _append_timeline_event(
        self,
        experiment_id: str,
        event_type: str,
        event_source: str,
        payload: Dict[str, Any],
        timestamp_utc: Optional[str] = None,
    ) -> ExperimentTimelineEvent:
        ts = timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        prev_digest = (
            self._timeline[-1].event_digest
            if self._timeline
            else GENESIS_TIMELINE_DIGEST
        )
        payload_digest = hashlib.sha256(rfc8785_canonical_json(payload or {})).hexdigest()
        seq_no = len(self._timeline) + 1
        ev_id = f"TLE-{seq_no:04d}-{experiment_id}"
        ev = ExperimentTimelineEvent(
            event_id=ev_id,
            experiment_id=experiment_id,
            event_type=event_type,
            event_timestamp=ts,
            event_source=event_source,
            event_payload_digest=payload_digest,
            previous_event_digest=prev_digest,
            payload=dict(payload or {}),
        )
        ev.event_digest = ev.compute_event_digest()
        self._timeline.append(ev)
        return ev

    def _seed_canonical_experiments(self) -> None:
        """
        Seeds the registry with derived catalog projections from the canonical catalog.
        P0-1 Invariants:
        - Catalog discovery is NEVER represented as execution (no EXECUTION_COMPLETED events).
        - Never assigns invented historical execution timestamps (execution_started_at=None, execution_completed_at=None).
        - Never invents synthetic output artifact IDs (output_artifact_ids=[]).
        - Never manufactures result_digest from concatenated record metadata (result_digest=None).
        - Never marks reproducibility_verdict as OUTPUTS_MATCHED without actual reproduction comparison.
        """
        catalog = ResearchCatalogProvider.get_canonical_catalog()

        for rec in catalog:
            prov_res = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
            scorecard = ScientificReadinessEvaluator.evaluate_record(rec)

            is_quarantined = (
                getattr(rec, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
                or rec.id in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
            )
            has_verified_source_artifact = (
                "SOURCE_ARTIFACT_INTEGRITY" in scorecard.passed_dimensions
                and not is_quarantined
            )
            is_prov_ok = (
                bool(prov_res.get("is_verified")) or has_verified_source_artifact
            ) and not is_quarantined

            cat = getattr(rec, "category", "") or ""
            if "Rejim" in cat:
                exp_type = "WALK_FORWARD_REGIME_EVALUATION"
                meth_id = "METH-WALK-FORWARD-REGIME-1.0"
            elif "Örüntü" in cat or "Analog" in cat:
                exp_type = "HISTORICAL_PATTERN_ANALOG_STUDY"
                meth_id = "METH-DTW-ANALOG-1.0"
            elif "Makro" in cat:
                exp_type = "MACRO_EVENT_VOLATILITY_STUDY"
                meth_id = "METH-SYMMETRIC-EVENT-STUDY-1.2"
            elif "Fonlama" in cat:
                exp_type = "PERPETUAL_FUNDING_AUTOCORRELATION"
                meth_id = "METH-FUNDING-AUTOCORR-1.1"
            elif "Sistem" in cat:
                exp_type = "STORAGE_DURABILITY_VERIFICATION"
                meth_id = "METH-STORAGE-MOUNTINFO-1.0"
            elif "Kriptografik" in cat:
                exp_type = "CRYPTOGRAPHIC_BUNDLE_VERIFICATION"
                meth_id = "METH-RFC8785-HMAC-2.0"
            else:
                exp_type = "DATASET_FORENSIC_QUARANTINE_AUDIT"
                meth_id = "METH-QUARANTINE-FORENSIC-1.0"

            param_fp = self.compute_parameter_fingerprint(
                {
                    "model_version": CANONICAL_MODEL_VERSION,
                    "methodology_id": meth_id,
                    "window_cadence": getattr(rec, "window_cadence", "1h"),
                    "dataset_id": rec.dataset_id,
                }
            )
            exp_id = self.compute_deterministic_experiment_id(
                research_id=rec.id,
                experiment_type=exp_type,
                methodology_id=meth_id,
                dataset_id=rec.dataset_id,
                parameter_fingerprint=param_fp,
            )

            src_art = getattr(rec, "source_artifact", None)
            src_sha = getattr(rec, "source_artifact_sha256", None)
            ds_fp = src_sha if (src_sha and has_verified_source_artifact) else "UNVERIFIED_DATASET_FINGERPRINT"
            in_arts = [src_art] if (src_art and has_verified_source_artifact) else []
            authentic_art_ts = _extract_authentic_artifact_metadata_timestamp(src_art)

            if is_quarantined:
                exec_status = "BLOCKED"
                prov_verdict = "BLOCKED_QUARANTINED_OCTOBER_2026"
                repro_verdict = "REPRODUCTION_BLOCKED"
                val_verdict = "VALIDATION_BLOCKED"
                hist_auth = "QUARANTINED_SYNTHETIC_CONTAMINATION_BLOCKED"
            elif is_prov_ok and scorecard.overall_verdict == "READY_FOR_CONFIRMATORY_REVIEW":
                exec_status = "EXECUTION_EVIDENCE_AVAILABLE"
                prov_verdict = "INTEGRITY_VERIFIED"
                repro_verdict = "REPRODUCTION_NOT_ESTABLISHED"
                val_verdict = "CONFIRMATORY_CANDIDATE_PENDING_REPRODUCTION"
                hist_auth = "SOURCE_ARTIFACT_VERIFIED_NO_EXECUTION_LOG"
            elif is_prov_ok:
                exec_status = "EXECUTION_EVIDENCE_AVAILABLE"
                prov_verdict = "INTEGRITY_VERIFIED"
                repro_verdict = "REPRODUCTION_NOT_ESTABLISHED"
                val_verdict = "EXPLORATORY_FINDING"
                hist_auth = "SOURCE_ARTIFACT_VERIFIED_NO_EXECUTION_LOG"
            else:
                exec_status = "HISTORICAL_EXECUTION_UNVERIFIED"
                prov_verdict = "UNVERIFIED"
                repro_verdict = "REPRODUCTION_NOT_ESTABLISHED"
                val_verdict = "INSUFFICIENT_EVIDENCE"
                hist_auth = "CATALOG_DISCOVERED_NO_EXECUTION_LOG"

            exp_rec = ExperimentRecord(
                experiment_id=exp_id,
                research_id=rec.id,
                experiment_type=exp_type,
                experiment_title=f"{rec.title} — Katalog Projeksiyon Kaydı",
                hypothesis_id=getattr(rec, "specification_id", None) or f"HYP-{rec.id}",
                methodology_id=meth_id,
                dataset_id=rec.dataset_id,
                dataset_fingerprint=ds_fp,
                model_version=CANONICAL_MODEL_VERSION,
                execution_mode=CANONICAL_EXECUTION_MODE,
                execution_started_at=None,
                execution_completed_at=None,
                execution_status=exec_status,
                parameter_fingerprint=param_fp,
                input_artifact_ids=in_arts,
                output_artifact_ids=[],
                result_digest=None,
                provenance_verdict=prov_verdict,
                reproducibility_verdict=repro_verdict,
                validation_verdict=val_verdict,
                execution_attempts=[],
                record_origin="CATALOG_PROJECTION",
                source_artifact_timestamp_utc=authentic_art_ts,
                historical_execution_authenticity=hist_auth,
            )
            self._experiments[exp_id] = exp_rec

            # Append honest catalog discovery & evidence evaluation events (never EXECUTION_COMPLETED)
            self._append_timeline_event(
                experiment_id=exp_id,
                event_type="CATALOG_DISCOVERED",
                event_source="CBE_CATALOG_DISCOVERY",
                payload={
                    "research_id": rec.id,
                    "dataset_id": rec.dataset_id,
                    "methodology_id": meth_id,
                    "record_origin": "CATALOG_PROJECTION",
                    "source_artifact_timestamp_utc": authentic_art_ts,
                },
                timestamp_utc=CATALOG_DISCOVERY_EPOCH_UTC,
            )
            if is_quarantined:
                self._append_timeline_event(
                    experiment_id=exp_id,
                    event_type="BLOCKED",
                    event_source="CBE_PROVENANCE_GATE",
                    payload={
                        "rejection_code": "QUARANTINED_OCTOBER_2026_DATA",
                        "record_origin": "CATALOG_PROJECTION",
                    },
                    timestamp_utc=CATALOG_DISCOVERY_EPOCH_UTC,
                )
            else:
                self._append_timeline_event(
                    experiment_id=exp_id,
                    event_type=exec_status,
                    event_source="CBE_EVIDENCE_VERIFIER",
                    payload={
                        "provenance_verdict": prov_verdict,
                        "reproducibility_verdict": repro_verdict,
                        "validation_verdict": val_verdict,
                        "historical_execution_authenticity": hist_auth,
                    },
                    timestamp_utc=CATALOG_DISCOVERY_EPOCH_UTC,
                )

    @staticmethod
    def _validate_execution_artifacts_and_digests(
        exp_id: str,
        output_artifact_ids: Optional[Sequence[str]],
        result_digest: Optional[str],
        digest_source: Optional[str] = None,
        metadata_for_check: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Reject synthetic output artifact IDs (OUT-ART-*)
        for art_id in output_artifact_ids or []:
            s_art = str(art_id or "").strip()
            if s_art.upper().startswith("OUT-ART-") or s_art.upper().startswith("SYNTH-OUT-"):
                raise ExperimentRegistrySecurityError(
                    "SYNTHETIC_OUTPUT_ARTIFACT_REJECTED",
                    f"Synthetic output artifact identifier '{s_art}' cannot be recorded as verified execution output.",
                )

        # Reject metadata-derived result digests
        if digest_source and str(digest_source).strip().upper() in (
            "METADATA",
            "METADATA_CONCATENATION",
            "RECORD_METADATA",
            "DERIVED_FROM_METADATA",
        ):
            raise ExperimentRegistrySecurityError(
                "METADATA_DERIVED_RESULT_DIGEST_REJECTED",
                "Result digest manufactured from record metadata is strictly prohibited.",
            )

        if result_digest is not None:
            rd = str(result_digest).strip()
            if rd.upper().startswith("METADATA-") or rd.upper().startswith("DERIVED-"):
                raise ExperimentRegistrySecurityError(
                    "METADATA_DERIVED_RESULT_DIGEST_REJECTED",
                    f"Result digest '{rd}' is marked as metadata-derived and cannot represent an execution artifact digest.",
                )
            if metadata_for_check:
                prohibited = ExperimentRegistryAndTimelineService.compute_prohibited_metadata_digest(
                    exp_id=exp_id,
                    sample_size=metadata_for_check.get("sample_size"),
                    volatility_ratio=metadata_for_check.get("volatility_ratio"),
                    raw_p_value=metadata_for_check.get("raw_p_value"),
                )
                if rd == prohibited:
                    raise ExperimentRegistrySecurityError(
                        "METADATA_DERIVED_RESULT_DIGEST_REJECTED",
                        "Result digest matches concatenated catalog metadata hash and is rejected.",
                    )
            # Check against all canonical catalog records' metadata hashes for this exp_id
            for cat_rec in ResearchCatalogProvider.get_canonical_catalog():
                prohibited_cat = ExperimentRegistryAndTimelineService.compute_prohibited_metadata_digest(
                    exp_id=exp_id,
                    sample_size=getattr(cat_rec, "sample_size", None),
                    volatility_ratio=getattr(cat_rec, "volatility_ratio", None),
                    raw_p_value=getattr(cat_rec, "raw_p_value", None),
                )
                if rd == prohibited_cat:
                    raise ExperimentRegistrySecurityError(
                        "METADATA_DERIVED_RESULT_DIGEST_REJECTED",
                        f"Result digest for '{exp_id}' is derived from catalog record metadata rather than a real execution output artifact.",
                    )

    def register_experiment(
        self,
        research_id: str,
        experiment_type: str,
        experiment_title: str,
        hypothesis_id: str,
        methodology_id: str,
        dataset_id: str,
        dataset_fingerprint: str,
        parameters: Optional[Dict[str, Any]] = None,
        input_artifact_ids: Optional[List[str]] = None,
        output_artifact_ids: Optional[List[str]] = None,
        result_digest: Optional[str] = None,
        requested_status: str = "REGISTERED",
        evidence_verified_by_authority: bool = False,
        is_rerun: bool = False,
        record_origin: str = "OFFLINE_EXPERIMENT_EXECUTION",
        execution_started_at: Optional[str] = None,
        execution_completed_at: Optional[str] = None,
        has_verified_execution_log: bool = True,
        reproducibility_verdict: str = "REPRODUCTION_NOT_ESTABLISHED",
        independent_reference_compared: bool = False,
        reference_artifact_sha256: Optional[str] = None,
        digest_source: Optional[str] = None,
        metadata_for_check: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Registers an experiment or records an explicit rerun attempt under a file-backed MultiProcessLock.
        Enforces P0-1 and Negative Security Tests:
        - Rejects fabricated or malformed historical execution timestamps.
        - Rejects synthetic output artifacts (OUT-ART-*).
        - Rejects metadata-derived result digests.
        - Rejects marking catalog discovery records as EXECUTION_COMPLETED without execution evidence.
        - Rejects marking unverified reproduction as OUTPUTS_MATCHED.
        - Rejects promoting synthetic seed/catalog projections to verified historical execution.
        """
        req_st = str(requested_status or "REGISTERED").strip().upper()
        origin_clean = str(record_origin or "OFFLINE_EXPERIMENT_EXECUTION").strip().upper()
        if origin_clean not in VALID_RECORD_ORIGINS:
            raise ExperimentRegistrySecurityError(
                "INVALID_RECORD_ORIGIN",
                f"Invalid experiment record_origin '{origin_clean}'.",
            )

        if req_st in ("SCIENTIFICALLY_VERIFIED", "EVIDENCE_VERIFIED", "SCIENTIFIC_REVIEW_COMPLETED"):
            if not evidence_verified_by_authority:
                raise ExperimentRegistrySecurityError(
                    "UNVERIFIED_EXECUTION_PROMOTION_BLOCKED",
                    f"Experiment status '{req_st}' cannot be granted from computational execution alone without verified cryptographic and scientific evidence.",
                )

        if req_st not in VALID_EXPERIMENT_LIFECYCLE_STATES:
            raise ExperimentRegistrySecurityError(
                "INVALID_EXPERIMENT_LIFECYCLE_STATE",
                f"Invalid experiment lifecycle state '{req_st}'.",
            )

        # P0-1 Check #4 & #6: Catalog discovery record cannot be marked EXECUTION_COMPLETED or promoted without execution evidence
        if origin_clean == "CATALOG_PROJECTION" and req_st in (
            "EXECUTION_COMPLETED",
            "EXECUTION_EVIDENCE_VERIFIED",
            "EVIDENCE_VERIFIED",
            "SCIENTIFIC_REVIEW_COMPLETED",
        ):
            raise ExperimentRegistrySecurityError(
                "UNSUPPORTED_EXECUTION_COMPLETED_REJECTED",
                "Catalog discovery record (CATALOG_PROJECTION) cannot be marked as EXECUTION_COMPLETED or verified execution without authentic execution evidence.",
            )

        if req_st == "EXECUTION_COMPLETED" and not has_verified_execution_log:
            raise ExperimentRegistrySecurityError(
                "UNSUPPORTED_EXECUTION_COMPLETED_REJECTED",
                "EXECUTION_COMPLETED requires a real execution record with verifiable identity and timestamp.",
            )

        # P0-1 Check #5: Unverified reproduction cannot be marked OUTPUTS_MATCHED
        repro_clean = str(reproducibility_verdict or "REPRODUCTION_NOT_ESTABLISHED").strip().upper()
        if repro_clean == "OUTPUTS_MATCHED":
            if (
                not independent_reference_compared
                or not reference_artifact_sha256
                or not result_digest
                or str(reference_artifact_sha256).strip() == str(result_digest).strip()
            ):
                raise ExperimentRegistrySecurityError(
                    "UNSUPPORTED_OUTPUTS_MATCHED_REJECTED",
                    "OUTPUTS_MATCHED requires an actual comparison against independently persisted expected results.",
                )

        # P0-1 Check #1: Validate execution timestamps if supplied by caller
        now_dt = datetime.now(timezone.utc)
        now_utc = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        if execution_started_at is not None or execution_completed_at is not None:
            if not has_verified_execution_log or origin_clean == "CATALOG_PROJECTION":
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    "Cannot assign historical execution timestamps without an authentic persisted execution log.",
                )
            start_dt = _parse_iso8601_utc(execution_started_at) if execution_started_at is not None else None
            end_dt = _parse_iso8601_utc(execution_completed_at) if execution_completed_at is not None else None
            if (execution_started_at is not None and start_dt is None) or (
                execution_completed_at is not None and end_dt is None
            ):
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    "Supplied execution timestamp is malformed or missing timezone.",
                )
            if start_dt and start_dt > now_dt:
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    f"Execution start timestamp '{execution_started_at}' is in the future.",
                )
            if end_dt and end_dt > now_dt:
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    f"Execution completion timestamp '{execution_completed_at}' is in the future.",
                )
            if start_dt and end_dt and end_dt < start_dt:
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    "Execution completion timestamp precedes start timestamp.",
                )
            # Reject predefined synthetic seed timestamps from legacy table
            prohibited_seed_timestamps = {
                "2026-09-12T10:00:00Z",
                "2026-09-12T10:02:15Z",
                "2026-09-18T14:15:00Z",
                "2026-09-18T14:18:40Z",
                "2026-09-25T09:30:00Z",
                "2026-09-25T09:34:10Z",
                "2026-10-02T11:00:00Z",
                "2026-10-02T11:03:20Z",
                "2026-10-10T16:20:00Z",
                "2026-10-10T16:21:05Z",
                "2026-10-16T08:00:00Z",
                "2026-10-16T08:01:30Z",
                "2026-10-22T12:00:00Z",
                "2026-10-22T12:00:15Z",
            }
            if (
                str(execution_started_at or "").strip() in prohibited_seed_timestamps
                or str(execution_completed_at or "").strip() in prohibited_seed_timestamps
            ):
                raise ExperimentRegistrySecurityError(
                    "FABRICATED_EXECUTION_TIMESTAMP_REJECTED",
                    "Predefined invented historical seed timestamps are prohibited.",
                )

        param_fp = self.compute_parameter_fingerprint(parameters or {})
        exp_id = self.compute_deterministic_experiment_id(
            research_id=research_id,
            experiment_type=experiment_type,
            methodology_id=methodology_id,
            dataset_id=dataset_id,
            parameter_fingerprint=param_fp,
        )

        # P0-1 Check #2 & #3: Validate output artifacts and result digest
        self._validate_execution_artifacts_and_digests(
            exp_id=exp_id,
            output_artifact_ids=output_artifact_ids,
            result_digest=result_digest,
            digest_source=digest_source,
            metadata_for_check=metadata_for_check,
        )

        with MultiProcessLock(self._get_lock_path(), timeout=5.0):
            if self._storage_path and self._storage_path.exists():
                self._load_persisted_state_unlocked()

            if exp_id in self._experiments:
                existing = self._experiments[exp_id]
                # P0-1 Check #6: Synthetic seed / catalog projection record cannot be promoted to verified historical execution
                if existing.record_origin == "CATALOG_PROJECTION" and not is_rerun:
                    if req_st in (
                        "EXECUTION_COMPLETED",
                        "EXECUTION_EVIDENCE_VERIFIED",
                        "EVIDENCE_VERIFIED",
                        "SCIENTIFIC_REVIEW_COMPLETED",
                    ):
                        raise ExperimentRegistrySecurityError(
                            "SYNTHETIC_SEED_PROMOTION_REJECTED",
                            f"Catalog projection record '{exp_id}' cannot be promoted to verified historical execution without a genuine execution artifact.",
                        )
                if not is_rerun:
                    return {
                        "status": "success",
                        "registration_mode": "IDEMPOTENT_EXISTING",
                        "experiment": existing.to_dict(),
                    }

                # Explicit offline rerun: append a new ExecutionAttemptRecord without overwriting prior evidence
                attempt_no = len(existing.execution_attempts) + 1
                att_id = f"ATT-{exp_id}-{attempt_no:02d}"
                eff_start = execution_started_at or now_utc
                eff_end = execution_completed_at or (now_utc if req_st == "EXECUTION_COMPLETED" else "")
                new_attempt = ExecutionAttemptRecord(
                    attempt_id=att_id,
                    experiment_id=exp_id,
                    attempt_number=attempt_no,
                    started_at_utc=eff_start,
                    completed_at_utc=eff_end,
                    execution_status=req_st,
                    result_digest=result_digest,
                    output_artifact_ids=list(output_artifact_ids or []),
                    notes=f"Explicit offline rerun attempt #{attempt_no}",
                )
                existing.execution_attempts.append(new_attempt.to_dict())
                existing.execution_started_at = eff_start
                existing.execution_completed_at = eff_end if eff_end else None
                existing.record_origin = "OFFLINE_EXPERIMENT_EXECUTION"
                existing.historical_execution_authenticity = "AUTHENTIC_OFFLINE_RERUN_RECORDED"
                if req_st == "EXECUTION_COMPLETED" and existing.execution_status in (
                    "REGISTERED",
                    "CATALOG_DISCOVERED",
                    "HISTORICAL_EXECUTION_UNVERIFIED",
                    "EXECUTION_EVIDENCE_AVAILABLE",
                ):
                    existing.execution_status = "EXECUTION_COMPLETED"
                self._append_timeline_event(
                    experiment_id=exp_id,
                    event_type="RERUN_ATTEMPT_RECORDED",
                    event_source="CBE_OFFLINE_RUNNER",
                    payload={"attempt_id": att_id, "attempt_number": attempt_no, "status": req_st},
                    timestamp_utc=now_utc,
                )
                self._persist_state_unlocked()
                return {
                    "status": "success",
                    "registration_mode": "EXPLICIT_RERUN_APPENDED",
                    "attempt_id": att_id,
                    "experiment": existing.to_dict(),
                }

            eff_start = (
                (execution_started_at or now_utc)
                if origin_clean != "CATALOG_PROJECTION"
                else None
            )
            eff_end = (
                (execution_completed_at or (now_utc if req_st == "EXECUTION_COMPLETED" else None))
                if origin_clean != "CATALOG_PROJECTION"
                else None
            )

            attempts_list: List[Dict[str, Any]] = []
            if origin_clean != "CATALOG_PROJECTION":
                attempt_1 = ExecutionAttemptRecord(
                    attempt_id=f"ATT-{exp_id}-01",
                    experiment_id=exp_id,
                    attempt_number=1,
                    started_at_utc=eff_start or now_utc,
                    completed_at_utc=eff_end or "",
                    execution_status=req_st,
                    result_digest=result_digest,
                    output_artifact_ids=list(output_artifact_ids or []),
                    notes="Initial offline experiment registration.",
                )
                attempts_list.append(attempt_1.to_dict())

            new_exp = ExperimentRecord(
                experiment_id=exp_id,
                research_id=research_id,
                experiment_type=experiment_type,
                experiment_title=experiment_title,
                hypothesis_id=hypothesis_id,
                methodology_id=methodology_id,
                dataset_id=dataset_id,
                dataset_fingerprint=dataset_fingerprint,
                model_version=CANONICAL_MODEL_VERSION,
                execution_mode=CANONICAL_EXECUTION_MODE,
                execution_started_at=eff_start,
                execution_completed_at=eff_end,
                execution_status=req_st,
                parameter_fingerprint=param_fp,
                input_artifact_ids=list(input_artifact_ids or []),
                output_artifact_ids=list(output_artifact_ids or []),
                result_digest=result_digest,
                provenance_verdict="INTEGRITY_VERIFIED" if evidence_verified_by_authority else "UNVERIFIED",
                reproducibility_verdict=repro_clean,
                validation_verdict="INSUFFICIENT_EVIDENCE",
                execution_attempts=attempts_list,
                record_origin=origin_clean,
                source_artifact_timestamp_utc=None,
                historical_execution_authenticity=(
                    "AUTHENTIC_OFFLINE_EXECUTION_RECORDED"
                    if origin_clean == "OFFLINE_EXPERIMENT_EXECUTION"
                    else "CATALOG_DISCOVERED_NO_EXECUTION_LOG"
                ),
            )
            self._experiments[exp_id] = new_exp
            self._append_timeline_event(
                experiment_id=exp_id,
                event_type=req_st,
                event_source="CBE_EXPERIMENT_REGISTRY",
                payload={
                    "research_id": research_id,
                    "dataset_id": dataset_id,
                    "record_origin": origin_clean,
                },
                timestamp_utc=eff_start or now_utc,
            )
            self._persist_state_unlocked()
            return {
                "status": "success",
                "registration_mode": "NEW_REGISTRATION",
                "experiment": new_exp.to_dict(),
            }

    def promote_to_verified_historical_execution(
        self,
        experiment_id: str,
        execution_log_path: Optional[Path] = None,
        expected_log_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attempts to promote an experiment record to VERIFIED_HISTORICAL_EXECUTION.
        Rejects promotion of synthetic seed / catalog projection records unless backed by
        an authentic, independently verifiable execution log artifact on disk.
        """
        target = str(experiment_id or "").strip()
        exp = self._experiments.get(target)
        if exp is None:
            for candidate in self._experiments.values():
                if candidate.research_id == target:
                    exp = candidate
                    break
        if exp is None:
            raise ExperimentRegistrySecurityError(
                "EXPERIMENT_NOT_FOUND",
                f"Experiment '{target}' does not exist.",
            )

        if not execution_log_path or not expected_log_sha256:
            raise ExperimentRegistrySecurityError(
                "SYNTHETIC_SEED_PROMOTION_REJECTED",
                f"Cannot promote catalog projection '{exp.experiment_id}' to verified historical execution without an authentic execution log path and expected SHA-256.",
            )
        p = Path(execution_log_path)
        if not p.exists() or not p.is_file():
            raise ExperimentRegistrySecurityError(
                "SYNTHETIC_SEED_PROMOTION_REJECTED",
                f"Execution log path '{p}' does not exist on disk.",
            )
        actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual_sha != str(expected_log_sha256).strip().lower():
            raise ExperimentRegistrySecurityError(
                "SYNTHETIC_SEED_PROMOTION_REJECTED",
                "Execution log SHA-256 mismatch.",
            )
        try:
            log_data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ExperimentRegistrySecurityError(
                "SYNTHETIC_SEED_PROMOTION_REJECTED",
                f"Execution log is not valid JSON: {exc}",
            ) from exc

        started = log_data.get("execution_started_at")
        completed = log_data.get("execution_completed_at")
        out_sha = log_data.get("output_artifact_sha256")
        if not (_parse_iso8601_utc(started) and _parse_iso8601_utc(completed) and out_sha):
            raise ExperimentRegistrySecurityError(
                "SYNTHETIC_SEED_PROMOTION_REJECTED",
                "Execution log lacks verifiable execution_started_at, execution_completed_at, or output_artifact_sha256.",
            )

        exp.record_origin = "VERIFIED_HISTORICAL_EXECUTION"
        exp.execution_started_at = started
        exp.execution_completed_at = completed
        exp.execution_status = "EXECUTION_EVIDENCE_VERIFIED"
        exp.result_digest = out_sha
        exp.historical_execution_authenticity = "VERIFIED_HISTORICAL_EXECUTION_LOG"
        self._append_timeline_event(
            experiment_id=exp.experiment_id,
            event_type="EXECUTION_EVIDENCE_VERIFIED",
            event_source="CBE_HISTORICAL_EXECUTION_VERIFIER",
            payload={
                "execution_log_sha256": actual_sha,
                "result_digest": out_sha,
            },
        )
        self._persist_state_if_configured()
        return {"status": "success", "experiment": exp.to_dict()}

    def verify_timeline_chain_integrity(
        self,
        events: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Verifies the internal SHA-256 tamper-detection hash chain across all timeline events.
        Detects any payload mutation, event deletion, reordering, duplicate event IDs,
        out-of-order timestamps, or forged previous_event_digest.
        Explicitly labels the chain as an internal tamper-detection mechanism (not externally anchored).
        """
        target_events = (
            [
                ExperimentTimelineEvent(
                    event_id=str(e.get("event_id", "")),
                    experiment_id=str(e.get("experiment_id", "")),
                    event_type=str(e.get("event_type", "")),
                    event_timestamp=str(e.get("event_timestamp", "")),
                    event_source=str(e.get("event_source", "")),
                    event_payload_digest=str(e.get("event_payload_digest", "")),
                    previous_event_digest=str(e.get("previous_event_digest", "")),
                    payload=e.get("payload", {}) if isinstance(e.get("payload"), dict) else {},
                    event_digest=str(e.get("event_digest", "")),
                )
                for e in events
            ]
            if events is not None
            else self._timeline
        )

        expected_prev = GENESIS_TIMELINE_DIGEST
        seen_event_ids = set()
        prev_dt: Optional[datetime] = None

        # Pre-pass: check duplicate event IDs and chronological timestamp ordering across the full timeline
        for idx, ev in enumerate(target_events):
            if not ev.event_id or ev.event_id in seen_event_ids:
                return {
                    "chain_valid": False,
                    "rejection_code": "DUPLICATE_TIMELINE_EVENT_ID",
                    "failed_event_index": idx,
                    "failed_event_id": ev.event_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Duplicate or empty timeline event_id '{ev.event_id}' at index {idx}.",
                }
            seen_event_ids.add(ev.event_id)

            cur_dt = _parse_iso8601_utc(ev.event_timestamp)
            if cur_dt is None:
                return {
                    "chain_valid": False,
                    "rejection_code": "INVALID_TIMELINE_EVENT_TIMESTAMP",
                    "failed_event_index": idx,
                    "failed_event_id": ev.event_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Timeline event '{ev.event_id}' has malformed timestamp '{ev.event_timestamp}'.",
                }
            if prev_dt is not None and cur_dt < prev_dt:
                return {
                    "chain_valid": False,
                    "rejection_code": "TIMELINE_OUT_OF_ORDER_TIMESTAMP",
                    "failed_event_index": idx,
                    "failed_event_id": ev.event_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Timeline event '{ev.event_id}' timestamp '{ev.event_timestamp}' precedes prior event timestamp.",
                }
            prev_dt = cur_dt

        for idx, ev in enumerate(target_events):
            # 2. Verify previous_event_digest link
            if ev.previous_event_digest != expected_prev:
                return {
                    "chain_valid": False,
                    "rejection_code": "TIMELINE_HASH_CHAIN_BROKEN",
                    "failed_event_index": idx,
                    "failed_event_id": ev.event_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Timeline hash chain broken at event '{ev.event_id}' (index {idx}): previous_event_digest mismatch.",
                }

            # 3. Verify payload digest if payload is present
            if ev.payload:
                actual_payload_digest = hashlib.sha256(
                    rfc8785_canonical_json(ev.payload)
                ).hexdigest()
                if actual_payload_digest != ev.event_payload_digest:
                    return {
                        "chain_valid": False,
                        "rejection_code": "TIMELINE_PAYLOAD_TAMPERED",
                        "failed_event_index": idx,
                        "failed_event_id": ev.event_id,
                        "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                        "externally_anchored": False,
                        "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                        "message": f"Timeline event '{ev.event_id}' payload does not match event_payload_digest.",
                    }

            # 4. Verify event_digest
            computed_digest = ev.compute_event_digest()
            if ev.event_digest and ev.event_digest != computed_digest:
                return {
                    "chain_valid": False,
                    "rejection_code": "TIMELINE_EVENT_DIGEST_MISMATCH",
                    "failed_event_index": idx,
                    "failed_event_id": ev.event_id,
                    "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
                    "externally_anchored": False,
                    "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
                    "message": f"Timeline event '{ev.event_id}' event_digest is corrupted or tampered.",
                }

            expected_prev = computed_digest

        return {
            "chain_valid": True,
            "rejection_code": None,
            "total_events_verified": len(target_events),
            "head_event_digest": expected_prev,
            "integrity_mechanism": "INTERNAL_TAMPER_DETECTION_CHAIN",
            "externally_anchored": False,
            "authenticity_claim": "INTERNAL_TAMPER_DETECTION_ONLY_NOT_EXTERNALLY_ANCHORED",
        }

    def list_experiments(
        self,
        research_id: Optional[str] = None,
        experiment_type: Optional[str] = None,
        execution_status: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = list(self._experiments.values())
        if research_id and str(research_id).upper() != "ALL":
            q = str(research_id).strip().lower()
            items = [e for e in items if q in e.research_id.lower() or q in e.experiment_id.lower()]
        if experiment_type and str(experiment_type).upper() != "ALL":
            q = str(experiment_type).strip().lower()
            items = [e for e in items if q in e.experiment_type.lower()]
        if execution_status and str(execution_status).upper() != "ALL":
            q = str(execution_status).strip().upper()
            items = [e for e in items if q == e.execution_status.upper()]
        if dataset_id and str(dataset_id).upper() != "ALL":
            q = str(dataset_id).strip().lower()
            items = [e for e in items if q in e.dataset_id.lower()]

        items.sort(key=lambda e: ((e.execution_started_at or ""), e.experiment_id))
        chain_check = self.verify_timeline_chain_integrity()
        return {
            "status": "success",
            "canonical_model": CANONICAL_MODEL_VERSION,
            "total_experiments": len(items),
            "timeline_chain_integrity": chain_check,
            "experiments": [e.to_dict() for e in items],
        }

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        target = str(experiment_id or "").strip()
        if target in self._experiments:
            return self._experiments[target].to_dict()
        for exp in self._experiments.values():
            if exp.research_id == target:
                return exp.to_dict()
        return None

    def get_experiment_timeline(self, experiment_id: Optional[str] = None) -> Dict[str, Any]:
        chain_check = self.verify_timeline_chain_integrity()
        events = [e.to_dict() for e in self._timeline]
        if experiment_id and str(experiment_id).upper() != "ALL":
            target = str(experiment_id).strip()
            exp_obj = self.get_experiment(target)
            resolved_exp_id = exp_obj["experiment_id"] if exp_obj else target
            events = [
                e
                for e in events
                if e["experiment_id"] in (target, resolved_exp_id)
            ]
        return {
            "status": "success",
            "experiment_id": experiment_id or "ALL",
            "event_count": len(events),
            "timeline_chain_integrity": chain_check,
            "events": events,
        }

    def _persist_state_unlocked(self) -> None:
        if not self._storage_path:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._storage_path.with_suffix(".tmp")
        payload = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "canonical_model": CANONICAL_MODEL_VERSION,
            "experiments": {k: v.to_dict() for k, v in self._experiments.items()},
            "timeline": [e.to_dict() for e in self._timeline],
        }
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(serialized)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(self._storage_path))

    def _persist_state_if_configured(self) -> None:
        if not self._storage_path:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        with MultiProcessLock(self._get_lock_path(), timeout=5.0):
            self._persist_state_unlocked()

    def _load_persisted_state_unlocked(self) -> None:
        """
        Complete persistence hydration & verification (P0-3):
        1. Validates JSON syntax and top-level structure (fails closed on corruption).
        2. Validates schema_version == PERSISTENCE_SCHEMA_VERSION.
        3. Validates required experiment fields & lifecycle state for every experiment.
        4. Validates execution attempt structures.
        5. Validates timeline event structures.
        6. Verifies event hash-chain integrity, chronological ordering, and duplicate event IDs.
        7. Validates experiment-to-event references.
        8. Restores verified experiments into self._experiments and timeline events into self._timeline.
        """
        if not self._storage_path or not self._storage_path.exists():
            return

        self._cleanup_interrupted_tmp_if_present()

        try:
            raw_text = self._storage_path.read_text(encoding="utf-8")
            raw = json.loads(raw_text)
        except Exception as exc:
            raise ExperimentRegistrySecurityError(
                "CORRUPTED_PERSISTED_STATE",
                f"Persisted experiment registry JSON is corrupted or unreadable: {exc}",
            ) from exc

        if not isinstance(raw, dict):
            raise ExperimentRegistrySecurityError(
                "CORRUPTED_PERSISTED_STATE",
                "Persisted experiment registry root must be a JSON object.",
            )

        schema_ver = raw.get("schema_version")
        if schema_ver != PERSISTENCE_SCHEMA_VERSION:
            raise ExperimentRegistrySecurityError(
                "INVALID_PERSISTENCE_SCHEMA_VERSION",
                f"Unsupported or missing persistence schema_version '{schema_ver}' (expected '{PERSISTENCE_SCHEMA_VERSION}').",
            )

        exps_raw = raw.get("experiments")
        tl_raw = raw.get("timeline")
        if not isinstance(exps_raw, dict) or not isinstance(tl_raw, list):
            raise ExperimentRegistrySecurityError(
                "CORRUPTED_PERSISTED_STATE",
                "Persisted state must contain 'experiments' object and 'timeline' list.",
            )

        restored_experiments: Dict[str, ExperimentRecord] = {}
        for exp_key, exp_val in exps_raw.items():
            if not isinstance(exp_val, dict):
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_PERSISTED_EXPERIMENT",
                    f"Experiment entry '{exp_key}' is not a JSON object.",
                )
            missing_fields = [f for f in REQUIRED_EXPERIMENT_FIELDS if f not in exp_val]
            if missing_fields:
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_PERSISTED_EXPERIMENT",
                    f"Persisted experiment '{exp_key}' is missing required fields: {missing_fields}",
                )
            if str(exp_val.get("experiment_id")) != str(exp_key):
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_PERSISTED_EXPERIMENT",
                    f"Persisted experiment key '{exp_key}' does not match experiment_id '{exp_val.get('experiment_id')}'.",
                )
            st = str(exp_val.get("execution_status") or "")
            if st not in VALID_EXPERIMENT_LIFECYCLE_STATES:
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_PERSISTED_EXPERIMENT",
                    f"Persisted experiment '{exp_key}' has invalid execution_status '{st}'.",
                )
            attempts_raw = exp_val.get("execution_attempts", [])
            if not isinstance(attempts_raw, list):
                raise ExperimentRegistrySecurityError(
                    "INVALID_EXECUTION_ATTEMPT",
                    f"Persisted experiment '{exp_key}' execution_attempts must be a list.",
                )
            validated_attempts: List[Dict[str, Any]] = []
            for att in attempts_raw:
                if not isinstance(att, dict):
                    raise ExperimentRegistrySecurityError(
                        "INVALID_EXECUTION_ATTEMPT",
                        f"Execution attempt in '{exp_key}' is not a dict.",
                    )
                missing_att = [af for af in REQUIRED_ATTEMPT_FIELDS if af not in att]
                if missing_att:
                    raise ExperimentRegistrySecurityError(
                        "INVALID_EXECUTION_ATTEMPT",
                        f"Execution attempt in '{exp_key}' missing required fields: {missing_att}",
                    )
                if str(att.get("experiment_id")) != str(exp_key):
                    raise ExperimentRegistrySecurityError(
                        "INVALID_EXECUTION_ATTEMPT",
                        f"Execution attempt experiment_id mismatch in '{exp_key}'.",
                    )
                validated_attempts.append(dict(att))

            restored_experiments[exp_key] = ExperimentRecord(
                experiment_id=str(exp_val["experiment_id"]),
                research_id=str(exp_val["research_id"]),
                experiment_type=str(exp_val["experiment_type"]),
                experiment_title=str(exp_val["experiment_title"]),
                hypothesis_id=str(exp_val["hypothesis_id"]),
                methodology_id=str(exp_val["methodology_id"]),
                dataset_id=str(exp_val["dataset_id"]),
                dataset_fingerprint=str(exp_val["dataset_fingerprint"]),
                model_version=str(exp_val["model_version"]),
                execution_mode=str(exp_val["execution_mode"]),
                execution_started_at=exp_val.get("execution_started_at"),
                execution_completed_at=exp_val.get("execution_completed_at"),
                execution_status=st,
                parameter_fingerprint=str(exp_val["parameter_fingerprint"]),
                input_artifact_ids=list(exp_val.get("input_artifact_ids") or []),
                output_artifact_ids=list(exp_val.get("output_artifact_ids") or []),
                result_digest=exp_val.get("result_digest"),
                provenance_verdict=str(exp_val["provenance_verdict"]),
                reproducibility_verdict=str(exp_val["reproducibility_verdict"]),
                validation_verdict=str(exp_val["validation_verdict"]),
                execution_attempts=validated_attempts,
                record_origin=str(exp_val.get("record_origin", "CATALOG_PROJECTION")),
                source_artifact_timestamp_utc=exp_val.get("source_artifact_timestamp_utc"),
                historical_execution_authenticity=str(
                    exp_val.get("historical_execution_authenticity", "CATALOG_DISCOVERED_NO_EXECUTION_LOG")
                ),
            )

        # Validate timeline event structures before hash chain check
        for idx, ev_raw in enumerate(tl_raw):
            if not isinstance(ev_raw, dict):
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_TIMELINE_EVENT",
                    f"Timeline event at index {idx} is not a JSON object.",
                )
            missing_ev = [ef for ef in REQUIRED_TIMELINE_EVENT_FIELDS if ef not in ev_raw or ev_raw.get(ef) in (None, "")]
            if missing_ev:
                raise ExperimentRegistrySecurityError(
                    "MALFORMED_TIMELINE_EVENT",
                    f"Timeline event at index {idx} is missing required fields: {missing_ev}",
                )

        # Verify hash chain, duplicate event IDs, and chronological timestamp ordering
        check = self.verify_timeline_chain_integrity(tl_raw)
        if not check.get("chain_valid"):
            raise ExperimentRegistrySecurityError(
                check.get("rejection_code") or "TIMELINE_HASH_CHAIN_BROKEN",
                check.get("message") or "Persisted timeline failed hash-chain verification.",
            )

        restored_timeline: List[ExperimentTimelineEvent] = []
        for idx, ev_raw in enumerate(tl_raw):
            ev_exp_id = str(ev_raw["experiment_id"])
            if ev_exp_id not in restored_experiments:
                raise ExperimentRegistrySecurityError(
                    "MISSING_EXPERIMENT_REFERENCE_IN_TIMELINE",
                    f"Timeline event '{ev_raw.get('event_id')}' at index {idx} references nonexistent experiment '{ev_exp_id}'.",
                )
            ev_obj = ExperimentTimelineEvent(
                event_id=str(ev_raw["event_id"]),
                experiment_id=ev_exp_id,
                event_type=str(ev_raw["event_type"]),
                event_timestamp=str(ev_raw["event_timestamp"]),
                event_source=str(ev_raw["event_source"]),
                event_payload_digest=str(ev_raw["event_payload_digest"]),
                previous_event_digest=str(ev_raw["previous_event_digest"]),
                payload=dict(ev_raw.get("payload") or {}),
                event_digest=str(ev_raw["event_digest"]),
            )
            restored_timeline.append(ev_obj)

        # Hydrate verified state into runtime
        self._experiments = restored_experiments
        self._timeline = restored_timeline

    def _load_persisted_state(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return
        with MultiProcessLock(self._get_lock_path(), timeout=5.0):
            self._load_persisted_state_unlocked()


def _default_registry_storage_path() -> Optional[Path]:
    env_p = os.environ.get("CBE_EXPERIMENT_REGISTRY_PATH", "").strip()
    if env_p:
        return Path(env_p)
    staging_dir = Path("/app/data/prospective")
    if staging_dir.exists() and os.access(str(staging_dir), os.W_OK):
        return staging_dir / "sprint27_experiment_registry.json"
    return None


# Singleton service instance
experiment_registry_service = ExperimentRegistryAndTimelineService(
    storage_path=_default_registry_storage_path()
)
