# CBE — Product Acceleration 01 Deployment Readiness Audit
## Coolify Infrastructure, Container Packaging & Staging Workflow

**Repository:** `selimoyan2/coin-behavior-engine`  
**Base Commit:** `2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9`  
**Infrastructure Domain:** `coin.ozelweb.com.tr`  
**Execution Status:** STOPPED BEFORE DEPLOYMENT — AWAITING OPERATOR AUTHORIZATION  
**Date:** 2026-10-23  

---

### 1. Existing Coolify Infrastructure Inventory

The deployment architecture is managed via Coolify on a Linux VPS:

| Service Name | Compose File | Target Port | Role | Current Status |
| :--- | :--- | :--- | :--- | :--- |
| `coin-behavior-engine` | `docker-compose.yml` (Root) | `8000:8000` | Main production web monitoring server | Configured / Dormant |
| `cbe-market-intelligence-staging` | `deploy/staging/docker-compose.market-intelligence-staging.yaml` | `127.0.0.1:8080:8000` | Hardened read-only staging container | Configured / Recommended for Staging Validation |
| `cbe-080-shadow-inert` | `deploy/shadow_v080/docker-compose.coolify-inert.yaml` | None | One-shot inert environment verifier | Verified in Sprint 09.13 |
| `cbe-080-live-capture` | `deploy/shadow_v080/docker-compose.coolify-live-capture.yaml` | None | Dedicated spot market capture worker | Fail-Closed (Approval 3 Pending) |

---

### 2. Container Build & Packaging Compatibility

The root [`Dockerfile`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/Dockerfile) and staging templates were analyzed for compatibility with the new Product Dashboard:

1. **Python Runtime:** `python:3.11-slim`
2. **Zero Node/NPM Runtime Dependency:**
   The frontend is implemented purely in native modern HTML5, CSS3, and vanilla JS (`client.js`). It requires **no Node.js build step, no npm install, and no webpack/vite bundling**.
   This guarantees that building the Docker image or running the staging container in Coolify requires **zero internet asset fetching** beyond Python wheels.
3. **Read-Only Root Filesystem:**
   The staging configuration enforces `read_only: true`. The new `ProductDashboardApiService` and `dashboard_ui.py` perform **zero filesystem writes**, adhering 100% to immutable container requirements.
4. **Health Check Compatibility:**
   `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1` passes in sub-millisecond time.

---

### 3. Environment Variables Verification

The required environment variables for the Product Dashboard and Market Intelligence server:

| Variable | Recommended Staging Value | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8000` | HTTP listening port inside container |
| `HOST` | `0.0.0.0` | Container network bind address |
| `PYTHONUNBUFFERED` | `1` | Immediate stdout/stderr flush for Docker logs |
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevents `.pyc` creation on read-only filesystems |
| `CBE_ENV` | `staging` | Runtime environment classification |
| `CBE_TRADING_DISABLED` | `true` | Hard software interlock prohibiting order execution |
| `CBE_PROSPECTIVE_OBSERVATION_ENABLED` | `false` | Disables unattended background worker |
| `CBE_APPROVAL_4_AUTHORIZED` | `false` | Suppresses unvalidated prospective scoring |
| `START_WORKER` | `false` | Enforces read-only HTTP server mode |

*Note: No sensitive secrets, private keys, or API tokens are required or permitted in the environment.*

---

### 4. Zero Data Loss & Rollback Runbook

1. **Production Data Protection:**
   - All mounts to `cbe_live_capture_data` and `data/` remain strictly `:ro` (read-only).
   - No database schemas are altered or migrated.
2. **Rollback Procedure:**
   If any regression is detected upon staging activation:
   ```bash
   # Step 1: Stop staging container
   docker compose -f deploy/staging/docker-compose.market-intelligence-staging.yaml down

   # Step 2: Rollback to previous known-good commit
   git checkout 2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9

   # Step 3: Verify clean container state
   docker ps -a | grep cbe
   ```

---

### 5. Deployment Authorization Status

```
COOLIFY DEPLOYMENT DECISION: NOT_ATTEMPTED_UNLESS_AUTHORIZED
CURRENT ACTION: STOPPED BEFORE MUTATION
OPERATOR APPROVAL REQUEST: Awaiting formal operator confirmation before staging deploy.
```
