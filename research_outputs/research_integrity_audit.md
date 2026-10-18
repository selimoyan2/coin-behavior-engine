# CBE Research Integrity Audit & Historical Discrepancy Reconciliation
**Sprint 11.04 Deliverable — Mandatory Research Integrity Review**  
**Audit Scope:** Verification of Binance source data, candle counts, aggregation boundaries, benchmark accounting, and event classification.  
**Integrity Rule:** Previous research reports are preserved as immutable historical artifacts; corrections are formally registered here.

---

## 1. Executive Reconciliation Summary

A comprehensive post-implementation audit of Sprint 11.03 research outputs identified three significant integrity discrepancies:
1. **Candle Count & Boundary Aggregation Discrepancy:** The previous run reported 36,000 1m candles aggregated into 7,201 5m candles.
2. **Benchmark Drawdown Hardcoding Error:** Buy & Hold maximum drawdown was reported as 0.00% despite an -8.51% peak-to-trough market drop.
3. **Event Verification Status Overstatement:** Five events were labeled `VERIFIED` despite lacking verifiable primary permalinks or third-party corroboration.

All three discrepancies have been identified, mathematically reconciled, and programmatically corrected in Sprint 11.04.

---

## 2. Granular Discrepancy Investigation & Corrections

### A. Reconciling 36,000 1-Minute vs. 7,201 5-Minute Candles

- **Audit Finding:**
  $36,000 \text{ bars} / 5 = 7,200 \text{ bars}$. An exact integer division yields 7,200 buckets, yet 7,201 bars were emitted in Sprint 11.03.
- **Root Cause Identified:**
  The downloaded 1m dataset started at `2026-09-23T11:34:00Z` and ended at `2026-10-18T11:33:00Z`.
  In 5-minute bucket grouping:
  - Bucket 1 (`11:30`): contained ONLY **1** constituent 1m bar (`11:34:00Z`).
  - Interior buckets (`11:35` to `11:25`): contained **7,199** complete 5-bar buckets ($7,199 \times 5 = 35,995$ 1m bars).
  - Final bucket (`11:30`): contained ONLY **4** constituent 1m bars (`11:30` to `11:33`).
  - Total emitted: $1 + 7,199 + 1 = 7,201$ buckets.
  The Sprint 11.03 aggregator emitted partial, incomplete boundary buckets as completed 5m closed candles.
- **Sprint 11.04 Remediation:**
  [`TimeframeAggregator`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/src/coin_behavior_engine/research_lab/historical_data.py) now defaults to `allow_partial_boundaries = False`. Incomplete boundary buckets are discarded. The clean reconciled dataset contains **exactly 7,199 complete, unbroken 5-minute candles** covering `2026-09-23T11:35:00Z` to `2026-10-18T11:29:59Z`.

---

### B. Correction of Benchmark Buy-and-Hold Drawdown & Mark-to-Market Accounting

- **Audit Finding:**
  Sprint 11.03 strategy comparison table reported:
  `Benchmark_Buy_and_Hold: Max Drawdown (%) = 0.00%`.
- **Root Cause Identified:**
  The evaluator hardcoded `0.0%` for Buy & Hold drawdown in the comparison table dictionary instead of tracking the mark-to-market equity path.
- **Sprint 11.04 Mathematical Reconciliation:**
  Under identical execution frictions (0.05% slippage on entry/exit, 0.10% taker fee on entry/exit):
  - Starting Cash: \$10,000.00
  - Entry Fill: \$85,554.77 (Open of bar 0 + 0.05% slippage)
  - Entry Fee: \$10.00
  - Position: 0.116767 BTC
  - True Mark-to-Market Maximum Drawdown: **-8.27%**
  - Exit Fill: \$82,062.98 (Close of final bar - 0.05% slippage)
  - Exit Fee: \$9.57
  - Final Capital: \$9,572.82
  - True Net Return: **-4.27%** (Net PnL: -\$427.18)
  - Annualized Sharpe: **-1.59**
  - Total Fees Paid: \$19.57

---

### C. Validation of BTC Peak, Trough, and Decline Magnitude

- **Audit Finding:**
  Sprint 11.03 executive notes reported peak of \$86,999 on Oct 5 (-8.28% decline), whereas the Case Study reported peak of \$87,220 on Oct 2 (-8.51% decline).
- **Forensic Verification:**
  - Absolute Dataset Peak: **\$87,220.00** at `2026-10-02T12:30:00Z` (confirmed across 1m and 5m series).
  - Intermediate Lower High: **\$86,999.10** at `2026-10-05T14:15:00Z`.
  - Absolute Dataset Trough: **\$79,800.00** at `2026-10-15T13:55:00Z`.
  - Absolute Peak-to-Trough Decline: **-8.51%** (-\$7,420.00).
  - Earliest Objective Risk Signal: `2026-10-02T14:25:00Z` (115 minutes after peak; transition into `TRENDING_BEAR` regime with 3-bar drop > 1.5%).

---

### D. Historical Event Source Verification & Classification Audit

- **Audit Finding:**
  All five curated events in Sprint 11.03 were marked `VERIFIED`, but lacked authentic primary source permalinks.
- **Audit Classifications Applied:**
  1. `EVT-20260921-FOMC-HAWK`: Reclassified to `REPORTED_UNCONFIRMED`. Published `2026-09-21T18:00:00Z`, which is **outside the active dataset observation window** (dataset starts Sept 23). Marked `is_pre_dataset_window = True`.
  2. `EVT-20261006-SEC-WARNING`: Reclassified to `UNSUPPORTED`. Generic root URL (`https://www.sec.gov/news/press-release`) without specific docket or document permalink.
  3. `EVT-20261007-LIQUIDATION-SPIKE`: Reclassified to `RETROSPECTIVE_INTERPRETATION`. Sourced from internal mock URL (`https://coin-behavior-engine.local/liquidation`).
  4. `EVT-20261008-BOTTOM-ABSORPTION`: Reclassified to `RETROSPECTIVE_INTERPRETATION`. Sourced from internal mock URL (`https://coin-behavior-engine.local/flows`).
  5. `EVT-20261014-CPI-SURPRISE`: Reclassified to `UNSUPPORTED`. Generic root URL (`https://www.bls.gov/cpi`) without specific monthly release permalink.
- **Research Integrity Enforcement:**
  Because 0 of 5 events meet the strict evidentiary standard for `VERIFIED_EVENT`, **Strategy B (Verified Context Aware) is prohibited from using unverified news inputs**. Strategy B explicitly reports insufficient verified news coverage and abstains (`NO_TRADE`), protecting capital and maintaining research integrity.

---
*Report published as part of Sprint 11.04 Research Integrity Review.*
