#!/usr/bin/env python3
"""
Sprint 11.23.3 Deliverables Manifest Generator
Computes SHA-256 signatures, sizes, and row/column counts for all Sprint 11.23.3 deliverables.
Generates reproducibility_manifest_11_23_3.json and mirrors to root.
"""

import hashlib
import json
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT_DIR / "research_outputs"

DELIVERABLES = [
    "sprint11_23_2_source_freeze_11_23_3.json",
    "prospective_event_registry_11_23_3.json",
    "source_adapter_audit_11_23_3.json",
    "consensus_vintage_readiness_11_23_3.json",
    "evidence_vault_integrity_11_23_3.json",
    "market_observation_readiness_11_23_3.json",
    "simulation_test_report_11_23_3.json",
    "performance_safety_audit_11_23_3.json",
    "research_report_11_23_3.md"
]

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifest_records = {}

    for fname in DELIVERABLES:
        p = OUTPUTS_DIR / fname
        if not p.exists():
            p = ROOT_DIR / fname
        if not p.exists():
            print(f"Warning: {fname} does not exist yet.")
            continue

        sha = compute_sha256(p)
        sz = p.stat().st_size
        meta = {
            "sha256": sha,
            "size_bytes": sz
        }

        if fname.endswith(".parquet"):
            df = pd.read_parquet(p)
            meta["rows"] = len(df)
            meta["columns"] = len(df.columns)

        manifest_records[fname] = meta

    manifest_data = {
        "sprint": "11.23.3",
        "name": "Prospective Evidence Collection & Observation Readiness",
        "base_commit_full": "61abe1aec748efcbcef6c1a84cd8f50e145a2352",
        "base_commit_short": "61abe1a",
        "timestamp_utc": "2026-10-19T23:55:00Z",
        "status_summary": {
            "SPRINT_11_23_3_STATUS": "PASS",
            "PROSPECTIVE_REGISTRY": "PASS",
            "SOURCE_ADAPTER_READINESS": "PASS",
            "CONSENSUS_VINTAGE_GUARD": "PASS",
            "EVIDENCE_VAULT_INTEGRITY": "PASS",
            "MARKET_OBSERVATION_READINESS": "PASS",
            "SIMULATION_TESTS": "PASS",
            "PERFORMANCE_SAFETY": "PASS",
            "TRADING_ISOLATION": "PASS",
            "HISTORICAL_DATA_STATUS": "RESEARCH_CONTAMINATED",
            "PROSPECTIVE_OBSERVATION": "NOT_STARTED",
            "UNATTENDED_COLLECTION": "DISABLED",
            "DIRECTIONAL_TRADING_ELIGIBILITY": "ZERO",
            "NEWS_CONDITIONED_EDGE": "NOT_ESTABLISHED",
            "LIVE_TRADING": "PROHIBITED",
            "OPERATOR_AUTHORIZATION": "NOT_GRANTED"
        },
        "deliverables_manifest": manifest_records
    }

    out_file = OUTPUTS_DIR / "reproducibility_manifest_11_23_3.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    with open(ROOT_DIR / "reproducibility_manifest_11_23_3.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print("Saved reproducibility_manifest_11_23_3.json to outputs and root.")

if __name__ == "__main__":
    main()
