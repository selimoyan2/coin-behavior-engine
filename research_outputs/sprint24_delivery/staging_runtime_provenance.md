# Staging Runtime Provenance — Sprint 24 Deployment
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Deployment Target:** Authorized Staging (`srv1114257:18080`)
**Host IP:** `168.231.125.238`
**Deployment Timestamp:** 2026-11-09T20:59:35Z
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY FROZEN)

---

## 1. Container & Image Identity

| Attribute | Verified Value |
| :--- | :--- |
| **Container ID** | `432b095da253` |
| **Container Name** | `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942` |
| **Image Tag** | `cbe-market-intelligence:sprint24-061a9e72386542ca895b01b3da75b4cc9d0e734f` |
| **Image SHA-256 ID** | `sha256:cfafdde60cdea486cebae3b33f16fffe164e3ff78b2d715e0281d9ef788211e1` |
| **Base Image** | `python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535` |
| **Build Host Directory** | `/tmp/cbe_sprint19_build` |
| **Source Commit SHA** | `061a9e72386542ca895b01b3da75b4cc9d0e734f` |
| **Staging Port** | `127.0.0.1:18080 -> 8000/tcp` |

---

## 2. Mounts & Storage Durability

| Mount Destination | Mount Type | Source / Volume Name | Verification Status |
| :--- | :--- | :--- | :--- |
| `/app/data/live_capture` | Volume (ro) | `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` | **MOUNTED_RO** |
| `/app/data/prospective` | Volume (rw) | `dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f` | **PERSISTENT_VERIFIED** |
| `/tmp` | tmpfs (rw,noexec,nosuid) | 64MB memory-backed tmpfs | **VERIFIED** |
| `/run` | tmpfs (rw,noexec,nosuid) | 16MB memory-backed tmpfs | **VERIFIED** |
| `/` (Root Filesystem) | rootfs | Read-Only container overlay | **READ_ONLY_ENFORCED** |

---

## 3. Verified Health & Governance Status

```json
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
