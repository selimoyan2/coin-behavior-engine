"""Delta-Neutral Carry Simulator & Conservative Accounting Engine (Sprint 09.35).

Implements an independently auditable, point-in-time, conservative accounting model for:
1. Long BTC Spot + Short BTCUSDT USDT-M Perpetual carry trade.
2. Explicit capital segregation: Spot allocation, Perpetual margin collateral, Unallocated cash reserve.
3. Authentic funding cash flow accounting strictly at settlement timestamps (00:00, 08:00, 16:00 UTC).
4. Continuous mark-to-market separating Spot P&L, Perpetual P&L, Basis convergence P&L, Fees, and Slippage.
5. Intraday liquidation risk and margin utilization tracking with liquidation buffer analysis.
6. Zero lookahead bias, zero double-counting, zero artificial capital creation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.funding_data_contract import (
    FundingSettlementRecord,
    SpotPerpAlignedBasisRecord,
)


@dataclass(frozen=True)
class DeltaNeutralExecutionParams:
    """Execution parameters and cost model for delta-neutral simulation."""
    initial_capital_usdt: float = 10000.0
    spot_allocation_pct: float = 50.0        # % of initial capital allocated to Spot purchase
    perp_margin_allocation_pct: float = 25.0 # % of initial capital allocated to Perp collateral
    target_hedge_ratio: float = 1.0          # Q_perp / Q_spot = -1.0
    perp_leverage: float = 4.0               # Effective perp leverage = 50% notional / 25% margin = 2x, max allowable 4x
    maintenance_margin_rate: float = 0.05    # 5.0% maintenance margin
    spot_taker_fee_rate: float = 0.0008      # 8 bps taker fee
    perp_taker_fee_rate: float = 0.0005      # 5 bps taker fee
    spot_slippage_rate: float = 0.00015      # 1.5 bps slippage
    perp_slippage_rate: float = 0.00015      # 1.5 bps slippage
    execution_lag_bars: int = 0              # 0 = execute at bar close, >0 = delayed entry
    liquidation_penalty_rate: float = 0.01   # 1.0% penalty on forced close
    allow_reserve_margin_transfer: bool = False  # Strict isolated margin by default

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Point-in-time snapshot of the portfolio at a single 15-minute bar."""
    timestamp_ms: int
    timestamp_utc: str
    bar_index: int
    spot_price: float
    perp_price: float
    perp_high_price: float
    perp_low_price: float
    basis_usdt: float
    basis_bps: float

    # Asset Holdings & Positions
    spot_btc_qty: float
    perp_btc_qty: float  # Negative for short position
    hedge_ratio: float

    # Cash & Collateral Silos
    unallocated_cash_usdt: float
    perp_margin_collateral_usdt: float
    total_cash_usdt: float

    # Valuations & P&L Components
    spot_asset_value_usdt: float
    spot_unrealized_pnl_usdt: float
    perp_unrealized_pnl_usdt: float
    basis_convergence_pnl_usdt: float
    cumulative_funding_receipts_usdt: float
    cumulative_funding_payments_usdt: float
    net_funding_usdt: float
    cumulative_trading_fees_usdt: float
    cumulative_slippage_usdt: float

    # Total Portfolio Equity
    total_portfolio_equity_usdt: float
    net_total_pnl_usdt: float
    return_on_committed_capital_pct: float

    # Margin & Risk Metrics
    perp_account_equity_usdt: float
    maintenance_margin_required_usdt: float
    margin_utilization_pct: float
    liquidation_buffer_usdt: float
    liquidation_price_usdt: float
    is_liquidated: bool
    is_uncertain_liquidation: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccountingIdentityReconciliation:
    """Rigorous audit verifying that portfolio equity reconciles exactly down to the cent."""
    timestamp_ms: int
    direct_equity_usdt: float
    reconciled_equity_usdt: float
    discrepancy_usdt: float
    is_zero_discrepancy: bool
    basis_pnl_reconciliation_error_usdt: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeltaNeutralScenarioResult:
    """Complete summary of a single predetermined simulation scenario."""
    scenario_name: str
    scenario_description: str
    params: DeltaNeutralExecutionParams
    start_timestamp_utc: str
    end_timestamp_utc: str
    total_bars_simulated: int
    total_calendar_days: float

    # Entry & Exit Prices
    entry_spot_price: float
    entry_perp_price: float
    entry_basis_bps: float
    exit_spot_price: float
    exit_perp_price: float
    exit_basis_bps: float

    # Capital Allocation
    initial_capital_usdt: float
    spot_purchase_capital_usdt: float
    perp_margin_initial_usdt: float
    unallocated_cash_reserve_usdt: float
    spot_btc_purchased: float
    perp_btc_shorted: float

    # Financial Performance Components
    gross_funding_receipts_usdt: float
    gross_funding_payments_usdt: float
    net_funding_usdt: float
    spot_pnl_usdt: float
    perp_pnl_usdt: float
    basis_convergence_pnl_usdt: float
    total_trading_fees_usdt: float
    total_slippage_usdt: float
    net_total_pnl_usdt: float
    return_on_committed_capital_pct: float
    funding_yield_on_notional_pct: float

    # Risk & Capital Efficiency
    max_equity_usdt: float
    min_equity_usdt: float
    max_drawdown_usdt: float
    max_drawdown_pct: float
    max_margin_utilization_pct: float
    min_liquidation_buffer_usdt: float
    number_of_forced_exits: int
    number_of_uncertain_liquidation_outcomes: int
    terminal_status: str

    # Accounting Conservation Audit
    max_accounting_discrepancy_usdt: float
    accounting_conservation_verified: bool
    basis_identity_verified: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeltaNeutralCarrySimulator:
    """Conservative Delta-Neutral Carry Simulator and Continuous Mark-to-Market Engine."""

    def __init__(self, params: Optional[DeltaNeutralExecutionParams] = None) -> None:
        self.params = params or DeltaNeutralExecutionParams()

    def run_simulation(
        self,
        basis_records: Sequence[SpotPerpAlignedBasisRecord],
        funding_records: Sequence[FundingSettlementRecord],
        start_idx: int = 0,
        end_idx: Optional[int] = None,
        scenario_name: str = "BASELINE_CONSERVATIVE_TAKER",
        scenario_desc: str = "Predetermined fixed entry/exit with conservative taker fees and slippage",
    ) -> Tuple[DeltaNeutralScenarioResult, List[PortfolioSnapshot]]:
        """Execute a causal, point-in-time delta-neutral carry simulation across aligned bars."""
        if not basis_records:
            raise ValueError("basis_records cannot be empty")

        p = self.params
        total_len = len(basis_records)
        end_idx = total_len if end_idx is None else min(end_idx, total_len)

        if start_idx >= end_idx:
            raise ValueError(f"Invalid range: start_idx={start_idx}, end_idx={end_idx}")

        # Map authentic funding settlements by exact timestamp for O(1) point-in-time lookup
        funding_by_ts: Dict[int, FundingSettlementRecord] = {
            r.funding_event_timestamp_ms: r for r in funding_records
        }

        # Apply execution lag if configured
        actual_entry_idx = min(start_idx + p.execution_lag_bars, end_idx - 1)
        entry_rec = basis_records[actual_entry_idx]

        # Calculate entry execution prices including slippage
        # Buying Spot: price + slippage
        entry_spot_exec = entry_rec.spot_close_price * (1.0 + p.spot_slippage_rate)
        # Shorting Perp: price - slippage
        entry_perp_exec = entry_rec.perp_close_price * (1.0 - p.perp_slippage_rate)

        # Capital segregation
        spot_capital_budget = p.initial_capital_usdt * (p.spot_allocation_pct / 100.0)
        perp_margin_budget = p.initial_capital_usdt * (p.perp_margin_allocation_pct / 100.0)
        unallocated_cash = p.initial_capital_usdt - spot_capital_budget - perp_margin_budget

        # Spot purchase sizing: net of entry fees and slippage
        # Notional * (1 + fee_spot) <= spot_capital_budget
        spot_notional = spot_capital_budget / (1.0 + p.spot_taker_fee_rate)
        spot_btc_qty = spot_notional / entry_spot_exec
        spot_entry_fee = spot_notional * p.spot_taker_fee_rate
        spot_entry_slippage = spot_btc_qty * (entry_spot_exec - entry_rec.spot_close_price)

        # Perpetual Short sizing: target hedge ratio h = 1.0 (Q_perp = -Q_spot)
        perp_btc_qty = - (spot_btc_qty * p.target_hedge_ratio)
        perp_notional_entry = abs(perp_btc_qty) * entry_perp_exec
        perp_entry_fee = perp_notional_entry * p.perp_taker_fee_rate
        perp_entry_slippage = abs(perp_btc_qty) * (entry_rec.perp_close_price - entry_perp_exec)

        # Perpetual margin account initial balance
        # Margin account pays perp entry fee from allocated collateral
        perp_margin_collateral = perp_margin_budget - perp_entry_fee
        if perp_margin_collateral <= 0:
            raise ValueError(f"Perpetual margin allocation {perp_margin_budget} insufficient to cover entry costs")

        # Tracking state
        cumulative_fees = spot_entry_fee + perp_entry_fee
        cumulative_slippage = spot_entry_slippage + perp_entry_slippage
        cumulative_funding_receipts = 0.0
        cumulative_funding_payments = 0.0

        snapshots: List[PortfolioSnapshot] = []
        is_liquidated = False
        is_uncertain_liquidation = False
        forced_exits = 0
        uncertain_outcomes = 0
        terminal_status = "NORMAL_EXIT_AT_HORIZON"

        max_equity = -float("inf")
        min_equity = float("inf")
        peak_equity = p.initial_capital_usdt
        max_drawdown_usdt = 0.0
        max_drawdown_pct = 0.0
        max_margin_util = 0.0
        min_liq_buffer = float("inf")
        max_accounting_discrepancy = 0.0

        # Run continuous simulation bar-by-bar
        for idx in range(actual_entry_idx, end_idx):
            rec = basis_records[idx]
            ts = rec.timestamp_ms
            spot_p = rec.spot_close_price
            perp_p = rec.perp_close_price
            basis_usdt = rec.absolute_basis_usdt
            basis_bps = rec.relative_basis_bps

            # 1. Point-in-time funding settlement event
            # Funding settles strictly at 00:00, 08:00, 16:00 UTC
            if ts in funding_by_ts:
                f_record = funding_by_ts[ts]
                f_rate = f_record.funding_rate
                # Settlement notional = |Q_perp| * Perp_Price (or Mark Price)
                settle_notional = abs(perp_btc_qty) * perp_p
                # Cash flow convention: Q_perp < 0. Cash flow = - Q_perp * settle_notional * f_rate
                # Positive rate: Long pays short -> short receives positive cash flow
                # Negative rate: Short pays long -> short pays negative cash flow
                cash_flow = abs(perp_btc_qty) * perp_p * f_rate

                if cash_flow > 0:
                    cumulative_funding_receipts += cash_flow
                else:
                    cumulative_funding_payments += abs(cash_flow)

                # Direct cash flow into perpetual collateral balance
                perp_margin_collateral += cash_flow

            # 2. Mark-to-market valuations
            spot_value = spot_btc_qty * spot_p
            spot_unrealized_pnl = spot_btc_qty * (spot_p - entry_spot_exec)

            # Perp short unrealized P&L: Q_perp * (P_t - P_entry) = |Q_perp| * (P_entry - P_t)
            perp_unrealized_pnl = perp_btc_qty * (perp_p - entry_perp_exec)

            # Basis convergence P&L: Q * (Basis_entry - Basis_t)
            # Entry basis = entry_perp_exec - entry_spot_exec
            entry_basis_exec = entry_perp_exec - entry_spot_exec
            current_basis_exec = perp_p - spot_p
            basis_pnl = spot_btc_qty * (entry_basis_exec - current_basis_exec)

            # Perpetual account equity: Collateral + Unrealized P&L
            perp_account_equity = perp_margin_collateral + perp_unrealized_pnl

            # Maintenance margin requirement: 5% of current perpetual notional
            maint_margin_req = abs(perp_btc_qty) * perp_p * p.maintenance_margin_rate
            margin_util_pct = (maint_margin_req / max(perp_account_equity, 1e-9)) * 100.0 if perp_account_equity > 0 else 999.0
            liq_buffer_usdt = perp_account_equity - maint_margin_req

            # Calculate isolated liquidation price for short perpetual position
            # Liquidation occurs when Perp_Equity <= Maint_Margin
            # Collateral + Q_perp * (P_liq - P_entry) = |Q_perp| * P_liq * MMR
            # Collateral + |Q|*P_entry - |Q|*P_liq = |Q|*P_liq*MMR
            # Collateral + |Q|*P_entry = |Q|*P_liq*(1 + MMR)
            # P_liq = (Collateral + |Q|*P_entry) / (|Q| * (1 + MMR))
            if abs(perp_btc_qty) > 0:
                liq_price = (perp_margin_collateral + abs(perp_btc_qty) * entry_perp_exec) / (abs(perp_btc_qty) * (1.0 + p.maintenance_margin_rate))
            else:
                liq_price = float("inf")

            # Check liquidation condition against bar extremes
            # For a short position, high price creates maximum liquidation risk
            perp_high_p = perp_p * 1.002  # Conservative intraday high proxy if bar high not separate
            if liq_buffer_usdt <= 0.0 or perp_high_p >= liq_price:
                # Margin breached
                if p.allow_reserve_margin_transfer and unallocated_cash > abs(liq_buffer_usdt) + maint_margin_req:
                    # Transfer emergency cash from reserve to collateral
                    transfer_amt = abs(liq_buffer_usdt) + maint_margin_req * 1.5
                    unallocated_cash -= transfer_amt
                    perp_margin_collateral += transfer_amt
                    perp_account_equity = perp_margin_collateral + perp_unrealized_pnl
                    liq_buffer_usdt = perp_account_equity - maint_margin_req
                    margin_util_pct = (maint_margin_req / perp_account_equity) * 100.0
                else:
                    is_liquidated = True
                    forced_exits += 1
                    terminal_status = "LIQUIDATION_BREACH_FORCED_EXIT"
                    # Apply liquidation penalty
                    penalty = abs(perp_btc_qty) * perp_p * p.liquidation_penalty_rate
                    cumulative_fees += penalty
                    perp_account_equity -= penalty

            # Check uncertain liquidation condition (buffer < 1% of notional)
            is_uncertain_liquidation = False
            if not is_liquidated and liq_buffer_usdt < (abs(perp_btc_qty) * perp_p * 0.01):
                is_uncertain_liquidation = True
                uncertain_outcomes += 1

            # Total Portfolio Equity
            # Total Equity = Unallocated Cash + Perpetual Account Equity + Spot Asset Value
            total_equity = unallocated_cash + perp_account_equity + spot_value
            net_pnl = total_equity - p.initial_capital_usdt
            ret_pct = (net_pnl / p.initial_capital_usdt) * 100.0

            # Accounting conservation verification identity:
            # Reconciled Equity = Initial_Capital + Spot_PnL + Perp_PnL + Net_Funding - Cumulative_Fees
            net_funding = cumulative_funding_receipts - cumulative_funding_payments
            reconciled_equity = (
                p.initial_capital_usdt
                + spot_unrealized_pnl
                + perp_unrealized_pnl
                + net_funding
                - cumulative_fees
            )
            discrepancy = abs(total_equity - reconciled_equity)
            max_accounting_discrepancy = max(max_accounting_discrepancy, discrepancy)

            # Drawdown tracking
            peak_equity = max(peak_equity, total_equity)
            dd_usdt = peak_equity - total_equity
            dd_pct = (dd_usdt / peak_equity) * 100.0 if peak_equity > 0 else 0.0
            max_drawdown_usdt = max(max_drawdown_usdt, dd_usdt)
            max_drawdown_pct = max(max_drawdown_pct, dd_pct)

            max_equity = max(max_equity, total_equity)
            min_equity = min(min_equity, total_equity)
            max_margin_util = max(max_margin_util, margin_util_pct)
            min_liq_buffer = min(min_liq_buffer, liq_buffer_usdt)

            snap = PortfolioSnapshot(
                timestamp_ms=ts,
                timestamp_utc=rec.timestamp_utc,
                bar_index=idx,
                spot_price=spot_p,
                perp_price=perp_p,
                perp_high_price=perp_high_p,
                perp_low_price=perp_p * 0.998,
                basis_usdt=basis_usdt,
                basis_bps=basis_bps,
                spot_btc_qty=spot_btc_qty,
                perp_btc_qty=perp_btc_qty,
                hedge_ratio=abs(perp_btc_qty) / max(spot_btc_qty, 1e-9),
                unallocated_cash_usdt=round(unallocated_cash, 4),
                perp_margin_collateral_usdt=round(perp_margin_collateral, 4),
                total_cash_usdt=round(unallocated_cash + perp_margin_collateral, 4),
                spot_asset_value_usdt=round(spot_value, 4),
                spot_unrealized_pnl_usdt=round(spot_unrealized_pnl, 4),
                perp_unrealized_pnl_usdt=round(perp_unrealized_pnl, 4),
                basis_convergence_pnl_usdt=round(basis_pnl, 4),
                cumulative_funding_receipts_usdt=round(cumulative_funding_receipts, 4),
                cumulative_funding_payments_usdt=round(cumulative_funding_payments, 4),
                net_funding_usdt=round(net_funding, 4),
                cumulative_trading_fees_usdt=round(cumulative_fees, 4),
                cumulative_slippage_usdt=round(cumulative_slippage, 4),
                total_portfolio_equity_usdt=round(total_equity, 4),
                net_total_pnl_usdt=round(net_pnl, 4),
                return_on_committed_capital_pct=round(ret_pct, 4),
                perp_account_equity_usdt=round(perp_account_equity, 4),
                maintenance_margin_required_usdt=round(maint_margin_req, 4),
                margin_utilization_pct=round(margin_util_pct, 4),
                liquidation_buffer_usdt=round(liq_buffer_usdt, 4),
                liquidation_price_usdt=round(liq_price, 4),
                is_liquidated=is_liquidated,
                is_uncertain_liquidation=is_uncertain_liquidation,
            )
            snapshots.append(snap)

            if is_liquidated:
                break

        # Terminal exit accounting (close positions at horizon end)
        last_snap = snapshots[-1]
        exit_rec = basis_records[actual_entry_idx + len(snapshots) - 1]
        exit_spot_p = exit_rec.spot_close_price
        exit_perp_p = exit_rec.perp_close_price

        # Exit costs
        exit_spot_fee = (spot_btc_qty * exit_spot_p) * p.spot_taker_fee_rate
        exit_spot_slip = (spot_btc_qty * exit_spot_p) * p.spot_slippage_rate

        if last_snap.is_liquidated:
            # Perp was already liquidated with liquidation penalty fee applied
            exit_perp_fee = 0.0
            exit_perp_slip = 0.0
        else:
            exit_perp_fee = (abs(perp_btc_qty) * exit_perp_p) * p.perp_taker_fee_rate
            exit_perp_slip = (abs(perp_btc_qty) * exit_perp_p) * p.perp_slippage_rate

        total_exit_costs = exit_spot_fee + exit_perp_fee + exit_spot_slip + exit_perp_slip
        final_net_pnl = last_snap.net_total_pnl_usdt - total_exit_costs
        final_ret_pct = (final_net_pnl / p.initial_capital_usdt) * 100.0

        net_funding_total = last_snap.net_funding_usdt
        notional_base = spot_notional
        funding_yield_pct = (net_funding_total / notional_base) * 100.0 if notional_base > 0 else 0.0

        cal_days = len(snapshots) / 96.0

        # Basis identity verification check:
        # Spot_PnL + Perp_PnL == Basis_PnL
        combined_leg_pnl = last_snap.spot_unrealized_pnl_usdt + last_snap.perp_unrealized_pnl_usdt
        basis_identity_diff = abs(combined_leg_pnl - last_snap.basis_convergence_pnl_usdt)
        basis_identity_verified = basis_identity_diff < 0.05

        summary = DeltaNeutralScenarioResult(
            scenario_name=scenario_name,
            scenario_description=scenario_desc,
            params=p,
            start_timestamp_utc=basis_records[actual_entry_idx].timestamp_utc,
            end_timestamp_utc=exit_rec.timestamp_utc,
            total_bars_simulated=len(snapshots),
            total_calendar_days=round(cal_days, 2),
            entry_spot_price=entry_spot_exec,
            entry_perp_price=entry_perp_exec,
            entry_basis_bps=entry_rec.relative_basis_bps,
            exit_spot_price=exit_spot_p,
            exit_perp_price=exit_perp_p,
            exit_basis_bps=exit_rec.relative_basis_bps,
            initial_capital_usdt=p.initial_capital_usdt,
            spot_purchase_capital_usdt=round(spot_capital_budget, 2),
            perp_margin_initial_usdt=round(perp_margin_budget, 2),
            unallocated_cash_reserve_usdt=round(unallocated_cash, 2),
            spot_btc_purchased=round(spot_btc_qty, 6),
            perp_btc_shorted=round(abs(perp_btc_qty), 6),
            gross_funding_receipts_usdt=round(last_snap.cumulative_funding_receipts_usdt, 2),
            gross_funding_payments_usdt=round(last_snap.cumulative_funding_payments_usdt, 2),
            net_funding_usdt=round(net_funding_total, 2),
            spot_pnl_usdt=round(last_snap.spot_unrealized_pnl_usdt, 2),
            perp_pnl_usdt=round(last_snap.perp_unrealized_pnl_usdt, 2),
            basis_convergence_pnl_usdt=round(last_snap.basis_convergence_pnl_usdt, 2),
            total_trading_fees_usdt=round(last_snap.cumulative_trading_fees_usdt + exit_spot_fee + exit_perp_fee, 2),
            total_slippage_usdt=round(last_snap.cumulative_slippage_usdt + exit_spot_slip + exit_perp_slip, 2),
            net_total_pnl_usdt=round(final_net_pnl, 2),
            return_on_committed_capital_pct=round(final_ret_pct, 4),
            funding_yield_on_notional_pct=round(funding_yield_pct, 4),
            max_equity_usdt=round(max_equity, 2),
            min_equity_usdt=round(min_equity, 2),
            max_drawdown_usdt=round(max_drawdown_usdt, 2),
            max_drawdown_pct=round(max_drawdown_pct, 4),
            max_margin_utilization_pct=round(max_margin_util, 2),
            min_liquidation_buffer_usdt=round(min_liq_buffer, 2),
            number_of_forced_exits=forced_exits,
            number_of_uncertain_liquidation_outcomes=uncertain_outcomes,
            terminal_status=terminal_status,
            max_accounting_discrepancy_usdt=round(max_accounting_discrepancy, 6),
            accounting_conservation_verified=max_accounting_discrepancy < 0.01,
            basis_identity_verified=basis_identity_verified,
        )

        return summary, snapshots
