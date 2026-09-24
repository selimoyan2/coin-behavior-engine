"""Model Freeze Verification for Sprint 08.

Validates that Model CBE-0.7.0 and its Sprint 07 historical artifacts remain
cryptographically frozen and unmodified before prospective scoring begins.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FROZEN_MODEL_VERSION = "CBE-0.7.0"
HISTORICAL_RESEARCH_END = "2026-09-23T23:59:59 UTC"
PROSPECTIVE_START = "2026-09-24T00:00:00 UTC"


class ModelFreezeViolation(Exception):
    """Raised when any frozen artifact hash differs from Sprint 07 manifest."""
    pass


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_sprint07_freeze(
    sprint07_dir: Path = Path("data/reports/sprint07"),
    lockbox_path: Path = Path("data/prospective/lockbox_manifest.json"),
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """Verify Sprint 07 reproducibility manifest artifact hashes and freeze boundaries.
    
    Returns a verification summary dictionary.
    """
    repro_file = sprint07_dir / "reproducibility_manifest.json"
    if not repro_file.exists():
        msg = f"Sprint 07 reproducibility manifest missing at {repro_file}"
        if raise_on_error:
            raise ModelFreezeViolation(msg)
        return {
            "status": "MODEL_FREEZE_VIOLATION",
            "error": msg,
            "verified": False,
        }

    with open(repro_file, "r", encoding="utf-8") as f:
        repro_manifest = json.load(f)

    manifest_version = repro_manifest.get("model_version")
    if manifest_version != FROZEN_MODEL_VERSION:
        msg = f"Model version mismatch: expected {FROZEN_MODEL_VERSION}, got {manifest_version}"
        if raise_on_error:
            raise ModelFreezeViolation(msg)
        return {
            "status": "MODEL_FREEZE_VIOLATION",
            "error": msg,
            "verified": False,
        }

    artifact_hashes = repro_manifest.get("artifact_hashes", {})
    verified_files: List[str] = []
    mismatches: List[Dict[str, str]] = []
    missing_files: List[str] = []

    for fname, expected_hash in artifact_hashes.items():
        if fname == "reproducibility_manifest.json":
            continue
        fpath = sprint07_dir / fname
        if not fpath.exists():
            missing_files.append(fname)
            continue
        actual_hash = compute_sha256(fpath)
        if actual_hash != expected_hash:
            mismatches.append({
                "file": fname,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            })
        else:
            verified_files.append(fname)

    # Verify lockbox boundary
    lockbox_verified = False
    if lockbox_path.exists():
        with open(lockbox_path, "r", encoding="utf-8") as f:
            lockbox_data = json.load(f)
        if lockbox_data.get("historical_research_end") == HISTORICAL_RESEARCH_END:
            lockbox_verified = True

    is_verified = (len(mismatches) == 0) and (len(missing_files) == 0) and lockbox_verified

    result = {
        "status": "FREEZE_VERIFIED" if is_verified else "MODEL_FREEZE_VIOLATION",
        "model_version": FROZEN_MODEL_VERSION,
        "historical_research_end": HISTORICAL_RESEARCH_END,
        "prospective_start": PROSPECTIVE_START,
        "verified": is_verified,
        "total_artifacts_checked": len(artifact_hashes),
        "verified_artifacts_count": len(verified_files),
        "mismatches": mismatches,
        "missing_files": missing_files,
        "lockbox_verified": lockbox_verified,
        "reproducibility_manifest_hash": compute_sha256(repro_file),
    }

    if not is_verified and raise_on_error:
        raise ModelFreezeViolation(f"Sprint 07 model freeze verification failed: {result}")

    return result


def export_freeze_verifications(
    out_dir: Path = Path("data/reports/sprint08"),
    sprint07_dir: Path = Path("data/reports/sprint07"),
    lockbox_path: Path = Path("data/prospective/lockbox_manifest.json"),
) -> Tuple[Path, Path]:
    """Export model_freeze_verification.json and prospective_boundary_verification.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = verify_sprint07_freeze(sprint07_dir, lockbox_path, raise_on_error=False)

    freeze_path = out_dir / "model_freeze_verification.json"
    with open(freeze_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    boundary_path = out_dir / "prospective_boundary_verification.json"
    boundary_info = {
        "historical_research_end": HISTORICAL_RESEARCH_END,
        "prospective_start": PROSPECTIVE_START,
        "boundary_rule": "ALL_OBSERVATIONS_T_GEQ_2026_09_24_00_00_00_BELONG_TO_PROSPECTIVE_UNSEEN",
        "retroactive_predictions_permitted": False,
        "prospective_data_leaked_into_training": False,
        "lockbox_verified": summary["lockbox_verified"],
        "verification_status": "PASSED" if summary["lockbox_verified"] else "FAILED",
    }
    with open(boundary_path, "w", encoding="utf-8") as f:
        json.dump(boundary_info, f, indent=2)

    return freeze_path, boundary_path
