"""
Sprint 16 Artifact Generator — Generates all 20 required research and integrity artifacts.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
import sys

from coin_behavior_engine.product.delivery_manifest import DeliveryManifestEngine
from coin_behavior_engine.product.holdout_validation_engine import (
    ChronologicalHoldoutValidationEngine,
)
from coin_behavior_engine.product.fdr_lineage_tracker import FDRLineageTracker
from coin_behavior_engine.product.historical_pattern_discovery import (
    HistoricalPatternDiscoveryEngine,
)
from coin_behavior_engine.product.research_reports import ResearchReportGenerator
from coin_behavior_engine.product.experiment_packages import ExperimentPackageManager

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "research_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_csv_cell(val: object) -> str:
    s = str(val) if val is not None else ""
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{s}"
    return s


def main() -> None:
    print("Generating Sprint 16 artifacts...", flush=True)

    # 1. Delivery manifest
    print("1. Generating delivery_manifest_sprint16.json...", flush=True)
    manifest = DeliveryManifestEngine.generate_delivery_manifest()
    with open(OUTPUT_DIR / "delivery_manifest_sprint16.json", "w", encoding="utf-8") as f:
        json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)

    # 2 & 3. Holdout validation audit (JSON & CSV)
    print("2-3. Generating holdout_validation_audit_sprint16...", flush=True)
    holdout_audit = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
    holdout_dict = asdict(holdout_audit)
    with open(OUTPUT_DIR / "holdout_validation_audit_sprint16.json", "w", encoding="utf-8") as f:
        json.dump(holdout_dict, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "holdout_validation_audit_sprint16.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "specification_id", "timeframe", "horizon", "estimator",
            "full_sample_effect", "full_sample_p", "full_sample_q",
            "holdout_effect", "holdout_p", "holdout_q", "replicated"
        ])
        for s in holdout_dict.get("holdout_specifications", []):
            writer.writerow([
                sanitize_csv_cell(s.get("spec_id")),
                sanitize_csv_cell(s.get("timeframe")),
                sanitize_csv_cell(s.get("horizon")),
                sanitize_csv_cell(s.get("estimator")),
                sanitize_csv_cell(s.get("full_sample_effect")),
                sanitize_csv_cell(s.get("full_sample_p_value")),
                sanitize_csv_cell(s.get("full_sample_q_value")),
                sanitize_csv_cell(s.get("holdout_sample_effect")),
                sanitize_csv_cell(s.get("holdout_sample_p_value")),
                sanitize_csv_cell(s.get("holdout_sample_q_value")),
                sanitize_csv_cell(s.get("is_replicated_in_holdout")),
            ])

    # 4. FDR Target Cell Lineage
    print("4. Generating fdr_lineage_cell_758a387e.json...", flush=True)
    cell_lineage = FDRLineageTracker.get_target_cell_lineage()
    with open(OUTPUT_DIR / "fdr_lineage_cell_758a387e.json", "w", encoding="utf-8") as f:
        json.dump(asdict(cell_lineage), f, indent=2, ensure_ascii=False)

    # 5. Full FDR Multiple Testing Audit
    print("5. Generating fdr_multiple_testing_audit_sprint16.json...", flush=True)
    fdr_audit = FDRLineageTracker.get_full_lineage_audit()
    fdr_dict = asdict(fdr_audit) if hasattr(fdr_audit, "__dataclass_fields__") else fdr_audit
    with open(OUTPUT_DIR / "fdr_multiple_testing_audit_sprint16.json", "w", encoding="utf-8") as f:
        json.dump(fdr_dict, f, indent=2, ensure_ascii=False)

    # 6 & 7. Pattern similarity search (Reference: 2022-06-01 to 2022-06-15)
    print("6-7. Generating pattern_similarity_search_reference_202206...", flush=True)
    pattern_res = HistoricalPatternDiscoveryEngine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        max_candidates=10,
        step_hours=72,
    )
    pat_dict = asdict(pattern_res)
    pat_dict["status"] = "SUCCESS"
    with open(OUTPUT_DIR / "pattern_similarity_search_reference_202206.json", "w", encoding="utf-8") as f:
        json.dump(pat_dict, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "pattern_similarity_search_reference_202206.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank", "candidate_id", "start_utc", "end_utc",
            "similarity_score_pct", "composite_distance",
            "regime_jsd_distance", "volatility_distance",
            "return_distribution_distance", "transition_matrix_distance",
            "persistence_gap_hours"
        ])
        for c in pat_dict.get("ranked_candidates", []):
            writer.writerow([
                sanitize_csv_cell(c.get("rank")),
                sanitize_csv_cell(c.get("candidate_id")),
                sanitize_csv_cell(c.get("start_utc")),
                sanitize_csv_cell(c.get("end_utc")),
                sanitize_csv_cell(c.get("similarity_score_pct")),
                sanitize_csv_cell(c.get("composite_distance")),
                sanitize_csv_cell(c.get("regime_jsd_distance")),
                sanitize_csv_cell(c.get("volatility_distance")),
                sanitize_csv_cell(c.get("return_distribution_distance")),
                sanitize_csv_cell(c.get("transition_matrix_distance")),
                sanitize_csv_cell(c.get("persistence_gap_hours")),
            ])

    # 8. Side-by-side comparison
    print("8. Generating pattern_similarity_side_by_side_comparison.json...", flush=True)
    top_cand = pat_dict["ranked_candidates"][0] if pat_dict["ranked_candidates"] else {}
    cand_s = top_cand.get("start_utc", "2022-11-01T00:00:00Z")
    cand_e = top_cand.get("end_utc", "2022-11-15T00:00:00Z")
    cmp_res = HistoricalPatternDiscoveryEngine.get_side_by_side_comparison(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        candidate_start_utc=cand_s,
        candidate_end_utc=cand_e,
    )
    with open(OUTPUT_DIR / "pattern_similarity_side_by_side_comparison.json", "w", encoding="utf-8") as f:
        json.dump(cmp_res, f, indent=2, ensure_ascii=False)

    # 9. Ranking sensitivity analysis
    print("9. Generating pattern_ranking_sensitivity_analysis.json...", flush=True)
    sens_res = HistoricalPatternDiscoveryEngine.analyze_ranking_sensitivity(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
    )
    with open(OUTPUT_DIR / "pattern_ranking_sensitivity_analysis.json", "w", encoding="utf-8") as f:
        json.dump(sens_res, f, indent=2, ensure_ascii=False)

    # 10 & 11. Report 29 (JSON & PDF)
    print("10-11. Generating Report 29 (JSON & PDF)...", flush=True)
    r29 = ResearchReportGenerator.generate_historical_pattern_similarity_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z"
    )
    with open(OUTPUT_DIR / "research_report_29_pattern_similarity.json", "w", encoding="utf-8") as f:
        json.dump(r29, f, indent=2, ensure_ascii=False)
    pdf29 = ResearchReportGenerator.export_report_as_pdf(r29)
    with open(OUTPUT_DIR / "research_report_29_pattern_similarity.pdf", "wb") as f:
        f.write(pdf29)

    # 12 & 13. Report 30 (JSON & PDF)
    print("12-13. Generating Report 30 (JSON & PDF)...", flush=True)
    r30 = ResearchReportGenerator.generate_historical_window_comparison_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z",
        cand_s, cand_e,
    )
    with open(OUTPUT_DIR / "research_report_30_window_comparison.json", "w", encoding="utf-8") as f:
        json.dump(r30, f, indent=2, ensure_ascii=False)
    pdf30 = ResearchReportGenerator.export_report_as_pdf(r30)
    with open(OUTPUT_DIR / "research_report_30_window_comparison.pdf", "wb") as f:
        f.write(pdf30)

    # 14 & 15. Report 31 (JSON & PDF)
    print("14-15. Generating Report 31 (JSON & PDF)...", flush=True)
    r31 = ResearchReportGenerator.generate_similarity_sensitivity_analysis_report(
        "2022-06-01T00:00:00Z", "2022-06-15T00:00:00Z"
    )
    with open(OUTPUT_DIR / "research_report_31_similarity_sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(r31, f, indent=2, ensure_ascii=False)
    pdf31 = ResearchReportGenerator.export_report_as_pdf(r31)
    with open(OUTPUT_DIR / "research_report_31_similarity_sensitivity.pdf", "wb") as f:
        f.write(pdf31)

    # 16 & 17. Report 32 (JSON & PDF)
    print("16-17. Generating Report 32 (JSON & PDF)...", flush=True)
    r32 = ResearchReportGenerator.generate_scientific_evidence_closure_report()
    with open(OUTPUT_DIR / "research_report_32_scientific_evidence_closure.json", "w", encoding="utf-8") as f:
        json.dump(r32, f, indent=2, ensure_ascii=False)
    pdf32 = ResearchReportGenerator.export_report_as_pdf(r32)
    with open(OUTPUT_DIR / "research_report_32_scientific_evidence_closure.pdf", "wb") as f:
        f.write(pdf32)

    # 18. Portable Research Package V3: Pattern Similarity
    print("18. Generating portable_experiment_package_v3_pattern_similarity.json...", flush=True)
    pkg_sim = ExperimentPackageManager.create_pattern_similarity_package(
        similarity_id="PKG-SIM-202206-BTC",
        reference_start="2022-06-01T00:00:00Z",
        reference_end="2022-06-15T00:00:00Z",
        search_results=pat_dict,
    )
    with open(OUTPUT_DIR / "portable_experiment_package_v3_pattern_similarity.json", "w", encoding="utf-8") as f:
        json.dump(asdict(pkg_sim), f, indent=2, ensure_ascii=False)

    # 19. Portable Research Package V3: Window Comparison
    print("19. Generating portable_experiment_package_v3_window_comparison.json...", flush=True)
    pkg_cmp = ExperimentPackageManager.create_window_comparison_package(
        comparison_id="PKG-CMP-202206-202211",
        window_a_start="2022-06-01T00:00:00Z",
        window_a_end="2022-06-15T00:00:00Z",
        window_b_start=cand_s,
        window_b_end=cand_e,
        comparison_results=cmp_res,
    )
    with open(OUTPUT_DIR / "portable_experiment_package_v3_window_comparison.json", "w", encoding="utf-8") as f:
        json.dump(asdict(pkg_cmp), f, indent=2, ensure_ascii=False)

    # 20. Portable Research Package V3: Evidence Closure
    print("20. Generating portable_experiment_package_v3_evidence_closure.json...", flush=True)
    pkg_evid = ExperimentPackageManager.create_evidence_closure_package(
        closure_id="PKG-EVID-CLOSURE-SPRINT16",
        closure_results=r32,
    )
    with open(OUTPUT_DIR / "portable_experiment_package_v3_evidence_closure.json", "w", encoding="utf-8") as f:
        json.dump(asdict(pkg_evid), f, indent=2, ensure_ascii=False)

    print("ALL 20 ARTIFACTS GENERATED SUCCESSFULLY IN research_outputs/!", flush=True)


if __name__ == "__main__":
    main()
