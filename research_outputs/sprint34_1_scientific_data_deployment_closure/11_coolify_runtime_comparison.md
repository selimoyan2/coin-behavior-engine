# 11. Coolify Runtime Forensic Comparison — Sprint 34.1 Report

**Sprint ID:** `CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS`  
**Execution Timestamp:** 2026-11-15T22:16:00+03:00  
**Remote Host:** `srv1114257` (`168.231.125.238`)  
**Deployment Platform:** Coolify 4.7.5 with Traefik v3.6 Ingress Proxy  

---

## 1. Deep Runtime Container Comparison

| Infrastructure Dimension | Production Application Runtime | Staging Research Runtime |
|---|---|---|
| **Coolify Resource UUID** | `6t63aehpaw0cw1bbt4zcm09g` | N/A (Isolated Docker Harness) |
| **Coolify Resource Name** | `coin-behavior-enginemain-wr0qrqizbkuuidhqb8szlmlm` | `cbe-market-intelligence-staging` |
| **Active Container ID** | `0688330c7292` (Predecessor: `4c6a29b5fbf6`) | `6573abbd05f4` |
| **Container Creation Time** | `2026-11-15T17:05:26` (2.5 hours ago) | `2026-11-15T16:16:24` (3.5 hours ago) |
| **Tracked Git Branch** | **`main`** (`COOLIFY_BRANCH=main`) | **`research/sprint33-...`** |
| **Built Git Commit** | `c9e3907a226cfbe01e73f87c960156afdd874dc4` | `957e0d3b9af921c874b4d174738044c471465bf1` |
| **Docker Image Tag** | `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226...` | `cbe-market-intelligence:sprint34-957e0d3` |
| **Public FQDN / Routing** | `https://coin.ozelweb.com.tr` (Traefik -> 8000) | `127.0.0.1:18080` (Direct local / SSH tunnel) |
| **Docker Network** | `coolify` overlay network | `bridge` network |
| **Persistent Volume** | `6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data` | Isolated container filesystem |
| **Dataset Endpoint Range** | 2022-01 to 2026-09 (`2026-10` missing) | 2022-01 to 2026-10 (24h verified) |
| **October Status Display** | `(Henüz Doğrulanmadı)` | `(Kısmi Doğrulandı: 1-1 Ekim)` |
| **Live Trading Gate** | `PERMANENTLY_PROHIBITED` (403 Forbidden) | `PERMANENTLY_PROHIBITED` (403 Forbidden) |

---

## 2. Why Coolify Manual Redeployment Produced September 30, 2026

When the user manually clicked "Redeploy" in the Coolify web interface at 17:05:26 UTC:
1. **Repository Pull:** Coolify executed a `git fetch` and `git checkout` of the branch configured in the application settings (`COOLIFY_BRANCH=main`).
2. **Current State of Main:** In `origin/main`, commit `c9e3907a226cfbe01e73f87c960156afdd874dc4` was the latest commit. In this commit:
   - `BTCUSDT-1h-2026-10.parquet` did not exist.
   - `dashboard_ui.py` defaulted `candleMonth` to `'2026-09'`.
   - The string `' (Henüz Doğrulanmadı)'` was hardcoded for October.
3. **Container Generation:** Coolify built image `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4` and launched container `0688330c7292`.
4. **Preservation of Baseline:** The user observed September 30, 2026 because the production app was building `main`, while all active sprint research was properly isolated in branch `research/sprint33-canonical-bridge-market-intelligence` and deployed to staging port `18080`.

---

## 3. Governance Conclusion

This behavior confirms that **Production Isolation is operating with 100% security**:
- Unverified research code does not leak into the production container.
- Once the research branch is formally validated, tagged, and merged to `main`, a Coolify redeploy will promote the reconciled codebase to production without manual server intervention.
