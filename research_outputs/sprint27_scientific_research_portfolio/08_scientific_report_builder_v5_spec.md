# 08 — Scientific Report Builder V5 Specification (Module 27.7)

- **File:** `src/coin_behavior_engine/product/scientific_report_builder_v5.py`
- **Primary Class:** `ScientificReportBuilderV5`

## 8 Report Types & 21 Mandatory Sections
- **Report Types:** `INDIVIDUAL_RESEARCH_REPORT`, `EXPERIMENT_COMPARISON_REPORT`, `EVIDENCE_TRACEABILITY_REPORT`, `SCIENTIFIC_READINESS_REPORT`, `REPRODUCIBILITY_AND_INDEPENDENCE_REPORT`, `CONTRADICTION_ANALYSIS_REPORT`, `RESEARCH_PORTFOLIO_SUMMARY`, `SCIENTIFIC_REVIEW_DECISION_REPORT`.
- **21 Sections:** `report_id`, `report_type`, `generated_at`, `canonical_model_version`, `governance_status`, `executive_summary`, `research_scope`, `hypotheses`, `datasets_and_provenance`, `methodology_and_assumptions`, `experiments_evaluated`, `statistical_validation_summary`, `walk_forward_and_regime_summary`, `robustness_and_sensitivity_summary`, `reproducibility_and_independence_summary`, `evidence_traceability_table`, `contradictions_and_open_questions`, `evidence_gaps_and_limitations`, `review_decision_and_next_steps`, `artifact_digest_manifest`, and `report_content_sha256`.
- Enforces path traversal protection (`REPORT_EXPORT_PATH_TRAVERSAL_BLOCKED`) and HTML/script escaping (`html.escape`).
