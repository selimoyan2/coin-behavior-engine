# CBE Sprint 11.15.1 Shadow Decision Schema Consistency Audit

**Sprint:** CBE — 11.15.1  
**Mission:** Prospective Protocol Hardening & Independent Readiness Audit  
**Audit Target:** Schema Compliance, Serialization Rigor & Regime Vocabulary  
**Audit Date:** 2026-10-18T22:15:00+03:00  
**Schema Path:** `research_outputs/shadow_decision_schema.json`  
**Base Commit:** `09773621f7026ac2630fb7674cd11aadaf934a70`  

---

## 1. Executive Summary & Defect Remediation Register

This audit evaluated the formal Draft-07 JSON Schema against decision records emitted by the CBE research pipeline across JSONL and CSV serialization formats.

### Forensic Finding Summary:
All 8 investigation targets have been audited. Two critical defects were identified in the Sprint 11.15 delivery and repaired:
1. **Regime Vocabulary Mismatch:** Emitted records contained `MEAN_REVERTING` and `LOW_VOLATILITY_COMPRESSION`, which caused schema validation failure because `shadow_decision_schema.json` permitted only 5 regimes. The schema enum has been expanded to all 10 canonical market regimes with documented semantic mappings.
2. **CSV Nested Object Serialization Defect:** In `prospective_shadow_decisions.csv`, nested objects (`forecast_probabilities` and `evidence_rationale`) were serialized via Python's default `str(dict)` representation (using single quotes `'` and Python booleans `True`/`False`), producing malformed JSON. Repaired by implementing `to_csv_dict()` with explicit `json.dumps()` serialization.

---

## 2. Investigation of the 8 Schema Targets

### Target 1: Market Regime Vocabulary & Normalization
- **Defect Identified:** Sprint 11.15's `shadow_decision_schema.json` permitted only:
  `["TRENDING_BULL", "TRENDING_BEAR", "SIDEWAYS", "HIGH_VOLATILITY", "UNCERTAIN"]`.
  However, the underlying market regime classifier produces `MEAN_REVERTING` and `LOW_VOLATILITY_COMPRESSION`.
- **Policy Invariant:** Per sprint mission, the engine must *never silently relabel market regimes*.
- **Remediation:** `shadow_decision_schema.json` now includes all 10 regimes defined in `MarketRegimeType`:
  ```json
  "enum": [
    "TRENDING_BULL",
    "TRENDING_BEAR",
    "SIDEWAYS",
    "HIGH_VOLATILITY",
    "POSSIBLE_REVERSAL",
    "UNCERTAIN",
    "MEAN_REVERTING",
    "LOW_VOLATILITY_COMPRESSION",
    "HIGH_VOLATILITY_EXPANSION",
    "CASCADE_LIQUIDATION"
  ]
  ```
- **Documented Semantic Mapping:**
  - `MEAN_REVERTING`: Range-bound mean-reversion with stationary oscillatory properties.
  - `LOW_VOLATILITY_COMPRESSION`: Severe ATR volatility squeeze prior to breakout.
  - `HIGH_VOLATILITY_EXPANSION`: Rapid volatility surge beyond normal ATR thresholds.
  - `CASCADE_LIQUIDATION`: Extreme adverse liquidation cascade.
  - `POSSIBLE_REVERSAL`: Exhaustion signal with counter-trend structural divergence.
  - `SIDEWAYS`: Baseline stationary consolidation.
  - `TRENDING_BULL` / `TRENDING_BEAR`: Directional momentum above/below 24h & 72h SMAs.
  - `UNCERTAIN`: Data latency exceeded or unclassified boundary condition.

### Target 2: Nested Object Serialization Across JSONL and CSV
- **Defect Identified:** When pandas converted `ShadowDecisionRecord` dicts into CSV rows, `str(dict)` produced `"{'p_up': 0.55, ...}"`. Standard JSON parsers (`json.loads()`) failed with `JSONDecodeError: Expecting property name enclosed in double quotes`.
- **Remediation:** Added `ShadowDecisionRecord.to_csv_dict()`:
  ```python
  def to_csv_dict(self) -> Dict[str, Any]:
      d = asdict(self)
      d["forecast_probabilities"] = json.dumps(self.forecast_probabilities, sort_keys=True, separators=(",", ":"))
      d["evidence_rationale"] = json.dumps(self.evidence_rationale, sort_keys=True, separators=(",", ":"))
      return d
  ```
  Both JSONL and CSV formats now guarantee valid JSON strings.

### Target 3: Probability Normalization
- **Requirement:** $p_{\text{up}} + p_{\text{down}} + p_{\text{flat}} = 1.0$ within numerical tolerance $\epsilon = 10^{-4}$.
- **Remediation:** Constructor and hash computation enforce:
  $$\left|\left(p_{\text{up}} + p_{\text{down}} + p_{\text{flat}}\right) - 1.0\right| \le 10^{-4}$$
  Violations raise `ValueError("Probabilities do not sum to 1.0")`. Floating-point artifacts (e.g., `0.19999999999999996`) are rounded to 6 decimal places.

### Target 4: Temporal Monotonicity & Causal Event Ordering
- **Requirement:** Observation timestamp $t_{\text{obs}}$ and data availability timestamp $t_{\text{avail}}$ must satisfy:
  $$t_{\text{avail}} \ge t_{\text{obs}}$$
- **Remediation:** Evaluator computes $\Delta t = t_{\text{avail}} - t_{\text{obs}}$. If $\Delta t < 0$, raises `ValueError("Lookahead violation: data available before observation")`.

### Target 5: Portfolio Equity Conservation
- **Invariant:** At every step:
  $$\text{hypothetical\_total\_equity\_usdt} = \text{usdt\_balance} + \left(\text{btc\_balance} \times \text{btc\_spot\_reference\_price}\right)$$
  When a position closes:
  $$\text{Ending Equity} = \text{Starting Capital} + \text{Gross Realized PnL} - \text{Total Friction}$$
  Conservation holds strictly to $\pm 0.01\text{ USDT}$.

### Target 6: Policy and Commit Identifiers
- Every record explicitly carries `policy_id`, `policy_version`, and `code_commit_hash`.
- Replaced hardcoded historical commit with the authoritative base commit `09773621f7026ac2630fb7674cd11aadaf934a70`.

### Target 7: Required vs Optional Fields
- Schema enforces 19 required fields in `shadow_decision_schema.json`.
- Optional fields (`hypothetical_target_price`, `hypothetical_stop_price`) are explicitly permitted to be `["number", "null"]`.

### Target 8: Schema Compatibility Across JSONL and CSV Exports
- Comprehensive round-trip tests confirm that records exported to JSONL and CSV can be deserialized and verified against the canonical JSON schema with zero validation errors.
