import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mutual_info_score

from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import CanonicalModelResearchBridge
from coin_behavior_engine.product.btc_timing_research.historical_feature_adapter import HistoricalFeatureAdapter

def compute_incremental():
    bridge = CanonicalModelResearchBridge()
    adapter = HistoricalFeatureAdapter()

    df_2023_raw = pd.read_parquet('data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet')
    res_2023 = bridge.evaluate_historical_dataset(df_2023_raw, 'DS-BTC-1H-2023-2024')
    df_2023 = res_2023.classified_series.copy()
    df_adapt_2023 = adapter.compute_cbe_regimes(df_2023_raw)
    df_2023['derived_regime'] = df_adapt_2023['market_regime']

    df_2025_raw = pd.read_parquet('data/historical/historical_binance_btcusdt_1h_2025.parquet')
    res_2025 = bridge.evaluate_historical_dataset(df_2025_raw, 'DS-BTC-1H-2025-SEALED')
    df_2025 = res_2025.classified_series.copy()
    df_adapt_2025 = adapter.compute_cbe_regimes(df_2025_raw)
    df_2025['derived_regime'] = df_adapt_2025['market_regime']

    df = pd.concat([df_2023, df_2025], ignore_index=True)

    # 1. Forward 24h return & forward 24h MAE
    close = df['close'].astype(float)
    low = df['low'].astype(float)
    df['fwd_ret_24h'] = np.log(close.shift(-24) / close)
    df['fwd_vol_24h'] = df['fwd_ret_24h'].abs()

    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=24)
    df['fwd_mae_24h'] = (low.rolling(window=indexer).min() - close) / close

    # Baseline A: SMA 50/200 Crossover
    sma_50 = close.rolling(50).mean()
    sma_200 = close.rolling(200).mean()
    df['baseline_a_sma'] = np.where(sma_50 > sma_200, 'BULLISH', 'BEARISH')

    # Baseline B: Rolling Parkinson Volatility Quantiles
    p_vol = df['volatility_parkinson_24h']
    q_low = p_vol.quantile(0.33)
    q_high = p_vol.quantile(0.66)
    df['baseline_b_vol'] = np.where(p_vol < q_low, 'LOW_VOL', np.where(p_vol > q_high, 'HIGH_VOL', 'MID_VOL'))

    # Baseline C: Derived Research Regime (historical_feature_adapter)
    # Baseline D: Canonical CBE-0.7.0 Regime (canonical_regime)

    baselines = {
        "Baseline A: SMA 50/200 Trend": "baseline_a_sma",
        "Baseline B: Parkinson Volatility Quantile": "baseline_b_vol",
        "Baseline C: Derived Research Heuristic": "derived_regime",
        "Baseline D: Canonical CBE-0.7.0 (Bridge)": "canonical_regime",
    }

    eval_results = {}
    valid_df = df.dropna(subset=['fwd_ret_24h', 'fwd_mae_24h'])

    for name, col in baselines.items():
        groups = [group['fwd_ret_24h'].values for _, group in valid_df.groupby(col)]
        groups_mae = [group['fwd_mae_24h'].values for _, group in valid_df.groupby(col)]

        # ANOVA on 24h returns
        f_stat, p_val = stats.f_oneway(*groups)
        kw_stat, kw_p = stats.kruskal(*groups)

        # Risk differentiation: Max CVaR difference across regimes
        cvars = []
        for g in groups:
            p05 = np.percentile(g, 5)
            tail = g[g <= p05]
            cvars.append(tail.mean())
        cvar_spread = max(cvars) - min(cvars)

        # MAE spread
        mean_maes = [g.mean() for g in groups_mae]
        mae_spread = max(mean_maes) - min(mean_maes)

        # Mutual information with discrete forward returns (e.g. quintiles)
        ret_quantiles = pd.qcut(valid_df['fwd_ret_24h'], 5, labels=False)
        mi = mutual_info_score(valid_df[col].astype(str), ret_quantiles)

        eval_results[name] = {
            "anova_f_stat": float(round(f_stat, 4)),
            "anova_p_val": float(round(p_val, 6)),
            "kruskal_h_stat": float(round(kw_stat, 4)),
            "kruskal_p_val": float(round(kw_p, 6)),
            "cvar_spread_pct": float(round(cvar_spread * 100.0, 4)),
            "mae_spread_pct": float(round(mae_spread * 100.0, 4)),
            "mutual_info_score": float(round(mi, 4)),
        }

    print("Incremental Evaluation Results:")
    for k, v in eval_results.items():
        print(f"\n{k}:")
        for ik, iv in v.items():
            print(f"  {ik}: {iv}")

    # Output JSON summary to be referenced in 08_incremental_value_assessment.md
    with open("scripts/incremental_stats.json", "w") as f:
        json.dump(eval_results, f, indent=2)

if __name__ == '__main__':
    compute_incremental()
