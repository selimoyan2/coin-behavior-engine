# OPERATOR RUNBOOK: OFFLINE LINUX RUNTIME BENCHMARK (APPROVAL 1)

**TARGET HOST:** `srv1114257`  
**CANDIDATE:** CBE-0.8.0  
**SAFETY LEVEL:** 100% OFFLINE / ZERO NETWORK / ZERO PRODUCTION MUTATION  
**MAXIMUM RUNTIME:** $\le 3$ Minutes  

---

## 1. OBJECTIVE & SCOPE

This runbook guides the human operator in safely executing **APPROVAL_1 (Linux Runtime Staging Benchmark)** directly on host `srv1114257`.

The benchmark executes:
1. 350-bar initial warm-up.
2. 500 steady-state dual-branch observation cycles (total 850 cycles).
3. Prediction generation & outcome resolution.
4. Process RSS & container cgroup memory measurement.
5. Restart and crash recovery audit.
6. Bit-for-bit cryptographic hash chain verification.

**What This Runbook DOES NOT Do:**
- Does NOT connect to Binance API (zero network calls).
- Does NOT start an ongoing or background daemon.
- Does NOT register any cron jobs or systemd services.
- Does NOT touch or modify CBE-0.7.0 production containers or databases.
- Does NOT execute or route trades.

---

## 2. PREREQUISITES

1. SSH terminal access to `srv1114257`.
2. Normal user shell (no root or sudo privileges required).
3. Docker installed on the host (preferred) or Python 3.10+.
4. Repository cloned at `/opt/coin-behavior-engine` (or operator workspace) with commit `a3c4d98d3e78ab7b2ef0e85ac46c63c345194650`.

---

## 3. EXECUTION OPTIONS

### OPTION 1: Ephemeral Isolated Docker Container (Preferred: Strict CGroup v2 Enforcement)

This is the **preferred option** because it executes in a fully hermetic, read-only sandbox with zero network access and kernel-enforced memory ceilings via cgroups.

> [!IMPORTANT]
> **Why Docker CGroup Memory Limits (`--memory=300m`) are Preferred over `ulimit -v`:**
> Virtual address space limits (`ulimit -v` / `RLIMIT_AS`) constrain the entire virtual address mapping table, which includes shared libraries (`libc`, Python dynamic extensions, BLAS/LAPACK runtime), read-only mmap memory, thread stacks, and heap reservations. On 64-bit Linux with Python and scientific libraries (`numpy`, `scikit-learn`, `pandas`), virtual address allocations routinely exceed 1 GB even when physical resident memory (RSS) is only ~100–135 MB.
> 
> Setting `ulimit -v 350000` causes synthetic allocation failures (`MemoryError` or premature crashes during dynamic library loading) that have no correlation with actual RAM consumption on the shared host.
> In contrast, Docker cgroup memory limits (`--memory=300m`) and kernel cgroups track and limit genuine physical memory usage (`resident_set_size` + active page cache). This prevents host OOM while allowing the Python process to safely initialize its virtual address space.

```bash
# 1. Build local ephemeral staging image (from repo root)
cd /opt/coin-behavior-engine

# Verify commit SHA
git rev-parse HEAD
# MUST RETURN: a3c4d98d3e78ab7b2ef0e85ac46c63c345194650

docker build -t cbe-080-staging:local -f deploy/shadow_v080/Dockerfile.staging .

# 2. Run strictly isolated container (network none, read-only root, 300M memory limit, 0.25 CPU)
mkdir -p /tmp/cbe_docker_bench_output
chmod 777 /tmp/cbe_docker_bench_output

docker run --rm \
  --name cbe_staging_bench \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=67108864 \
  --memory=300m \
  --cpus=0.25 \
  -v /tmp/cbe_docker_bench_output:/app/data/prospective_shadow:rw \
  cbe-080-staging:local \
  python3 -m coin_behavior_engine.shadow_v080.benchmark_staging_linux \
    --output-dir /app/data/prospective_shadow \
    --warmup-bars 350 \
    --cycles 500 \
    --rss-budget 250.0

# 3. Inspect generated JSON benchmark report
cat /tmp/cbe_docker_bench_output/staging_linux_benchmark_results.json | grep -E "measured_peak_process_rss_mb|cgroup|status"
```

---

### OPTION 2: Standalone Ephemeral Process (Alternative: Native Python Venv)

If Docker is not available, execute directly in an ephemeral Python virtual environment. Notice that `ulimit -v` is explicitly omitted: process memory is monitored and verified against the 250.0 MB budget directly by the benchmark's internal `VmHWM` / `VmRSS` telemetry.

```bash
# 1. Navigate to repository root
cd /opt/coin-behavior-engine

# 2. Verify clean git state and commit SHA
git rev-parse HEAD
# MUST RETURN: a3c4d98d3e78ab7b2ef0e85ac46c63c345194650

# 3. Create ephemeral virtual environment in /tmp
python3 -m venv /tmp/cbe_bench_venv
source /tmp/cbe_bench_venv/bin/activate

# 4. Install minimal scientific dependencies into ephemeral venv
pip install --no-cache-dir joblib scikit-learn pandas numpy

# 5. Create temporary output directory
mkdir -p /tmp/cbe_bench_output

# 6. Execute benchmark without artificial virtual memory restrictions
PYTHONPATH=src python3 src/coin_behavior_engine/shadow_v080/benchmark_staging_linux.py \
  --output-dir /tmp/cbe_bench_output \
  --warmup-bars 350 \
  --cycles 500 \
  --rss-budget 250.0

# 7. Inspect generated JSON benchmark report
cat /tmp/cbe_bench_output/staging_linux_benchmark_results.json | grep -E "measured_peak_process_rss_mb|status|step_latency"
```

---

## 4. EXPECTED OUTPUTS & ACCEPTANCE CRITERIA

| Evaluation Item | Required Value / Acceptance Threshold |
|:---|:---:|
| **Overall Status** | `"PASS"` |
| **Peak Process RSS (`VmHWM` / `VmRSS`)** | **$\le 250.0$ MB** (Expected: ~110–135 MB on Linux) |
| **Step Latency (Mean)** | **$\le 20.0$ ms** (Expected: 5–15 ms on Linux) |
| **Step Latency (P95)** | **$\le 40.0$ ms** |
| **Restart & Restore Success** | `true` (350 bars restored from snapshot) |
| **Hash Chain Integrity** | `true` (all 5,100 predictions cryptographically valid) |
| **Accounting Conservation** | `true` ($N_{predictions} = N_{matured\_valid} + N_{disqualified} + N_{pending}$) |
| **Network Calls** | `0` (Zero network requests) |
| **Prospective Guard** | `true` (Zero live prospective events emitted) |
| **Total Wall Clock Runtime** | **$\le 120$ Seconds (2 minutes)** |

---

## 5. FAILURE CONDITIONS & IMMEDIATE ACTIONS

If any of the following occur:
1. **Peak Process RSS $> 250.0$ MB:** Reject `APPROVAL_1`. Report memory footprint to development.
2. **Process terminated by OOM / Killed:** Reject `APPROVAL_1`. Memory ceiling breached.
3. **Step Latency Mean $> 50$ ms:** Flag CPU throttling concern.
4. **Hash Chain Invalid (`is_valid == False`):** Cryptographic regression detected. Immediate stop.

---

## 6. CLEANUP COMMANDS (ZERO TRACE LEFTOVER)

Run immediately after copying the JSON results:

```bash
# Clean Option A artifacts
rm -rf /tmp/cbe_bench_venv /tmp/cbe_bench_output

# Clean Option B artifacts (if used)
rm -rf /tmp/cbe_docker_bench_output
docker rmi cbe-080-staging:local 2>/dev/null || true
```

---

## 7. CONFIRM PRODUCTION IS COMPLETELY UNAFFECTED

Run these read-only checks on the host to verify zero production impact:

```bash
# 1. Confirm CBE-0.7.0 production container is running and healthy
docker ps | grep -E "coin-behavior-engine|cbe-0.7"

# 2. Check production logs have no errors or restart events
docker logs --tail 20 cbe-production-worker 2>/dev/null || true

# 3. Confirm available memory remains ~3.2 GiB
free -h
```
