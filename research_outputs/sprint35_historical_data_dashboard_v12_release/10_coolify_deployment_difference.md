# SPRINT 35 — COOLIFY DEPLOYMENT DIFFERENCE AUDIT & FORENSIC ANALYSIS

**Audit Date:** 2026-11-15 / 2026-11-16  
**Audited Target:** Coolify Production Container (`3ec682ef49a4`) vs Staging Container (`e4bfd88ebc75`)  
**Host Server:** `srv1114257` (`168.231.125.238`)  
**Production URL:** `https://coin.ozelweb.com.tr` (Port 8000)  
**Staging URL:** `http://168.231.125.238:18080` (Port 18080)  

---

## 1. The Core User-Facing Phenomenon

The operator noted that the production web application at `https://coin.ozelweb.com.tr` only displays historical data up to **September 2026** and does not show October or November 2026 data, despite multiple research sprints completing data recovery work.

---

## 2. Root Cause Forensic Determination

An independent inspection of the Coolify deployment pipeline and host Docker runtime identified the definitive root cause:

### Cause 1: Git Branch Decoupling
- **Production Container:** Coolify Application `6t63aehpaw0cw1bbt4zcm09g` is configured to track Git branch `main`.
- **Branch `main` State:** The HEAD commit of `main` is `c9e3907a226cfbe01e73f87c960156afdd874dc4` (Sprint 33).
- **All Research Sprints (34, 34.1, 34.2, 35):** All development, data engineering, and dashboard improvements have taken place strictly on the research branch: `research/sprint33-canonical-bridge-market-intelligence`.
- **Production Zero-Touch Invariant:** In accordance with the inviolable governance rule (`STRICT_ZERO_TOUCH`), no agent has merged research commits into `main` or triggered the production deployment webhook.

### Cause 2: Physical Docker Image Layer Storage
- When Docker builds the production image from `main`:
  - The repository files are copied via `COPY . /app`.
  - On branch `main`, `data/binance_spot_multiyear/5m/` literally ends at `BTCUSDT-5m-2026-09.parquet`.
  - There is physically no October or November parquet file inside the production container.
- Even when the Coolify webhook re-triggers a build on production, it pulls from `main`, rebuilding the September 2026 snapshot.

### Cause 3: Staging vs Production Separation
- **Staging Container (`e4bfd88ebc75`):** Deployed manually on port 18080 using the research branch code and data. It successfully serves October and November data.
- **Production Container (`3ec682ef49a4`):** Strictly isolated, serving the frozen `main` branch on port 8000.

---

## 3. Comparison Matrix

| Attribute | Production Container (`3ec682ef49a4`) | Staging Container (`e4bfd88ebc75`) |
|---|---|---|
| **Host Port** | `8000` (mapped to `https://coin.ozelweb.com.tr`) | `18080` |
| **Git Tracking** | `origin/main` (`c9e3907a226cfbe01e73f87c960156afdd874dc4`) | `research/sprint33-canonical-bridge-...` |
| **Latest Month on Disk** | `2026-09` (Eylül 2026) | `2026-11` (15 Kas 21:15 UTC) |
| **Total Monthly Partitions** | 57 Months | 59 Months (58 Complete + 1 Partial) |
| **Dashboard UI Version** | Dashboard V10 / V11 | Dashboard V12 |
| **Status Badge Support** | Static text | Dynamic Complete / Partial Badges |
| **Live Trading Gate** | HTTP 403 Forbidden | HTTP 403 Forbidden |

---

## 4. Resolution Protocol for Operator

To promote Sprint 35 to production without violating zero-touch governance:
1. Review the Release Candidate Manifest (`11_release_candidate_manifest.json`).
2. Review the Production Release Plan (`12_production_release_plan.md`).
3. The human operator executes the authorized merge of `research/sprint33-canonical-bridge-market-intelligence` into `main` and invokes the Coolify production build.
