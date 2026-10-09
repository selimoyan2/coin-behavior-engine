# OPERATOR RUNBOOK: ISOLATED COOLIFY INERT SERVICE READINESS (APPROVAL 2)

> [!CAUTION]
> **PREPARATION & REVIEW ONLY — DO NOT EXECUTE WITHOUT EXPLICIT APPROVAL 2**
> This runbook is a prospective operational specification. It does NOT authorize deployment.
> No containers, networks, volumes, or services may be created in Coolify until the human operator has reviewed and explicitly approved this procedure.

---

## 1. OBJECTIVE & SAFETY ARCHITECTURE

This runbook defines the exact, fail-closed procedure for landing an **isolated, inert staging container** for **CBE-0.8.0** within the operator's existing Coolify instance on host `srv1114257`.

### Core Architectural Distinctions

```
+-----------------------------------------------------------------------------------+
| SHARED LINUX VPS (srv1114257)                                                     |
|                                                                                   |
|  [ PRODUCTION WORKSPACE ]                 [ CBE-0.8.0 SHADOW STAGING (INERT) ]   |
|  CBE-0.7.0 Service (Coolify App)          cbe_080_coolify_inert (approval-2)     |
|  - SQLite DB / Production State           - Zero Database Access                 |
|  - Active API / Worker Feeds              - Zero Network (network_mode: none)    |
|  - Coolify Managed Network                - Read-Only Root Filesystem            |
|  - Unaffected by Shadow Staging           - Exits 0 upon Inert Safety Check      |
|                                           - 0 MB RAM / 0% CPU Consumption at Rest|
+-----------------------------------------------------------------------------------+
```

1. **Inert Landing vs Active Worker:**
   - **Inert Landing (Approval 2):** Container executes safety contract verification (`deploy_safety.py`), audits zero network / zero prospective / zero trading, and cleanly terminates with `exit 0` (or stays strictly stopped). At rest, it consumes **0 MB RAM and 0% CPU**.
   - **Continuous Observation Worker:** Polling Binance and generating prospective scores is **STRICTLY PROHIBITED** and blocked by fail-closed software interlocks. (Requires subsequent APPROVAL 3 for Binance feed and APPROVAL 4 for prospective scoring).
2. **Zero Production Mutation:** The service operates in complete isolation: no shared volumes, no shared databases, no shared network bridge.

---

## 2. PRE-DEPLOYMENT PREREQUISITE CHECKS

Before initiating any action in Coolify, the operator must verify:

1. **Git Commit Baseline:**
   ```bash
   git rev-parse HEAD
   # Must return verified baseline commit
   ```
2. **Canonical Freeze Verification:**
   ```bash
   python3 -c "from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze; print(verify_sprint07_freeze()['status'])"
   # Must output: FREEZE_VERIFIED (29/29)
   ```
3. **VPS Host Capacity Check:**
   ```bash
   free -h
   docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Size}}" | wc -l
   # Ensure >= 2.0 GiB available RAM and host stability
   ```

---

## 3. REQUIRED COOLIFY SERVICE CONFIGURATION

When configuring the service in the Coolify UI dashboard:

| Setting Category | Configuration Parameter | Required Value / Policy |
| :--- | :--- | :--- |
| **Service Type** | Service Blueprint | **Docker Compose** |
| **Compose Source** | Path in Repository | `deploy/shadow_v080/docker-compose.coolify-inert.yaml` |
| **Deployment Mode** | Auto Deploy | **DISABLED** (Manual deployments only) |
| **Webhooks** | Git Push Webhook | **DISABLED** |
| **Domains / Routing** | FQDN / Traefik Routing | **NONE** (Leave completely blank) |
| **Port Mapping** | Published Ports | **NONE** (Zero ports exposed) |
| **Health Check** | Type | **None** or `/bin/true` |
| **Restart Policy** | Container Restart | **Never / No (`restart: "no"`)** |
| **Memory Limit** | Hard Memory Ceiling | **300 MB** (`mem_limit: 300m`) |
| **CPU Limit** | Quota | **0.25 CPU** (`cpus: 0.25`) |
| **PIDs Limit** | Process Threads Ceiling | **64** (`pids_limit: 64`) |
| **Log Driver** | Rotation Policy | `json-file`, max 10MB x 3 files |

---

## 4. ENVIRONMENT VARIABLE CONTRACT (FAIL-CLOSED)

The following environment variables are baked into `docker-compose.coolify-inert.yaml` and verified at runtime:

```dotenv
CBE_ENV=staging_coolify_inert
PYTHONUNBUFFERED=1
CBE_RECORD_LABEL=WARMUP_REPLAY
CBE_PROSPECTIVE_OBSERVATION_ENABLED=false
CBE_BINANCE_COLLECTION_ENABLED=false
CBE_ENFORCE_PROSPECTIVE_GUARD=true
CBE_TRADING_DISABLED=true
CBE_SHADOW_DATA_DIR=/app/data/prospective_shadow
```

> [!IMPORTANT]
> If any operator or script attempts to set `CBE_BINANCE_COLLECTION_ENABLED=true` without separate **APPROVAL 3**, or `CBE_PROSPECTIVE_OBSERVATION_ENABLED=true` without separate **APPROVAL 4**, the container entrypoint immediately triggers `SAFETY_HALT` and exits with code 1 (`FAILED_SAFE`).

---

## 5. OPERATOR DEPLOYMENT PROCEDURE (UPON EXPLICIT APPROVAL 2 ONLY)

> **REMINDER: DO NOT EXECUTE BEFORE OPERATOR SIGNOFF.**

### Step 1: Import Service Definition in Coolify
1. Navigate to Coolify Dashboard $\to$ **Projects** $\to$ Select Target Environment.
2. Click **+ New Resource** $\to$ **Docker Compose**.
3. Select Git repository `selimoyan2/coin-behavior-engine` and branch `main`.
4. Point to Compose file: `deploy/shadow_v080/docker-compose.coolify-inert.yaml`.
5. Under Application Settings, verify:
   - **Auto deploy:** Manual deployments only.
   - **Domains:** Empty.
   - **Healthcheck:** Disabled.

### Step 2: Trigger Manual Initial Build & Landing
1. Click **Deploy** manually.
2. Coolify builds `cbe-080-shadow:coolify-inert` using `deploy/shadow_v080/Dockerfile.staging`.
3. The container starts, executes `entrypoint_inert.sh`, verifies all safety interlocks, writes audit JSON, and terminates cleanly with exit code 0 (`Exited (0)`).

---

## 6. POST-DEPLOYMENT INERT STATE VERIFICATION

Execute the following commands on `srv1114257` to confirm the container landed inert:

1. **Verify Container Status:**
   ```bash
   docker ps -a --filter "name=cbe_080_coolify_inert" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
   # Expected status: Exited (0)
   ```

2. **Verify Zero Host Resource Consumption:**
   ```bash
   docker stats --no-stream cbe_080_coolify_inert
   # When exited/stopped: 0B / 0B (0.00% CPU, 0.00% MEM)
   ```

3. **Verify Inert Safety Audit Logs:**
   ```bash
   docker logs cbe_080_coolify_inert
   # Look for:
   # [DeploySafety] Verification Status: PASS
   # [DeploySafety] Lifecycle State: DEPLOYED_INERT
   # [DeploySafety] Trading Disabled: True
   # [DeploySafety] Prospective Scoring Disabled: True
   # [DeploySafety] Binance Collection Disabled: True
   # [DeploySafety] Network Isolation Confirmed: True
   # [DeploySafety] INERT LANDING VERIFICATION SUCCESSFUL (EXIT CODE 0)
   ```

4. **Verify Network Isolation (Zero Sockets):**
   ```bash
   docker inspect cbe_080_coolify_inert --format '{{.HostConfig.NetworkMode}}'
   # MUST RETURN: none
   ```

5. **Verify CBE-0.7.0 Production is 100% Intact:**
   ```bash
   # Check CBE-0.7.0 container status and databases
   docker ps --filter "name=coin-behavior-engine" --format "table {{.Names}}\t{{.Status}}"
   ls -la /opt/coin-behavior-engine/data/prospective/
   # Confirm timestamps and processes are completely unaffected
   ```

---

## 7. ROLLBACK & REMOVAL PROCEDURE

If any discrepancy or unintended behavior is observed:

1. **Stop & Remove Container Immediately:**
   ```bash
   docker stop cbe_080_coolify_inert || true
   docker rm -v cbe_080_coolify_inert || true
   ```
2. **Remove Isolated Volume (If Needed):**
   ```bash
   docker volume rm cbe_080_shadow_data || true
   ```
3. **Delete Coolify Service Resource:**
   In the Coolify dashboard, select the `cbe-080-shadow-inert` service $\to$ **Settings** $\to$ **Delete Resource**.
4. Confirm CBE-0.7.0 production operation remains normal.
