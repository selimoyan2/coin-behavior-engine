"""
Script to compute SHA-256 hashes of all Sprint 29 delivery artifacts and generate
research_outputs/sprint29_btc_timing_research/24_sha256_delivery_manifest.json.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DELIVERY_DIR = ROOT_DIR / "research_outputs" / "sprint29_btc_timing_research"


def generate_manifest():
    manifest_entries = {}
    for f in sorted(DELIVERY_DIR.iterdir()):
        if f.is_file():
            if f.name == "24_sha256_delivery_manifest.json":
                continue
            data = f.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            manifest_entries[f.name] = {
                "file_path": str(f.relative_to(ROOT_DIR)).replace("\\", "/"),
                "size_bytes": len(data),
                "sha256": sha,
            }

    manifest_path = DELIVERY_DIR / "24_sha256_delivery_manifest.json"
    manifest_data = {
        "manifest_version": "CBE-SPRINT-29-MANIFEST-V1",
        "sprint_id": "CBE_SPRINT29_BTC_TIMING_RESEARCH_AND_HISTORICAL_PAPER_PORTFOLIO",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_files": len(manifest_entries) + 1,
        "files": manifest_entries,
    }
    with open(manifest_path, "w", encoding="utf-8") as out:
        json.dump(manifest_data, out, indent=2, ensure_ascii=False)
        out.write("\n")

    print(f"Generated manifest: 24_sha256_delivery_manifest.json with {len(manifest_entries)} artifact entries.")


if __name__ == "__main__":
    generate_manifest()
