"""Deterministic event-driven historical paper trading simulator.

Sprint 11.03: Market Behavior Research Lab.
Simulates hypothetical spot trades with next-bar execution, fees, slippage,
intrabar stop/target evaluation, and complete equity curve tracking.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    DecisionAction,
    PaperTrade,
    ResearchDecision,
    SimulationRunResult,
    TradeExitReason,
)


class HistoricalPaperSimulator:
    """Simulates trading strategies without contacting any external network or execution endpoint."""

    def __init__(self, config: Optional[ResearchLabConfig] = None):
        self.config = config or ResearchLabConfig()

    def simulate(
        self,
        candles: List[CandleData],
        decisions: List[ResearchDecision],
        strategy_name: str = "Strategy_A_Technical",
    ) -> SimulationRunResult:
        """Run deterministic backtest over candle and decision sequences."""
        run_id = f"SIM-{strategy_name}-{uuid.uuid4().hex[:6]}"
        initial_capital = self.config.initial_capital_usdt
        cash = initial_capital
        position_qty = 0.0
        position_cost_basis = 0.0
        active_trade: Optional[Dict[str, Any]] = None
        trades: List[PaperTrade] = []
        equity_series: List[Dict[str, Any]] = []

        # Map decisions by bar index
        dec_by_idx: Dict[int, ResearchDecision] = {
            i: dec for i, dec in enumerate(decisions)
        }

        # Track benchmarks
        buy_and_hold_start_price = candles[0].close if candles else 1.0
        buy_and_hold_end_price = candles[-1].close if candles else 1.0
        bnh_return_pct = round(((buy_and_hold_end_price - buy_and_hold_start_price) / buy_and_hold_start_price) * 100.0, 3)

        for i, c in enumerate(candles):
            curr_price = c.close
            
            # 1. Manage active position exit evaluation if holding
            if active_trade is not None:
                # Update Max Favorable / Adverse Excursion
                p_entry = active_trade["entry_price"]
                bar_high_pct = (c.high - p_entry) / p_entry
                bar_low_pct = (c.low - p_entry) / p_entry
                active_trade["mfe"] = max(active_trade["mfe"], bar_high_pct)
                active_trade["mae"] = min(active_trade["mae"], bar_low_pct)
                active_trade["bars_held"] += 1

                exit_triggered = False
                exit_price = 0.0
                exit_reason = TradeExitReason.STOP_LOSS

                sl_price = active_trade["stop_loss_price"]
                tp_price = active_trade["target_price"]

                # Conservative Policy: Stop loss checked first if both touched within same bar
                if sl_price and c.low <= sl_price:
                    exit_triggered = True
                    # Exit price capped by open if gap down
                    raw_exit = min(sl_price, c.open)
                    exit_price = raw_exit * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.STOP_LOSS
                elif tp_price and c.high >= tp_price:
                    exit_triggered = True
                    raw_exit = max(tp_price, c.open)
                    exit_price = raw_exit * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.TAKE_PROFIT
                elif active_trade["bars_held"] >= active_trade["max_holding_bars"]:
                    exit_triggered = True
                    exit_price = c.close * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.TIME_EXPIRY
                elif i in dec_by_idx and dec_by_idx[i].action == DecisionAction.SELL_CANDIDATE:
                    exit_triggered = True
                    exit_price = c.close * (1.0 - self.config.slippage_pct)
                    exit_reason = TradeExitReason.SIGNAL_REVERSAL

                if exit_triggered:
                    gross_proceeds = position_qty * exit_price
                    exit_fee = gross_proceeds * self.config.taker_fee_pct
                    net_proceeds = gross_proceeds - exit_fee
                    net_pnl = net_proceeds - position_cost_basis
                    ret_pct = (net_pnl / position_cost_basis) * 100.0 if position_cost_basis > 0 else 0.0

                    trade_rec = PaperTrade(
                        trade_id=active_trade["trade_id"],
                        strategy_name=strategy_name,
                        symbol=c.symbol,
                        side="BUY",
                        entry_time_utc=active_trade["entry_time_utc"],
                        entry_price=round(active_trade["entry_price"], 2),
                        exit_time_utc=c.datetime_close_utc,
                        exit_price=round(exit_price, 2),
                        exit_reason=exit_reason,
                        quantity=round(position_qty, 6),
                        gross_pnl=round(gross_proceeds - (position_qty * active_trade["entry_price"]), 2),
                        fees_paid=round(active_trade["entry_fee"] + exit_fee, 2),
                        slippage_cost=round(active_trade["entry_slippage"] + (position_qty * (raw_exit - exit_price if 'raw_exit' in locals() else 0.0)), 2),
                        net_pnl=round(net_pnl, 2),
                        return_pct=round(ret_pct, 3),
                        holding_period_minutes=active_trade["bars_held"] * 5,  # 5-min intervals
                        max_favorable_excursion=round(active_trade["mfe"] * 100.0, 3),
                        max_adverse_excursion=round(active_trade["mae"] * 100.0, 3),
                    )
                    trades.append(trade_rec)

                    cash += net_proceeds
                    position_qty = 0.0
                    position_cost_basis = 0.0
                    active_trade = None

            # 2. Process Entry Signals (Next-Bar Execution Rule)
            # If previous bar generated BUY_CANDIDATE and we are not currently holding
            if active_trade is None and (i - 1) in dec_by_idx:
                prev_dec = dec_by_idx[i - 1]
                if prev_dec.action == DecisionAction.BUY_CANDIDATE and cash > 50.0:
                    # Execute at current bar open (next observable price)
                    raw_entry = c.open
                    effective_entry_price = raw_entry * (1.0 + self.config.slippage_pct)
                    
                    # Position sizing
                    alloc_usd = min(cash * 0.98, (prev_dec.position_size_pct / 100.0) * cash)
                    if alloc_usd > 50.0:
                        entry_fee = alloc_usd * self.config.taker_fee_pct
                        net_invest = alloc_usd - entry_fee
                        qty = net_invest / effective_entry_price

                        cash -= alloc_usd
                        position_qty = qty
                        position_cost_basis = alloc_usd

                        active_trade = {
                            "trade_id": f"TRD-{uuid.uuid4().hex[:8]}",
                            "entry_time_utc": c.datetime_open_utc,
                            "entry_price": effective_entry_price,
                            "entry_fee": entry_fee,
                            "entry_slippage": qty * (effective_entry_price - raw_entry),
                            "stop_loss_price": prev_dec.stop_loss_price,
                            "target_price": prev_dec.target_price,
                            "max_holding_bars": prev_dec.max_holding_bars,
                            "bars_held": 0,
                            "mfe": 0.0,
                            "mae": 0.0,
                        }

            # 3. Track Portfolio Equity
            pos_val = position_qty * curr_price
            tot_equity = cash + pos_val
            equity_series.append({
                "bar_index": i,
                "timestamp_open": c.timestamp_open,
                "datetime_utc": c.datetime_open_utc,
                "cash": round(cash, 2),
                "position_value": round(pos_val, 2),
                "total_equity": round(tot_equity, 2),
                "drawdown_pct": 0.0,
            })

        # Close out any remaining open position at end of simulation
        if active_trade is not None and candles:
            last_c = candles[-1]
            exit_price = last_c.close * (1.0 - self.config.slippage_pct)
            gross_proceeds = position_qty * exit_price
            exit_fee = gross_proceeds * self.config.taker_fee_pct
            net_proceeds = gross_proceeds - exit_fee
            net_pnl = net_proceeds - position_cost_basis
            ret_pct = (net_pnl / position_cost_basis) * 100.0 if position_cost_basis > 0 else 0.0

            trades.append(PaperTrade(
                trade_id=active_trade["trade_id"],
                strategy_name=strategy_name,
                symbol=last_c.symbol,
                side="BUY",
                entry_time_utc=active_trade["entry_time_utc"],
                entry_price=round(active_trade["entry_price"], 2),
                exit_time_utc=last_c.datetime_close_utc,
                exit_price=round(exit_price, 2),
                exit_reason=TradeExitReason.END_OF_DATA,
                quantity=round(position_qty, 6),
                gross_pnl=round(gross_proceeds - (position_qty * active_trade["entry_price"]), 2),
                fees_paid=round(active_trade["entry_fee"] + exit_fee, 2),
                slippage_cost=round(active_trade["entry_slippage"], 2),
                net_pnl=round(net_pnl, 2),
                return_pct=round(ret_pct, 3),
                holding_period_minutes=active_trade["bars_held"] * 5,
                max_favorable_excursion=round(active_trade["mfe"] * 100.0, 3),
                max_adverse_excursion=round(active_trade["mae"] * 100.0, 3),
            ))
            cash += net_proceeds
            position_qty = 0.0

        # Calculate final performance metrics
        final_capital = cash
        total_net_pnl = final_capital - initial_capital
        net_ret_pct = round((total_net_pnl / initial_capital) * 100.0, 3)

        winning_trades = [t for t in trades if t.net_pnl > 0]
        losing_trades = [t for t in trades if t.net_pnl <= 0]
        n_trades = len(trades)
        win_rate = round(len(winning_trades) / n_trades, 4) if n_trades > 0 else 0.0

        gross_gains = sum(t.net_pnl for t in winning_trades)
        gross_losses = abs(sum(t.net_pnl for t in losing_trades))
        profit_factor = round(gross_gains / gross_losses, 3) if gross_losses > 0 else (999.0 if gross_gains > 0 else 0.0)

        avg_win = gross_gains / len(winning_trades) if winning_trades else 0.0
        avg_loss = gross_losses / len(losing_trades) if losing_trades else 0.0
        expectancy = round((win_rate * avg_win) - ((1.0 - win_rate) * avg_loss), 2)

        # Max drawdown computation across equity curve
        peak_equity = initial_capital
        max_dd_amount = 0.0
        max_dd_pct = 0.0

        for eq_entry in equity_series:
            eq = eq_entry["total_equity"]
            if eq > peak_equity:
                peak_equity = eq
            dd_amt = peak_equity - eq
            dd_pct = (dd_amt / peak_equity) * 100.0 if peak_equity > 0 else 0.0
            eq_entry["drawdown_pct"] = round(dd_pct, 2)
            if dd_amt > max_dd_amount:
                max_dd_amount = dd_amt
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        total_fees = sum(t.fees_paid for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)
        turnover = sum(t.quantity * t.entry_price for t in trades)

        # Sharpe ratio on periodic returns
        period_returns = []
        for j in range(1, len(equity_series)):
            e_curr = equity_series[j]["total_equity"]
            e_prev = equity_series[j - 1]["total_equity"]
            if e_prev > 0:
                period_returns.append((e_curr - e_prev) / e_prev)

        if len(period_returns) > 1:
            mean_r = sum(period_returns) / len(period_returns)
            std_r = math.sqrt(sum((r - mean_r) ** 2 for r in period_returns) / (len(period_returns) - 1))
            # Annualized assuming 5m intervals (105,120 bars/year)
            sharpe = round((mean_r / std_r) * math.sqrt(105120), 2) if std_r > 0 else 0.0
            neg_rets = [r for r in period_returns if r < 0]
            down_std = math.sqrt(sum(r ** 2 for r in neg_rets) / len(neg_rets)) if neg_rets else 0.0
            sortino = round((mean_r / down_std) * math.sqrt(105120), 2) if down_std > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        start_time_s = candles[0].datetime_open_utc if candles else ""
        end_time_s = candles[-1].datetime_close_utc if candles else ""

        return SimulationRunResult(
            run_id=run_id,
            strategy_name=strategy_name,
            start_time_utc=start_time_s,
            end_time_utc=end_time_s,
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            total_net_pnl=round(total_net_pnl, 2),
            return_pct=net_ret_pct,
            total_trades=n_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            max_drawdown_amount=round(max_dd_amount, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            turnover=round(turnover, 2),
            total_fees=round(total_fees, 2),
            total_slippage=round(total_slippage, 2),
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            baseline_buy_and_hold_return_pct=bnh_return_pct,
            baseline_cash_return_pct=0.0,
            trades=trades,
            equity_series=equity_series,
        )

    @classmethod
    def export_trades_csv(cls, trades: List[PaperTrade], output_csv: Path) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [t.to_dict() for t in trades]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    @classmethod
    def export_equity_series_csv(cls, equity_series: List[Dict[str, Any]], output_csv: Path) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(equity_series)
        df.to_csv(output_csv, index=False)
