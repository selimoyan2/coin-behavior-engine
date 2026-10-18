# CBE — PREDICTION METRIC & STATISTICAL BASELINE AUDIT
## Independent Mathematical Validation of Probabilistic Predictions, Horizons & Baselines

**Audit Executed UTC:** 2026-10-18T13:08:20.857221+00:00  
**Evaluated Ledger:** `research_outputs/conditional_predictions.csv` (1529 queries)  
**Formal Audit Verdict:** `NO_VERIFIED_DIRECTIONAL_EDGE`  

---

## 1. Executive Summary & Critical Baseline Finding

Sprint 11.07 reported a **69.82% directional accuracy** and a **+31.25% Brier Skill Score over Random Walk**. 
This audit independently validates the mathematical execution of those calculations, but places them within their true statistical context.

### The Baseline Comparison Hierarchy

| Predictor / Baseline | 3-Class Accuracy | Binary Directional Accuracy (Moves Only) | Multi-Class Brier Score | Advantage over Model |
|---|---|---|---|---|
| **CBE Analogue Model** | **69.72%** | **51.9%** (232 / 447) | **0.153** | Base |
| **Empirical Unconditional Prior** | — | 50.00% | **0.1521** | **Model Loses by +0.0009** |
| **Majority Class (Always NEUTRAL)** | **70.77%** | 0.00% | 0.1949 | Model Loses by 1.05% |
| **Uniform Random Walk (1/3, 1/3, 1/3)** | 33.33% | 50.00% | 0.2222 | Model Wins by +31.14% |

> [!WARNING]
> **Primary Audit Revelation:**
> 1. The apparent high accuracy (69.82%) is driven by **severe class imbalance**: **70.77% of all 4-hour forward intervals are NEUTRAL** ($[-0.60\%, +0.60\%]$). A naive trivial strategy that simply predicts "NEUTRAL" for every single candle achieves **70.77% accuracy**.
> 2. When evaluated using probabilistic calibration, the model's Brier score of **0.153** beats crude uniform guessing (0.2222), but fails to outperform the stationary **Empirical Unconditional Frequency prior (0.1521)**.
> 3. When restricted strictly to actual market moves (UP or DOWN), the model's binary directional accuracy is **51.9%**, which is statistically indistinguishable from a coin flip ($p = 0.443$).
>
> In accordance with scientific integrity standards, the formal rating is:
> **`NO_VERIFIED_DIRECTIONAL_EDGE`** over the empirical unconditional prior.

---

## 2. Sample Overlap & Degrees of Freedom

- **Total Test Predictions:** 1529 timestamped observations.
- **Decision Cadence:** 12 bars (1.0 hour).
- **Forward Horizon:** 48 bars (4.0 hours).
- **Autocorrelation / Overlap:** Because each 4-hour forecast advances by only 1 hour, consecutive predictions share **75% of the same price movement**.
- **Effective Independent Sample Size:**
  $$N_{\text{eff}} = \frac{N}{4} = 383 \text{ non-overlapping 4-hour blocks}$$

---

## 3. Why the Apparent Signal Fails to Generate Trading Profits

1. **Threshold Squeeze:** To capture moves that exceed exchange friction ($> 0.19\%$), the forecast target was set at $\pm 0.60\%$. But because 70.8% of market time is spent compressing inside that threshold, directional forecasts occur primarily near range exhaustion points.
2. **Binary Drift:** Conditional on a move occurring, predicting UP vs DOWN with 51.9% accuracy provides an expected gross edge of only $\approx 0.02\%$ per trade, which is entirely obliterated by the $0.28\%$ friction hurdle rate.
