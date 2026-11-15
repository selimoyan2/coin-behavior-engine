# 01. Git & Runtime Baseline Audit — Sprint 34.1 Forensic Report

**Sprint ID:** `CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS`  
**Execution Timestamp:** 2026-11-15T22:08:00+03:00  
**Verification Target:** Git HEAD SHA, Remote Server Runtimes, Coolify Tracking Configuration, UI State Discrepancy  

---

## 1. Executive Summary

This forensic audit resolves the apparent discrepancy where the user redeployed the application in Coolify but observed market data terminating at **September 30, 2026** with the Turkish annotation **"(Henüz Doğrulanmadı)"** for October 2026.

The root cause has been conclusively identified through container inspection, environment variable verification, and git ref auditing:
1. **Branch Misalignment in Coolify:** The production Coolify application (`6t63aehpaw0cw1bbt4zcm09g`) is explicitly configured to track `origin/main` (`COOLIFY_BRANCH=main`, `SOURCE_COMMIT=c9e3907a226cfbe01e73f87c960156afdd874dc4`), not the research development branch (`research/sprint33-canonical-bridge-market-intelligence`).
2. **Main Branch Contents:** In `main`, the dataset ends at `2026-09`, `BTCUSDT-1h-2026-10.parquet` does not exist, and `dashboard_ui.py` contains hardcoded fallbacks to `'2026-09'` and the string `' (Henüz Doğrulanmadı)'`.
3. **Production Isolation & Zero-Touch Compliance:** In Sprint 33 and Sprint 34, research code and data updates were deployed strictly to the authorized **Staging Runtime** (`srv1114257:18080`), adhering to `STRICT_ZERO_TOUCH` on the production container (port 8000). The user's manual redeploy in Coolify pulled `main`, building container `0688330c7292` from `main`, exactly preserving the September 30, 2026 baseline.

---

## 2. Git & Runtime Environment Comparison

| Attribute | Research Branch Workspace | Staging Runtime (`srv1114257:18080`) | Production Runtime (`coin.ozelweb.com.tr` / 8000) |
|---|---|---|---|
| **Git Branch** | `research/sprint33-canonical-bridge-market-intelligence` | `research/sprint33-...` (staged build) | `main` |
| **Commit SHA (40-char)** | `82de95a29d4154acb7ec35598f1b33a9d5250a63` | `957e0d3b9af921c874b4d174738044c471465bf1` (Sprint 34 staging) | `c9e3907a226cfbe01e73f87c960156afdd874dc4` |
| **Container ID** | N/A (Local / Dev) | `6573abbd05f4` | `0688330c7292` (Predecessor: `4c6a29b5fbf6`) |
| **Container Name** | N/A | `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261115T161624` | `6t63aehpaw0cw1bbt4zcm09g-20261115T170526` |
| **Managed By** | Local Git | Authorized Staging Deployment Harness | Coolify 4.7.5 (`coolify.applicationUuid: 6t63aehpaw0cw1bbt4zcm09g`) |
| **Network / Ingress** | N/A | `127.0.0.1:18080` (Direct SSH tunnel / curl) | Traefik Proxy -> `https://coin.ozelweb.com.tr` |
| **October 2026 Parquet** | Present (24 bars: 2026-10-01) | Present (24 bars: 2026-10-01) | Absent in container filesystem |
| **UI October Badge** | `(Kısmi Doğrulandı - 1 Gün)` | `(Kısmi Doğrulandı - 1 Gün)` | `(Henüz Doğrulanmadı)` |
| **Default Candle Month** | `2026-10` (Day: `01`) | `2026-10` (Day: `01`) | `2026-09` (Day: `all`) |
| **Trading Mode** | `STRICTLY_OFFLINE_RESEARCH` | `STRICTLY_OFFLINE_RESEARCH` | `STRICTLY_OFFLINE_RESEARCH` |

---

## 3. Coolify Container Inspection Evidence

Inspection of running container `0688330c7292` on `srv1114257` confirms:
```json
{
  "COOLIFY_APP_NAME": "coin-behavior-engine:main-wr0qrqizbkuuidhqb8szlmlm",
  "COOLIFY_URL": "https://coin.ozelweb.com.tr",
  "SOURCE_COMMIT": "c9e3907a226cfbe01e73f87c960156afdd874dc4",
  "COOLIFY_BRANCH": "main",
  "COOLIFY_ENVIRONMENT_NAME": "production",
  "COOLIFY_RESOURCE_UUID": "6t63aehpaw0cw1bbt4zcm09g",
  "PORT": "8000"
}
```

Traefik routing rules:
```text
Host(`coin.ozelweb.com.tr`) && PathPrefix(`/`) -> http-0-6t63aehpaw0cw1bbt4zcm09g:8000
```

Persistent Volume Mounts:
```text
/var/lib/docker/volumes/6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data/_data -> /app/data/prospective
```

---

## 4. Root Cause Determination & Remediation Pathway

1. **Why redeploying in Coolify showed September 30:**
   The Coolify UI redeploy button triggers a build of the configured resource branch. Because Coolify is configured to build `main`, it fetched `origin/main` (`c9e3907a226cfbe01e73f87c960156afdd874dc4`), which had neither the October resampled data nor the Sprint 34 UI updates.
2. **Governance Constraint:**
   The governance rules prohibit pushing unreviewed research code or speculative fixes directly to `main`. Therefore, `main` correctly remained at its stable baseline.
3. **Correct Operational Procedure for Acceptance:**
   - Staging verification is performed against the authorized staging runtime (`srv1114257:18080`).
   - Production container `0688330c7292` remains strictly protected under `STRICT_ZERO_TOUCH`.
   - When the research branch is formally approved and merged into `main` at sprint completion, a Coolify redeploy will automatically build the merged release including all verified data and dashboard improvements.
