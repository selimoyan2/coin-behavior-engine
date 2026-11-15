"""Generate 10_sha256_delivery_manifest.json for Sprint 32.1."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    repo_root = Path(__file__).resolve().parent.parent
    delivery_dir = repo_root / "research_outputs" / "sprint32_1_final_acceptance_closure"
    artifact_dir = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")

    deliverables = [
        "01_accounting_root_cause.md",
        "02_corrected_portfolio_reconciliation.json",
        "03_initial_capital_consistency_audit.md",
        "04_production_container_identity_forensics.md",
        "05_production_continuity_evidence.json",
        "06_dashboard_and_report_corrections.md",
        "07_targeted_test_results.json",
        "08_full_regression_results.json",
        "09_staging_verification.json",
        "11_final_acceptance_report.md",
    ]

    files_dict = {}
    for filename in deliverables:
        p = delivery_dir / filename
        if not p.exists():
            print(f"WARNING: File {filename} not found!")
            continue
        sha = compute_sha256(p)
        size = p.stat().st_size
        files_dict[filename] = {
            "sha256": sha,
            "byte_size": size,
        }
        print(f"Hashed {filename}: {sha[:16]}... ({size:,} bytes)")

    manifest = {
        "sprint_id": "CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_deliverables": len(files_dict) + 1,  # including 10 manifest itself
        "files": files_dict,
    }

    manifest_path = delivery_dir / "10_sha256_delivery_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if artifact_dir.exists():
        shutil.copy2(manifest_path, artifact_dir / "10_sha256_delivery_manifest.json")
        for filename in deliverables:
            src = delivery_dir / filename
            if src.exists():
                shutil.copy2(src, artifact_dir / filename)

    print("Successfully generated and synchronized 10_sha256_delivery_manifest.json!")


if __name__ == "__main__":
    main()
