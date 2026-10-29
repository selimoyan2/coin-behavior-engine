# Coin Behavior Engine — Sprint 19 Architecture Review
## Research Intelligence Explorer V1, Comparative Analytics & Research Library V1

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_19`  
**Depot:** `selimoyan2/coin-behavior-engine` (Branch: `main`)  
**Base Commit Verified:** `948222a380327b07ffd3b865d4fd224b61a2a6f4` (Sprint 18 Final Closure)  
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS)  
**Target Environments:** Local Development & Coolify Staging (`srv1114257`)  
**Production Status:** STRICT ZERO-TOUCH / READ-ONLY AUDIT (`https://coin.ozelweb.com.tr`)  

---

### 1. Architectural Baseline & Provenance Trace

Sprint 18 successfully closed all outstanding delivery hardening items:
- Staging running a clean, immutable Docker image `sha256:48158ed0e23581c6c66a3208fbd888b7e4900590c5414374de5fa5c7070ccc11` (`cbe-market-intelligence:sprint18-be13d7f`).
- Full product acceleration regression suite (304 tests) passing at 100%.
- Staging warm session latency measured at 7.45 ms (< 100 ms target).
- Production container `eb1941ac5372` preserved in zero-touch state with model `CBE-0.7.0` frozen (uptime >283,500s).

Sprint 19 extends this platform by introducing the **Research Intelligence Explorer V1** and **Research Library V1** without altering frozen model parameters or violating non-trading governance boundaries.

---

### 2. Module Composition & Data Flow

```
+-----------------------------------------------------------------------------------+
|                           BROWSER CLIENT (HTML5 / SVG / JS)                       |
|   +---------------------------------------+   +-------------------------------+   |
|   |  Interactive Candlestick & Volume     |   |  Comparison Studio V2         |   |
|   |  Regime Overlays & Macro Event Markers|   |  Dual Time / Normalized Axis  |   |
|   +---------------------------------------+   +-------------------------------+   |
|   +---------------------------------------------------------------------------+   |
|   |  Research Library V1 Manager (Save, List, Search, Filter, Export, Import)  |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
                                         | HTTP REST (JSON)
                                         v
+-----------------------------------------------------------------------------------+
|                        PRODUCT DASHBOARD SERVICE (dashboard_api.py)               |
|  - GET /api/v1/product/research-explorer/capabilities                             |
|  - GET /api/v1/product/research-explorer/historical-series                        |
|  - GET /api/v1/product/research-explorer/regime-overlay                           |
|  - GET /api/v1/product/research-explorer/macro-events                             |
|  - GET /api/v1/product/research-explorer/comparison                               |
|  - GET /api/v1/product/research-library (List, Search, Filter)                    |
|  - POST /api/v1/product/research-library (Save, Import)                           |
|  - GET / PATCH / DELETE /api/v1/product/research-library/{research_id}            |
+-----------------------------------------------------------------------------------+
                                         |
         +-------------------------------+-------------------------------+
         |                                                               |
         v                                                               v
+-------------------------------------------------+   +---------------------------------+
| ResearchIntelligenceExplorerEngine              |   | ResearchLibraryEngine           |
| (research_intelligence_explorer.py)             |   | (research_library persistence)  |
| - Verifies UTC timestamps & range bounds        |   | - Atomic JSON persistence       |
| - Server-side bucket downsampling (preserving   |   | - Thread-safe lock & validation |
|   true Min/Max/Open/Close semantics)            |   | - Bounded storage (max 100 entries)
| - Extracts canonical 6-regime overlays          |   | - Path traversal protection     |
| - Links 238 verified canonical macro events     |   | - Safe schema migrations        |
| - Orchestrates dual period comparisons          |   | - Safe local/single-user auth   |
+-------------------------------------------------+   +---------------------------------+
         |                                                               |
         +-------------------------------+-------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                           CANONICAL RESEARCH ENGINES (FROZEN)                     |
|  - UnifiedResearchWorkspaceEngine (Sprint 18 orchestration & session cache)       |
|  - HistoricalPatternDiscoveryEngine (Sprint 17 V2 disjoint search & ranking)      |
|  - MacroEventTaxonomyEngine (238 verified events across 6 cohorts)                |
|  - ContentIntegrityEngine (Canonical dataset manifest fe6c73326c...)              |
|  - Parquet Historical Partitions: 2022-01 to 2026-09 (41,615 hourly candles)      |
|  - Strictly Quarantined: October 2026 partitions excluded                         |
+-----------------------------------------------------------------------------------+
```

---

### 3. Server-Side Downsampling Specification

To ensure high performance and prevent browser memory exhaustion when visualizing long historical ranges (e.g., 2022–2026), the engine applies deterministic financial bucket downsampling:

1. **Resolution Threshold:** When the requested range contains more candles than `downsample_max_points` (default 500, max 2,000), candles are aggregated into $K$ equal-sized chronological buckets.
2. **Strict Financial Semantics:**
   - $\text{Open} = \text{Open of the first candle in bucket}$
   - $\text{High} = \max(\text{High values in bucket})$
   - $\text{Low} = \min(\text{Low values in bucket})$
   - $\text{Close} = \text{Close of the last candle in bucket}$
   - $\text{Volume} = \sum \text{Volume of candles in bucket}$
   - $\text{Regime} = \text{Dominant (mode) regime within bucket}$
   - $\text{Parkinson Volatility} = \text{Mean Parkinson volatility across bucket}$
3. **Integrity Rule:** Zero synthetic or interpolated price points are fabricated. The resulting downsampled series accurately reflects the true price boundaries and extremes.

---

### 4. Research Library Persistence Architecture

1. **Storage Location:**
   - In container runtime: `/app/data/prospective/research_library/` (mounted on persistent volume `91573bc4...`).
   - In local development: `data/research_library/`.
   - Fallback configurable via `CBE_RESEARCH_LIBRARY_PATH` environment variable.
2. **Concurrency & Atomicity:**
   - In-memory `threading.Lock()` serializes write operations.
   - Files are written to temporary files (`.tmp`) and atomically replaced using `os.replace` to prevent partial or corrupted writes.
3. **Bounded Capacity:**
   - Storage is capped at a maximum of 100 entries to prevent uncontrolled disk utilization.
   - When the limit is reached, an explicit error is returned requiring user pruning, or oldest unlocked research definitions can be pruned.
4. **Security & Validation:**
   - Research IDs strictly follow `RLIB-[a-f0-9]{12}`.
   - Path traversal prevention: File names are strictly generated from validated research IDs without accepting user-supplied filenames.
   - Input payloads validate schema versions, string lengths (title $\le$ 100 chars, description $\le$ 500 chars), ISO-8601 UTC timestamps, supported intervals, and quarantine exclusion.
   - Zero secrets or tokens are stored in research definition JSON files.

---

### 5. Governance & Non-Trading Invariants

All Sprint 19 components adhere strictly to the immutable governance specifications:
```yaml
CANONICAL_MODEL: CBE-0.7.0
MODEL_PARAMETER_MUTATIONS: ZERO
TECHNICAL_DECISION: TECHNICAL_NO_GO
GOVERNANCE_AUTHORIZATION: NOT_GRANTED
PRODUCTION_TOKEN: NOT_ISSUED
REAL_NETWORK_MARKET_COLLECTION: DISABLED
BTCUSDT_LIVE_OBSERVATION: DISABLED
UNATTENDED_MONITORING: DISABLED
LIVE_ORDER_EXECUTION: PERMANENTLY_PROHIBITED
DIRECTIONAL_TRADING_ELIGIBILITY: ZERO
```
