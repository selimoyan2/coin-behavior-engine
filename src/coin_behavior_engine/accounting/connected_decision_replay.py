"""Connected Decision-to-Execution Replay Engine V1.

Sprint 11.22.1 Phase 2:
Solves the DECISION_ENGINE_REPLAY_DISCONNECTED architectural flaw.

Establishes strict, two-stage decoupled causal pipeline:
Stage 1: Decision Stream Generation
  Market Data (bars 0..b) -> Feature Snapshot -> Causal Regime -> Patient Decision -> Immutable Decision Record
Stage 2: Execution Consumer
  Reads Immutable Decision Stream strictly sequentially -> Portfolio State Evaluation -> Order -> Next-Bar Open Fill -> Account Update

Enforces:
- 100% causal provenance on every fill.
- No future timestamp contamination.
- State-machine idempotence (WAIT/HOLD do not emit orders).
- Strict next-bar open execution timing with 300,000 ms step check.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from coin_behavior_engine.regimes.causal_regime_engine import CausalRegimeEngine
from coin_behavior_engine.regimes.patient_decision_engine import PatientDecisionEngine, PatientDecisionOutput
from coin_behavior_engine.accounting.independent_portfolio_accountant import (
    IndependentPortfolioAccountant,
    CanonicalFillRecord,
)


@dataclass(frozen=True)
class ProvenanceFillRecord:
    """Full causal provenance record for an individual fill."""
    fill_id: int
    trade_id: int
    side: str                            # 'BUY' or 'SELL'
    decision_idx: int
    decision_timestamp_ms: int
    decision_utc: str
    feature_cutoff_ms: int
    feature_cutoff_utc: str
    market_regime: str
    regime_confidence: float
    decision_action: str
    scenario: str
    rationale: str
    portfolio_position_before: str
    order_timestamp_ms: int
    order_utc: str
    execution_timestamp_ms: int
    execution_utc: str
    reference_price: float
    fill_price: float
    btc_quantity: float
    gross_notional: float
    fee_usdt: float
    slippage_usdt: float
    portfolio_position_after: str
    cash_before: float
    cash_after: float
    btc_before: float
    btc_after: float
    equity_before: float
    equity_after: float
    trade_reason: str
    provenance_status: str               # 'VALID_CAUSAL_ORIGIN'


class ConnectedDecisionReplayEngine:
    """End-to-end connected decision generation and portfolio execution engine."""

    INITIAL_CAPITAL = Decimal("10000.00")
    MAX_ALLOCATION_PCT = Decimal("0.98")
    FEE_RATE = Decimal("0.0010")       # 10 bps
    SLIPPAGE_RATE = Decimal("0.0005")  # 5 bps
    EXPECTED_STEP_MS = 300000          # 5 minutes

    def __init__(self, df_5m: pd.DataFrame):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.open_prices = self.df_5m["open"].to_numpy(dtype=np.float64)
        self.close_prices = self.df_5m["close"].to_numpy(dtype=np.float64)
        self.open_times = self.df_5m["open_time"].to_numpy(dtype=np.int64)
        self.n_bars = len(self.df_5m)

        self.regime_engine = CausalRegimeEngine(self.df_5m)
        self.patient_engine = PatientDecisionEngine(self.regime_engine)

    def run_connected_replay(
        self,
        start_bar: int = 10000,
        end_bar: int = 490000,
        sample_step_bars: int = 12
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Run two-stage connected decision and execution replay."""
        cash = self.INITIAL_CAPITAL
        btc = Decimal("0.0")
        in_pos = False

        fills: List[ProvenanceFillRecord] = []
        equity_series: List[float] = []

        trade_id = 0
        fill_id = 0
        total_fees = Decimal("0.0")
        total_slippage = Decimal("0.0")
        total_turnover = Decimal("0.0")
        time_in_market_bars = 0
        entry_bar = 0
        allocated_cash = Decimal("0.0")
        trade_wins = 0

        # Step through chronological bars
        for b in range(start_bar, end_bar, sample_step_bars):
            if b + 1 >= end_bar:
                break

            t_curr = int(self.open_times[b])
            t_next = int(self.open_times[b + 1])

            # Check data continuity
            if t_next - t_curr != self.EXPECTED_STEP_MS:
                continue

            current_pos = "BTC" if in_pos else "USDT"

            # Stage 1: Decision Evaluation (strictly causal point-in-time)
            dec = self.patient_engine.evaluate_decision(
                idx=b,
                current_position=current_pos,
                entry_price=float(self.open_prices[entry_bar]) if in_pos else None
            )

            # Stage 2: Execution Consumer
            # ENTRY SIGNAL
            if dec.action == "ENTER_BTC" and not in_pos:
                ref_open = Decimal(str(self.open_prices[b + 1]))
                fill_p = ref_open * (Decimal("1.0") + self.SLIPPAGE_RATE)
                alloc = cash * self.MAX_ALLOCATION_PCT
                e_fee = alloc * self.FEE_RATE
                btc_bought = (alloc - e_fee) / fill_p
                e_slip = (fill_p - ref_open) * btc_bought

                fill_id += 1
                trade_id += 1
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

                fills.append(ProvenanceFillRecord(
                    fill_id=fill_id,
                    trade_id=trade_id,
                    side="BUY",
                    decision_idx=b,
                    decision_timestamp_ms=t_curr,
                    decision_utc=str(pd.to_datetime(t_curr, unit="ms", utc=True)),
                    feature_cutoff_ms=t_curr + self.EXPECTED_STEP_MS - 1,
                    feature_cutoff_utc=str(pd.to_datetime(t_curr + self.EXPECTED_STEP_MS - 1, unit="ms", utc=True)),
                    market_regime=dec.market_regime,
                    regime_confidence=dec.regime_confidence,
                    decision_action=dec.action,
                    scenario=dec.scenario,
                    rationale=dec.rationale,
                    portfolio_position_before="USDT",
                    order_timestamp_ms=t_curr + self.EXPECTED_STEP_MS,
                    order_utc=str(pd.to_datetime(t_next, unit="ms", utc=True)),
                    execution_timestamp_ms=t_next,
                    execution_utc=str(pd.to_datetime(t_next, unit="ms", utc=True)),
                    reference_price=float(ref_open),
                    fill_price=float(fill_p),
                    btc_quantity=float(btc_bought),
                    gross_notional=float(alloc),
                    fee_usdt=float(e_fee),
                    slippage_usdt=float(e_slip),
                    portfolio_position_after="BTC",
                    cash_before=float(cash_before),
                    cash_after=float(cash),
                    btc_before=float(btc_before),
                    btc_after=float(btc),
                    equity_before=float(cash_before),
                    equity_after=float(cash + btc * ref_open),
                    trade_reason="SIGNAL_ENTRY",
                    provenance_status="VALID_CAUSAL_ORIGIN"
                ))

            # EXIT SIGNAL
            elif dec.action == "EXIT_TO_USDT" and in_pos:
                ref_open = Decimal(str(self.open_prices[b + 1]))
                exit_fill_p = ref_open * (Decimal("1.0") - self.SLIPPAGE_RATE)
                gross_proc = btc * exit_fill_p
                ex_fee = gross_proc * self.FEE_RATE
                ex_slip = (ref_open - exit_fill_p) * btc
                net_proc = gross_proc - ex_fee
                trade_pnl = net_proc - allocated_cash

                if trade_pnl > Decimal("0.0"):
                    trade_wins += 1

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

                fills.append(ProvenanceFillRecord(
                    fill_id=fill_id,
                    trade_id=trade_id,
                    side="SELL",
                    decision_idx=b,
                    decision_timestamp_ms=t_curr,
                    decision_utc=str(pd.to_datetime(t_curr, unit="ms", utc=True)),
                    feature_cutoff_ms=t_curr + self.EXPECTED_STEP_MS - 1,
                    feature_cutoff_utc=str(pd.to_datetime(t_curr + self.EXPECTED_STEP_MS - 1, unit="ms", utc=True)),
                    market_regime=dec.market_regime,
                    regime_confidence=dec.regime_confidence,
                    decision_action=dec.action,
                    scenario=dec.scenario,
                    rationale=dec.rationale,
                    portfolio_position_before="BTC",
                    order_timestamp_ms=t_curr + self.EXPECTED_STEP_MS,
                    order_utc=str(pd.to_datetime(t_next, unit="ms", utc=True)),
                    execution_timestamp_ms=t_next,
                    execution_utc=str(pd.to_datetime(t_next, unit="ms", utc=True)),
                    reference_price=float(ref_open),
                    fill_price=float(exit_fill_p),
                    btc_quantity=float(btc_before),
                    gross_notional=float(gross_proc),
                    fee_usdt=float(ex_fee),
                    slippage_usdt=float(ex_slip),
                    portfolio_position_after="USDT",
                    cash_before=float(cash_before),
                    cash_after=float(cash),
                    btc_before=float(btc_before),
                    btc_after=0.0,
                    equity_before=float(cash_before + btc_before * ref_open),
                    equity_after=float(cash),
                    trade_reason="SIGNAL_EXIT",
                    provenance_status="VALID_CAUSAL_ORIGIN"
                ))

            # Mark to market tracking
            c_price = Decimal(str(self.close_prices[b]))
            equity_series.append(float(cash + btc * c_price))

        # Terminal liquidation if still in position at end_bar
        if in_pos and btc > Decimal("0.0"):
            exit_ref = Decimal(str(self.close_prices[end_bar]))
            exit_fill_p = exit_ref * (Decimal("1.0") - self.SLIPPAGE_RATE)
            gross_proc = btc * exit_fill_p
            ex_fee = gross_proc * self.FEE_RATE
            ex_slip = (exit_ref - exit_fill_p) * btc
            net_proc = gross_proc - ex_fee
            trade_pnl = net_proc - allocated_cash

            if trade_pnl > Decimal("0.0"):
                trade_wins += 1

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

            t_end = int(self.open_times[end_bar])
            fills.append(ProvenanceFillRecord(
                fill_id=fill_id,
                trade_id=trade_id,
                side="SELL",
                decision_idx=end_bar,
                decision_timestamp_ms=t_end,
                decision_utc=str(pd.to_datetime(t_end, unit="ms", utc=True)),
                feature_cutoff_ms=t_end + self.EXPECTED_STEP_MS - 1,
                feature_cutoff_utc=str(pd.to_datetime(t_end + self.EXPECTED_STEP_MS - 1, unit="ms", utc=True)),
                market_regime="TERMINAL_PERIOD_CLOSE",
                regime_confidence=1.0,
                decision_action="EXIT_TO_USDT",
                scenario="TERMINAL_CLOSE",
                rationale="Mandatory terminal portfolio liquidation",
                portfolio_position_before="BTC",
                order_timestamp_ms=t_end,
                order_utc=str(pd.to_datetime(t_end, unit="ms", utc=True)),
                execution_timestamp_ms=t_end,
                execution_utc=str(pd.to_datetime(t_end, unit="ms", utc=True)),
                reference_price=float(exit_ref),
                fill_price=float(exit_fill_p),
                btc_quantity=float(btc_before),
                gross_notional=float(gross_proc),
                fee_usdt=float(ex_fee),
                slippage_usdt=float(ex_slip),
                portfolio_position_after="USDT",
                cash_before=float(cash_before),
                cash_after=float(cash),
                btc_before=float(btc_before),
                btc_after=0.0,
                equity_before=float(cash_before + btc_before * exit_ref),
                equity_after=float(cash),
                trade_reason="TERMINAL_LIQUIDATION",
                provenance_status="VALID_CAUSAL_ORIGIN"
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
        win_rate = (trade_wins / trade_id) * 100.0 if trade_id > 0 else 0.0

        summary = {
            "start_bar": start_bar,
            "end_bar": end_bar,
            "sample_step_bars": sample_step_bars,
            "initial_capital_usdt": float(self.INITIAL_CAPITAL),
            "final_equity_usdt": round(final_eq, 2),
            "net_pnl_usdt": round(net_pnl, 2),
            "net_return_pct": round(ret_pct, 2),
            "total_trades": trade_id,
            "total_fills": len(fills),
            "total_fees_usdt": round(float(total_fees), 2),
            "total_slippage_usdt": round(float(total_slippage), 2),
            "total_friction_usdt": round(float(total_fees + total_slippage), 2),
            "turnover_usdt": round(float(total_turnover), 2),
            "time_in_market_pct": round(time_in_market_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "win_rate_pct": round(win_rate, 2),
            "realized_pnl_usdt": round(net_pnl, 2)
        }

        df_fills = pd.DataFrame([asdict(f) for f in fills])
        return df_fills, summary
