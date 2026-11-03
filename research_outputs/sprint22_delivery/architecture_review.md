# CBE Sprint 22 Architecture Review
## Research Intelligence Reporting & Evidence Presentation V1

**Sprint ID:** `CBE_PRODUCT_ACCELERATION_22`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Branch:** `main`  
**Verified Sprint 21 Closure Commit:** `3b06ca3ee578b36675e9ad6260f37e6b2f057af8`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY FROZEN, 0 parameter mutations)  
**Execution Environment:** Local development & Authorized Staging (`srv1114257`)  
**Production Isolation:** STRICT ZERO-TOUCH (`1a867269c843` untouched)  

---

## 1. Executive Mission & Scope

Coin Behavior Engine has assembled a rich, retrospective research ecosystem across Sprints 17–21:
- Historical Market Intelligence Explorer & Unified Research Workspace V1
- Historical Pattern Discovery V2 & Comparison Studio V2
- Research Library V2 with atomic persistence and SHA-256 integrity
- Unified Research Workflow with guided stages (Steps 1–6)
- Research Quality Assurance Engine (`research_reproducibility.py`)
- Independent Evidence Verifier (`research_evidence_verifier.py`)
- Scientific Integrity Audit & Quality Scorecard (`research_scientific_audit.py`)
- Performance Regression Observatory (`research_performance_audit.py`)

Sprint 22 bridges the gap between active analytical exploration and formal, auditable scientific reporting. It establishes an end-to-end reporting architecture enabling researchers and audit stakeholders to synthesize multi-module historical research sessions into authoritative, deterministic, tamper-verifiable research reports with offline-capable HTML and publication-quality PDF exports.

Crucially, the reporting layer remains **strictly descriptive and retrospective**:
- Zero predictive trading functionality
- Zero real-time data collection
- Zero automated trade execution
- Zero parameter mutations to canonical model `CBE-0.7.0`
- Zero external LLM / cloud generation dependencies (deterministic templates only)

---

## 2. Audit of Existing Research Modules & Reusable Services

| Module / Component | File | Reusable Assets & Capabilities |
| :--- | :--- | :--- |
| **Unified Research Workspace** | `unified_research_workspace.py` | 5-module research execution engine (candles, regime clustering, volatility estimation, macro events, statistical holdouts). Provides canonical session dictionary structure. |
| **Historical Pattern Discovery V2** | `historical_pattern_discovery.py`, `research_intelligence_explorer.py` | 5-dimensional similarity scoring (dtw, return, volatility, regime, volume) with explainable dimension breakdown. |
| **Comparison Studio V2** | `research_intelligence_explorer.py` | Normalized base-100 price paths, cross-period regime comparison, volatility divergence. |
| **Research Library V2** | `research_intelligence_explorer.py` | Atomic JSON storage with `.library.lock`, sanitized IDs (`RLIB-[a-f0-9]{12}`), definition replay, and provenance checking. |
| **Research Workflow V1** | `research_workflow.py` | Shared workflow state, stage progression, evidence package encapsulation. |
| **Research Reproducibility Engine V1** | `research_reproducibility.py` | Dual-replay evaluation, strict numerical tolerances (`1e-5`, `1e-4`, `1e-6`), RFC 8259 finiteness validation, full 40-char commit provenance. |
| **Evidence Verifier** | `research_evidence_verifier.py` | Deterministic SHA-256 package checksum verification, holdout criteria enforcement (`HOLD_2 / CONF_0`). |
| **Scientific Audit & Scorecard** | `research_scientific_audit.py` | 6-dimension scorecard (`dataset_integrity`, `canonical_model_integrity`, `reproducibility`, `evidence_completeness`, `historical_comparison_integrity`, `scientific_disclosure_completeness`). |
| **Performance Observatory** | `research_performance_audit.py` | On-demand latency benchmarks (8 operations) with strict production execution gating (`403 Forbidden`). |
| **Dashboard API & UI** | `dashboard_api.py`, `research_explorer_ui.py` | REST API endpoints, token authentication, 6-step visual stepper navigation. |

---

## 3. Sprint 22 Architectural Design & New Modules

```
                    ┌────────────────────────────────────────────────────────┐
                    │            Unified Research Workflow / Library          │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                    Research Report Builder Engine (research_report_builder.py)             │
│   Schema: CBE-RESEARCH-REPORT-1.0.0 | Deterministic ID: RPT-<canonical-hash>              │
│   States: READY, GENERATING, COMPLETED, PARTIAL, BLOCKED, FAILED                           │
├────────────────────────────────────────────────┬───────────────────────────────────────────┤
│                                                │                                           │
│  ┌──────────────────────────────────────────┐  │  ┌──────────────────────────────────────┐ │
│  │ Scientific Narrative Engine              │  │  │ Historical Comparison Reporting      │ │
│  │ (research_narratives.py)                 │  │  │ (research_comparison_reporting.py)   │ │
│  │ - Deterministic Turkish explanations     │  │  │ - 8 Comparison Dimensions            │ │
│  │ - Traceable findings & limitations       │  │  │ - Normalized Base-100 Paths          │ │
│  │ - Holdout disclosures (HOLD_2 / CONF_0) │  │  │ - Actual historical metrics only      │ │
│  └──────────────────────────────────────────┘  │  └──────────────────────────────────────┘ │
└───────────────────────────┬────────────────────┴─────────────────────┬─────────────────────┘
                            │                                          │
                            ▼                                          ▼
┌────────────────────────────────────────────────┐  ┌────────────────────────────────────────┐
│ Standalone HTML Renderer                       │  │ Server-Side PDF Generator              │
│ (research_report_html.py)                      │  │ (research_report_pdf.py)               │
│ - Self-contained offline HTML5                 │  │ - Matplotlib PdfPages / Vector engine   │
│ - Responsive & print-friendly CSS              │  │ - A4 Multi-page layout, Cover page     │
│ - Zero CDN / Zero remote font dependencies     │  │ - Turkish Unicode glyph support        │
│ - Embedded SVG vector charts                   │  │ - Bounded memory & size (< 5MB)        │
└───────────────────────────┬────────────────────┘  └──────────────────┬─────────────────────┘
                            │                                          │
                            └────────────────────┬─────────────────────┘
                                                 │
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│             Verifiable Evidence Bundle & Verifier (research_report_evidence.py)            │
│   Bundle: Canonical Report JSON + Config + Provenance + Scorecard + Sealed SHA-256         │
│   Verification: Tampering detection, schema validation, independent hash check             │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Report Builder Engine (`src/coin_behavior_engine/product/research_report_builder.py`)
- **Schema:** `CBE-RESEARCH-REPORT-1.0.0`
- **Canonical Structure (15 Sections):**
  1. `report_metadata` (ID, version, generated_at_utc, state, hash)
  2. `executive_summary` (Turkish narrative, scope, key observations)
  3. `historical_scope` (asset, start_utc, end_utc, interval, bars_count)
  4. `canonical_model_identity` (CBE-0.7.0, frozen status, 0 mutations)
  5. `regime_analysis` (dominant regime, distribution, transition stability)
  6. `volatility_analysis` (Parkinson estimate, realized range, relative baseline)
  7. `historical_pattern_discovery` (matched candidates, similarity score, 5D breakdown)
  8. `historical_comparison` (reference vs candidate comparison metrics)
  9. `macro_context` (verified temporal events, non-causal overlay)
  10. `statistical_evidence` (holdout disclosures, p-values, sample bounds)
  11. `research_quality_scorecard` (6 dimensions pass/fail status, strict gate)
  12. `reproducibility_verification` (dual-run match, numerical tolerances, verdict)
  13. `evidence_provenance` (dataset manifest, source commit SHA, package checksum)
  14. `scientific_limitations` (mandatory disclaimers, exploratory bounds)
  15. `technical_verification_metadata` (host, environment, security posture)
- **Deterministic Identifier:** `RPT-<sha256(canonical_inputs)[:16]>`. Contains no volatile timestamps to ensure identical research configurations yield deterministic report IDs.
- **State Machine:**
  - `READY`: Initialized with verified inputs.
  - `GENERATING`: Synthesis in progress.
  - `COMPLETED`: All mandatory sections compiled and validated.
  - `PARTIAL`: Optional modules unavailable (explicitly marked).
  - `BLOCKED`: Mandatory scientific provenance missing (certification blocked).
  - `FAILED`: Validation error or corrupted input.

### 3.2 Scientific Narrative Engine (`src/coin_behavior_engine/product/research_narratives.py`)
- Deterministic, template-driven Turkish text generation. Zero external generative AI or cloud endpoints; 100% offline-capable.
- Strict traceability: Every generated observation links back to an explicit numeric field, module source, and dataset version.
- Epistemological boundary preservation: strictly enforces that holdout satisfaction (`PREDECLARED_HOLDOUT_CRITERIA_SATISFIED = 2`) is never conflated with independent confirmatory replication (`INDEPENDENT_CONFIRMATORY_REPLICATIONS = 0`).

### 3.3 Historical Comparison Reporting (`src/coin_behavior_engine/product/research_comparison_reporting.py`)
- Synthesizes comparative data across reference and candidate historical episodes.
- Evaluates 8 distinct dimensions: date range, base-100 normalized price trajectory, regime distribution, Parkinson volatility, 5D similarity breakdown, macro-event context, statistical evidence, and quality verification.
- Descriptive comparative metrics only; zero forward-looking directional bias.

### 3.4 Standalone HTML Report Exporter (`src/coin_behavior_engine/product/research_report_html.py`)
- Generates fully self-contained HTML5 documents.
- Print-friendly CSS media queries (`@media print`).
- Zero remote fonts (standard system font stacks: Inter, -apple-system, Segoe UI, Roboto, sans-serif).
- Zero remote scripts, CDN links, or tracking tags.
- Charts embedded as inline SVG vector graphics or Base64 data URIs.
- Complete Turkish Unicode support (UTF-8 encoding).

### 3.5 Server-Side PDF Report Generator (`src/coin_behavior_engine/product/research_report_pdf.py`)
- Utilizes `matplotlib.backends.backend_pdf.PdfPages` and vector figure composition (pre-installed, tested, zero extra heavy dependencies).
- Professional multi-page A4 portrait document:
  - Page 1: Formal Cover Page & Executive Summary
  - Page 2: Historical Regime & Volatility Analysis (with visual distribution bar)
  - Page 3: Historical Pattern Discovery & Normalized Comparison (with normalized price trajectory chart)
  - Page 4: Scientific Integrity Scorecard & Reproducibility Verification
  - Page 5: Verifiable Evidence Provenance & Scientific Limitations
- Formatted headers, footers, page numbering ("Sayfa X / Y"), and timestamp/SHA references.
- Bounded document size (< 5MB) and strict memory isolation.

### 3.6 Verifiable Research Report Bundle (`src/coin_behavior_engine/product/research_report_evidence.py`)
- Bundles canonical report JSON, research configuration, dataset provenance, scorecard, and reproducibility manifest into a verifiable evidence package.
- Computes deterministic SHA-256 package checksum across canonical JSON representation.
- Provides independent bundle verification: detects modified timestamps, tampered regimes, altered disclosures, or model mismatches.

### 3.7 Research Library Report Association
- Extends `ResearchLibraryEngine` in `research_intelligence_explorer.py`:
  - `save_report_for_definition(research_id, report_data)`
  - `get_reports_for_definition(research_id)`
  - `get_report_by_id(report_id)`
  - `verify_report_integrity(report_id)`
- Atomic persistence with `.library.lock` and path sanitization (`RPT-[a-f0-9]{12,16}`).

### 3.8 Dashboard API & UI Integration
- **API Routes (`dashboard_api.py`):**
  - `GET  /api/v1/product/research-reports/capabilities`
  - `POST /api/v1/product/research-reports/generate`
  - `GET  /api/v1/product/research-reports/{report_id}`
  - `GET  /api/v1/product/research-reports/{report_id}/html`
  - `GET  /api/v1/product/research-reports/{report_id}/pdf`
  - `GET  /api/v1/product/research-reports/{report_id}/evidence`
  - `POST /api/v1/product/research-reports/verify`
- **UI Stepper Navigation (`research_explorer_ui.py`):**
  - Adds **Step 7 — Araştırma Raporu ve Kanıtlar** (`#step-node-7`).
  - Interactive report overview, narrative viewer, comparative chart, quality scorecard, evidence checksums, and export triggers for HTML, PDF, and Evidence Bundle.

---

## 4. Security, Concurrency & Resource Controls

1. **Authentication & Authorization:** All report generation, verification, and file download endpoints require valid `X-Operator-Token` in protected environments, utilizing constant-time comparison via `hmac.compare_digest()`.
2. **Path Traversal Defense:** Report IDs are strictly validated against `^RPT-[a-f0-9]{12,16}$`. Arbitrary filesystem navigation is rejected with `400 Bad Request`.
3. **Content-Disposition & Sanitization:** Exported files use safe alphanumeric filenames and RFC 6266 headers (`Content-Disposition: attachment; filename="report-RPT-xxxx.html"`). HTML rendering escapes user-supplied titles.
4. **Concurrency & Memory Throttling:** Report and PDF generation are bounded by semaphores (max 2 concurrent server-side PDF renders) to protect the shared staging/production host from memory spikes.
5. **Production Gating:** No mutation or report generation operations can run against the production database or container (`TECHNICAL_NO_GO`, zero-touch enforced).

---

## 5. Staging & Production Strategy

- **Staging Deployment:** Built as immutable container `cbe-market-intelligence:sprint22-<commit>` on `srv1114257` (`168.231.125.238`), bound to loopback `127.0.0.1:18080->8000`.
- **Production Container `1a867269c843`:** 100% untouched and monitored throughout the sprint.
- **Model Invariant:** `CBE-0.7.0` remains strictly frozen (0 parameter mutations).
