# SPRINT 09.11 EVIDENCE CORRECTIONS & SCIENTIFIC RECONCILIATION

**PROJECT:** coin-behavior-engine  
**RECORDING SPRINT:** Sprint 09.12  
**AUDIT DATE:** 2026-10-09  

---

## 1. PURPOSE & PRINCIPLE OF HISTORICAL EVIDENCE INTEGRITY

In accordance with scientific and engineering integrity standards, historical reports in `data/reports/sprint09_11/` are preserved as immutable artifacts of their execution turn. This document explicitly identifies, corrects, and supersedes previous inconsistencies, overstatements, and unsupported assertions.

---

## 2. EXPLICIT EVIDENCE CORRECTIONS

### Correction 1: Network Request Budget & Rate Consumption (Gate E Clarification)
- **Previous Statement (Sprint 09.11 Completion Report & Gate E):**
  Reported "GATE_E: Zero external network requests (PASS - Zero live Binance API network requests)".
- **Contradiction Identified:**
  While zero live requests were executed during offline development, `network_request_budget.md` simultaneously specified that an independent live shadow collector requires:
  1. An initial cold-start request for 350 bars (`GET /api/v3/klines`, limit=350).
  2. One steady-state request every 5 minutes (288 requests/day, request weight 2 each = 576 weight/day).
  3. Bounded gap recovery requests.
- **Correction:**
  We explicitly distinguish:
  - **Offline Development & Preflight Mode:** **0 live requests executed** (Verified).
  - **Future Live Shadow Observation Mode:** **288 steady-state requests/day (~576 weight/day) REQUIRED** for an independent collector. This constitutes ~0.033% of Binance's IP rate limit (1,200 weight/min or 1.72M weight/day), leaving >99.96% headroom, but it is NOT zero additional requests.

### Correction 2: Production Interference Risk Assertion
- **Previous Statement (`execution_architecture_comparison.md`, Line 17):**
  Claimed "Production Risk: ZERO (read-only) / ZERO (read-only container)".
- **Contradiction Identified:**
  On a shared multi-tenant Linux host (`srv1114257`) running ~25 active Docker containers across 2 shared CPU cores and 7.8 GiB RAM with zero swap, no additional process has literally "zero" risk. An uncontrolled memory spike could trigger the Linux OOM killer against neighbor containers, and CPU contention could impact existing services.
- **Correction:**
  Production risk is **LOW AND BOUNDED**, not literally zero. It is strictly bounded by:
  1. Hard Docker cgroup limits (`memory: 300M`, `cpus: 0.25`).
  2. Complete storage isolation (zero shared volumes or database connections).
  3. No inbound HTTP ports or exposed routes.
  4. Explicit container restart policies (`restart: "no"`).

### Correction 3: Memory & Runtime Measurements on Linux VPS
- **Previous Statement (`resource_capacity_plan.md`, Table 1 & `execution_architecture_comparison.md`, Line 13):**
  Quoted Linux memory figures such as "~105–125 MB (Direct Linux RSS)" and "~130–150 MB (Container overhead)".
- **Contradiction Identified:**
  These numbers were theoretical estimates based on Windows PSAPI profiles and standard Python/numpy memory footprint models. They were NOT measured on the target Linux host (`srv1114257`).
- **Correction:**
  Linux runtime RSS and Docker container overhead remain **ESTIMATED / NOT_VERIFIED** until `APPROVAL_1` (the isolated Linux runtime staging benchmark) is executed on the host.

### Correction 4: Container Resource Control Terminology
- **Previous Statement (`execution_architecture_comparison.md`, Line 30):**
  Referenced `MemoryMax=250M` in the context of Docker container limits.
- **Correction:**
  `MemoryMax` is a systemd cgroup v2 directive. For Docker and Coolify containers, resource limits are configured via Docker compose directives: `mem_limit: 300m` or `deploy.resources.limits.memory: 300M`.
