import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

DELIVERY_DIR = Path("research_outputs/sprint33_canonical_model_market_behavior")
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def generate_manifest():
    manifest_entries = {}
    
    # List of expected 21 files (including 14_* screenshots and json)
    all_files = sorted([f for f in DELIVERY_DIR.iterdir() if f.is_file() and not f.name.startswith("20_sha256") and not f.name.endswith(".log")])
    
    for f in all_files:
        sha = compute_sha256(f)
        size = f.stat().st_size
        manifest_entries[f.name] = {
            "sha256": sha,
            "byte_size": size
        }

    manifest = {
        "sprint_id": "CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_deliverables": len(manifest_entries),
        "files": manifest_entries
    }

    manifest_path = DELIVERY_DIR / "20_sha256_delivery_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if ARTIFACT_DIR.exists():
        shutil.copy2(manifest_path, ARTIFACT_DIR / "20_sha256_delivery_manifest.json")

    print(f"Generated manifest with {len(manifest_entries)} files!")
    print(f"Saved to {manifest_path}")

if __name__ == "__main__":
    generate_manifest()
