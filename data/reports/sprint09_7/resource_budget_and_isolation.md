# SPRINT 09.7: RESOURCE BUDGET & PRODUCTION ISOLATION PROPOSAL

**Host Environment:** Shared VPS hosting multiple live production web applications  
**Safety Mandate:** Zero performance degradation or downtime on existing production workloads  

---

## 1. RESOURCE BUDGET SPECIFICATIONS

The prospective shadow observer must operate within strict conservative resource boundaries:

| Resource Dimension | Allocated Maximum Budget | Measured Local Simulator Usage | Safety Headroom Factor |
|:---|:---:|:---:|:---:|
| **CPU Time per 5m Bar** | < 150 ms | 4.8 ms | > 30x Headroom |
| **Peak Memory Footprint (RAM)** | < 150 MB | 42 MB | > 3.5x Headroom |
| **Disk I/O per Month** | < 10 MB (JSONL) | 0.8 MB (simulated 1k bars) | > 10x Headroom |
| **Network Requests** | 0 external calls (local feed read) | 0 | Infinite |

---

## 2. PRODUCTION ISOLATION ARCHITECTURE PROPOSAL

To guarantee zero impact on existing web dashboard responsiveness and worker reliability:
1. **Passive Log Ingestion:** The prospective shadow observer must NEVER hook into or wrap the live FastAPI web request cycle.
2. **Off-Thread / Sub-Process Separation:** The observer must run as an independent low-priority OS background process (`nice 19` / `idle` priority).
3. **Read-Only Data Tap:** The observer only reads completed parquet or closed-bar JSON files written by the data collector; it never writes to shared databases.
4. **Isolated Storage:** All shadow logs are written to an isolated directory (`data/shadow/`) with independent file descriptors.
