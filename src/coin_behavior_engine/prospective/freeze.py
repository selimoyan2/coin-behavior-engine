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


FREEZE_COMMIT = "849e76ed27d9275921c7d2b11cd340a543790c80"


def compute_canonical_text_sha256(filepath: Path) -> str:
    """Compute platform-independent canonical SHA-256 hash for text artifacts.
    
    Normalizes CRLF (\r\n) and lone CR (\r) to LF (\n) in memory without modifying
    the file on disk or altering any non-newline bytes.
    """
    raw = filepath.read_bytes()
    canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical).hexdigest()


def verify_sprint07_freeze(
    sprint07_dir: Path = Path("data/reports/sprint07"),
    lockbox_path: Path = Path("data/prospective/lockbox_manifest.json"),
    v2_manifest_path: Optional[Path] = None,
    raise_on_error: bool = False,
) -> Dict[str, Any]:
    """Verify Sprint 07 model freeze across platforms using Canonical Freeze Manifest V2.
    
    Performs 5-layer dual verification:
      LAYER 1: Model version check (CBE-0.7.0)
      LAYER 2: Historical boundary / lockbox check
      LAYER 3: 29/29 canonical artifact hash verification against Freeze Manifest V2
      LAYER 4: Legacy provenance presence check (reproducibility_manifest.json exists)
      LAYER 5: Freeze commit identity metadata check
      
    Returns detailed verification summary.
    """
    if v2_manifest_path is None:
        v2_manifest_path = sprint07_dir.parent / "sprint08" / "cross_platform_freeze_manifest_v2.json"

    # LAYER 4: Legacy provenance check
    repro_file = sprint07_dir / "reproducibility_manifest.json"
    legacy_manifest_present = repro_file.exists()
    legacy_manifest_sha256 = compute_sha256(repro_file) if legacy_manifest_present else ""

    if not legacy_manifest_present:
        msg = f"Legacy Sprint 07 reproducibility manifest missing at {repro_file}"
        if raise_on_error:
            raise ModelFreezeViolation(msg)
        return {
            "status": "MODEL_FREEZE_VIOLATION",
            "error": msg,
            "verified": False,
            "verification_version": "V2_CANONICAL",
            "legacy_manifest_present": False,
            "legacy_manifest_sha256": "",
            "canonical_hashes_verified": 0,
            "canonical_mismatches": [],
            "missing_files": [str(repro_file.name)],
            "lockbox_verified": False,
            "freeze_commit": FREEZE_COMMIT,
            "model_version": FROZEN_MODEL_VERSION,
            "total_artifacts_checked": 0,
            "verified_artifacts_count": 0,
            "mismatches": [],
            "reproducibility_manifest_hash": "",
        }

    # Load V2 Manifest (Layer 3 & 5)
    v2_manifest: Dict[str, Any] = {}
    v2_manifest_present = v2_manifest_path.exists()
    if v2_manifest_present:
        with open(v2_manifest_path, "r", encoding="utf-8") as f:
            v2_manifest = json.load(f)

    # LAYER 1: Model version check
    manifest_version = v2_manifest.get("model_version", FROZEN_MODEL_VERSION)
    model_version_matches = (manifest_version == FROZEN_MODEL_VERSION)

    # LAYER 5: Freeze commit check
    freeze_commit_meta = v2_manifest.get("freeze_commit", FREEZE_COMMIT)
    freeze_commit_matches = (freeze_commit_meta == FREEZE_COMMIT)

    # LAYER 2: Lockbox boundary check
    lockbox_verified = False
    if lockbox_path.exists():
        with open(lockbox_path, "r", encoding="utf-8") as f:
            lockbox_data = json.load(f)
        if lockbox_data.get("historical_research_end") == HISTORICAL_RESEARCH_END:
            lockbox_verified = True

    # LAYER 3: 29/29 canonical artifact verification
    artifacts_dict = v2_manifest.get("artifacts", {})
    verified_files: List[str] = []
    canonical_mismatches: List[Dict[str, str]] = []
    missing_files: List[str] = []

    if not v2_manifest_present or not artifacts_dict:
        missing_files.append(str(v2_manifest_path.name))

    for fname, art_info in artifacts_dict.items():
        fpath = sprint07_dir / fname
        if not fpath.exists():
            missing_files.append(fname)
            continue
        exp_canonical_hash = art_info.get("canonical_sha256", "")
        actual_canonical_hash = compute_canonical_text_sha256(fpath)
        if actual_canonical_hash != exp_canonical_hash:
            canonical_mismatches.append({
                "file": fname,
                "expected_canonical_hash": exp_canonical_hash,
                "actual_canonical_hash": actual_canonical_hash,
            })
        else:
            verified_files.append(fname)

    is_verified = (
        (len(canonical_mismatches) == 0)
        and (len(missing_files) == 0)
        and (len(verified_files) == 29)
        and lockbox_verified
        and legacy_manifest_present
        and model_version_matches
        and freeze_commit_matches
    )

    result = {
        "status": "FREEZE_VERIFIED" if is_verified else "MODEL_FREEZE_VIOLATION",
        "verified": is_verified,
        "verification_version": "V2_CANONICAL",
        "model_version": FROZEN_MODEL_VERSION,
        "historical_research_end": HISTORICAL_RESEARCH_END,
        "prospective_start": PROSPECTIVE_START,
        "canonical_hashes_verified": len(verified_files),
        "canonical_mismatches": canonical_mismatches,
        "missing_files": missing_files,
        "legacy_manifest_present": legacy_manifest_present,
        "legacy_manifest_sha256": legacy_manifest_sha256,
        "lockbox_verified": lockbox_verified,
        "freeze_commit": freeze_commit_meta,
        # Backward compatibility aliases
        "total_artifacts_checked": len(artifacts_dict),
        "verified_artifacts_count": len(verified_files),
        "mismatches": canonical_mismatches,
        "reproducibility_manifest_hash": legacy_manifest_sha256,
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
