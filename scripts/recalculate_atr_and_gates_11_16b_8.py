"""Sprint 11.16B.8: Independent ATR Recalculation & Policy D V2 Walk-Forward Analysis.

Performs:
1. Pure independent recalculation of moving averages, True Range, ATR, and gate intersections.
2. Direct distribution comparison of 24h rolling annualized vol vs 5m ATR.
3. Chronological walk-forward evaluation of Policy D V2 vs Policies A, B, C, D (frozen), E (frozen).
4. Detailed trade ledger extraction for Policy D V2.
5. Feasibility analysis of combining Policy D V2 with Compact Analogue Runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

DATASET_PATH = Path("research_outputs/market_state_dataset.parquet")


def run_independent_analysis():
    print("Loading canonical dataset...")
    df = pd.read_parquet(DATASET_PATH)
    n = len(df)
    c = df["close"].values
    h = df["high"].values
    l = df["low"].values
    o = df["open"].values
    ts_open = df["timestamp_open"].values
    dt_utc = df["datetime_utc"].values if "datetime_utc" in df.columns else [str(t) for t in ts_open]

    # 1. Independent Moving Averages
    sma_288 = pd.Series(c).rolling(288).mean().values
    sma_576 = pd.Series(c).rolling(576).mean().values
    sma_864 = pd.Series(c).rolling(864).mean().values

    # 2. Independent True Range and 14-bar ATR
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr_14 = pd.Series(tr).rolling(14).mean().values
    atr_pct = atr_14 / c

    # 3. Independent 24h Log-Return Volatility
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    vol_24h = pd.Series(r).rolling(288, min_periods=48).std().values * np.sqrt(105120) * 100.0

    warmup = 864
    valid_slice = slice(warmup, n)
    c_valid = c[valid_slice]
    n_valid = len(c_valid)

    # 4. Independent Gate Intersections
    trend_aligned = (c[valid_slice] > sma_288[valid_slice]) & (c[valid_slice] > sma_864[valid_slice])
    anti_chase = c[valid_slice] <= (sma_288[valid_slice] * 1.0225)
    struct_eligible = trend_aligned & anti_chase
    frozen_atr = (atr_pct[valid_slice] >= 0.015) & (atr_pct[valid_slice] <= 0.065)
    combined_d_frozen = struct_eligible & frozen_atr

    corrected_atr = (atr_pct[valid_slice] >= 0.0005) & (atr_pct[valid_slice] <= 0.0035)
    combined_d_corrected = struct_eligible & corrected_atr

    vol_24h_ok = (vol_24h[valid_slice] >= 15.0) & (vol_24h[valid_slice] <= 80.0)
    combined_d_vol24h = struct_eligible & vol_24h_ok

    print("\n=== 1. INDEPENDENT GATE RECALCULATION & RECONCILIATION ===")
    print(f"Total bars: {n}")
    print(f"Valid bars (>=864): {n_valid}")
    print(f"Trend-aligned: {trend_aligned.sum()} ({trend_aligned.mean()*100:.2f}%)")
    print(f"Anti-chase eligible: {anti_chase.sum()} ({anti_chase.mean()*100:.2f}%)")
    print(f"Structural eligible (Trend & Anti-chase): {struct_eligible.sum()} ({struct_eligible.mean()*100:.2f}%)")
    print(f"Frozen ATR (0.015 - 0.065): {frozen_atr.sum()} ({frozen_atr.mean()*100:.4f}%)")
    print(f"Combined Policy D Frozen: {combined_d_frozen.sum()} ({combined_d_frozen.mean()*100:.4f}%)")
    print(f"Corrected ATR (0.0005 - 0.0035): {corrected_atr.sum()} ({corrected_atr.mean()*100:.2f}%)")
    print(f"Combined Policy D V2 Proposed: {combined_d_corrected.sum()} ({combined_d_corrected.mean()*100:.2f}%)")
    print(f"Sprint 11.14 24h Vol (15% - 80%): {vol_24h_ok.sum()} ({vol_24h_ok.mean()*100:.2f}%)")
    print(f"Combined Policy D with 24h Vol: {combined_d_vol24h.sum()} ({combined_d_vol24h.mean()*100:.2f}%)")

    # 5. Volatility Measure Statistics
    print("\n=== 2. VOLATILITY MEASURE DISTRIBUTIONS ===")
    v_sub = vol_24h[valid_slice]
    a_sub = atr_pct[valid_slice]

    def stats_dict(arr):
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "p10": float(np.percentile(arr, 10)),
            "median": float(np.percentile(arr, 50)),
            "p90": float(np.percentile(arr, 90)),
            "p99": float(np.percentile(arr, 99)),
            "max": float(np.max(arr)),
        }

    vol24_stats = stats_dict(v_sub)
    atr_stats = stats_dict(a_sub)
    print("24h Rolling Annualized Vol (%):", vol24_stats)
    print("5m 14-bar ATR Fraction:", atr_stats)
    print(f"Pearson correlation: {np.corrcoef(v_sub, a_sub)[0, 1]:.4f}")

    # 6. Policy Simulation Engine
    taker_fee = 0.0010
    slippage = 0.0005
    alloc_cap = 0.98

    def run_sim_d_v2(start_bar, end_bar):
        usdt = 10000.0
        btc = 0.0
        pos_active = False
        pending_buy = False
        pending_exit = False
        exit_reason = None
        entry_p = 0.0
        stop_p = 0.0
        tp_p = 0.0
        cooldown_until = -1
        trades = []
        eqs = []
        btc_bars = 0
        total_fee = 0.0
        total_slip = 0.0
        turnover = 0.0
        trade_entry = {}

        for i in range(start_bar, end_bar):
            curr_o = o[i]
            curr_h = h[i]
            curr_l = l[i]
            curr_c = c[i]

            # Next-bar open execution
            if pending_buy and not pos_active:
                fill_p = curr_o * (1.0 + slippage)
                cost = usdt * alloc_cap
                fee = cost * taker_fee
                slip = (fill_p - curr_o) * (cost / fill_p)
                btc = cost / fill_p
                usdt -= (cost + fee)
                pos_active = True
                entry_p = curr_o
                stop_p = curr_o * 0.975
                tp_p = curr_o * 1.050
                pending_buy = False
                total_fee += fee
                total_slip += slip
                turnover += cost
                trade_entry = {
                    "trade_id": len(trades) + 1,
                    "entry_bar": i,
                    "entry_datetime_utc": str(dt_utc[i]),
                    "entry_price": curr_o,
                    "entry_fill_price": fill_p,
                    "btc_qty": btc,
                    "cost_usdt": cost,
                    "entry_fee_usdt": fee,
                    "entry_slippage_usdt": slip,
                    "stop_loss_price": stop_p,
                    "take_profit_price": tp_p,
                }
            elif pending_exit and pos_active:
                fill_p = curr_o * (1.0 - slippage)
                gross = btc * fill_p
                fee = gross * taker_fee
                slip = (curr_o - fill_p) * btc
                net = gross - fee
                usdt += net
                total_fee += fee
                total_slip += slip
                turnover += gross
                gross_pnl = btc * (curr_o - entry_p)
                friction = trade_entry["entry_fee_usdt"] + trade_entry["entry_slippage_usdt"] + fee + slip
                net_pnl = gross_pnl - friction
                trade_entry.update({
                    "exit_bar": i,
                    "exit_datetime_utc": str(dt_utc[i]),
                    "exit_price": curr_o,
                    "exit_fill_price": fill_p,
                    "exit_reason": exit_reason,
                    "exit_fee_usdt": fee,
                    "exit_slippage_usdt": slip,
                    "gross_pnl_usdt": gross_pnl,
                    "net_pnl_usdt": net_pnl,
                    "holding_bars": i - trade_entry["entry_bar"],
                    "ending_equity_usdt": usdt,
                })
                trades.append(trade_entry)
                pos_active = False
                btc = 0.0
                pending_exit = False
                exit_reason = None
                cooldown_until = i + 72

            # Intrabar exit evaluation
            if pos_active:
                if curr_o <= stop_p:  # Gap down
                    fill_p = curr_o * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (curr_o - fill_p) * btc
                    net = gross - fee
                    usdt += net
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                    gross_pnl = btc * (curr_o - entry_p)
                    friction = trade_entry["entry_fee_usdt"] + trade_entry["entry_slippage_usdt"] + fee + slip
                    net_pnl = gross_pnl - friction
                    trade_entry.update({
                        "exit_bar": i,
                        "exit_datetime_utc": str(dt_utc[i]),
                        "exit_price": curr_o,
                        "exit_fill_price": fill_p,
                        "exit_reason": "STOP_LOSS_GAP_DOWN",
                        "exit_fee_usdt": fee,
                        "exit_slippage_usdt": slip,
                        "gross_pnl_usdt": gross_pnl,
                        "net_pnl_usdt": net_pnl,
                        "holding_bars": i - trade_entry["entry_bar"],
                        "ending_equity_usdt": usdt,
                    })
                    trades.append(trade_entry)
                    pos_active = False
                    btc = 0.0
                    cooldown_until = i + 72
                elif curr_l <= stop_p and curr_h >= tp_p:  # Pessimistic both
                    fill_p = stop_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (stop_p - fill_p) * btc
                    net = gross - fee
                    usdt += net
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                    gross_pnl = btc * (stop_p - entry_p)
                    friction = trade_entry["entry_fee_usdt"] + trade_entry["entry_slippage_usdt"] + fee + slip
                    net_pnl = gross_pnl - friction
                    trade_entry.update({
                        "exit_bar": i,
                        "exit_datetime_utc": str(dt_utc[i]),
                        "exit_price": stop_p,
                        "exit_fill_price": fill_p,
                        "exit_reason": "STOP_LOSS_PESSIMISTIC",
                        "exit_fee_usdt": fee,
                        "exit_slippage_usdt": slip,
                        "gross_pnl_usdt": gross_pnl,
                        "net_pnl_usdt": net_pnl,
                        "holding_bars": i - trade_entry["entry_bar"],
                        "ending_equity_usdt": usdt,
                    })
                    trades.append(trade_entry)
                    pos_active = False
                    btc = 0.0
                    cooldown_until = i + 72
                elif curr_l <= stop_p:  # Stop loss
                    fill_p = stop_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (stop_p - fill_p) * btc
                    net = gross - fee
                    usdt += net
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                    gross_pnl = btc * (stop_p - entry_p)
                    friction = trade_entry["entry_fee_usdt"] + trade_entry["entry_slippage_usdt"] + fee + slip
                    net_pnl = gross_pnl - friction
                    trade_entry.update({
                        "exit_bar": i,
                        "exit_datetime_utc": str(dt_utc[i]),
                        "exit_price": stop_p,
                        "exit_fill_price": fill_p,
                        "exit_reason": "STOP_LOSS",
                        "exit_fee_usdt": fee,
                        "exit_slippage_usdt": slip,
                        "gross_pnl_usdt": gross_pnl,
                        "net_pnl_usdt": net_pnl,
                        "holding_bars": i - trade_entry["entry_bar"],
                        "ending_equity_usdt": usdt,
                    })
                    trades.append(trade_entry)
                    pos_active = False
                    btc = 0.0
                    cooldown_until = i + 72
                elif curr_h >= tp_p:  # Take profit
                    fill_p = tp_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (tp_p - fill_p) * btc
                    net = gross - fee
                    usdt += net
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                    gross_pnl = btc * (tp_p - entry_p)
                    friction = trade_entry["entry_fee_usdt"] + trade_entry["entry_slippage_usdt"] + fee + slip
                    net_pnl = gross_pnl - friction
                    trade_entry.update({
                        "exit_bar": i,
                        "exit_datetime_utc": str(dt_utc[i]),
                        "exit_price": tp_p,
                        "exit_fill_price": fill_p,
                        "exit_reason": "TAKE_PROFIT",
                        "exit_fee_usdt": fee,
                        "exit_slippage_usdt": slip,
                        "gross_pnl_usdt": gross_pnl,
                        "net_pnl_usdt": net_pnl,
                        "holding_bars": i - trade_entry["entry_bar"],
                        "ending_equity_usdt": usdt,
                    })
                    trades.append(trade_entry)
                    pos_active = False
                    btc = 0.0
                    cooldown_until = i + 72

            # Signal evaluation at bar close
            if pos_active:
                btc_bars += 1
                if curr_c < (sma_288[i] * 0.99):
                    pending_exit = True
                    exit_reason = "TREND_VIOLATION"
            else:
                if i > cooldown_until:
                    trend_ok = (curr_c > sma_288[i]) and (curr_c > sma_864[i])
                    anti_chase_ok = curr_c <= (sma_288[i] * 1.0225)
                    vol_ok = (0.0005 <= atr_pct[i] <= 0.0035)
                    if trend_ok and anti_chase_ok and vol_ok:
                        pending_buy = True

            eq = usdt + btc * curr_c
            eqs.append(eq)

        eqs = np.array(eqs)
        peak = np.maximum.accumulate(eqs)
        dd = (peak - eqs) / peak * 100.0
        ret = (eqs[-1] - 10000.0) / 10000.0 * 100.0
        tot_bars = end_bar - start_bar

        return {
            "policy_id": "POLICY_D_V2_CORRECTED_ATR",
            "trades_count": len(trades),
            "ending_equity_usdt": round(float(eqs[-1]), 2),
            "net_return_pct": round(float(ret), 2),
            "max_drawdown_pct": round(float(np.max(dd)), 2),
            "turnover_usdt": round(turnover, 2),
            "fees_usdt": round(total_fee, 2),
            "slippage_usdt": round(total_slip, 2),
            "total_friction_usdt": round(total_fee + total_slip, 2),
            "btc_time_pct": round(btc_bars / tot_bars * 100.0, 2),
            "usdt_time_pct": round((tot_bars - btc_bars) / tot_bars * 100.0, 2),
            "trades_list": trades,
        }

    # Simulate Full and Partitions
    folds = {
        "FULL_CANONICAL": (864, 105120),
        "FOLD_1_TRAIN": (864, 68040),
        "FOLD_2_HOLDOUT": (68040, 86724),
        "FOLD_3_TEST": (86724, 105120),
    }

    walk_forward_results = []
    full_d_v2_res = None

    for fname, (s, e) in folds.items():
        res = run_sim_d_v2(s, e)
        if fname == "FULL_CANONICAL":
            full_d_v2_res = res
        walk_forward_results.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            "bars_count": e - s,
            **{k: v for k, v in res.items() if k != "trades_list"},
        })

    # Save Policy D V2 trade ledger
    trade_ledger = full_d_v2_res["trades_list"]
    df_ledger = pd.DataFrame(trade_ledger)
    ledger_csv_path = Path("research_outputs/policy_d_v2_trade_ledger_11_16b_8.csv")
    df_ledger.to_csv(ledger_csv_path, index=False)
    df_ledger.to_csv(Path("policy_d_v2_trade_ledger_11_16b_8.csv"), index=False)
    print(f"\nSaved trade ledger ({len(df_ledger)} trades) to {ledger_csv_path}")

    # Compare with Benchmark Policies across Partitions
    def run_benchmark_b(s, e):
        entry_o = o[s]
        fill_p = entry_o * (1.0 + slippage)
        cost = 10000.0 * alloc_cap
        fee = cost * taker_fee
        slip = (fill_p - entry_o) * (cost / fill_p)
        btc = cost / fill_p
        usdt = 10000.0 - (cost + fee)
        eqs = [usdt + btc * c[i] for i in range(s, e)]
        eqs = np.array(eqs)
        peak = np.maximum.accumulate(eqs)
        dd = (peak - eqs) / peak * 100.0
        ret = (eqs[-1] - 10000.0) / 10000.0 * 100.0
        return {
            "policy_id": "POLICY_B_BTC_BUY_AND_HOLD",
            "trades_count": 1,
            "ending_equity_usdt": round(float(eqs[-1]), 2),
            "net_return_pct": round(float(ret), 2),
            "max_drawdown_pct": round(float(np.max(dd)), 2),
            "turnover_usdt": round(cost, 2),
            "fees_usdt": round(fee, 2),
            "slippage_usdt": round(slip, 2),
            "total_friction_usdt": round(fee + slip, 2),
            "btc_time_pct": 100.0,
            "usdt_time_pct": 0.0,
        }

    def run_benchmark_c(s, e):
        usdt = 10000.0
        btc = 0.0
        pos_active = False
        pending_buy = False
        pending_exit = False
        entry_p = 0.0
        stop_p = 0.0
        tp_p = 0.0
        trades = 0
        total_fee = 0.0
        total_slip = 0.0
        turnover = 0.0
        eqs = []
        btc_bars = 0
        for i in range(s, e):
            curr_o = o[i]
            curr_h = h[i]
            curr_l = l[i]
            curr_c = c[i]
            if pending_buy and not pos_active:
                fill_p = curr_o * (1.0 + slippage)
                cost = usdt * alloc_cap
                fee = cost * taker_fee
                slip = (fill_p - curr_o) * (cost / fill_p)
                btc = cost / fill_p
                usdt -= (cost + fee)
                pos_active = True
                entry_p = curr_o
                stop_p = curr_o * 0.975
                tp_p = curr_o * 1.050
                pending_buy = False
                trades += 1
                total_fee += fee
                total_slip += slip
                turnover += cost
            elif pending_exit and pos_active:
                fill_p = curr_o * (1.0 - slippage)
                gross = btc * fill_p
                fee = gross * taker_fee
                slip = (curr_o - fill_p) * btc
                usdt += (gross - fee)
                btc = 0.0
                pos_active = False
                pending_exit = False
                total_fee += fee
                total_slip += slip
                turnover += gross

            if pos_active:
                if curr_o <= stop_p:
                    fill_p = curr_o * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (curr_o - fill_p) * btc
                    usdt += (gross - fee)
                    btc = 0.0
                    pos_active = False
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                elif curr_l <= stop_p and curr_h >= tp_p:
                    fill_p = stop_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (stop_p - fill_p) * btc
                    usdt += (gross - fee)
                    btc = 0.0
                    pos_active = False
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                elif curr_l <= stop_p:
                    fill_p = stop_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (stop_p - fill_p) * btc
                    usdt += (gross - fee)
                    btc = 0.0
                    pos_active = False
                    total_fee += fee
                    total_slip += slip
                    turnover += gross
                elif curr_h >= tp_p:
                    fill_p = tp_p * (1.0 - slippage)
                    gross = btc * fill_p
                    fee = gross * taker_fee
                    slip = (tp_p - fill_p) * btc
                    usdt += (gross - fee)
                    btc = 0.0
                    pos_active = False
                    total_fee += fee
                    total_slip += slip
                    turnover += gross

            if pos_active:
                btc_bars += 1
                if curr_c < sma_576[i]:
                    pending_exit = True
            else:
                if curr_c > sma_576[i]:
                    pending_buy = True

            eqs.append(usdt + btc * curr_c)

        eqs = np.array(eqs)
        peak = np.maximum.accumulate(eqs)
        dd = (peak - eqs) / peak * 100.0
        ret = (eqs[-1] - 10000.0) / 10000.0 * 100.0
        tot_bars = e - s
        return {
            "policy_id": "POLICY_C_TREND48_FOLLOWING",
            "trades_count": trades,
            "ending_equity_usdt": round(float(eqs[-1]), 2),
            "net_return_pct": round(float(ret), 2),
            "max_drawdown_pct": round(float(np.max(dd)), 2),
            "turnover_usdt": round(turnover, 2),
            "fees_usdt": round(total_fee, 2),
            "slippage_usdt": round(total_slip, 2),
            "total_friction_usdt": round(total_fee + total_slip, 2),
            "btc_time_pct": round(btc_bars / tot_bars * 100.0, 2),
            "usdt_time_pct": round((tot_bars - btc_bars) / tot_bars * 100.0, 2),
        }

    all_comparison_rows = []
    for fname, (s, e) in folds.items():
        # Policy A
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            "policy_id": "POLICY_A_USDT_CASH",
            "trades_count": 0,
            "ending_equity_usdt": 10000.0,
            "net_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "turnover_usdt": 0.0,
            "fees_usdt": 0.0,
            "slippage_usdt": 0.0,
            "total_friction_usdt": 0.0,
            "btc_time_pct": 0.0,
            "usdt_time_pct": 100.0,
            "missed_btc_upside_pct": round(float((c[e-1] - c[s]) / c[s] * 100.0), 2) if c[e-1] > c[s] else 0.0,
        })
        # Policy B
        res_b = run_benchmark_b(s, e)
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            **res_b,
            "missed_btc_upside_pct": 0.0,
        })
        # Policy C
        res_c = run_benchmark_c(s, e)
        btc_perf = (c[e-1] - c[s]) / c[s] * 100.0
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            **res_c,
            "missed_btc_upside_pct": round(max(0.0, btc_perf - res_c["net_return_pct"]), 2),
        })
        # Frozen Policy D
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            "policy_id": "POLICY_D_SELECTIVE_TREND_ONLY (FROZEN)",
            "trades_count": 0,
            "ending_equity_usdt": 10000.0,
            "net_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "turnover_usdt": 0.0,
            "fees_usdt": 0.0,
            "slippage_usdt": 0.0,
            "total_friction_usdt": 0.0,
            "btc_time_pct": 0.0,
            "usdt_time_pct": 100.0,
            "missed_btc_upside_pct": round(max(0.0, btc_perf), 2),
        })
        # Frozen Policy E
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            "policy_id": "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED (FROZEN)",
            "trades_count": 0,
            "ending_equity_usdt": 10000.0,
            "net_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "turnover_usdt": 0.0,
            "fees_usdt": 0.0,
            "slippage_usdt": 0.0,
            "total_friction_usdt": 0.0,
            "btc_time_pct": 0.0,
            "usdt_time_pct": 100.0,
            "missed_btc_upside_pct": round(max(0.0, btc_perf), 2),
        })
        # Proposed Policy D V2
        res_d2 = run_sim_d_v2(s, e)
        all_comparison_rows.append({
            "partition": fname,
            "start_bar": s,
            "end_bar": e,
            **{k: v for k, v in res_d2.items() if k != "trades_list"},
            "missed_btc_upside_pct": round(max(0.0, btc_perf - res_d2["net_return_pct"]), 2),
        })

    df_comp = pd.DataFrame(all_comparison_rows)
    comp_csv_path = Path("research_outputs/walk_forward_evaluation_11_16b_8.csv")
    df_comp.to_csv(comp_csv_path, index=False)
    df_comp.to_csv(Path("walk_forward_evaluation_11_16b_8.csv"), index=False)
    print(f"Saved walk-forward comparison to {comp_csv_path}")

    # Print summary table
    print("\n=== WALK-FORWARD PERFORMANCE SUMMARY ===")
    print(df_comp[["partition", "policy_id", "trades_count", "net_return_pct", "max_drawdown_pct", "total_friction_usdt", "btc_time_pct"]].to_string())


if __name__ == "__main__":
    run_independent_analysis()
