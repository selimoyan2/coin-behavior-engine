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
    _artifact_registry: Dict[str, Dict[str, Any]] = {}

    # Safe cache: key -> (mtime_ns, size_bytes, VerifiedArtifact)
    _cache: Dict[str, Tuple[int, int, VerifiedArtifact]] = {}

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

        stat = path.stat()
        mtime_ns = stat.st_mtime_ns
        size_bytes = stat.st_size

        # Check safe cache
        if clean_id in cls._cache:
            c_mtime, c_size, c_art = cls._cache[clean_id]
            if c_mtime == mtime_ns and c_size == size_bytes:
                # Cache valid, re-check expected parameters if provided
                if expected_sha256 and c_art.actual_sha256 != expected_sha256:
                    return None, f"Artifact SHA-256 mismatch: expected {expected_sha256}, got {c_art.actual_sha256}"
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

        # Check for fraudulent self-comparison by file identity
        if expected_art.file_path.resolve() == actual_art.file_path.resolve():
            return False, "FRAUDULENT_SELF_COMPARISON", 0.0, 0.0, [
                "Self-comparison fraud detected: expected and actual resolve to identical physical artifact file."
            ]

        # Check execution ID identity
        if expected_art.execution_id and actual_art.execution_id and expected_art.execution_id == actual_art.execution_id:
            return False, "FRAUDULENT_SELF_COMPARISON", 0.0, 0.0, [
                "Self-comparison fraud detected: expected and actual resolve to identical execution ID."
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

