# 21 — Final Acceptance & Empirical Evaluation Report: Sprint 31
## Sealed BTC Strategy Evaluation & Offline Shadow Research

**Sprint ID:** `CBE_SPRINT31_SEALED_SHADOW_EVALUATION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Verified Baseline:** `9e4fa2229ed5c29118052a8052d86289a1589406`  
**Execution Date:** `2026-11-15T10:22:46.726154+00:00`  
**Acceptance Status:** **`SPRINT_31_FUNCTIONAL_DELIVERY_VERIFIED`** & **`SPRINT_31_EMPIRICAL_EVALUATION_VERIFIED`**  
**Canonical Model Status:** `CBE-0.7.0` (STRICTLY FROZEN) — `NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`  
**Production Status:** STRICT ZERO-TOUCH (Container `fdbdba96e677`, 0 restarts)  

---

# 1. EXECUTIVE MISSION & OUTCOMES

Sprint 31 successfully answered the core scientific question of the Coin Behavior Engine BTC timing research programme:

> **Can the low-turnover timing policies developed in Sprint 30 maintain their historical risk-control characteristics on a genuinely unseen historical dataset without adjusting their parameters?**

The answers are definitive, empirically grounded, and mathematically reconciled:

1. **Risk Control & Transaction Cost Reduction Generalize Robustly:**
   - Transaction costs were reduced by **88.31%** (from $6,789.12 to $793.47).
   - Net return improved by **+33.81 percentage points** over naive trend following (-28.80% vs -62.60%), preserving $3,380.57 of equity.
   - Maximum drawdown severity was reduced by **25.92 percentage points** (-39.20% vs -65.12%).
   - Hypotheses **H1, H2, and H3** are **`SUPPORTED`**.

2. **Trend-Following Fails to Outperform Buy & Hold in Choppy Markets:**
   - On the unseen 2025 dataset, passive Buy & Hold delivered **-9.69%**, while Trend Low Turnover delivered **-28.80%** (excess alpha: **-19.10 pp**).
   - Hypothesis **H4** is **`UNSUPPORTED`** (Empirically Rejected).
   - In non-trending, range-bound markets, active timing generates negative excess returns due to signal lag at reversals and inevitable friction.

3. **Incremental Value of Regime Filtering:**
   - Incorporating derived regime confirmation improved return by **+20.27 pp** over naive trend following (-42.33% vs -62.60%) and Sharpe by **+0.73**.
   - Hypothesis **H5** is **`SUPPORTED`** (with explicit notice that canonical CBE-0.7.0 parity was not used; only the derived research classifier).

---

# 2. SEVENTEEN DETAILED RESEARCH ANSWERS

### 1. Has the evaluation dataset genuinely never been seen by policies or parameters?
**Yes.** The 2025 dataset (`2025-01-01` to `2025-12-31`) was sealed in offline storage. All policies and parameters were designed and fitted strictly on 2024 data during Sprint 30. The holdout usage ledger confirmed zero prior access events.

### 2. What is the exact SHA-256 seal of the frozen policy package?
The seal is **`73a8349dcf340be2360631df4e6307e5cb09ffa3b34ead81d27b9a0215f2ed3c`**. Any change in parameter values modifies this hash and fails verification.

### 3. Did any parameter tuning or optimization take place after seeing the 2025 results?
**No.** Zero parameter alterations were performed. The evaluation was strictly one-way and immutable.

### 4. What is the status of the canonical model CBE-0.7.0?
The canonical model remains strictly frozen. Its status is **`NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE`**. The regime filtering evaluated corresponds exclusively to the **Derived Research Classifier**.

### 5. What are the exact mathematical properties of the 2025 dataset?
Total 8,760 hourly candles, 0 missing gaps, 0 duplicates, strictly monotonic timestamps, and 0 OHLCV rule violations ($H \ge \max(O,C,L)$, $L \le \min(O,C,H)$, $V \ge 0$).

### 6. How does the manual offline import workflow enforce provenance integrity?
It checks files against format, schema, monotonicity, and holdout contamination, strictly rejecting caller-supplied self-declarations and assigning `PROVISIONAL_OFFLINE_IMPORT`.

### 7. What are the net returns of the 6 evaluated policies in 2025?
- `POLICY_BUY_AND_HOLD`: **-9.69%** (Final Equity: $9,030.69)
- `POLICY_USDT_CASH`: **0.00%** (Final Equity: $10,000.00)
- `POLICY_SIMPLE_TREND`: **-62.60%** (Final Equity: $3,739.79)
- `POLICY_TREND_LOW_TURNOVER`: **-28.80%** (Final Equity: $7,120.36)
- `POLICY_PERIODIC_REBALANCE`: **-2.23%** (Final Equity: $9,777.47)
- `POLICY_DERIVED_REGIME_CONFIRMATION`: **-42.33%** (Final Equity: $5,767.02)

### 8. Did turnover control reduce transaction costs by at least 50% (H1)?
**Yes.** Total costs fell from $6,789.12 to $793.47, an **88.31% reduction** (trades fell from 616 to 57). H1 is **SUPPORTED**.

### 9. Did turnover control improve net return over naive trend (H2)?
**Yes.** Net return rose from -62.60% to -28.80% (+33.81 pp), preserving $3,380.57 of equity. H2 is **SUPPORTED**.

### 10. Did turnover control reduce maximum drawdown severity (H3)?
**Yes.** Maximum drawdown decreased from -65.12% to -39.20% (a 25.92 pp severity reduction). H3 is **SUPPORTED**.

### 11. Did active timing outperform passive Buy & Hold in 2025 (H4)?
**No.** Buy & Hold (-9.69%) beat Trend Low Turnover (-28.80%) by 19.10 pp. H4 is **UNSUPPORTED**.

### 12. Did derived regime confirmation add incremental value over Simple Trend (H5)?
**Yes.** Return improved by +20.27 pp (-42.33% vs -62.60%) and Sharpe improved by +0.73. H5 is **SUPPORTED**.

### 13. What is the exact cash and satoshi reconciliation status?
Double-entry accounting balanced to 0.00000000 satoshi discrepancy across all 8,760 hours. Value is strictly conserved.

### 14. What are the key features of Dashboard V9?
Subtab "Gölge Değerlendirme" with Evaluation Readiness, Offline Dataset Import, Sealed Evaluation Execution, Shadow Portfolio with HTML5 Canvas equity curve, Benchmark Comparison table, and Hypotheses findings cards.

### 15. Were all security gates and test suites verified?
- Live trading is permanently disabled (HTTP 403 Forbidden).
- Sprint 31 test suite: 34/34 passed (100%).
- Full regression suite: ~3,506 tests passed cleanly.
- Playwright multi-viewport: Desktop, Tablet, Mobile verified with 0 console errors.

### 16. Was staging deployment verified?
Deployed to `srv1114257:18080`, `/ready` returned HTTP 200, and container restart recovery was verified.

### 17. Was production container zero-touch maintained?
**Yes.** Container `fdbdba96e677` was verified running untouched with strictly **0 restarts**.

---

# 3. ACCEPTANCE CERTIFICATION TOKENS

```text
SPRINT_31_FUNCTIONAL_DELIVERY_VERIFIED
SPRINT_31_EMPIRICAL_EVALUATION_VERIFIED
```
