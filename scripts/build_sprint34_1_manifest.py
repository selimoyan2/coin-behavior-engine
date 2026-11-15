"""Generate SHA-256 delivery manifest for Sprint 34.1 artifacts."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    delivery_dir = Path("research_outputs/sprint34_1_scientific_data_deployment_closure")
    files = sorted([f for f in delivery_dir.iterdir() if f.is_file() and f.name != "18_sha256_delivery_manifest.json"])

    manifest = {
        "sprint_id": "CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_artifacts": len(files),
        "artifacts": [],
    }

    for f in files:
        sha = compute_sha256(f)
        manifest["artifacts"].append({
            "filename": f.name,
            "bytes": f.stat().st_size,
            "sha256": sha,
        })

    out_file = delivery_dir / "18_sha256_delivery_manifest.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated manifest with {len(files)} artifacts at {out_file}")

if __name__ == "__main__":
    main()
