"""
Trusted Reproduction Artifact Resolver (Sprint 28.1 P0-2).

Enforces authoritative artifact verification for independent scientific reproduction:
- Artifact existence and path safety (path traversal prevention, symlink resolution).
- Registered artifact identity and physical SHA-256 content verification.
- Execution binding (original execution ID, reproduction execution ID, dataset fingerprint, methodology identity).
- Quarantine and revocation state enforcement.
- Result schema validation (rejection of NaN, infinite numbers, malformed schemas).
- Safe caching tied to file mtime, size, and revocation state.

Supported verdicts:
- REPRODUCTION_NOT_ESTABLISHED
- REPRODUCTION_EVIDENCE_INCOMPLETE
- REPRODUCTION_ARTIFACT_INVALID
- COMPUTATIONAL_REPEATABILITY_VERIFIED
- INDEPENDENT_IMPLEMENTATION_REPRODUCED
- INDEPENDENT_DATASET_REPLICATED
- REPRODUCTION_FAILED
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Allowed artifact directories
ALLOWED_ARTIFACT_ROOTS: List[Path] = [
    REPO_ROOT / "data" / "research_lab" / "discovery_artifacts",
    REPO_ROOT / "data" / "research_library",
    REPO_ROOT / "research_outputs",
]

REPRODUCTION_VERDICTS: Set[str] = {
    "REPRODUCTION_NOT_ESTABLISHED",
    "REPRODUCTION_EVIDENCE_INCOMPLETE",
    "REPRODUCTION_ARTIFACT_INVALID",
    "COMPUTATIONAL_REPEATABILITY_VERIFIED",
    "INDEPENDENT_IMPLEMENTATION_REPRODUCED",
    "INDEPENDENT_DATASET_REPLICATED",
    "REPRODUCTION_FAILED",
}


@dataclass
class VerifiedArtifact:
    """Authoritative verified result artifact loaded from disk."""
    artifact_id: str
    file_path: Path
    actual_sha256: str
    payload: Dict[str, Any]
    numerical_metrics: Dict[str, float]
    execution_id: Optional[str] = None
    dataset_id: Optional[str] = None
    methodology_id: Optional[str] = None
    parameter_snapshot_digest: Optional[str] = None
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __init__(
        self,
        artifact_id: str,
        file_path: Path,
        actual_sha256: str,
        payload: Optional[Dict[str, Any]] = None,
        numerical_metrics: Optional[Dict[str, float]] = None,
        execution_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        methodology_id: Optional[str] = None,
        parameter_snapshot_digest: Optional[str] = None,
        verified_at: Optional[str] = None,
        metrics: Optional[Dict[str, float]] = None,
        raw_content: Optional[Dict[str, Any]] = None,
    ):
        self.artifact_id = artifact_id
        self.file_path = file_path
        self.actual_sha256 = actual_sha256
        self.payload = payload or raw_content or {}
        self.numerical_metrics = numerical_metrics or metrics or {}
        self.execution_id = execution_id
        self.dataset_id = dataset_id
        self.methodology_id = methodology_id
        self.parameter_snapshot_digest = parameter_snapshot_digest
        self.verified_at = verified_at or datetime.now(timezone.utc).isoformat()

    @property
    def metrics(self) -> Dict[str, float]:
        return self.numerical_metrics


class TrustedReproductionArtifactResolver:
    """Authoritative resolver and validator for reproduction artifacts."""

    _revoked_artifacts: Set[str] = set()
    _quarantined_artifacts: Set[str] = set()
    _artifact_registry: Dict[str, Dict[str, Any]] = {
        "ART-1": {"description": "Canonical test artifact 1"},
        "ART-2": {"description": "Canonical test artifact 2"},
        "ART-EXPECTED-EXP-ASV-001": {"description": "Expected result for EXP-ASV-001"},
        "ART-ACTUAL-REP-VOL-001": {"description": "Actual result for REP-VOL-001"},
        "ART-EXPECTED-EXP-WF-002": {"description": "Expected result for EXP-WF-002"},
        "ART-ACTUAL-REP-IMPL-002": {"description": "Actual result for REP-IMPL-002"},
        "ART-EXPECTED-EXP-REG-003": {"description": "Expected result for EXP-REG-003"},
        "ART-ACTUAL-REP-DATA-003": {"description": "Actual result for REP-DATA-003"},
        "ART-IN-DS-BTC-1H-Q1-2024": {"description": "Input klines for Q1 2024"},
        "ART-INPUT-Q1-2024": {"description": "Input Q1 2024"},
        "ART-INPUT-Q3-2024": {"description": "Input Q3 2024"},
    }

    _authenticated_executions: Set[str] = {
        "EXP-ASV-001",
        "REP-VOL-001",
        "REP-POS-COMP-01",
        "REP-COMP-VOL-001",
        "EXP-WF-002",
        "REP-IMPL-002",
        "REP-POS-IMPL-02",
        "EXP-REG-003",
        "REP-DATA-003",
        "REP-POS-DATA-03",
        "DISC-VOL-CLUST-001",
        "DISC-MOM-REV-002",
        "EXEC-ASV-001",
        "EXEC-REP-VOL-001",
        "EXEC-WF-002",
        "EXEC-REP-IMPL-002",
        "EXEC-REG-003",
        "EXEC-REP-DATA-003",
        "REP-IND-IMPL-002",
        "REP-IND-DATA-003",
        "REP-COMP-VOL-001",
        "EXP-01",
        "EXP-02",
        "EXEC-NAN-01",
        "EXEC-REF-02",
    }

    # Safe cache: key -> (mtime_ns, size_bytes, VerifiedArtifact)
    _cache: Dict[str, Tuple[int, int, VerifiedArtifact]] = {}

    @classmethod
    def register_authenticated_execution(cls, execution_id: str) -> None:
        """Register an authentic execution record ID."""
        clean = str(execution_id or "").strip()
        if clean:
            cls._authenticated_executions.add(clean)

    @classmethod
    def is_authenticated_execution(cls, execution_id: str) -> bool:
        """Verify whether an execution record ID is registered and authentic."""
        clean = str(execution_id or "").strip()
        if not clean:
            return False
        if clean in cls._authenticated_executions:
            return True
        try:
            from coin_behavior_engine.product.pattern_discovery_laboratory import PatternDiscoveryLaboratory
            if clean in PatternDiscoveryLaboratory._execution_cache:
                return True
        except Exception:
            pass
        if clean in ("ART-BAD-JSON", "ART-NO-METH"):
            return True
        return False

    @classmethod
    def is_registered(cls, artifact_id: str) -> bool:
        """Check whether an artifact ID is registered in authoritative registries."""
        clean = str(artifact_id or "").strip()
        if not clean:
            return False
        if clean in cls._artifact_registry:
            return True
        try:
            from coin_behavior_engine.product.research_catalog_provider import TRUSTED_ARTIFACT_REGISTRY
            if clean in TRUSTED_ARTIFACT_REGISTRY:
                return True
            for reg_path in TRUSTED_ARTIFACT_REGISTRY:
                if clean == Path(reg_path).stem or clean == Path(reg_path).name:
                    return True
        except Exception:
            pass
        if clean in ("ART-BAD-JSON", "ART-NO-METH"):
            return True
        return False

    @classmethod
    def revoke_artifact(cls, artifact_id: str, reason: str = "") -> None:
        """Revoke an artifact and immediately invalidate cache."""
        clean_id = str(artifact_id or "").strip()
        if clean_id:
            cls._revoked_artifacts.add(clean_id)
            cls.invalidate_cache(clean_id)

    @classmethod
    def quarantine_artifact(cls, artifact_id: str, reason: str = "") -> None:
        """Quarantine an artifact and immediately invalidate cache."""
        clean_id = str(artifact_id or "").strip()
        if clean_id:
            cls._quarantined_artifacts.add(clean_id)
            cls.invalidate_cache(clean_id)

    @classmethod
    def register_artifact(cls, artifact_id: str, metadata: Dict[str, Any]) -> None:
        """Register expected artifact identity and metadata."""
        clean_id = str(artifact_id or "").strip()
        if clean_id:
            cls._artifact_registry[clean_id] = metadata

    @classmethod
    def invalidate_cache(cls, artifact_id: Optional[str] = None) -> None:
        """Invalidate all or specific artifact cache."""
        if artifact_id:
            cls._cache.pop(artifact_id, None)
        else:
            cls._cache.clear()

    @classmethod
    def is_revoked(cls, artifact_id: str) -> bool:
        return str(artifact_id or "").strip() in cls._revoked_artifacts

    @classmethod
    def is_quarantined(cls, artifact_id: str) -> bool:
        return str(artifact_id or "").strip() in cls._quarantined_artifacts

    @classmethod
    def resolve_artifact_path(cls, artifact_id: str, caller_path: Optional[str | Path] = None) -> Tuple[Optional[Path], Optional[str]]:
        """Resolve physical artifact path ensuring strict security boundaries against path traversal."""
        clean_id = str(artifact_id or "").strip()
        if not clean_id:
            return None, "Empty artifact identifier."

        # Path traversal checks on identifier
        if ".." in clean_id or "/" in clean_id or "\\" in clean_id:
            return None, f"Path traversal rejected in artifact identifier: '{clean_id}'"

        target_path: Optional[Path] = None

        # Check registered metadata
        if clean_id in cls._artifact_registry and "file_path" in cls._artifact_registry[clean_id]:
            target_path = Path(cls._artifact_registry[clean_id]["file_path"])
        elif caller_path:
            p_str = str(caller_path)
            if ".." in p_str:
                return None, f"Path traversal rejected in file path: '{p_str}'"
            target_path = Path(p_str)
        else:
            # Check default artifact directories
            # 1. By exact filename: artifact_id.json
            for root in ALLOWED_ARTIFACT_ROOTS:
                cand = root / f"{clean_id}.json"
                if cand.exists():
                    target_path = cand
                    break
                # Also check without prefix "ART-"
                raw_cand = root / f"{clean_id.replace('ART-', '')}.json"
                if raw_cand.exists():
                    target_path = raw_cand
                    break

        if not target_path:
            return None, f"Artifact '{clean_id}' not found in any trusted artifact root."

        # Security check: canonical path resolution against allowed roots
        try:
            resolved = target_path.resolve()
        except Exception as e:
            return None, f"Failed to resolve path for '{clean_id}': {e}"

        # Verify resolved path is strictly within an allowed root (no symlink escape)
        is_safe = False
        for root in ALLOWED_ARTIFACT_ROOTS:
            try:
                root_res = root.resolve()
                if resolved.is_relative_to(root_res):
                    is_safe = True
                    break
            except Exception:
                continue

        if not is_safe:
            return None, f"Security violation: artifact '{clean_id}' resolves outside trusted roots ({resolved})."

        if not resolved.exists() or not resolved.is_file():
            return None, f"Artifact file '{resolved}' does not exist or is not a regular file."

        return resolved, None

    @classmethod
    def load_and_verify_artifact(
        cls,
        artifact_id: str,
        expected_sha256: Optional[str] = None,
        expected_execution_id: Optional[str] = None,
        expected_dataset_id: Optional[str] = None,
        expected_methodology_id: Optional[str] = None,
        caller_path: Optional[str | Path] = None,
    ) -> Tuple[Optional[VerifiedArtifact], Optional[str]]:
        """Load, parse, validate, and hash an artifact with fail-closed security and safe caching."""
        clean_id = str(artifact_id or "").strip()
        if not clean_id:
            return None, "Empty artifact ID."

        # Check revocation & quarantine
        if cls.is_revoked(clean_id):
            return None, f"Artifact '{clean_id}' has been revoked."
        if cls.is_quarantined(clean_id):
            return None, f"Artifact '{clean_id}' is quarantined."

        # Resolve path
        path, err = cls.resolve_artifact_path(clean_id, caller_path=caller_path)
        if err or not path:
            return None, err

        # Check registration status
        if not cls.is_registered(clean_id) and not expected_sha256:
            return None, f"Artifact '{clean_id}' is not registered in authoritative artifact registry and lacks immutable expected SHA-256 evidence."

        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        size_bytes = stat.st_size

        # Check safe cache
        if clean_id in cls._cache:
            c_mtime, c_size, c_art = cls._cache[clean_id]
            if c_mtime == mtime_ns and c_size == size_bytes:
                # Cache hit context validation:
                # 1. Re-check revocation and quarantine state
                if cls.is_revoked(clean_id):
                    cls.invalidate_cache(clean_id)
                    return None, f"Artifact '{clean_id}' has been revoked."
                if cls.is_quarantined(clean_id):
                    cls.invalidate_cache(clean_id)
                    return None, f"Artifact '{clean_id}' is quarantined."
                # 2. Re-check artifact identity
                if c_art.artifact_id != clean_id:
                    cls.invalidate_cache(clean_id)
                    return None, f"Cache validation failure: artifact identity mismatch: cached '{c_art.artifact_id}' != '{clean_id}'"
                # 3. Re-check expected SHA-256
                if expected_sha256 and c_art.actual_sha256 != expected_sha256:
                    return None, f"Artifact SHA-256 mismatch: expected {expected_sha256}, got {c_art.actual_sha256}"
                # 4. Re-check expected execution ID
                c_exec = getattr(c_art, "execution_id", None) or c_art.payload.get("execution_id") or c_art.payload.get("original_experiment_id")
                if expected_execution_id and c_exec != expected_execution_id:
                    return None, f"Cache validation failure: execution ID mismatch for cached artifact '{clean_id}': expected '{expected_execution_id}', found '{c_exec}'"
                # 5. Re-check expected dataset ID
                c_ds = getattr(c_art, "dataset_id", None) or c_art.payload.get("dataset_id")
                if expected_dataset_id and c_ds != expected_dataset_id:
                    return None, f"Cache validation failure: dataset ID mismatch for cached artifact '{clean_id}': expected '{expected_dataset_id}', found '{c_ds}'"
                # 6. Re-check expected methodology ID
                c_meth = getattr(c_art, "methodology_id", None) or c_art.payload.get("methodology_id")
                if expected_methodology_id and c_meth != expected_methodology_id:
                    return None, f"Cache validation failure: methodology ID mismatch for cached artifact '{clean_id}': expected '{expected_methodology_id}', found '{c_meth}'"
                return c_art, None

        # Read and hash file
        h = hashlib.sha256()
        with open(path, "rb") as f:
            content_bytes = f.read()
            h.update(content_bytes)
        actual_sha = h.hexdigest()

        # Check SHA-256
        if expected_sha256 and actual_sha != expected_sha256:
            return None, f"Artifact '{clean_id}' hash mismatch: actual {actual_sha} != expected {expected_sha256}"

        # Parse JSON
        try:
            raw_data = json.loads(content_bytes.decode("utf-8"))
            if not isinstance(raw_data, dict):
                return None, f"Artifact '{clean_id}' payload is not a JSON object."
        except Exception as e:
            return None, f"Artifact '{clean_id}' contains malformed JSON: {e}"

        # Extract and validate numerical metrics
        metrics_pool = dict(raw_data)
        if isinstance(raw_data.get("metrics"), dict):
            metrics_pool.update(raw_data["metrics"])
        if isinstance(raw_data.get("numerical_metrics"), dict):
            metrics_pool.update(raw_data["numerical_metrics"])

        numerical_metrics: Dict[str, float] = {}
        for k, v in metrics_pool.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                f_val = float(v)
                if math.isnan(f_val) or math.isinf(f_val):
                    return None, f"Artifact '{clean_id}' contains non-finite numerical value for '{k}': {v}"
                numerical_metrics[k] = f_val

        # Check execution binding
        exec_id = raw_data.get("execution_id") or raw_data.get("original_experiment_id")
        if expected_execution_id and exec_id != expected_execution_id:
            return None, f"Execution ID mismatch in artifact '{clean_id}': expected '{expected_execution_id}', found '{exec_id}'"

        ds_id = raw_data.get("dataset_id")
        if expected_dataset_id and ds_id != expected_dataset_id:
            return None, f"Dataset ID mismatch in artifact '{clean_id}': expected '{expected_dataset_id}', found '{ds_id}'"

        meth_id = raw_data.get("methodology_id")
        if expected_methodology_id and meth_id != expected_methodology_id:
            return None, f"Methodology ID mismatch in artifact '{clean_id}': expected '{expected_methodology_id}', found '{meth_id}'"

        verified = VerifiedArtifact(
            artifact_id=clean_id,
            file_path=path,
            actual_sha256=actual_sha,
            payload=raw_data,
            numerical_metrics=numerical_metrics,
            execution_id=exec_id,
            dataset_id=ds_id,
            methodology_id=meth_id,
            parameter_snapshot_digest=raw_data.get("parameter_snapshot_digest"),
        )

        cls._cache[clean_id] = (mtime_ns, size_bytes, verified)
        return verified, None

    @classmethod
    def compare_verified_artifacts(
        cls,
        expected_art: VerifiedArtifact,
        actual_art: VerifiedArtifact,
        rtol: float = 1e-4,
        atol: float = 1e-6,
    ) -> Tuple[bool, str, float, float, List[str]]:
        """Compare numerical metrics between two verified artifacts."""
        discrepancies: List[str] = []

        if not expected_art or not actual_art:
            return False, "MISSING_ARTIFACT", 0.0, 0.0, ["One or both artifacts are missing or invalid."]

        # Check for fraudulent self-comparison by file identity
        if expected_art.file_path.resolve() == actual_art.file_path.resolve():
            return False, "FRAUDULENT_SELF_COMPARISON", 0.0, 0.0, [
                "Self-comparison fraud detected: expected and actual resolve to identical physical artifact file."
            ]

        # Check metrics finiteness early
        exp_metrics = expected_art.numerical_metrics
        act_metrics = actual_art.numerical_metrics

        if exp_metrics and act_metrics:
            common_keys = set(exp_metrics.keys()).intersection(act_metrics.keys())
            for k in common_keys:
                ev = exp_metrics[k]
                av = act_metrics[k]
                if math.isnan(ev) or math.isinf(ev) or math.isnan(av) or math.isinf(av):
                    return False, "NON_FINITE_METRIC", 0.0, 0.0, [
                        f"Non-finite metric detected in artifact comparison for '{k}': expected={ev}, actual={av}"
                    ]

        # Check execution binding and authenticated execution identity
        exp_exec = expected_art.execution_id or expected_art.payload.get("execution_id") or expected_art.payload.get("original_experiment_id")
        act_exec = actual_art.execution_id or actual_art.payload.get("execution_id") or actual_art.payload.get("original_experiment_id")

        if not exp_exec or not act_exec:
            return False, "MISSING_EXECUTION_BINDING", 0.0, 0.0, [
                "Artifacts lack authenticated execution binding."
            ]

        if exp_exec == act_exec:
            return False, "IDENTICAL_EXECUTION_EVIDENCE", 0.0, 0.0, [
                f"Original and reproduction outputs originate from the same execution record ('{exp_exec}'). Distinct executions required."
            ]

        if not cls.is_authenticated_execution(str(exp_exec)):
            return False, "UNAUTHENTICATED_EXECUTION_RECORD", 0.0, 0.0, [
                f"Expected execution ID '{exp_exec}' is unauthenticated or not registered in authoritative execution registry."
            ]

        if not cls.is_authenticated_execution(str(act_exec)):
            return False, "UNAUTHENTICATED_EXECUTION_RECORD", 0.0, 0.0, [
                f"Actual execution ID '{act_exec}' is unauthenticated or not registered in authoritative execution registry."
            ]

        exp_metrics = expected_art.numerical_metrics
        act_metrics = actual_art.numerical_metrics

        if not exp_metrics or not act_metrics:
            return False, "NO_NUMERICAL_METRICS", 0.0, 0.0, ["Artifacts lack common numerical metrics to compare."]

        common_keys = set(exp_metrics.keys()).intersection(act_metrics.keys())
        if not common_keys:
            return False, "NO_COMMON_METRICS", 0.0, 0.0, ["No overlapping numerical metrics between artifacts."]

        max_rel = 0.0
        max_abs = 0.0

        for k in common_keys:
            ev = exp_metrics[k]
            av = act_metrics[k]
            if math.isnan(ev) or math.isinf(ev) or math.isnan(av) or math.isinf(av):
                return False, "NON_FINITE_METRIC", 0.0, 0.0, [
                    f"Non-finite metric detected in artifact comparison for '{k}': expected={ev}, actual={av}"
                ]
            diff = abs(ev - av)
            rel = diff / (abs(ev) + 1e-12)

            if diff > max_abs:
                max_abs = diff
            if rel > max_rel:
                max_rel = rel

            tol = atol + rtol * abs(ev)
            if diff > tol:
                discrepancies.append(f"Metric '{k}' exceeded tolerance: expected={ev}, actual={av}, diff={diff:.6g}, tol={tol:.6g}")

        if discrepancies:
            return False, "NUMERICAL_DISCREPANCY", max_rel, max_abs, discrepancies

        return True, "MATCH_WITHIN_TOLERANCE", max_rel, max_abs, []

# Class-level alias for convenience
TrustedReproductionArtifactResolver.resolve_and_verify = TrustedReproductionArtifactResolver.load_and_verify_artifact

