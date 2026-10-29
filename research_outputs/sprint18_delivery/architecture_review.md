# Coin Behavior Engine — Sprint 18 Architecture Review
## Unified Research Workspace V1 & Multi-Module Session Orchestration

**Sprint:** `CBE_PRODUCT_ACCELERATION_18`  
**Date:** `2026-10-29T19:30:11.759671+00:00`  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)  

### 1. Architectural Strategy
Prior to Sprint 18, retrospective market analyses were distributed across distinct product modules:
- Historical Pattern Discovery V2 (`HistoricalPatternDiscoveryEngine`)
- Market Regime Analysis & Persistence (`HistoricalRegimeComparisonStudio`, `HistoricalRegimeTransitionLabEngine`)
- Volatility & Higher Moments (`HistoricalDistributionLabEngine`)
- Macro-Event Context (`MacroEventTaxonomyEngine`, `MacroEventComparisonEngine`)
- Statistical Validation (`ChronologicalHoldoutValidationEngine`, `FDRLineageTracker`)

Sprint 18 introduces the **Unified Research Session Engine** (`UnifiedResearchWorkspaceEngine`), which:
1. **Unifies Orchestration without Duplication:** Reuses existing data adapters and analytical kernels without reimplementing statistical algorithms.
2. **Deterministic Session Hashing:** Identical input tuples produce deterministic identifiers `URS-<hash>`.
3. **Stateless Execution with Bounded Caching:** Employs an in-memory cache of capacity 64 entries, achieving warm retrieval in <50ms.
4. **Module-Level Error Isolation:** If a specific analysis (e.g. macro events) encounters sparse data, it returns `"status": "UNAVAILABLE"`, allowing other modules to complete.
5. **Cross-Period Comparison Studio:** Enables side-by-side comparative analysis between Period A and Period B across JSD regime distance, annual volatility gap, return moments, and macro events.
6. **Standardized Evidence Export:** Implements the `CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0` format with SHA-256 integrity checksums.

### 2. Service Interaction Flow

```
[ Researcher UI / REST Client ]
               │
               ▼
[ ProductDashboardApiService ]
  ├─ /capabilities
  ├─ /session
  ├─ /compare
  └─ /evidence
               │
               ▼
[ UnifiedResearchWorkspaceEngine ]
  ├─ Input Validation & Quarantine Check (2026-10 Excluded)
  ├─ In-Memory Session Cache (Capacity: 64)
  │
  ├─ Module Orchestration:
  │    ├─ Candle Data Adapter (Parquet cache)
  │    ├─ Market Regime Analysis (JSD, Markov transitions)
  │    ├─ Volatility & Higher Moments (Realized, Parkinson, Skew, Kurt)
  │    ├─ Historical Pattern Discovery V2 (Disjoint, Stability)
  │    ├─ Macro-Event Taxonomy (Point-in-time canonical events)
  │    └─ Statistical Evidence (95% CI, Holdout disclosure, FDR lineage)
  │
  └─ Package Generator (CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0)
```
