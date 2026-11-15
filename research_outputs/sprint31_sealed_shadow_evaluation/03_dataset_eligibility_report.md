# 03 — Dataset Eligibility & Integrity Audit Report

**Sprint ID:** `CBE_SPRINT31_SEALED_SHADOW_EVALUATION`  
**Audit Timestamp:** `2026-11-15T10:22:37.775038+00:00`  
**Dataset Target:** `data/historical/historical_binance_btcusdt_1h_2025.parquet`  
**Dataset Identifier:** `DS-BTC-1H-2025-SEALED`  
**Eligibility Verdict:** **`ELIGIBLE_UNSEEN_HOLDOUT`**  

---

## 1. Executive Summary

To conduct a genuinely unbiased sealed evaluation of the low-turnover timing policies developed in Sprint 30, the dataset must meet strict offline scientific standards before any evaluation code is granted access.

The dataset under audit comprises contiguous hourly observations for the entire calendar year 2025 (`2025-01-01 00:00:00 UTC` to `2025-12-31 23:00:00 UTC`).

## 2. Mathematical & Structural Validation Matrix

| Validation Dimension | Specification Standard | Observed Value | Status |
| :--- | :--- | :--- | :--- |
| **Trading Symbol** | Strict SPOT `BTCUSDT` | `BTCUSDT` | PASS |
| **Market Type** | Spot Market Only (`SPOT`) | `SPOT` | PASS |
| **Total Candles** | Exactly 8,760 hours (365 days) | `8760` | PASS |
| **Start Timestamp** | `2025-01-01 00:00:00 UTC` | `1735689600000` | PASS |
| **End Timestamp** | `2025-12-31 23:00:00 UTC` | `1767222000000` | PASS |
| **Interval Step** | Fixed 3,600,000 ms (1 hour) | Uniform 3,600,000 ms | PASS |
| **Missing Gaps** | Strictly 0 missing intervals | `0` missing intervals | PASS |
| **Duplicate Timestamps** | Strictly 0 duplicate bars | `0` duplicates | PASS |
| **Monotonicity** | Strict monotonic increasing $T_k > T_{k-1}$ | Monotonically Increasing | PASS |
| **OHLCV Math Invariants** | $H \ge \max(O,C,L)$, $L \le \min(O,C,H)$, $V \ge 0$ | $0$ violations across 8,760 bars | PASS |
| **Quarantine Status** | Quarantined / Contaminated Exclusion | NOT_QUARANTINED | PASS |

## 3. Holdout Ledger Verification

The dataset identifier `DS-BTC-1H-2025-SEALED` was checked against the historical holdout ledger. No previous evaluation runs or parameter optimization passes had ever accessed this 2025 dataset during Sprints 29 or 30.

## 4. Conclusion & Certification

The dataset satisfies all pre-flight criteria. The sealed evaluation runner is authorized to perform historical simulation under one-way execution constraints.
