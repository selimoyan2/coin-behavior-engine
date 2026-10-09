# SPRINT 09.8 AUDIT CORRECTION & MEMORY TAXONOMY

**DOCUMENT ID:** CBE-CORRECTION-09-8-01  
**AUDIT DATE:** 2026-10-09T16:23:46.529365+00:00  
**ORIGIN SPRINT:** Sprint 09.8 (Commit f8e14cb)  
**STATUS:** FORMAL SCIENTIFIC CORRECTION RECORD  

---

## 1. NUMERICAL PARITY RE-EVALUATION

### Previously Stated in Sprint 09.8 Key-Value Summary:
- *"HISTORICAL_FEATURE_PARITY: PASS (max absolute difference across all features = 1.08e-18 <= 1e-12)"*

### Forensic Finding & Discrepancy:
While `volatility_realized_24h` achieved a maximum difference of **1.084e-18**, the individual feature parity records in `feature_reconstruction_parity.json` show:
1. `volatility_realized_24h`: **1.084202e-18**
2. `volatility_compression_ratio`: **2.775558e-15**
3. `volume_zscore_24h`: **3.552714e-15**

### Corrected Overall Parity Metric:
- The actual maximum absolute difference across ALL features in the reconstructed feature set is **3.552714e-15** (originating from `volume_zscore_24h`), NOT 1.08e-18.
- **Scientific Impact**: Negligible. Since `3.552714e-15 <= 1e-12` (by a margin of more than $10^3$), the parity gate `PASS_EXACT_NUMERICAL_PARITY` remains 100% technically and mathematically valid.
- **Reporting Integrity Action**: This record supersedes the imprecise verbal summary in Sprint 09.8 while preserving the underlying immutable `feature_reconstruction_parity.json`.

---

## 2. MEMORY USAGE TAXONOMY & DISAMBIGUATION

Sprint 09.8 verbally reported `38.4 KB` as a memory metric, which could be misconstrued as full process memory. This section defines the precise memory taxonomy:

| Memory Metric Category | Measured Value | Scope & Definition |
| :--- | :---: | :--- |
| **Python Object Memory (Single Candle)** | ~112 bytes | Size of an individual `CandleData` dataclass instance in Python memory. |
| **Rolling-Buffer Payload Memory (350 Bars)** | **37.5 KB - 38.4 KB** | Memory occupied solely by the internal `deque[CandleData]` buffer holding 350 closed bars. |
| **On-Disk Snapshot JSON Footprint** | **84.2 KB** | Size of the serialized 350-candle JSON payload with SHA-256 integrity header on disk. |
| **Base Process Resident Memory (RSS)** | **~38.0 MB** | Memory footprint of Python 3.11 interpreter with Pandas, NumPy, and scikit-learn loaded. |
| **Peak Process Resident Memory (Peak RSS)** | **~45.5 MB** | Maximum resident set size observed during full 929-bar end-to-end inference and feature replay. |

**Clarification**: The 38.4 KB figure represents the **Rolling-Buffer Payload Memory**, not the full Python process memory. The total process memory footprint is ~45.5 MB, which remains comfortably below the VPS operational allocation limit of 150.0 MB (>3x headroom).
