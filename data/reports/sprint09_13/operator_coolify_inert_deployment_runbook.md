# OPERATOR RUNBOOK: ISOLATED COOLIFY INERT SERVICE READINESS (APPROVAL 2)

> [!CAUTION]
> **PREPARATION & REVIEW ONLY — DO NOT EXECUTE WITHOUT EXPLICIT APPROVAL 2**
> This runbook is an operational specification. It does NOT authorize deployment.
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
   - **Inert Landing (Approval 2):** Container executes safety contract verification (`deploy_safety.py`), audits zero network / zero prospective / zero trading, writes persistent audit JSON, and terminates cleanly with `exit 0` (`STOPPED`). At rest, it consumes **0 MB RAM and 0% CPU**.
   - **Continuous Observation Worker:** Polling Binance and generating prospective scores is **STRICTLY PROHIBITED** and blocked by fail-closed software interlocks. (Requires subsequent APPROVAL 3 for Binance feed and APPROVAL 4 for prospective scoring).
2. **Safe By Default Image:** The image's default `CMD` runs `/app/entrypoint_inert.sh`. Accidental invocation without arguments executes the inert verification and exits 0; it never executes the 850-cycle benchmark or any collector.
3. **Zero Production Mutation:** The service operates in complete isolation: no shared volumes, no shared databases, no shared network bridge.

---

## 2. COOLIFY COMPATIBILITY BOUNDARIES & UNCERTAINTIES

> [!IMPORTANT]
> **Verification Separation:**
> - **Static Validation (CI / Repository):** Compose syntax, YAML schema, resource limits, and environment variable contracts are verified offline in automated tests.
> - **Local Container Sandbox (Offline):** Image build, read-only root, non-root user, and exit-code behavior are verified in local Docker tests.
> - **Coolify Operator Verification (Pending Approval 2):** Actual execution within Coolify on `srv1114257` has **NOT** been executed yet and must be verified by the human operator.

### Documented Coolify Uncertainties Requiring Operator Inspection
1. **Docker Compose Profile Behavior:** In standard Docker Compose, services with `profiles: ["manual"]` are ignored unless `--profile manual` is passed. Because Coolify executes `docker compose up -d` without custom profile flags by default, `profiles: ["manual"]` has been omitted from `docker-compose.coolify-inert.yaml`. Manual deployment control is instead enforced via Coolify's native **`Auto deploy = Manual deployments only`** setting, and background execution is prevented via **`restart: "no"`** and the one-shot inert entrypoint.
2. **`network_mode: "none"` Support:** Coolify typically attaches containers to an internal bridge network (`coolify`) for reverse-proxy routing. With `network_mode: "none"`, Docker disables all external networking. The operator must verify that Coolify does not reject the compose file or force a secondary network attachment.
3. **Exited Container Display:** Because the inert container terminates with code 0 after verifying safety, Coolify will display the service as `Exited (0)` or `Stopped`. This is the intended quiescent state.
4. **Build Context Resolution (`--project-directory`):** Coolify executes `docker compose --project-directory <checkout> -f <checkout>/deploy/shadow_v080/docker-compose.coolify-inert.yaml build`. Under Docker Compose specification, `--project-directory` defines the base directory for resolving relative paths in `build.context`. Setting `build.context: .` anchors the build context directly to the repository root `<checkout>`, allowing `dockerfile: deploy/shadow_v080/Dockerfile.staging` and all build inputs (`src/`, `data/models/`, `entrypoint_inert.sh`) to resolve without directory traversal errors.

---

## 3. PRE-DEPLOYMENT PREREQUISITE CHECKS

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

## 4. REQUIRED COOLIFY SERVICE CONFIGURATION

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

## 5. ENVIRONMENT VARIABLE CONTRACT (FAIL-CLOSED)

The following exact values are baked into `docker-compose.coolify-inert.yaml` and strictly enforced by `deploy_safety.py`:

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

> [!CAUTION]
> Every variable is validated using **exact string matching**. If any variable is missing, empty, or set to an unapproved value (e.g. attempting to enable Binance or prospective observation), the container entrypoint immediately halts with code 1 (`FAILED_SAFE`).

---

## 6. OPERATOR DEPLOYMENT PROCEDURE (UPON EXPLICIT APPROVAL 2 ONLY)

> **REMINDER: DO NOT EXECUTE BEFORE EXPLICIT OPERATOR APPROVAL.**

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
1. Click **Deploy** manually in Coolify.
2. Coolify builds `cbe-080-shadow:coolify-inert` using `deploy/shadow_v080/Dockerfile.staging`.
3. The container starts, executes `entrypoint_inert.sh`, verifies all safety interlocks, writes audit JSON to `/app/data/prospective_shadow/audit/coolify_inert_landing_audit.json`, and terminates cleanly with exit code 0 (`Exited (0)`).

---

## 7. POST-DEPLOYMENT INERT STATE VERIFICATION

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

4. **Verify Authoritative Docker Host Isolation & Security Settings:**
   ```bash
   # Network Isolation: MUST BE 'none'
   docker inspect cbe_080_coolify_inert --format '{{.HostConfig.NetworkMode}}'
   
   # Read-Only Root Filesystem: MUST BE 'true'
   docker inspect cbe_080_coolify_inert --format '{{.HostConfig.ReadonlyRootfs}}'
   
   # Non-Root User Identity: MUST BE '1000:1000'
   docker inspect cbe_080_coolify_inert --format '{{.Config.User}}'
   
   # Volume Mount Configuration: Ensure cbe_080_shadow_data is mounted read-write to /app/data/prospective_shadow
   docker inspect cbe_080_coolify_inert --format '{{range .Mounts}}{{println .Type .Name .Destination .RW}}{{end}}'
   ```

5. **Verify Persistent Audit Evidence in Volume:**
   The inert verification creates two audit artifacts in the volume:
   - `coolify_inert_landing_audit.json`: Atomic latest audit report with cryptographic checksum.
   - `coolify_inert_landing_history.jsonl`: Append-only, bounded history (max 500 entries) retaining the genesis record and newest runs.

   ```bash
   # Inspect latest audit summary
   docker run --rm -v cbe_080_shadow_data:/data:ro alpine cat /data/audit/coolify_inert_landing_audit.json

   # Inspect audit history entries count
   docker run --rm -v cbe_080_shadow_data:/data:ro alpine wc -l /data/audit/coolify_inert_landing_history.jsonl
   ```

6. **Volume Permission Semantics & Operator Recovery:**
   - **First-Start Behavior:** Docker initializes an empty named volume with the ownership of the underlying image directory (`/app/data/prospective_shadow`, configured in `Dockerfile.staging` as `cbe:cbe` UID/GID `1000:1000`).
   - **Existing Volume Safety:** If the volume was previously created or accessed by `root`, it may be owned by `0:0`. If UID 1000 cannot write to it, `deploy_safety.py` detects this fail-closed and aborts with `VOLUME_PERMISSION_DENIED` (exit code 1).
   - **Operator Recovery Procedure (if volume permission error occurs):**
     ```bash
     # Fix ownership to non-root UID:GID 1000:1000
     docker run --rm -v cbe_080_shadow_data:/data alpine chown -R 1000:1000 /data
     ```

7. **Verify CBE-0.7.0 Production is 100% Intact:**
   ```bash
   # Check CBE-0.7.0 container status and databases
   docker ps --filter "name=coin-behavior-engine" --format "table {{.Names}}\t{{.Status}}"
   ls -la /opt/coin-behavior-engine/data/prospective/
   # Confirm timestamps and processes are completely unaffected
   ```

---

## 8. SAFE ROLLBACK & RESOURCE REMOVAL PROCEDURE

If any discrepancy or unintended behavior is observed, use Coolify-managed lifecycle operations first:

1. **Step 1: Coolify UI Stop**
   In the Coolify dashboard, select `cbe-080-shadow-inert` and click **Stop**.

2. **Step 2: Verify Identity Before Any Deletion**
   Verify the exact container ID and name before executing any operation:
   ```bash
   docker inspect cbe_080_coolify_inert --format 'Name: {{.Name}} | Image: {{.Config.Image}} | State: {{.State.Status}}'
   ```

3. **Step 3: Coolify UI Resource Deletion**
   In the Coolify dashboard, navigate to **Settings** $\to$ **Delete Resource**. Coolify cleanly deregisters the service and stops the container without risking production containers.

4. **Step 4: Audit Volume Preservation vs Manual Cleanup**
   - **Recommended:** Retain named volume `cbe_080_shadow_data` to preserve the cryptographic audit trail `coolify_inert_landing_audit.json`.
   - **Manual Volume Deletion (Only if explicitly required by operator):**
     Confirm volume identity before deletion:
     ```bash
     docker volume inspect cbe_080_shadow_data --format 'Volume Name: {{.Name}} | Driver: {{.Driver}}'
     # ONLY delete after confirming it is NOT a production volume:
     docker volume rm cbe_080_shadow_data
     ```

5. **Step 5: Verify Production Health**
   Confirm CBE-0.7.0 production containers and SQLite databases continue normal operations.
