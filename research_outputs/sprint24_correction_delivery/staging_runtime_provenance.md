# Staging Runtime Provenance & Deployment Certification
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Governance Decision:** `TECHNICAL_NO_GO`

---

## 1. Staging Host & Runtime Identity

* **Authorized Remote Host:** `srv1114257` (`168.231.125.238`)
* **Operating System:** Linux Debian GNU/Linux 13 (trixie)
* **Docker Engine:** Version 29.9.1, build dfc520d
* **Staging Service Container Name:** `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942`
* **Staging Container ID:** `7e6268bbd2a7`
* **Staging Image Name & Tag:** `cbe-market-intelligence:sprint24-correction-54c43cdceedf22214bb0f01cb908b8ba6fabe48e`
* **Internal Image SHA-256:** `sha256:e2360b502269ae0325919e0cb1d01fb5f964245f14efc6911fd802db411c0ebd`
* **Staging Port Binding:** `127.0.0.1:18080 -> 8000/tcp`
* **Build Directory on Host:** `/tmp/cbe_sprint19_build` (verified at HEAD `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`)
* **Compose File Path:** `/data/coolify/applications/dzzfws54by1whlbq6fk4ywut/docker-compose.yaml`

---

## 2. Authorized Storage Volume Mounts

* **Prospective Research Data (Read-Write Persistent Volume):**
  * Volume Name: `dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f`
  * Container Path: `/app/data/prospective`
  * Verified Filesystem: `ext4`
  * Durability Status: `PERSISTENT_VERIFIED`
* **Live Capture Data (Read-Only Volume):**
  * Volume Name: `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`
  * Container Path: `/app/data/live_capture:ro`
* **Tmpfs Mounts:**
  * `/tmp`: 64 MB (rw, noexec, nosuid)
  * `/run`: 16 MB (rw, noexec, nosuid)

---

## 3. Live Staging Verification Outputs

### 3.1 Health & Readiness Probes (`http://127.0.0.1:18080`)
```json
// GET /health
{
  "status": "healthy",
  "service": "coin-behavior-engine",
  "model_version": "CBE-0.7.0",
  "model_status": "FROZEN",
  "freeze_verified": true,
  "worker_status": "RUNNING",
  "hash_chain_valid": true,
  "last_processed_bar": "2026-09-24T13:15:00Z",
  "prediction_count": 2,
  "uptime_seconds": 3.8
}

// GET /ready
{
  "status": "READY",
  "service": "coin-behavior-engine",
  "canonical_model_version": "CBE-0.7.0",
  "canonical_model_status": "STRICTLY_FROZEN",
  "governance_decision": "TECHNICAL_NO_GO",
  "parameter_mutations": 0,
  "directional_trading": "STRICTLY_PROHIBITED",
  "live_order_execution": "PERMANENTLY_PROHIBITED",
  "storage_durability": "PERSISTENT_VERIFIED",
  "storage_writable": true,
  "environment": "staging"
}
```

### 3.2 Dynamic Revalidation of Saved Comparisons
Live query to `/api/v1/product/workspace/overview` confirmed that existing legacy comparison `CMP-C0A448A7F8A0` was dynamically re-evaluated and marked `REVALIDATION_FAILED` due to `SAMPLING_CADENCE_MISMATCH`.

### 3.3 Live Comparison Gate Execution on Staging
* **Compatible Pair (`["RES-REGIME-01", "RES-ANALOG-01"]`):**
  * `HTTP Status:` `200 OK`
  * `is_compatible:` `true`
  * `rejection_code:` `null`
  * `difference_analysis:` Computed successfully with mandatory disclaimer.
* **Cadence Mismatch (`["RES-FUND-01", "RES-REGIME-01"]`):**
  * `HTTP Status:` `200 OK`
  * `is_compatible:` `false`
  * `rejection_code:` `SAMPLING_CADENCE_MISMATCH`
  * `difference_analysis:` `[]` (suppressed).
* **Quarantined Record (`["RES-REGIME-01", "RES-CRYPTO-01"]`):**
  * `HTTP Status:` `200 OK`
  * `is_compatible:` `false`
  * `rejection_code:` `QUARANTINED_RECORD`
  * `difference_analysis:` `[]` (suppressed).
