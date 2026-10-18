# CBE Sprint 11.15.1 Prospective Statistical Validity & Evaluation Protocol Audit

**Sprint:** CBE — 11.15.1  
**Mission:** Prospective Protocol Hardening & Independent Readiness Audit  
**Audit Target:** Sample Independence, Multiple Hypothesis Correction & Economic Benchmarking  
**Audit Date:** 2026-10-18T22:30:00+03:00  
**Base Commit:** `09773621f7026ac2630fb7674cd11aadaf934a70`  
**Plan Audited:** `research_outputs/prospective_evaluation_plan.md`  

---

## 1. Executive Summary & Methodological Rectification

This independent scientific audit evaluates the prospective evaluation plan delivered in Sprint 11.15. 

### Core Audit Rectification:
In Sprint 11.15 documentation, thirty calendar days and 20 completed trades were described in language suggesting they were thresholds for declaring statistical viability or selecting a live deployment candidate.

**Scientific Correction:** 30 days and 20 trades are **minimum observation milestones**, NOT statistical proof of an economic edge. In spot BTC markets, a 20-trade sample exhibits enormous binomial uncertainty (95% confidence interval for a 50% observed win rate spans from $28.4\%$ to $71.6\%$). Testing five concurrent policies without multiple-comparison corrections inflates the family-wise false discovery rate to $1 - (1-0.05)^5 \approx 22.6\%$.

Sprint 11.15.1 formalizes six mandatory statistical corrections:

---

## 2. Statistical Rigor Protocol (6 Pillars)

### Pillar 1: Multiple Hypothesis Testing Correction
When evaluating five candidate policies ($M = 5$) concurrently against the null hypothesis $H_0$ (zero risk-adjusted excess return over Policy A cash and Policy B buy-and-hold):
- **Bonferroni Significance Threshold:**
  $$\alpha_{\text{adjusted}} = \frac{\alpha_{\text{nominal}}}{M} = \frac{0.05}{5} = 0.010$$
- Any prospective $t$-statistic or bootstrap return comparison must achieve $p < 0.010$ before statistical significance can be claimed.

### Pillar 2: Serial Correlation & Effective Sample Size ($N_{\text{eff}}$)
5-minute cryptocurrency returns and market volatility exhibit heavy autocorrelation and volatility clustering.
- The effective sample size $N_{\text{eff}}$ must be computed via the first-order autocorrelation $\rho_1$:
  $$N_{\text{eff}} = N \cdot \frac{1 - \rho_1}{1 + \rho_1}$$
- Standard errors and confidence bounds must be computed using $N_{\text{eff}}$, rather than raw observation counts $N$.

### Pillar 3: Overlapping Horizon Decoupling
Multi-bar outcome evaluations (e.g. 24h / 288-bar forward returns) create moving-average error structures. Standard Ordinary Least Squares (OLS) standard errors are severely downward-biased.
- **Enforcement:** All multi-horizon statistical inference must employ **Newey-West (HAC)** covariance estimators or non-overlapping block bootstrapping with block length $L \ge \text{Horizon}$.

### Pillar 4: Unequal Market Exposure Normalization
- Policy A has 0% market exposure. Policy B has 100% market exposure. Policies D and E spend significant time in USDT cash.
- Comparing raw absolute return without adjusting for time-at-risk produces biased conclusions.
- **Required Metrics:**
  - **Exposure-Adjusted Return:** $\text{Return}_{\text{annualized}} / \text{Market Exposure Fraction}$
  - **Information Ratio against Buy-and-Hold:** $\frac{R_p - R_B}{\sigma(R_p - R_B)}$
  - **Sortino & Calmar Ratios:** Computed strictly over active holding periods.

### Pillar 5: Counterfactual Diagnostics vs Realized Equity Invariant
- **Rule:** Avoided drawdown in cash ($DD_{\text{avoided}}$) and missed appreciation ($App_{\text{missed}}$) are counterfactual behavioral diagnostic measures.
- **Accounting Invariant:** Under no circumstances may counterfactual avoided drawdown be added to portfolio equity as "economic gain".
- Realized economic performance is determined exclusively by actual account balance:
  $$\text{Ending Equity} = \text{Starting Capital} + \text{Realized Net PnL}$$

### Pillar 6: Fail-Safe Sample Size Verdict
- If after an observation epoch the completed sample size has not attained sufficient statistical power to reject $H_0$ under the Bonferroni-corrected threshold:
- **Mandatory Verdict:** **`INSUFFICIENT_PROSPECTIVE_EVIDENCE`**
- Under no circumstances will a "winner" be crowned or recommended for real-money deployment on marginal or unproven samples.

---

## 3. Disentangled Evaluation Taxonomy

To prevent premature commercialization claims, Sprint 11.15.1 formally replaces all language implying "Live Trading Readiness" with a multi-layered scientific verdict hierarchy:

```
[Scientific Verdict Hierarchy]
├── Layer 1: Protocol Infrastructure Integrity -> [VERIFIED / FAILED]
├── Layer 2: Market Data Provenance & Freshness -> [VERIFIED / CONTAMINATED]
├── Layer 3: Statistical Predictive Edge (H1)  -> [CONFIRMED / REJECTED / INSUFFICIENT_EVIDENCE]
├── Layer 4: Net Economic Viability (H2/H3)    -> [VIABLE / UNVIABLE / INSUFFICIENT_EVIDENCE]
└── Layer 5: Operational Governance State      -> [FROZEN_OFFLINE_RESEARCH_ONLY]
```

All terms such as *"Viable Live Trading Candidate"* are expunged from the protocol and replaced with:  
**`RESEARCH_POLICY_UNTESTED_PROSPECTIVELY`**.
