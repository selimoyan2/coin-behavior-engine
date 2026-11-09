# COIN BEHAVIOR ENGINE — SPRINT 24
## Architecture Audit & Product Baseline
### Sprint ID: `CBE_PRODUCT_ACCELERATION_24`

**Repository:** `selimoyan2/coin-behavior-engine`  
**Verified Sprint 23 Closure Commit:** `cf4ca9720b586a928503f68b81e4324bcf222795`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Governance Decision:** `TECHNICAL_NO_GO`  
**Date:** 2026-11-09  

---

## 1. System Overview & Technology Stack

The Coin Behavior Engine (CBE) is a deterministic cryptocurrency market behavior analysis and research platform.
- **Backend:** Python 3.11 with custom asynchronous HTTP server (`server.py`), REST API router (`dashboard_api.py`), and modular analytical engines (`src/coin_behavior_engine/product/`).
- **Data Persistence:** Persistent Docker volume mounted at `/app/data/prospective` in staging/production, backed by strict cryptographic HMAC-SHA256 attestation (`storage_durability.py`). Research library definitions are persisted as RFC 8785 canonical JSON files. Session management uses SQLite with Write-Ahead Logging (WAL) at `/app/data/prospective/sessions.db`.
- **Concurrency & Resource Governance:** Multi-process concurrency control with file-backed semaphores in `/tmp/cbe_locks/` limiting heavy operations (PDF/HTML rendering, holdout evaluations) to prevent memory exhaustion and server starvation.
- **Frontend Architecture:** Self-contained Single Page Application (SPA) delivered via `render_product_dashboard_html()` in `dashboard_ui.py` with injected modular styles, DOM elements, and vanilla JavaScript from `research_explorer_ui.py`.
- **Zero External Network Dependencies:** Self-contained Canvas/SVG time-series charts and responsive styling without external CDNs or unverified third-party scripts.

---

## 2. Rendering & Routing Architecture

1. **HTTP Server (`src/coin_behavior_engine/web/server.py`):**
   - Routes `/` and `/product` to `render_product_dashboard_html()`.
   - Routes `/api/v1/product/*` and `/api/v1/operator/*` to `ProductDashboardApiService.handle_request()` (and respective POST/PATCH/DELETE handlers).
   - Routes `/health` and `/ready` for Kubernetes / Coolify orchestration probes.
   - Routes `/diagnostics` for privileged runtime inspection.
   - Enforces CSRF validation for state-mutating requests (`POST`, `DELETE`, `PATCH`).

2. **API Dispatcher (`src/coin_behavior_engine/product/dashboard_api.py`):**
   - Handles 150+ granular analytical sub-paths covering research findings, candle retrieval, regime transitions, analog patterns, holdout validation, evidence intelligence, reports, and sessions.
   - Integrates `SessionManager` for cookie-based session verification with cryptographically signed tokens and rolling expiration.
   - Enforces `ResourceGovernor` locks for report generation and intensive computations.

3. **Frontend Presentation (`src/coin_behavior_engine/product/research_explorer_ui.py` & `dashboard_ui.py`):**
   - Renders responsive Turkish-first views with dark-mode scientific UI theme.
   - Interactive Canvas chart with zoom, pan, hover tooltips, and crosshair inspection.
   - Stepper-based research workflow and reporting center.
   - Research library management with search, filter, and persistence verification.

---

## 3. Sprint 23 Carry-Forward & Security Verification

- **Signed Volume Attestation:** Preserved and hardened. In `storage_durability.py`, missing runtime container or image identities cannot bypass container-bound or image-bound attestations; unverified identities fail closed with `UNVERIFIABLE_VOLUME_IDENTITY`.
- **RFC 8785 Canonical JSON:** Preserved. Evidence hashing uses RFC 8785 canonicalization with backward-compatible support for legacy v1 formats.
- **SQLite WAL Session Store:** Preserved in `session_manager.py` with HMAC-SHA256 session tokens.
- **Resource Governor:** Preserved with file-backed semaphores and max payload limits (2 MB).
- **Zero-Touch Production:** Staging on `srv1114257:18080` remains completely isolated from production (`coin.ozelweb.com.tr`, container `9363556531a7`).
