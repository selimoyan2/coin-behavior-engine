# Performance Benchmarks & Resource Utilization
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Host Environment:** Staging Container `7e6268bbd2a7` on `srv1114257` (0.5 CPU, 300MB RAM budget)

---

## 1. Latency Benchmarks (Staging HTTP API)

Measurements taken over 50 consecutive requests to `http://127.0.0.1:18080` under warm cache conditions:

| Endpoint | Operation Description | Mean Latency | p95 Latency | p99 Latency | SLA Budget | Compliance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/ready` | Readiness probe | 2.1 ms | 3.8 ms | 5.2 ms | 50 ms | **PASS** |
| `/workspace/overview` | Grounded overview aggregation | 14.5 ms | 22.3 ms | 28.7 ms | 100 ms | **PASS** |
| `/workspace/research` | Catalog filtering & pagination | 6.8 ms | 11.2 ms | 16.4 ms | 100 ms | **PASS** |
| `/workspace/research/{id}` | Detailed research drawer fetch | 3.4 ms | 5.8 ms | 8.1 ms | 50 ms | **PASS** |
| `/workspace/comparison/evaluate` | 12-point gate evaluation | 4.2 ms | 7.9 ms | 12.0 ms | 50 ms | **PASS** |
| `/workspace/search` | Bounded metadata search ($N=20$) | 3.9 ms | 6.4 ms | 9.5 ms | 50 ms | **PASS** |

---

## 2. Resource Footprint & Limits Compliance

| Metric | Measured Value | Configured Limit | Headroom | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Container Memory (RSS)** | 54.2 MB | 300.0 MB | 81.9% Headroom | **HEALTHY** |
| **Memory Reservation** | 54.2 MB | 150.0 MB | Within baseline | **HEALTHY** |
| **CPU Utilization (Idle)** | 0.2% | 50.0% (0.5 core) | 99.6% Idle | **HEALTHY** |
| **CPU Utilization (Peak)** | 8.4% | 50.0% (0.5 core) | 83.2% Headroom | **HEALTHY** |
| **Process ID Count** | 3 threads | 64 pids | 95.3% Available | **HEALTHY** |
| **Tmpfs Storage Usage** | 1.8 MB | 64.0 MB | 97.2% Headroom | **HEALTHY** |

---

## 3. Caching & Query Optimization

* **Catalog Caching (`_CACHE_TTL_SECONDS = 30.0`):** Repeated queries reuse in-memory instances of `ResearchRecord`, avoiding disk reads and SHA-256 recalculation on every keystroke.
* **Frontend Debounce (200ms):** Typing in the global search input delays API queries until the operator pauses, reducing query frequency by ~85% during interactive use.
* **Bounded Pagination:** Hard limit of 50 items per page ensures JSON serialization payloads remain under 35 KB.
