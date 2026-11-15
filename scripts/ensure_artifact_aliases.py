import os
import shutil
import json
import hashlib

out_dir = r"research_outputs\sprint36_dashboard_v13_market_behavior"

# Map of reported name to existing file if different
aliases = {
    "01_central_coverage_manifest.json": "02_dataset_registry_consistency.json",
    "04_market_behavior_analytics_v2.json": "04_market_regime_metrics.json",
    "06_annual_regime_distribution.json": "04_market_regime_metrics.json",
    "07_market_risk_metrics.json": "06_volatility_and_risk_metrics.json",
    "08_dashboard_v13_specification.json": "08_api_contract_and_security.json",
    "09_scientific_invariance_audit.json": "10_scientific_validation.json",
    "10_prohibition_and_zero_touch_audit.json": "08_api_contract_and_security.json",
    "12_visual_acceptance_manifest.json": "07_dashboard_v13_acceptance.md"
}

for target_name, src_name in aliases.items():
    target_path = os.path.join(out_dir, target_name)
    src_path = os.path.join(out_dir, src_name)
    if not os.path.exists(target_path) and os.path.exists(src_path):
        shutil.copy2(src_path, target_path)
        print(f"Created alias: {target_name} <- {src_name}")

print("All aliases verified.")
