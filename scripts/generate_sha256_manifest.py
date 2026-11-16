"""Generate cryptographic SHA-256 delivery manifest for Sprint 37 deliverables."""

import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

OUTPUT_DIR = Path("research_outputs/sprint37_predictive_validity")
BRAIN_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")

# Copy 17_final_acceptance_report.md to brain first
shutil.copyfile(OUTPUT_DIR / "17_final_acceptance_report.md", BRAIN_DIR / "17_final_acceptance_report.md")

manifest = {
    "sprint_id": "CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "hash_algorithm": "SHA-256",
    "files_count": 0,
    "manifest": {}
}

# Collect all files except the manifest itself
files = sorted([f for f in OUTPUT_DIR.glob("*") if f.is_file() and not f.name.startswith("16_") and not f.name.endswith(".log")])

for f in files:
    hasher = hashlib.sha256()
    with open(f, "rb") as fh:
        while chunk := fh.read(65536):
            hasher.update(chunk)
    sha256_hex = hasher.hexdigest()
    manifest["manifest"][f.name] = {
        "sha256": sha256_hex,
        "size_bytes": f.stat().st_size
    }

manifest["files_count"] = len(manifest["manifest"])

manifest_path = OUTPUT_DIR / "16_sha256_delivery_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

shutil.copyfile(manifest_path, BRAIN_DIR / "16_sha256_delivery_manifest.json")
print(f"Manifest written with {manifest['files_count']} files.")
