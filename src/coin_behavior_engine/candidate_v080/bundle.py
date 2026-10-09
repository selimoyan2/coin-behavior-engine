"""CBE-0.8.0 Research Model Bundle Serialization & Schema.

Provides deterministic, non-executable (JSON-only) serialization for candidate Ridge models,
feature manifests, target specifications, and fitted scaler parameters.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np


class BundleIntegrityError(Exception):
    """Raised when model bundle validation or hash check fails."""
    pass


@dataclass
class ScalerParameters:
    mean_: List[float]
    scale_: List[float]
    var_: List[float]
    n_features_in_: int


@dataclass
class RidgeModelParameters:
    horizon: str
    coefficients: List[float]
    intercept: float
    alpha: float
    training_r2: float
    training_mae: float
    training_rows: int


@dataclass
class ModelBundleV080:
    schema_version: str = "CBE-BUNDLE-0.8.0"
    candidate_model_version: str = "CBE-0.8.0"
    bundle_status: str = "RESEARCH_CANDIDATE_ARTIFACT_VALID"
    created_at_utc: str = ""
    source_commit: str = "b5ffdfe"
    source_sprint: str = "SPRINT_09.2"
    runtime_tier: str = "SPOT_ONLY_U0"
    training_environment: Dict[str, str] = field(default_factory=dict)
    dataset_fingerprints: Dict[str, str] = field(default_factory=dict)
    partition_boundaries: Dict[str, str] = field(default_factory=dict)
    feature_manifest: Dict[str, Any] = field(default_factory=dict)
    target_manifest: Dict[str, Any] = field(default_factory=dict)
    scaler: Optional[ScalerParameters] = None
    models: Dict[str, RidgeModelParameters] = field(default_factory=dict)
    preprocessing_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_canonical_json(self) -> str:
        """Serialize to deterministic, compact, key-sorted JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)

    def compute_sha256(self) -> str:
        canonical_str = self.to_canonical_json()
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def save(self, bundle_path: Path, lockbox_path: Optional[Path] = None) -> str:
        bundle_path = Path(bundle_path)
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_json = self.to_canonical_json()
        bundle_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write(canonical_json)

        if lockbox_path:
            lockbox_path = Path(lockbox_path)
            lockbox_path.parent.mkdir(parents=True, exist_ok=True)
            lockbox_data = {
                "bundle_filename": bundle_path.name,
                "bundle_sha256": bundle_hash,
                "candidate_version": self.candidate_model_version,
                "schema_version": self.schema_version,
                "created_at_utc": self.created_at_utc,
                "verification_method": "SHA256_CANONICAL_JSON",
            }
            with open(lockbox_path, "w", encoding="utf-8") as f:
                json.dump(lockbox_data, f, indent=2)

        return bundle_hash

    @classmethod
    def load(
        cls,
        bundle_path: Path,
        lockbox_path: Optional[Path] = None,
        verify_lockbox: bool = True,
    ) -> "ModelBundleV080":
        bundle_path = Path(bundle_path)
        if not bundle_path.exists():
            raise BundleIntegrityError(f"Bundle file not found: {bundle_path}")

        with open(bundle_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        computed_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        if verify_lockbox and lockbox_path:
            lockbox_path = Path(lockbox_path)
            if not lockbox_path.exists():
                raise BundleIntegrityError(f"Lockbox manifest not found: {lockbox_path}")
            with open(lockbox_path, "r", encoding="utf-8") as f:
                lockbox_data = json.load(f)
            expected_hash = lockbox_data.get("bundle_sha256")
            if computed_hash != expected_hash:
                raise BundleIntegrityError(
                    f"Bundle hash mismatch! Computed: {computed_hash}, Expected in lockbox: {expected_hash}"
                )

        data = json.loads(raw_text)
        cls.validate_data(data)

        scaler_data = data.get("scaler")
        scaler = ScalerParameters(**scaler_data) if scaler_data else None

        models_data = data.get("models", {})
        models = {}
        for h, m_data in models_data.items():
            models[h] = RidgeModelParameters(**m_data)

        bundle = cls(
            schema_version=data.get("schema_version", "CBE-BUNDLE-0.8.0"),
            candidate_model_version=data.get("candidate_model_version", "CBE-0.8.0"),
            bundle_status=data.get("bundle_status", "UNKNOWN"),
            created_at_utc=data.get("created_at_utc", ""),
            source_commit=data.get("source_commit", ""),
            source_sprint=data.get("source_sprint", ""),
            runtime_tier=data.get("runtime_tier", "SPOT_ONLY_U0"),
            training_environment=data.get("training_environment", {}),
            dataset_fingerprints=data.get("dataset_fingerprints", {}),
            partition_boundaries=data.get("partition_boundaries", {}),
            feature_manifest=data.get("feature_manifest", {}),
            target_manifest=data.get("target_manifest", {}),
            scaler=scaler,
            models=models,
            preprocessing_rules=data.get("preprocessing_rules", {}),
        )
        return bundle

    @staticmethod
    def validate_data(data: Dict[str, Any]) -> None:
        required_keys = [
            "schema_version",
            "candidate_model_version",
            "feature_manifest",
            "target_manifest",
            "scaler",
            "models",
        ]
        for k in required_keys:
            if k not in data:
                raise BundleIntegrityError(f"Missing required bundle key: {k}")

        # Check features
        feat_manifest = data["feature_manifest"]
        ordered_feats = feat_manifest.get("ordered_features", [])
        if not ordered_feats:
            raise BundleIntegrityError("Ordered features list is empty in feature_manifest")

        n_feats = len(ordered_feats)

        # Check scaler dimensions
        scaler_data = data["scaler"]
        if len(scaler_data["mean_"]) != n_feats:
            raise BundleIntegrityError(
                f"Scaler mean_ dimension mismatch: {len(scaler_data['mean_'])} != {n_feats}"
            )
        if len(scaler_data["scale_"]) != n_feats:
            raise BundleIntegrityError(
                f"Scaler scale_ dimension mismatch: {len(scaler_data['scale_'])} != {n_feats}"
            )

        # Check models
        models = data["models"]
        for h in ["1h", "4h", "24h"]:
            if h not in models:
                raise BundleIntegrityError(f"Missing model for horizon {h}")
            m = models[h]
            if len(m["coefficients"]) != n_feats:
                raise BundleIntegrityError(
                    f"Model {h} coefficients dimension mismatch: {len(m['coefficients'])} != {n_feats}"
                )
            if not np.isfinite(m["intercept"]):
                raise BundleIntegrityError(f"Model {h} intercept is non-finite: {m['intercept']}")
            for idx, c in enumerate(m["coefficients"]):
                if not np.isfinite(c):
                    raise BundleIntegrityError(f"Model {h} coef[{idx}] is non-finite: {c}")
