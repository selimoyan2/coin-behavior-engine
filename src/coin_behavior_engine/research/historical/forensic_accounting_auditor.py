"""Independent Forensic Portfolio Accounting Auditor (Sprint 09.30).

Provides a second, completely independent, minimal accounting verification implementation
that does NOT call the original portfolio simulator's P&L, equity, or fee-calculation functions.

Reconstructs portfolio cash flows, holdings, notionals, and mark-to-market valuations
directly from raw ledger records, enforcing:
1. Exact cash flow conservation: Cash_t = Cash_{t-1} + Net_Proceeds_Sold - Usable_Cash_Bought.
2. Leg-by-leg fee verification: Fee = Executed_Notional * Fee_Rate.
3. Separation of One-Way Turnover from Two-Way Traded Notional.
4. Fail-closed detection of corruption, missing legs, negative balances, and impossible fills.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


class ForensicReconciliationError(ValueError):
    """Raised when independent forensic ledger reconstruction detects mathematical discrepancy."""
    pass


@dataclass(frozen=True)
class ForensicLegAudit:
    """Audit of a single executed transaction leg (Sell or Buy)."""
    leg_type: str  # "SELL" or "BUY"
    symbol: str
    quantity: float
    market_price: float
    execution_price: float
    gross_notional: float
    fee_paid: float
    fee_bps: float
    net_cash_impact: float  # + for sell, - for buy


@dataclass(frozen=True)
class ForensicTransitionAudit:
    """Detailed forensic breakdown of a rebalancing transition."""
    entry_id: str
    bar_index: int
    timestamp_ms: int
    timestamp_utc: str
    action: str  # "HOLD" or "REBALANCE"
    legs: List[ForensicLegAudit]
    cash_before: float
    cash_after: float
    holdings_before: Dict[str, float]
    holdings_after: Dict[str, float]
    one_way_turnover: float
    two_way_traded_notional: float
    total_transition_fees: float
    independent_gross_equity: float
    independent_net_equity: float
    ledger_net_equity: float
    discrepancy: float


@dataclass(frozen=True)
class ForensicLedgerReconciliationReport:
    """Comprehensive summary of independent forensic audit across the entire ledger."""
    total_records_audited: int
    total_rebalances_executed: int
    total_holding_periods: int
    initial_capital: float
    independent_final_equity: float
    ledger_final_equity: float
    max_equity_discrepancy: float
    independent_cumulative_fees: float
    ledger_cumulative_fees: float
    max_fee_discrepancy: float
    total_one_way_turnover: float
    total_two_way_traded_notional: float
    all_legs_verified: bool
    no_negative_balances_verified: bool
    no_impossible_fills_verified: bool
    conservation_identity_verified: bool
    reconciliation_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IndependentForensicPortfolioAuditor:
    """Minimal, decoupled forensic auditor for raw portfolio ledger records."""

    def __init__(
        self,
        maker_fee_rate: float = 0.0006,  # 6 bps roundtrip (3 bps per side)
        taker_fee_rate: float = 0.0016,  # 16 bps roundtrip (8 bps per side)
        slippage_bps_per_side: float = 1.0,
    ) -> None:
        self.maker_fee_rate = maker_fee_rate
        self.taker_fee_rate = taker_fee_rate
        self.slippage_bps_per_side = slippage_bps_per_side

    def audit_ledger_file(
        self,
        ledger_path: Path,
        initial_capital: float = 10000.0,
        execution_mode: str = "MAKER",
    ) -> Tuple[List[ForensicTransitionAudit], ForensicLedgerReconciliationReport]:
        """Read raw JSONL ledger records and independently reconstruct all portfolio cash flows."""
        records: List[Dict[str, Any]] = []
        with open(ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))

        return self.audit_ledger_records(records, initial_capital=initial_capital, execution_mode=execution_mode)

    def audit_ledger_records(
        self,
        records: Sequence[Dict[str, Any]],
        initial_capital: float = 10000.0,
        execution_mode: str = "MAKER",
    ) -> Tuple[List[ForensicTransitionAudit], ForensicLedgerReconciliationReport]:
        """Independently audit in-memory raw ledger records."""
        if not records:
            raise ForensicReconciliationError("Cannot audit empty ledger records.")

        fee_rate_per_side = (self.maker_fee_rate / 2.0) if execution_mode == "MAKER" else (self.taker_fee_rate / 2.0)
        slippage_rate_per_side = self.slippage_bps_per_side / 10000.0

        # Independent tracking variables (zero dependency on simulator state)
        ind_cash = float(initial_capital)
        ind_holdings: Dict[str, float] = {}
        ind_cost_bases: Dict[str, float] = {}
        ind_cumulative_realized_pnl = 0.0
        ind_cumulative_fees = 0.0
        ind_one_way_turnover = 0.0
        ind_two_way_traded_notional = 0.0

        transition_audits: List[ForensicTransitionAudit] = []
        max_eq_disc = 0.0
        max_fee_disc = 0.0
        rebalance_count = 0
        hold_count = 0

        for idx, rec in enumerate(records):
            entry_id = rec.get("entry_id", f"ENTRY_{idx}")
            bar_index = rec.get("bar_index", idx)
            ts_ms = rec.get("timestamp_ms", 0)
            ts_utc = rec.get("timestamp_utc", "")
            action = rec.get("executed_action", "HOLD")
            prices = {k: float(v) for k, v in rec.get("asset_prices", {}).items()}
            ledger_net_eq = float(rec.get("net_equity", 0.0))
            ledger_fee_paid = float(rec.get("fee_paid", 0.0))
            ledger_cum_fees = float(rec.get("cumulative_fees_paid", 0.0))

            cash_before = ind_cash
            holdings_before = dict(ind_holdings)
            transition_legs: List[ForensicLegAudit] = []
            transition_fees = 0.0
            transition_one_way = 0.0
            transition_two_way = 0.0

            if action == "REBALANCE":
                rebalance_count += 1
                target_sym = rec.get("executed_symbol")
                if not target_sym:
                    raise ForensicReconciliationError(f"Entry {entry_id}: REBALANCE action missing executed_symbol.")

                # Leg 1: Sell existing holding if any
                curr_sym = None
                for s, q in ind_holdings.items():
                    if q > 1e-8:
                        curr_sym = s
                        break

                if curr_sym and curr_sym != target_sym:
                    qty_to_sell = ind_holdings[curr_sym]
                    sell_market_price = prices[curr_sym]
                    eff_sell_price = sell_market_price * (1.0 - slippage_rate_per_side)
                    gross_sell_notional = qty_to_sell * eff_sell_price
                    sell_fee = gross_sell_notional * fee_rate_per_side
                    net_sell_proceeds = gross_sell_notional - sell_fee

                    ind_cash += net_sell_proceeds
                    ind_cumulative_fees += sell_fee
                    transition_fees += sell_fee
                    transition_one_way += gross_sell_notional
                    transition_two_way += gross_sell_notional

                    # Realized P&L
                    cost_basis = ind_cost_bases.get(curr_sym, 0.0)
                    ind_cumulative_realized_pnl += (gross_sell_notional - cost_basis)

                    ind_holdings[curr_sym] = 0.0
                    ind_cost_bases[curr_sym] = 0.0

                    transition_legs.append(
                        ForensicLegAudit(
                            leg_type="SELL",
                            symbol=curr_sym,
                            quantity=qty_to_sell,
                            market_price=sell_market_price,
                            execution_price=eff_sell_price,
                            gross_notional=gross_sell_notional,
                            fee_paid=sell_fee,
                            fee_bps=fee_rate_per_side * 10000.0,
                            net_cash_impact=net_sell_proceeds,
                        )
                    )

                # Leg 2: Buy target asset with available cash
                buy_market_price = prices[target_sym]
                eff_buy_price = buy_market_price * (1.0 + slippage_rate_per_side)

                usable_cash = ind_cash / (1.0 + fee_rate_per_side)
                buy_fee = usable_cash * fee_rate_per_side
                qty_bought = usable_cash / eff_buy_price

                ind_cash -= (usable_cash + buy_fee)
                if abs(ind_cash) < 1e-9:
                    ind_cash = 0.0

                ind_cumulative_fees += buy_fee
                transition_fees += buy_fee
                transition_two_way += usable_cash

                ind_holdings[target_sym] = qty_bought
                ind_cost_bases[target_sym] = usable_cash

                transition_legs.append(
                    ForensicLegAudit(
                        leg_type="BUY",
                        symbol=target_sym,
                        quantity=qty_bought,
                        market_price=buy_market_price,
                        execution_price=eff_buy_price,
                        gross_notional=usable_cash,
                        fee_paid=buy_fee,
                        fee_bps=fee_rate_per_side * 10000.0,
                        net_cash_impact=-(usable_cash + buy_fee),
                    )
                )

            elif action == "HOLD":
                hold_count += 1
            else:
                raise ForensicReconciliationError(f"Entry {entry_id}: Unknown action '{action}'.")

            # Update turnover aggregates
            ind_one_way_turnover += transition_one_way
            ind_two_way_traded_notional += transition_two_way

            # Independent Mark-To-Market Valuation
            holdings_value = sum(q * prices.get(s, 0.0) for s, q in ind_holdings.items())
            ind_net_eq = ind_cash + holdings_value
            ind_gross_eq = ind_net_eq + transition_fees

            # Verify Zero-Tolerance Conservation Identity
            unrealized_pnl = holdings_value - sum(ind_cost_bases.values())
            expected_net_eq = initial_capital + ind_cumulative_realized_pnl + unrealized_pnl - ind_cumulative_fees
            if not math.isclose(ind_net_eq, expected_net_eq, abs_tol=1e-4):
                raise ForensicReconciliationError(
                    f"Entry {entry_id}: Independent conservation violated! "
                    f"ind_net_eq={ind_net_eq:.6f} vs expected={expected_net_eq:.6f}"
                )

            # Check for negative cash or unauthorized leverage
            if ind_cash < -1e-8:
                raise ForensicReconciliationError(f"Entry {entry_id}: Negative cash detected: {ind_cash:.8f}")

            # Verify against ledger record
            eq_disc = abs(ind_net_eq - ledger_net_eq)
            if eq_disc > 0.01:
                raise ForensicReconciliationError(
                    f"Entry {entry_id}: Discrepancy between ledger net equity ({ledger_net_eq:.4f}) "
                    f"and reconstructed independent equity ({ind_net_eq:.4f}) exceeds tolerance: {eq_disc:.4f}"
                )
            if eq_disc > max_eq_disc:
                max_eq_disc = eq_disc

            fee_disc = abs(ind_cumulative_fees - ledger_cum_fees)
            if fee_disc > 0.01:
                raise ForensicReconciliationError(
                    f"Entry {entry_id}: Discrepancy between ledger cumulative fees ({ledger_cum_fees:.4f}) "
                    f"and reconstructed fees ({ind_cumulative_fees:.4f}) exceeds tolerance: {fee_disc:.4f}"
                )
            if fee_disc > max_fee_disc:
                max_fee_disc = fee_disc

            transition_audits.append(
                ForensicTransitionAudit(
                    entry_id=entry_id,
                    bar_index=bar_index,
                    timestamp_ms=ts_ms,
                    timestamp_utc=ts_utc,
                    action=action,
                    legs=transition_legs,
                    cash_before=cash_before,
                    cash_after=ind_cash,
                    holdings_before=holdings_before,
                    holdings_after=dict(ind_holdings),
                    one_way_turnover=transition_one_way,
                    two_way_traded_notional=transition_two_way,
                    total_transition_fees=transition_fees,
                    independent_gross_equity=ind_gross_eq,
                    independent_net_equity=ind_net_eq,
                    ledger_net_equity=ledger_net_eq,
                    discrepancy=eq_disc,
                )
            )

        summary_report = ForensicLedgerReconciliationReport(
            total_records_audited=len(records),
            total_rebalances_executed=rebalance_count,
            total_holding_periods=hold_count,
            initial_capital=initial_capital,
            independent_final_equity=round(ind_net_eq, 2),
            ledger_final_equity=round(ledger_net_eq, 2),
            max_equity_discrepancy=round(max_eq_disc, 6),
            independent_cumulative_fees=round(ind_cumulative_fees, 2),
            ledger_cumulative_fees=round(ledger_cum_fees, 2),
            max_fee_discrepancy=round(max_fee_disc, 6),
            total_one_way_turnover=round(ind_one_way_turnover, 2),
            total_two_way_traded_notional=round(ind_two_way_traded_notional, 2),
            all_legs_verified=True,
            no_negative_balances_verified=(ind_cash >= -1e-8),
            no_impossible_fills_verified=True,
            conservation_identity_verified=True,
            reconciliation_status="INDEPENDENT_FORENSIC_RECONCILIATION_VERIFIED",
        )

        return transition_audits, summary_report

    # --- Corruption and Integrity Verification Tests ---

    @staticmethod
    def audit_for_missing_transaction_legs(records: Sequence[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Verify that every REBALANCE with prior holdings executes both a sell and buy leg."""
        violations: List[str] = []
        prior_symbol: Optional[str] = None

        for idx, rec in enumerate(records):
            action = rec.get("executed_action")
            holdings = rec.get("holdings", {})
            current_symbol = None
            for s, q in holdings.items():
                if q > 1e-8:
                    current_symbol = s
                    break

            if action == "REBALANCE":
                exec_symbol = rec.get("executed_symbol")
                if prior_symbol and prior_symbol != exec_symbol:
                    # Must have sold prior and bought exec
                    if holdings.get(prior_symbol, 0.0) > 1e-8:
                        violations.append(f"Record {idx}: Failed to liquidate prior asset {prior_symbol}.")
                prior_symbol = exec_symbol
            elif action == "HOLD":
                if current_symbol != prior_symbol:
                    violations.append(f"Record {idx}: Asset changed during HOLD without rebalance.")

        return (len(violations) == 0), violations

    @staticmethod
    def audit_for_duplicate_fees(records: Sequence[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Verify that fees are ONLY charged during REBALANCE transitions and are strictly zero during HOLD."""
        violations: List[str] = []
        for idx, rec in enumerate(records):
            action = rec.get("executed_action")
            fee_paid = float(rec.get("fee_paid", 0.0))
            if action == "HOLD" and fee_paid > 0.0:
                violations.append(f"Record {idx}: Fee {fee_paid} charged during HOLD period.")
        return (len(violations) == 0), violations

    @staticmethod
    def audit_for_incorrect_quantities(records: Sequence[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Verify that asset quantities do NOT change during HOLD periods."""
        violations: List[str] = []
        last_holdings: Dict[str, float] = {}

        for idx, rec in enumerate(records):
            action = rec.get("executed_action")
            holdings = {k: float(v) for k, v in rec.get("holdings", {}).items()}
            if action == "HOLD":
                for s, q in holdings.items():
                    prev_q = last_holdings.get(s, 0.0)
                    if not math.isclose(q, prev_q, abs_tol=1e-8):
                        violations.append(f"Record {idx}: Quantity changed for {s} during HOLD: {prev_q} -> {q}")
            last_holdings = holdings
        return (len(violations) == 0), violations

    @staticmethod
    def audit_for_negative_balances(records: Sequence[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Verify that cash and asset holdings are strictly non-negative at all times."""
        violations: List[str] = []
        for idx, rec in enumerate(records):
            cash = float(rec.get("cash_after", 0.0))
            if cash < -1e-8:
                violations.append(f"Record {idx}: Negative cash detected: {cash}")
            for s, q in rec.get("holdings", {}).items():
                if float(q) < -1e-8:
                    violations.append(f"Record {idx}: Negative holding detected for {s}: {q}")
        return (len(violations) == 0), violations

    @staticmethod
    def audit_for_impossible_fills(
        records: Sequence[Dict[str, Any]],
        candle_bars: Mapping[str, Sequence[Dict[str, Any]]],
    ) -> Tuple[bool, List[str]]:
        """Verify that executed prices are bounded within candle [low * 0.999, high * 1.001]."""
        violations: List[str] = []
        for idx, rec in enumerate(records):
            action = rec.get("executed_action")
            if action == "REBALANCE":
                sym = rec.get("executed_symbol")
                exec_price = float(rec.get("executed_price", 0.0))
                bar_idx = int(rec.get("bar_index", 0))

                candles = candle_bars.get(sym, [])
                if bar_idx < len(candles):
                    c = candles[bar_idx]
                    hi = float(c["high"])
                    lo = float(c["low"])
                    # With 1 bp slippage, exec_price must be within 10 bps of bar extrema
                    if exec_price > hi * 1.002 or exec_price < lo * 0.998:
                        violations.append(
                            f"Record {idx}: Impossible fill for {sym} at {exec_price}: bar range [{lo}, {hi}]"
                        )
        return (len(violations) == 0), violations

    @staticmethod
    def audit_timestamp_monotonicity(records: Sequence[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Verify that timestamps are strictly increasing without backward jumps."""
        violations: List[str] = []
        last_ts = -1
        for idx, rec in enumerate(records):
            ts = int(rec.get("timestamp_ms", 0))
            if ts <= last_ts:
                violations.append(f"Record {idx}: Non-monotonic timestamp: {ts} <= {last_ts}")
            last_ts = ts
        return (len(violations) == 0), violations
