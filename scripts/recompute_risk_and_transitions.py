import pandas as pd
import numpy as np
from coin_behavior_engine.product.market_behavior_analytics import MarketBehaviorAnalyticsEngine

engine = MarketBehaviorAnalyticsEngine.get_instance()
df_1h = engine.load_hourly_series()
print(f"Total hourly bars: {len(df_1h)}")
print(f"Start: {df_1h['datetime'].min()}, End: {df_1h['datetime'].max()}")

# Year breakdown
df_1h["year"] = pd.to_datetime(df_1h["datetime"]).dt.year
print("\nYearly bar counts:")
for yr, cnt in df_1h["year"].value_counts().sort_index().items():
    print(f"  {yr}: {cnt} bars")

# Transition matrix analysis
trans_res = engine.get_transition_matrix()
matrix_prob = trans_res["transition_probabilities"]
matrix_counts = trans_res["transition_counts"]
regimes = trans_res["canonical_regimes"]
total_transitions = trans_res["total_transitions"]

print(f"\nTotal transitions reported: {total_transitions}")

print("\n6x6 Transition Matrix (Row Probabilities):")
for r_from in regimes:
    row = matrix_prob[r_from]
    row_sum = sum(row.values())
    probs_str = ", ".join([f"{r_to}: {p:.4f}" for r_to, p in row.items()])
    print(f"  {r_from:<18} (sum: {row_sum:.4f}) -> {probs_str}")

print("\n6x6 Transition Matrix (Raw Counts):")
for r_from in regimes:
    row = matrix_counts[r_from]
    row_sum = sum(row.values())
    counts_str = ", ".join([f"{r_to}: {c}" for r_to, c in row.items()])
    print(f"  {r_from:<18} (sum: {row_sum:<5}) -> {counts_str}")

# Risk metrics check
risk = engine.get_market_risk_metrics()
print("\nRisk metrics:")
print("Historical Drawdown:", risk["historical_drawdown"])
print("Downside Risk:", risk["downside_risk"])

# Let's verify drawdown independently
closes = df_1h["close"].values
running_max = np.maximum.accumulate(closes)
dds = (closes - running_max) / running_max
min_dd_idx = np.argmin(dds)
max_dd = dds[min_dd_idx]
peak_idx = np.argmax(closes[:min_dd_idx+1])

print(f"\nIndependent Drawdown Verification:")
print(f"  Max Drawdown: {max_dd * 100:.2f}%")
print(f"  Peak Index: {peak_idx}, Time: {df_1h['datetime'].iloc[peak_idx]}, Price: {closes[peak_idx]}")
print(f"  Trough Index: {min_dd_idx}, Time: {df_1h['datetime'].iloc[min_dd_idx]}, Price: {closes[min_dd_idx]}")

# Downside deviation check
returns = df_1h["return"].dropna().values
neg_returns = returns[returns < 0]
downside_dev_hourly = np.std(neg_returns, ddof=1) if len(neg_returns) > 1 else 0.0
downside_dev_annual = downside_dev_hourly * np.sqrt(8760) * 100
print(f"\nIndependent Downside Deviation Verification:")
print(f"  Hourly Downside Dev: {downside_dev_hourly * 100:.4f}%")
print(f"  Annualized Downside Dev: {downside_dev_annual:.2f}%")

# VaR and CVaR check
losses = -returns
var_95 = np.percentile(losses, 95) * 100
var_99 = np.percentile(losses, 99) * 100
cvar_95 = np.mean(losses[losses >= np.percentile(losses, 95)]) * 100
cvar_99 = np.mean(losses[losses >= np.percentile(losses, 99)]) * 100
print(f"\nIndependent VaR & CVaR Verification:")
print(f"  1h VaR 95%: {var_95:.2f}%")
print(f"  1h VaR 99%: {var_99:.2f}%")
print(f"  1h CVaR 95%: {cvar_95:.2f}%")
print(f"  1h CVaR 99%: {cvar_99:.2f}%")
