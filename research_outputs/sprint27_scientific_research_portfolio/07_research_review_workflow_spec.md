# 07 — Research Review & Decision Workflow Specification (Module 27.6)

- **File:** `src/coin_behavior_engine/product/research_review_workflow.py`
- **Primary Class:** `ResearchReviewWorkflowEngine`

## Review States, Decisions & Security Controls
- **States:** `UNREVIEWED`, `EVIDENCE_CHECK_PENDING`, `EVIDENCE_CHECK_COMPLETED`, `STATISTICAL_REVIEW_COMPLETED`, `REPRODUCIBILITY_REVIEW_COMPLETED`, `INDEPENDENT_VALIDATION_REQUIRED`, `REVIEW_COMPLETED`, `ARCHIVED`, `BLOCKED`.
- **Decisions:** `ACCEPT_AS_EXPLORATORY_FINDING`, `ACCEPT_AS_REPRODUCED_FINDING`, `REQUIRE_ADDITIONAL_EVIDENCE`, `REQUIRE_INDEPENDENT_VALIDATION`, `REJECT_UNSUPPORTED_CLAIM`, `MARK_INCONCLUSIVE`, `BLOCK_DUE_TO_PROVENANCE_FAILURE`, `ARCHIVE_HISTORICAL_RECORD`.
- Requires server-verified operator session or token (`UNAUTHENTICATED_REVIEW_SUBMISSION_BLOCKED`), rejects client-supplied `is_admin`/`role` (`CLIENT_SUPPLIED_ROLE_ESCALATION_BLOCKED`), and maintains a SHA-256 hash-chained review audit log (`verify_review_audit_chain()`).
