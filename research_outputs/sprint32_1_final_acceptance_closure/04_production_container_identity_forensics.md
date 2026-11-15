# 04 — Production Container Identity Forensics & Zero-Touch Audit
## Forensic Investigation into Container Identity Shift Between Sprint 31 (`fdbdba96e677`) and Sprint 32 (`33c3b568c4c1`)

**Sprint ID:** `CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE`  
**Investigation Date UTC:** `2026-11-15T14:15:00Z`  
**Remote Host:** `srv1114257` (`168.231.125.238`)  
**Application UUID:** `6t63aehpaw0cw1bbt4zcm09g` (`coin-behavior-enginemain-wr0qrqizbkuuidhqb8szlmlm`)  
**Continuity Classification:** **`PRODUCTION_ZERO_TOUCH_CONTINUITY_NOT_PROVEN`**  

---

## 1. The Incident Under Investigation

- **Sprint 31 Reported Production Container ID:** `fdbdba96e677` (StartedAt: `2026-11-14T18:56:57.442994328Z`)
- **Sprint 32 Reported Production Container ID:** `33c3b568c4c1` (StartedAt: `2026-11-15T11:04:21.579142362Z`)

Sprint 32 reported container `33c3b568c4c1` as running untouched with `RestartCount: 0`. However, the container ID had changed completely from the `fdbdba96e677` ID reported in Sprints 29, 30, and 31.

---

## 2. Read-Only Forensic Evidence Gathered on `srv1114257`

### 2.1. Coolify Deployment Queue Audit
A read-only query to the Coolify management PostgreSQL database (`coolify-db`) table `application_deployment_queues` revealed the authoritative lifecycle records:

```text
 id  | application_id |     deployment_uuid      |                  commit                  |  status  |     created_at      |     updated_at      
-----+----------------+--------------------------+------------------------------------------+----------+---------------------+---------------------
 573 | 10             | w7r8pvhk0vph4uzrqyomz95x | 3f3fe5a2aac183a5928f1ef541134f19f3677c67 | finished | 2026-11-15 11:01:55 | 2026-11-15 11:05:09
 572 | 10             | hdqxrm8luxsoucxo2fxtvfho | c0c7fa86236e3de683fe561c3cbdd1d4935af051 | finished | 2026-11-14 18:54:55 | 2026-11-14 18:57:45
```

- **Deployment 572:**
  - Target Commit: `c0c7fa86236e3de683fe561c3cbdd1d4935af051` (Sprint 28.1 closure / Sprint 29 start).
  - Started container `fdbdba96e677` at `2026-11-14T18:56:57.442994328Z`.
  - Remained active throughout Sprint 29, Sprint 30, and Sprint 31.

- **Deployment 573:**
  - Target Commit: `3f3fe5a2aac183a5928f1ef541134f19f3677c67` (The baseline commit of Sprint 32 / delivery of Sprint 31).
  - Triggered at `2026-11-15 11:01:55 UTC`.
  - Completed at `2026-11-15 11:05:09 UTC`.
  - Started container `33c3b568c4c1` at `2026-11-15T11:04:21.579142362Z`.

### 2.2. Container Metadata & Image Immutable Digest
Inspection of `33c3b568c4c1` via Docker API:
- **Created:** `2026-11-15T11:04:21.476343003Z`
- **StartedAt:** `2026-11-15T11:04:21.579142362Z`
- **Image ID:** `sha256:8dd78360feb5df238530b28b8e1eae954a60491332dca4d95b9eaa2c7c750d52`
- **Config Image Tag:** `6t63aehpaw0cw1bbt4zcm09g:3f3fe5a2aac183a5928f1ef541134f19f3677c67`
- **Container Name:** `6t63aehpaw0cw1bbt4zcm09g-20261115T110155`
- **Routing:** Traefik HTTPS ingress for `Host('coin.ozelweb.com.tr')` on internal port 8000.

---

## 3. Forensic Root-Cause Determination

The investigation answers the user's specific diagnostic options:

1. **An actual production container replacement:** **YES.**
   At `2026-11-15T11:04:21Z`, Coolify deployment 573 terminated container `fdbdba96e677` and spawned container `33c3b568c4c1` running the freshly built image for commit `3f3fe5a2aac183a5928f1ef541134f19f3677c67`.
2. **An unrelated container being identified as production:** **NO.**
   Both containers belonged to the authoritative production application UUID `6t63aehpaw0cw1bbt4zcm09g`.
3. **A reporting error:** **PARTIAL.**
   The Sprint 32 deployment script reported `33c3b568c4c1` as having 0 restarts, but erroneously claimed zero-touch continuity without disclosing that the container had been replaced by Coolify just before Sprint 32 began.
4. **Infrastructure Event:** Coolify auto-deployment on commit push to `main`.

---

## 4. Continuity Verdict & Epistemological Rectification

A current restart count of zero on a newly created container does **not** prove historical zero-touch continuity.

Because container `fdbdba96e677` was terminated and replaced by container `33c3b568c4c1` at `2026-11-15T11:04:21Z`, unbroken historical continuity from Sprint 31 was **interrupted**.

Therefore, the only honest, evidence-based scientific verdict is:

```text
PRODUCTION_ZERO_TOUCH_CONTINUITY_NOT_PROVEN
```

All unsupported assertions of continuous historical zero-touch operations are formally revoked.
