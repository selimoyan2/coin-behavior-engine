"""Generate 18_sha256_delivery_manifest.json for Sprint 32."""

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
    delivery_dir = repo_root / "research_outputs" / "sprint32_scientific_validation_dashboard_v10"
    artifact_dir = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
    
    deliverables = [
        "01_dataset_provenance_audit.md",
        "02_raw_to_merged_data_verification.md",
        "03_statistical_claims_audit.md",
        "04_corrected_h1_h5_classifications.json",
        "05_transaction_cost_convention_audit.md",
        "06_independent_portfolio_reconciliation.json",
        "07_policy_freeze_chronology_audit.md",
        "08_scientific_evidence_classification.json",
        "09_dashboard_v10_desktop.png",
        "10_dashboard_v10_tablet.png",
        "11_dashboard_v10_mobile.png",
        "12_dashboard_v10_acceptance_evidence.json",
        "13_browser_console_zero_errors.json",
        "14_automated_test_results.json",
        "15_full_regression_results.json",
        "16_staging_deployment_evidence.json",
        "17_production_zero_touch_evidence.json",
        "19_final_sprint32_acceptance_report.md",
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
            "byte_size": size
        }
        print(f"Hashed {filename}: {sha[:16]}... ({size:,} bytes)")
        
    manifest = {
        "sprint_id": "CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_deliverables": len(files_dict) + 1,  # including 18 manifest itself
        "files": files_dict
    }
    
    manifest_path = delivery_dir / "18_sha256_delivery_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    if artifact_dir.exists():
        shutil.copy2(manifest_path, artifact_dir / "18_sha256_delivery_manifest.json")
        for filename in deliverables:
            src = delivery_dir / filename
            if src.exists():
                shutil.copy2(src, artifact_dir / filename)
                
    print("Successfully generated and synchronized 18_sha256_delivery_manifest.json!")

if __name__ == "__main__":
    main()
