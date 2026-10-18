# Sprint 11.06 Methodology Audit & Experimental Corrections
**Sprint 11.07 — Phase 1 Research Audit**  
**Audit Timestamp:** 2026-10-18 12:49:02 UTC  
**Audited Target:** Sprint 11.06 Controlled Ablation Experiments (`research_outputs/context_ablation_experiments.csv`)  
**Status:** Methodological Corrections Documented & Implemented  

---

## 1. Executive Summary

Sprint 11.06 investigated whether market-context filtering provided genuine predictive alpha or was merely an artifact of reduced trade frequency in a losing strategy. The final verdict correctly concluded `NO_VERIFIED_CONTEXT_EDGE`.

However, a formal audit of Sprint 11.06 experimental procedures reveals two significant methodological defects that must be corrected for all future research:

1. **Static Post-Hoc Trade Selection Defect (Model C):**
   In Model C (Random Trade Matching), 91 trades were randomly drawn from Strategy A's 137 completed trades post-hoc. This static sampling assumes that trade opportunities are path-independent, ignoring that skipping a trade frees portfolio cash and allows entering alternative subsequent signals.
2. **Violation of i.i.d. Assumptions in Statistical Testing:**
   Reporting standard parametric Welch's $t$-tests on non-independent trade series violates basic statistical assumptions due to autocorrelation, overlapping prediction windows, and regime clustering.

This report documents these defects in detail, quantifies their impact, and establishes the strict causal event-driven backtesting standards enforced in Sprint 11.07.

---

## 2. Detailed Audit Findings

### Defect 1: Static Post-Hoc Trade Selection vs. Event-Driven Portfolio State

In Sprint 11.06, Model C evaluated random trade frequency reduction by sampling 91 trades out of Strategy A's 137 trades across 100 seeds.

#### Why This Is Methodologically Flawed:
- **Sequential Position Locking:** In CBE's single-asset spot simulator, entering a trade locks capital and prevents opening any new position until the existing trade is exited (stop-loss, take-profit, or max holding bars).
- **Alternative Entry Opportunities:** When a filter (news, volatility, or random blackout) rejects a trade at bar $t$, the portfolio remains 100% in cash. If another valid buy candidate occurs at bar $t+k$ while Strategy A was still in position, the filtered strategy is free to enter that new trade!
- **Empirical Proof:** In Sprint 11.06's actual simulation:
  - Strategy A executed 137 trades.
  - Strategy B executed 91 trades.
  - **Strategy A and Strategy B shared only 13 identical trade entries!**
  - Strategy B took **78 completely distinct trades** that Strategy A never entered because Strategy A was locked in other positions.
- **Consequence:** Subsampling Strategy A's executed trades post-hoc does NOT represent how a random trading strategy would actually behave in real time. It measures an artificial subset of Strategy A's path, rather than an authentic alternative portfolio trajectory.

### Defect 2: Statistical Significance Testing on Non-i.i.d. Returns

Sprint 11.06 evaluated the difference between Model B and Model C using parametric $t$-statistics and $z$-scores ($z = -3.07$).

#### Why This Is Methodologically Flawed:
- **Autocorrelation & Volatility Clustering:** Financial time series exhibit volatility clustering and regime dependency (Mandelbrot, 1963; Engle, 1982). Trade returns within the same macro selloff or chop regime are strongly correlated.
- **Overlapping Horizons:** Trades occurring within the same 24-hour window share common market shocks and cannot be treated as independent degrees of freedom.
- **Degrees of Freedom Overstatement:** Treating 91 trades as 91 independent degrees of freedom dramatically inflates statistical confidence.
- **Correct Approach:** Use **block bootstrap** (Kunsch, 1989; Politis & Romano, 1994) or **full event-driven randomized strategy replays** (where random seeds dictate real-time signal entry decisions, as demonstrated in Model D).

---

## 3. Methodological Corrections Implemented in Sprint 11.07

All subsequent research in Sprint 11.07 and beyond enforces the following standards:

1. **Full Event-Driven Portfolio Replay:**
   No randomized or ablation experiment may ever evaluate trades post-hoc. Every comparison must execute sequentially through the simulator:
   $$\text{Decision}(t) \longrightarrow \text{Order}(t+1) \longrightarrow \text{Inventory Tracking} \longrightarrow \text{Exit}(t+k)$$
2. **Causal Historical Analogues:**
   Predictions must be derived from historical market patterns observed strictly before the decision bar, with a mandatory purged buffer ($t' < t - \text{horizon}$) to eliminate overlapping forward leakage.
3. **Chronological Walk-Forward Partitioning:**
   Expanding or rolling walk-forward windows where model parameters and historical memory are frozen before evaluating holdout periods.
4. **Separation of Missing Feeds from Neutral Market Observations:**
   A quiet news period with a verified healthy feed is an informative observation; a disconnected feed or missing provider is an unobserved state.

---

## 4. Conclusion

Sprint 11.06's qualitative finding that news context did not provide positive alpha remains correct, but the mechanism is now understood with higher mathematical rigor: **Strategy B's underperformance was driven by path-dependent entries into choppy regimes that occurred because it had abstained earlier.**

Sprint 11.07 advances to a true **Behavioral Learning Engine** that learns from 365 days of empirical market analogues rather than relying on brittle heuristic rules.
