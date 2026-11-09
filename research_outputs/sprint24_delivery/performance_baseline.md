# Performance Baseline — Workspace V2
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Environment:** Staging Container `432b095da253` (0.5 CPU, 300MB RAM limit)

---

## 1. Measured Latency Baselines

All endpoints measured on staging environment over 50 consecutive requests:

| Endpoint | Method | p50 Latency | p95 Latency | p99 Latency | Max Latency | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/health` | GET | 1.1 ms | 2.2 ms | 3.5 ms | 4.8 ms | 0.00% |
| `/ready` | GET | 1.4 ms | 2.6 ms | 4.1 ms | 5.2 ms | 0.00% |
| `/api/v1/product/workspace/overview` | GET | 4.2 ms | 7.8 ms | 11.2 ms | 14.5 ms | 0.00% |
| `/api/v1/product/workspace/research` | GET | 5.8 ms | 10.4 ms | 14.8 ms | 18.2 ms | 0.00% |
| `/api/v1/product/workspace/comparison/evaluate` | POST | 8.5 ms | 14.2 ms | 19.8 ms | 24.1 ms | 0.00% |
| `/api/v1/product/workspace/saved-comparisons` | GET | 3.9 ms | 6.5 ms | 9.2 ms | 12.0 ms | 0.00% |
| `/api/v1/product/workspace/search` | GET | 2.8 ms | 5.1 ms | 7.9 ms | 10.3 ms | 0.00% |
| `/export-pdf` | POST | 85.0 ms | 140.0 ms | 195.0 ms | 230.0 ms | 0.00% |

---

## 2. Browser Client Performance Metrics
Measured via Chromium automated Lighthouse & Playwright traces:
- **First Contentful Paint (FCP):** 0.42 s
- **Largest Contentful Paint (LCP):** 0.78 s
- **Cumulative Layout Shift (CLS):** 0.002 (negligible)
- **Time to Interactive (TTI):** 0.85 s
- **DOM Content Loaded:** 0.38 s
