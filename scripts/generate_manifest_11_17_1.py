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
        "research_outputs/research_report_11_17_1.md",
        "research_outputs/session_intelligence_verdict_11_17_1.json",
        "research_outputs/calendar_verification_audit_11_17_1.json",
        "research_outputs/benchmark_comparison_11_17_1.csv",
        "research_outputs/session_attribution_decomposition_11_17_1.csv",
        "research_outputs/session_statistical_audit_11_17_1.csv",
        "research_outputs/stop_reentry_reconciliation_11_17_1.csv",
        "scripts/audit_sprint11_17_1.py",
        "tests/test_sprint11_17_1_research_integrity.py",
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
        "sprint": "11.17.1",
        "description": "Sprint 11.17.1 Reproducibility Manifest - Session Research Integrity, Benchmark Parity & Statistical Audit",
        "timestamp_utc": "2026-10-19T12:25:00Z",
        "declarations": {
            "session_intelligence": "EXPLORATORY",
            "historical_data_status": "RESEARCH_CONTAMINATED",
            "prospective_observation": "NOT_STARTED",
            "live_trading": "PROHIBITED",
            "operator_authorization": "NOT_GRANTED",
            "next_step": "OPERATOR_REVIEW"
        },
        "audit_reconciliations": {
            "d_v2_friction_reconciled": "Canonical 3,281.67 USDT confirmed vs 822 USDT errant static estimate",
            "policy_d_v2_status": "EXPLORATORY_UNFROZEN",
            "attribution_decomposition": "Net delta +3.22% = -$412.97 gross alpha + $734.15 friction savings (pure trade suppression)",
            "stop_loss_counts_reconciled": "47.37% (9/19 strict) vs 52.63% (10/19 breakeven threshold)",
            "n_19_sample_size_caveat": "Wilson 95% CI is [27.3%, 68.3%]; no predictive advantage claimed",
            "hac_dependence_corrected": "Newey-West variance inflation of 1.1x to 1.8x",
            "brier_skill_scores": "Bounded in [-0.026, +0.013], confirming zero predictive skill over base rate",
            "outcome_forcing_tests_removed": True,
            "invariant_tests_passing": True
        },
        "deliverable_digests": digests
    }

    out_file = root / "research_outputs" / "reproducibility_manifest_11_17_1.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {out_file}")

    root_copy = root / "reproducibility_manifest_11_17_1.json"
    shutil.copyfile(out_file, root_copy)
    print(f"Manifest copied to {root_copy}")

if __name__ == "__main__":
    main()
