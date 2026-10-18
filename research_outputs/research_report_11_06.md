# CBE Research Report — Sprint 11.06
## Historical News Provenance, Context Causality & Controlled Trading Experiments

**Project:** Coin Behavior Engine (CBE)  
**Sprint:** 11.06  
**Status:** COMPLETE — Offline Quantitative Audit  
**Date:** 2026-10-18 12:30:41 UTC  
**Instrument:** `BTCUSDT` Spot (5m resolution)  
**Analyzed Period:** 25 Days (7,199 5m candles, 36,000 1m candles)  
**Safety Status:** PASSIVE RESEARCH ONLY — Execution Disabled, Fail-Closed

---

## 1. Executive Summary & Verdict

Sprint 11.06 was commissioned to resolve the foundational question raised in Sprint 11.05:
**Does adding real economic news and market context improve cryptocurrency trading predictions, or was the apparent benefit merely the artifact of reducing trade frequency in a losing strategy?**

Through complete provenance verification of all 122 reported historical events, 100-seed controlled randomized ablations, trade-by-trade rejection attribution, and market regime decomposition, this audit delivers an unequivocal conclusion:

```
=============================================================================
                      FINAL SCIENTIFIC VERDICT:
                       NO_VERIFIED_CONTEXT_EDGE
=============================================================================
```

### Key Quantitative Findings:

1. **Provenance Audit Disqualification (96.7% Noise):**
   - Out of 122 ingested events, **118 were inert noise**:
     - 103 Binance CMS notices (98 were altcoin listings, token airdrops, P2P Kenyan Shilling fee waivers, or trading carnivals).
     - 14 SEC press releases (13 were traditional equity fraud or mutual fund cherry-picking cases; 1 was a broad custody rulemaking notice).
     - 1 Liquidation cascade event (`EVT-LIQ-20261007-0815`) was **NOT** an authentic derivatives order feed, but a synthetic price/volume proxy derived from kline data.
   - Only **4 events** represented genuine, observable macroeconomic news (FOMC Minutes, Fed Discount Rate Minutes, BLS CPI, BLS Employment Situation).

2. **Reproduction of Previous Results:**
   - Replicated Sprint 11.05 simulation with exact parity:
     - Strategy A (Technical Only): 137 trades, Net PnL **-\$981.48**, Return **-9.815%**, Win Rate **19.7%**, Fees **\$652.56**.
     - Strategy B (Context Aware): 91 trades, Net PnL **-\$766.61**, Return **-7.666%**, Win Rate **8.8%**, Fees **\$438.28**.
     - Strategy C (Risk Controlled): 49 trades, Net PnL **-\$305.66**, Return **-3.057%**, Win Rate **10.2%**, Fees **\$180.81**.

3. **Controlled Random Ablation (Model B vs Model C):**
   - In 100 randomized trials of 91 trades sampled from Strategy A:
     - Mean Random PnL: **-\$651.22** (Standard Deviation: \$37.55, Range: -\$744.07 to -\$563.82).
     - Mean Random Win Rate: **20.0%**.
   - Strategy B (-\$766.61, 8.8% win rate) performed **worse than the worst random seed** (-$744.07) and underperformed the random mean by **-\$115.39** ($z = -3.07, p < 0.001$).
   - The apparent "improvement" from Strategy A (-\$981.48) to Strategy B (-\$766.61) was 100% attributable to paying **\$214.28 less in fees** by trading 46 fewer times.

4. **Regime & Filter Insights:**
   - A simple technical volatility filter (Model E, avoiding extreme ATR expansion or compression) achieved **-\$554.90** Net PnL and **5.60% Max Drawdown**, beating news context filtering by **+\$211.71** with zero news data.
   - For the first 14 days of the 25-day dataset, Strategy B took 0 trades because verified news coverage was below threshold. Its smaller loss was entirely due to sitting in cash during a downtrend.

---

## 2. Deliverables Summary

| Artifact Name | Format | Purpose | Status |
| :--- | :--- | :--- | :--- |
| `historical_news_provenance_audit.csv` | CSV | 122-event provenance, latency, and relevance classification | VERIFIED |
| `verified_event_coverage_report.md` | Markdown | Exhaustive source coverage and archival limitations report | VERIFIED |
| `reproduced_sprint11_05_results.json` | JSON | Independent numerical reproduction of Sprint 11.05 ledger | VERIFIED |
| `context_ablation_experiments.csv` | CSV | Models A through G performance across 100 random seeds | VERIFIED |
| `rejected_trade_attribution.csv` | CSV | 121-trade attribution of rejected signals and avoided PnL | VERIFIED |
| `market_regime_comparison.csv` | CSV | Performance breakdown across 5 defined market regimes | VERIFIED |
| `context_edge_statistical_report.md` | Markdown | Formal hypothesis test, Welch's t-test and bootstrap analysis | VERIFIED |
| `research_report_11_06.md` | Markdown | This comprehensive master research synthesis | VERIFIED |
| `run_manifest_11_06.json` | JSON | Cryptographic run manifest with Git commit and checksums | VERIFIED |

---

## 3. Engineering Recommendations for Next Sprints

1. **Cease High-Frequency News Filtering for Intraday Scalping:** Textual headlines do not improve 5-minute technical trend predictions; their latency and ambiguity degrade entry timing.
2. **Prioritize True Structural Market Regimes:** Volatility compression and higher-timeframe trend alignment (Models E & F) provided far stronger risk reduction than economic news.
3. **Address Negative Expectancy at the Technical Core:** No filter (news, volatility, or random) can make a system profitable if its raw signal expectancy after transaction costs is negative. Future research must focus on regime-dependent edge discovery.
