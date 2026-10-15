"""Research result provenance and auditable trade ledger for historical experiments.

Enforces:
1. Strict provenance metadata on every experiment result (SHA-256, commit, date range, seed).
2. Auditable line-by-line trade ledger (JSONL and DataFrame).
3. Automated mathematical reconciliation between trade ledger lines and portfolio totals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import pandas as pd

from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentOpportunity,
    PortfolioEvaluationReport,
    SimulatedTradeResult,
    TradeCostModel,
)


@dataclass(frozen=True)
class ExperimentProvenanceRecord:
    """Complete provenance envelope for a historical experiment run."""

    symbol: str
    market_type: str
    dataset_id: str
    dataset_sha256: str
    date_range_utc: tuple[str, str]
    timeframe: str
    hypothesis_id: str
    signal_version: str
    evaluation_partition: str
    execution_mode: str
    cost_model: dict[str, float]
    total_candidates: int
    executed_trades: int
    independent_trades: int
    capital_allocation_pct: float
    random_seed: Optional[int]
    code_commit_sha: str
    experiment_config_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditableTradeRecord:
    """Line-by-line ledger entry for a simulated trade."""

    opportunity_id: str
    symbol: str
    direction: str
    entry_bar_index: int
    entry_timestamp_ms: int
    exit_bar_index: int
    exit_timestamp_ms: int
    intended_entry_price: float
    effective_entry_price: float
    exit_price: float
    exit_reason: str
    holding_bars: int
    is_filled: bool
    fill_ratio: float
    adverse_selection_bps: float
    cost_bps: float
    gross_return_pct: float
    net_return_pct: float
    net_return_bps: float
    is_win: bool
    is_independent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditableTradeLedger:
    """Manages line-by-line experiment ledgers and mathematical reconciliation."""

    def __init__(self, records: Sequence[AuditableTradeRecord]) -> None:
        self.records = list(records)

    @classmethod
    def from_simulated_trades(
        cls,
        opportunities: Sequence[InvestmentOpportunity],
        trade_results: Sequence[SimulatedTradeResult],
        independent_trade_ids: set[str],
        unfilled_opp_ids: set[str] | None = None,
    ) -> AuditableTradeLedger:
        """Construct an auditable ledger from simulated trade results."""
        unfilled = unfilled_opp_ids or set()
        res_by_id = {r.opportunity_id: r for r in trade_results}

        records: list[AuditableTradeRecord] = []
        for opp in opportunities:
            opp_id = opp.opportunity_id
            if opp_id in res_by_id:
                tr = res_by_id[opp_id]
                rec = AuditableTradeRecord(
                    opportunity_id=opp_id,
                    symbol=opp.symbol,
                    direction=opp.direction.value,
                    entry_bar_index=tr.entry_bar_index,
                    entry_timestamp_ms=tr.entry_timestamp_ms,
                    exit_bar_index=tr.exit_bar_index,
                    exit_timestamp_ms=tr.exit_timestamp_ms,
                    intended_entry_price=opp.entry_price,
                    effective_entry_price=tr.entry_price,
                    exit_price=tr.exit_price,
                    exit_reason=tr.exit_reason,
                    holding_bars=tr.holding_bars,
                    is_filled=True,
                    fill_ratio=1.0,
                    adverse_selection_bps=round(abs(tr.entry_price - opp.entry_price) / opp.entry_price * 10_000.0, 2),
                    cost_bps=round(tr.total_cost_pct * 10_000.0, 2),
                    gross_return_pct=float(tr.gross_return_pct),
                    net_return_pct=float(tr.net_return_pct),
                    net_return_bps=round(tr.net_return_pct * 10_000.0, 4),
                    is_win=tr.is_win,
                    is_independent=(opp_id in independent_trade_ids),
                )
                records.append(rec)
            elif opp_id in unfilled:
                rec = AuditableTradeRecord(
                    opportunity_id=opp_id,
                    symbol=opp.symbol,
                    direction=opp.direction.value,
                    entry_bar_index=opp.entry_bar_index,
                    entry_timestamp_ms=opp.entry_timestamp_ms,
                    exit_bar_index=opp.entry_bar_index,
                    exit_timestamp_ms=opp.entry_timestamp_ms,
                    intended_entry_price=opp.entry_price,
                    effective_entry_price=0.0,
                    exit_price=0.0,
                    exit_reason="EXPIRED_UNFILLED",
                    holding_bars=0,
                    is_filled=False,
                    fill_ratio=0.0,
                    adverse_selection_bps=0.0,
                    cost_bps=0.0,
                    gross_return_pct=0.0,
                    net_return_pct=0.0,
                    net_return_bps=0.0,
                    is_win=False,
                    is_independent=False,
                )
                records.append(rec)

        return cls(records)

    def reconcile_with_report(self, report: PortfolioEvaluationReport) -> dict[str, Any]:
        """Perform zero-tolerance reconciliation between line-by-line records and portfolio report."""
        filled_records = [r for r in self.records if r.is_filled]
        unfilled_records = [r for r in self.records if not r.is_filled]

        n_filled = len(filled_records)
        assert n_filled == report.executed_trades, (
            f"Ledger filled count {n_filled} != report executed trades {report.executed_trades}"
        )

        indep_records = [r for r in filled_records if r.is_independent]
        assert len(indep_records) == report.independent_opportunities_count, (
            f"Ledger independent count {len(indep_records)} != report independent count {report.independent_opportunities_count}"
        )

        # Reconcile sum of net returns
        ledger_sum_pct = sum(r.net_return_pct for r in filled_records)
        diff_sum = abs(ledger_sum_pct - report.total_net_return_pct)
        assert diff_sum < 1e-4, f"Ledger sum return {ledger_sum_pct} != report total net return {report.total_net_return_pct}"

        # Reconcile win count
        ledger_wins = sum(1 for r in filled_records if r.is_win)
        assert ledger_wins == report.win_count, f"Ledger wins {ledger_wins} != report wins {report.win_count}"

        # Reconcile mean expectancy
        ledger_mean_exp = (ledger_sum_pct / n_filled) if n_filled > 0 else 0.0
        diff_exp = abs(ledger_mean_exp - report.net_expectancy_pct)
        assert diff_exp < 1e-5, f"Ledger mean expectancy {ledger_mean_exp} != report expectancy {report.net_expectancy_pct}"

        return {
            "status": "RECONCILED",
            "total_records": len(self.records),
            "filled_records": n_filled,
            "unfilled_records": len(unfilled_records),
            "independent_records": len(indep_records),
            "ledger_sum_return_pct": round(ledger_sum_pct * 100.0, 4),
            "report_sum_return_pct": round(report.total_net_return_pct * 100.0, 4),
            "discrepancy": round(diff_sum, 8),
            "is_perfect_reconciliation": bool(diff_sum < 1e-4),
        }

    def save_jsonl(self, filepath: Path) -> None:
        """Export auditable trade ledger to JSONL."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            for rec in self.records:
                f.write(json.dumps(rec.to_dict()) + "\n")
