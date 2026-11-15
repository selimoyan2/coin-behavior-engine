# 12. Production Release Readiness Proposal & Migration Specification — Sprint 34.2

**Sprint ID:** `CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS`  
**Execution Timestamp:** 2026-11-15T23:31:30+03:00  
**Attribution Tier:** `RELEASE_MANAGEMENT_AND_GOVERNANCE`  
**Current Production Status:** `STRICT_ZERO_TOUCH` (Untouched, tracking `main`)  
**Promotion Authorization:** `REQUIRES_EXPLICIT_OPERATOR_APPROVAL`  

---

## 1. Executive Summary

This proposal outlines the precise, low-risk operational procedure for promoting the verified research and market behavior intelligence improvements from the research branch `research/sprint33-canonical-bridge-market-intelligence` into production (`main`), once explicit operator authorization is granted.

**Strict Governance Guarantees:**
- No automatic merge to `main` has occurred.
- No Coolify production deployment webhook has been triggered.
- No production database, volume, or container has been modified.
- Production continues to run undisturbed on container `4cdc04ccb16b` at `https://coin.ozelweb.com.tr`.

---

## 2. Release Candidate Identification

| Component | Release Candidate Value |
|---|---|
| **Source Branch** | `research/sprint33-canonical-bridge-market-intelligence` |
| **Target Branch** | `main` |
| **Candidate Commit SHA** | Current research HEAD after Sprint 34.2 commit |
| **Canonical Model Version** | `CBE-0.7.0` (STRICTLY_FROZEN) |
| **Base Docker Image** | `python:3.11-slim` with multi-stage wheels |
| **Staging Image Tested** | `cbe-market-intelligence:sprint34_2-<short_sha>` |
| **Target Deployment Host** | `srv1114257 (168.231.125.238)` via Coolify |

---

## 3. Required Data Artifacts & Manifests

Upon promotion to production, the following data artifacts must be present in the container build context:

1. **Frozen Canonical Model Lockbox:**
   - `data/models/cbe_070_canonical_frozen_lockbox.pkl` (SHA-256: `3e089ffe584fac31c0bb6aa284a83ad6fdd0b0cffdf3b7645eec1a731d83fabd`)
   - `data/models/cbe_070_canonical_frozen_lockbox_manifest.json`
2. **Historical Spot Partitions:**
   - 57 complete verified monthly partitions (`2022-01` through `2026-09`) across 5 intervals (`5m`, `15m`, `1h`, `4h`, `1d`).
   - October 2026 verified partition (`2026-10`, containing verified 288 5m bars = 24 1h bars for Oct 1).
   - Canonical dataset manifest: `data/binance_spot_multiyear/manifest.json`.
3. **Research Artifacts:**
   - All 15 Sprint 34.2 authoritative evidence artifacts in `research_outputs/sprint34_2_final_reconciliation/`.

---

## 4. Dataset Volume Migration & Persistence Plan

1. **Persistent Volumes:**
   - Production uses the Coolify persistent Docker volume:
     `6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data` mounted at `/app/data/prospective`.
   - This volume stores prospective audit receipts and prospective telemetry. It requires **zero schema migration** because prospective schemas remain 100% backward compatible.
2. **Read-Only Datasets:**
   - Multi-year historical spot datasets (`/app/data/binance_spot_multiyear`) and frozen models (`/app/data/models`) are baked immutably into the Docker image, ensuring zero host file-system dependencies or race conditions.

---

## 5. Deployment Impact & Zero-Downtime Procedure

1. **Zero-Downtime Rolling Deployment:**
   - Coolify executes rolling container replacement:
     1. Build new container image from `main`.
     2. Start candidate container and await HTTP 200 on `/health` and `/ready` healthchecks.
     3. Traefik automatically switches ingress routes from old container (`4cdc04ccb16b`) to the new container.
     4. Terminate old container.
   - **Expected Downtime:** **0.00 seconds (Zero Downtime)**.
2. **Live Trading Prohibition Safeguard:**
   - The environment variable `CBE_TRADING_DISABLED=true` remains hardcoded in Dockerfile and entrypoint script.
   - Any order execution request receives immediate HTTP 403 Forbidden.

---

## 6. Rollback Plan

If any anomaly is detected post-deployment:
1. **Immediate Container Rollback via Coolify UI:**
   - Navigate to Coolify Dashboard -> `coin-davranis-motoru` -> Deployments.
   - Select previous healthy deployment commit `c9e3907a226cfbe01e73f87c960156afdd874dc4`.
   - Click "Redeploy".
   - Rollback completes in $< 30$ seconds.
2. **Git Rollback:**
   - If `main` was merged via fast-forward:
     `git push origin +c9e3907a226cfbe01e73f87c960156afdd874dc4:main`
   - Coolify auto-deploys the restored commit.

---

## 7. Operator Approval Checklist

Before merging to `main` and initiating deployment, the operator must verify:

- [ ] **Gate A:** Portfolio accounting matches authoritative ledgers ($\sum \text{fees} = \$2,685.40 / \$1,403.15$, Max DD $= -28.94\% / -25.66\%$).
- [ ] **Gate B:** Statistical evidence classified as `STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED` for returns and `DESCRIPTIVE_HISTORICAL_FINDING` for MAE risk.
- [ ] **Gate C:** Complete repository regression suite passes with `FAILED=0`.
- [ ] **Gate D:** October 2026 verified partial (24h), November 2026 missing (`VERİ HENÜZ MEVCUT DEĞİL`), zero synthetic candles.
- [ ] **Gate E:** Staging deployment verified on `srv1114257:18080`, Playwright multi-viewport tests passed, production container `4cdc04ccb16b` untouched.
