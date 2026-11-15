# SPRINT 34 — POINT-IN-TIME THRESHOLD CORRECTION
## Rigorous Causal Calibration & Elimination of Lookahead Bias

- **Sprint ID:** `CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA`
- **Methodology Implemented:** Pre-Declared Frozen Calibration & Expanding Causal Window
- **Causal Guarantee:** Classification at timestamp $T$ depends strictly on $t \le T$; zero dependency on $t > T$.

---

### 1. MATHEMATICAL FORMULATION

#### 1.1 The Lookahead Defect in Sprint 33
In Sprint 33, thresholds $\Theta$ were computed as:
$$\Theta = f\left(\{x_t\}_{t=0}^{N-1}\right)$$
$$\text{Regime}(T) = g(x_T, \Theta)$$

Because $\Theta$ integrates information from $t = T+1 \dots N-1$, the classification at time $T$ was conditioned on future observations.

#### 1.2 Causal Formulation (Sprint 34 Standard)
In Sprint 34, thresholds must satisfy:
$$\Theta(T) = f\left(\{x_t\}_{t=0}^{T-1}\right) \quad \text{or} \quad \Theta = f\left(\mathcal{D}_{\text{Discovery}}\right)$$
$$\text{Regime}(T) = g(x_T, \Theta(T))$$

Where $\mathcal{D}_{\text{Discovery}}$ is a chronological calibration split completely preceding the evaluation period ($T_{\text{Discovery}} < T$).

---

### 2. SUPPORTED CAUSAL MODES IN SPRINT 34

1. **`PREDECLARED_FROZEN` (Primary Canonical Standard):**
   - Thresholds are calibrated on the pre-declared Discovery split (2023 calibration partition: 2,000 hourly bars, October–December 2023).
   - Calibrated values:
     - $\tau_{\text{vol,25}} = 0.2548$
     - $\tau_{\text{vol,75}} = 0.4540$
     - $\tau_{\text{comp,25}} = 0.6232$
     - $\tau_{\text{comp,75}} = 1.2040$
     - $\tau_{\text{tail}} = 1.25 \times \tau_{\text{vol,75}} = 0.5675$
   - These thresholds remain constant across the entire 2024 and 2025 out-of-sample evaluation.
   - **Prefix Invariance:** Trivially and mathematically guaranteed ($100\%$ invariant).

2. **`EXPANDING_CAUSAL_WINDOW` (Adaptive Causal Standard):**
   - At timestamp $T$, percentiles are calculated over the causal history $\{x_t\}_{t=0}^{T-1}$.
   - Minimum warm-up period: 720 hours (30 days). For $T < 720$, the pre-declared prior constants are used.
   - For all $T$, no candle $t \ge T$ is included in the quantile calculation.
   - **Prefix Invariance:** Guaranteed because appending observations at $T+k$ cannot affect the slice $[0, T-1]$.

---

### 3. VERIFICATION OF PREFIX INVARIANCE

Prefix invariance is formally defined as:
$$\forall T \in [0, N-k], \quad \text{Evaluate}(\mathcal{S}_{0:T})[T] \equiv \text{Evaluate}(\mathcal{S}_{0:T+k})[T]$$

A test suite evaluating prefix invariance across multiple horizons ($k \in \{24, 72, 168, 720, 2160\}$ bars) and distinct historical regimes confirms $100.0\%$ concordance between truncated and full-series evaluations.
