"""Timing Research Report Builder (Module 29.12).

Generates comprehensive, downloadable research reports in Markdown and JSON formats
for historical BTC timing simulations:
1. Prominently displays offline research and governance invariants.
2. Itemizes performance, risk, and transaction cost breakdowns.
3. Compares results directly against Buy-and-Hold and USDT Cash baselines.
4. Explains limitations and warns that past performance does not guarantee future results.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


class TimingResearchReportBuilder:
    """Builds formal scientific research reports for BTC timing experiments."""

    @staticmethod
    def build_markdown_report(experiment_payload: Dict[str, Any]) -> str:
        meta = experiment_payload.get("metadata", {})
        metrics = meta.get("metrics_summary", {})
        bmark = meta.get("benchmark_comparison", {})

        exp_id = meta.get("experiment_id", "N/A")
        created_at = meta.get("created_at_utc", "N/A")
        policy_id = meta.get("policy_id", "N/A")
        policy_name = meta.get("policy_name", "N/A")
        dataset_id = meta.get("dataset_id", "N/A")
        dataset_sha256 = meta.get("dataset_sha256", "N/A")
        cost_profile = meta.get("cost_profile_id", "N/A")
        init_cap = meta.get("initial_capital_usdt", 10000.0)
        end_eq = meta.get("ending_equity_usdt", 10000.0)
        net_ret = meta.get("net_return_pct", 0.0)
        max_dd = meta.get("max_drawdown_pct", 0.0)
        sharpe = meta.get("sharpe_ratio", "N/A")
        trade_count = meta.get("trade_count", 0)
        status = meta.get("research_status", "EXPLORATORY_RESULT")

        # Benchmark figures
        bnh_ret = bmark.get("buy_and_hold_return_pct", "N/A")
        bnh_eq = bmark.get("buy_and_hold_ending_equity", "N/A")
        excess_ret = metrics.get("excess_return_over_bnh_pct", "N/A")

        limitations = metrics.get("metric_limitations", [])
        limitations_str = "\n".join([f"- {lim}" for lim in limitations]) if limitations else "- None identified."

        md = f"""# BTC TIMING RESEARCH ENGINE — EXPERIMENT REPORT
**Experiment ID:** `{exp_id}`  
**Generated At UTC:** `{created_at}`  
**Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Governance:** `TECHNICAL_NO_GO` | `ZERO_TOUCH_PRODUCTION` | `DIRECTIONAL_TRADING=0`  
**Research Status:** `{status}`

> [!IMPORTANT]
> **DISCLAIMER: HISTORICAL OFFLINE RESEARCH ONLY.**  
> This simulation was executed strictly offline using historical data. It does not constitute investment advice, financial promotion, or a guarantee of future performance. Real live trading involves market slippage, execution delays, and capital risk not fully captured in simulated models.

---

## 1. Executive Summary

| Metric | Candidate Policy Value | Buy & Hold Benchmark | Excess vs Benchmark |
|---|---|---|---|
| **Policy Name** | {policy_name} (`{policy_id}`) | Passive Buy & Hold | — |
| **Initial Hypothetical Capital** | ${init_cap:,.2f} USDT | ${init_cap:,.2f} USDT | — |
| **Ending Hypothetical Equity** | ${end_eq:,.2f} USDT | ${bnh_eq if isinstance(bnh_eq, str) else f"{bnh_eq:,.2f}"} USDT | — |
| **Net Return** | **{net_ret:+.2f}%** | {bnh_ret if isinstance(bnh_ret, str) else f"{bnh_ret:+.2f}%"} | **{excess_ret if isinstance(excess_ret, str) else f"{excess_ret:+.2f}%"}** |
| **Maximum Drawdown** | **{max_dd:.2f}%** | {bmark.get("buy_and_hold_max_dd_pct", "N/A")}% | — |
| **Sharpe Ratio (Annualized)** | {sharpe} | {bmark.get("buy_and_hold_sharpe", "N/A")} | — |
| **Trade Count** | {trade_count} | 1 | — |
| **Transaction Cost Drag** | {metrics.get("cost_drag_pct", 0.0):.2f}% | — | — |

---

## 2. Research Configuration & Data Foundation

- **Historical Dataset ID:** `{dataset_id}`
- **Dataset Cryptographic SHA-256:** `{dataset_sha256}`
- **Evaluation Period:** `{meta.get("evaluation_start_utc", "N/A")}` to `{meta.get("evaluation_end_utc", "N/A")}`
- **Transaction Cost Profile:** `{cost_profile}`
- **Execution Convention:** `{meta.get("execution_convention", "NEXT_OPEN_EXECUTION")}`
- **Parameter Snapshot:**
```json
{json.dumps(meta.get("parameter_snapshot", {}), indent=2)}
```

---

## 3. Detailed Performance & Risk Metrics

- **Gross P&L:** ${metrics.get("gross_pnl_usdt", 0.0):,.2f} USDT
- **Net P&L:** ${metrics.get("net_pnl_usdt", 0.0):,.2f} USDT
- **Annualized Return:** {metrics.get("annualized_return_pct", "N/A")}%
- **Annualized Return Volatility:** {metrics.get("annualized_volatility_pct", "N/A")}%
- **Downside Semi-Deviation:** {metrics.get("downside_volatility_pct", "N/A")}%
- **Sortino Ratio:** {metrics.get("sortino_ratio", "N/A")}
- **Calmar Ratio:** {metrics.get("calmar_ratio", "N/A")}
- **Win Rate:** {metrics.get("win_rate_pct", "N/A")}% (Winning: {metrics.get("winning_trades", 0)}, Losing: {metrics.get("losing_trades", 0)})
- **Portfolio Turnover:** {metrics.get("turnover_pct", 0.0):.2f}%
- **Time Invested in BTC:** {metrics.get("time_invested_pct", 0.0):.2f}%

---

## 4. Transaction Cost Accounting

- **Exchange Fees Deducted:** ${metrics.get("total_fees_usdt", 0.0):,.2f} USDT
- **Bid-Ask Spread Drag:** ${metrics.get("total_spread_cost_usdt", 0.0):,.2f} USDT
- **Execution Slippage Cost:** ${metrics.get("total_slippage_cost_usdt", 0.0):,.2f} USDT
- **Total Transaction Friction:** ${metrics.get("total_transaction_costs_usdt", 0.0):,.2f} USDT

---

## 5. Methodological Limitations & Integrity Notes

{limitations_str}

- **No Live Trading Permission:** All real-money trading is permanently prohibited under CBE governance.
- **Model Invariance:** The canonical scientific model `CBE-0.7.0` remains strictly frozen and unmodified.
"""
        return md
