"""Build SHA-256 Manifest for Sprint 34.2 Deliverables.

Computes cryptographic SHA-256 digests for all artifacts in:
research_outputs/sprint34_2_final_reconciliation/

Sprint ID: CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint34_2_final_reconciliation"
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = sorted([f for f in DELIVERY_DIR.iterdir() if f.is_file() and f.name != "14_sha256_manifest.json"])

    manifest_entries = []
    for f in files:
        digest = sha256_file(f)
        size_bytes = f.stat().st_size
        manifest_entries.append({
            "filename": f.name,
            "sha256": digest,
            "size_bytes": size_bytes,
        })
        print(f"{f.name:50} {digest} ({size_bytes:,} bytes)")

    manifest = {
        "metadata": {
            "sprint_id": "CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "target_branch": "research/sprint33-canonical-bridge-market-intelligence",
            "canonical_model": "CBE-0.7.0",
            "model_status": "STRICTLY_FROZEN",
            "total_artifacts": len(manifest_entries),
        },
        "artifacts": manifest_entries,
    }

    out_path = DELIVERY_DIR / "14_sha256_manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if ARTIFACT_DIR.exists():
        shutil.copy2(out_path, ARTIFACT_DIR / "14_sha256_manifest.json")

    print(f"\nSaved manifest with {len(manifest_entries)} artifacts to {out_path}")


if __name__ == "__main__":
    main()
