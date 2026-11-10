# Evidence-Backed Research Catalog Architecture
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Architectural Mission

The Evidence-Backed Research Catalog replaces static, hardcoded research metadata arrays with a verifiable, file-backed discovery engine. It guarantees that every metric, status indicator, and parameter displayed in the Research Workspace originates from an authentic, cryptographically checked on-disk artifact.

---

## 2. 5-Tier Evidence Precedence Hierarchy

When consolidating research records across multiple storage directories, `ResearchCatalogProvider` resolves conflicting definitions through a strict precedence hierarchy:

```
[Tier 1: CANONICAL_ARTIFACT]      Authoritative release reports in data/reports/ (SHA-256 verified)
            │
            ▼
[Tier 2: EVIDENCE_BUNDLE]         RFC 8785 canonical bundles in research_outputs/ (.cbe-hyp.json)
            │
            ▼
[Tier 3: SPEC_REGISTRY]           Formal Research Library definitions in data/research_library/
            │
            ▼
[Tier 4: HISTORICAL_PROVENANCE]   Unsigned historical outputs & exploratory notebooks
            │
            ▼
[Tier 5: UNVERIFIED_DESCRIPTIVE]  Fallback descriptive templates (all metrics strictly None)
```

1. **Tier 1 (CANONICAL_ARTIFACT):** Frozen historical reports produced during canonical sprint milestones (e.g., `sprint09_27`, `sprint09_38`). If an artifact exists here, its observed values override all lower tiers.
2. **Tier 2 (EVIDENCE_BUNDLE):** Structured hypothesis experiments containing RFC 8785 serialized payloads and calculated test statistics.
3. **Tier 3 (SPEC_REGISTRY):** Persistent definitions saved by research operators via the Research Library.
4. **Tier 4 (HISTORICAL_PROVENANCE):** Raw exploratory artifacts with verified source files but unstandardized metadata.
5. **Tier 5 (UNVERIFIED_DESCRIPTIVE):** Descriptive-only specifications. All empirical fields are set to `None`.

---

## 3. Separation of Metadata Domains

`ResearchRecord` enforces a strict 4-way separation of concerns to prevent descriptive configurations from being mistaken for empirical observations:

```python
@dataclass
class ResearchRecord:
    # 1. Descriptive Metadata (What was configured)
    id: str
    title: str
    title_en: str
    category: str
    dataset_id: str
    historical_period: str
    window_cadence: str
    specification_id: str
    parameters: Dict[str, Any]

    # 2. Observed Scientific Results (What was empirically measured)
    sample_size: Optional[int]
    volatility_ratio: Optional[float]
    holdout_fdr_q: Optional[float]
    raw_p_value: Optional[float]
    direction_match: Optional[bool]
    key_findings_tr: str
    methodological_limitations: str
    observed_metrics: Dict[str, Any]

    # 3. Verification & Provenance Metadata (How trust is established)
    source_artifact: str
    source_artifact_sha256: str
    evidence_bundle_id: Optional[str]
    signature_verification_status: str
    verification_timestamp_utc: str
    canonicalization_scheme: str
    source_precedence_tier: str

    # 4. Governance & Invariants (Policy compliance)
    scientific_eligibility: str          # ELIGIBLE | INELIGIBLE
    quarantine_status: str               # CLEAR | QUARANTINED
    record_status: str                   # VERIFIED | UNVERIFIED | QUARANTINED
    model_version: str                   # CBE-0.7.0 (STRICTLY_FROZEN)
    trading_prohibition: str             # LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED
```

---

## 4. Performance & Caching Strategy

* **In-Memory Cache with TTL:** `ResearchCatalogProvider` caches the loaded catalog for **30 seconds** (`_CACHE_TTL_SECONDS = 30.0`). Keystroke searches or rapid tab navigation do not trigger disk I/O or SHA-256 recomputations.
* **Bounded Pagination:** Query results are bounded by `limit` (max 50) and `page` parameters, preventing memory bloat on large libraries.
* **Multi-Attribute Sorting:** Sorting supports Parkinson volatility, sample size, creation timestamp, and title with null-safe handling (records with `None` values sort safely to the end).
