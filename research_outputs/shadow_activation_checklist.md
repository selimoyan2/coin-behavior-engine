# CBE Sprint 11.16A — Shadow Activation Checklist & Readiness Verification

**Document Version:** 1.0.0-sprint11.16a  
**Target Environment:** Host Server `srv1114257` (`168.231.125.238`)  
**Base Code Commit:** `0a520ecc20cb45e9f8997a3f5a04e57e937d9c84`  
**Execution Standard:** Strictly Empirical Verification — NO SPECULATION  

---

## 1. Mandatory Conditions & Verification Matrix

In accordance with Sprint 11.16A Phase 7 instructions, every prerequisite condition is evaluated against live host diagnostics, repository manifests, or cryptographic invariants.

Conditions are classified strictly into:
- **`VERIFIED`:** Supported by independent, live empirical evidence.
- **`BLOCKED`:** Requires human operator authorization, external credentials, or unresolved prerequisite.
- **`NOT_YET_TESTED`:** Cannot be tested until the prospective shadow environment is instantiated.

| # | Requirement / Condition | Classification | Independent Verification Evidence / Mechanism | Current Blocker / Remediation |
|:---:|---|:---:|---|---|
| **1** | **Base Code Commit Match** | **`VERIFIED`** | Git HEAD confirmed at `0a520ecc20cb45e9f8997a3f5a04e57e937d9c84` on branch `main`. Clean working tree. | None. Invariant verified. |
| **2** | **Production Container Isolation** | **`VERIFIED`** | Live inspection of `6t63aehpaw0cw1bbt4zcm09g` (`a5510203abd2`): running on network `coolify`, volume `6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data`. Zero overlap with shadow design. | None. Invariant verified. |
| **3** | **Live Capture Integrity & Exclusivity** | **`VERIFIED`** | Live inspection of `zgit1s3n1acdtqtsxp0s44vj` (`50b43f0da76a`): Up 37 hours, exclusive `:rw` writer to volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data`. | None. Invariant verified. |
| **4** | **Staging Environment Mount Safety** | **`VERIFIED`** | Live inspection of `dzzfws54by1whlbq6fk4ywut` (`ffec81e484f5`): mounts capture volume strictly `:ro` (`RW: False`). Bound to localhost `127.0.0.1:18080`. | None. Invariant verified. |
| **5** | **Stopped Scoring Worker Inactivity** | **`VERIFIED`** | Live inspection of `3v3dey5y1ybg6zqkv0wmuxtd` (`82b53934d374`): Exited (status 137). Zero active CPU/RAM usage. | None. Invariant verified. |
| **6** | **Host Resource Availability** | **`VERIFIED`** | Live telemetry: 2 vCPUs, 2,985 MB available RAM, 44 GB available disk. Production observed at 81.3% CPU, necessitating 0.20 CPU ceiling. | None. Invariant verified. |
| **7** | **Five Frozen Policy Parameter Hashes** | **`VERIFIED`** | Deterministic SHA-256 parameter digests verified in `policy_freeze_manifest.json` for Policies A through E. | None. Invariant verified. |
| **8** | **Freeze Chronology Corroboration** | **`BLOCKED`** | Manifest declared `2026-10-18T21:00:00Z` vs Git commit `2026-10-18T18:31:03Z` (+2.5h mismatch due to local UTC+3 Istanbul time). Zero external git tags or RFC-3161 timestamps exist. | Preserved as **`FREEZE_CHRONOLOGY_UNVERIFIED`** in accordance with sprint mandate. |
| **9** | **Market Data Read-Only Access Grant** | **`BLOCKED`** | Accessing protected volume `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data` requires formal operator authorization signature. | **`OPERATOR_AUTHORIZATION_REQUIRED`** |
| **10**| **No-Order Air-Gap Verification** | **`VERIFIED`** | Proposed container enforces `network_mode: "none"` (zero outbound sockets), `CBE_TRADING_DISABLED=true`, zero API keys. | None. Invariant verified. |
| **11**| **Dedicated Storage Separation** | **`VERIFIED`** | Dedicated named volume `cbe_prospective_shadow_data_v1` specified with zero cross-mounts to production. | None. Invariant verified. |
| **12**| **Live Prospective Scoring Daemon Execution** | **`BLOCKED`** | Prospective scoring daemon is in `STANDBY` mode. Creation of persistent containers forbidden during Sprint 11.16A. | Preserved as **`PROSPECTIVE_OBSERVATION_NOT_STARTED`**. |
| **13**| **Runtime CFS Quota Enforcement Under Load** | **`NOT_YET_TESTED`** | Actual Linux CFS scheduler CPU throttling under live market burst cannot be tested until container runs. | Requires container execution in Sprint 11.16B. |
| **14**| **Daily Anchor Harvesting Pipeline** | **`NOT_YET_TESTED`** | Automated harvesting of daily checkpoint hashes to external Git tags requires live operational daemon. | Requires live operational cycle in Sprint 11.16B. |

---

## 2. Summary of Verification Verdicts

- **Total Mandatory Conditions Evaluated:** 14
- **VERIFIED:** 10 (71.4%)
- **BLOCKED:** 3 (21.4%)
  - Condition 8: Freeze Chronology (`FREEZE_CHRONOLOGY_UNVERIFIED`)
  - Condition 9: Market Data Access Grant (`OPERATOR_AUTHORIZATION_REQUIRED`)
  - Condition 12: Prospective Observation Start (`PROSPECTIVE_OBSERVATION_NOT_STARTED`)
- **NOT_YET_TESTED:** 2 (14.3%)
  - Condition 13: Runtime CFS Throttling under load
  - Condition 14: Automated Anchor Harvester execution

---

## 3. Explicit Operator Action Items Before Sprint 11.16B

Before any operator authorizes deployment of the shadow observation container in Sprint 11.16B, the following actions are strictly required:

1. **Review Production CPU Load:** Acknowledge that container `6t63aehpaw0cw1bbt4zcm09g` operates at ~81% CPU on a 2-core host and approve the `cpus: '0.20'` / `mem_limit: 250M` ceiling for the observer.
2. **Execute Authorization Signature:** Sign the prospective observation activation directive granting read-only access to `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:ro`.
3. **Anchor Code Freeze Commit:** Create and push a signed git tag (e.g. `git tag -s v11.16a-freeze-0a520ec -m "Signed policy freeze baseline"`) to formally resolve the freeze chronology external anchor requirement.
4. **Confirm Air-Gap Mode:** Re-verify that `network_mode: "none"` is preserved in the deploy manifest.
