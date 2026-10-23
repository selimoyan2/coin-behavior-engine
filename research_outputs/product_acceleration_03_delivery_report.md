# CBE — Product Acceleration Sprint 03: Delivery Report
## Coolify Runtime Repair, Historical Market Intelligence, Research UX & Macro Event Replay

**Date:** 2026-10-24  
**Target Environment:** Coolify Linux VPS (`coin.ozelweb.com.tr` staging)  
**Authorized Scope:** `cbe-market-intelligence-staging` container (`127.0.0.1:8080:8000`)  
**Production Isolation:** Verified untouched (`6t63aehpaw0cw1bbt4zcm09g`)  
**Technical Decision:** `TECHNICAL_NO_GO` (Safety Lock Intact)  
**Governance Authorization:** `NOT_GRANTED` (Live execution prohibited)  

---

## 1. Executive Summary

Sprint 03 successfully closed the gap between local research capabilities and live staging deployment by resolving the root cause of blank candlestick charts on Coolify, implementing dynamic runtime revision tracking, creating a unified interactive Research Workspace on the Overview tab, upgrading the Historical Market Explorer with 5 multi-year candle intervals and audited macro event overlays, and conducting complete browser verification via Playwright Chromium.

All 60 automated tests passed (100% green), all 10 browser acceptance tests passed across desktop, tablet, and mobile viewports, and 285 multi-year Parquet partitions (65 MB total) were incorporated directly into version control.

---

## 2. Root Cause Analysis & Runtime Fixes

### 2.1 Blank Candlestick Chart Root Cause
- **Problem:** On staging, navigating to the Historical Explorer displayed: *"Veri yükleniyor veya bu dönem için mum kaydı bulunamadı..."* even though local development displayed candles.
- **Root Cause:**
  1. `.gitignore` line 50 contained `data/binance_spot_multiyear/`. Because Coolify builds containers by cloning directly from the Git repository, the container image had an empty data directory.
  2. `Dockerfile` lacked `COPY research_outputs/ ./research_outputs/`, omitting precomputed analog patterns and research artifacts.
- **Remediation:**
  - Modified `.gitignore` to only ignore `data/binance_spot_multiyear/1m/` (210 MB, reserved for high-frequency offline backtests).
  - Explicitly tracked and staged all 285 multi-year Parquet partitions for `5m`, `15m`, `1h`, `4h`, and `1d` intervals spanning 2022-01 to 2026-09 (65 MB total, all individual files < 1 MB, fully compliant with GitHub limits).
  - Added `COPY research_outputs/ ./research_outputs/` into `Dockerfile`.
  - Added multi-path fallback resolver in `dashboard_api.py` searching project root, repo root, and fallback data paths.

### 2.2 Hardcoded Git SHA Elimination
- **Problem:** UI components previously displayed a static placeholder `2e7ad236ba07f71...`.
- **Root Cause:** Hardcoded strings in `dashboard_api.py` and `dashboard_ui.py`.
- **Remediation:**
  - Implemented `get_runtime_git_revision()` with a robust 4-layer resolution strategy:
    1. Environment variables (`GIT_COMMIT`, `SOURCE_COMMIT`, `COOLIFY_GIT_COMMIT`).
    2. Local `.git/HEAD` reference parsing.
    3. `git rev-parse HEAD` subprocess fallback.
    4. `build_metadata.json` lookup.
  - Refactored `dashboard_ui.py` to bind `.dyn-git-rev` and `.dyn-git-rev-short` elements dynamically from API payloads.

---

## 3. Architecture & Product Capabilities Delivered

### 3.1 Overview Tab — Interactive Research Workspace
- Embedded high-performance HTML5 Canvas Candlestick Chart with interactive Crosshair HUD displaying Time, Open, High, Low, Close, Volume, and Change %.
- Real-time Dataset Status Header reporting active symbol (`BTCUSDT`), date range (`2022-01 - 2026-09`), total partitions (`285 Parquet files`), and macro event count (`236 events`).
- Quick-action buttons providing seamless deep-linking to Market Behavior, Macro Ledger, Analog Explorer, and Governance.
- Four Empirical Research Intelligence Cards:
  1. **Regime Distribution & Stability:** 5-regime classification breakdown with transition matrices.
  2. **Top Correlated Historical Analogs:** Top-3 pattern matches with Pearson $r$, DTW distance, and projected 14-day path.
  3. **High-Impact Macro Reaction Profile:** Fed rate decision and CPI reaction envelopes ($T+15\text{m}$, $T+1\text{h}$, $T+24\text{h}$).
  4. **Durability & Operational Health:** Segregated staging container runtime vs offline benchmark audit.
- Compact Cryptographic Governance Status Bar with fail-closed badges.

### 3.2 Historical Market Explorer Upgrades
- Interval switching between `5m`, `15m`, `1h`, `4h`, and `1d` with sub-50ms render latency.
- Dynamic Month Navigator covering 57 months from 2022-01 to 2026-09.
- Macroeconomic Event Overlays: Flag pins pinned directly above candlesticks at exact event timestamps with hover tooltips displaying category, headline, surprise factor, and audited return impacts.
- Interactive Zoom & Pan controls with reset capabilities.
- Volatility Regime color bands rendered beneath price action.

### 3.3 Audited Macro Reactions Table & Explorer
- Dedicated reaction ledger populated from `verified_event_reaction_ledger_11_23_1.parquet` (236 verified historical events).
- Dynamic category filtering (`US_INFLATION`, `US_MONETARY_POLICY`, `US_LABOR`, `REGULATION`, `US_GROWTH`).
- Audited post-event return metrics ($T+15\text{m}$, $T+1\text{h}$, $T+24\text{h}$) with color-coded directional styling.

### 3.4 New API Endpoints
1. `GET /api/v1/product/macro-reactions`:
   - Query parameters: `category`, `limit`, `offset`.
   - Returns merged event metadata, surprise indices, and verified multi-horizon returns.
2. `GET /api/v1/product/dataset-catalog`:
   - Returns full inventory of multi-year Parquet files, interval coverage, total file sizes, and historical regime dates.
3. Upgraded `GET /api/v1/product/historical-candles`:
   - Returns candle array, interval, month, symbol, record count, and pre-matched `event_markers`.

---

## 4. Verification & Testing Summary

| Test Category | Suite | Passed | Failed | Status |
| :--- | :--- | :---: | :---: | :---: |
| Web Server Core | `tests/test_web_server.py` | 13 | 0 | PASSED |
| Product Acceleration 01 API | `tests/test_sprint_product_acceleration_01_api.py` | 13 | 0 | PASSED |
| Product Acceleration 01 Integration | `tests/test_sprint_product_acceleration_01_integration.py` | 5 | 0 | PASSED |
| Product Acceleration 02 API | `tests/test_sprint_product_acceleration_02_api.py` | 12 | 0 | PASSED |
| Product Acceleration 03 Deep Suite | `tests/test_sprint_product_acceleration_03.py` | 9 | 0 | PASSED |
| Staging Hardening | `tests/test_sprint11_02b_1_staging_hardening.py` | 8 | 0 | PASSED |
| **Total Automated Pytest** | **All Suites** | **60** | **0** | **100% PASS** |
| **Playwright Chromium E2E** | `run_browser_acceptance.py` | **10** | **0** | **100% PASS** |

---

## 5. Governance & Production Safeguards

- **Staging Port:** Container runs isolated on `127.0.0.1:8080:8000`.
- **Production Target:** `coin.ozelweb.com.tr` (`6t63aehpaw0cw1bbt4zcm09g`) was not modified or accessed.
- **Fail-Closed Governance:** `TECHNICAL_NO_GO` decision and `NOT_GRANTED` authorization were maintained without compromise.
- **Network Acquisition:** Live market data collection disabled; system operates strictly offline on audited historical datasets.
