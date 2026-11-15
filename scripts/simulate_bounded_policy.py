import json
from pathlib import Path
import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import CanonicalModelResearchBridge

def simulate_bounded_policy():
    bridge = CanonicalModelResearchBridge()

    df_2023_raw = pd.read_parquet('data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet')
    res_2023 = bridge.evaluate_historical_dataset(df_2023_raw, 'DS-BTC-1H-2023-2024')
    df_2023 = res_2023.classified_series.copy()

    df_2025_raw = pd.read_parquet('data/historical/historical_binance_btcusdt_1h_2025.parquet')
    res_2025 = bridge.evaluate_historical_dataset(df_2025_raw, 'DS-BTC-1H-2025-SEALED')
    df_2025 = res_2025.classified_series.copy()

    def run_backtest(df, initial_capital=10000.0, fee_bps=10.0, slippage_bps=5.0):
        close = df['close'].values
        regimes = df['canonical_regime'].values
        n = len(df)
        cost_rate = (fee_bps + slippage_bps) / 10000.0

        # Policy 1: Buy and Hold
        bnh_equity = initial_capital * (close / close[0])
        bnh_dd = (bnh_equity - np.maximum.accumulate(bnh_equity)) / np.maximum.accumulate(bnh_equity)

        # Policy 2: Bounded Canonical Tail-Protection Policy
        # Exposure = 1.0 normally; 0.2 during TAIL_RISK_ELEVATED
        # Hysteresis: only switch if regime persists for >= 3 consecutive hours
        target_target = np.ones(n)
        for i in range(n):
            if regimes[i] == 'TAIL_RISK_ELEVATED':
                target_target[i] = 0.20
            else:
                target_target[i] = 1.0

        # Apply 3-hour confirmation filter
        smooth_exposure = np.ones(n)
        curr_exp = 1.0
        pending_exp = 1.0
        pending_count = 0

        for i in range(n):
            t = target_target[i]
            if t != curr_exp:
                if t == pending_exp:
                    pending_count += 1
                    if pending_count >= 3:
                        curr_exp = t
                        pending_count = 0
                else:
                    pending_exp = t
                    pending_count = 1
            else:
                pending_count = 0
            smooth_exposure[i] = curr_exp

        # Simulate equity
        cash = initial_capital * (1.0 - smooth_exposure[0])
        btc = (initial_capital * smooth_exposure[0]) / close[0]
        # initial cost
        cash -= (btc * close[0]) * cost_rate

        equity = np.zeros(n)
        trades = 0
        total_costs = (btc * close[0]) * cost_rate

        for i in range(n):
            total_val = cash + btc * close[i]
            equity[i] = total_val
            target_w = smooth_exposure[i]
            curr_w = (btc * close[i]) / total_val if total_val > 0 else 0

            # Rebalance if weight difference > 0.05
            if abs(target_w - curr_w) > 0.05:
                target_btc_val = total_val * target_w
                trade_val = abs(target_btc_val - btc * close[i])
                fee = trade_val * cost_rate
                total_costs += fee
                trades += 1
                if target_btc_val > btc * close[i]:
                    # buy
                    cash -= (trade_val + fee)
                    btc = target_btc_val / close[i]
                else:
                    # sell
                    cash += (trade_val - fee)
                    btc = target_btc_val / close[i]

        bounded_dd = (equity - np.maximum.accumulate(equity)) / np.maximum.accumulate(equity)

        return {
            "initial_capital": initial_capital,
            "bnh_final_equity": float(round(bnh_equity[-1], 2)),
            "bnh_max_drawdown_pct": float(round(bnh_dd.min() * 100.0, 2)),
            "bnh_trades": 1,
            "bnh_total_cost": float(round(initial_capital * cost_rate, 2)),
            "bounded_final_equity": float(round(equity[-1], 2)),
            "bounded_max_drawdown_pct": float(round(bounded_dd.min() * 100.0, 2)),
            "bounded_trades": trades,
            "bounded_total_cost": float(round(total_costs, 2)),
        }

    res_2023 = run_backtest(df_2023)
    res_2025 = run_backtest(df_2025)

    print("2023-2024 Simulation:", res_2023)
    print("2025 Simulation:", res_2025)

    out = {
        "simulation_2023_2024": res_2023,
        "simulation_2025": res_2025,
    }
    with open("scripts/bounded_policy_simulation.json", "w") as f:
        json.dump(out, f, indent=2)

if __name__ == '__main__':
    simulate_bounded_policy()
