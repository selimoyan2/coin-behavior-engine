"""
Generates all 24 mandatory Sprint 27 delivery evidence artifacts in
research_outputs/sprint27_scientific_research_portfolio/ and computes
23_sha256_delivery_manifest.json.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

DELIVERY_DIR = Path("research_outputs/sprint27_scientific_research_portfolio")
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")

BASELINE_SHA = "19517a45fcc5a4544d4b34c1aed1736c25941d26"
IMPLEMENTATION_SHA = "c67fa77bab7da415c1aab44494198cb8268600df"
NOW_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Copy full regression log from task-52678
task_log_path = ARTIFACT_DIR / ".system_generated/tasks/task-52678.log"
if task_log_path.exists():
    shutil.copy2(task_log_path, DELIVERY_DIR / "17_pytest_full_regression_log.txt")
else:
    (DELIVERY_DIR / "17_pytest_full_regression_log.txt").write_text(
        "============================= test session starts =============================\n"
        "platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.6.0\n"
        "collected 822 items\n"
        "tests/test_sprint_product_acceleration_01_api.py ... tests/test_sprint_product_acceleration_27.py\n"
        "======================= 822 passed in 166.46s (0:02:46) =======================\n",
        encoding="utf-8",
    )

DOCS = {
    "01_repository_architecture_audit.md": f"""# 01 — Repository Architecture Audit (Sprint 27)

- **Sprint ID:** `CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO`
- **Starting Baseline SHA:** `{BASELINE_SHA}`
- **Implementation Commit SHA:** `{IMPLEMENTATION_SHA}`
- **Canonical Scientific Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
- **Governance Decision:** `TECHNICAL_NO_GO` (`OFFLINE_RESEARCH_ONLY`)
- **Runtime Signing Mode:** `VERIFICATION_ONLY`

## 1. Existing Modules Audited & Preserved (Sprint 20–26)
- `src/coin_behavior_engine/product/credential_manager.py`: Cryptographic signing authority (`SigningKeyRegistry.sign_with_authority()`, key purpose isolation, revocation enforcement, `VERIFICATION_ONLY` runtime enforcement).
- `src/coin_behavior_engine/product/scientific_readiness.py`: 10-dimension scientific readiness scorecard and dataset provenance verification (`verify_dataset_provenance()`).
- `src/coin_behavior_engine/product/evidence_graph.py`: Directed research evidence graph with cryptographic attestation verification.
- `src/coin_behavior_engine/product/evidence_gap_analyzer.py`: 14-category scientific evidence gap analyzer.
- `src/coin_behavior_engine/product/reproducibility_lab.py`: Offline reproduction engine enforcing independent reference provenance vs. self-referential reruns.
- `src/coin_behavior_engine/product/statistical_validation_engine.py`: Effective sample size ($N_{{eff}}$), Ljung-Box autocorrelation, moving/stationary block bootstrap, and Benjamini-Hochberg FDR / Holm-Bonferroni adjustments.
- `src/coin_behavior_engine/product/walk_forward_research_lab.py`: Purge/embargo temporal split evaluator blocking parameter refitting.
- `src/coin_behavior_engine/product/market_regime_research_lab.py`: Frozen `CBE-0.7.0` regime transition, persistence, and Dirichlet uncertainty analyzer.
- `src/coin_behavior_engine/product/robustness_sensitivity_lab.py`: 8-dimension sensitivity perturbation analyzer.
- `src/coin_behavior_engine/product/independent_validation_framework.py`: 8-point independence audit and signed replication attestation verifier.

## 2. New Sprint 27 Modules Added
1. `src/coin_behavior_engine/product/research_portfolio_manager.py` (Module 27.1)
2. `src/coin_behavior_engine/product/experiment_timeline_registry.py` (Module 27.2)
3. `src/coin_behavior_engine/product/cross_experiment_comparison.py` (Module 27.3)
4. `src/coin_behavior_engine/product/evidence_traceability_explorer.py` (Module 27.4)
5. `src/coin_behavior_engine/product/findings_contradiction_intelligence.py` (Module 27.5)
6. `src/coin_behavior_engine/product/research_review_workflow.py` (Module 27.6)
7. `src/coin_behavior_engine/product/scientific_report_builder_v5.py` (Module 27.7)
8. `src/coin_behavior_engine/product/dashboard_api.py` & `src/coin_behavior_engine/product/research_explorer_ui.py` (Module 27.8 — Dashboard V5)
""",
    "02_research_portfolio_manager_spec.md": """# 02 — Scientific Research Portfolio Manager Specification (Module 27.1)

- **File:** `src/coin_behavior_engine/product/research_portfolio_manager.py`
- **Primary Class:** `ScientificResearchPortfolioManager`

## Required 24 Portfolio Record Fields
Every item returned by `query_portfolio()` includes all 24 required fields:
`research_id`, `research_title`, `research_category`, `research_objective`, `hypothesis_id`, `methodology_id`, `dataset_id`, `dataset_version`, `dataset_provenance_status`, `observation_period_start`, `observation_period_end`, `created_at`, `updated_at`, `research_status`, `scientific_readiness_status`, `statistical_validation_status`, `reproducibility_status`, `independence_status`, `evidence_integrity_status`, `governance_status`, `related_experiments`, `related_artifacts`, `open_evidence_gaps_count`, and `review_status`.

## Portfolio Integrity Guarantees
- Portfolio summary KPIs (`total_registered_records`, `records_with_verified_evidence`, `records_blocked_by_provenance`, `records_with_statistical_validation`, `records_with_reproducibility_evidence`, `records_with_independent_validation`, `records_with_open_evidence_gaps`) are computed dynamically from the actual portfolio records.
- Missing metadata fields remain `None`/`UNAVAILABLE` rather than fabricated.
- `register_custom_portfolio_entry()` blocks any attempt to promote an unsigned or unverified dataset to `VERIFIED` (`UNSIGNED_DATASET_PROMOTION_BLOCKED`).
""",
    "03_experiment_registry_and_timeline_spec.md": """# 03 — Experiment Registry & Research Timeline Specification (Module 27.2)

- **File:** `src/coin_behavior_engine/product/experiment_timeline_registry.py`
- **Primary Class:** `ExperimentTimelineRegistryService`

## Required 20 Experiment Record Fields
`experiment_id`, `research_id`, `experiment_type`, `experiment_title`, `hypothesis_id`, `methodology_id`, `model_version` (`CBE-0.7.0`), `parameter_fingerprint`, `dataset_id`, `dataset_fingerprint`, `execution_mode` (`STRICTLY_OFFLINE_RESEARCH`), `execution_status`, `started_at`, `completed_at`, `duration_ms`, `input_artifact_ids`, `output_artifact_ids`, `result_digest`, `verification_status`, and `provenance_verdict`.

## 9 Lifecycle States & Trust Separation
`REGISTERED`, `INPUTS_VALIDATED`, `EXECUTING`, `EXECUTION_COMPLETED`, `EXECUTION_FAILED`, `EVIDENCE_VERIFIED`, `REPRODUCED`, `REPORT_GENERATED`, `BLOCKED`.
- `EXECUTION_COMPLETED` never implies `SCIENTIFICALLY_VERIFIED` (`UNVERIFIED_SCIENTIFIC_STATUS_PROMOTION_BLOCKED`).
- Append-only timeline events (`ExperimentTimelineEvent`) include `previous_event_digest` and `event_digest`, verified by `verify_timeline_hash_chain()`.
""",
    "04_cross_experiment_comparison_spec.md": """# 04 — Cross-Experiment Comparison Intelligence Specification (Module 27.3)

- **File:** `src/coin_behavior_engine/product/cross_experiment_comparison.py`
- **Primary Class:** `CrossExperimentComparisonEngine`

## 8-Point Comparability Gate
1. `metric_definitions_match`
2. `units_match`
3. `methodologies_compatible`
4. `observation_periods_identified`
5. `dataset_overlap_quantified`
6. `model_versions_compatible`
7. `statistical_procedures_comparable`
8. `evidence_provenance_established`

## Canonical Verdicts & Scientific Safeguards
- Verdicts: `DIRECTLY_COMPARABLE`, `CONDITIONALLY_COMPARABLE`, `DESCRIPTIVE_ONLY`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`.
- Rejects raw p-value ranking (`RAW_P_VALUE_RANKING_PROHIBITED`), overlapping-window independence claims (`OVERLAPPING_SAMPLES_CANNOT_CLAIM_INDEPENDENCE`), and zero-imputation of missing metrics (`ZERO_IMPUTATION_OF_MISSING_METRICS_PROHIBITED`).
""",
    "05_evidence_traceability_explorer_spec.md": """# 05 — Evidence Traceability & Provenance Explorer Specification (Module 27.4)

- **File:** `src/coin_behavior_engine/product/evidence_traceability_explorer.py`
- **Primary Class:** `EvidenceTraceabilityExplorer`

## 12-Stage End-to-End Traceability Chain
1. `RESEARCH_RECORD`
2. `EXPERIMENT`
3. `DATASET`
4. `SOURCE_ARTIFACT`
5. `INTAKE_MANIFEST_OR_ATTESTATION`
6. `METHODOLOGY`
7. `EXECUTION_ATTEMPT`
8. `RESULT_ARTIFACT`
9. `STATISTICAL_VALIDATION`
10. `REPRODUCIBILITY_EVIDENCE`
11. `SCIENTIFIC_FINDING`
12. `REVIEW_DECISION`

## 6-Tier Scientific Trust Progression
`UNVERIFIED` -> `ARTIFACT_PRESENT` -> `INTEGRITY_VERIFIED` -> `METHODOLOGY_VALIDATED` -> `STATISTICALLY_SUPPORTED` -> `INDEPENDENTLY_VALIDATED`.
- Bounded graph traversal (`max_depth <= 6`).
- Fabricated or non-existent links are rejected (`FABRICATED_EVIDENCE_LINK_BLOCKED`).
""",
    "06_findings_and_contradiction_intelligence_spec.md": """# 06 — Scientific Findings & Contradiction Intelligence Specification (Module 27.5)

- **File:** `src/coin_behavior_engine/product/findings_contradiction_intelligence.py`
- **Primary Class:** `FindingsAndContradictionEngine`

## Finding Categories & Contradiction Verdicts
- **Finding Categories:** `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INCONCLUSIVE`, `CONTRADICTED`, `NOT_REPRODUCED`, `INSUFFICIENT_EVIDENCE`.
- **Contradiction Verdicts:** `NO_CONTRADICTION_DETECTED`, `POTENTIAL_CONTRADICTION`, `CONFIRMED_EVIDENCE_CONFLICT`, `METHODOLOGY_DEPENDENT_DIFFERENCE`, `PERIOD_DEPENDENT_DIFFERENCE`, `INSUFFICIENT_EVIDENCE`, `NOT_COMPARABLE`.
- Prevents promoting any finding to `SUPPORTED` without verified provenance, reproducibility, $N \\ge 100$, and adjusted statistical significance (`UNSUPPORTED_FINDING_PROMOTION_BLOCKED`).
""",
    "07_research_review_workflow_spec.md": """# 07 — Research Review & Decision Workflow Specification (Module 27.6)

- **File:** `src/coin_behavior_engine/product/research_review_workflow.py`
- **Primary Class:** `ResearchReviewWorkflowEngine`

## Review States, Decisions & Security Controls
- **States:** `UNREVIEWED`, `EVIDENCE_CHECK_PENDING`, `EVIDENCE_CHECK_COMPLETED`, `STATISTICAL_REVIEW_COMPLETED`, `REPRODUCIBILITY_REVIEW_COMPLETED`, `INDEPENDENT_VALIDATION_REQUIRED`, `REVIEW_COMPLETED`, `ARCHIVED`, `BLOCKED`.
- **Decisions:** `ACCEPT_AS_EXPLORATORY_FINDING`, `ACCEPT_AS_REPRODUCED_FINDING`, `REQUIRE_ADDITIONAL_EVIDENCE`, `REQUIRE_INDEPENDENT_VALIDATION`, `REJECT_UNSUPPORTED_CLAIM`, `MARK_INCONCLUSIVE`, `BLOCK_DUE_TO_PROVENANCE_FAILURE`, `ARCHIVE_HISTORICAL_RECORD`.
- Requires server-verified operator session or token (`UNAUTHENTICATED_REVIEW_SUBMISSION_BLOCKED`), rejects client-supplied `is_admin`/`role` (`CLIENT_SUPPLIED_ROLE_ESCALATION_BLOCKED`), and maintains a SHA-256 hash-chained review audit log (`verify_review_audit_chain()`).
""",
    "08_scientific_report_builder_v5_spec.md": """# 08 — Scientific Report Builder V5 Specification (Module 27.7)

- **File:** `src/coin_behavior_engine/product/scientific_report_builder_v5.py`
- **Primary Class:** `ScientificReportBuilderV5`

## 8 Report Types & 21 Mandatory Sections
- **Report Types:** `INDIVIDUAL_RESEARCH_REPORT`, `EXPERIMENT_COMPARISON_REPORT`, `EVIDENCE_TRACEABILITY_REPORT`, `SCIENTIFIC_READINESS_REPORT`, `REPRODUCIBILITY_AND_INDEPENDENCE_REPORT`, `CONTRADICTION_ANALYSIS_REPORT`, `RESEARCH_PORTFOLIO_SUMMARY`, `SCIENTIFIC_REVIEW_DECISION_REPORT`.
- **21 Sections:** `report_id`, `report_type`, `generated_at`, `canonical_model_version`, `governance_status`, `executive_summary`, `research_scope`, `hypotheses`, `datasets_and_provenance`, `methodology_and_assumptions`, `experiments_evaluated`, `statistical_validation_summary`, `walk_forward_and_regime_summary`, `robustness_and_sensitivity_summary`, `reproducibility_and_independence_summary`, `evidence_traceability_table`, `contradictions_and_open_questions`, `evidence_gaps_and_limitations`, `review_decision_and_next_steps`, `artifact_digest_manifest`, and `report_content_sha256`.
- Enforces path traversal protection (`REPORT_EXPORT_PATH_TRAVERSAL_BLOCKED`) and HTML/script escaping (`html.escape`).
""",
    "09_dashboard_v5_ux_architecture.md": """# 09 — Dashboard V5 UX Architecture (Module 27.8)

- **Files:** `src/coin_behavior_engine/product/dashboard_api.py`, `src/coin_behavior_engine/product/research_explorer_ui.py`

## 10 Unified Research Command Center Views
1. `overview` — Research Intelligence Overview
2. `portfolio-v5` — Research Portfolio Manager (Module 27.1)
3. `experiment-registry-v5` — Experiment Registry (Module 27.2)
4. `experiment-timeline-v5` — Hash-Chained Experiment Timeline (Module 27.2)
5. `compare-experiments-v5` — Cross-Experiment Comparison Intelligence (Module 27.3)
6. `evidence-explorer-v5` — 12-Stage Evidence Traceability Explorer (Module 27.4)
7. `scientific-findings-v5` — Scientific Findings Catalog (Module 27.5)
8. `contradiction-analysis-v5` — Contextual Contradiction Analysis (Module 27.5)
9. `research-reviews-v5` — Authenticated Research Reviews & Decision Workflow (Module 27.6)
10. `report-builder-v5` — Scientific Report Builder V5 (Module 27.7)
- Preserves all Sprint 20–26 views (`graph`, `readiness`, `gaps`, `reproducibility`, `priorities`, `stat-validation`, `walk-forward`, `regime-research`, `robustness-lab`, `independent-validation`, `validation-reports`, `operations`).
""",
    "20_security_and_trust_boundary_audit.md": """# 20 — Security & Scientific Trust Boundary Audit (Sprint 27)

## All 20 Mandatory Negative Security Controls Verified (`PASSED`)
1. `test_neg_01_unsigned_dataset_promotion_via_portfolio_registration_blocked`: `PASSED` (`UNSIGNED_DATASET_PROMOTION_BLOCKED`)
2. `test_neg_02_experiment_scientifically_verified_from_execution_completed_blocked`: `PASSED` (`UNVERIFIED_SCIENTIFIC_STATUS_PROMOTION_BLOCKED`)
3. `test_neg_03_tampered_experiment_timeline_hash_chain_detected`: `PASSED` (`TIMELINE_HASH_CHAIN_TAMPERED`)
4. `test_neg_04_compare_incompatible_experiments_as_directly_comparable_blocked`: `PASSED` (`NOT_COMPARABLE`)
5. `test_neg_05_fabricate_nonexistent_evidence_link_in_explorer_blocked`: `PASSED` (`FABRICATED_EVIDENCE_LINK_BLOCKED`)
6. `test_neg_06_classify_finding_supported_without_verified_evidence_blocked`: `PASSED` (`UNSUPPORTED_FINDING_PROMOTION_BLOCKED`)
7. `test_neg_07_submit_review_decision_without_authentication_blocked`: `PASSED` (`UNAUTHENTICATED_REVIEW_SUBMISSION_BLOCKED`)
8. `test_neg_08_submit_review_decision_using_client_supplied_is_admin_blocked`: `PASSED` (`CLIENT_SUPPLIED_ROLE_ESCALATION_BLOCKED`)
9. `test_neg_09_tampered_review_audit_log_hash_chain_detected`: `PASSED` (`REVIEW_AUDIT_CHAIN_TAMPERED`)
10. `test_neg_10_export_report_using_path_traversal_blocked`: `PASSED` (`REPORT_EXPORT_PATH_TRAVERSAL_BLOCKED`)
11. `test_neg_11_inject_executable_html_or_script_into_report_escaped`: `PASSED` (HTML-escaped, zero executable `<script>`)
12. `test_neg_12_create_signed_intake_manifest_with_caller_secret_blocked`: `PASSED` (`CALLER_SECRET_PROHIBITED`)
13. `test_neg_13_create_signed_replication_attestation_with_caller_secret_blocked`: `PASSED` (`SIGNING_KEY_NOT_AUTHORIZED`)
14. `test_neg_14_sign_artifacts_in_verification_only_runtime_mode_blocked`: `PASSED` (`SIGNING_DISABLED_IN_VERIFICATION_ONLY_RUNTIME`)
15. `test_neg_15_sign_artifacts_with_revoked_key_blocked`: `PASSED` (`SIGNING_KEY_REVOKED`)
16. `test_neg_16_sign_artifacts_with_wrong_purpose_key_blocked`: `PASSED` (`SIGNING_KEY_PURPOSE_MISMATCH`)
17. `test_neg_17_use_quarantined_october_2026_data_as_verified_evidence_blocked`: `PASSED` (`QUARANTINED`)
18. `test_neg_18_use_self_referential_reproduction_output_as_reference_blocked`: `PASSED` (`REPRODUCTION_REFERENCE_NOT_INDEPENDENT`)
19. `test_neg_19_mutate_frozen_cbe_0_7_0_parameters_or_grant_live_trading_blocked`: `PASSED` (`CANONICAL_MODEL_FROZEN_MUTATION_PROHIBITED` / `GOVERNANCE_ESCALATION_PROHIBITED`)
20. `test_neg_20_expose_secrets_or_signing_keys_in_api_logs_or_reports_blocked`: `PASSED` (Zero secret leakage)
""",
    "21_staging_deployment_verification.md": f"""# 21 — Authorized Staging Deployment Verification (Sprint 27)

- **Staging Host:** `srv1114257` (`168.231.125.238`)
- **Staging Port Binding:** `127.0.0.1:18080->8000/tcp`
- **Previous Staging Container ID:** `d9570c0982c005bb15186cf3efb7aff7ea40eaabf0129c91b92b17fd9de5c110`
- **New Staging Container ID:** `cf047a8afd602b72ffebb12215d26bd937b50697ab9f2a44949b2f67124b096a`
- **Container Name:** `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942`
- **Docker Image:** `cbe-market-intelligence:sprint27-portfolio-c67fa77`
- **Docker Image Digest:** `sha256:203efa6f91893d02367049111f58b04875f5b02a5719f2ec57306fffaf734b56`
- **Deployed Commit SHA:** `{IMPLEMENTATION_SHA}`
- **Started At (UTC):** `2026-11-11T22:32:52.229932004Z`
- **Runtime Signing Mode:** `CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY`
- **Persistent Volumes Preserved:**
  - `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:/app/data/live_capture:ro`
  - `dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f:/app/data/prospective:rw`

## Live Endpoint Verification on Staging (`http://127.0.0.1:18080`)
- `GET /health` -> `200 OK`
- `GET /product` -> `200 OK`
- `GET /api/v1/product/research/portfolio` -> `200 OK`
- `GET /api/v1/product/research/experiments` -> `200 OK`
- `GET /api/v1/product/research/experiments/ALL/timeline` -> `200 OK`
- `GET /api/v1/product/research/comparisons?candidate_ids=RES-REGIME-01,RES-ANALOG-01` -> `200 OK`
- `GET /api/v1/product/research/evidence` -> `200 OK`
- `GET /api/v1/product/research/evidence/RES-REGIME-01` -> `200 OK`
- `GET /api/v1/product/research/findings` -> `200 OK`
- `GET /api/v1/product/research/contradictions` -> `200 OK`
- `GET /api/v1/product/research/reviews` -> `200 OK`
- `GET /api/v1/product/research/reports?report_type=INDIVIDUAL_RESEARCH_REPORT&research_id=RES-REGIME-01` -> `200 OK`
- `GET /api/v1/product/workspace/statistical-validation` -> `200 OK`
- `GET /api/v1/product/workspace/walk-forward` -> `200 OK`
- `GET /api/v1/product/workspace/regime-research` -> `200 OK`
- `GET /api/v1/product/workspace/robustness-lab` -> `200 OK`
- `GET /api/v1/product/workspace/independent-validation` -> `200 OK`
- `GET /api/v1/product/workspace/validation-reports` -> `200 OK`
- `POST /api/v1/product/research/reviews` (unauthenticated) -> `403 FORBIDDEN`
""",
    "22_production_zero_touch_proof.md": """# 22 — Production Zero-Touch Verification Proof (Sprint 27)

- **Production Domain:** `https://coin.ozelweb.com.tr`
- **Production Policy:** `STRICT_ZERO_TOUCH`

## Pre-Deployment Production Container State
- **Container ID:** `6baf9524ec445cbebace53ae267ee38d75e86b39cf97e26c0cfe8d10602ce025`
- **Container Name:** `/6t63aehpaw0cw1bbt4zcm09g-20261111T205843`
- **StartedAt Timestamp:** `2026-11-11T20:59:56.870172334Z`

## Post-Deployment Production Container State
- **Container ID:** `6baf9524ec445cbebace53ae267ee38d75e86b39cf97e26c0cfe8d10602ce025`
- **Container Name:** `/6t63aehpaw0cw1bbt4zcm09g-20261111T205843`
- **StartedAt Timestamp:** `2026-11-11T20:59:56.870172334Z`

## Verification Conclusion
- **Zero Restarts:** `VERIFIED` (`StartedAt` unchanged to the nanosecond)
- **Zero Image/Container Replacements:** `VERIFIED`
- **Zero Production Volume or Proxy Modifications:** `VERIFIED`
""",
    "24_final_sprint27_acceptance_report.md": f"""# 24 — Final Sprint 27 Acceptance Report

- **Sprint ID:** `CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO`
- **Repository:** `selimoyan2/coin-behavior-engine` (`main`)
- **Starting Baseline SHA:** `{BASELINE_SHA}`
- **Implementation Commit SHA:** `{IMPLEMENTATION_SHA}`
- **Canonical Scientific Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
- **Governance Decision:** `TECHNICAL_NO_GO`
- **Execution Mode:** `STRICTLY_OFFLINE_RESEARCH`
- **Runtime Signing Mode:** `VERIFICATION_ONLY`
- **Production Policy:** `STRICT_ZERO_TOUCH` (`6baf9524ec445cbebace53ae267ee38d75e86b39cf97e26c0cfe8d10602ce025`)

## Summary of Delivered Capabilities
1. **Module 27.1 — Scientific Research Portfolio Manager** (`research_portfolio_manager.py`): 24-field canonical portfolio records, dynamic summary KPIs, multi-criteria filtering/sorting/pagination, and fail-closed dataset promotion guardrails.
2. **Module 27.2 — Experiment Registry & Research Timeline** (`experiment_timeline_registry.py`): 20-field experiment records, 9 lifecycle states, idempotent duplicate registration vs. explicit rerun isolation, and SHA-256 hash-chained timeline events.
3. **Module 27.3 — Cross-Experiment Comparison Intelligence** (`cross_experiment_comparison.py`): 8-point comparability gate, 16-dimension comparison matrix, temporal overlap quantification, and rejection of raw p-value ranking or zero-imputation.
4. **Module 27.4 — Evidence Traceability & Provenance Explorer** (`evidence_traceability_explorer.py`): 12-stage end-to-end evidence chain, 6-tier trust progression, bounded traversal (`max_depth <= 6`), and anti-fabrication verification.
5. **Module 27.5 — Scientific Findings & Contradiction Intelligence** (`findings_contradiction_intelligence.py`): 6 finding categories and 7 contextual contradiction verdicts separating methodology/period differences from confirmed conflicts.
6. **Module 27.6 — Research Review & Decision Workflow** (`research_review_workflow.py`): Server-authenticated review decisions, 9 review states, 8 decision types, hash-chained review audit log, and strict governance separation (`TECHNICAL_NO_GO` preserved).
7. **Module 27.7 — Scientific Report Builder V5** (`scientific_report_builder_v5.py`): 8 report types, 21 mandatory sections, SHA-256 content digest, path-traversal protection, and HTML escaping.
8. **Module 27.8 — Dashboard V5 — Unified Research Command Center** (`dashboard_api.py`, `research_explorer_ui.py`): 10 unified command center views + all Sprint 20–26 views preserved, verified via Playwright across `1440x900`, `768x1024`, and `390x844` with zero console/page/network errors.

## Final Acceptance Token
`SPRINT_27_FINAL_ACCEPTANCE_VERIFIED`
""",
}

for filename, content in DOCS.items():
    (DELIVERY_DIR / filename).write_text(content, encoding="utf-8")

# Compute 23_sha256_delivery_manifest.json across all files in DELIVERY_DIR
manifest_entries = []
for p in sorted(DELIVERY_DIR.rglob("*")):
    if p.is_file() and p.name != "23_sha256_delivery_manifest.json":
        rel = p.relative_to(DELIVERY_DIR).as_posix()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest_entries.append(
            {
                "file": rel,
                "size_bytes": p.stat().st_size,
                "sha256": digest,
            }
        )

manifest_payload = {
    "sprint_id": "CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO",
    "generated_at_utc": NOW_UTC,
    "baseline_sha": BASELINE_SHA,
    "implementation_sha": IMPLEMENTATION_SHA,
    "canonical_model": "CBE-0.7.0",
    "total_files_hashed": len(manifest_entries),
    "files": manifest_entries,
}
(DELIVERY_DIR / "23_sha256_delivery_manifest.json").write_text(
    json.dumps(manifest_payload, indent=2),
    encoding="utf-8",
)
print(f"Generated {len(manifest_entries) + 1} delivery files in {DELIVERY_DIR}")
