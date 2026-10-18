# Context Edge Statistical Significance Report
**Sprint 11.06 Deliverable**  
**Generated:** 2026-10-18 12:30:41 UTC  
**Evaluation Mode:** Offline Quantitative Hypothesis Testing  
**Primary Research Question:** Does adding macroeconomic news and market context provide a genuine, reproducible predictive edge, or is the apparent loss reduction purely an artifact of trading less frequently in a negative-expectancy strategy?

---

## 1. Formal Hypothesis & Statistical Test Formulation

- **Null Hypothesis ($H_0$):** Market-context filtering provides no true predictive edge over random trade pruning after controlling for trade frequency ($E[PnL_B] \le E[PnL_C]$).
- **Alternative Hypothesis ($H_1$):** Market-context filtering provides an authentic informational edge ($E[PnL_B] > E[PnL_C]$).
- **Controlled Variable:** Exactly **91 trades** executed across identical execution friction (0.20% taker fee + 0.10% slippage, \$10,000 initial capital).

---

## 2. Experimental Ablation Comparison Table

| Model ID | Description | Trade Count | Net PnL (\$) | Net PnL (Mean ± Std) | Return (%) | Win Rate (%) | Max Drawdown (%) | Profit Factor | Sharpe |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model A** | Technical Only | 137 | \$-981.48 | — | -9.81% | 19.7% | 9.78% | 0.109 | -33.59 |
| **Model B** | Context Aware | 91 | \$-766.61 | — | -7.67% | 8.8% | 7.67% | 0.038 | -33.67 |
| **Model C** | Random Trade Matching (100 seeds) | 91 | \$-651.22 | \$-651.22 ± \$37.55 | -6.51% | 20.0% | 6.52% | 0.112 | -329.98 |
| **Model D** | Time-Matched Window Filter (100 seeds) | 116 | \$-837.94 | \$-837.94 ± \$70.58 | -8.38% | 19.5% | 8.35% | 0.108 | -30.98 |
| **Model E** | Volatility-Only Filter (ATR ratio) | 74 | \$-554.90 | — | -5.55% | 13.5% | 5.60% | 0.064 | -29.11 |

---

## 3. Statistical Significance Test Results

1. **Comparison with Random Trade Matching (Model B vs Model C):**
   - **Model B Net PnL:** \$-766.61
   - **Model C (Random 91 Trades) Mean PnL:** \$-651.22 (Standard Deviation: \$37.55)
   - **Model C Range (Min to Max):** \$-744.07 to \$-563.82
   - **Z-Score:** `-3.07` standard deviations below random mean.
   - **Bootstrap Empirical P-Value ($P(PnL_C \le PnL_B)$):** `p = 0.000` (In 100 out of 100 randomized trials, random trade removal outperformed context-aware filtering).
   - **Win Rate Collapse:** Model B achieved only **8.8% win rate** compared to **20.0% win rate** for random 91-trade sampling.

2. **Comparison with Pure Volatility Filtering (Model B vs Model E):**
   - Simple market volatility filtering without any news data (Model E) achieved **-\$554.90** Net PnL and **5.60% Max Drawdown**, outperforming Model B by **+\$211.71** with significantly lower tail risk.

---

## 4. Definitive Audit Verdict

> **VERDICT: NO_VERIFIED_CONTEXT_EDGE**

### Scientific Explanation:
1. **The "Benefit" Was Purely Reduced Trade Count:** In Sprint 11.05, Strategy A lost -\$981.48 over 137 trades (an expectancy of -\$7.16 per trade, driven by 0.30% round-trip trading friction and poor technical signal quality). Reducing trade count from 137 to 91 reduced total fees paid from \$652.56 to \$438.28 (\$214.28 saved in transaction friction).
2. **Context Filtering Was Harmful, Not Helpful:** The average random trade reduction of 46 trades resulted in an average loss of -\$651.22. Strategy B lost -\$766.61 — which is **worse than all 100 random seeds**.
3. **Causal Mechanism:** Macroeconomic news headlines caused the context engine to filter out trades during volatile intervals. However, those volatile intervals contained sharp mean-reversion counter-trend bounces that were profitable in Strategy A. By systematically eliminating high-volatility bounces while entering chop during quiet periods, news filtering degraded win rate from 19.7% to 8.8%.
4. **Final Conclusion:** Real-time historical economic news context provided **zero positive alpha** and **no defensive advantage** over simple trade frequency reduction.
