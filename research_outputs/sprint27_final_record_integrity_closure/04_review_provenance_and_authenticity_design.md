# 04 — Review Provenance & Authenticity Design (`P0-2`)

- **Primary Module:** `src/coin_behavior_engine/product/research_review_workflow.py`
- **Implementation Commit SHA:** `6dd263fab00d6362d7196abf5112d847d84789b2`

## Strict Separation of Automated Assessments vs. Authenticated Review Decisions

1. **System-Generated Assessments (`SYSTEM_GENERATED_ASSESSMENT`):**
   - `record_origin = "AUTOMATED_ASSESSMENT"`
   - `review_classification = "AUTOMATED_ASSESSMENT"`
   - `reviewer_identity = "SYSTEM_GENERATED_ASSESSMENT"`
   - `authoritative = False`
   - `governance_effect = "NONE_NON_AUTHORITATIVE_AUTOMATED_ASSESSMENT"`
   - Never attributed to `CBE_SCIENTIFIC_REVIEW_BOARD` or `CBE_DATA_GOVERNANCE_COUNCIL` and never grants `REVIEW_COMPLETED`.

2. **Authenticated Review Decisions (`AUTHENTICATED_REVIEW_DECISION`):**
   - Requires server-verified operator token (`_verify_reviewer_authentication`).
   - Rejects client boolean flags (`is_admin`, `authorized`, `reviewer_override`, `grant_live_trading`, `remove_technical_no_go`).
   - Rejects forged or synthetic timestamps (`FORGED_REVIEW_TIMESTAMP_REJECTED`).
   - Requires non-empty verifiable `supporting_evidence_ids` (`UNVERIFIED_EVIDENCE_REFERENCE_REJECTED`).
