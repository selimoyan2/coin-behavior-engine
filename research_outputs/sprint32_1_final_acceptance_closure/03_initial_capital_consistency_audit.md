# 03 — Initial Capital Consistency & Configuration Audit
## Comprehensive Cross-System Audit of Portfolio Starting Capital

**Sprint ID:** `CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE`  
**Audit Date UTC:** `2026-11-15T14:12:00Z`  
**Audited Starting Capital:** `10,000.00 USDT`  
**Classification:** `INITIAL_CAPITAL_VERIFIED_CONSISTENT_AT_10K`  

---

## 1. Discrepancy Statement

In the executive narrative and prompt deliverables for Sprint 32, certain texts referenced an initial portfolio capital of `$100,000` (100,000 USDT). Conversely, all underlying code artifacts, quantitative results, and simulation ledgers recorded a starting capital of `$10,000` (10,000.0 USDT).

This audit conducts an exhaustive, read-only verification across all repository layers to identify the authentic simulation configuration, correct erroneous documentation, and enforce consistency.

---

## 2. Multi-Layer Cross-System Forensic Audit

| Layer | File / Artifact Path | Audited Initial Capital Field | Observed Value | Match Status |
|---|---|---|---:|---|
| **Simulation Engine** | `src/coin_behavior_engine/product/btc_timing_research/sealed_evaluation_engine.py:552` | `initial_capital_usdt` | 10,000.0 USDT | **MATCH** |
| **Persisted Shadow Data** | `research_outputs/sprint31_sealed_shadow_evaluation/08_historical_shadow_portfolio_results.json` | `initial_capital_usdt` across all 6 policies | 10,000.0 USDT | **MATCH** |
| **Experiment Registry** | `data/research_lab/btc_timing_experiments/EXP-POLICY_*.json` | `initial_capital_usdt` | 10,000.0 USDT | **MATCH** |
| **Audit Routine** | `src/coin_behavior_engine/product/btc_timing_research/transaction_cost_auditor.py:93` | `initial_capital` | 10,000.0 USDT | **MATCH** |
| **V10 Research Engine** | `src/coin_behavior_engine/product/btc_timing_research/investment_research_v10.py:238` | `initial_capital_usdt` | 10,000.0 USDT | **MATCH** |
| **User Interface Default** | `src/coin_behavior_engine/product/btc_timing_research/btc_timing_ui.py:378` | `<input id="timing-input-capital" value="10000">` | 10,000.0 USDT | **MATCH** |
| **REST API Endpoint** | `/api/v1/product/research/btc-timing/v10/comparison` | `policies[].initial_capital_usdt` | 10,000.0 USDT | **MATCH** |
| **Double-Entry Ledger** | `research_outputs/sprint32_1_final_acceptance_closure/02_corrected_portfolio_reconciliation.json` | `initial_cash_usdt` across all 6 policies | 10,000.0 USDT | **MATCH** |

---

## 3. Findings & Resolution

1. **Authentic Simulation Reality:**  
   The actual simulation executed during Sprint 31 and validated in Sprint 32 was configured with **10,000.00 USDT**. Initial trades, percentage allocations, cash balances, fee amounts, and ending equities ($9,030.69, $7,120.36, etc.) all mathematically derive from 10,000 USDT.
   
2. **Typographical Narrative Error:**  
   The reference to "$100,000" in the Sprint 32 narrative was a textual error originating from prompt descriptions that was inadvertently repeated in text summaries.
   
3. **No Retrospective Rerunning:**  
   As strictly required by governance invariants, the historical simulation was **not** re-run with 100,000 USDT merely to conform to an erroneous text label. The historical empirical evidence has been preserved, and all documentation and UI labels have been verified and reconciled to 10,000.00 USDT.
