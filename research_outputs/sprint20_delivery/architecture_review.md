# Research Workflow V1 & Product Architecture Review

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_20`  
**Architecture Layer:** Lightweight Research Orchestrator & State Machine  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS)

---

### 1. Unified Research Journey State Machine

The research platform coordinates previously developed standalone modules into a single, cohesive workflow without recalculating or duplicating scientific logic:

```text
       INITIAL (Page Loaded / Form Blank)
          |
          v
    PERIOD_SELECTED (Start/End Range, Interval, Asset Validated)
          |
          v
     SESSION_READY (Unified Research Session Configured)
          |
          v
   ANALYSIS_COMPLETED (5-Module URS Executed & Stored)
          |
          +-------------------------------+
          |                               |
          v                               v
   PATTERNS_REVIEWED (Top Analogs)  RESEARCH_SAVED
          |                               |
          v                               v
   COMPARISON_READY (Dual-Period)   EVIDENCE_EXPORTED
```

### 2. Shared Research Context Contract

All modules (Historical Explorer, URS, Pattern Discovery V2, Comparison Studio V2, Research Library V2, Evidence Export) operate against a single synchronized context schema:

```json
{
  "schema_version": "1.0.0",
  "workflow_id": "RWF-11695566f1eebf18",
  "stage": "ANALYSIS_COMPLETED",
  "asset": "BTCUSDT",
  "interval": "1h",
  "reference_start_utc": "2022-06-01T00:00:00Z",
  "reference_end_utc": "2022-06-15T00:00:00Z",
  "selected_modules": [
    "regime_analysis",
    "volatility_analysis",
    "historical_pattern_discovery",
    "macro_comparison",
    "statistical_evidence"
  ],
  "research_session_id": "URS-a01124326dc3",
  "pattern_experiment_id": "EXP-PAT-V2-...",
  "comparison_reference": null,
  "research_library_id": "RLIB-3bcb63181a12",
  "dataset_manifest_sha256": "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97",
  "canonical_model_version": "CBE-0.7.0",
  "research_only": true,
  "context_version": 2
}
```

### 3. Stale-Result Invalidation Invariant

When the researcher modifies the date range (`reference_start_utc` or `reference_end_utc`), the backend automatically invalidates dependent `research_session_id`, `pattern_experiment_id`, and `comparison_reference` objects, setting stage back to `PERIOD_SELECTED`. The frontend surfaces an immediate warning banner preventing the display of stale data under new period headings.
