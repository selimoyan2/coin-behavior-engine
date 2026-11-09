# Implemented Feature Matrix — Research Intelligence Workspace V2
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Implementation Commit:** `061a9e72386542ca895b01b3da75b4cc9d0e734f`

---

## 1. Feature Implementation Matrix

| Component | Feature | Specification | Implementation File | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Workspace Navigation** | 7 First-Class Views | Overview, Catalog, Comparison Lab, Visualization, Evidence Center, Library V2, Operations | `research_explorer_ui.py`, `dashboard_api.py` | VERIFIED (Playwright Scenario 1-8) |
| **Workspace Overview** | KPI Cards & Activity Feed | Research count, candidate breakdown, top regime, verification score | `research_intelligence_workspace.py`, `dashboard_api.py` | VERIFIED (Playwright Scenario 9) |
| **Research Catalog** | Multi-attribute Filtering | Search text, type filter, status filter, regime filter | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 10-14) |
| **Research Catalog** | Multi-column Sorting | Sort by ID, title, score, sharpe, created_at (asc/desc) | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 13) |
| **Research Catalog** | Pagination | Page 1, Page 2, page_size controls with total count | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 14) |
| **Research Catalog** | Quick Candidate Selection | Quick-add to Comparison Lab from Catalog Drawer | `research_explorer_ui.py` | VERIFIED (Playwright Scenario 15) |
| **Comparison Lab** | 2-4 Candidate Selection | Restrict comparison set to 2, 3, or 4 candidates; reject 1 or >4 | `research_intelligence_workspace.py`, `research_explorer_ui.py` | VERIFIED (Playwright Scenario 16, 23) |
| **Comparison Lab** | Scientific Compatibility Gate | Family compatibility, regime overlap, sample size, status rules | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 17, 24) |
| **Comparison Lab** | Cross-Candidate Matrix | Side-by-side metrics: Sharpe, Drawdown, Sample Size, p-value | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 18, 21) |
| **Comparison Lab** | Difference Analysis | Pairwise metric delta calculations with baseline | `research_intelligence_workspace.py` | VERIFIED (Playwright Scenario 22) |
| **Comparison Lab** | Comparison Persistence | Save comparison state, title, and notes to persistent volume | `research_intelligence_workspace.py` (`/app/data/prospective/saved_comparisons`) | VERIFIED (Playwright Scenario 25) |
| **Visualization Studio** | Metric Charting | Cumulative return, regime distribution, drawdown curves | `research_explorer_ui.py` | VERIFIED (Playwright Scenario 26-28) |
| **Visualization Studio** | Interactive Controls | SVG/Canvas zoom, pan, tooltip inspection, multi-series | `research_explorer_ui.py` | VERIFIED (Playwright Scenario 29-30) |
| **Evidence Center** | 4-Pillar Verification | Reproducibility, Evidence Bundle, Governance, Durability | `research_explorer_ui.py`, `dashboard_api.py` | VERIFIED (Playwright Scenario 31-33) |
| **Evidence Center** | Cryptographic Signatures | Ed25519 signature status and RFC 8785 canonical hash display | `research_report_evidence.py`, `dashboard_api.py` | VERIFIED (Playwright Scenario 32) |
| **Report Builder** | Interactive Export | Instant PDF / HTML generation with canonical report structure | `dashboard_api.py`, `web/server.py` | VERIFIED (Playwright Scenario 36-37) |
| **Research Library V2** | Catalog Integration | Deep link to research artifacts, run IDs, and metadata | `research_library_v2.py`, `research_explorer_ui.py` | VERIFIED (Playwright Scenario 34-35) |
| **Global Search** | Omnibar Navigation | Fast prefix & keyword indexing across all research entities | `dashboard_api.py`, `research_explorer_ui.py` | VERIFIED (Playwright Scenario 38-40) |
| **Operations Panel** | Resource Governance | CPU, memory, thread pool, storage health, persistent volume | `research_explorer_ui.py`, `storage_durability.py` | VERIFIED (Playwright Scenario 41-42) |
| **Responsive UX** | Desktop / Tablet / Mobile | Fluid layout, collapsible drawer, responsive data tables | CSS Grid, Flexbox, Media Queries | VERIFIED (Playwright Scenario 43-45) |

---

## 2. Invariant Adherence

- **Model Invariants:** Canonical Scientific Model `CBE-0.7.0` — STRICTLY FROZEN. Parameter mutations: 0.
- **Trading Invariants:** `TECHNICAL_NO_GO` maintained. Live order execution permanently disabled (`CBE_TRADING_DISABLED=true`).
- **Storage Durability Invariants:** Persistent volume verified via strict container identity binding (`/app/data/prospective`).
- **Release Invariants:** Two-commit release pipeline strictly followed.
