"""Build Sprint 34 SHA-256 Manifest and Copy to Brain Artifact Directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

REPO_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint34_canonical_causal_and_historical_data"
BRAIN_ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = sorted([f for f in DELIVERY_DIR.iterdir() if f.is_file() and f.name != "21_sha256_artifact_manifest.json"])
    manifest_entries = []

    for f in files:
        sha = compute_sha256(f)
        size = f.stat().st_size
        manifest_entries.append({
            "filename": f.name,
            "size_bytes": size,
            "sha256": sha,
            "type": f.suffix.replace(".", "").upper(),
        })

    manifest = {
        "sprint_id": "CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA",
        "timestamp_utc": "2026-11-15T19:17:00Z",
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "total_artifacts": len(manifest_entries) + 1,  # including manifest itself
        "artifacts": manifest_entries,
    }

    manifest_path = DELIVERY_DIR / "21_sha256_artifact_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as out_f:
        json.dump(manifest, out_f, indent=2)

    # Compute manifest self hash
    manifest_sha = compute_sha256(manifest_path)
    print(f"Generated 21_sha256_artifact_manifest.json (SHA-256: {manifest_sha})")

    # Copy all files to brain artifact directory
    if BRAIN_ARTIFACT_DIR.exists():
        for f in DELIVERY_DIR.iterdir():
            if f.is_file():
                dest = BRAIN_ARTIFACT_DIR / f.name
                shutil.copy2(f, dest)
                print(f"Copied to brain: {f.name}")


if __name__ == "__main__":
    main()
