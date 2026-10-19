"""Independent Portfolio Accounting Engine & Execution Ledger V1.

Sprint 11.22 Phase 1:
Completely independent implementation of canonical spot portfolio accounting:
- Starting Capital: 10,000.00 USDT.
- Maximum Allocation: 98% (9,800.00 USDT max allocation per entry).
- Frictions:
  * Entry fee: 10 bps, entry slippage: 5 bps (fill = next_open * 1.0005).
  * Exit fee: 10 bps, exit slippage: 5 bps (fill = next_open * 0.9995).
  * Nominal round-trip: ~30 bps.
- Next-bar Open fills.
- Strict data continuity and outage checks (300,000 ms step for 5m candles).
- Comprehensive fill ledger recording every transaction with before/after balances.
- Terminal mark-to-market and final liquidation accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CanonicalFillRecord:
    """Individual execution fill record with complete before/after audit states."""
    decision_id: int
    order_id: int
    fill_id: int
    strategy_id: str
    decision_utc: str
    execution_utc: str
    side: str                          # 'BUY' or 'SELL'
    reference_price: float             # next bar open
    fill_price: float                  # open * (1 +/- slippage)
    btc_quantity: float
    gross_notional: float
    fee_usdt: float
    slippage_usdt: float
    cash_before: float
    cash_after: float
    btc_before: float
    btc_after: float
    equity_before: float
    equity_after: float
    position_id: int
    reason: str                        # 'STRATEGY_SIGNAL', 'TERMINAL_LIQUIDATION'


class IndependentPortfolioAccountant:
    """Independent decimal-safe portfolio accountant."""

    INITIAL_CAPITAL = Decimal("10000.00")
    MAX_ALLOCATION_PCT = Decimal("0.98")
    FEE_RATE = Decimal("0.0010")       # 10 bps
    SLIPPAGE_RATE = Decimal("0.0005")  # 5 bps
    EXPECTED_STEP_MS = 300000          # 5 minutes in milliseconds

    def __init__(self, df_5m: pd.DataFrame):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.open_prices = self.df_5m["open"].to_numpy(dtype=np.float64)
        self.close_prices = self.df_5m["close"].to_numpy(dtype=np.float64)
        self.open_times = self.df_5m["open_time"].to_numpy(dtype=np.int64)
        self.n_bars = len(self.df_5m)

    def execute_replay(
        self,
        strategy_id: str,
        start_bar: int,
        end_bar: int,
        signal_generator_fn: Any
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Execute independent replay with complete fill auditing."""
        cash = self.INITIAL_CAPITAL
        btc = Decimal("0.0")
        in_pos = False

        fills: List[CanonicalFillRecord] = []
        equity_series: List[float] = []

        position_id = 0
        fill_id = 0
        order_id = 0
        total_fees = Decimal("0.0")
        total_slippage = Decimal("0.0")
        total_turnover = Decimal("0.0")
        time_in_market_bars = 0
        entry_bar = 0

        # Special case: CASH_ONLY
        if strategy_id == "CASH_ONLY":
            summary = {
                "strategy_id": strategy_id,
                "start_bar": start_bar,
                "end_bar": end_bar,
                "initial_capital_usdt": float(self.INITIAL_CAPITAL),
                "final_equity_usdt": float(self.INITIAL_CAPITAL),
                "net_pnl_usdt": 0.0,
                "net_return_pct": 0.0,
                "total_trades": 0,
                "total_fills": 0,
                "total_fees_usdt": 0.0,
                "total_slippage_usdt": 0.0,
                "total_friction_usdt": 0.0,
                "turnover_usdt": 0.0,
                "time_in_market_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "realized_pnl_usdt": 0.0,
                "terminal_unrealized_pnl_usdt": 0.0
            }
            return pd.DataFrame(), summary

        # Special case: BUY_AND_HOLD
        if strategy_id == "BUY_AND_HOLD":
            # Check continuity for entry
            t_curr = self.open_times[start_bar]
            t_next = self.open_times[start_bar + 1]
            if t_next - t_curr != self.EXPECTED_STEP_MS:
                raise ValueError(f"Data gap detected at start bar {start_bar}: step={t_next - t_curr}ms")

            # Entry
            ref_open = Decimal(str(self.open_prices[start_bar + 1]))
            fill_p = ref_open * (Decimal("1.0") + self.SLIPPAGE_RATE)
            allocated = cash * self.MAX_ALLOCATION_PCT
            entry_fee = allocated * self.FEE_RATE
            entry_slip = (fill_p - ref_open) * ((allocated - entry_fee) / fill_p)

            order_id += 1
            fill_id += 1
            position_id += 1
            btc_bought = (allocated - entry_fee) / fill_p
            cash_before = cash
            cash -= allocated
            btc_before = btc
            btc += btc_bought
            total_fees += entry_fee
            total_slippage += entry_slip
            total_turnover += allocated

            fills.append(CanonicalFillRecord(
                decision_id=start_bar,
                order_id=order_id,
                fill_id=fill_id,
                strategy_id=strategy_id,
                decision_utc=str(pd.to_datetime(int(self.open_times[start_bar]), unit="ms", utc=True)),
                execution_utc=str(pd.to_datetime(int(t_next), unit="ms", utc=True)),
                side="BUY",
                reference_price=float(ref_open),
                fill_price=float(fill_p),
                btc_quantity=float(btc_bought),
                gross_notional=float(allocated),
                fee_usdt=float(entry_fee),
                slippage_usdt=float(entry_slip),
                cash_before=float(cash_before),
                cash_after=float(cash),
                btc_before=float(btc_before),
                btc_after=float(btc),
                equity_before=float(cash_before),
                equity_after=float(cash + btc * ref_open),
                position_id=position_id,
                reason="STRATEGY_SIGNAL"
            ))

            # Mark to market continuously
            for b in range(start_bar + 1, end_bar + 1):
                c_price = Decimal(str(self.close_prices[b]))
                mtm_eq = cash + (btc * c_price)
                equity_series.append(float(mtm_eq))

            # Terminal liquidation
            exit_ref = Decimal(str(self.close_prices[end_bar]))
            exit_fill_p = exit_ref * (Decimal("1.0") - self.SLIPPAGE_RATE)
            gross_proc = btc * exit_fill_p
            exit_fee = gross_proc * self.FEE_RATE
            exit_slip = (exit_ref - exit_fill_p) * btc
            net_proc = gross_proc - exit_fee

            order_id += 1
            fill_id += 1
            cash_before = cash
            cash += net_proc
            btc_before = btc
            btc = Decimal("0.0")
            total_fees += exit_fee
            total_slippage += exit_slip
            total_turnover += gross_proc

            fills.append(CanonicalFillRecord(
                decision_id=end_bar,
                order_id=order_id,
                fill_id=fill_id,
                strategy_id=strategy_id,
                decision_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                execution_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                side="SELL",
                reference_price=float(exit_ref),
                fill_price=float(exit_fill_p),
                btc_quantity=float(btc_before),
                gross_notional=float(gross_proc),
                fee_usdt=float(exit_fee),
                slippage_usdt=float(exit_slip),
                cash_before=float(cash_before),
                cash_after=float(cash),
                btc_before=float(btc_before),
                btc_after=0.0,
                equity_before=float(cash_before + btc_before * exit_ref),
                equity_after=float(cash),
                position_id=position_id,
                reason="TERMINAL_LIQUIDATION"
            ))

            final_eq = float(cash)
            net_pnl = final_eq - float(self.INITIAL_CAPITAL)
            ret_pct = (net_pnl / float(self.INITIAL_CAPITAL)) * 100.0

            eq_arr = np.array(equity_series)
            running_max = np.maximum.accumulate(eq_arr)
            dd = (eq_arr - running_max) / running_max
            max_dd = float(np.min(dd) * 100.0) if len(dd) > 0 else 0.0

            summary = {
                "strategy_id": strategy_id,
                "start_bar": start_bar,
                "end_bar": end_bar,
                "initial_capital_usdt": float(self.INITIAL_CAPITAL),
                "final_equity_usdt": round(final_eq, 2),
                "net_pnl_usdt": round(net_pnl, 2),
                "net_return_pct": round(ret_pct, 2),
                "total_trades": 1,
                "total_fills": len(fills),
                "total_fees_usdt": round(float(total_fees), 2),
                "total_slippage_usdt": round(float(total_slippage), 2),
                "total_friction_usdt": round(float(total_fees + total_slippage), 2),
                "turnover_usdt": round(float(total_turnover), 2),
                "time_in_market_pct": 100.0,
                "max_drawdown_pct": round(max_dd, 2),
                "win_rate_pct": 100.0 if net_pnl > 0 else 0.0,
                "realized_pnl_usdt": round(net_pnl, 2),
                "terminal_unrealized_pnl_usdt": 0.0
            }
            return pd.DataFrame([f.__dict__ for f in fills]), summary

        # Step-by-step active strategy execution
        step_bars = 12
        allocated_cash = Decimal("0.0")
        trade_wins = 0
        total_completed_trades = 0

        for b in range(start_bar, end_bar, step_bars):
            # Check data continuity to next bar
            if b + 1 >= end_bar:
                break
            t_curr = self.open_times[b]
            t_next = self.open_times[b + 1]
            if t_next - t_curr != self.EXPECTED_STEP_MS:
                # Reject execution across gap
                continue

            current_pos = "BTC" if in_pos else "USDT"
            signal = signal_generator_fn(b, current_pos)

            # Signal execution at bar b+1 open
            if signal == "ENTER" and not in_pos:
                ref_open = Decimal(str(self.open_prices[b + 1]))
                fill_p = ref_open * (Decimal("1.0") + self.SLIPPAGE_RATE)
                alloc = cash * self.MAX_ALLOCATION_PCT
                e_fee = alloc * self.FEE_RATE
                e_slip = (fill_p - ref_open) * ((alloc - e_fee) / fill_p)
                btc_bought = (alloc - e_fee) / fill_p

                order_id += 1
                fill_id += 1
                position_id += 1
                cash_before = cash
                cash -= alloc
                btc_before = btc
                btc += btc_bought
                allocated_cash = alloc
                in_pos = True
                entry_bar = b + 1
                total_fees += e_fee
                total_slippage += e_slip
                total_turnover += alloc

                fills.append(CanonicalFillRecord(
                    decision_id=b,
                    order_id=order_id,
                    fill_id=fill_id,
                    strategy_id=strategy_id,
                    decision_utc=str(pd.to_datetime(int(t_curr), unit="ms", utc=True)),
                    execution_utc=str(pd.to_datetime(int(t_next), unit="ms", utc=True)),
                    side="BUY",
                    reference_price=float(ref_open),
                    fill_price=float(fill_p),
                    btc_quantity=float(btc_bought),
                    gross_notional=float(alloc),
                    fee_usdt=float(e_fee),
                    slippage_usdt=float(e_slip),
                    cash_before=float(cash_before),
                    cash_after=float(cash),
                    btc_before=float(btc_before),
                    btc_after=float(btc),
                    equity_before=float(cash_before),
                    equity_after=float(cash + btc * ref_open),
                    position_id=position_id,
                    reason="STRATEGY_SIGNAL"
                ))

            elif signal == "EXIT" and in_pos:
                ref_open = Decimal(str(self.open_prices[b + 1]))
                exit_fill_p = ref_open * (Decimal("1.0") - self.SLIPPAGE_RATE)
                gross_proc = btc * exit_fill_p
                ex_fee = gross_proc * self.FEE_RATE
                ex_slip = (ref_open - exit_fill_p) * btc
                net_proc = gross_proc - ex_fee
                trade_pnl = net_proc - allocated_cash

                if trade_pnl > 0:
                    trade_wins += 1
                total_completed_trades += 1

                order_id += 1
                fill_id += 1
                cash_before = cash
                cash += net_proc
                btc_before = btc
                btc = Decimal("0.0")
                in_pos = False
                h_bars = (b + 1) - entry_bar
                time_in_market_bars += h_bars
                total_fees += ex_fee
                total_slippage += ex_slip
                total_turnover += gross_proc

                fills.append(CanonicalFillRecord(
                    decision_id=b,
                    order_id=order_id,
                    fill_id=fill_id,
                    strategy_id=strategy_id,
                    decision_utc=str(pd.to_datetime(int(t_curr), unit="ms", utc=True)),
                    execution_utc=str(pd.to_datetime(int(t_next), unit="ms", utc=True)),
                    side="SELL",
                    reference_price=float(ref_open),
                    fill_price=float(exit_fill_p),
                    btc_quantity=float(btc_before),
                    gross_notional=float(gross_proc),
                    fee_usdt=float(ex_fee),
                    slippage_usdt=float(ex_slip),
                    cash_before=float(cash_before),
                    cash_after=float(cash),
                    btc_before=float(btc_before),
                    btc_after=0.0,
                    equity_before=float(cash_before + btc_before * ref_open),
                    equity_after=float(cash),
                    position_id=position_id,
                    reason="STRATEGY_SIGNAL"
                ))

            # MTM equity tracking
            c_price = Decimal(str(self.close_prices[b]))
            equity_series.append(float(cash + btc * c_price))

        # Terminal liquidation if still in position
        if in_pos and btc > Decimal("0.0"):
            exit_ref = Decimal(str(self.close_prices[end_bar]))
            exit_fill_p = exit_ref * (Decimal("1.0") - self.SLIPPAGE_RATE)
            gross_proc = btc * exit_fill_p
            ex_fee = gross_proc * self.FEE_RATE
            ex_slip = (exit_ref - exit_fill_p) * btc
            net_proc = gross_proc - ex_fee
            trade_pnl = net_proc - allocated_cash

            if trade_pnl > 0:
                trade_wins += 1
            total_completed_trades += 1

            order_id += 1
            fill_id += 1
            cash_before = cash
            cash += net_proc
            btc_before = btc
            btc = Decimal("0.0")
            in_pos = False
            h_bars = end_bar - entry_bar
            time_in_market_bars += h_bars
            total_fees += ex_fee
            total_slippage += ex_slip
            total_turnover += gross_proc

            fills.append(CanonicalFillRecord(
                decision_id=end_bar,
                order_id=order_id,
                fill_id=fill_id,
                strategy_id=strategy_id,
                decision_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                execution_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                side="SELL",
                reference_price=float(exit_ref),
                fill_price=float(exit_fill_p),
                btc_quantity=float(btc_before),
                gross_notional=float(gross_proc),
                fee_usdt=float(ex_fee),
                slippage_usdt=float(ex_slip),
                cash_before=float(cash_before),
                cash_after=float(cash),
                btc_before=float(btc_before),
                btc_after=0.0,
                equity_before=float(cash_before + btc_before * exit_ref),
                equity_after=float(cash),
                position_id=position_id,
                reason="TERMINAL_LIQUIDATION"
            ))

        final_eq = float(cash)
        net_pnl = final_eq - float(self.INITIAL_CAPITAL)
        ret_pct = (net_pnl / float(self.INITIAL_CAPITAL)) * 100.0

        eq_arr = np.array(equity_series)
        running_max = np.maximum.accumulate(eq_arr)
        dd = (eq_arr - running_max) / running_max
        max_dd = float(np.min(dd) * 100.0) if len(dd) > 0 else 0.0

        total_window_bars = end_bar - start_bar
        time_in_market_pct = (time_in_market_bars / total_window_bars) * 100.0 if total_window_bars > 0 else 0.0
        win_rate = (trade_wins / total_completed_trades) * 100.0 if total_completed_trades > 0 else 0.0

        summary = {
            "strategy_id": strategy_id,
            "start_bar": start_bar,
            "end_bar": end_bar,
            "initial_capital_usdt": float(self.INITIAL_CAPITAL),
            "final_equity_usdt": round(final_eq, 2),
            "net_pnl_usdt": round(net_pnl, 2),
            "net_return_pct": round(ret_pct, 2),
            "total_trades": total_completed_trades,
            "total_fills": len(fills),
            "total_fees_usdt": round(float(total_fees), 2),
            "total_slippage_usdt": round(float(total_slippage), 2),
            "total_friction_usdt": round(float(total_fees + total_slippage), 2),
            "turnover_usdt": round(float(total_turnover), 2),
            "time_in_market_pct": round(time_in_market_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate_pct": round(win_rate, 2),
            "realized_pnl_usdt": round(net_pnl, 2),
            "terminal_unrealized_pnl_usdt": 0.0
        }

        df_fills = pd.DataFrame([f.__dict__ for f in fills])
        return df_fills, summary
