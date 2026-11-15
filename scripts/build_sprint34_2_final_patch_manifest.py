"""Build SHA256 delivery manifest for Sprint 34.2 Final Patch.

Sprint 34.2 P0 Final Patch Manifest Builder.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_patch_manifest():
    patch_dir = Path("research_outputs/sprint34_2_final_patch")
    assert patch_dir.exists(), "Patch directory must exist"

    manifest_entries = []
    for p in sorted(patch_dir.glob("*")):
        if p.is_file() and p.name != "05_sha256_manifest.json":
            sha = compute_sha256(p)
            size = p.stat().st_size
            manifest_entries.append({
                "file_name": p.name,
                "relative_path": str(p.relative_to(Path("."))).replace("\\", "/"),
                "sha256": sha,
                "size_bytes": size,
            })

    # Also add the new test file
    test_path = Path("tests/test_portfolio_drawdown_integrity_patch.py")
    if test_path.exists():
        manifest_entries.append({
            "file_name": test_path.name,
            "relative_path": str(test_path.relative_to(Path("."))).replace("\\", "/"),
            "sha256": compute_sha256(test_path),
            "size_bytes": test_path.stat().st_size,
        })

    payload = {
        "sprint_id": "CBE_SPRINT34_2_FINAL_PATCH_DRAWDOWN_STATISTICAL_INFERENCE_CLOSURE",
        "standard": "CBE-DELIVERY-MANIFEST-V1.3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "research_mode": "STRICTLY_OFFLINE_RESEARCH",
        "production_status": "STRICT_ZERO_TOUCH",
        "live_trading_status": "PERMANENTLY_PROHIBITED",
        "total_files": len(manifest_entries),
        "files": manifest_entries,
    }

    out_file = patch_dir / "05_sha256_manifest.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Generated {out_file} with {len(manifest_entries)} entries.")


if __name__ == "__main__":
    build_patch_manifest()
