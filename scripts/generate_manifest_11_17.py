import json
import hashlib
from pathlib import Path
import shutil

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    root = Path(".")
    files_to_hash = [
        "research_outputs/research_report_11_17.md",
        "research_outputs/session_intelligence_verdict_11_17.json",
        "research_outputs/global_exchange_session_calendar_audit_11_17.json",
        "research_outputs/session_event_study_11_17.csv",
        "research_outputs/session_behavior_summary_11_17.csv",
        "research_outputs/session_predictive_metrics_11_17.csv",
        "research_outputs/stop_reentry_forensics_11_17.csv",
        "research_outputs/session_vs_blind_comparison_11_17.csv",
        "research_outputs/patient_session_trade_ledger_11_17.csv",
        "src/coin_behavior_engine/macro/global_session_calendar.py",
        "scripts/run_sprint11_17_session_research.py",
        "research_outputs/market_state_dataset.parquet",
    ]

    digests = {}
    for rel_path in files_to_hash:
        p = root / rel_path
        if not p.exists():
            print(f"WARNING: {rel_path} does not exist!")
            continue
        digests[p.name] = {
            "path": str(rel_path).replace("\\", "/"),
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p)
        }

    manifest = {
        "sprint": "11.17",
        "description": "Sprint 11.17 Reproducibility Manifest - Global Market Session Intelligence & Patient Spot Trading Research",
        "timestamp_utc": "2026-10-19T12:15:00Z",
        "declarations": {
            "session_intelligence": "EXPLORATORY",
            "prospective_observation": "NOT_STARTED",
            "live_trading": "PROHIBITED",
            "operator_authorization": "NOT_GRANTED",
            "next_step": "OPERATOR_REVIEW"
        },
        "verifications": {
            "scientific_classification": "SESSION_EDGE_NOT_SUPPORTED",
            "hypothesized_70_80_accuracy_refuted": True,
            "mean_directional_accuracy_pct": 51.8,
            "multiple_comparison_correction": "Holm-Bonferroni (all p_adj > 0.05)",
            "transaction_cost_model": "Canonical Execution Policy V2 (30 bps nominal roundtrip)",
            "cost_adjusted_net_ev": "Uniformly Negative (-7 to -63 bps)",
            "patient_holding_verified": True
        },
        "deliverable_digests": digests
    }

    out_file = root / "research_outputs" / "reproducibility_manifest_11_17.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {out_file}")

    root_copy = root / "reproducibility_manifest_11_17.json"
    shutil.copyfile(out_file, root_copy)
    print(f"Manifest copied to {root_copy}")

if __name__ == "__main__":
    main()
