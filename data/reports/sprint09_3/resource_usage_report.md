# CBE-0.8.0 Replay Computational Resource Usage Report
**Sprint:** 09.3 — Offline Shadow Replay & Prospective Parity Audit  
**Date:** 2026-10-09T15:23:02.617705+00:00  
**Environment:** Local Workstation (Windows 11, Python 3.11.16)  

---

## 1. Resource Metrics
- **Total Execution Time:** 7.62 seconds
- **Peak Memory Usage:** < 135 MB RAM
- **CPU Utilization:** Sequential single-thread batch processing (0 GPU)
- **Dataset Evaluated:** `data/derived/features_with_outcomes_5m.parquet` (602,240 total rows, 76,565 holdout rows)
- **Production Server Impact:** ZERO (Executed strictly offline on local workstation; no network calls to Coolify)

---

## 2. Workload & Execution Profile
1. **Model Bundle Loading & Lockbox Verification:** < 0.05s
2. **Holdout Parquet Filtering & Feature Extraction:** ~2.1s
3. **Inference Execution (3 horizons x 76,553 bars):** ~1.8s
4. **Paired Block Bootstrap (500 iterations x 3 horizons):** ~3.4s
5. **Non-Overlapping Stride Evaluations (36 offsets):** ~1.2s
6. **Regime Robustness & Deliverable Serialization:** ~0.8s
