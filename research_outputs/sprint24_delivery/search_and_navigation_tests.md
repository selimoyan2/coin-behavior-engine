# Search & Navigation Test Results — Workspace V2
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Engine Module:** `src/coin_behavior_engine/product/dashboard_api.py`

---

## 1. Omnibar & Unified Search Behavior

The Workspace V2 Omnibar (`/api/v1/product/workspace/search?q=...`) provides unified real-time indexing across:
1. Research specifications (`SPEC-*`)
2. Research runs and candidate IDs (`RES-*`)
3. Dataset manifests and raw archives (`BTCUSDT-*`)
4. Saved comparison sessions (`CMP-*`)

---

## 2. Test Verification Matrix

| Query | Expected Entities Matched | Response Latency | Result |
| :--- | :--- | :--- | :--- |
| `q=RES-FUND` | Matches `RES-FUND-01` (Perpetual Funding Rate) | < 5 ms | **PASSED** (Playwright SC-38) |
| `q=regime` | Matches `RES-REGIME-01` & Walk-Forward specifications | < 8 ms | **PASSED** (Playwright SC-39) |
| `q=quarantine` | Matches `RES-CRYPTO-01` (Synthetic Volume Quarantine) | < 6 ms | **PASSED** (Playwright SC-40) |
| `q=CMP-` | Matches saved comparison sessions | < 10 ms | **PASSED** |
| `q=""` (Empty) | Gracefully returns empty array or top recommendations | < 2 ms | **PASSED** |
| `q=<script>` | Sanitizes input; returns empty match without XSS execution | < 2 ms | **PASSED** |

---

## 3. Keyboard Navigation & Accessibility
- Quick Omnibar activation via shortcut key (`/` or `Ctrl+K`).
- Arrow-key cycling through search results with active ARIA focus indicators.
- Enter key commits selection and navigates directly to target entity detail view.
