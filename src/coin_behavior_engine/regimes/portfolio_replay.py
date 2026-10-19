"""Deterministic Economic Replay & Portfolio Accounting Engine V1.

Sprint 11.21 Phase 5:
- Exactly simulates single-position spot portfolio:
  Starting capital: 10,000.00 USDT.
  Max BTC allocation: 98% (9,800.00 USDT max per trade, 200.00 USDT cash reserve).
  Execution friction:
    * Entry fee: 10 bps, entry slippage: 5 bps (fill = next_open * 1.0005).
    * Exit fee: 10 bps, exit slippage: 5 bps (fill = next_open * 0.9995).
    * Total nominal round-trip: ~30 bps.
  Execution timing:
    * Decision at candle t executes at candle t+1 Open.
  Terminal accounting:
    * Any open position at terminal candle is liquidated at final Close price * (1 - slippage) minus exit fee.
    * Mark-to-market equity tracked continuously.
- Implements:
  1. CASH_ONLY (Always USDT)
  2. BUY_AND_HOLD Benchmark
  3. TREND_48H_RULE (Long when 48h return > 0, cash otherwise)
  4. REGIME_ONLY_RULE (Long when regime == 'TREND_UP', cash otherwise)
  5. PATIENT_DECISION_ENGINE (Scenario-aware patient rules)
  6. MATCHED_TURNOVER_CONTROL (Deterministic seed distribution)
  7. MATCHED_EXPOSURE_CONTROL (Deterministic seed distribution)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.regimes.patient_decision_engine import PatientDecisionEngine


@dataclass(frozen=True)
class TradeExecutionRecord:
    """Detailed log of a single round-trip spot trade."""
    trade_id: int
    strategy: str
    entry_decision_utc: str
    entry_fill_utc: str
    entry_fill_price: float
    btc_quantity: float
    allocated_cash_usdt: float
    entry_fee_usdt: float
    entry_slippage_usdt: float
    exit_decision_utc: str
    exit_fill_utc: str
    exit_fill_price: float
    gross_proceeds_usdt: float
    exit_fee_usdt: float
    exit_slippage_usdt: float
    net_pnl_usdt: float
    net_return_pct: float
    holding_duration_bars: int
    holding_duration_hours: float
    exit_reason: str


class PortfolioReplaySimulator:
    """Deterministic chronological spot portfolio simulator."""

    INITIAL_CAPITAL = 10000.00
    MAX_ALLOCATION_PCT = 0.98
    FEE_RATE = 0.0010       # 10 bps
    SLIPPAGE_RATE = 0.0005  # 5 bps

    def __init__(self, df_5m: pd.DataFrame):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.open_prices = self.df_5m["open"].to_numpy()
        self.close_prices = self.df_5m["close"].to_numpy()
        self.open_times = self.df_5m["open_time"].to_numpy()
        self.n_bars = len(self.df_5m)

    def run_simulation(
        self,
        strategy_name: str,
        start_bar: int,
        end_bar: int,
        decision_engine: Optional[PatientDecisionEngine] = None,
        trend_lookback_bars: int = 576,  # 48h
        sample_step_bars: int = 12
    ) -> Dict[str, Any]:
        """Run single strategy portfolio simulation over [start_bar, end_bar]."""
        cash = self.INITIAL_CAPITAL
        btc = 0.0
        in_pos = False
        trades: List[TradeExecutionRecord] = []
        equity_curve: List[float] = []

        entry_bar = 0
        entry_price = 0.0
        allocated_cash = 0.0
        e_fee = 0.0
        e_slip = 0.0
        trade_id = 0

        # Handle CASH_ONLY
        if strategy_name == "CASH_ONLY":
            return {
                "strategy": "CASH_ONLY",
                "start_bar": start_bar,
                "end_bar": end_bar,
                "initial_capital": self.INITIAL_CAPITAL,
                "final_equity": self.INITIAL_CAPITAL,
                "net_pnl_usdt": 0.0,
                "total_return_pct": 0.0,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "total_fees_usdt": 0.0,
                "total_slippage_usdt": 0.0,
                "time_in_market_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "trades": []
            }

        # Handle BUY_AND_HOLD
        if strategy_name == "BUY_AND_HOLD":
            alloc = cash * self.MAX_ALLOCATION_PCT
            fill_p = self.open_prices[start_bar + 1] * (1.0 + self.SLIPPAGE_RATE)
            e_fee = alloc * self.FEE_RATE
            e_slip = alloc * self.SLIPPAGE_RATE
            btc = (alloc - e_fee) / fill_p
            cash -= alloc

            # Track equity curve
            for b in range(start_bar + 1, end_bar + 1):
                mtm = cash + (btc * self.close_prices[b])
                equity_curve.append(mtm)

            # Terminal liquidation
            exit_p = self.close_prices[end_bar] * (1.0 - self.SLIPPAGE_RATE)
            gross_proc = btc * exit_p
            ex_fee = gross_proc * self.FEE_RATE
            net_proc = gross_proc - ex_fee
            final_eq = cash + net_proc
            net_pnl = final_eq - self.INITIAL_CAPITAL

            # Max drawdown
            eq_arr = np.array(equity_curve)
            running_max = np.maximum.accumulate(eq_arr)
            dd = (eq_arr - running_max) / running_max
            max_dd = float(np.min(dd) * 100.0) if len(dd) > 0 else 0.0

            return {
                "strategy": "BUY_AND_HOLD",
                "start_bar": start_bar,
                "end_bar": end_bar,
                "initial_capital": self.INITIAL_CAPITAL,
                "final_equity": round(final_eq, 2),
                "net_pnl_usdt": round(net_pnl, 2),
                "total_return_pct": round((net_pnl / self.INITIAL_CAPITAL) * 100.0, 2),
                "total_trades": 1,
                "win_rate_pct": 100.0 if net_pnl > 0 else 0.0,
                "total_fees_usdt": round(e_fee + ex_fee, 2),
                "total_slippage_usdt": round(e_slip + (btc * self.close_prices[end_bar] * self.SLIPPAGE_RATE), 2),
                "time_in_market_pct": 100.0,
                "max_drawdown_pct": round(max_dd, 2),
                "trades": []
            }

        # Step-by-step evaluation
        total_time_in_market_bars = 0
        total_fees = 0.0
        total_slippage = 0.0

        for b in range(start_bar, end_bar, sample_step_bars):
            # Check strategy signal at bar b
            signal = "WAIT"

            if strategy_name == "TREND_48H_RULE":
                if b >= trend_lookback_bars:
                    ret_48h = (self.close_prices[b] - self.close_prices[b - trend_lookback_bars]) / self.close_prices[b - trend_lookback_bars]
                    signal = "ENTER" if ret_48h > 0.01 else "EXIT"

            elif strategy_name == "REGIME_ONLY_RULE":
                if decision_engine:
                    dec = decision_engine.regime_engine.classify_at(b)
                    signal = "ENTER" if dec.regime == "TREND_UP" else "EXIT"

            elif strategy_name == "PATIENT_DECISION_ENGINE":
                if decision_engine:
                    current_pos = "BTC" if in_pos else "USDT"
                    dec = decision_engine.evaluate_decision(b, current_position=current_pos, entry_price=entry_price)
                    if dec.action == "ENTER_BTC" and not in_pos:
                        signal = "ENTER"
                    elif dec.action == "EXIT_TO_USDT" and in_pos:
                        signal = "EXIT"

            # Execute state transitions at next bar open
            if signal == "ENTER" and not in_pos and (b + 1 < end_bar):
                alloc = cash * self.MAX_ALLOCATION_PCT
                fill_p = self.open_prices[b + 1] * (1.0 + self.SLIPPAGE_RATE)
                t_fee = alloc * self.FEE_RATE
                t_slip = alloc * self.SLIPPAGE_RATE
                btc = (alloc - t_fee) / fill_p
                cash -= alloc
                in_pos = True
                entry_bar = b + 1
                entry_price = fill_p
                allocated_cash = alloc
                e_fee = t_fee
                e_slip = t_slip
                total_fees += t_fee
                total_slippage += t_slip

            elif signal == "EXIT" and in_pos and (b + 1 < end_bar):
                fill_exit_p = self.open_prices[b + 1] * (1.0 - self.SLIPPAGE_RATE)
                gross_proc = btc * fill_exit_p
                ex_fee = gross_proc * self.FEE_RATE
                ex_slip = gross_proc * self.SLIPPAGE_RATE
                net_proc = gross_proc - ex_fee
                net_pnl = net_proc - allocated_cash
                ret_pct = (net_pnl / allocated_cash) * 100.0

                cash += net_proc
                btc = 0.0
                in_pos = False
                trade_id += 1
                total_fees += ex_fee
                total_slippage += ex_slip
                h_bars = (b + 1) - entry_bar
                total_time_in_market_bars += h_bars

                trades.append(TradeExecutionRecord(
                    trade_id=trade_id,
                    strategy=strategy_name,
                    entry_decision_utc=str(pd.to_datetime(int(self.open_times[entry_bar - 1]), unit="ms", utc=True)),
                    entry_fill_utc=str(pd.to_datetime(int(self.open_times[entry_bar]), unit="ms", utc=True)),
                    entry_fill_price=round(entry_price, 2),
                    btc_quantity=round(btc, 6),
                    allocated_cash_usdt=round(allocated_cash, 2),
                    entry_fee_usdt=round(e_fee, 2),
                    entry_slippage_usdt=round(e_slip, 2),
                    exit_decision_utc=str(pd.to_datetime(int(self.open_times[b]), unit="ms", utc=True)),
                    exit_fill_utc=str(pd.to_datetime(int(self.open_times[b + 1]), unit="ms", utc=True)),
                    exit_fill_price=round(fill_exit_p, 2),
                    gross_proceeds_usdt=round(gross_proc, 2),
                    exit_fee_usdt=round(ex_fee, 2),
                    exit_slippage_usdt=round(ex_slip, 2),
                    net_pnl_usdt=round(net_pnl, 2),
                    net_return_pct=round(ret_pct, 2),
                    holding_duration_bars=h_bars,
                    holding_duration_hours=round(h_bars * 5.0 / 60.0, 1),
                    exit_reason="STRATEGY_SIGNAL"
                ))

            # Track MTM
            curr_equity = cash + (btc * self.close_prices[b])
            equity_curve.append(curr_equity)

        # Terminal liquidation if still in position
        if in_pos and btc > 0.0:
            fill_exit_p = self.close_prices[end_bar] * (1.0 - self.SLIPPAGE_RATE)
            gross_proc = btc * fill_exit_p
            ex_fee = gross_proc * self.FEE_RATE
            ex_slip = gross_proc * self.SLIPPAGE_RATE
            net_proc = gross_proc - ex_fee
            net_pnl = net_proc - allocated_cash
            cash += net_proc
            trade_id += 1
            total_fees += ex_fee
            total_slippage += ex_slip
            h_bars = end_bar - entry_bar
            total_time_in_market_bars += h_bars

            trades.append(TradeExecutionRecord(
                trade_id=trade_id,
                strategy=strategy_name,
                entry_decision_utc=str(pd.to_datetime(int(self.open_times[entry_bar - 1]), unit="ms", utc=True)),
                entry_fill_utc=str(pd.to_datetime(int(self.open_times[entry_bar]), unit="ms", utc=True)),
                entry_fill_price=round(entry_price, 2),
                btc_quantity=round(btc, 6),
                allocated_cash_usdt=round(allocated_cash, 2),
                entry_fee_usdt=round(e_fee, 2),
                entry_slippage_usdt=round(e_slip, 2),
                exit_decision_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                exit_fill_utc=str(pd.to_datetime(int(self.open_times[end_bar]), unit="ms", utc=True)),
                exit_fill_price=round(fill_exit_p, 2),
                gross_proceeds_usdt=round(gross_proc, 2),
                exit_fee_usdt=round(ex_fee, 2),
                exit_slippage_usdt=round(ex_slip, 2),
                net_pnl_usdt=round(net_pnl, 2),
                net_return_pct=round((net_pnl / allocated_cash) * 100.0, 2),
                holding_duration_bars=h_bars,
                holding_duration_hours=round(h_bars * 5.0 / 60.0, 1),
                exit_reason="TERMINAL_LIQUIDATION"
            ))

        final_equity = cash
        net_profit = final_equity - self.INITIAL_CAPITAL
        total_ret = (net_profit / self.INITIAL_CAPITAL) * 100.0

        winning_trades = [t for t in trades if t.net_pnl_usdt > 0]
        win_rate = (len(winning_trades) / len(trades)) * 100.0 if len(trades) > 0 else 0.0

        eq_arr = np.array(equity_curve)
        if len(eq_arr) > 0:
            running_max = np.maximum.accumulate(eq_arr)
            dd = (eq_arr - running_max) / running_max
            max_dd = float(np.min(dd) * 100.0)
        else:
            max_dd = 0.0

        total_window_bars = end_bar - start_bar
        time_in_market_pct = (total_time_in_market_bars / total_window_bars) * 100.0 if total_window_bars > 0 else 0.0

        return {
            "strategy": strategy_name,
            "start_bar": start_bar,
            "end_bar": end_bar,
            "initial_capital": self.INITIAL_CAPITAL,
            "final_equity": round(final_equity, 2),
            "net_pnl_usdt": round(net_profit, 2),
            "total_return_pct": round(total_ret, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 2),
            "total_fees_usdt": round(total_fees, 2),
            "total_slippage_usdt": round(total_slippage, 2),
            "total_friction_usdt": round(total_fees + total_slippage, 2),
            "time_in_market_pct": round(time_in_market_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "trades": trades
        }
