import hashlib
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone

OUT_DIR = Path("research_outputs/sprint35_historical_data_dashboard_v12_release")
ARTIFACT_DIR = Path(r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97")

def get_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

files = sorted([f for f in os.listdir(OUT_DIR) if f != "18_sha256_delivery_manifest.json"])

manifest = {
    "metadata": {
        "sprint_id": "CBE_SPRINT35_HISTORICAL_DATA_COMPLETION_DASHBOARD_V12_RELEASE_READINESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_branch": "research/sprint33-canonical-bridge-market-intelligence",
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "staging_verified_port": 18080,
        "staging_container_id": "fa065f377c81",
        "production_zero_touch_container": "3ec682ef49a4",
        "production_zero_touch_verified": True,
        "total_artifacts": len(files)
    },
    "artifacts": []
}

for fname in files:
    fpath = OUT_DIR / fname
    sha = get_file_sha256(fpath)
    sz = os.path.getsize(fpath)
    manifest["artifacts"].append({
        "filename": fname,
        "sha256": sha,
        "size_bytes": sz
    })

manifest_path = OUT_DIR / "18_sha256_delivery_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Generated 18_sha256_delivery_manifest.json with {len(manifest['artifacts'])} artifacts.")

# Copy all files to ARTIFACT_DIR
if ARTIFACT_DIR.exists():
    for f in os.listdir(OUT_DIR):
        src = OUT_DIR / f
        dst = ARTIFACT_DIR / f
        shutil.copy2(src, dst)
    print(f"Successfully copied all {len(os.listdir(OUT_DIR))} items to {ARTIFACT_DIR}")
else:
    print(f"Artifact directory {ARTIFACT_DIR} does not exist.")
