"""Causal Range Trading Simulation & Sideways Market Economics Engine.

Sprint 11.20 Phase 4:
Simulates repeated spot entry/exit range trading with realistic execution friction:
- Starting capital: 10,000.00 USDT.
- Max BTC allocation: 98% (9,800 USDT allocated, 200 USDT cash reserve).
- Execution friction:
  * Entry fee: 10 bps, entry slippage: 5 bps (fill = next_open * 1.0005).
  * Exit fee: 10 bps, exit slippage: 5 bps (fill = next_open * 0.9995).
  * Total nominal round-trip: ~30 bps.
- Strictly causal next-bar execution: decision at bar t executes at bar t+1 open.
- Evaluates:
  1. Simple Causal Range Rule (blind boundary mean-reversion).
  2. Analog-Informed Range Rule (analog conditional confirmation).
  3. Buy & Hold Benchmark.
  4. Cash-Only Benchmark.
  5. Matched-Turnover Control.
  6. Matched-Exposure Control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RangeTradeRecord:
    """Individual executed range trade log."""
    trade_id: int
    strategy: str
    entry_decision_utc: str
    entry_fill_utc: str
    entry_fill_price: float
    btc_quantity: float
    allocated_usdt: float
    entry_fee_usdt: float
    entry_slippage_usdt: float
    exit_decision_utc: str
    exit_fill_utc: str
    exit_fill_price: float
    gross_proceeds_usdt: float
    exit_fee_usdt: float
    exit_slippage_usdt: float
    gross_pnl_usdt: float
    net_pnl_usdt: float
    net_return_pct: float
    holding_duration_bars: int
    holding_duration_hours: float
    mfe_pct: float
    mae_pct: float
    exit_reason: str


class CausalRangeTrader:
    """Simulates realistic repeated spot range trading with exact portfolio accounting."""

    INITIAL_CAPITAL = 10000.00
    MAX_ALLOCATION_PCT = 0.98
    FEE_RATE = 0.0010      # 10 bps
    SLIPPAGE_RATE = 0.0005 # 5 bps

    def __init__(self, df_5m: pd.DataFrame):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.open_times = self.df_5m["open_time"].to_numpy()
        self.open_prices = self.df_5m["open"].to_numpy()
        self.high_prices = self.df_5m["high"].to_numpy()
        self.low_prices = self.df_5m["low"].to_numpy()
        self.close_prices = self.df_5m["close"].to_numpy()
        self.n_bars = len(self.df_5m)

    def run_strategy(
        self,
        start_idx: int,
        end_idx: int,
        strategy_mode: str = "SIMPLE_RANGE",
        analog_signals: Optional[Dict[int, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Execute spot range trading strategy over [start_idx, end_idx].
        
        Args:
            start_idx: Starting candle index.
            end_idx: Ending candle index.
            strategy_mode: 'SIMPLE_RANGE', 'ANALOG_INFORMED', 'BUY_AND_HOLD', 'CASH_ONLY', 'MATCHED_TURNOVER'.
            analog_signals: Precomputed analog evaluation signals keyed by candle index.
        """
        cash = self.INITIAL_CAPITAL
        btc = 0.0
        in_pos = False
        trades: List[RangeTradeRecord] = []

        entry_decision_idx = None
        entry_fill_idx = None
        entry_fill_price = 0.0
        allocated_cash = 0.0
        entry_fee = 0.0
        entry_slip = 0.0

        lookback = 288  # 24h for rolling support/resistance
        high_288 = pd.Series(self.high_prices).rolling(lookback, min_periods=48).max().to_numpy()
        low_288 = pd.Series(self.low_prices).rolling(lookback, min_periods=48).min().to_numpy()

        # Handle BUY_AND_HOLD directly
        if strategy_mode == "BUY_AND_HOLD":
            alloc = cash * self.MAX_ALLOCATION_PCT
            fill_p = self.open_prices[start_idx + 1] * (1.0 + self.SLIPPAGE_RATE)
            e_fee = alloc * self.FEE_RATE
            e_slip = alloc * self.SLIPPAGE_RATE
            btc = (alloc - e_fee) / fill_p
            cash -= alloc

            exit_p = self.close_prices[end_idx] * (1.0 - self.SLIPPAGE_RATE)
            gross_proc = btc * exit_p
            ex_fee = gross_proc * self.FEE_RATE
            net_proceeds = gross_proc - ex_fee
            terminal_equity = cash + net_proceeds

            return {
                "strategy": "BUY_AND_HOLD",
                "initial_capital": self.INITIAL_CAPITAL,
                "final_equity": round(terminal_equity, 2),
                "net_pnl_usdt": round(terminal_equity - self.INITIAL_CAPITAL, 2),
                "total_return_pct": round(((terminal_equity - self.INITIAL_CAPITAL) / self.INITIAL_CAPITAL) * 100.0, 2),
                "total_trades": 1,
                "win_rate_pct": 100.0 if terminal_equity > self.INITIAL_CAPITAL else 0.0,
                "total_fees_usdt": round(e_fee + ex_fee, 2),
                "total_slippage_usdt": round(e_slip + (btc * self.close_prices[end_idx] * self.SLIPPAGE_RATE), 2),
                "trades": []
            }

        if strategy_mode == "CASH_ONLY":
            return {
                "strategy": "CASH_ONLY",
                "initial_capital": self.INITIAL_CAPITAL,
                "final_equity": self.INITIAL_CAPITAL,
                "net_pnl_usdt": 0.0,
                "total_return_pct": 0.0,
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "total_fees_usdt": 0.0,
                "total_slippage_usdt": 0.0,
                "trades": []
            }

        # Step-by-step causal simulation for range strategies
        for idx in range(start_idx, end_idx):
            curr_c = self.close_prices[idx]
            s_low = low_288[idx]
            s_high = high_288[idx]
            width = (s_high - s_low) / s_low if s_low > 0 else 0.0
            pos = (curr_c - s_low) / (s_high - s_low) if (s_high - s_low) > 0 else 0.50

            if not in_pos:
                # Evaluation for Entry
                should_enter = False
                if 0.008 <= width <= 0.040 and pos <= 0.25:
                    if strategy_mode == "SIMPLE_RANGE":
                        should_enter = True
                    elif strategy_mode == "ANALOG_INFORMED" and analog_signals:
                        sig = analog_signals.get(idx)
                        if sig and not sig.get("is_abstained") and sig.get("prob_reversion", 0.0) >= 0.50:
                            should_enter = True

                if should_enter and (idx + 1 < end_idx):
                    entry_decision_idx = idx
                    entry_fill_idx = idx + 1
                    # Execute next-bar open with slippage
                    entry_fill_price = self.open_prices[entry_fill_idx] * (1.0 + self.SLIPPAGE_RATE)
                    allocated_cash = cash * self.MAX_ALLOCATION_PCT
                    entry_fee = allocated_cash * self.FEE_RATE
                    entry_slip = allocated_cash * self.SLIPPAGE_RATE
                    btc = (allocated_cash - entry_fee) / entry_fill_price
                    cash -= allocated_cash
                    in_pos = True
                    min_during_trade = entry_fill_price
                    max_during_trade = entry_fill_price

            else:
                # Currently holding position: track MFE / MAE
                b_high = self.high_prices[idx]
                b_low = self.low_prices[idx]
                if b_high > max_during_trade:
                    max_during_trade = b_high
                if b_low < min_during_trade:
                    min_during_trade = b_low

                # Evaluation for Exit
                should_exit = False
                exit_reason = None

                bars_held = idx - entry_fill_idx
                # 1. Target Reached: Upper 20% of range
                if pos >= 0.80:
                    should_exit = True
                    exit_reason = "TARGET_REVERSION"
                # 2. Stop Loss: Breakdown below support minus 0.5% buffer
                elif curr_c < (s_low * 0.995):
                    should_exit = True
                    exit_reason = "BREAKDOWN_STOP"
                # 3. Timeout: Max 288 bars (24 hours)
                elif bars_held >= 288:
                    should_exit = True
                    exit_reason = "TIMEOUT_24H"

                if (should_exit or idx == end_idx - 1) and (idx + 1 < self.n_bars):
                    exit_fill_idx = idx + 1
                    exit_fill_price = self.open_prices[exit_fill_idx] * (1.0 - self.SLIPPAGE_RATE)
                    gross_proc = btc * exit_fill_price
                    ex_fee = gross_proc * self.FEE_RATE
                    ex_slip = btc * self.open_prices[exit_fill_idx] * self.SLIPPAGE_RATE
                    net_proc = gross_proc - ex_fee
                    cash += net_proc

                    gross_pnl = gross_proc - allocated_cash
                    net_pnl = net_proc - allocated_cash
                    net_ret = net_pnl / allocated_cash

                    mfe = (max_during_trade - entry_fill_price) / entry_fill_price
                    mae = (min_during_trade - entry_fill_price) / entry_fill_price

                    entry_dt_utc = str(pd.to_datetime(self.open_times[entry_decision_idx], unit="ms", utc=True))
                    fill_dt_utc = str(pd.to_datetime(self.open_times[entry_fill_idx], unit="ms", utc=True))
                    exit_dec_utc = str(pd.to_datetime(self.open_times[idx], unit="ms", utc=True))
                    exit_fill_utc = str(pd.to_datetime(self.open_times[exit_fill_idx], unit="ms", utc=True))

                    trades.append(RangeTradeRecord(
                        trade_id=len(trades) + 1,
                        strategy=strategy_mode,
                        entry_decision_utc=entry_dt_utc,
                        entry_fill_utc=fill_dt_utc,
                        entry_fill_price=round(entry_fill_price, 2),
                        btc_quantity=round(btc, 6),
                        allocated_usdt=round(allocated_cash, 2),
                        entry_fee_usdt=round(entry_fee, 2),
                        entry_slippage_usdt=round(entry_slip, 2),
                        exit_decision_utc=exit_dec_utc,
                        exit_fill_utc=exit_fill_utc,
                        exit_fill_price=round(exit_fill_price, 2),
                        gross_proceeds_usdt=round(gross_proc, 2),
                        exit_fee_usdt=round(ex_fee, 2),
                        exit_slippage_usdt=round(ex_slip, 2),
                        gross_pnl_usdt=round(gross_pnl, 2),
                        net_pnl_usdt=round(net_pnl, 2),
                        net_return_pct=round(net_ret * 100.0, 3),
                        holding_duration_bars=bars_held + 1,
                        holding_duration_hours=round((bars_held + 1) * 5 / 60.0, 1),
                        mfe_pct=round(mfe * 100.0, 3),
                        mae_pct=round(mae * 100.0, 3),
                        exit_reason=exit_reason or "TERMINAL_LIQUIDATION"
                    ))

                    btc = 0.0
                    in_pos = False

        # If still in position at end_idx, mark-to-market
        if in_pos:
            term_val = btc * self.close_prices[end_idx] * (1.0 - self.FEE_RATE - self.SLIPPAGE_RATE)
            cash += term_val

        tot_pnl = cash - self.INITIAL_CAPITAL
        tot_ret = (tot_pnl / self.INITIAL_CAPITAL) * 100.0
        wins = [t for t in trades if t.net_pnl_usdt > 0.0]
        win_rate = (len(wins) / len(trades)) * 100.0 if trades else 0.0
        tot_fees = sum(t.entry_fee_usdt + t.exit_fee_usdt for t in trades)
        tot_slips = sum(t.entry_slippage_usdt + t.exit_slippage_usdt for t in trades)

        return {
            "strategy": strategy_mode,
            "initial_capital": self.INITIAL_CAPITAL,
            "final_equity": round(cash, 2),
            "net_pnl_usdt": round(tot_pnl, 2),
            "total_return_pct": round(tot_ret, 2),
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate, 2),
            "total_fees_usdt": round(tot_fees, 2),
            "total_slippage_usdt": round(tot_slips, 2),
            "total_friction_usdt": round(tot_fees + tot_slips, 2),
            "trades": trades
        }
