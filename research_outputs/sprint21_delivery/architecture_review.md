# SPRINT 21 ARCHITECTURE & REPRODUCIBILITY AUDIT
## Baseline Verification, Reproducibility Risks, Scientific Governance & Quality Assurance Architecture

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_21`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Branch:** `main`  
**Verified Base Closure Commit:** `dae157a127c14ea9487a3833db619efbc0161a0c`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS)  
**Execution Environment:** Local development & authorized Coolify staging (`srv1114257`)  
**Production Isolation:** Container `c2d07df3c505` (`coin.ozelweb.com.tr`) — STRICT ZERO-TOUCH  

---

### 1. Architectural Baseline Inspection & Commit Ancestry

An audit of Git HEAD confirms linear ancestry from Sprint 20 final closure:
- **HEAD Commit:** `dae157a127c14ea9487a3833db619efbc0161a0c` (`chore(sprint20): finalize acceptance hardening, sha256 credentials remediation, and delivery manifest`)
- **Preceding Commit:** `57cd7cc18922080617e708cd050370dc8cb7e9f2` (`fix(sprint20): eliminate plaintext revoked credentials, enforce sha256 token fingerprints, and verify 20-gate e2e acceptance`)
- **Implementation Commit:** `33ef573ae23875442b308d68b73c479eb26ac870` (`feat(sprint20): unified research workflow v1, state machine, secret redaction, and full regression`)
- **Sprint 19 Baseline:** `ba15325642c14815d91b0a73dd7d69d2b8b503b5`

All 340 product acceleration regression tests pass with 0 failures across Python 3.11.

---

### 2. Research Engines & Data Provenance Inspection

1. **Unified Research Workspace (`unified_research_workspace.py`):**
   - Orchestrates 5 historical research engines:
     - Market regime analytics & Markov transition matrices (`historical_regime_transition_lab.py`).
     - Realized volatility, Parkinson volatility, and jump diffusion metrics (`event_regime_research.py`).
     - Historical Pattern Discovery V2 with 5D feature space (`historical_pattern_discovery.py`).
     - Macro-event contextualization & calendar alignment (`macro_comparison.py`).
     - Holdout disclosures & statistical evidence (`holdout_validation_engine.py`).
2. **Historical Data Provenance:**
   - Canonical Parquet partitions for BTCUSDT (5m, 15m, 1h, 4h, 1d) spanning 2021 to 2026.
   - Governed by `ContentIntegrityEngine` and `DatasetProvenanceEngine` generating canonical manifest SHA-256 hashes.
   - October 2026 quarantine strictly enforced across all exploratory endpoints (`OCTOBER_2026_QUARANTINE_START = "2026-10-01T00:00:00Z"`).
3. **Research Library Persistence (`research_intelligence_explorer.py`):**
   - Atomic JSON persistence via `.tmp` write and `os.replace`.
   - Two-tier concurrency synchronization (`threading.Lock` + OS file lock on `.library.lock`).
   - Token authorization (`_authorize_research_library_mutation`), CSRF rejection, and read-only production blocking.

---

### 3. Reproducibility Risks & Failure Modes Analysis

The audit identified the following potential reproducibility risks:
1. **Floating-Point Non-Determinism Across Platforms/Architectures:**
   - Vectorized dot products, norm calculations, and rolling standard deviations can exhibit minor LSB (least significant bit) discrepancies (`~1e-7` to `1e-5`) between Intel x86_64, AMD, and ARM processors or BLAS/LAPACK implementations.
   - *Mitigation:* Explicit, documented numerical tolerances (`1e-5` for regime transitions, `1e-4` for composite cosine/Euclidean distance metrics, `1e-6` for statistical p-values). Exact equality enforced for discrete outputs, IDs, dates, and categorical regimes.
2. **Dataset Manifest Drift:**
   - A saved research session rerun months later might encounter updated or appended historical datasets.
   - *Mitigation:* Canonical manifest SHA-256 validation. Any change in historical Parquet digests triggers `DATASET_PROVENANCE_MISMATCH` with detailed diffs.
3. **Evidence Package Tampering:**
   - External users could alter historical timestamps, volatility numbers, or scientific limitations inside JSON packages.
   - *Mitigation:* Standalone, independent evidence verifier recalculating canonical SHA-256 checksums over deterministic key-sorted JSON, detecting any modifications.
4. **Epistemological Confusion Regarding Replications:**
   - Risk of conflating holdout criteria satisfaction with independent confirmatory replication.
   - *Mitigation:* Strict invariant enforcement: `PREDECLARED_HOLDOUT_CRITERIA_SATISFIED = 2`, `INDEPENDENT_CONFIRMATORY_REPLICATIONS = 0`. Clear Turkish disclosures that past exposure eliminates confirmatory status.
5. **Security & Low-Entropy Fingerprint Vulnerability:**
   - Plain SHA-256 fingerprints of short or predictable revoked passwords could theoretically be brute-forced offline.
   - *Mitigation:* Active credentials must use high-entropy random secrets (`secrets.token_hex(24)`). Support keyed HMAC revocation checking alongside SHA-256 blacklisting, constant-time comparisons, and strict fail-closed authorization.
6. **Performance Degradation via Expensive Verification:**
   - Full historical data scans or repeated matrix computations could saturate memory or CPU.
   - *Mitigation:* Bounded cache sizes, rate limiting, explicit operator triggering (no automatic background loops), and performance observatory tracking latency thresholds.

---

### 4. Sprint 21 Architecture Design

```
+----------------------------------------------------------------------------------------------------+
|                                    RESEARCH QUALITY ASSURANCE V1                                   |
+----------------------------------------------------------------------------------------------------+
|  1. Research Reproducibility Engine (research_reproducibility.py)                                  |
|     - Manifest Schema: CBE-REPRODUCIBILITY-1.0.0                                                  |
|     - Deterministic Replay: Dual-execution verification & canonical output comparison               |
|     - Numerical Policy: Strict categorical equality & calibrated floating-point tolerances        |
|     - Verdicts: REPRODUCIBLE_EXACT, REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE, NON_REPRODUCIBLE, etc.   |
+----------------------------------------------------------------------------------------------------+
|  2. Independent Evidence Verifier (research_evidence_verifier.py)                                 |
|     - Standalone JSON verification without in-memory dependencies                                   |
|     - Tampering Detection: Field modification, timestamp altering, checksum discrepancy           |
|     - Epistemological Boundary: Cryptographic integrity vs scientific ground truth                 |
+----------------------------------------------------------------------------------------------------+
|  3. Scientific Integrity Audit Engine (research_scientific_audit.py)                               |
|     - Historical data integrity (monotonicity, quarantine, coverage)                               |
|     - Canonical model freeze enforcement (CBE-0.7.0, 0 parameter mutations)                       |
|     - Disjoint pattern windows & explainable similarity decomposition                              |
|     - Mandatory holdout disclosures (2 satisfied, 0 confirmatory replications)                     |
+----------------------------------------------------------------------------------------------------+
|  4. Research Quality Scorecard & UI (research_explorer_ui.py)                                      |
|     - Multi-dimensional status: PASS, WARNING, FAIL, UNAVAILABLE (Strict gating, no masking)       |
|     - Interactive Quality Dashboard embedded in Research Workflow with clear Turkish explanations   |
+----------------------------------------------------------------------------------------------------+
|  5. Performance Regression Observatory (research_performance_audit.py)                             |
|     - Latency benchmarking across 8 core operations                                                |
|     - Configurable regression thresholds & resource bounds (No live collection, no trading)        |
+----------------------------------------------------------------------------------------------------+
|  6. Quality Assurance API Endpoints (dashboard_api.py)                                            |
|     - /api/v1/product/research-quality/capabilities                                                |
|     - /api/v1/product/research-quality/verify                                                      |
|     - /api/v1/product/research-quality/evidence/verify                                             |
|     - /api/v1/product/research-quality/scientific-audit                                            |
|     - /api/v1/product/research-quality/performance-audit                                           |
+----------------------------------------------------------------------------------------------------+
```

---

### 5. Mandatory Governance Invariants

Sprint 21 preserves all non-negotiable safety rules:
- **Canonical Model:** `CBE-0.7.0` (Strictly frozen).
- **Mutations:** Zero parameter modifications.
- **Directional Trading:** Strictly prohibited.
- **Live Orders:** Strictly prohibited.
- **Quarantine:** October 2026 partitions strictly excluded from historical research.
- **Production Environment:** Zero-touch (`c2d07df3c505` untouched).
