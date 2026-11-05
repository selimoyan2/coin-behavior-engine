# Coin Behavior Engine — Sprint 23 Architecture & Security Audit
## Enterprise-Grade Security Hardening, Multi-Process Concurrency, Durable Research Storage & Operational Readiness

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_23`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Branch:** `main`  
**Verified Baseline Commit:** `db3bb63e1aca90582847880e80abd9e87938b142` (Sprint 22 Final Closure)  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY FROZEN, 0 parameter mutations)  
**Governance Invariant:** `TECHNICAL_NO_GO` (Directional predictions and live execution permanently disabled)  
**Production Isolation:** STRICT ZERO-TOUCH on Production Container `1a867269c843`  
**Audit Timestamp:** `2026-11-06T01:54:00Z`  

---

### 1. Executive Summary & Repository Discovery

Coin Behavior Engine has evolved through Sprints 17–22 into a sophisticated historical scientific research platform encompassing:
- Historical Market Intelligence Explorer & Unified Research Workspace
- Pattern Discovery V2 & Comparison Studio V2
- Research Library with Reusable Definitions & Associated Report Tracking
- Scientific Integrity Scorecard & Dual Deterministic Reproducibility
- Research Report Builder (15-section scientific reporting)
- Scientific Narrative Generation & TrueType Unicode PDF / Offline HTML Exporters
- Verifiable Evidence Bundles with Independent Server-Side Authenticity Verification

While Sprint 22 successfully eliminated fabricated values, enforced timezone-aware datetime validation, and introduced atomic file replacement, Sprint 23 targets the enterprise software engineering layer: eliminating credential cross-purpose reuse, removing raw tokens from browser JavaScript, replacing thread-only locks with cross-process file locks, verifying durable Docker volume mounts, enforcing strict VPS resource limits, and delivering end-to-end operational observability.

---

### 2. Architecture & Component Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    BROWSER / CLIENT WORKSPACE                                      |
|  - Research Explorer UI  - Workflow Stepper (1-7)  - Operational Status Panel                      |
|  - HttpOnly Session Cookies (No raw operator secrets in JS)  - CSRF Token Headers                  |
+----------------------------------------------------------------------------------------------------+
                                      | HTTP / TLS (18080 / 8000)
                                      v
+----------------------------------------------------------------------------------------------------+
|                                  WEB SERVER & SECURITY GATEWAY                                     |
|  - Request Routing (`server.py`)                                                                   |
|  - Security Middleware: Session Validation, CSRF Verification, Fetch Metadata, Origin Enforcement  |
|  - Resource Governor: Concurrency Semaphores (Research: 2, PDF: 2, Evidence: 4), Payload Limits   |
|  - Secret Isolation: Operator Token vs Evidence Signing Key vs Admin Token                         |
+----------------------------------------------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         v                                                         v
+---------------------------------------+       +---------------------------------------+
|        RESEARCH CORE ENGINES          |       |         PERSISTENCE & AUDIT           |
| - Unified Research Workspace Engine   |       | - Multi-Process Advisory File Locking |
| - Research Reproducibility Engine     | <===> | - Atomic Temp-Fsync-Replace Protocol  |
| - Scientific Narrative Engine         |       | - Durable Docker Volume Validator     |
| - Comparison Reporting Engine         |       | - Research Library JSON Storage       |
| - Evidence Bundle & Signing Engine    |       | - Backup & Restore Engine             |
| - PDF (ReportLab) & HTML Exporters    |       | - Redacted Structured JSON Logger     |
+---------------------------------------+       +---------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------------------------+
|                                  CANONICAL SCIENTIFIC GOVERNANCE                                   |
|  - Model: CBE-0.7.0 (STRICTLY FROZEN, 0 Mutations)                                                |
|  - Governance Decision: TECHNICAL_NO_GO                                                            |
|  - Quarantine Boundary: 2026-10-01T00:00:00Z (Strictly Enforced)                                  |
|  - Real Network Binance / Live Trading: PERMANENTLY PROHIBITED                                     |
+----------------------------------------------------------------------------------------------------+
```

---

### 3. Security Boundary & Threat Model

| Boundary | Assets Protected | Threat Vectors | Sprint 23 Remediation |
| :--- | :--- | :--- | :--- |
| **B1: Client / Browser** | Operator credentials, session tokens | XSS, script scraping, credential leakage in browser logs/traces | Replace `window.CBE_OPERATOR_TOKEN` and `sessionStorage` with server-issued `HttpOnly; SameSite=Strict` cookies and short-lived CSRF tokens. |
| **B2: Credential Purpose** | Operator Auth vs Evidence Signing | Credential reuse, token misuse, unauthorized signing | Distinct environment variables (`CBE_OPERATOR_TOKEN`, `CBE_EVIDENCE_SIGNING_KEY`, `CBE_TEST_OPERATOR_TOKEN`, `CBE_ADMIN_DIAGNOSTICS_TOKEN`). Key registry with versioning and rotation. |
| **B3: Web Mutations** | Research Library, Report Creation | CSRF, cross-site origin spoofing, unauthorized writes | Origin and `Sec-Fetch-Site` verification, mandatory CSRF token header for state-changing requests, fail-closed revocation check. |
| **B4: Evidence Authenticity** | Research Integrity & Provenance | Forged signatures, recomputed client hashes, tampered reports | Never trust client checksums as trust anchors; verify HMAC-SHA256 signatures with registered key; full byte-equality check against server storage. |
| **B5: Concurrent Persistence** | Report JSON, Library metadata | Race conditions, dirty reads, partial file writes, multi-worker collisions | `MultiProcessLock` utilizing OS file locks (`fcntl.flock` / `msvcrt.locking`) plus thread locks; atomic `.tmp` -> `fsync()` -> `replace()` pattern. |
| **B6: VPS Resource Protection** | Shared CPU, RAM, Disk I/O | Denial of Service, OOM kill, CPU starvation during dual replay | Bounded concurrency semaphores, bounded candle limits, bounded report size (2 MB), query timeouts, backpressure (HTTP 429/503). |
| **B7: Storage Durability** | Retrospective research artifacts | Container recreation data loss, ephemeral mount writes | Docker volume validation (`PERSISTENT_VERIFIED`), rejection of tmpfs/ephemeral mounts in staging/prod, non-destructive backup/restore verification. |

---

### 4. Data Flow & Persistence Map

1. **Research Request Flow:**
   ```
   Client POST /api/v1/product/research-reports/generate
     -> Session & CSRF Authentication
     -> Resource Governor Semaphore Check (max 2 active)
     -> Historical Dataset Load (Cached / Range Validated)
     -> Quality Scorecard & Dual Replay Execution
     -> 15-Section Report Compilation
     -> Multi-Process Lock Acquisition (`.<report_id>.lock`)
     -> Atomic File Save (`.<report_id>.<pid>.<tid>.<ns>.tmp` -> `fsync` -> `os.replace` -> `<report_id>.json`)
     -> Parent Directory `fsync`
     -> Multi-Process Lock Release
     -> Semaphore Release
     -> Return Canonical Report JSON
   ```

2. **Evidence Packaging & Verification Flow:**
   ```
   Client POST /api/v1/product/research-reports/{id}/evidence
     -> Fetch canonical report from persistent store
     -> Compute canonical payload & package checksum
     -> Sign with active key from SigningKeyRegistry (`CBE_EVIDENCE_SIGNING_KEY`)
     -> Return Sealed Bundle JSON

   Client POST /api/v1/product/research-reports/verify
     -> Verify internal canonical checksum consistency
     -> Verify non-finite floats (NaN/Inf) & ISO datetime bounds
     -> Verify dataset manifest & source commit identity
     -> If signature present: verify cryptographically against SigningKeyRegistry
     -> If report_id matches persistent store: compare 100% full canonical JSON
     -> Return Explicit Verdict:
        * AUTHENTICITY_VERIFIED (if store match or valid signature)
        * INTEGRITY_VERIFIED_UNTRUSTED_SOURCE (if valid payload but unverified origin)
        * AUTHORITATIVE_CONTENT_MISMATCH (if store conflict)
        * REVOKED_SIGNING_KEY (if signed by revoked key)
        * INVALID_OPERATOR_SIGNATURE (if signature check fails)
   ```

3. **Storage Mount Architecture:**
   - **Persistent Volumes:**
     - `/app/data/prospective` (Docker volume `dbc52dc547a4...` mounted `rw`): Designated persistent store for research reports (`/app/data/prospective/reports`) and research library definitions (`/app/data/prospective/research_library`).
     - `/app/data/live_capture` (Docker volume `zgit1s3n1acdtqtsxp0s44vj...` mounted `ro`): Canonical historical dataset.
   - **Ephemeral / Disallowed for Reports:**
     - `/tmp`, `/run` (tmpfs 64MB / 16MB `rw,noexec,nosuid`): Temporary scratch files only; research reports strictly prohibited.
     - Container rootfs (`read_only: true`): Immutable system root.

---

### 5. Performance Hotspots & Resource Ceilings

1. **Identified Bottlenecks:**
   - Dual Deterministic Replay in `ResearchReproducibilityEngine`: Re-runs historical sessions across 336+ candles, consuming 60–80 seconds of CPU on single-core VPS constraints.
   - Matplotlib PDF Rendering in `ResearchReportPdfRenderer`: Memory and font caching overhead during chart generation.
   - Full Historical Scans during Pattern Discovery candidate matching.
2. **Resource Ceilings Implemented:**
   - Concurrency Semaphore: Max 2 simultaneous report generation jobs.
   - Concurrency Semaphore: Max 2 simultaneous PDF render jobs.
   - Concurrency Semaphore: Max 4 simultaneous evidence verification jobs.
   - Request timeout: 60 seconds execution budget.
   - Payload limit: 2 MB maximum JSON request body.
   - Candle range limit: Maximum 5,000 candles per ad-hoc research request.

---

### 6. Prioritized Remediation Plan

- **Phase 1 (P0):** Credential separation (`CBE_OPERATOR_TOKEN` vs `CBE_EVIDENCE_SIGNING_KEY` vs `CBE_ADMIN_DIAGNOSTICS_TOKEN`), key registry with rotation and revocation.
- **Phase 2 (P0):** Server-managed sessions with HttpOnly cookies, CSRF protection, and removal of raw credentials from browser JavaScript.
- **Phase 3 (P0):** Multi-dimensional evidence verification with explicit non-misleading verdicts and canonical serialization.
- **Phase 4 (P0):** Multi-process advisory file locking (`MultiProcessLock`), atomic write safety without direct-write fallback.
- **Phase 5 (P0):** Durable Docker volume classification (`PERSISTENT_VERIFIED`), backup/restore engine, container recreation test.
- **Phase 6 & 7 (P1):** Concurrency semaphores, request backpressure, bounded caching, latency benchmarks.
- **Phase 8 & 9 (P1):** Health (`/health`), readiness (`/ready`), privileged diagnostics (`/api/v1/product/diagnostics`), structured error taxonomy.
- **Phase 10 (P1):** Redacted structured JSON logging with correlation IDs.
- **Phase 11 (P1):** ReportLab PDF pagination, TrueType Unicode font embedding, visual regression verification.
- **Phase 12 (P2):** Operational status panel integrated into Research Explorer UI.
- **Phase 13 (P1):** API input validation and contract hardening.
- **Phase 14 & 15 (P0):** Comprehensive automated testing (`test_sprint_product_acceleration_23.py`) and Playwright E2E suite (`run_playwright_sprint23.py`, 34 scenarios).
- **Phase 16–18 (P0):** Staging deployment, zero-touch production verification, delivery artifacts and manifest certification.

---

### 7. Governance Invariants (Strictly Maintained)

- `CANONICAL_SCIENTIFIC_MODEL`: `CBE-0.7.0` (FROZEN, 0 parameter mutations)
- `TECHNICAL_DECISION`: `TECHNICAL_NO_GO`
- `DIRECTIONAL_TRADING`: `STRICTLY_PROHIBITED`
- `LIVE_ORDER_EXECUTION`: `PERMANENTLY_PROHIBITED`
- `QUARANTINE_BOUNDARY`: `2026-10-01T00:00:00Z`
- `PRODUCTION_CONTAINER`: `1a867269c843` (Strict Zero-Touch)
