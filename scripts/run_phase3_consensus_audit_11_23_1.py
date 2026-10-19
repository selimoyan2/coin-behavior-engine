#!/usr/bin/env python3
"""
Sprint 11.23.1 Phase 3: Pre-Release Consensus Vintage Audit
Forensically audits the 216 pre-release consensus claims from Sprint 11.23,
enforcing strict evidence provenance rules and eliminating retrospective survey leakage.
"""

import json
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT_DIR / "research_outputs"

def main():
    print("=" * 80)
    print("SPRINT 11.23.1 PHASE 3: PRE-RELEASE CONSENSUS VINTAGE AUDIT")
    print("=" * 80)

    p_canon = OUTPUTS_DIR / "canonical_event_verification_11_23_1.parquet"
    if not p_canon.exists():
        p_canon = ROOT_DIR / "canonical_event_verification_11_23_1.parquet"
    df = pd.read_parquet(p_canon)

    audit_records = []
    claimed_consensus_count = 0
    verified_consensus_count = 0
    unverified_consensus_count = 0

    category_summary = {}

    for idx, row in df.iterrows():
        eid = row["event_id"]
        cat = row["event_category"]
        name = row["event_name"]
        t_pub = row["official_published_at_utc"]
        claimed_consensus = row["consensus_forecast_value"]
        actual_val = row["actual_value"]
        unit = row["release_vintage"]

        if cat not in category_summary:
            category_summary[cat] = {
                "total_events": 0,
                "claimed_consensus_count": 0,
                "verified_consensus_count": 0,
                "unverified_consensus_count": 0
            }
        category_summary[cat]["total_events"] += 1

        if pd.notna(claimed_consensus):
            claimed_consensus_count += 1
            category_summary[cat]["claimed_consensus_count"] += 1

            # Forensic verification check:
            # Does the repository contain physical contemporaneous survey wire documentation from Bloomberg/Reuters
            # stamped prior to t_pub? No. The numbers in Sprint 11.23 were transcribed from retrospective calendars.
            is_vintage_verified = False
            verified_val = None # Strictly set to NULL for causal signal purposes
            consensus_status = "CONSENSUS_UNVERIFIED"
            quarantine_reason = "CONTEMPORANEOUS_PRE_RELEASE_SURVEY_WIRE_BYTES_NOT_ARCHIVED"
            unverified_consensus_count += 1
            category_summary[cat]["unverified_consensus_count"] += 1
        else:
            is_vintage_verified = False
            verified_val = None
            consensus_status = "NO_CONSENSUS_APPLICABLE"
            quarantine_reason = None

        audit_records.append({
            "event_id": eid,
            "event_category": cat,
            "event_name": name,
            "official_published_at_utc": t_pub,
            "actual_value": actual_val,
            "claimed_consensus_value": claimed_consensus if pd.notna(claimed_consensus) else None,
            "claimed_consensus_source": "Bloomberg/Reuters Survey (Retrospective Calendar Transcription)",
            "contemporaneous_survey_wire_archived": False,
            "consensus_vintage_verified": is_vintage_verified,
            "causally_eligible_consensus_value": verified_val,
            "consensus_verification_status": consensus_status,
            "quarantine_reason": quarantine_reason
        })

    df_consensus_audit = pd.DataFrame(audit_records)

    # Save consensus_vintage_audit_11_23_1.parquet
    out_parquet = OUTPUTS_DIR / "consensus_vintage_audit_11_23_1.parquet"
    df_consensus_audit.to_parquet(out_parquet, index=False)
    print(f"Saved Consensus Vintage Audit Ledger ({len(df_consensus_audit)} rows) to {out_parquet}")
    root_parquet = ROOT_DIR / "consensus_vintage_audit_11_23_1.parquet"
    df_consensus_audit.to_parquet(root_parquet, index=False)
    print(f"Mirrored to {root_parquet}")

    summary_data = {
        "sprint": "11.23.1",
        "phase": "3_CONSENSUS_VINTAGE_AUDIT",
        "status": "PASS",
        "timestamp_utc": "2026-10-19T20:35:00Z",
        "summary_counts": {
            "total_events_audited": len(df_consensus_audit),
            "claimed_pre_release_consensus_count": claimed_consensus_count,
            "pre_release_consensus_verified": verified_consensus_count,
            "pre_release_consensus_unverified": unverified_consensus_count,
            "no_consensus_applicable_events": len(df_consensus_audit) - claimed_consensus_count
        },
        "category_breakdown": category_summary,
        "forensic_conclusions": [
            "1. PROVENANCE INTEGRITY: In Sprint 11.23, 216 pre-release consensus numbers were transcribed from retrospective economic calendar portals with attribution to 'Bloomberg/Reuters Survey'.",
            "2. EVIDENCE GAP IDENTIFIED: Contemporaneous survey wire release documents, lockup timestamps, and survey participant distributions were not captured or archived locally.",
            "3. CAUSAL ACTION: In compliance with Sprint 11.23.1 scientific integrity rules, all 216 unverified consensus figures are set to NULL for causal execution signals and marked CONSENSUS_UNVERIFIED.",
            "4. NO RETROSPECTIVE SURPRISE SIGNALS: Without proven contemporaneous pre-release survey documents, no macroeconomic announcement may be treated as a validated quantitative surprise signal."
        ]
    }

    out_json = OUTPUTS_DIR / "consensus_verification_summary_11_23_1.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved Consensus Verification Summary to {out_json}")
    root_json = ROOT_DIR / "consensus_verification_summary_11_23_1.json"
    with open(root_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Mirrored to {root_json}")

if __name__ == "__main__":
    main()
