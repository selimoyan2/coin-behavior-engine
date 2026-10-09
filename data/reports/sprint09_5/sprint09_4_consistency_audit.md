# Sprint 09.4 Scientific & Statistical Consistency Audit

**Sprint:** 09.5  
**Subject:** Formal Forensic Reconciliation of Sprint 09.4 Reported Figures  
**Status:** RECONCILED AND DOCUMENTED  

---

## 1. Discrepancy Investigation: Market State Distribution

A discrepancy was identified between the user-facing completion report text and the committed research reports for Sprint 09.4:

| Primary State | Completion Report Text | Committed `classifier_validation.json` & `executive_summary.md` | Clean Filtered Sample (75,989 bars) |
| :--- | :---: | :---: | :---: |
| **LOW_VOLATILITY** | 46.88% | **46.83%** | 46.67% |
| **NORMAL_VOLATILITY** | 49.33% | **46.16%** | 46.27% |
| **HIGH_VOLATILITY** | 3.79% | **7.00%** | 7.06% |

### Forensic Finding:
1. The numbers in [`classifier_validation.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/data/reports/sprint09_4/classifier_validation.json) (46.83% LOW, 46.16% NORMAL, 7.00% HIGH) are **100% reproducible and authoritative** across the full Holdout 2026 dataset (76,565 bars):
   - `LOW_VOLATILITY`: 35,859 / 76,565 = 46.83%
   - `NORMAL_VOLATILITY`: 35,343 / 76,565 = 46.16%
   - `HIGH_VOLATILITY`: 5,363 / 76,565 = 7.00%
2. When evaluated on the clean/eligible forward-matured sample (75,989 bars, excluding 288-bar boundaries):
   - `LOW_VOLATILITY`: 35,467 / 75,989 = 46.67%
   - `NORMAL_VOLATILITY`: 35,159 / 75,989 = 46.27%
   - `HIGH_VOLATILITY`: 5,363 / 75,989 = 7.06%
3. The completion report text figures (`49.33% / 46.88% / 3.79%`) originated from an exploratory interactive query using an unverified secondary flag mask, and were erroneously pasted into the text response.
4. **Correction:** The committed JSON artifact is confirmed correct and unmodified.

---

## 2. Incremental Information Audit: Association vs Forecasting Utility

In Sprint 09.4, an in-sample nested OLS regression on Validation 2025 yielded:
- Incremental $R^2$: $+0.006568$
- $F$-statistic: $558.49$
- $p$-value: $5.45 \times 10^{-242}$

### Forensic Finding:
1. The tiny $p$-value is an artifact of estimating OLS on 104,544 five-minute observations with 11-bar forward overlapping windows, which artificially inflates sample size and standard errors.
2. In strict out-of-sample chronological evaluation (trained on Discovery, tested on 2026 Holdout):
   - Incremental $R^2$ is **negative** ($-0.00023$ for 1h, $-0.00038$ for 4h).
   - $\Delta \text{MAE}$ is $< 0.00005$ (0.6% relative change, statistically indistinguishable from zero).
3. **Scientific Classification:** Market-state labels do NOT possess incremental point forecasting power beyond continuous volatility features. They are classified as **`DESCRIPTIVE_ONLY`**.
