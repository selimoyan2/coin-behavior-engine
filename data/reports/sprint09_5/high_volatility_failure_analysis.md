# CBE-0.8.0 High-Volatility Prediction Interval Failure Analysis

**Sprint:** 09.5  
**Subject:** Scientific Root Cause Analysis of High-Volatility Interval Under-Coverage  
**Status:** REPRODUCED, DIAGNOSED, AND MATHEMATICALLY DEMONSTRATED  

---

## 1. Executive Summary

During Sprint 09.4, candidate prediction intervals for CBE-0.8.0 were calibrated using a global split-conformal procedure on the 2025 Validation partition. While achieving nominal marginal coverage across the full dataset (~78.4% on 80% nominal, ~94.8% on 95% nominal), the intervals suffered severe **conditional under-coverage** during high-volatility market episodes:
- **1h Horizon (80% Nominal):** HIGH_VOLATILITY coverage collapsed to **50.38%** (29.62% under-coverage).
- **1h Horizon (95% Nominal):** HIGH_VOLATILITY coverage collapsed to **82.30%** (12.70% under-coverage).
- **4h Horizon (80% Nominal):** HIGH_VOLATILITY coverage collapsed to **51.07%** (28.93% under-coverage).

This forensic report proves that this failure is the inevitable consequence of **residual variance heterogeneity** under marginal conformal pooling.

---

## 2. Mathematical Root Cause: Variance Heterogeneity Across Regimes

Global split-conformal calibration assumes exchangeability across the entire validation dataset and computes a single global empirical quantile pair $[q_0.1, q_0.9]$:
$$L_{80, t} = \max(0, \hat{y}_t + q_{0.10}), \quad U_{80, t} = \max(\hat{y}_t, \hat{y}_t + q_{0.90})$$

However, financial return volatility exhibits pronounced regime-dependent innovation variance:
- In `LOW_VOLATILITY` (2025): Residual standard deviation $\sigma_{\text{res}} = 0.007789$, MAE $= 0.005305$.
- In `NORMAL_VOLATILITY` (2025): Residual standard deviation $\sigma_{\text{res}} = 0.013063$, MAE $= 0.007393$.
- In `HIGH_VOLATILITY` (2025): Residual standard deviation $\sigma_{\text{res}} = 0.020767$, MAE $= 0.014781$.

The residual standard deviation in `HIGH_VOLATILITY` is **2.67 times higher** than in `LOW_VOLATILITY`!

Because `LOW_VOLATILITY` and `NORMAL_VOLATILITY` constitute ~92.4% of all calibration samples in 2025, the pooled quantiles are dominated by the low-dispersion regimes. The resulting fixed width interval is far too narrow for the large forecast innovations occurring in volatile regimes.

Simultaneously, in `LOW_VOLATILITY`, the intervals are excessively wide (empirical coverage of 86.74%), which mathematically compensates on average for the high-volatility deficit, producing an illusion of marginal validity (80.0% overall).

---

## 3. Asymmetric Innovation Skewness

In addition to variance expansion, volatility forecast errors in `HIGH_VOLATILITY` exhibit heavy positive skewness (volatility spikes):
- Residual skewness in HIGH_VOLATILITY: 1.684
- Excess kurtosis in HIGH_VOLATILITY: 8.3029

When a market shock hits, realized volatility increases non-linearly, blowing past symmetric or marginally pooled upper bounds.

---

## 4. Remediation Strategy

To achieve reliable conditional coverage without expanding intervals in quiet markets, calibration must condition upon the market volatility state (`STATE_CONDITIONED` or `HYBRID`), dynamically allocating wider bounds to `HIGH_VOLATILITY` while tightening bounds in `LOW_VOLATILITY`.
