# SPRINT 35 — PRODUCTION RELEASE & ROLLBACK PLAN

**Target Release:** CBE Release Candidate V12 (`CBE-RC-SPRINT35-V12`)  
**Target Environment:** Coolify Production (`https://coin.ozelweb.com.tr`, port 8000)  
**Governance Condition:** STRICT_ZERO_TOUCH — Execution requires explicit human operator action  

---

## 1. Release Prerequisites (All Verified)
- [x] Full regression test suite passes with `FAILED = 0`.
- [x] Staging container (`srv1114257:18080`) built and validated across desktop, tablet, and mobile.
- [x] Importer security audit passes (zero path traversal, zero candle physics violations).
- [x] October 2026 dataset 100% complete and verified across all 5 timeframes.
- [x] November 2026 dataset registered with verified cutoff (15 Nov 21:15 UTC) and zero synthetic candles.
- [x] Live trading endpoints permanently respond with HTTP 403 Forbidden.

---

## 2. Operator Release Execution Steps

When the operator decides to release Sprint 35 to production:

### Step 1: Remote Git Fast-Forward Merge
From the operator's authorized environment:
```bash
git checkout main
git pull origin main
git merge --ff-only research/sprint33-canonical-bridge-market-intelligence
git push origin main
```

### Step 2: Trigger Coolify Production Deployment
- In the Coolify Dashboard: navigate to application `6t63aehpaw0cw1bbt4zcm09g` (`coin.ozelweb.com.tr`).
- Click **Deploy** (or trigger the production webhook).
- Coolify will pull the updated `main` branch containing the 59 monthly partitions and Dashboard V12.

### Step 3: Production Post-Deployment Verification
Verify HTTP 200 on main entry points and HTTP 403 on trading endpoints:
```bash
curl -I https://coin.ozelweb.com.tr/
curl -I "https://coin.ozelweb.com.tr/api/v1/product/historical-candles?interval=5m&month=2026-11"
curl -X POST https://coin.ozelweb.com.tr/api/v1/order/execute # Expect HTTP 403
```

---

## 3. Rollback Procedure

If any anomaly occurs in production after release:

```bash
git checkout main
git reset --hard c9e3907a226cfbe01e73f87c960156afdd874dc4
git push origin main --force
```
Trigger Coolify redeployment to immediately restore the Sprint 33 production baseline.
