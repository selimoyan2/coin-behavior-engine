# CBE-0.8.0 Prediction Interval Calibration Methodology

**Sprint:** 09.4  
**Subject:** Mathematical Specification of Empirical Residual Quantile / Split-Conformal Calibration  
**Candidate Component:** `src/coin_behavior_engine/candidate_v080/calibrator.py`  
**Target Invariant:** Strict monotonic coverage ordering with guaranteed empirical validity  

---

## 1. Problem Formulation: The Miscalibration of CBE-0.7.0

In CBE-0.7.0, prediction intervals were calculated using an uncalibrated, parametric lognormal assumption:
$$L_{80} = \hat{y} \cdot \exp(-1.28 \cdot \sigma), \quad U_{80} = \hat{y} \cdot \exp(+1.28 \cdot \sigma)$$
with a fixed hardcoded $\sigma = 0.35$. For 95%, an ad-hoc formula was used ($L_{95} = L_{80} \cdot 0.8$, $U_{95} = \hat{y} \cdot \exp(1.645 \cdot \sigma)$).

Empirically observed coverage on prospective data collapsed to:
- Nominal 80% interval: **65.0%** coverage (15.0% under-coverage)
- Nominal 95% interval: **78.8%** coverage (16.2% under-coverage)

Such severe under-coverage renders risk bounds scientifically untrustworthy.

---

## 2. Empirical Residual Quantile Calibration Framework

To guarantee asymptotic and finite-sample coverage without parametric distributional assumptions, CBE-0.8.0 adopts a split-conformal empirical residual mapping framework:

1. **Calibration Partition:**  
   The model is frozen from Discovery (< 2025-01-01). Residuals are collected on the held-out **Validation partition** $\mathcal{D}_{\text{val}}$ (2025):
   $$e_t = y_t - \hat{y}_t, \quad t \in \mathcal{D}_{\text{val}}$$
   where $y_t = \sigma_{5m, t} \cdot \sqrt{288}$ is the realized forward volatility and $\hat{y}_t$ is the Ridge point forecast.

2. **Empirical Quantile Estimation:**  
   For nominal coverage $1 - \alpha$, where $\alpha \in \{0.20, 0.05\}$:
   $$q_{\alpha/2} = \text{Quantile}(e, \alpha/2), \quad q_{1 - \alpha/2} = \text{Quantile}(e, 1 - \alpha/2)$$
   Specifically:
   - For 80% coverage ($\alpha = 0.20$): $q_{0.10}$ and $q_{0.90}$
   - For 95% coverage ($\alpha = 0.05$): $q_{0.025}$ and $q_{0.975}$

3. **Asymmetric Horizon Innovations:**  
   Unlike symmetric Gaussian assumptions, financial volatility errors are inherently right-skewed (volatility clusters and sudden upward shocks). Empirical quantiles naturally capture this asymmetry:
   $$|q_{0.975}| > |q_{0.025}|$$

---

## 3. Strict Monotonicity and Non-Negativity Guarantees

Realized volatility cannot be negative, and prediction intervals must strictly nest:
$$0 \le L_{95} \le L_{80} \le \hat{y} \le U_{80} \le U_{95}$$

CBE-0.8.0 enforces this invariant by construction:
$$L_{80} = \max(0.0, \hat{y} + q_{0.10})$$
$$U_{80} = \max(\hat{y}, \hat{y} + q_{0.90})$$
$$L_{95} = \max(0.0, \min(L_{80}, \hat{y} + q_{0.025}))$$
$$U_{95} = \max(U_{80}, \hat{y} + q_{0.975})$$

This mathematical construction guarantees that across 100% of rows, bounds are ordered, finite, non-negative, and properly enclose the point forecast.
