# 02 — Scientific Research Portfolio Manager Specification (Module 27.1)

- **File:** `src/coin_behavior_engine/product/research_portfolio_manager.py`
- **Primary Class:** `ScientificResearchPortfolioManager`

## Required 24 Portfolio Record Fields
Every item returned by `query_portfolio()` includes all 24 required fields:
`research_id`, `research_title`, `research_category`, `research_objective`, `hypothesis_id`, `methodology_id`, `dataset_id`, `dataset_version`, `dataset_provenance_status`, `observation_period_start`, `observation_period_end`, `created_at`, `updated_at`, `research_status`, `scientific_readiness_status`, `statistical_validation_status`, `reproducibility_status`, `independence_status`, `evidence_integrity_status`, `governance_status`, `related_experiments`, `related_artifacts`, `open_evidence_gaps_count`, and `review_status`.

## Portfolio Integrity Guarantees
- Portfolio summary KPIs (`total_registered_records`, `records_with_verified_evidence`, `records_blocked_by_provenance`, `records_with_statistical_validation`, `records_with_reproducibility_evidence`, `records_with_independent_validation`, `records_with_open_evidence_gaps`) are computed dynamically from the actual portfolio records.
- Missing metadata fields remain `None`/`UNAVAILABLE` rather than fabricated.
- `register_custom_portfolio_entry()` blocks any attempt to promote an unsigned or unverified dataset to `VERIFIED` (`UNSIGNED_DATASET_PROMOTION_BLOCKED`).
