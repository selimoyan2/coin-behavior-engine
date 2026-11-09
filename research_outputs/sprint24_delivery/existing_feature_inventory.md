# COIN BEHAVIOR ENGINE — SPRINT 24
## Existing Feature Inventory & Capabilities Matrix
### Sprint ID: `CBE_PRODUCT_ACCELERATION_24`

---

## 1. Research & Analysis Features

| Component / Subsystem | Primary Implementation File | Key Endpoints / Methods | Status |
| :--- | :--- | :--- | :--- |
| **Historical Pattern Discovery V2** | `historical_pattern_discovery.py` | `/api/v1/product/pattern-discovery/*` | Active & Verified |
| **Interactive Specification Curves** | `interactive_specification_curves.py` | `/api/v1/product/specification-curves` | Active & Verified |
| **Holdout Validation Engine** | `holdout_validation_engine.py` | `/api/v1/product/holdout-validation` | Active & Verified |
| **Distribution Lab** | `distribution_lab.py` | `/api/v1/product/distribution-lab` | Active & Verified |
| **Robustness Explorer** | `robustness_explorer.py` | `/api/v1/product/robustness-matrix` | Active & Verified |
| **Scientific Comparison Policy** | `scientific_comparison_policy.py` | `ScientificComparisonPolicyCatalog` | Active & Verified |
| **Historical Series Explorer** | `research_intelligence_explorer.py` | `/api/v1/product/research-explorer/*` | Active & Verified |
| **Research Library Engine** | `research_intelligence_explorer.py` | `/api/v1/product/research-library/*` | Active & Verified |
| **Research Report Builder** | `research_report_builder.py` | `/api/v1/product/research-reports/*` | Active & Verified |
| **Evidence Bundle Verifier** | `research_report_evidence.py` | `/api/v1/product/evidence-verification` | Active & Verified |
| **Session & Auth Manager** | `session_manager.py` | `/api/v1/product/session/*` | Active & Verified |
| **Resource Governor** | `resource_governor.py` | `ResourceGovernor.governed_operation` | Active & Verified |
| **Storage Durability** | `storage_durability.py` | `/api/v1/product/storage/status` | Active & Verified |

---

## 2. Research Catalog & Datasets

- Canonical datasets available:
  - `BTCUSDT-PERP-FUNDING-2022-2026` (4,380 epochs, 8h cadence)
  - `BTCUSDT-SPOT-1H-2022-2026` (41,400 hourly bars, chronological train/test/holdout split)
  - `BTCUSDT-OCTOBER-2026-INTAKE` (quarantined synthetic audit dataset)
  - `US_CPI_EVENT_WINDOWS` & `US_FOMC_EVENT_WINDOWS` (macroeconomic event studies)
- Canonical research records:
  - `RES-FUND-01`: Funding Rate Predictability & Compute Latency
  - `RES-REGIME-01`: 2022–2026 Chronological Walk-Forward Stability
  - `RES-ANALOG-01`: Historical Dynamic Time Warping Pattern Discovery
  - `RES-MACRO-01`: CPI & FOMC Macroeconomic Volatility Shift
  - `RES-DURABILITY-01`: Storage Durability & Evidence Provenance Hardening
  - `RES-CRYPTO-01`: Cross-Asset Regime Synchronization
