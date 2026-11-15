"""Generate SHA-256 Delivery Manifest for Sprint 30."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint30_btc_timing_optimization"
MANIFEST_PATH = DELIVERY_DIR / "22_sha256_delivery_manifest.json"
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest: dict[str, dict] = {}
    for item in sorted(DELIVERY_DIR.iterdir()):
        if item.is_file() and item.name != "22_sha256_delivery_manifest.json":
            sha = compute_sha256(item)
            manifest[item.name] = {
                "sha256": sha,
                "size_bytes": item.stat().st_size,
            }

    payload = {
        "sprint_id": "CBE_SPRINT30_BTC_TIMING_OPTIMIZATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_deliverables": len(manifest),
        "files": manifest,
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Generated manifest with {len(manifest)} files: {MANIFEST_PATH}")

    if ARTIFACT_DIR.exists():
        shutil.copy2(MANIFEST_PATH, ARTIFACT_DIR / MANIFEST_PATH.name)
        print(f"Copied manifest to artifact dir: {ARTIFACT_DIR / MANIFEST_PATH.name}")


if __name__ == "__main__":
    main()
