# EXECUTION ARCHITECTURE COMPARISON & SELECTION ANALYSIS

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. COMPARISON OF CANDIDATE ARCHITECTURES

| Evaluation Dimension | Architecture A: Standalone Systemd Process | Architecture B: Dedicated Coolify Docker Container | Architecture C: Shared Worker Transport |
|:---|:---:|:---:|:---:|
| **Additional RAM Usage** | ~105–125 MB (Direct Linux RSS) | ~130–150 MB (Container overhead) | ~40–60 MB (In-process plugin) |
| **CPU Usage** | Negligible (< 1% core) | Negligible (< 1% core) | Negligible |
| **Network Request Rate** | 1 req / 5 min (0.2 req/min) | 1 req / 5 min (0.2 req/min) | 0 req / min (Shared feed) |
| **Process Isolation** | Full OS isolation | Full container cgroup isolation | **ZERO isolation (shared worker)** |
| **Production Risk** | **ZERO (read-only)** | **ZERO (read-only container)** | **HIGH (crash impairs production)** |
| **Storage Separation** | Dedicated host directory | Dedicated named volume | Shared SQLite/Postgres DB |
| **Restart Containment** | Independent restart | Independent container restart | Worker restart restarts both |
| **Operational Simplicity** | Simple systemd unit | Standard Coolify service | Complex thread orchestration |

---

## 2. ARCHITECTURAL RECOMMENDATION

**Recommended Design:** **Architecture B (Dedicated Coolify Container)** with a fallback to **Architecture A (Standalone systemd)** if container daemon memory is constrained.

**Rationale:**
1. Architecture C (modifying the production CBE-0.7.0 worker) is strictly **PROHIBITED** by project safety rules. Any crash or bug in candidate 0.8.0 would directly impact frozen production.
2. Architecture B provides strict cgroup memory enforcement (`MemoryMax=250M`), dedicated filesystem volumes, and clean restart isolation without touching production code.
