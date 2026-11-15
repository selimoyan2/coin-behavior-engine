# SPRINT 35 — PRODUCTION RELEASE & ROLLBACK PLAN

**Target Release:** CBE Release Candidate V12 (`CBE-RC-SPRINT35-V12`)  
**Target Environment:** Coolify Production (`https://coin.ozelweb.com.tr`, port 8000)  
**Governance Condition:** `STRICT_ZERO_TOUCH` — Execution requires explicit human operator action. No automatic deployment.  
**Verified Candidate Commit:** `4724a3a57117fabff91229130f836b7af0b71677`  
**Verified Baseline (`main`):** `c9e3907a226cfbe01e73f87c960156afdd874dc4`  

---

## 1. Release Prerequisites & Invariants (All Verified)

- [x] **Git Lineage Parity:** `git merge-base origin/main HEAD` strictly equals `c9e3907a226cfbe01e73f87c960156afdd874dc4`. Research branch is a strict linear descendant (13 commits ahead, 0 divergence). Fast-forward merge (`--ff-only`) is 100% clean.
- [x] **Full Regression Test Suite:** 3,627 passed, 0 failed, 8 skipped.
- [x] **Container Image Validation:** Docker image contains all 295 Parquet files across all 5 intervals (5m: 59, 15m: 59, 1h: 59, 4h: 59, 1d: 59), physically verified inside container.
- [x] **Multi-Viewport UI Acceptance:** Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) verified with 0 console errors and 0 page errors.
- [x] **Historical Data Provenance:** October 2026 is 100% complete (8,928 bars, 0 gaps, 0 synthetic). November 2026 is registered up to verified cutoff (2026-11-15 21:15 UTC) with 8 physical missing bars documented (0 synthetic).
- [x] **Governance Enforcement:** Live trading endpoints permanently respond with HTTP 403 Forbidden (`GOVERNANCE_VIOLATION`).

---

## 2. Image Digests & Provenance Ledger

| Environment | Tag | Docker Image ID | Verified Port | Status |
|---|---|---|---|---|
| **Production Current (Baseline)** | `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4` | `sha256:6969f8cb761cb01fc783c1ffbb2b896be8c98f975ed9a438e5d02b4c4820047f` | 8000 | Active, 0 Restarts |
| **Staging Candidate (Sprint 35)** | `cbe-market-intelligence:sprint35-ec7d393` | `sha256:20e9fe8ac295326c9f43959bff36bbc16993305003a6abd6fcf6dfbdb49784d2` | 18080 | Active, Healthy |

---

## 3. Operator Release Execution Steps

When authorized operator approval is granted:

### Step 1: Safe Fast-Forward Merge to `main`
```bash
git checkout main
git pull origin main
# Verify fast-forward compatibility
git merge --ff-only research/sprint33-canonical-bridge-market-intelligence
# Push clean linear history (NO FORCE PUSH)
git push origin main
```

### Step 2: Trigger Coolify Production Deployment
1. Log in to Coolify UI (`https://coolify.ozelweb.com.tr` or server panel).
2. Navigate to Application `6t63aehpaw0cw1bbt4zcm09g` (`coin.ozelweb.com.tr`).
3. Click **Deploy** to build and spin up the new container from `main`.
4. Coolify performs healthcheck (`/health`) on the new container before updating Traefik routing, ensuring zero downtime.

### Step 3: Production Post-Deployment Verification
Verify HTTP 200 on API endpoints and HTTP 403 on trading endpoints:
```bash
curl -I https://coin.ozelweb.com.tr/health
curl -s "https://coin.ozelweb.com.tr/api/v1/product/available-dates?interval=5m" | jq '.latest_month, .total_months'
curl -I "https://coin.ozelweb.com.tr/api/v1/product/historical-candles?interval=5m&month=2026-10"
curl -I "https://coin.ozelweb.com.tr/api/v1/product/historical-candles?interval=5m&month=2026-11"
# Verify live trading prohibition
curl -s -X POST https://coin.ozelweb.com.tr/api/v1/product/order/execute # Expect HTTP 403 Forbidden
```

---

## 4. Safe Production Rollback Procedures (No Force Push)

If any anomaly occurs in production after release, the operator can execute either of the two safe, non-destructive rollback options:

### Option A: Instant Coolify Image Rollback (Fastest & Safest - Tested on Staging)
Because Coolify preserves prior container images on `srv1114257`:
1. In Coolify UI under **Deployments**, locate the prior successful deployment (`6t63aehpaw0cw1bbt4zcm09g-20261115T212024`).
2. Click **Redeploy** (or point the image tag back to `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4`).
3. Service is restored to the Sprint 33 baseline in < 5 seconds without altering git history.
*(This exact image was verified on staging port 18081, booting in 3 seconds and serving 57 months).*

### Option B: Safe Git Revert (Clean History Preservation)
If repository rollback is required on GitHub:
```bash
git checkout main
git pull origin main
# Create forward revert commits preserving full audit trail
git revert --no-edit c9e3907a226cfbe01e73f87c960156afdd874dc4..HEAD
git push origin main
```
> [!IMPORTANT]
> `git push --force` and `git reset --hard` on production branches are strictly forbidden. Git history remains strictly append-only.
