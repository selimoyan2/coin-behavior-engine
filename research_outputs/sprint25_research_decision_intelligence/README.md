# COIN BEHAVIOR ENGINE — SPRINT 25
## Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform
**Sprint ID:** `CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE`  
**Model Status:** `CBE-0.7.0 — STRICTLY_FROZEN`  
**Governance Decision:** `TECHNICAL_NO_GO`  
**Execution Mode:** `STRICTLY_OFFLINE_RESEARCH`  
**Production Status:** `STRICT ZERO-TOUCH (Container 19004adaea21 Untouched)`  
**Staging Status:** `DEPLOYED & VERIFIED (Container 90534f6b12fe on srv1114257:18080)`  

---

### Executive Overview
Sprint 25 delivers a comprehensive scientific decision-support platform on top of the Research Intelligence Workspace V2. The engine does NOT generate trading signals, authorize live execution, or alter the canonical mathematical parameters of CBE-0.7.0. Instead, it systematically answers:
1. Which scientific findings are grounded in authentic, cryptographically verified evidence?
2. Which findings lack verification or contain critical data/methodological gaps?
3. Which research procedures can be locally reproduced deterministically, and what are their exact non-replication caveats?
4. What are the prioritized research tasks to resolve unverified claims without trading bias?

### Core Modules Delivered
1. **Module 25.1 — Scientific Evidence Graph (`evidence_graph.py`):**
   - 11 node types (`CATALOG_RECORD`, `SOURCE_DATASET`, `OBSERVATION_DATA`, `EVIDENCE_BUNDLE`, `ATTESTATION_RECORD`, `METRIC_SPEC`, `METHODOLOGY_DOC`, `VERIFICATION_RUN`, `REPRODUCIBILITY_LOG`, `GOVERNANCE_GATE`, `GAP_INDICATOR`).
   - 10 edge types with strict cycle safety and bounded traversal depth.
   - Proactive missing link detection flagging ungrounded claims.
2. **Module 25.2 — Scientific Readiness Scorecard (`scientific_readiness.py`):**
   - 10 evaluated dimensions (Dataset Provenance, Source Artifact Integrity, Observation Completeness, Methodology Compatibility, Sample Sufficiency, Statistical Validity, Reproducibility, Independent Replication, Evidence Freshness, Governance Compliance).
   - 6 critical fail-closed gates (`is_ready_for_review=False` if any critical gate fails).
   - Heuristic readiness index with prominent scientific disclaimer.
3. **Module 25.3 — Evidence Gap Analyzer (`evidence_gap_analyzer.py`):**
   - 14 gap categories spanning missing attestations, unverified hash integrity, missing methodology specs, and quarantined datasets.
   - Severity grading: `CRITICAL` (P0), `HIGH` (P1), `MEDIUM` (P2), `LOW` (P3).
   - Concrete, deterministic scientific remedies for every gap.
4. **Module 25.4 — Scientific Reproducibility Lab (`reproducibility_lab.py`):**
   - 5 allowlisted offline computational procedures (`PROC_PARKINSON_VOLATILITY`, `PROC_FUNDING_RATE_SUMMARY`, `PROC_REGIME_STABILITY_EVAL`, `PROC_DTW_PATTERN_DISTANCE`, `PROC_STORAGE_VERIFICATION`).
   - Dual-hash provenance recording reference and reproduced outputs with numerical tolerance checks.
   - **Strict Non-Replication Invariant:** Local re-execution is explicitly flagged with `is_independent_replication=False` and prominent governance disclaimers.
5. **Module 25.5 — Research Priority Engine (`research_priority_engine.py`):**
   - Deterministic ranking insulated from market PnL or trading expectations.
   - Ranks research tasks based on gap severity, readiness score, and scientific blocking status.
6. **Module 25.6 — Research Decision Reports (`research_decision_reports.py`):**
   - 13 comprehensive sections providing complete governance, readiness, gap, and evidence lineage summaries in both structured JSON and publication-ready HTML.
7. **Module 25.7 — Research Intelligence Dashboard V3 (UI & API):**
   - 5 interactive views integrated into `/product#research-explorer`: Evidence Graph, Scientific Readiness, Evidence Gaps, Reproducibility Lab, Research Priorities.
   - REST API endpoints fully wired under `/api/v1/product/workspace/*`.
